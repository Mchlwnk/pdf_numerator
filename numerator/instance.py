"""Pojedyncza instancja: plik z portem i tokenem oraz zamykanie starej kopii."""

from __future__ import annotations

import json
import os
import socket
import time
import urllib.request
from pathlib import Path

APP_MARKER = "pdf-numerator"


def instance_file() -> Path:
    override = os.environ.get("PDFN_INSTANCE_FILE")
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "PDFNumerator" / "instance.json"


def read_instance() -> dict | None:
    try:
        data = json.loads(instance_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def write_instance(port: int, token: str) -> None:
    path = instance_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"app": APP_MARKER, "port": port, "token": token}),
            encoding="utf-8",
        )
    except OSError:
        pass


def clear_instance() -> None:
    try:
        instance_file().unlink()
    except OSError:
        pass


def stop_previous(timeout: float = 3.0) -> bool:
    """Zamyka poprzednią kopię programu, jeśli nadal działa na zapisanym porcie."""
    data = read_instance()
    if not data or data.get("app") != APP_MARKER:
        return False
    port = data.get("port")
    token = data.get("token")
    if not isinstance(port, int) or not isinstance(token, str):
        return False

    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/health", timeout=1.5
        ) as response:
            health = json.loads(response.read().decode("utf-8"))
        if health.get("app") != APP_MARKER:
            return False
    except Exception:
        return False

    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/quit",
            data=b"{}",
            method="POST",
            headers={"Content-Type": "application/json", "X-Token": token},
        )
        urllib.request.urlopen(request, timeout=2.0).read()
    except Exception:
        pass

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", port))
                return True
            except OSError:
                time.sleep(0.15)
    return True
