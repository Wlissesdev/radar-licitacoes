# Radar de Licitações para MEI/ME — Especificação para o agente de IA

Documento de instruções para um agente (DeepSeek via API, com Kimi como filtro barato) construir e operar o projeto de ponta a ponta. Versão de 23/11/2026.

## 0. Como usar este documento
Cole este documento inteiro como contexto inicial do agente (ou salve como SPEC.md no repositório). Depois mande o agente executar a Seção 13, tarefa por tarefa, uma por vez, pedindo para ele rodar e mostrar a saída antes de seguir.

Papel do agente: construir o pipeline, rodá-lo todo dia, e entregar ao dono (humano) três coisas prontas: (1) o boletim diário de oportunidades, (2) listas de leads com dossiê e mensagem rascunhada, (3) um relatório semanal de métricas. O humano faz o contato e fecha a venda. O agente nunca envia mensagem a terceiros sozinho.

## 1. Validação da ideia (resultado da pesquisa)
Veredito: a ideia genérica ("alerta de licitação") está validada como demanda, mas NÃO como oportunidade. O mercado é ocupado. Só vale a pena num recorte estreito.

O que a pesquisa mostrou:
- Dados: viáveis e gratuitos. O PNCP tem API de consulta pública, sem login, em https://pncp.gov.br/api/consulta, com Swagger em https://pncp.gov.br/api/consulta/swagger-ui/index.html. Existe cliente Python assíncrono (pypncp, licença MIT). A Lei 14.133 obriga a publicação de contratos no PNCP, então a cobertura é ampla.
- Qualidade dos dados: ruim. A Transparência Brasil apontou datas irreais, campos faltantes, status desatualizado e documentação da API inconsistente. O pipeline precisa de camada de validação e não pode confiar cegamente nos campos.
- Demanda: provada. O ConLicitação declara mais de 80 mil usuários ativos e alertas por WhatsApp. Há dezenas de ferramentas.
- Concorrência: pesada em todos os níveis. O Alerta Licitação cobra cerca de R$ 34,90/mês no app e R$ 44,90/mês no site (planos anuais saem por cerca de R$ 30/mês) e diz varrer mais de 5 mil sites. O Effecti tem plano grátis. O ConLicitação vende planos completos com robô de lances, análise de mercado e "Pergunte ao Edital" (IA sobre o edital).
- Consequência: cobrar R$ 49–199/mês por um simples alerta filtrado não se sustenta. O preço-âncora de alerta básico é R$ 30–45. Para cobrar mais, é preciso entregar algo que eles não entregam.

Onde ainda existe espaço (hipótese a testar, não certeza):
1. Recorte regional e de porte: microempreendedores e pequenas empresas do Maranhão/Pará/Tocantins/Piauí que nunca venderam ao governo. As ferramentas grandes são feitas para quem já licita profissionalmente.
2. Linguagem simples e decisão pronta: em vez de lista de editais, entregar "vale a pena? o que preciso ter? qual o risco? qual o prazo?" em 5 linhas, com checklist de documentos. Isso é trabalho de IA sobre o edital.
3. Licitações pequenas e compras diretas (dispensa) e cotação eletrônica, onde o MEI tem vantagem legal (preferência ME/EPP) e onde o grande player dá menos atenção.
4. Serviço, não só software: o produto é "te aviso e te ajudo a montar a proposta" (modelo de proposta, checklist, declaração). Cobra-se por resultado ou por pacote.
5. Lado B (opcional): vender a lista de empresas que vencem licitações na região para quem vende a elas (contabilidade, certidões, consultoria, crédito).

Critério de morte: se em 30 dias não houver 10 pessoas dispostas a pagar (mesmo R$ 29), o agente deve recomendar abandonar ou pivotar. Ver Seção 12.

## 2. Produto (versão mínima)
Nome de trabalho: Radar Licita MEI (trocar depois).

