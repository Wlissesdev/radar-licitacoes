"""Cliente HTTP da API do PNCP.

Cobre os DOIS hosts (ver docs/RECON_PNCP.md):
  - base_consulta : https://pncp.gov.br/api/consulta  (listagem, detalhe, contratos, atas)
  - base_arquivos : https://pncp.gov.br/pncp-api      (itens, anexos, download de PDF)

Responsabilidades: User-Agent, retry com backoff exponencial + jitter, timeout,
pausa entre requisições e cache local em disco com TTL.
"""
from __future__ import annotations

import hashlib
import json
import logging
import random
import time
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlencode

import requests

from .config import PNCPConfig, RAIZ, carregar_config

log = logging.getLogger("radar.pncp")

# Base do backoff (s). Testes zeram para não dormir.
BACKOFF_BASE_S = 1.5


class PNCPError(RuntimeError):
    """Erro definitivo ao consultar o PNCP (após esgotar tentativas)."""


def _http_get(url: str, headers: dict[str, str], timeout: int):
    """Ponto único de acesso HTTP — substituível em testes."""
    return requests.get(url, headers=headers, timeout=timeout)


def _espera(tentativa: int) -> None:
    time.sleep(BACKOFF_BASE_S * (2 ** (tentativa - 1)) + random.uniform(0, 0.5))


class PNCPClient:
    def __init__(
        self,
        cfg: PNCPConfig | None = None,
        *,
        usar_cache: bool = True,
        cache_dir: Path | None = None,
    ) -> None:
        self.cfg = cfg or carregar_config().pncp
        self.usar_cache = usar_cache
        self.cache_dir = Path(cache_dir) if cache_dir else (RAIZ / "cache" / "pncp")

    # ---------- cache ----------
    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / (hashlib.sha1(url.encode("utf-8")).hexdigest() + ".json")

    def _ler_cache(self, url: str) -> Any | None:
        if not self.usar_cache:
            return None
        p = self._cache_path(url)
        if not p.exists():
            return None
        if time.time() - p.stat().st_mtime > self.cfg.cache_ttl_h * 3600:
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _gravar_cache(self, url: str, data: Any) -> None:
        if not self.usar_cache:
            return
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._cache_path(url).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:  # noqa: BLE001
            log.warning("não foi possível gravar cache: %s", exc)

    # ---------- transporte ----------
    def _com_retry(self, url: str) -> tuple[int, bytes]:
        headers = {"User-Agent": self.cfg.user_agent, "Accept": "application/json"}
        ultimo = "sem tentativas"
        for tent in range(1, self.cfg.max_tentativas + 1):
            try:
                resp = _http_get(url, headers, self.cfg.timeout_s)
            except requests.exceptions.RequestException as exc:
                ultimo = f"erro de rede: {exc}"
                log.warning("pncp temporário tentativa=%d/%d: %s", tent, self.cfg.max_tentativas, ultimo)
                if tent < self.cfg.max_tentativas:
                    _espera(tent)
                    continue
                break

            sc = resp.status_code
            if sc == 200:
                time.sleep(self.cfg.pausa_entre_requisicoes_s)
                return 200, resp.content
            if sc == 204:
                return 204, b""
            if sc == 429 or 500 <= sc < 600:
                ultimo = f"HTTP {sc}: {resp.text[:160]}"
                log.warning("pncp temporário tentativa=%d/%d: %s", tent, self.cfg.max_tentativas, ultimo)
                if tent < self.cfg.max_tentativas:
                    _espera(tent)
                    continue
                break
            # 4xx não-429: definitivo
            raise PNCPError(f"HTTP {sc} em {url}: {resp.text[:200]}")

        raise PNCPError(f"esgotou {self.cfg.max_tentativas} tentativas em {url}: {ultimo}")

    def _buscar(self, base: str, path: str, params: dict[str, Any] | None = None) -> Any:
        url = base.rstrip("/") + path
        if params:
            url = url + "?" + urlencode(params)
        cacheado = self._ler_cache(url)
        if cacheado is not None:
            return cacheado
        status, body = self._com_retry(url)
        data = json.loads(body.decode("utf-8")) if (status == 200 and body) else {}
        self._gravar_cache(url, data)
        return data

    # ---------- endpoints (base_consulta) ----------
    def _contratacoes(self, path: str, uf: str, modalidade: int, data_ini: str, data_fim: str,
                      pagina: int = 1, tamanho: int | None = None) -> dict:
        params = {
            "dataInicial": data_ini,
            "dataFinal": data_fim,
            "codigoModalidadeContratacao": modalidade,
            "uf": uf,
            "pagina": pagina,
            "tamanhoPagina": tamanho or self.cfg.tamanho_pagina,
        }
        return self._buscar(self.cfg.base_consulta, path, params)

    def publicacoes(self, uf: str, modalidade: int, data_ini: str, data_fim: str,
                    pagina: int = 1, tamanho: int | None = None) -> dict:
        return self._contratacoes("/v1/contratacoes/publicacao", uf, modalidade, data_ini, data_fim, pagina, tamanho)

    def atualizacoes(self, uf: str, modalidade: int, data_ini: str, data_fim: str,
                     pagina: int = 1, tamanho: int | None = None) -> dict:
        return self._contratacoes("/v1/contratacoes/atualizacao", uf, modalidade, data_ini, data_fim, pagina, tamanho)

    def detalhe(self, cnpj: str, ano: int, sequencial: int) -> dict:
        return self._buscar(self.cfg.base_consulta, f"/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}")

    def paginar_publicacoes(self, uf: str, modalidade: int, data_ini: str, data_fim: str,
                            max_paginas: int | None = None) -> Iterator[dict]:
        pagina = 1
        while True:
            j = self.publicacoes(uf, modalidade, data_ini, data_fim, pagina)
            dados = (j or {}).get("data") or []
            for r in dados:
                yield r
            total = (j or {}).get("totalPaginas") or 0
            if not dados or pagina >= total or (max_paginas and pagina >= max_paginas):
                break
            pagina += 1

    # ---------- endpoints (base_arquivos) ----------
    def itens(self, cnpj: str, ano: int, sequencial: int) -> list:
        return self._buscar(self.cfg.base_arquivos, f"/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/itens") or []

    def arquivos(self, cnpj: str, ano: int, sequencial: int) -> list:
        return self._buscar(self.cfg.base_arquivos, f"/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos") or []

    def baixar_arquivo(self, cnpj: str, ano: int, sequencial: int, n: int) -> bytes:
        url = (f"{self.cfg.base_arquivos.rstrip('/')}"
               f"/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos/{n}")
        _, body = self._com_retry(url)
        return body
