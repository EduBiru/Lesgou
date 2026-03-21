import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .maestro import (
    AZURE_OPENAI_DEPLOYMENT_ENV,
    AZURE_OPENAI_ENDPOINT_ENV,
    AZURE_OPENAI_API_VERSION_ENV,
    DEFAULT_GOOGLE_MODEL,
    DEFAULT_NIL_MODEL,
    GITHUB_TOKEN_ENV,
    GOOGLE_API_KEY_ENV,
    GOOGLE_MODEL_ENV,
    NIL_MODEL_ENV,
    NIL_PROVIDER_ENV,
    carregar_memoria_e_turn_id,
    criar_turno,
    parse_input_usuario,
    responder_gemini_google,
    responder_nil,
    salvar_turno_txt,
)

app = FastAPI(title="Armada do Silício - Maestro API")

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"
UPLOADS_DIR = BASE_DIR / "uploads"
DOWNLOADS_DIR = BASE_DIR / "downloads"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

if WEB_DIR.exists():
    app.mount("/web", StaticFiles(directory=str(WEB_DIR)), name="web")


class ChatRequest(BaseModel):
    text: str
    target: str | None = None  # "nil" | "gemini" | "ambos" | None
    attachment_ids: list[str] = Field(default_factory=list)
    attachment_mode: str | None = None  # "full" | "summary"


# ---------------------------
# Telemetria por sessão (RAM)
# ---------------------------
TELEMETRY: dict[str, Any] = {
    "session_started_at": time.time(),
    "req_count": 0,
    "last_latency_ms": None,
    "agents": {
        "nil": {"in_words": 0, "in_chars": 0, "out_words": 0, "out_chars": 0, "calls": 0, "last_latency_ms": None},
        "gemini": {"in_words": 0, "in_chars": 0, "out_words": 0, "out_chars": 0, "calls": 0, "last_latency_ms": None},
    },
}

# Upload index em RAM (somente IDs enviados)
UPLOAD_INDEX: dict[str, dict[str, Any]] = {}

# Limites (segurança)
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25MB
# Ajustado pra reduzir chance de 413/tokens_limit em providers menores
MAX_EXTRACT_CHARS_FULL = 80_000
MAX_EXTRACT_CHARS_SUMMARY = 6_000


def _count_words_chars(text: str) -> tuple[int, int]:
    t = (text or "").strip()
    if not t:
        return 0, 0
    words = len([w for w in t.split() if w])
    chars = len(t)
    return words, chars


def _current_status_payload() -> dict[str, Any]:
    nil_provider = os.getenv(NIL_PROVIDER_ENV, "github").strip().lower() or "github"

    if nil_provider == "azure":
        dep = os.getenv(AZURE_OPENAI_DEPLOYMENT_ENV, "").strip() or "?"
        endpoint = os.getenv(AZURE_OPENAI_ENDPOINT_ENV, "").strip()
        api_ver = os.getenv(AZURE_OPENAI_API_VERSION_ENV, "").strip()
        nil_model_label = f"azure:{dep}"
        nil_env_ok = bool(os.getenv("AZURE_OPENAI_API_KEY", "").strip()) and bool(endpoint) and bool(dep)
        extra = {"azure_endpoint": endpoint, "azure_api_version": api_ver}
    else:
        nil_model = os.getenv(NIL_MODEL_ENV, DEFAULT_NIL_MODEL).strip() or DEFAULT_NIL_MODEL
        nil_model_label = nil_model
        nil_env_ok = bool(os.getenv(GITHUB_TOKEN_ENV, "").strip())
        extra = {}

    google_model = os.getenv(GOOGLE_MODEL_ENV, DEFAULT_GOOGLE_MODEL).strip() or DEFAULT_GOOGLE_MODEL

    return {
        "ok": True,
        "models": {"nil": nil_model_label, "gemini": google_model},
        "providers": {"nil": nil_provider},
        "env": {
            "has_nil_credentials": nil_env_ok,
            "has_github_token": bool(os.getenv(GITHUB_TOKEN_ENV, "").strip()),
            "has_google_api_key": bool(os.getenv(GOOGLE_API_KEY_ENV, "").strip()),
        },
        "extra": extra,
    }


def _safe_filename(name: str) -> str:
    name = (name or "arquivo").strip()
    name = re.sub(r"[\\/]+", "_", name)
    name = re.sub(r"[^a-zA-Z0-9._ -]+", "_", name)
    name = name.strip().replace(" ", "_")
    return name or "arquivo"


def _get_upload_path(upload_id: str) -> Path | None:
    meta = UPLOAD_INDEX.get(upload_id)
    if not meta:
        return None
    p = Path(meta["path"]).resolve()
    # hard safety: garante que está dentro de uploads
    if not str(p).startswith(str(UPLOADS_DIR.resolve())):
        return None
    if not p.exists():
        return None
    return p


def _read_text_file(path: Path, max_chars: int) -> str:
    data = path.read_bytes()
    try:
        txt = data.decode("utf-8")
    except UnicodeDecodeError:
        txt = data.decode("latin-1", errors="replace")
    txt = txt.strip()
    if len(txt) > max_chars:
        txt = txt[:max_chars] + "\n\n[...cortado por limite de tamanho...]"
    return txt


