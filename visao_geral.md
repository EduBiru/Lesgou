# Visão Geral — Armada do Silício

## Objetivo

Permitir que Eduardo converse com dois agentes de IA (Nil e Gemini) de forma organizada, com histórico persistente e gestão de turnos via terminal.

## Arquitetura

```
src/
  maestro.py        # Orquestrador principal
data/
  participantes.json    # Definição dos participantes
  exemplo_de_turno.json # Exemplo de formato de turno
contrato_social.md  # Regras de convivência entre agentes
visao_geral.md      # Este documento
README.md           # Documentação de uso
requirements.txt    # Dependências Python
```

## Fluxo de um Turno

1. Eduardo digita uma mensagem no terminal.
2. O `maestro.py` identifica o(s) alvo(s) (`nil`, `gemini`, ou ambos).
3. O turno de Eduardo é salvo no histórico (RAM + TXT).
4. Para cada alvo, o Maestro chama a API correspondente e obtém a resposta.
5. Cada resposta é salva como um novo turno e exibida no terminal.

## Memória

- **Curta (RAM):** últimos `MEMORIA_MAX_TURNOS` (padrão: 10) turnos em `deque`.
- **Longa (TXT):** arquivo `src/historico.txt` — append a cada sessão.

## Participantes

| ID | Nome | Tipo | Provedor |
|---|---|---|---|
| `edu` | Eduardo | Humano | — |
| `nil` | Nil | IA | GitHub Models |
| `gemini` | Gemini | IA | Google Gemini |
