# G.I.---Machine — Armada do Silício

A multi-agent chat orchestrator that lets you converse with two AI assistants simultaneously from the terminal.

## Agents

| ID | Name | Provider |
|---|---|---|
| `edu` | Eduardo | Human |
| `nil` | Nil | GitHub Models |
| `gemini` | Gemini | Google Gemini |

## Requirements

```
pip install openai google-genai
```

## Configuration

### GITHUB_TOKEN — para o Nil (GitHub Models)

**Sim, gere o token nessa página:**
👉 https://github.com/settings/personal-access-tokens/new

Passos:
1. **Token name:** coloque qualquer nome (ex: `armada-nil`)
2. **Expiration:** escolha o prazo que quiser (ex: 90 dias)
3. **Resource owner:** sua conta pessoal
4. **Repository access:** deixe em *"Public Repositories (read-only)"* — GitHub Models não precisa de acesso a repositórios
5. Em **Account permissions**, procure **"Models"** e selecione **"Read"** (se a opção aparecer)
6. Clique em **Generate token** e copie o valor gerado

> Se preferir, também funciona o token clássico em https://github.com/settings/tokens/new (sem selecionar nenhum escopo).

### GOOGLE_API_KEY — para o Gemini

Gemini usa a API da Google (nível gratuito disponível):
👉 https://aistudio.google.com/

### Variáveis de ambiente

| Variável | Descrição | Padrão |
|---|---|---|
| `GITHUB_TOKEN` | Personal Access Token do GitHub (para Nil via GitHub Models) | *(obrigatório para Nil)* |
| `GOOGLE_API_KEY` | Chave da API do Google Gemini | *(obrigatório para Gemini)* |
| `NIL_MODEL` | Modelo servido via GitHub Models | `gpt-4o-mini` |
| `GOOGLE_MODEL` | Modelo do Google | `gemini-2.5-flash` |

**Windows:**
```
setx GITHUB_TOKEN "seu_token_aqui"
setx GOOGLE_API_KEY "sua_chave_aqui"
```
> Feche e reabra o terminal após usar `setx`.

**Linux/macOS:**
```
export GITHUB_TOKEN="seu_token_aqui"
export GOOGLE_API_KEY="sua_chave_aqui"
```

## Usage

```
python src/maestro.py
```

### Commands

| Comando | Descrição |
|---|---|
| `/para nil <msg>` | Envia mensagem só para o Nil |
| `/para gemini <msg>` | Envia mensagem só para o Gemini |
| `/para ambos <msg>` | Envia para os dois |
| `/ajuda` | Mostra os comandos disponíveis |
| `/historico` | Mostra o histórico recente em memória |
| `/debug` | Liga/desliga modo debug |
| `/limpar` | Limpa a memória curta (não apaga o arquivo TXT) |
| `/sair` | Encerra o programa |

Sem o prefixo `/para`, a mensagem vai para os agentes que forem mencionados pelo nome, ou para ambos se nenhum for citado.

## History

O histórico é salvo em `src/historico.txt` e recarregado no início de cada sessão (últimos `10` turnos).
