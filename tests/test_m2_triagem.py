"""Testes do M2 (triagem) — sem rede: classificar injetado."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from radar import db
from radar.m2_triagem import NICHO_OUTROS, normalizar_classificacoes, triar


NICHOS = ["papelaria_escritorio", "ti_equipamentos", "alimentos_merenda"]


class TestNormalizar(unittest.TestCase):
    def test_nicho_invalido_vira_outros(self):
        (c,) = normalizar_classificacoes([{"id": "A", "nicho": "foguete", "confianca": 0.9}], NICHOS)
        self.assertEqual(c["nicho"], NICHO_OUTROS)

    def test_confianca_fora_da_faixa_e_limitada(self):
        cls = normalizar_classificacoes(
            [{"id": "A", "nicho": "ti_equipamentos", "confianca": 5},
             {"id": "B", "nicho": "ti_equipamentos", "confianca": -1},
             {"id": "C", "nicho": "ti_equipamentos", "confianca": "abc"}], NICHOS)
        self.assertEqual(cls[0]["confianca"], 1.0)
        self.assertEqual(cls[1]["confianca"], 0.0)
        self.assertEqual(cls[2]["confianca"], 0.0)

    def test_palavras_chave_string_vira_lista(self):
        (c,) = normalizar_classificacoes([{"id": "A", "nicho": "ti_equipamentos",
                                           "palavras_chave": "notebook"}], NICHOS)
        self.assertEqual(c["palavras_chave"], ["notebook"])

    def test_item_sem_id_e_ignorado(self):
        self.assertEqual(normalizar_classificacoes([{"nicho": "ti_equipamentos"}], NICHOS), [])


class TestTriar(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.conectar(Path(self.tmp.name) / "t.db")
        db.init_db(self.conn)
        for i in range(5):
            db.upsert_contratacao(self.conn, {
                "id_pncp": f"ID-{i}", "objeto": f"objeto {i}", "uf": "MA",
                "valor_estimado": 100.0, "data_publicacao": "2026-11-20T00:00:00",
                "status_validacao": "ok",
            })

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def _contar(self):
        return self.conn.execute("SELECT COUNT(*) FROM triagens").fetchone()[0]

    def test_triar_persiste_e_respeita_lote(self):
        chamadas = []

        def fake(lote):
            chamadas.append(len(lote))
            return ([{"id": it["id_pncp"], "nicho": "papelaria_escritorio",
                      "confianca": 0.9, "palavras_chave": []} for it in lote], None)

        resumo = triar(self.conn, nichos=NICHOS, lote=2, classificar=fake)
        self.assertEqual(resumo["classificados"], 5)
        self.assertEqual(chamadas, [2, 2, 1])
        self.assertEqual(self._contar(), 5)

    def test_nao_retria_ja_classificados(self):
        fake = lambda lote: ([{"id": it["id_pncp"], "nicho": "outros", "confianca": 0.1,
                               "palavras_chave": []} for it in lote], None)  # noqa: E731
        r1 = triar(self.conn, nichos=NICHOS, lote=10, classificar=fake)
        r2 = triar(self.conn, nichos=NICHOS, lote=10, classificar=fake)
        self.assertEqual(r1["classificados"], 5)
        self.assertEqual(r2["pendentes"], 0)
        self.assertEqual(r1["outros"], 5)
        self.assertEqual(self._contar(), 5)

    def test_falha_de_lote_nao_derruba(self):
        estado = {"n": 0}

        def fake(lote):
            estado["n"] += 1
            if estado["n"] == 1:
                raise RuntimeError("modelo fora do ar")
            return ([{"id": it["id_pncp"], "nicho": "ti_equipamentos", "confianca": 0.8,
                      "palavras_chave": []} for it in lote], None)

        resumo = triar(self.conn, nichos=NICHOS, lote=2, classificar=fake)
        self.assertEqual(resumo["sem_resposta"], 2)
        self.assertEqual(resumo["classificados"], 3)


if __name__ == "__main__":
    unittest.main()
