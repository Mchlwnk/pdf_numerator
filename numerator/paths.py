"""Wyliczanie nazwy pliku wyjściowego - oryginał nigdy nie jest nadpisywany."""

from __future__ import annotations

import re
from pathlib import Path

INVALID_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
MAX_STEM_LENGTH = 180


class PathError(ValueError):
    """Problem z plikiem wejściowym lub docelowym."""


def normalize_suffix(suffix: str) -> str:
    suffix = INVALID_NAME_CHARS.sub("_", suffix or "")
    return suffix.strip()


def ensure_pdf_source(path: Path) -> Path:
    """Sprawdza, że plik istnieje, jest plikiem i wygląda na PDF."""
    path = Path(path).expanduser()
    if not path.exists():
        raise PathError(f"Nie znaleziono pliku: {path}")
    if not path.is_file():
        raise PathError(f"To nie jest plik: {path}")
    try:
        with path.open("rb") as handle:
            head = handle.read(1024)
    except OSError as exc:
        raise PathError(f"Nie mogę odczytać pliku: {exc.strerror or exc}") from exc
    if b"%PDF-" not in head:
        raise PathError(
            f"Plik nie wygląda na PDF: {path.name}. Obsługiwane są tylko dokumenty PDF."
        )
    return path


def _candidate(directory: Path, stem: str, suffix: str, index: int) -> Path:
    stem = stem[: MAX_STEM_LENGTH - len(suffix)]
    name = f"{stem}{suffix}" if index <= 1 else f"{stem}{suffix}_{index}"
    return directory / f"{name}.pdf"


def resolve_output(
    source: Path,
    *,
    suffix: str = "_numerowany",
    destination: Path | None = None,
    overwrite: bool = False,
) -> Path:
    """Zwraca ścieżkę wynikową: domyślnie obok oryginału, z unikaniem kolizji."""
    source = Path(source)
    suffix = normalize_suffix(suffix)

    if destination is not None:
        destination = Path(destination).expanduser()
        if destination.suffix.lower() != ".pdf":
            destination = destination.with_suffix(".pdf")
        if destination.exists() and destination.resolve() == source.resolve():
            raise PathError("Nie można nadpisać pliku źródłowego - zapis jest zawsze kopią.")
        if destination.exists() and not overwrite:
            raise PathError(f"Plik docelowy już istnieje: {destination}")
        return destination

    directory = source.parent
    candidate = _candidate(directory, source.stem, suffix, 1)
    if overwrite:
        return candidate
    index = 1
    while candidate.exists():
        index += 1
        candidate = _candidate(directory, source.stem, suffix, index)
    return candidate


def is_writable_directory(directory: Path) -> bool:
    """Czy w katalogu da się utworzyć plik (np. nie jest to tylko-do-odczytu nośnik)."""
    probe = Path(directory) / ".pdf-numerator-test"
    try:
        probe.write_bytes(b"")
    except OSError:
        return False
    finally:
        try:
            probe.unlink()
        except OSError:
            pass
    return True
