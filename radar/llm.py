"""Wrapper LLM único — função chat(model_alias, messages).

Trata, de forma centralizada:
  - retry com backoff exponencial + jitter em erros temporários (429, 5xx, rede, timeout);
  - fallback entre provedores (DeepSeek <-> Kimi/NVIDIA), conforme config.yaml;
  - timeout por provedor;
  - log de cada tentativa (entrada, saída, erro);
  - controle de custo em tokens (ledger em logs/custos_llm.jsonl).

Trocar de modelo é uma linha no config.yaml. Nada aqui conhece nomes de modelo
"hard-coded": tudo vem da configuração.
"""
from __future__ import annotations

import json
import logging
import os
import random
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import requests

from .config import Config, ProvedorLLM, RAIZ, carregar_config, chave_provedor

log = logging.getLogger("radar.llm")

# Base do backoff (segundos). Testes zeram esta constante para não dormir.
BACKOFF_BASE_S = 1.5
LEDGER = Path(RAIZ) / "logs" / "custos_llm.jsonl"

_config_cache: Config | None = None
_custo_acumulado_usd = 0.0


class LLMError(RuntimeError):
    """Falha definitiva após esgotar retries e fallback."""


class _Temporario(Exception):
    """Erro que vale a pena repetir no mesmo provedor (429/5xx/rede)."""


class _Definitivo(Exception):
    """Erro que NÃO deve ser repetido no mesmo provedor (4xx, payload inválido)."""


@dataclass
class LLMResult:
    text: str
    alias_pedido: str
    provedor: str
    modelo: str
    tokens_entrada: int
    tokens_saida: int
    custo_usd: float
    tentativas: int
    latencia_s: float


def _config() -> Config:
    global _config_cache
    if _config_cache is None:
        _config_cache = carregar_config()
    return _config_cache


def _definir_config(cfg: Config | None) -> None:
    """Usado por testes para injetar uma configuração."""
    global _config_cache
    _config_cache = cfg


def _post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: int):
    """Ponto único de acesso HTTP — substituível em testes."""
    return requests.post(url, headers=headers, json=payload, timeout=timeout)


def _calcular_custo(prov: ProvedorLLM, tokens_entrada: int, tokens_saida: int) -> float:
    return (
        tokens_entrada / 1_000_000 * prov.preco_entrada_por_mtok_usd
        + tokens_saida / 1_000_000 * prov.preco_saida_por_mtok_usd
    )


def _extrair_uso(data: dict[str, Any]) -> tuple[int, int]:
    uso = data.get("usage") or {}
    ti = uso.get("prompt_tokens", uso.get("input_tokens", 0)) or 0
    to = uso.get("completion_tokens", uso.get("output_tokens", 0)) or 0
    return int(ti), int(to)


def _chamar_uma_vez(
    prov: ProvedorLLM,
    messages: list[dict[str, str]],
    *,
    temperature: float,
    max_tokens: int | None,
    json_mode: bool,
) -> tuple[str, int, int]:
    chave = chave_provedor(prov)
    if not chave:
        raise _Definitivo(f"chave de API ausente ({prov.api_key_env})")

    url = prov.base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {chave}", "Content-Type": "application/json"}
    payload: dict[str, Any] = {
        "model": prov.modelo,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if json_mode and prov.suporta_json:
        payload["response_format"] = {"type": "json_object"}

    try:
        resp = _post_json(url, headers, payload, prov.timeout_s)
    except requests.exceptions.RequestException as exc:
        raise _Temporario(f"erro de rede: {exc}") from exc

    sc = resp.status_code
    if sc == 200:
        try:
            data = resp.json()
            escolha = data["choices"][0]
            mensagem = escolha.get("message") or {}
            # Modelos de raciocínio (ex.: kimi-k3.1-pro) podem devolver content=None
            # quando max_tokens é consumido por reasoning_content.
            texto = (mensagem.get("content") or "").strip()
            finish = escolha.get("finish_reason")
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise _Definitivo(f"resposta malformada: {exc}") from exc
        if not texto:
            raise _Definitivo(f"resposta sem conteúdo (finish_reason={finish}); aumente max_tokens")
        ti, to = _extrair_uso(data)
        return texto, ti, to
    if sc == 429 or 500 <= sc < 600:
        raise _Temporario(f"HTTP {sc}: {resp.text[:200]}")
    raise _Definitivo(f"HTTP {sc}: {resp.text[:200]}")


def _registrar_ledger(registro: dict[str, Any]) -> None:
    global _custo_acumulado_usd
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(registro, ensure_ascii=False) + "\n")
    except OSError as exc:  # noqa: BLE001
        log.warning("não foi possível gravar o ledger de custos: %s", exc)
    _custo_acumulado_usd += float(registro.get("custo_usd", 0.0))