Promessa: "Todo dia de manhã, no seu Telegram/WhatsApp, as 3 a 5 compras públicas da sua região e do seu ramo que você pode disputar, explicadas em linguagem simples."

Cada alerta contém: órgão, cidade/UF, objeto em uma frase, valor estimado, prazo final, modalidade, se há exclusividade ME/EPP, documentos exigidos (checklist), nota de risco (baixo/médio/alto) com motivo, link oficial. Nenhuma informação sem link para a fonte.

Planos para teste (a validar): Grátis (resumo semanal, 1 nicho) · Básico R$ 29/mês (alerta diário, 1 nicho, 1 UF) · Pro R$ 79/mês (3 nichos, checklist, modelo de proposta) · Assistido R$ 197–397/mês ou taxa de êxito (o humano ajuda a montar a proposta).

## 3. Regras invioláveis para o agente
1. Nunca inventar dado. Todo número, data, valor e exigência precisa vir do campo da API ou do texto do edital. Se não estiver lá, escrever "não informado".
2. Toda saída tem link da fonte oficial.
3. Nunca enviar mensagem a terceiros. Só produzir rascunhos para o humano revisar e enviar.
4. Não fazer scraping agressivo. Respeitar limites da API, usar pausa entre requisições, cache local, e nunca ignorar robots.txt em sites que não sejam a API oficial.
5. Dados pessoais (LGPD): coletar apenas dados públicos de empresas (CNPJ, razão social, CNAE, município, telefone/e-mail comercial de cadastro). Não cruzar com dados pessoais de sócios além do que for público e necessário. Guardar origem de cada dado. Todo contato deve oferecer opção de parar de receber.
6. Sem promessas de ganho ("você vai ganhar a licitação"). O produto informa, não garante resultado.
7. Logar tudo: entradas, saídas, custo em tokens, erros. Se um dado não passar na validação, descartar e registrar o motivo.
8. Trocar de modelo com uma linha de configuração. A API de US$ 1 pode mudar ou sumir.

## 4. Arquitetura
```
[PNCP API consulta] -> [Coleta diária] -> [SQLite/Postgres]
                                      -> [Validação de dados]
                                      -> [Triagem barata: Kimi/NVIDIA classifica por ramo]
                                      -> [Análise: DeepSeek lê o edital e gera resumo+checklist+risco]
                                      -> [Verificação: 2o passe confere cada campo contra a fonte]
                                      -> [Boletim por assinante/nicho]
                                      -> [Telegram (canal grátis + bot pago)] / [e-mail]
[Fontes de leads] -> [Dossiê de lead] -> [Rascunho de mensagem] -> [Fila para o humano]
[Eventos: cliques, respostas, pagamentos] -> [Relatório semanal]
```
Stack sugerida: Python 3.12, httpx ou pypncp, SQLite no início (migrar para Postgres/Supabase se escalar), python-telegram-bot, agendamento por cron (ou n8n), um arquivo config.yaml com provedores de modelo (deepseek, kimi_nvidia) e um wrapper llm.py com uma função chat(model_alias, messages) que trata retry, timeout e fallback entre provedores.

Divisão de trabalho entre modelos: Kimi grátis para classificação em lote (assíncrono, lentidão não importa). DeepSeek para leitura de edital, resumo, checklist e redação. Para a verificação, usar um prompt diferente (e de preferência o outro modelo) para reduzir erro correlacionado.

## 5. Fontes de dados
Fonte principal: API de Consulta do PNCP.
- Base: https://pncp.gov.br/api/consulta
- Documentação: Swagger no endereço acima e o "Manual PNCP API Consultas" em gov.br/pncp.
- Endpoints a usar (o agente deve confirmar nomes e parâmetros exatos no Swagger antes de codar, não assumir): contratações por data de publicação, contratações com propostas em aberto, itens da contratação, arquivos/anexos (editais em PDF), atas de registro de preço e contratos.
- Parâmetros típicos: intervalo de datas, UF, código de modalidade, página, tamanho de página. Paginar sempre; tratar erro 429/5xx com backoff exponencial.
- Alternativa de cliente: biblioteca pypncp, só depois de ler o código-fonte e conferir que ela cobre os endpoints necessários.

