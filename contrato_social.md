# 📜 Contrato Social da Armada

### 1. Regra de Ouro (Interrupção)
O humano (Eduardo) tem prioridade absoluta. Se ele começar a falar ou digitar, qualquer processo de voz (TTS) das IAs deve ser interrompido imediatamente.

### 2. Gestão de Turnos
O "Maestro" (Orquestrador) decide quem fala com base no `target_id`. Se uma IA é citada, ela entra na fila de resposta.

### 3. Identidade e Transparência
- **Interno:** IDs técnicos (`edu`, `nil`, `gemini`).
- **Externo:** Nomes reais.
- **Estilo:** Manter o tom original de cada modelo (Sem maquilhagem de prompt).

### 4. Memória de Curto Prazo
O sistema deve lembrar apenas os últimos 3 a 5 turnos para manter o contexto sem explodir o custo de tokens ou a memória do computador.