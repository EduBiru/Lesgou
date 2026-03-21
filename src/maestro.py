import os
import re
from collections import deque
from datetime import datetime, timezone
from typing import Any

# Dependencias externas:
# pip install openai google-genai
try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore

try:
    from google import genai
except Exception:  # pragma: no cover
    genai = None  # type: ignore


PARTICIPANTES = {
    "edu": "Eduardo",
    "nil": "Nil",
    "gemini": "Gemini",
}

MEMORIA_MAX_TURNOS = 10

ARQUIVO_HISTORICO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "historico.txt")

# Providers / env vars
NIL_PROVIDER_ENV = "NIL_PROVIDER"  # github | azure

GITHUB_TOKEN_ENV = "GITHUB_TOKEN"
GOOGLE_API_KEY_ENV = "GOOGLE_API_KEY"

NIL_MODEL_ENV = "NIL_MODEL"
GOOGLE_MODEL_ENV = "GOOGLE_MODEL"

DEFAULT_NIL_MODEL = "gpt-4o-mini"  # usado quando NIL_PROVIDER=github
DEFAULT_GOOGLE_MODEL = "gemini-1.5-pro"

# GitHub Models endpoint (OpenAI-compatible)
GITHUB_MODELS_ENDPOINT = "https://models.inference.ai.azure.com"

# Azure OpenAI env vars
AZURE_OPENAI_API_KEY_ENV = "AZURE_OPENAI_API_KEY"
AZURE_OPENAI_ENDPOINT_ENV = "AZURE_OPENAI_ENDPOINT"  # ex: https://nel.openai.azure.com/
AZURE_OPENAI_API_VERSION_ENV = "AZURE_OPENAI_API_VERSION"  # ex: 2025-12-01
AZURE_OPENAI_DEPLOYMENT_ENV = "AZURE_OPENAI_DEPLOYMENT"  # ex: NIL

DEFAULT_AZURE_API_VERSION = "2025-12-01"


def agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def iniciar_sessao_no_txt(caminho: str = ARQUIVO_HISTORICO) -> None:
    parent = os.path.dirname(caminho)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(caminho, "a", encoding="utf-8") as f:
        f.write(f"\n=== SESSAO {agora_iso()} ===\n")


def parse_targets(texto: str) -> list[str]:
    texto_lower = texto.lower()
    targets: list[str] = []

    if re.search(r"\bnil\b", texto_lower):
        targets.append("nil")
    if re.search(r"\bgemini\b", texto_lower):
        targets.append("gemini")

    if not targets:
        targets = ["nil", "gemini"]

    return targets


def parse_input_usuario(texto: str) -> tuple[list[str], str] | tuple[None, str]:
    if not texto.startswith("/para "):
        return parse_targets(texto), texto

    payload = texto[6:].strip()
    if not payload:
        return None, "Uso: /para <nil|gemini|ambos> <mensagem>"

    partes = payload.split(" ", 1)
    if len(partes) < 2:
        return None, "Faltou mensagem. Uso: /para <nil|gemini|ambos> <mensagem>"

    alvo = partes[0].lower().strip()
    mensagem = partes[1].strip()

    if alvo == "nil":
        return ["nil"], mensagem
    if alvo == "gemini":
        return ["gemini"], mensagem
    if alvo in {"ambos", "todos"}:
        return ["nil", "gemini"], mensagem

    return None, "Alvo invalido. Use: nil, gemini, ambos"


def criar_turno(
    turn_id: int,
    quem_fala: str,
    para_quem: list[str],
    mensagem: str,
    status: str = "created",
) -> dict[str, Any]:
    return {
        "turn_id": turn_id,
        "speaker_id": quem_fala,
        "speaker_name": PARTICIPANTES.get(quem_fala, quem_fala),
        "target_id": para_quem,
        "target_name": [PARTICIPANTES.get(p, p) for p in para_quem],
        "text": mensagem,
        "status": status,
        "timestamp": agora_iso(),
    }


def imprimir_turno(turno: dict[str, Any]) -> None:
    speaker = turno["speaker_name"]
    targets = ", ".join(turno["target_name"])
    print(f"\n[{turno['turn_id']}] {speaker} -> {targets}")
    print(f"{turno['text']}")


