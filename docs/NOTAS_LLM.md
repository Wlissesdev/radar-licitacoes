# Notas sobre os modelos de LLM (Tarefa 2)

Data: 23/11/2026. Verificado ao vivo contra o catálogo NVIDIA (`GET /v1/models`) e uma
chamada real de chat.

## Decisões
- **DeepSeek** (`deepseek-chat`, `https://api.deepseek.com/v1`): papel principal (M3/M4 —
  leitura de edital, resumo, checklist, redação). Modelo **não** de raciocínio → mais
  barato e previsível. Preço em `config.yaml` marcado como **RECHECAR** antes de faturar.
- **Kimi via NVIDIA** (`moonshotai/kimi-k3.1-pro`, `https://integrate.api.nvidia.com/v1`):
  papel de triagem em lote (M2). Camada gratuita; lentidão não importa.

## Achados de campo que afetaram o código
1. O modelo antigo `moonshotai/kimi-k2-instruct` **chegou ao fim de vida em 12/05/2026**
   (a API devolve `410 Gone`). O único modelo Moonshot/Kimi no catálogo NVIDIA hoje é
   `moonshotai/kimi-k3.1-pro`. Corrigido em `config.yaml`.
2. **É um modelo de raciocínio.** A resposta traz `message.reasoning_content` além de
   `message.content`. Se `max_tokens` for pequeno, todo o orçamento é consumido pelo
   raciocínio e `content` vem `None` com `finish_reason=length`.
   → O wrapper trata isso: nunca trata `content` nulo como sucesso e orienta aumentar
   `max_tokens`. Para chamadas longas (M3), usar `max_tokens` generoso.
3. `reasoning_tokens` são cobrados como tokens de saída (`completion_tokens_details`).
   O ledger de custo já usa `completion_tokens`, então a conta fecha.

## Idiomas e cotas
- `NVIDIA_API_KEY` estava presente no ambiente local; `DEEPSEEK_API_KEY` ainda não.
  O wrapper reporta quais chaves existem via `py -3.11 -m radar config`.
- Latência observada do Kimi: ~36 s para uma resposta trivial. Compatível com uso em lote.

## Alternativas baratas para M2 (se o Kimi ficar caro/lento)
Do catálogo NVIDIA: `minimaxai/minimax-m3.1-flash`, `z-ai/glm-5.3-flash`,
`nvidia/nemotron-3.5-lightning-30b-a3b`. Trocar é uma linha no `config.yaml`.
