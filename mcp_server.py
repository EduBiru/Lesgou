from __future__ import annotations

import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.adapters.orchestrator import OrchestratorAdapter

app = FastAPI(title="Lesgou MCP Bridge")
adapter = OrchestratorAdapter()


class MessageRequest(BaseModel):
    mensagem: str


@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "lesgou-mcp",
        "has_github_token": bool(os.getenv("GITHUB_TOKEN")),
        "has_google_api_key": bool(os.getenv("GOOGLE_API_KEY")),
    }


@app.post("/tools/falar_com_nil")
def falar_com_nil(req: MessageRequest):
    try:
        resposta = adapter.falar_com_nil(req.mensagem)
        return {"ok": True, "tool": "falar_com_nil", "result": resposta}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/falar_com_gemini")
def falar_com_gemini(req: MessageRequest):
    try:
        resposta = adapter.falar_com_gemini(req.mensagem)
        return {"ok": True, "tool": "falar_com_gemini", "result": resposta}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/falar_com_ambos")
def falar_com_ambos(req: MessageRequest):
    try:
        resposta = adapter.falar_com_ambos(req.mensagem)
        return {"ok": True, "tool": "falar_com_ambos", "result": resposta}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))