"""Acesso ao banco SQLite. Esquema conforme SPEC §6 (+ campos auxiliares)."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from .config import RAIZ

DDL = """
CREATE TABLE IF NOT EXISTS contratacoes (
  id_pncp                    TEXT PRIMARY KEY,
  orgao                      TEXT,
  cnpj_orgao                 TEXT,
  ano_compra                 INTEGER,
  sequencial                 INTEGER,
  uf                         TEXT,
  municipio                  TEXT,
  modalidade                 TEXT,
  modalidade_id              INTEGER,
  objeto                     TEXT,
  valor_estimado             REAL,
  data_publicacao            TEXT,
  data_abertura              TEXT,
  data_encerramento_propostas TEXT,
  exclusivo_mei_epp          INTEGER,
  propostas_abertas          INTEGER,
  url_oficial                TEXT,
  url_sistema_origem         TEXT,
  status_validacao           TEXT,
  motivo_validacao           TEXT,
  raw_json                   TEXT,
  coletado_em                TEXT
);
CREATE INDEX IF NOT EXISTS ix_contratacoes_uf_prazo
  ON contratacoes (uf, data_encerramento_propostas);
CREATE INDEX IF NOT EXISTS ix_contratacoes_status ON contratacoes (status_validacao);

CREATE TABLE IF NOT EXISTS anexos (
  id                    INTEGER PRIMARY KEY AUTOINCREMENT,
  id_pncp               TEXT NOT NULL,
  nome                  TEXT,
  url                   TEXT,
  tipo_documento        TEXT,
  sequencial_documento  INTEGER,
  texto_extraido        TEXT,
  hash                  TEXT,
  baixado_em            TEXT,
  UNIQUE (id_pncp, sequencial_documento)
);

CREATE TABLE IF NOT EXISTS analises (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  id_pncp        TEXT NOT NULL,
  nicho          TEXT,
  resumo         TEXT,
  checklist_json TEXT,
  risco          TEXT,
  motivo_risco   TEXT,
  verificado     INTEGER DEFAULT 0,
  modelo_usado   TEXT,
  tokens_gastos  INTEGER,
  criado_em      TEXT
);

CREATE TABLE IF NOT EXISTS assinantes (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  canal      TEXT,
  chat_id    TEXT,
  nichos     TEXT,
  ufs        TEXT,
  plano      TEXT,
  status     TEXT,
  origem     TEXT,
  criado_em  TEXT
);

CREATE TABLE IF NOT EXISTS envios (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  assinante_id  INTEGER,
  id_pncp       TEXT,
  enviado_em    TEXT,
  clicou        INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS leads (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  cnpj              TEXT UNIQUE,
  razao_social      TEXT,
  municipio         TEXT,
  cnae              TEXT,
  porte             TEXT,
  telefone_publico  TEXT,
  email_publico     TEXT,
  origem_dado       TEXT,
  motivo_do_fit     TEXT,
  status            TEXT DEFAULT 'novo',
  optout            INTEGER DEFAULT 0,
  notas             TEXT,
  criado_em         TEXT
);

CREATE TABLE IF NOT EXISTS metricas_semana (
  semana            TEXT PRIMARY KEY,
  assinantes_novos  INTEGER,
  ativos            INTEGER,
  churn             INTEGER,
  receita           REAL,
  custo_ia          REAL,
  taxa_clique       REAL
);

CREATE TABLE IF NOT EXISTS triagens (
  id_pncp        TEXT PRIMARY KEY,
  nicho          TEXT,
  confianca      REAL,
  palavras_chave TEXT,
  modelo_usado   TEXT,
  criado_em      TEXT
);
"""


def caminho_padrao() -> Path:
    return Path(os.environ.get("RADAR_DB") or (RAIZ / "data" / "radar.db"))


def conectar(caminho: str | Path | None = None) -> sqlite3.Connection:
    p = Path(caminho) if caminho else caminho_padrao()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(DDL)
    conn.commit()


def upsert_contratacao(conn: sqlite3.Connection, row: dict) -> bool:
    """Insere ou atualiza. Devolve True se o registro é NOVO (não existia)."""
    cur = conn.execute("SELECT 1 FROM contratacoes WHERE id_pncp = ?", (row["id_pncp"],))
    novo = cur.fetchone() is None
    cols = list(row.keys())
    placeholders = ",".join("?" for _ in cols)
    atualiza = ",".join(f"{c}=excluded.{c}" for c in cols if c != "id_pncp")
    sql = (
        f"INSERT INTO contratacoes ({','.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT(id_pncp) DO UPDATE SET {atualiza}"
    )
    conn.execute(sql, [row[c] for c in cols])
    conn.commit()
    return novo


def contar(conn: sqlite3.Connection, tabela: str = "contratacoes") -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
