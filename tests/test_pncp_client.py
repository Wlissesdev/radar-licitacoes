"""Testes do cliente PNCP (sem rede: _http_get substituído)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from radar import pncp_client as pncp
from radar.config import PNCPConfig


class FakeResp:
    def __init__(self, status: int, body: bytes | str = b"", text: str | None = None):
        self.status_code = status
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.content = body
        self.text = text if text is not None else body.decode("utf-8", "replace")


def cfg() -> PNCPConfig:
    return PNCPConfig(
        base_consulta="https://pncp.gov.br/api/consulta",
        base_arquivos="https://pncp.gov.br/pncp-api",
        user_agent="teste",
        pausa_entre_requisicoes_s=0.0,
        max_tentativas=3,
    )


class TestPNCPClient(unittest.TestCase):
    def setUp(self):
        pncp.BACKOFF_BASE_S = 0.0
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def _client(self, usar_cache=False):
        return pncp.PNCPClient(cfg(), usar_cache=usar_cache, cache_dir=Path(self.tmp.name))

    def test_sucesso_parses_json(self):
        corpo = json.dumps({"data": [{"numeroControlePNCP": "A"}], "totalPaginas": 1}).encode()
        with mock.patch.object(pncp, "_http_get", return_value=FakeResp(200, corpo)):
            j = self._client().publicacoes("MA", 8, "20261116", "20261123")
        self.assertEqual(j["data"][0]["numeroControlePNCP"], "A")

    def test_retry_em_429(self):
        corpo = json.dumps({"data": [], "totalPaginas": 0}).encode()
        respostas = [FakeResp(429, text="rate"), FakeResp(200, corpo)]
        with mock.patch.object(pncp, "_http_get", side_effect=respostas) as m:
            j = self._client().publicacoes("MA", 8, "20261116", "20261123")
        self.assertEqual(m.call_count, 2)
        self.assertEqual(j["totalPaginas"], 0)

    def test_204_devolve_vazio(self):
        with mock.patch.object(pncp, "_http_get", return_value=FakeResp(204)):
            j = self._client().publicacoes("MA", 8, "20261116", "20261123")
        self.assertEqual(j, {})

    def test_4xx_e_definitivo(self):
        with mock.patch.object(pncp, "_http_get", return_value=FakeResp(400, text="bad")):
            with self.assertRaises(pncp.PNCPError):
                self._client().publicacoes("MA", 8, "20261116", "20261123")

    def test_cache_evita_segunda_chamada(self):
        corpo = json.dumps({"data": [], "totalPaginas": 0}).encode()
        with mock.patch.object(pncp, "_http_get", return_value=FakeResp(200, corpo)) as m:
            c = self._client(usar_cache=True)
            c.publicacoes("MA", 8, "20261116", "20261123")
            c.publicacoes("MA", 8, "20261116", "20261123")
        self.assertEqual(m.call_count, 1)

    def test_baixar_arquivo_devolve_bytes(self):
        with mock.patch.object(pncp, "_http_get", return_value=FakeResp(200, b"%PDF-1.7")):
            b = self._client().baixar_arquivo("01596450000151", 2026, 6, 1)
        self.assertTrue(b.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
