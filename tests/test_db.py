"""Testes do banco SQLite (arquivo temporário)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from radar.db import conectar, contar, init_db, upsert_contratacao


def linha(id_pncp="X-1", objeto="Papel A4", valor=100.0) -> dict:
    return {
        "id_pncp": id_pncp, "orgao": "Órgão", "cnpj_orgao": "123", "ano_compra": 2026,
        "sequencial": 1, "uf": "MA", "municipio": "Imperatriz", "modalidade": "Dispensa",
        "modalidade_id": 8, "objeto": objeto, "valor_estimado": valor,
        "data_publicacao": "2026-11-16T08:00:00", "data_abertura": None,
        "data_encerramento_propostas": "2026-12-01T08:00:00", "exclusivo_mei_epp": None,
        "propostas_abertas": 1, "url_oficial": "https://x", "url_sistema_origem": None,
        "status_validacao": "ok", "motivo_validacao": None, "raw_json": "{}",
        "coletado_em": "2026-11-23T06:00:00",
    }


class TestDB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = conectar(Path(self.tmp.name) / "t.db")
        init_db(self.conn)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_insercao_e_deduplicacao(self):
        self.assertTrue(upsert_contratacao(self.conn, linha()))
        self.assertFalse(upsert_contratacao(self.conn, linha()))  # já existe
        self.assertEqual(contar(self.conn), 1)

    def test_atualizacao_sobrescreve_campos(self):
        upsert_contratacao(self.conn, linha(valor=100.0))
        upsert_contratacao(self.conn, linha(valor=250.0))
        valor = self.conn.execute(
            "SELECT valor_estimado FROM contratacoes WHERE id_pncp='X-1'"
        ).fetchone()[0]
        self.assertEqual(valor, 250.0)

    def test_init_idempotente(self):
        init_db(self.conn)  # não deve falhar
        self.assertEqual(contar(self.conn), 0)


if __name__ == "__main__":
    unittest.main()
