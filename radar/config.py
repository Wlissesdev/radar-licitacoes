"""Carregamento e validação de config.yaml + variáveis de ambiente (.env).

Regra inviolável: chaves NUNCA ficam no código nem no config.yaml. Aqui só se
lê o nome da variável de ambiente (api_key_env) e o valor é buscado em runtime.
"""
from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, model_validator

RAIZ = Path(__file__).resolve().parents[1]


def _carregar_dotenv() -> None:
    """Carrega o .env da raiz do projeto, se existir (e se dotenv estiver instalado)."""
    try:
        from dotenv import load_dotenv

        load_dotenv(RAIZ / ".env")
    except Exception:  # noqa: BLE001 — dotenv é conveniência, não obrigação
        pass


class ProvedorLLM(BaseModel):
    model_config = ConfigDict(extra="allow")

    base_url: str
    api_key_env: str
    modelo: str
    suporta_json: bool = False
    timeout_s: int = 120
    max_tentativas: int = 3
    preco_entrada_por_mtok_usd: float = 0.0
    preco_saida_por_mtok_usd: float = 0.0


class LLMConfig(BaseModel):
    alias_padrao: str
    fallback: dict[str, list[str]]
    provedores: dict[str, ProvedorLLM]

    @model_validator(mode="after")
    def _validar(self) -> "LLMConfig":
        if self.alias_padrao not in self.provedores:
            raise ValueError(f"alias_padrao '{self.alias_padrao}' não existe em provedores")
        for alias, cadeia in self.fallback.items():
            if alias not in self.provedores:
                raise ValueError(f"fallback tem alias desconhecido: '{alias}'")
            for alvo in cadeia:
                if alvo not in self.provedores:
                    raise ValueError(f"fallback de '{alias}' aponta para provedor desconhecido: '{alvo}'")
        return self


class PNCPConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    base_consulta: str
    base_arquivos: str
    user_agent: str
    timeout_s: int = 90
    max_tentativas: int = 4
    pausa_entre_requisicoes_s: float = 1.0
    tamanho_pagina: int = 50


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    nome: str
    ambiente: str = "dev"
    ufs_alvo: list[str]
    modalidades_alvo: list[int]
    nichos: list[str]


class Config(BaseModel):
    app: AppConfig
    pncp: PNCPConfig
    llm: LLMConfig


def carregar_config(caminho: str | Path | None = None) -> Config:
    """Lê config.yaml, carrega o .env e devolve um objeto Config validado."""
    _carregar_dotenv()
    import yaml

    if caminho is None:
        caminho = os.environ.get("RADAR_CONFIG") or (RAIZ / "config.yaml")
    caminho = Path(caminho)
    if not caminho.exists():
        raise FileNotFoundError(f"config não encontrado: {caminho}")
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    return Config(**dados)


def chave_provedor(prov: ProvedorLLM) -> str | None:
    """Devolve a chave do provedor lida do ambiente, ou None se ausente/vazia."""
    valor = os.environ.get(prov.api_key_env, "").strip()
    return valor or None