def imprimir_debug(turno: dict[str, Any]) -> None:
    print(
        "   [debug] "
        f"speaker_id={turno['speaker_id']} "
        f"target_id={turno['target_id']} "
        f"status={turno['status']} "
        f"timestamp={turno['timestamp']}"
    )


def salvar_turno_txt(turno: dict[str, Any], caminho: str = ARQUIVO_HISTORICO) -> None:
    parent = os.path.dirname(caminho)
    if parent:
        os.makedirs(parent, exist_ok=True)

    def _csv(v: list[str]) -> str:
        return ",".join(v)

    text = str(turno.get("text", ""))
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    with open(caminho, "a", encoding="utf-8") as f:
        f.write("\n--- TURNO ---\n")
        f.write(f"turn_id: {turno.get('turn_id')}\n")
        f.write(f"speaker_id: {turno.get('speaker_id')}\n")
        f.write(f"speaker_name: {turno.get('speaker_name')}\n")
        f.write(f"target_id: {_csv(turno.get('target_id', []))}\n")
        f.write(f"target_name: {_csv(turno.get('target_name', []))}\n")
        f.write(f"status: {turno.get('status')}\n")
        f.write(f"timestamp: {turno.get('timestamp')}\n")
        f.write("text:\n")
        f.write(text + "\n")
        f.write("--- FIM_TURNO ---\n")


def _parse_turnos_do_txt(caminho: str) -> list[dict[str, Any]]:
    if not os.path.exists(caminho):
        return []

    with open(caminho, "r", encoding="utf-8") as f:
        linhas = f.read().splitlines()

    turnos: list[dict[str, Any]] = []
    i = 0
    while i < len(linhas):
        if linhas[i].strip() != "--- TURNO ---":
            i += 1
            continue

        i += 1
        t: dict[str, Any] = {}

        while i < len(linhas):
            line = linhas[i]
            if line.strip() == "text:":
                i += 1
                break
            if ": " in line:
                k, v = line.split(": ", 1)
                t[k.strip()] = v.strip()
            i += 1

        text_lines: list[str] = []
        while i < len(linhas) and linhas[i].strip() != "--- FIM_TURNO ---":
            text_lines.append(linhas[i])
            i += 1

        if i < len(linhas) and linhas[i].strip() == "--- FIM_TURNO ---":
            i += 1

        try:
            t["turn_id"] = int(t.get("turn_id", "0"))
        except ValueError:
            t["turn_id"] = 0

        t["speaker_id"] = t.get("speaker_id", "")
        t["speaker_name"] = t.get("speaker_name", PARTICIPANTES.get(str(t["speaker_id"]), str(t["speaker_id"])))
        t["status"] = t.get("status", "completed")
        t["timestamp"] = t.get("timestamp", "")

        target_id = str(t.get("target_id", "")).strip()
        target_name = str(t.get("target_name", "")).strip()
        t["target_id"] = [x for x in target_id.split(",") if x] if target_id else []
        t["target_name"] = [x for x in target_name.split(",") if x] if target_name else []

        t["text"] = "\n".join(text_lines).strip()

        if t.get("speaker_name") and t.get("text") is not None:
            turnos.append(t)

    return turnos


def carregar_memoria_e_turn_id(caminho: str = ARQUIVO_HISTORICO) -> tuple[deque, int]:
    turnos = _parse_turnos_do_txt(caminho)
    memoria: deque = deque(turnos[-MEMORIA_MAX_TURNOS :], maxlen=MEMORIA_MAX_TURNOS)

    if not turnos:
        return memoria, 1

    maior = max((t.get("turn_id", 0) for t in turnos), default=0)
    return memoria, maior + 1


def _memoria_para_mensagens(memoria: deque) -> list[dict[str, str]]:
    mensagens: list[dict[str, str]] = []
    for t in memoria:
        speaker_id = t.get("speaker_id")
        speaker_name = t.get("speaker_name", "Alguem")
        text = t.get("text", "")

        if speaker_id == "edu":
            role = "user"
        else:
            role = "assistant"

        if text:
            # O GRANDE TRUQUE: Injeta o nome da pessoa/IA na mensagem pro cérebro ler!
            mensagens.append({"role": role, "content": f"[{speaker_name} disse]: {text}"})

    return mensagens


