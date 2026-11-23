"""M2 — Triagem barata: classifica o objeto em um nicho (SPEC §7).

Roda em lotes (vários objetos por chamada) para reduzir custo e latência, já que
o Kimi é um modelo de raciocínio lento. A saída é persistida em `triagens`.

Saída esperada do modelo (JSON):
  {"classificacoes": [{"id": "<id_pncp>", "nicho": "<nicho>",
                       "confianca": 0.0-1.0, "palavras_chave": ["..."]}]}
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from . import llm
from .config import Config, carregar_config

log = logging.getLogger("radar.m2")

NICHO_OUTROS = "outros"
ALIAS_PADRAO_TRIAGEM = "kimi_nvidia"

# Dicas curtas para orientar o modelo (não são dados: são descrição do nicho).
NICHOS_DESCRICAO = {
    "alimentos_merenda": "gêneros alimentícios, merenda escolar, água, café, cestas",
    "papelaria_escritorio": "material de escritório, papelaria, toner, impressão",
    "ti_equipamentos": "computadores, informática, software, redes, equipamentos de TI",
    "limpeza_higiene": "material de limpeza, higiene, saneantes, descartáveis",
    "obras_manutencao": "obras, reformas, engenharia, manutenção predial",
    "servicos_gerais": "serviços gerais, mão de obra terceirizada, vigilância, transporte",
    "veiculos_combustivel": "veículos, peças, combustível, pneus",
    "saude_insumos": "saúde, medicamentos, insumos e equipamentos hospitalares",
    "eventos_grafica": "eventos, gráfica, comunicação visual, locação de som, brindes",
}


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _alias_triagem(cfg: Config) -> str:
    return ALIAS_PADRAO_TRIAGEM if ALIAS_PADRAO_TRIAGEM in cfg.llm.provedores else cfg.llm.alias_padrao


def _montar_mensagens(lote: list[dict], nichos: list[str]) -> list[dict]:
    linhas = []
    for n in nichos:
        desc = NICHOS_DESCRICAO.get(n, "")
        linhas.append(f"- {n}: {desc}" if desc else f"- {n}")
    sistema = (
        "Você é um classificador de compras públicas brasileiras. Classifique cada objeto "
        "em EXATAMENTE UM nicho da lista abaixo. Se nada se encaixar, use 'outros'.\n"
        "Nichos:\n" + "\n".join(linhas) + "\n"
        "Responda SOMENTE com JSON no formato "
        '{"classificacoes":[{"id":"<id>","nicho":"<nicho>","confianca":<0..1>,'
        '"palavras_chave":["...","..."]}]}. '
        "Classifique TODOS os ids recebidos. NUNCA invente um id que não foi enviado."
    )
    itens = [
        {"id": it["id_pncp"], "objeto": (it.get("objeto") or "")[:500],
         "valor": it.get("valor_estimado"), "uf": it.get("uf")}
        for it in lote
    ]
    usuario = json.dumps({"itens": itens}, ensure_ascii=False)
    return [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}]


def normalizar_classificacoes(itens: list[dict], nichos: list[str]) -> list[dict]:
    """Valida cada classificação: nicho permitido, confiança em [0,1], palavras-chave."""
    validos = set(nichos) | {NICHO_OUTROS}
    saida = []
    for it in itens or []:
        ident = it.get("id") or it.get("id_pncp")
        if not ident:
            continue
        nicho = str(it.get("nicho") or "").strip().lower()
        if nicho not in validos:
            nicho = NICHO_OUTROS
        try:
            conf = float(it.get("confianca", 0.0))
        except (TypeError, ValueError):
            conf = 0.0
        conf = max(0.0, min(1.0, conf))
        kws = it.get("palavras_chave") or []
        if isinstance(kws, str):
            kws = [kws]
        kws = [str(k) for k in kws if str(k).strip()]
        saida.append({"id": str(ident), "nicho": nicho, "confianca": conf, "palavras_chave": kws})
    return saida


def classificar_lote(alias: str, lote: list[dict], nichos: list[str], *,
                     max_tokens: int = 4000) -> tuple[list[dict], llm.LLMResult]:
    """Chama o modelo para um lote e devolve (classificações normalizadas, resultado)."""
    msgs = _montar_mensagens(lote, nichos)
    dados, resultado = llm.chat_json(alias, msgs, max_tokens=max_tokens)
    itens = dados.get("classificacoes") or dados.get("itens") or []
    return normalizar_classificacoes(itens, nichos), resultado


def _pendentes(conn, limite: int | None) -> list[dict]:
    sql = (
        "SELECT c.id_pncp, c.objeto, c.valor_estimado, c.uf "
        "FROM contratacoes c LEFT JOIN triagens t ON t.id_pncp = c.id_pncp "
        "WHERE t.id_pncp IS NULL AND c.objeto IS NOT NULL "
        "ORDER BY c.data_publicacao DESC"
    )
    if limite:
        sql += f" LIMIT {int(limite)}"
    return [dict(r) for r in conn.execute(sql).fetchall()]


def _salvar(conn, id_pncp, nicho, conf, kws, modelo):
    conn.execute(
        "INSERT INTO triagens (id_pncp, nicho, confianca, palavras_chave, modelo_usado, criado_em) "
        "VALUES (?,?,?,?,?,?) ON CONFLICT(id_pncp) DO UPDATE SET "
        "nicho=excluded.nicho, confianca=excluded.confianca, "
        "palavras_chave=excluded.palavras_chave, modelo_usado=excluded.modelo_usado, "
        "criado_em=excluded.criado_em",
        (id_pncp, nicho, conf, json.dumps(kws, ensure_ascii=False), modelo, _agora()),
    )


def triar(conn, *, cfg: Config | None = None, alias: str | None = None, nichos: list[str] | None = None,
          lote: int = 20, limite: int | None = None, classificar=None) -> dict:
    """Classifica as contratações ainda não triadas. `classificar` é injetável (testes)."""
    cfg = cfg or carregar_config()
    nichos = nichos or cfg.app.nichos
    pendentes = _pendentes(conn, limite)

    if classificar is None:
        alias = alias or _alias_triagem(cfg)
        classificar = lambda lote_itens: classificar_lote(alias, lote_itens, nichos)  # noqa: E731

    resumo = {"pendentes": len(pendentes), "lotes": 0, "classificados": 0,
              "outros": 0, "baixa_confianca": 0, "sem_resposta": 0,
              "tokens_entrada": 0, "tokens_saida": 0, "custo_usd": 0.0, "tempo_s": 0.0}
    t0 = time.time()

    for i in range(0, len(pendentes), lote):
        fatia = pendentes[i:i + lote]
        resumo["lotes"] += 1
        try:
            resultado, meta = classificar(fatia)
        except Exception as exc:  # noqa: BLE001 — um lote ruim não deve derrubar a triagem
            log.error("M2 lote %d falhou: %s", resumo["lotes"], exc)
            resumo["sem_resposta"] += len(fatia)
            continue
        if meta is not None:
            resumo["tokens_entrada"] += meta.tokens_entrada
            resumo["tokens_saida"] += meta.tokens_saida
            resumo["custo_usd"] += meta.custo_usd
            modelo = meta.modelo
        else:
            modelo = "fake"

        por_id = {r["id"]: r for r in resultado}
        for it in fatia:
            r = por_id.get(it["id_pncp"])
            if r is None:
                resumo["sem_resposta"] += 1
                continue
            _salvar(conn, it["id_pncp"], r["nicho"], r["confianca"], r["palavras_chave"], modelo)
            resumo["classificados"] += 1
            if r["nicho"] == NICHO_OUTROS:
                resumo["outros"] += 1
            if r["confianca"] < 0.5:
                resumo["baixa_confianca"] += 1
        conn.commit()
        log.info("M2 lote %d: %d objetos (acumulado %d)", resumo["lotes"], len(fatia), resumo["classificados"])

    resumo["tempo_s"] = round(time.time() - t0, 1)
    log.info("M2 concluído %s", resumo)
    return resumo
