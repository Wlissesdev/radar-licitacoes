"""Testes do wrapper LLM: sucesso, retry, fallback e chave ausente.

Não tocam a rede: substituem llm._post_json e zeram o backoff.
"""
from __future__ import annotations

import json
import os
import unittest
from unittest import mock

import requests

from radar import llm


class FakeResp:
    def __init__(self, status: int, body: dict | None = None, text: str | None = None):
        self.status_code = status
        self._body = body if body is not None else {}
        self.text = text if text is not None else json.dumps(self._body)

    def json(self):
        return self._body


def _corpo_ok(conteudo: str = "ok") -> dict:
    return {
        "choices": [{"message": {"content": conteudo}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


CHAVES = {"DEEPSEEK_API_KEY": "fake-ds", "NVIDIA_API_KEY": "fake-nv"}


class TestLLM(unittest.TestCase):
    def setUp(self):
        llm._definir_config(None)  # força recarregar o config.yaml real
        llm.BACKOFF_BASE_S = 0.0   # sem espera nos testes

    def test_sucesso_primeiro_provedor(self):
        with mock.patch.dict(os.environ, CHAVES), \
             mock.patch.object(llm, "_post_json", return_value=FakeResp(200, _corpo_ok("ok"))):
            r = llm.chat("deepseek", [{"role": "user", "content": "oi"}])
        self.assertEqual(r.text, "ok")
        self.assertEqual(r.provedor, "deepseek")
        self.assertEqual((r.tokens_entrada, r.tokens_saida), (10, 5))
        self.assertGreater(r.custo_usd, 0.0)
        self.assertEqual(r.tentativas, 1)

    def test_retry_em_429_depois_sucesso(self):
        chamadas = {"n": 0}

        def fake_post(url, headers, payload, timeout):
            chamadas["n"] += 1
            if chamadas["n"] == 1:
                return FakeResp(429, {}, "rate limit")
            return FakeResp(200, _corpo_ok())

        with mock.patch.dict(os.environ, CHAVES), \
             mock.patch.object(llm, "_post_json", side_effect=fake_post):
            r = llm.chat("deepseek", [{"role": "user", "content": "oi"}])
        self.assertEqual(r.tentativas, 2)
        self.assertEqual(r.provedor, "deepseek")

    def test_fallback_para_kimi_quando_deepseek_falha(self):
        def fake_post(url, headers, payload, timeout):
            if "deepseek" in url:
                raise requests.exceptions.ConnectionError("sem rota para deepseek")
            return FakeResp(200, _corpo_ok("resposta nvidia"))

        with mock.patch.dict(os.environ, CHAVES), \
             mock.patch.object(llm, "_post_json", side_effect=fake_post):
            r = llm.chat("deepseek", [{"role": "user", "content": "oi"}])
        self.assertEqual(r.provedor, "kimi_nvidia")
        self.assertEqual(r.text, "resposta nvidia")
        # 3 tentativas no deepseek (max_tentativas) + 1 no kimi
        self.assertGreaterEqual(r.tentativas, 2)

    def test_chave_ausente_em_todos(self):
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "", "NVIDIA_API_KEY": ""}):
            with self.assertRaises(llm.LLMError) as ctx:
                llm.chat("deepseek", [{"role": "user", "content": "oi"}])
        self.assertIn("chave", str(ctx.exception).lower())

    def test_alias_desconhecido(self):
        with self.assertRaises(llm.LLMError):
            llm.chat("nao_existe", [{"role": "user", "content": "oi"}])

    def test_resposta_sem_conteudo_falha(self):
        corpo = {"choices": [{"message": {"content": None}, "finish_reason": "length"}], "usage": {}}
        with mock.patch.dict(os.environ, CHAVES), \
             mock.patch.object(llm, "_post_json", return_value=FakeResp(200, corpo)):
            with self.assertRaises(llm.LLMError) as ctx:
                llm.chat("deepseek", [{"role": "user", "content": "oi"}])
        self.assertIn("conte", str(ctx.exception).lower())

    def test_extrair_json_com_cercas(self):
        texto = '```json\n{"a": 1, "b": [1,2]}\n```'
        self.assertEqual(llm.extrair_json(texto), {"a": 1, "b": [1, 2]})

    def test_extrair_json_invalido(self):
        with self.assertRaises(llm.LLMError):
            llm.extrair_json("sem json aqui")


if __name__ == "__main__":
    unittest.main()