def responder_nil_github(mensagem: str, memoria: deque) -> str:
    token = os.getenv(GITHUB_TOKEN_ENV, "").strip()
    if not token:
        return (
            "[erro] GITHUB_TOKEN nao encontrado. "
            "No Windows: setx GITHUB_TOKEN \"SEU_TOKEN\" e reabra o terminal."
        )

    if OpenAI is None:
        return "[erro] Dependencia 'openai' nao instalada. Rode: pip install openai"

    model = os.getenv(NIL_MODEL_ENV, DEFAULT_NIL_MODEL).strip() or DEFAULT_NIL_MODEL
    client = OpenAI(
        base_url=GITHUB_MODELS_ENDPOINT,
        api_key=token,
    )

    messages = [
        {"role": "system", "content": "Voce e o Nil. Seja direto, pratico e amigavel. Responda em pt-BR."},
        *_memoria_para_mensagens(memoria),
        {"role": "user", "content": mensagem},
    ]

    try:
        resp = client.chat.completions.create(model=model, messages=messages)
        content = (resp.choices[0].message.content or "").strip()
        return content or "[vazio] Nil nao retornou texto."
    except Exception as e:  # pragma: no cover
        return f"[erro] Falha ao chamar GitHub Models: {e}"


def responder_nil_azure(mensagem: str, memoria: deque) -> str:
    """
    Usa Azure OpenAI (deployment) como backend do Nil.
    Requer env vars:
      - AZURE_OPENAI_API_KEY
      - AZURE_OPENAI_ENDPOINT (https://nel.openai.azure.com/)
      - AZURE_OPENAI_API_VERSION (2025-12-01)
      - AZURE_OPENAI_DEPLOYMENT (NIL)
    """
    api_key = os.getenv(AZURE_OPENAI_API_KEY_ENV, "").strip()
    endpoint = os.getenv(AZURE_OPENAI_ENDPOINT_ENV, "").strip()
    api_version = os.getenv(AZURE_OPENAI_API_VERSION_ENV, DEFAULT_AZURE_API_VERSION).strip() or DEFAULT_AZURE_API_VERSION
    deployment = os.getenv(AZURE_OPENAI_DEPLOYMENT_ENV, "").strip()

    if not api_key:
        return (
            f"[erro] {AZURE_OPENAI_API_KEY_ENV} nao encontrada. "
            f"No Windows: setx {AZURE_OPENAI_API_KEY_ENV} \"SUA_CHAVE\" e reabra o terminal."
        )
    if not endpoint:
        return (
            f"[erro] {AZURE_OPENAI_ENDPOINT_ENV} nao encontrado. "
            f"Exemplo: setx {AZURE_OPENAI_ENDPOINT_ENV} \"https://nel.openai.azure.com/\""
        )
    if not deployment:
        return (
            f"[erro] {AZURE_OPENAI_DEPLOYMENT_ENV} nao encontrado. "
            f"Exemplo: setx {AZURE_OPENAI_DEPLOYMENT_ENV} \"NIL\""
        )
    if OpenAI is None:
        return "[erro] Dependencia 'openai' nao instalada. Rode: pip install openai"

    # Azure OpenAI é OpenAI-compatible via /openai/v1 quando usando o SDK openai.
    # (Mantemos api-version na query)
    base_url = endpoint.rstrip("/") + f"/openai/v1?api-version={api_version}"

    client = OpenAI(
        base_url=base_url,
        api_key=api_key,  # o SDK manda "Authorization: Bearer" por padrão; muitos setups aceitam.
    )

    messages = [
        {"role": "system", "content": "Voce e o Nil. Seja direto, pratico e amigavel. Responda em pt-BR."},
        *_memoria_para_mensagens(memoria),
        {"role": "user", "content": mensagem},
    ]

    try:
        # No Azure, o "model" aqui é o NOME DO DEPLOYMENT
        resp = client.chat.completions.create(model=deployment, messages=messages)
        content = (resp.choices[0].message.content or "").strip()
        return content or "[vazio] Nil (Azure) nao retornou texto."
    except Exception as e:  # pragma: no cover
        return f"[erro] Falha ao chamar Azure OpenAI (deployment={deployment}): {e}"


def responder_nil(mensagem: str, memoria: deque) -> str:
    # Forçado: sempre usar GitHub Models
    return responder_nil_github(mensagem, memoria)