def _read_pdf_text(path: Path, max_chars: int) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as e:
        raise RuntimeError("Leitura de PDF requer: pip install pypdf") from e

    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages:
        t = page.extract_text() or ""
        if t.strip():
            parts.append(t)
    txt = "\n\n".join(parts).strip()
    if not txt:
        txt = "[aviso] PDF sem texto extraível (pode ser escaneado)."
    if len(txt) > max_chars:
        txt = txt[:max_chars] + "\n\n[...cortado por limite de tamanho...]"
    return txt


def _read_docx_text(path: Path, max_chars: int) -> str:
    try:
        import docx  # type: ignore
    except Exception as e:
        raise RuntimeError("Leitura de DOCX requer: pip install python-docx") from e

    d = docx.Document(str(path))
    txt = "\n".join([p.text for p in d.paragraphs if p.text is not None]).strip()
    if not txt:
        txt = "[aviso] DOCX sem texto."
    if len(txt) > max_chars:
        txt = txt[:max_chars] + "\n\n[...cortado por limite de tamanho...]"
    return txt


def _image_ocr_text(path: Path, max_chars: int) -> str:
    # OCR opcional
    try:
        from PIL import Image  # type: ignore
    except Exception as e:
        raise RuntimeError("Leitura de imagem requer: pip install pillow") from e

    try:
        import pytesseract  # type: ignore
    except Exception as e:
        raise RuntimeError("OCR de imagem requer: pip install pytesseract (e instalar o Tesseract no Windows)") from e

    img = Image.open(str(path))
    txt = pytesseract.image_to_string(img) or ""
    txt = txt.strip()
    if not txt:
        txt = "[aviso] OCR não retornou texto (ou a imagem não tem texto legível)."
    if len(txt) > max_chars:
        txt = txt[:max_chars] + "\n\n[...cortado por limite de tamanho...]"
    return txt


def _image_meta(path: Path) -> str:
    try:
        from PIL import Image  # type: ignore
    except Exception:
        return f"[imagem] Arquivo: {path.name} (instale pillow para metadados/preview)."

    img = Image.open(str(path))
    return f"[imagem] Arquivo: {path.name} | formato={img.format} | tamanho={img.size[0]}x{img.size[1]} | modo={img.mode}"


def _extract_text(path: Path, max_chars: int) -> str:
    ext = path.suffix.lower()

    if ext in {".txt", ".md", ".py", ".js", ".ts", ".json", ".html", ".css", ".csv", ".log", ".yml", ".yaml"}:
        return _read_text_file(path, max_chars)

    if ext == ".pdf":
        return _read_pdf_text(path, max_chars)

    if ext == ".docx":
        return _read_docx_text(path, max_chars)

    if ext in {".png", ".jpg", ".jpeg", ".webp"}:
        try:
            ocr = _image_ocr_text(path, max_chars)
            return _image_meta(path) + "\n\n" + ocr
        except Exception as e:
            return _image_meta(path) + f"\n\n[aviso] OCR indisponível: {e}"

    raise RuntimeError(f"Extensão não suportada: {ext}")


def _build_attachments_block(attachment_ids: list[str], mode: str | None) -> str:
    if not attachment_ids:
        return ""

    mode = (mode or "full").lower().strip()
    full = mode == "full"
    max_chars = MAX_EXTRACT_CHARS_FULL if full else MAX_EXTRACT_CHARS_SUMMARY

    blocks: list[str] = []
    for upload_id in attachment_ids:
        meta = UPLOAD_INDEX.get(upload_id)
        if not meta:
            blocks.append(f"\n[ANEXO {upload_id}] inválido/expirado.\n")
            continue

        path = _get_upload_path(upload_id)
        if not path:
            blocks.append(f"\n[ANEXO {meta.get('filename','?')}] não encontrado ou fora da pasta uploads.\n")
            continue

        filename = meta["filename"]
        try:
            content = _extract_text(path, max_chars=max_chars).strip()
        except Exception as e:
            content = f"[erro] Falha ao extrair texto: {e}"

        if not content:
            content = "[anexo] vazio"

        blocks.append(
            "\n\n"
            f"[ANEXO: {filename} | modo={mode}]\n"
            "--------------------------\n"
            f"{content}\n"
            "--------------------------\n"
        )

    return "\n".join(blocks)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/status")
def status():
    return _current_status_payload()


