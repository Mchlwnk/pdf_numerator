"""Logowanie do pliku - przydatne, gdy program działa bez konsoli (EXE)."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def log_directory() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    root = Path(base) if base else Path.home() / ".local" / "share"
    return root / "PDFNumerator" / "logs"


def setup_logging(level: int = logging.INFO) -> Path:
    directory = log_directory()
    try:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "pdf-numerator.log"
        handler: logging.Handler = RotatingFileHandler(
            path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
    except OSError:
        path = Path(os.devnull)
        handler = logging.NullHandler()

    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.setLevel(level)
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    return path
