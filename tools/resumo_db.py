"""Resumo rápido do banco do Radar Licita MEI.

Uso:  py -3.11 tools/resumo_db.py [caminho_do_banco]
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RAIZ = Path(__file__).resolve().parents[1]
CAMINHO = Path(sys.argv[1]) if len(sys.argv) > 1 else (RAIZ / "data" / "radar.db")


def main() -> int:
    if not CAMINHO.exists():
        print(f"banco não encontrado: {CAMINHO}  (rode antes: py -3.11 -m radar coletar)")
        return 1
    conn = sqlite3.connect(str(CAMINHO))
    conn.row_factory = sqlite3.Row
    q = lambda sql: conn.execute(sql).fetchall()  # noqa: E731

    print(f"# Banco: {CAMINHO}")
    print(f"total de contratações: {q('SELECT COUNT(*) c FROM contratacoes')[0]['c']}\n")

    print("== Por UF ==")
    for r in q("SELECT uf, COUNT(*) n FROM contratacoes GROUP BY uf ORDER BY n DESC"):
        print(f"  {str(r['uf']):4s} {r['n']:4d}")

    print("\n== Por modalidade ==")
    for r in q("SELECT modalidade, COUNT(*) n FROM contratacoes GROUP BY modalidade ORDER BY n DESC"):
        print(f"  {r['n']:4d}  {r['modalidade']}")

    print("\n== Qualidade da validação ==")
    n_ok = q("SELECT COUNT(*) c FROM contratacoes WHERE status_validacao='ok'")[0]["c"]
    n_sus = q("SELECT COUNT(*) c FROM contratacoes WHERE status_validacao!='ok'")[0]["c"]
    n_sem_valor = q("SELECT COUNT(*) c FROM contratacoes WHERE valor_estimado IS NULL")[0]["c"]
    n_abertas = q("SELECT COUNT(*) c FROM contratacoes WHERE propostas_abertas=1")[0]["c"]
    print(f"  ok                          : {n_ok}")
    print(f"  suspeitos                   : {n_sus}")
    print(f"  sem valor informado         : {n_sem_valor}")
    print(f"  propostas ainda abertas     : {n_abertas}")

    print("\n== Motivos de suspeita ==")
    for r in q("SELECT motivo_validacao m, COUNT(*) n FROM contratacoes "
               "WHERE status_validacao!='ok' GROUP BY m ORDER BY n DESC"):
        print(f"  {r['n']:4d}  {r['m']}")

    print("\n== Amostra (maiores valores) ==")
    for r in q("SELECT uf, municipio, modalidade, valor_estimado, objeto, propostas_abertas "
               "FROM contratacoes ORDER BY valor_estimado DESC LIMIT 8"):
        valor = "não informado" if r["valor_estimado"] is None else f"R$ {r['valor_estimado']:,.2f}"
        obj = (r["objeto"] or "")[:48]
        print(f"  {str(r['uf']):3s} {str(r['municipio'])[:15]:15s} {valor:>16} "
              f"aberto={r['propostas_abertas']} | {obj}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
