"""CLI do Radar Licita MEI: `py -3.11 -m radar <comando>`.

Comandos:
  config            Mostra a configuração resolvida (sem segredos).
  ping [alias]      Faz uma chamada mínima ao modelo e mostra tokens/custo.
  recon             Roda o reconhecimento da API do PNCP (Tarefa 1).
"""
from __future__ import annotations

import argparse
import json
import sys

from .config import carregar_config, chave_provedor
from .logging_setup import configurar_logging


def _cmd_config(_args: argparse.Namespace) -> int:
    cfg = carregar_config()
    print(json.dumps(cfg.model_dump(), ensure_ascii=False, indent=2))
    print("\n# Chaves presentes no ambiente:")
    for alias, prov in cfg.llm.provedores.items():
        presente = "SIM" if chave_provedor(prov) else "NÃO"
        print(f"  {alias:14s} {prov.api_key_env:18s} -> {presente}")
    return 0


def _cmd_ping(args: argparse.Namespace) -> int:
    from . import llm

    cfg = carregar_config()
    alias = args.alias or cfg.llm.alias_padrao
    try:
        r = llm.chat(alias, [{"role": "user", "content": "Responda apenas: ok"}], max_tokens=256)
    except llm.LLMError as exc:
        print(f"FALHOU: {exc}")
        print("Verifique se o .env existe e se as chaves estão preenchidas.")
        return 1
    print(f"alias pedido : {r.alias_pedido}")
    print(f"provedor     : {r.provedor} ({r.modelo})")
    print(f"resposta     : {r.text.strip()[:80]!r}")
    print(f"tokens       : in={r.tokens_entrada} out={r.tokens_saida}")
    print(f"custo_usd    : {r.custo_usd:.8f}")
    print(f"tentativas   : {r.tentativas} | latência: {r.latencia_s:.2f}s")
    return 0


def _cmd_coletar(args: argparse.Namespace) -> int:
    from .db import conectar, contar, init_db
    from .m1_coleta import coletar
    from .pncp_client import PNCPClient

    cfg = carregar_config()
    ufs = args.ufs.split(",") if args.ufs else cfg.app.ufs_alvo
    modalidades = ([int(x) for x in args.modalidades.split(",")] if args.modalidades
                   else cfg.app.modalidades_alvo)

    conn = conectar(args.db) if args.db else conectar()
    init_db(conn)
    client = PNCPClient(cfg.pncp, usar_cache=not args.sem_cache)

    resumo = coletar(client, conn, ufs=ufs, modalidades=modalidades, dias=args.dias,
                     max_paginas=args.max_paginas)
    print(f"janela            : {resumo['janela']}")
    print(f"UF(s)             : {', '.join(ufs)} | modalidades: {modalidades}")
    print(f"vistos            : {resumo['vistos']}")
    print(f"gravados          : {resumo['gravados']} (novos: {resumo['novos']})")
    print(f"ok / suspeitos    : {resumo['ok']} / {resumo['suspeitos']}")
    print(f"descartados       : {resumo['invalidos']} (sem numeroControlePNCP)")
    print(f"por UF            : {resumo['por_uf']}")
    print(f"total no banco    : {contar(conn)}")
    return 0


def _cmd_recon(_args: argparse.Namespace) -> int:
    from pathlib import Path

    from .config import RAIZ

    caminho = Path(RAIZ) / "tools" / "recon_pncp.py"
    if not caminho.exists():
        print(f"script não encontrado: {caminho}")
        return 1
    import runpy

    runpy.run_path(str(caminho), run_name="__main__")
    return 0


def main(argv: list[str] | None = None) -> int:
    configurar_logging()
    parser = argparse.ArgumentParser(prog="radar", description="Radar Licita MEI")
    sub = parser.add_subparsers(dest="comando", required=True)

    sub.add_parser("config", help="mostra a configuração resolvida")

    p_ping = sub.add_parser("ping", help="testa um provedor de LLM")
    p_ping.add_argument("alias", nargs="?", help="alias do provedor (padrão: alias_padrao)")

    p_coletar = sub.add_parser("coletar", help="M1 — coleta diária do PNCP")
    p_coletar.add_argument("--dias", type=int, default=7, help="janela de publicação (padrão: 7)")
    p_coletar.add_argument("--ufs", help="UFs separadas por vírgula (padrão: config)")
    p_coletar.add_argument("--modalidades", help="códigos de modalidade separados por vírgula (padrão: config)")
    p_coletar.add_argument("--db", help="caminho do banco SQLite (padrão: data/radar.db)")
    p_coletar.add_argument("--sem-cache", action="store_true", help="ignora o cache local")
    p_coletar.add_argument("--max-paginas", type=int, default=None, help="limite de páginas por UF/modalidade")

    sub.add_parser("recon", help="reconhecimento da API do PNCP")

    args = parser.parse_args(argv)
    return {"config": _cmd_config, "ping": _cmd_ping, "coletar": _cmd_coletar, "recon": _cmd_recon}[args.comando](args)


if __name__ == "__main__":
    sys.exit(main())