Fontes complementares (adicionar só depois da v1 funcionar):
- Dados abertos de CNPJ da Receita Federal (para perfil de empresas e CNAE).
- Portais estaduais/municipais do MA/PA/TO/PI que não espelham tudo no PNCP (verificar caso a caso se vale o esforço).
- Diário Oficial dos municípios da região (só se houver formato estruturado).

Armadilhas conhecidas (relatório da Transparência Brasil): datas impossíveis, campos vazios, status que não atualiza, valores estimados mal preenchidos, API que diverge do manual. Regras de validação mínimas: data de abertura posterior à de publicação; valor estimado numérico e maior que zero (senão "não informado"); link do edital acessível; deduplicar pelo número de controle PNCP.

## 6. Esquema do banco (mínimo)
- contratacoes: id_pncp (único), orgao, cnpj_orgao, uf, municipio, modalidade, objeto, valor_estimado, data_publicacao, data_abertura, data_encerramento_propostas, exclusivo_mei_epp (bool/nulo), url_oficial, status_validacao, raw_json, coletado_em.
- anexos: id, id_pncp, nome, url, texto_extraido, hash.
- analises: id_pncp, nicho, resumo, checklist_json, risco, motivo_risco, verificado (bool), modelo_usado, tokens_gastos, criado_em.
- assinantes: id, canal, chat_id, nichos, ufs, plano, status, origem, criado_em.
- envios: id, assinante_id, id_pncp, enviado_em, clicou (bool).
- leads: id, cnpj, razao_social, municipio, cnae, telefone_publico, email_publico, origem_dado, motivo_do_fit, status (novo/rascunho/contatado/respondeu/pagou/descartado), optout (bool), notas.
- metricas_semana: semana, assinantes_novos, ativos, churn, receita, custo_ia, taxa_clique.

## 7. Pipeline — módulos
M1 Coleta (diária, 06:00). Buscar contratações publicadas nos últimos 2 dias e todas com prazo de propostas ainda aberto, filtrando pelas UFs-alvo. Salvar bruto, validar, deduplicar.

M2 Triagem (Kimi). Para cada contratação nova, classificar o objeto em categorias de ramo (ex.: alimentos/merenda, material de escritório, TI/equipamentos, limpeza/higiene, obras e manutenção, serviços gerais, veículos/combustível, saúde/insumos, eventos/gráfica). Saída em JSON: {categoria, confianca, palavras_chave}. Descartar baixa confiança para revisão posterior.

M3 Análise do edital (DeepSeek). Só para itens que casam com algum nicho ativo de assinante. Baixar o edital (PDF), extrair texto (pdfplumber/pypdf; OCR só se necessário), e gerar: resumo em até 3 frases, checklist de habilitação (documentos exigidos), critérios de julgamento, exclusividade ME/EPP, prazos, riscos (garantia, atestado de capacidade técnica exigido, amostra, local de entrega distante, prazo de pagamento). Cada campo cita o trecho do edital em que se baseia (máx. 15 palavras).

M4 Verificação. Segundo passe: para cada afirmação do M3, procurar o trecho de apoio no texto; se não achar, marcar não confirmado e remover do boletim. Valores e datas são comparados com os campos da API; divergência vai para o log e o item sai do envio.

M5 Boletim. Montar por assinante (nicho + UF), ordenar por prazo e adequação, no máximo 5 itens. Formato curto, com emojis mínimos, sem jargão.

M6 Envio. Telegram (canal público para o plano grátis, bot privado para pagantes). E-mail como reserva. WhatsApp só depois de validar demanda e somente pela API oficial do WhatsApp Business; evitar bibliotecas não oficiais, que arriscam banimento do número.

