# Reconhecimento da API do PNCP — Relatório (Tarefa 1 da Seção 13)

Data da coleta: 23/11/2026. Fonte: chamadas reais à API pública do PNCP.
Todos os resultados abaixo são reproduzíveis com o script `tools/recon_pncp.py`.

## 1. Resumo executivo

A API do PNCP é viável e gratuita, **mas a SPEC está errada em 3 pontos** que precisam ser corrigidos antes de codar:

| Item na SPEC | Realidade encontrada | Correção necessária |
| --- | --- | --- |
| Anexos/editais e itens acessíveis pela API de consulta | `.../itens` e `.../arquivos` retornam **403** em `https://pncp.gov.br/api/consulta` | Usar base não documentada `https://pncp.gov.br/pncp-api` |
| Campo direto de exclusividade ME/EPP | Não existe na contratação | Vem de `itens[].tipoBeneficio` / `tipoBeneficioNome` (base `pncp-api`) |
| Endpoint "contratações com propostas em aberto" | `/v1/contratacoes/proposta` retorna **500** após ~53s | Não usar; filtrar `dataEncerramentoProposta > hoje` sobre `publicacao`/`atualizacao` |

Ponto positivo crítico: **o PDF do edital é baixável** e o pipeline M1→M3 é tecnicamente viável.

## 2. Detalhes técnicos confirmados

### 2.1 Hosts e cabeçalhos
- **Listagem / detalhe:** `https://pncp.gov.br/api/consulta` (é este que tem Swagger em `/api/consulta/swagger-ui/index.html`; o OpenAPI está em `/api/consulta/v3/api-docs`).
- **Itens / anexos / download de PDF:** `https://pncp.gov.br/pncp-api` (também responde em `/api/pncp`). **Não aparece no Swagger.**
- **Cabeçalho obrigatório:** `User-Agent`. Sem ele, toda chamada retorna **403**. Com ele, 200.
- Codificação: UTF-8 (o mojibake no console do Windows é só exibição).

### 2.2 Endpoints relevantes (confirmados)
Base `api/consulta`:

| Endpoint | Parâmetros | Uso |
| --- | --- | --- |
| `GET /v1/contratacoes/publicacao` | `dataInicial`,`dataFinal` (yyyyMMdd, obrig.), `codigoModalidadeContratacao` (obrig.), `codigoModoDisputa`, `uf`, `codigoMunicipioIbge`, `cnpj`, `codigoUnidadeAdministrativa`, `idUsuario`, `pagina` (obrig.), `tamanhoPagina` (10–50) | Coleta por data de publicação |
| `GET /v1/contratacoes/atualizacao` | idem acima | **Delta diário** (por data de atualização global) |
| `GET /v1/contratacoes/proposta` | `dataFinal` (obrig.) + filtros | **QUEBRADO (500)** — não usar |
| `GET /v1/orgaos/{cnpj}/compras/{ano}/{sequencial}` | — | Detalhe (adiciona `existeResultado`, `orcamentoSigiloso*`) |
| `GET /v1/contratos` | `dataInicial`,`dataFinal` (obrig.), `cnpjOrgao`, ... | **Contratos publicados** → base dos leads (quem ganhou) |
| `GET /v1/contratos/atualizacao` | idem | Delta de contratos |
| `GET /v1/atas` / `GET /v1/atas/atualizacao` | `dataInicial`,`dataFinal`, ... | Atas de registro de preço |
| `GET /v1/pca/` , `/v1/pca/usuario`, `/v1/pca/atualizacao` | ver Swagger | Planos de contratação (não prioritário) |
| `GET /v1/instrumentoscobranca/inclusao` | `dataInicial`,`dataFinal` | Notas fiscais/empenhos (não prioritário) |

Base `pncp-api` (descoberta por teste):

| Endpoint | Resultado |
| --- | --- |
| `GET /v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens` | 200 — lista de itens (sem paginação; array direto) |
| `GET /v1/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos` | 200 — lista de documentos com `url` de download |
| `GET /v1/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos/{n}` | 200 — **PDF** (`application/octet-stream`, magic `%PDF`) |

### 2.3 Campos de item — a exclusividade ME/EPP está aqui
Exemplo real (INMEQ/MA, dispensa 2026/6):
```json
{"numeroItem":1,"descricao":"Serviço de impressão ...",
 "valorUnitarioEstimado":290.0,"valorTotal":1740.0,"quantidade":6.0,
 "unidadeMedida":"Serviço","criterioJulgamentoId":1,"criterioJulgamentoNome":"Menor preço",
 "situacaoCompraItem":1,"situacaoCompraItemNome":"Em andamento",
 "tipoBeneficio":4,"tipoBeneficioNome":"Sem benefício"}
```
> `tipoBeneficioNome` é o indicador de tratamento diferenciado (ME/EPP). Valores observados: `4 = Sem benefício`. Os demais códigos ainda precisam ser mapeados empiricamente (tarefa 3).

### 2.4 Campos vazios / estranhos observados (amostra MA)
- `valorTotalHomologado`: `null` enquanto a compra não tem resultado.
- `emendaParlamentar`, `informacaoComplementar`, `justificativaPresencial`, `orgaoSubRogado`, `unidadeSubRogada`: frequentemente `null`.
- `justificativaPresencial`: aparece como `""` e como `null` — normalizar para nulo.
- `linkProcessoEletronico`: `null` em muitos; o link útil costuma ser `linkSistemaOrigem` (ex. `licitama.com.br`, Compras.gov.br).
- `dataAberturaProposta` pode vir com hora `00:00:00`.

### 2.5 Latência e limites
- `publicacao`: ~5–6 s por página. `atualizacao`: ~13 s. `proposta`: 53 s → 500.
- `tamanhoPagina` máximo: **50** (listagem). Itens não paginam.
- Conclusão: timeouts ≥ 60 s e backoff exponencial são obrigatórios; requisições devem ser sequenciais com pausa.

## 3. Volumes de amostra (MA, 16–23/11/2026)
- Dispensa (`codigoModalidadeContratacao=8`): 67 registros em `publicacao`; **301** em `atualizacao`.
- Pregão Eletrônico (`=6`): 90 registros em `publicacao`.

## 4. Modalidades (`codigoModalidadeContratacao`)
Observados: `6` = Pregão Eletrônico, `8` = Dispensa. Demais códigos a confirmar empiricamente (tarefa 3). Faixa de interesse para MEI: 8 (Dispensa), 6 (Pregão Eletrônico), 4 (Concorrência Eletrônica).

## 5. Consequências para a arquitetura
1. Isolar os dois hosts em um único cliente HTTP (`src/pncp_client.py`) com `User-Agent`, retry/backoff, timeout e cache.
2. Trocar a fonte de "propostas abertas" por filtro local sobre `publicacao` + `atualizacao`.
3. `exclusivo_mei_epp` vem de `itens.tipoBeneficio`, não da contratação.
4. Detalhe + itens + arquivos são 3 chamadas por contratação → usar cache e só detalhar o que passa na triagem (controle de custo e de carga).
5. M3 é viável: baixar `arquivos/*` e extrair texto com pdfplumber.

## 6. Reprodução
Script: `tools/recon_pncp.py` (executa as chamadas acima e imprime um resumo).
