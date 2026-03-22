from __future__ import annotations

from collections import deque

from src.maestro import (
    carregar_memoria_e_turn_id,
    criar_turno,
    responder_gemini_google,
    responder_nil,
    salvar_turno_txt,
)

class OrchestratorAdapter:
    def __init__(self, persist_history: bool = True):
        self.persist_history = persist_history
        self.memoria, self.turn_id = carregar_memoria_e_turn_id()

    def _append_user_turn(self, mensagem: str, targets: list[str]) -> None:
        turno_edu = criar_turno(
            self.turn_id,
            "edu",
            targets,
            mensagem,
            status="completed",
        )
        self.memoria.append(turno_edu)
        if self.persist_history:
            salvar_turno_txt(turno_edu)
        self.turn_id += 1

    def _append_agent_turn(self, agente_id: str, resposta: str) -> None:
        turno_agente = criar_turno(
            self.turn_id,
            agente_id,
            ["edu"],
            resposta,
            status="completed",
        )
        self.memoria.append(turno_agente)
        if self.persist_history:
            salvar_turno_txt(turno_agente)
        self.turn_id += 1

    def falar_com_nil(self, mensagem: str) -> str:
        mensagem = (mensagem or "").strip()
        if not mensagem:
            raise ValueError("A mensagem não pode estar vazia.")

        self._append_user_turn(mensagem, ["nil"])
        resposta = responder_nil(mensagem, self.memoria)
        self._append_agent_turn("nil", resposta)
        return resposta

    def falar_com_gemini(self, mensagem: str) -> str:
        mensagem = (mensagem or "").strip()
        if not mensagem:
            raise ValueError("A mensagem não pode estar vazia.")

        self._append_user_turn(mensagem, ["gemini"])
        resposta = responder_gemini_google(mensagem, self.memoria)
        self._append_agent_turn("gemini", resposta)
        return resposta

    def falar_com_ambos(self, mensagem: str) -> str:
        mensagem = (mensagem or "").strip()
        if not mensagem:
            raise ValueError("A mensagem não pode estar vazia.")

        self._append_user_turn(mensagem, ["nil", "gemini"])

        resposta_nil = responder_nil(mensagem, self.memoria)
        self._append_agent_turn("nil", resposta_nil)

        resposta_gemini = responder_gemini_google(mensagem, self.memoria)
        self._append_agent_turn("gemini", resposta_gemini)

        return (
            "Nil:\n"
            f"{resposta_nil}\n\n"
            "Gemini:\n"
            f"{resposta_gemini}"
        )