M7 Métricas. Cliques (links encurtados com rastreio), respostas, conversões, custo de IA por boletim. Relatório toda segunda.

## 8. Prompts-modelo
Prompt de análise (M3) — esqueleto:
```
Você é um analista de licitações que explica editais para microempreendedores.
Use APENAS o texto do edital abaixo e os dados estruturados. Se algo não estiver
no texto, escreva "não informado". Nunca presuma.
Responda em JSON com as chaves: resumo (máx 3 frases, linguagem simples),
exclusivo_me_epp, prazo_propostas, valor_estimado, checklist_habilitacao (lista),
criterio_julgamento, riscos (lista de {risco, trecho_de_apoio}), nota_risco
(baixo|medio|alto), proximo_passo_sugerido.
Trecho_de_apoio: cópia literal de até 15 palavras do edital.
DADOS: {json_api}
EDITAL: {texto}
```
Prompt de verificação (M4): receber o JSON do M3 e o texto do edital; para cada afirmação responder {afirmacao, apoiada: true|false, trecho}. Qualquer false remove a afirmação.

Prompt de rascunho de abordagem (Seção 10): receber o dossiê do lead; escrever mensagem de até 4 linhas, citando uma licitação real e recente do ramo dele, sem exageros, terminando com pergunta simples e frase de saída ("se não quiser receber, é só avisar").

## 9. Operação diária do agente
1. 06:00 — M1 a M4.
2. 07:30 — M5/M6 enviam o boletim.
3. 08:00 — agente gera a fila de leads do dia (Seção 10) e entrega ao humano.
4. Segunda — relatório semanal (Seção 12) com recomendação: continuar, ajustar ou pivotar.
5. Sempre — se qualquer módulo falhar, avisar o humano no Telegram com o erro e o que já foi tentado.

## 10. Prospecção: do dado ao contato (o humano envia)
O objetivo é você chegar na conversa já com tudo pronto. Quem aperta enviar é o humano.

Quem prospectar:
- Empresas da região (Imperatriz e entorno, depois MA/PA/TO) com CNAE compatível com compras públicas recorrentes (papelaria, alimentos, material de limpeza, manutenção, informática, gráfica, eventos).
- Empresas que já ganharam contratos pequenos no PNCP na região (prova de que vendem ao governo; podem querer mais) — dados públicos de contratos.
- MEIs e microempresas novas (abertura recente) com CNAE de fornecimento, que provavelmente nunca licitaram.

Dossiê de cada lead (o agente monta): razão social, CNPJ, município, CNAE, porte, tempo de abertura, 2 a 3 licitações abertas hoje que casam com o ramo dele (com link), contratos que ele já ganhou (se houver), e o motivo do encaixe em uma frase.

Mensagem: curta, com uma oportunidade real e concreta, oferta de 7 dias grátis do boletim, e saída fácil. Ritmo: no máximo 15–20 contatos novos por dia, enviados manualmente, para proteger seu número e reputação.

Canais: preferir contato 1 a 1 pelo telefone comercial público e e-mail comercial da empresa, depois indicação de quem já assina. Não usar disparo em massa nem comprar listas.

Opt-out: se alguém pedir para parar, marcar optout = true e nunca mais incluir na fila.

Pontos de atenção legais: CNPJ de MEI é muitas vezes o CPF do dono, então telefone e e-mail do cadastro podem ser dado pessoal. Usar com finalidade clara e compatível (oferta de serviço diretamente ligado à atividade da empresa), registrar a origem, honrar opt-out. Em caso de dúvida, consultar um advogado ou contador antes de escalar.

