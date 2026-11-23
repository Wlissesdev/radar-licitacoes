"""Testes do M1 (coleta) com cliente falso e banco temporário."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from radar.db import conectar, contar, init_db
from radar.m1_coleta import coletar


def raw(id_pncp: str, **over) -> dict:
    r = {
        "numeroControlePNCP": id_pncp,
        "anoCompra": 2026,
        "sequencialCompra": 1,
        "objetoCompra": "Água mineral",
        "valorTotalEstimado": 500.0,
        "dataPublicacaoPncp": "2026-11-16T08:00:00",
        "dataEncerramentoProposta": "2026-12-01T08:00:00",
        "modalidadeId": 8,
        "modalidadeNome": "Dispensa",
        "orgaoEntidade": {"cnpj": "111", "razaoSocial": "Órgão"},
        "unidadeOrgao": {"ufSigla": "MA", "municipioNome": "Imperatriz"},
    }
    r.update(over)
    return r


class FakeClient:
    def __init__(self, paginas: dict):
        self.paginas = paginas

    def paginar_publicacoes(self, uf, modalidade, data_ini, data_fim, max_paginas=None):
        yield from self.paginas.get((uf, modalidade), [])


class TestM1(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = conectar(Path(self.tmp.name) / "t.db")
        init_db(self.conn)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_coleta_conta_novos_ok_suspeitos_invalidos(self):
        client = FakeClient({
            ("MA", 8): [
                raw("A"),
                raw("B", valorTotalEstimado=0),          # suspeito
                raw("C"),                                # ok
                {"sem": "numeroControle"},                # inválido (descartado)
            ],
            ("MA", 6): [raw("D")],
        })
        resumo = coletar(client, self.conn, ufs=["MA"], modalidades=[8, 6], dias=7)
        self.assertEqual(resumo["vistos"], 5)
        self.assertEqual(resumo["gravados"], 4)
        self.assertEqual(resumo["novos"], 4)
        self.assertEqual(resumo["invalidos"], 1)
        self.assertEqual(resumo["suspeitos"], 1)
        self.assertEqual(resumo["ok"], 3)
        self.assertEqual(contar(self.conn), 4)

    def test_segunda_coleta_nao_conta_como_novo(self):
        client = FakeClient({("MA", 8): [raw("A")]})
        coletar(client, self.conn, ufs=["MA"], modalidades=[8])
        resumo = coletar(client, self.conn, ufs=["MA"], modalidades=[8])
        self.assertEqual(resumo["novos"], 0)
        self.assertEqual(contar(self.conn), 1)


if __name__ == "__main__":
    unittest.main()