def custo_acumulado_usd() -> float:
    """Custo somado desde o início do processo (também gravado no ledger)."""
    return _custo_acumulado_usd


def chat(
    model_alias: str,
    messages: Iterable[dict[str, str]],
    *,
    temperature: float = 0.0,
    max_tokens: int | None = None,
    json_mode: bool = False,
) -> LLMResult:
    """Envia `messages` ao provedor de `model_alias`, com retry e fallback.

    Devolve um LLMResult. Levanta LLMError se todos os provedores da cadeia falharem.
    """
    cfg = _config()
    messages = list(messages)
    if model_alias not in cfg.llm.provedores:
        raise LLMError(f"alias desconhecido: '{model_alias}'")

    cadeia = cfg.llm.fallback.get(model_alias, [model_alias])
    erros: list[str] = []
    tentativas_total = 0

    for nome in cadeia:
        prov = cfg.llm.provedores[nome]
        t0 = time.time()
        for tent in range(1, prov.max_tentativas + 1):
            tentativas_total += 1
            try:
                texto, ti, to = _chamar_uma_vez(
                    prov, messages, temperature=temperature, max_tokens=max_tokens, json_mode=json_mode
                )
                custo = _calcular_custo(prov, ti, to)
                latencia = time.time() - t0
                log.info(
                    "llm ok | provedor=%s modelo=%s tokens_in=%d tokens_out=%d custo_usd=%.6f tentativas=%d",
                    nome, prov.modelo, ti, to, custo, tent,
                )
                _registrar_ledger(
                    {
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "alias_pedido": model_alias,
                        "provedor": nome,
                        "modelo": prov.modelo,
                        "ok": True,
                        "tokens_entrada": ti,
                        "tokens_saida": to,
                        "custo_usd": round(custo, 8),
                        "tentativas": tent,
                        "latencia_s": round(latencia, 3),
                    }
                )
                return LLMResult(
                    text=texto,
                    alias_pedido=model_alias,
                    provedor=nome,
                    modelo=prov.modelo,
                    tokens_entrada=ti,
                    tokens_saida=to,
                    custo_usd=custo,
                    tentativas=tentativas_total,
                    latencia_s=latencia,
                )
            except _Definitivo as exc:
                # Não repete no mesmo provedor; permite cair para o próximo da cadeia.
                log.warning("llm definitivo | provedor=%s: %s", nome, exc)
                erros.append(f"{nome}: {exc}")
                _registrar_ledger(
                    {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "alias_pedido": model_alias,
                     "provedor": nome, "ok": False, "erro": str(exc), "custo_usd": 0.0}
                )
                break
            except _Temporario as exc:
                log.warning("llm temporário | provedor=%s tentativa=%d/%d: %s",
                            nome, tent, prov.max_tentativas, exc)
                if tent < prov.max_tentativas:
                    espera = BACKOFF_BASE_S * (2 ** (tent - 1)) + random.uniform(0, 0.5)
                    time.sleep(espera)
                    continue
                erros.append(f"{nome}: esgotou {prov.max_tentativas} tentativas ({exc})")
                _registrar_ledger(
                    {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "alias_pedido": model_alias,
                     "provedor": nome, "ok": False, "erro": str(exc), "custo_usd": 0.0}
                )

    raise LLMError("falha em todos os provedores -> " + " | ".join(erros))


def chat_json(
    model_alias: str,
    messages: Iterable[dict[str, str]],
    *,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> tuple[dict[str, Any], LLMResult]:
    """Como chat(), mas exige e devolve um objeto JSON (para M2/M3/M4)."""
    resultado = chat(model_alias, messages, temperature=temperature, max_tokens=max_tokens, json_mode=True)
    return extrair_json(resultado.text), resultado


def extrair_json(texto: str) -> dict[str, Any]:
    """Extrai o primeiro objeto JSON de um texto, tolerando cercas ```json."""
    limpo = texto.strip()
    if limpo.startswith("```"):
        limpo = limpo.strip("`")
        if limpo.lower().startswith("json"):
            limpo = limpo[4:]
    inicio = limpo.find("{")
    fim = limpo.rfind("}")
    if inicio == -1 or fim == -1 or fim < inicio:
        raise LLMError(f"nenhum objeto JSON encontrado na resposta: {texto[:200]!r}")
    try:
        return json.loads(limpo[inicio : fim + 1])
    except json.JSONDecodeError as exc:
        raise LLMError(f"JSON inválido: {exc}") from exc


def resultado_para_dict(r: LLMResult) -> dict[str, Any]:
    return asdict(r)