def responder_gemini_google(mensagem: str, memoria: deque) -> str:
    api_key = os.getenv(GOOGLE_API_KEY_ENV, "").strip()
    if not api_key:
        return (
            "[erro] GOOGLE_API_KEY nao encontrada. "
            "No Windows: setx GOOGLE_API_KEY \"SUA_CHAVE\" e reabra o terminal."
        )

    if genai is None:
        return "[erro] Dependencia 'google-genai' nao instalada. Rode: pip install google-genai"

    model = os.getenv(GOOGLE_MODEL_ENV, DEFAULT_GOOGLE_MODEL).strip() or DEFAULT_GOOGLE_MODEL
    client = genai.Client(api_key=api_key)

    historico = _memoria_para_mensagens(memoria)
    contexto_txt = "\n".join([f"{m['role']}: {m['content']}" for m in historico][-20:])
    prompt = (
        "Voce e o Gemini. Seja direto, pratico e amigavel. Responda em pt-BR.\n\n"
        "Contexto recente (pode ignorar se atrapalhar):\n"
        f"{contexto_txt}\n\n"
        f"Mensagem do Eduardo: {mensagem}"
    )

    try:
        resp = client.models.generate_content(model=model, contents=prompt)
        texto = getattr(resp, "text", None)
        if isinstance(texto, str) and texto.strip():
            return texto.strip()
        return str(resp).strip() or "[vazio] Gemini nao retornou texto."
    except Exception as e:  # pragma: no cover
        return f"[erro] Falha ao chamar Gemini: {e}"


def exibir_ajuda() -> None:
    print("\nComandos disponiveis:")
    print("  /para X msg -> envia para alvo explicito (nil|gemini|ambos)")
    print("  /ajuda      -> mostra comandos")
    print("  /historico  -> mostra memoria curta")
    print("  /debug      -> alterna modo debug")
    print("  /limpar     -> limpa memoria curta (na RAM; nao apaga TXT)")
    print("  /sair       -> encerra o programa")


def imprimir_historico(memoria: deque) -> None:
    if not memoria:
        print("\nHistorico vazio.")
        return
    print("\n=== Historico curto (mais recente por ultimo) ===")
    for turno in memoria:
        imprimir_turno(turno)


def main() -> None:
    memoria, turn_id = carregar_memoria_e_turn_id()
    debug_ativo = False

    iniciar_sessao_no_txt()

    print("=== Armada do Silicio | Maestro (TXT + Nil + Gemini) ===")
    print(f"Historico (append): {ARQUIVO_HISTORICO}")
    print(f"Turnos carregados na memoria curta: {len(memoria)}")
    print(f"Env vars: {GITHUB_TOKEN_ENV}, {GOOGLE_API_KEY_ENV}, {NIL_PROVIDER_ENV}")
    exibir_ajuda()

    while True:
        texto = input("\nEduardo> ").strip()
        if not texto:
            continue

        if texto == "/sair":
            print("\nEncerrando Maestro.")
            break
        if texto == "/ajuda":
            exibir_ajuda()
            continue
        if texto == "/debug":
            debug_ativo = not debug_ativo
            estado = "ligado" if debug_ativo else "desligado"
            print(f"\nModo debug {estado}.")
            continue
        if texto == "/historico":
            imprimir_historico(memoria)
            continue
        if texto == "/limpar":
            memoria.clear()
            print("\nMemoria curta limpa (RAM).")
            continue

        targets, mensagem = parse_input_usuario(texto)
        if targets is None:
            print(f"\n{mensagem}")
            continue

        turno_edu = criar_turno(turn_id, "edu", targets, mensagem, status="completed")
        memoria.append(turno_edu)
        imprimir_turno(turno_edu)
        if debug_ativo:
            imprimir_debug(turno_edu)
        salvar_turno_txt(turno_edu)
        turn_id += 1

        for agente_id in targets:
            if agente_id == "nil":
                resposta = responder_nil(mensagem, memoria)
            elif agente_id == "gemini":
                resposta = responder_gemini_google(mensagem, memoria)
            else:
                resposta = f"[erro] Agente desconhecido: {agente_id}"

            turno_agente = criar_turno(turn_id, agente_id, ["edu"], resposta, status="completed")
            memoria.append(turno_agente)
            imprimir_turno(turno_agente)
            if debug_ativo:
                imprimir_debug(turno_agente)
            salvar_turno_txt(turno_agente)
            turn_id += 1


if __name__ == "__main__":
    main()