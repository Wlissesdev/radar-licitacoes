"""Gera uma planilha (CSV) para revisão humana do M2.

Escolhe uma amostra aleatória (reprodutível) das triagens e deixa em branco a coluna
`nicho_correto` para o humano preencher. Depois, `tools/acuracia_m2.py` mede o acerto.

Uso:
  py -3.11 tools/revisar_m2.py [--n 50] [--seed 42] [--db data/radar.db]
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RAIZ = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--db", default=str(RAIZ / "data" / "radar.db"))
    ap.add_argument("--saida", default=str(RAIZ / "data" / "revisao_m2.csv"))
    args = ap.parse_args()

    import sqlite3

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    linhas = conn.execute(
        "SELECT c.id_pncp, c.uf, c.municipio, c.valor_estimado, c.objeto, "
        "       t.nicho, t.confianca, t.palavras_chave "
        "FROM triagens t JOIN contratacoes c ON c.id_pncp = t.id_pncp"
    ).fetchall()
    if not linhas:
        print("Nenhuma triagem no banco. Rode antes: py -3.11 -m radar triar")
        return 1

    random.seed(args.seed)
    amostra = random.sample(list(linhas), min(args.n, len(linhas)))

    saida = Path(args.saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    with saida.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["id_pncp", "uf", "municipio", "valor_estimado", "nicho_sugerido",
                    "confianca", "palavras_chave", "objeto", "nicho_correto", "observacao"])
        for r in amostra:
            w.writerow([r["id_pncp"], r["uf"], r["municipio"], r["valor_estimado"],
                        r["nicho"], r["confianca"], r["palavras_chave"],
                        (r["objeto"] or "").replace("\n", " "), "", ""])
    print(f"Planilha gerada com {len(amostra)} itens: {saida}")
    print("Preencha a coluna 'nicho_correto' (use os mesmos nomes de nicho) e rode:")
    print("  py -3.11 tools/acuracia_m2.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