## 11. Monetização (em ordem de teste)
1. Assinatura do boletim (R$ 29 a R$ 79/mês) para o recorte regional.
2. Serviço assistido (R$ 197–397 por proposta ou mensalidade): o humano usa os checklists e modelos gerados pela IA para montar a documentação do cliente.
3. Parcerias: contadores, despachantes e certificadoras digitais que indicam clientes e recebem comissão. Esses parceiros também são o melhor canal de distribuição.
4. Lista de leads B2B da região para quem vende serviços a fornecedores do governo (testar só depois de ter audiência).
5. Conteúdo de vitrine: posts semanais ("as 3 maiores compras abertas na sua região") gerados do mesmo banco, publicados pelo humano com rosto e marca, apontando para o canal grátis.

## 12. Métricas e critérios de decisão (30 dias)
| Marco | Meta | Se não bater |
| --- | --- | --- |
| Dia 7 | Pipeline rodando; 3 boletins reais conferidos à mão sem erro factual | Corrigir validação antes de qualquer envio |
| Dia 14 | 30 pessoas no canal grátis ou lista de espera | Mudar o recorte (outro ramo ou outra região) |
| Dia 21 | 5 conversas de venda e 3 pagantes (mesmo R$ 19) | Revisar proposta de valor e preço |
| Dia 30 | 10 pagantes ou 3 pedidos de serviço assistido | Pivotar ou encerrar |

Métricas a reportar toda segunda: assinantes novos/ativos/churn, taxa de clique, respostas às abordagens, conversões, custo de IA por assinante, erros factuais encontrados e horas humanas gastas. Unit economics alvo: custo de IA e infraestrutura por assinante abaixo de 10% do preço.

## 13. Ordem de execução (tarefas para o agente)
Executar uma por vez, mostrando a saída e esperando aprovação.
1. Reconhecimento da API: abrir o Swagger do PNCP, listar os endpoints relevantes com parâmetros obrigatórios, e fazer 3 chamadas de teste para MA com saída resumida. Relatar campos vazios ou estranhos.
2. Repositório e configuração: estrutura de pastas, config.yaml, .env (chaves nunca no código), wrapper llm.py com fallback DeepSeek ↔ Kimi, logs e controle de custo em tokens.
3. M1 Coleta + banco + validação para MA, PA, TO e PI, com cache e backoff.
4. M2 Triagem com Kimi sobre 200 contratações reais; medir acurácia à mão em 50 delas e relatar.
5. M3 + M4 em 20 editais reais; entregar relatório com cada erro encontrado. Meta: zero afirmação sem apoio no texto.
6. M5/M6: canal de Telegram de teste, boletim formatado, links rastreados.
7. Dossiê de leads (Seção 10) para 50 empresas de Imperatriz e entorno, com rascunhos de mensagem para o humano revisar.
8. Relatório semanal (M7) e painel simples (planilha ou página) com as métricas.
9. Revisão após 14 dias: agente recomenda continuar, mudar o recorte ou pivotar, com números.

## 14. Riscos e como tratar
- Concorrência grande: só competir pelo recorte (região, porte, linguagem, serviço assistido), nunca por "mais um alerta".
- Erro factual do modelo: pode custar dinheiro ao cliente e destruir a reputação. Verificação obrigatória e revisão humana nas primeiras semanas.
- Dados ruins no PNCP: validar e preferir deixar de fora a enviar errado.
- Dependência de API barata: manter fallback e não assumir disponibilidade ou preço permanentes.
- Bloqueio de WhatsApp/redes: evitar automação não oficial; começar por Telegram e e-mail.
- LGPD: dados mínimos, origem registrada, opt-out respeitado.
- Excesso de escopo: não adicionar fontes, nichos ou recursos antes de ter pagantes.

## 15. Fontes consultadas nesta validação
- Portal Nacional de Contratações Públicas: manuais de consulta e perguntas e respostas (acesso público e gratuito, sem login).
- Transparência Brasil (2024): qualidade dos dados do PNCP.
- ConLicitação (planos e números de usuários), Alerta Licitação (preços), Effecti (plano grátis).
- Projeto pypncp no PyPI.

Nota: preços e números de concorrentes mudam; o agente deve rechecar as páginas oficiais antes de definir preço final.
