"""Configuração de logging central: console + arquivo em logs/radar.log."""
from __future__ import annotations

import logging
from pathlib import Path

from .config import RAIZ

FORMATO = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_CARREGADO = False


def configurar_logging(nivel: str = "INFO", arquivo: bool = True) -> None:
    """Idempotente: pode ser chamado por qualquer módulo sem duplicar handlers."""
    global _CARREGADO
    if _CARREGADO:
        return

    root = logging.getLogger()
    root.setLevel(getattr(logging, nivel.upper(), logging.INFO))

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(FORMATO))
    root.addHandler(console)

    if arquivo:
        destino = Path(RAIZ) / "logs" / "radar.log"
        destino.parent.mkdir(parents=True, exist_ok=True)
        fileh = logging.FileHandler(destino, encoding="utf-8")
        fileh.setFormatter(logging.Formatter(FORMATO))
        root.addHandler(fileh)

    _CARREGADO = True
