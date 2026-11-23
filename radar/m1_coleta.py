"""M1 — Coleta diária do PNCP.

Estratégia (ajustada ao que a API realmente oferece — ver docs/RECON_PNCP.md):
  - o endpoint /v1/contratacoes/proposta está quebrado (500); então coletamos por
    data de publicação numa janela de `dias` e marcamos `propostas_abertas` quando o
    prazo de encerramento ainda não passou;
  - para cada UF-alvo x modalidade-alvo, pagina os resultados, valida, normaliza e
    faz upsert (deduplicando pelo número de controle PNCP).
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from .db import upsert_contratacao
from .validacao import validar_contratacao

log = logging.getLogger("radar.m1")


def coletar(client, conn, *, ufs: list[str], modalidades: list[int], dias: int = 7,
            hoje: date | None = None, max_paginas: int | None = None) -> dict:
    """Coleta e persiste. Devolve um resumo com contagens."""
    hoje = hoje or date.today()
    inicio = hoje - timedelta(days=dias)
    data_ini, data_fim = inicio.strftime("%Y%m%d"), hoje.strftime("%Y%m%d")

    resumo = {
        "janela": f"{data_ini}..{data_fim}",
        "vistos": 0, "gravados": 0, "novos": 0,
        "ok": 0, "suspeitos": 0, "invalidos": 0,
        "por_uf": {uf: 0 for uf in ufs},
        "por_modalidade": {m: 0 for m in modalidades},
    }

    for uf in ufs:
        for modalidade in modalidades:
            for raw in client.paginar_publicacoes(uf, modalidade, data_ini, data_fim, max_paginas=max_paginas):
                resumo["vistos"] += 1
                linha = validar_contratacao(raw)
                if linha is None:
                    resumo["invalidos"] += 1
                    log.warning("descartado: sem numeroControlePNCP (%s/%s)", uf, modalidade)
                    continue
                novo = upsert_contratacao(conn, linha)
                resumo["gravados"] += 1
                resumo["por_uf"][uf] += 1
                resumo["por_modalidade"][modalidade] += 1
                if novo:
                    resumo["novos"] += 1
                if linha["status_validacao"] == "ok":
                    resumo["ok"] += 1
                else:
                    resumo["suspeitos"] += 1

    log.info(
        "M1 concluído janela=%s vistos=%d novos=%d ok=%d suspeitos=%d invalidos=%d",
        resumo["janela"], resumo["vistos"], resumo["novos"],
        resumo["ok"], resumo["suspeitos"], resumo["invalidos"],
    )
    return resumo
