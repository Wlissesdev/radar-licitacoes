"""Validação e normalização de contratações cruas vindas do PNCP.

Regra inviolável (SPEC §3): nunca inventar dado. Campo ausente/vazio vira None e
gera motivo de validação; nunca um valor inventado.

Armadilhas tratadas (SPEC §5): valores estimados vazios/zero, datas impossíveis,
campos faltantes, deduplicação pelo número de controle PNCP.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

URL_EDITAL = "https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}"


def agora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _txt(v: Any) -> str | None:
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return None


def _num(v: Any) -> float | None:
    """Número estritamente positivo; caso contrário None ('não informado')."""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


def _int(v: Any) -> int | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _dt(v: Any) -> datetime | None:
    s = _txt(v)
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def validar_contratacao(raw: dict) -> dict | None:
    """Normaliza um registro cru. Devolve a linha pronta para o banco, ou None se
    não houver número de controle PNCP (chave primária) — nesse caso o registro é
    descartado e o motivo é responsabilidade do chamador registrar."""
    id_pncp = _txt(raw.get("numeroControlePNCP"))
    if not id_pncp:
        return None

    orgao = raw.get("orgaoEntidade") or {}
    unidade = raw.get("unidadeOrgao") or {}
    cnpj = _txt(orgao.get("cnpj"))
    ano = _int(raw.get("anoCompra"))
    seq = _int(raw.get("sequencialCompra"))

    publicacao = _dt(raw.get("dataPublicacaoPncp"))
    abertura = _dt(raw.get("dataAberturaProposta"))
    encerramento = _dt(raw.get("dataEncerramentoProposta"))
    objeto = _txt(raw.get("objetoCompra"))
    valor = _num(raw.get("valorTotalEstimado"))
    uf = _txt(unidade.get("ufSigla"))

    motivos: list[str] = []
    if not objeto:
        motivos.append("objeto não informado")
    if valor is None:
        motivos.append("valor estimado não informado (ou zero)")
    if not uf:
        motivos.append("UF não informada")
    if not encerramento:
        motivos.append("prazo de propostas não informado")
    if publicacao and abertura and abertura < publicacao:
        motivos.append("data de abertura anterior à publicação")
    if abertura and encerramento and encerramento < abertura:
        motivos.append("encerramento anterior à abertura")

    if publicacao and encerramento and encerramento < publicacao:
        motivos.append("encerramento anterior à publicação")

    url_oficial = URL_EDITAL.format(cnpj=cnpj, ano=ano, seq=seq) if (cnpj and ano and seq) else None

    if encerramento is not None:
        abertas = 1 if encerramento >= agora() else 0
    else:
        abertas = None

    return {
        "id_pncp": id_pncp,
        "orgao": _txt(orgao.get("razaoSocial")),
        "cnpj_orgao": cnpj,
        "ano_compra": ano,
        "sequencial": seq,
        "uf": uf,
        "municipio": _txt(unidade.get("municipioNome")),
        "modalidade": _txt(raw.get("modalidadeNome")),
        "modalidade_id": _int(raw.get("modalidadeId")),
        "objeto": objeto,
        "valor_estimado": valor,
        "data_publicacao": publicacao.isoformat() if publicacao else None,
        "data_abertura": abertura.isoformat() if abertura else None,
        "data_encerramento_propostas": encerramento.isoformat() if encerramento else None,
        # Preenchido no M3 a partir de itens[].tipoBeneficio (ver docs/RECON_PNCP.md).
        "exclusivo_mei_epp": None,
        "propostas_abertas": abertas,
        "url_oficial": url_oficial,
        "url_sistema_origem": _txt(raw.get("linkSistemaOrigem")) or _txt(raw.get("linkProcessoEletronico")),
        "status_validacao": "suspeito" if motivos else "ok",
        "motivo_validacao": "; ".join(motivos) if motivos else None,
        "raw_json": json.dumps(raw, ensure_ascii=False),
        "coletado_em": agora().isoformat(timespec="seconds"),
    }


def apto_para_boletim(linha: dict) -> bool:
    """Critério mínimo para entrar no boletim (SPEC §3: sem link/objeto não vai)."""
    return bool(linha.get("id_pncp") and linha.get("objeto") and linha.get("url_oficial"))
