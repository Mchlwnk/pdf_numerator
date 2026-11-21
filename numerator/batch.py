"""Numerowanie wszystkich PDF-ów w folderze."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .core import number_pdf
from .options import NumberOptions
from .paths import is_writable_directory

MAX_FILES = 1000


class BatchError(RuntimeError):
    """Problem z folderem lub jego zawartością."""


@dataclass
class FolderSummary:
    folder: Path
    found: int
    done: list[dict[str, str]] = field(default_factory=list)
    failed: list[dict[str, str]] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "ok": True,
            "folder": str(self.folder),
            "found": self.found,
            "done": self.done,
            "failed": self.failed,
            "skipped": self.skipped,
            "numbered": len(self.done),
            "errors": len(self.failed),
        }

    def describe(self) -> str:
        if not self.failed:
            return f"Ponumerowano {len(self.done)} z {self.found} plików w {self.folder.name}."
        return (
            f"Ponumerowano {len(self.done)} z {self.found} plików, "
            f"{len(self.failed)} nie udało się."
        )


def read_folder(folder: str | Path, recursive: bool = False) -> Path:
    """Waliduje folder wejściowy."""
    path = Path(folder).expanduser()
    if not path.exists():
        raise BatchError(f"Nie znaleziono folderu: {path}")
    if not path.is_dir():
        raise BatchError(f"To nie jest folder: {path}")
    return path


def find_pdfs(folder: str | Path, recursive: bool = False,
              suffix: str | None = "_numerowany") -> list[Path]:
    """Lista plików PDF w folderze (bez kopii utworzonych wcześniej przez program)."""
    root = read_folder(folder, recursive)
    candidates = root.rglob("*") if recursive else root.glob("*")
    files: list[Path] = []
    for path in sorted(candidates, key=lambda p: p.name.lower()):
        if not path.is_file() or path.suffix.lower() != ".pdf":
            continue
        if suffix and _is_output_name(path.name, suffix):
            continue
        files.append(path)
    return files


def _is_output_name(name: str, suffix: str) -> bool:
    """Czy plik wygląda na kopię utworzoną przez program (np. raport_numerowany_2.pdf)."""
    if not suffix:
        return False
    stem = Path(name).stem
    pattern = re.escape(suffix) + r"(_\d+)?$"
    return re.search(pattern, stem) is not None


def number_folder(
    folder: str | Path,
    options: NumberOptions,
    recursive: bool = False,
    on_event=None,
) -> FolderSummary:
    """Numeruje wszystkie PDF-y w folderze. Błędy pojedynczych plików nie przerywają pracy.

    ``on_event`` jest wywoływane po każdym pliku z informacją o postępie:
    ``{"type": "start"|"ok"|"error", "name", "index", "total", ...}``.
    """
    root = read_folder(folder, recursive)
    if not is_writable_directory(root):
        raise BatchError(f"Brak prawa zapisu w folderze: {root}")

    files = find_pdfs(root, recursive, options.suffix)
    if not files:
        raise BatchError("W tym folderze nie ma plików PDF do ponumerowania.")
    if len(files) > MAX_FILES:
        raise BatchError(
            f"W folderze jest {len(files)} plików PDF, a limit to {MAX_FILES}. "
            "Podziel pracę na mniejsze foldery."
        )

    summary = FolderSummary(folder=root, found=len(files))
    total = len(files)
    for index, path in enumerate(files, start=1):
        if on_event is not None:
            on_event({"type": "start", "name": path.name, "index": index, "total": total})
        try:
            result = number_pdf(path, options)
        except Exception as exc:  # noqa: BLE001 - jeden plik nie może zatrzymać folderu
            message = str(exc) or exc.__class__.__name__
            summary.failed.append({"name": path.name, "error": message})
            if on_event is not None:
                on_event({
                    "type": "error", "name": path.name, "index": index,
                    "total": total, "error": message,
                })
            continue
        summary.done.append({"name": path.name, "output": result.output_path.name})
        if on_event is not None:
            on_event({
                "type": "ok", "name": path.name, "index": index, "total": total,
                "output": result.output_path.name, "pages": result.pages_numbered,
            })
    return summary
