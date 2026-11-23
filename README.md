# Radar Licita MEI

Pipeline que coleta compras públicas do PNCP, explica editais em linguagem simples
para MEI/ME da região (MA/PA/TO/PI) e entrega boletins, dossiês de lead e
relatórios de métricas ao dono humano.

- Especificação completa: [`SPEC.md`](SPEC.md)
- Reconhecimento da API do PNCP (Tarefa 1): [`docs/RECON_PNCP.md`](docs/RECON_PNCP.md)

## Estado

- [x] Tarefa 1 — Reconhecimento da API do PNCP
- [ ] Tarefa 2 — Repositório, config.yaml, wrapper `llm.py`
- [ ] Tarefa 3 — M1 Coleta + banco + validação (MA/PA/TO/PI)
- [ ] Tarefa 4 — M2 Triagem (Kimi)
- [ ] Tarefa 5 — M3 + M4 (Análise + Verificação)
- [ ] Tarefa 6 — M5/M6 (Boletim + Telegram)
- [ ] Tarefa 7 — Dossiê de leads
- [ ] Tarefa 8 — Relatório semanal (M7)
- [ ] Tarefa 9 — Revisão de 14 dias

## Regras invioláveis (resumo — ver SPEC §3)

1. Nunca inventar dado; se não está na fonte, escrever "não informado".
2. Toda saída tem link da fonte oficial.
3. O agente **nunca** envia mensagem a terceiros — só gera rascunhos.
4. Sem scraping agressivo; respeitar limites e cachear.
5. LGPD: dados públicos mínimos, origem registrada, opt-out respeitado.
6. Sem promessa de ganho.
7. Logar tudo (incl. custo em tokens).
8. Trocar de modelo por configuração.

## Pré-requisitos

Python 3.11 (o ambiente tem 3.11.9 e 3.14.6; usar 3.11 por compatibilidade de
bibliotecas como pdfplumber).

## Reconhecimento da API

```
py -3.11 tools/recon_pncp.py
```
