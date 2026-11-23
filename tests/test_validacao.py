"""Testes de validação/normalização (sem rede)."""
from __future__ import annotations

import unittest

from radar.validacao import apto_para_boletim, validar_contratacao


def raw_base(**over) -> dict:
    r = {
        "numeroControlePNCP": "01596450000151-1-000006/2026",
        "anoCompra": 2026,
        "sequencialCompra": 6,
        "objetoCompra": "Outsourcing de impressão",
        "valorTotalEstimado": 1740.0,
        "dataPublicacaoPncp": "2026-11-16T08:28:46",
        "dataAberturaProposta": "2026-11-17T00:00:00",
        "dataEncerramentoProposta": "2026-11-20T08:00:00",
        "modalidadeId": 8,
        "modalidadeNome": "Dispensa",
        "linkSistemaOrigem": "https://www.licitama.com.br/",
        "orgaoEntidade": {"cnpj": "01596450000151", "razaoSocial": "INMEQ/MA"},
        "unidadeOrgao": {"ufSigla": "MA", "municipioNome": "São Luís"},
    }
    r.update(over)
    return r


class TestValidacao(unittest.TestCase):
    def test_registro_valido(self):
        linha = validar_contratacao(raw_base())
        self.assertEqual(linha["status_validacao"], "ok")
        self.assertIsNone(linha["motivo_validacao"])
        self.assertEqual(linha["uf"], "MA")
        self.assertEqual(linha["valor_estimado"], 1740.0)
        self.assertEqual(linha["url_oficial"], "https://pncp.gov.br/app/editais/01596450000151/2026/6")
        self.assertTrue(apto_para_boletim(linha))

    def test_valor_zero_vira_nao_informado(self):
        linha = validar_contratacao(raw_base(valorTotalEstimado=0))
        self.assertIsNone(linha["valor_estimado"])
        self.assertEqual(linha["status_validacao"], "suspeito")
        self.assertIn("valor", linha["motivo_validacao"])

    def test_abertura_antes_da_publicacao(self):
        linha = validar_contratacao(raw_base(
            dataPublicacaoPncp="2026-11-16T08:00:00",
            dataAberturaProposta="2026-11-10T08:00:00",
        ))
        self.assertEqual(linha["status_validacao"], "suspeito")
        self.assertIn("abertura anterior", linha["motivo_validacao"])

    def test_sem_numero_controle_e_descartado(self):
        self.assertIsNone(validar_contratacao(raw_base(numeroControlePNCP=None)))

    def test_strings_vazias_viram_none(self):
        linha = validar_contratacao(raw_base(objetoCompra="   ", linkSistemaOrigem=""))
        self.assertIsNone(linha["objeto"])
        self.assertIsNone(linha["url_sistema_origem"])
        self.assertIn("objeto não informado", linha["motivo_validacao"])
        self.assertFalse(apto_para_boletim(linha))


if __name__ == "__main__":
    unittest.main()