@app.get("/api/telemetry")
def telemetry():
    agents = TELEMETRY["agents"]
    total_in_words = agents["nil"]["in_words"] + agents["gemini"]["in_words"]
    total_in_chars = agents["nil"]["in_chars"] + agents["gemini"]["in_chars"]
    total_out_words = agents["nil"]["out_words"] + agents["gemini"]["out_words"]
    total_out_chars = agents["nil"]["out_chars"] + agents["gemini"]["out_chars"]

    return {
        "ok": True,
        "session_uptime_s": int(time.time() - TELEMETRY["session_started_at"]),
        "req_count": TELEMETRY["req_count"],
        "last_latency_ms": TELEMETRY["last_latency_ms"],
        "agents": agents,
        "total": {
            "in_words": total_in_words,
            "in_chars": total_in_chars,
            "out_words": total_out_words,
            "out_chars": total_out_chars,
        },
    }


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    filename = (file.filename or "arquivo").strip()
    safe = _safe_filename(filename)
    ext = Path(safe).suffix.lower()

    allowed = {
        # texto
        ".txt", ".md", ".py", ".js", ".ts", ".json", ".html", ".css", ".csv", ".log", ".yml", ".yaml",
        # docs
        ".pdf", ".docx",
        # imagens
        ".png", ".jpg", ".jpeg", ".webp",
    }

    if ext not in allowed:
        return JSONResponse(
            {"ok": False, "error": f"Tipo não permitido: {ext}. Permitidos: {sorted(allowed)}"},
            status_code=400,
        )

    upload_id = uuid.uuid4().hex
    dest = (UPLOADS_DIR / f"{upload_id}__{safe}").resolve()

    size = 0
    chunks: list[bytes] = []
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > MAX_UPLOAD_BYTES:
            return JSONResponse({"ok": False, "error": "Arquivo grande demais (limite 25MB)."}, status_code=400)
        chunks.append(chunk)

    dest.write_bytes(b"".join(chunks))

    UPLOAD_INDEX[upload_id] = {
        "id": upload_id,
        "filename": filename,
        "path": str(dest),
        "size": size,
        "uploaded_at": time.time(),
        "ext": ext,
    }

    return {"ok": True, "id": upload_id, "filename": filename, "size": size, "ext": ext}


@app.get("/api/attachment/{upload_id}")
def attachment_meta(upload_id: str):
    meta = UPLOAD_INDEX.get(upload_id)
    if not meta:
        return JSONResponse({"ok": False, "error": "Attachment ID inválido/expirado."}, status_code=404)
    return {"ok": True, "attachment": meta}


@app.get("/api/download/{name}")
def download(name: str):
    path = (DOWNLOADS_DIR / name).resolve()
    if not str(path).startswith(str(DOWNLOADS_DIR.resolve())):
        return HTMLResponse("Path inválido.", status_code=400)
    if not path.exists():
        return HTMLResponse("Arquivo não encontrado.", status_code=404)
    return FileResponse(str(path), filename=path.name)


@app.get("/", response_class=HTMLResponse)
def index():
    html_path = WEB_DIR / "FACE2.html"
    if not html_path.exists():
        return HTMLResponse(
            "<h1>FACE2.html não encontrado</h1><p>Crie em web/FACE2.html</p>",
            status_code=404,
        )
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.post("/api/chat")
def chat(req: ChatRequest):
    memoria, turn_id = carregar_memoria_e_turn_id()

    texto = (req.text or "").strip()
    if not texto:
        return {"turns": []}

    TELEMETRY["req_count"] += 1

    attachments_block = _build_attachments_block(req.attachment_ids or [], req.attachment_mode)
    texto_final = texto + attachments_block

    if req.target in {"nil", "gemini", "ambos"}:
        texto_para_parse = f"/para {req.target} {texto_final}"
    else:
        texto_para_parse = texto_final

    targets, mensagem = parse_input_usuario(texto_para_parse)
    if targets is None:
        turno_erro = criar_turno(turn_id, "nil", ["edu"], mensagem, status="completed")
        return {"turns": [turno_erro]}

    turns: list[dict] = []

    turno_edu = criar_turno(turn_id, "edu", targets, mensagem, status="completed")
    memoria.append(turno_edu)
    salvar_turno_txt(turno_edu)
    turns.append(turno_edu)
    turn_id += 1

    in_words, in_chars = _count_words_chars(mensagem)
    for agente_id in targets:
        if agente_id in TELEMETRY["agents"]:
            TELEMETRY["agents"][agente_id]["in_words"] += in_words
            TELEMETRY["agents"][agente_id]["in_chars"] += in_chars

    for agente_id in targets:
        t0 = time.perf_counter()

        if agente_id == "nil":
            resposta = responder_nil(mensagem, memoria)
        elif agente_id == "gemini":
            resposta = responder_gemini_google(mensagem, memoria)
        else:
            resposta = f"[erro] Agente desconhecido: {agente_id}"

        latency_ms = int((time.perf_counter() - t0) * 1000)
        TELEMETRY["last_latency_ms"] = latency_ms

        if agente_id in TELEMETRY["agents"]:
            TELEMETRY["agents"][agente_id]["calls"] += 1
            TELEMETRY["agents"][agente_id]["last_latency_ms"] = latency_ms

            out_words, out_chars = _count_words_chars(resposta)
            TELEMETRY["agents"][agente_id]["out_words"] += out_words
            TELEMETRY["agents"][agente_id]["out_chars"] += out_chars

        turno_agente = criar_turno(turn_id, agente_id, ["edu"], resposta, status="completed")
        memoria.append(turno_agente)
        salvar_turno_txt(turno_agente)
        turns.append(turno_agente)
        turn_id += 1

    return {"turns": turns}