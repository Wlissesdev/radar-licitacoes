"""Tarefa 1 (Secao 13) — Reconhecimento da API do PNCP.

Executa as chamadas de verificacao usadas no relatorio docs/RECON_PNCP.md.
Uso:  py -3.11 tools/recon_pncp.py
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CONSULTA = "https://pncp.gov.br/api/consulta"
PNCP_API = "https://pncp.gov.br/pncp-api"
HEADERS = {
    # Sem User-Agent a API devolve 403. Este cabecalho e OBRIGATORIO.
    "User-Agent": "Mozilla/5.0 (compatible; RadarLicitaMEI/0.1; contato@exemplo)",
    "Accept": "application/json",
}


def get(url: str, timeout: int = 90):
    req = urllib.request.Request(url, headers=HEADERS)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, e.read(), time.time() - t0
    except Exception as e:  # noqa: BLE001
        return None, repr(e).encode(), time.time() - t0


def show(title, status, body, dt, as_json=True):
    print("=" * 72)
    print(f"[{title}] status={status} tempo={dt:.1f}s")
    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else str(body)
    if status == 200 and as_json:
        try:
            j = json.loads(text)
            if isinstance(j, dict) and "data" in j:
                print(f"  totalRegistros={j.get('totalRegistros')} retornados={len(j['data'])}")
                print("  " + json.dumps(j["data"][:1], ensure_ascii=False)[:600])
            else:
                print("  " + json.dumps(j, ensure_ascii=False)[:600])
        except Exception:  # noqa: BLE001
            print("  " + text[:400])
    else:
        print("  " + text[:400])


def main():
    # 1) itens/arquivos NAO sao servidos no host api/consulta (403 determinístico)
    print("\n### PROVA: itens/arquivos NAO existem em api/consulta (403) ###")
    cnpj0, ano0, seq0 = "01596450000151", 2026, 6
    req = urllib.request.Request(
        f"{CONSULTA}/v1/orgaos/{cnpj0}/compras/{ano0}/{seq0}/itens", headers=HEADERS
    )
    try:
        urllib.request.urlopen(req, timeout=30)
        print("  inesperado: retornou 200 (esperado 403 — usar host pncp-api)")
    except urllib.error.HTTPError as e:
        print(f"  status={e.code} (esperado 403 — usar host pncp-api)")

    # 2) publicacao por UF e modalidade
    p = urllib.parse.urlencode({
        "dataInicial": "20261116", "dataFinal": "20261123",
        "codigoModalidadeContratacao": 8, "uf": "MA", "pagina": 1, "tamanhoPagina": 10,
    })
    st, body, dt = get(f"{CONSULTA}/v1/contratacoes/publicacao?{p}")
    show("publicacao MA dispensa", st, body, dt)

    # 3) detalhe + itens + arquivos (hosts diferentes!)
    cnpj, ano, seq = "01596450000151", 2026, 6
    st, body, dt = get(f"{CONSULTA}/v1/orgaos/{cnpj}/compras/{ano}/{seq}")
    show("detalhe (api/consulta)", st, body, dt)
    st, body, dt = get(f"{PNCP_API}/v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens")
    show("itens (pncp-api) — contem tipoBeneficio", st, body, dt)
    st, body, dt = get(f"{PNCP_API}/v1/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos")
    show("arquivos (pncp-api)", st, body, dt)

    # 4) download do primeiro PDF de edital
    st, body, dt = get(f"{PNCP_API}/v1/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos/1", timeout=120)
    magic = body[:5] if isinstance(body, bytes) else b""
    print("=" * 72)
    print(f"[download arquivo 1] status={st} tempo={dt:.1f}s bytes={len(body)} magic={magic}")
    print(f"  e PDF: {magic == b'%PDF-'}")

    # 5) endpoint quebrado
    st, body, dt = get(f"{CONSULTA}/v1/contratacoes/proposta?"
                       + urllib.parse.urlencode({"dataFinal": "20261231", "uf": "MA",
                                                 "pagina": 1, "tamanhoPagina": 10}), timeout=90)
    show("proposta (esperado 500)", st, body, dt, as_json=False)


if __name__ == "__main__":
    main()
