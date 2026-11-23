"""Mede a acurácia do M2 a partir da planilha preenchida à mão (tools/revisar_m2.py).

Uso:
  py -3.11 tools/acuracia_m2.py [--csv data/revisao_m2.csv]
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RAIZ = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(RAIZ / "data" / "revisao_m2.csv"))
    args = ap.parse_args()

    caminho = Path(args.csv)
    if not caminho.exists():
        print(f"planilha não encontrada: {caminho}")
        return 1

    total = acertos = 0
    confusao = defaultdict(int)
    nao_preenchido = 0
    with caminho.open(encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            correto = (row.get("nicho_correto") or "").strip().lower()
            if not correto:
                nao_preenchido += 1
                continue
            sug = (row.get("nicho_sugerido") or "").strip().lower()
            total += 1
            if correto == sug:
                acertos += 1
            else:
                confusao[(sug, correto)] += 1

    if total == 0:
        print(f"Nenhuma linha preenchida ({nao_preenchido} em branco).")
        print("Preencha a coluna 'nicho_correto' na planilha e rode de novo.")
        return 1

    print(f"Revisadas: {total} (em branco: {nao_preenchido})")
    print(f"Acurácia : {acertos}/{total} = {acertos / total:.1%}")
    if confusao:
        print("\nErros mais comuns (sugerido -> correto):")
        for (sug, cor), n in sorted(confusao.items(), key=lambda kv: -kv[1]):
            print(f"  {n:3d}  {sug} -> {cor}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
