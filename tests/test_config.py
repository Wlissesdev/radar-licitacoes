"""Testes de configuração (sem rede, sem chaves reais)."""
from __future__ import annotations

import unittest

from radar.config import LLMConfig, carregar_config


class TestConfig(unittest.TestCase):
    def test_carrega_config_real(self):
        cfg = carregar_config()
        self.assertEqual(cfg.app.ufs_alvo, ["MA", "PA", "TO", "PI"])
        self.assertIn("deepseek", cfg.llm.provedores)
        self.assertIn("kimi_nvidia", cfg.llm.provedores)
        self.assertEqual(len(cfg.app.nichos), 9)

    def test_fallback_aponta_para_provedores_existentes(self):
        cfg = carregar_config()
        for alias, cadeia in cfg.llm.fallback.items():
            self.assertIn(alias, cfg.llm.provedores)
            for alvo in cadeia:
                self.assertIn(alvo, cfg.llm.provedores)

    def test_config_invalida_falha(self):
        with self.assertRaises(ValueError):
            LLMConfig(
                alias_padrao="inexistente",
                fallback={"deepseek": ["deepseek"]},
                provedores={
                    "deepseek": {
                        "base_url": "https://x", "api_key_env": "K", "modelo": "m",
                    }
                },
            )

    def test_fallback_para_alvo_invalido_falha(self):
        with self.assertRaises(ValueError):
            LLMConfig(
                alias_padrao="deepseek",
                fallback={"deepseek": ["deepseek", "nao_existe"]},
                provedores={
                    "deepseek": {
                        "base_url": "https://x", "api_key_env": "K", "modelo": "m",
                    }
                },
            )


if __name__ == "__main__":
    unittest.main()
