"""Składanie dokumentów: wstawianie stron z innych PDF-ów i zastępowanie stron."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .core import NumberingResult, _open_pdf, number_pdf
from .options import NumberOptions
from .paths import ensure_pdf_source, resolve_output

SPLICE_MODES = ("insert", "replace")


class AssembleError(RuntimeError):
    """Nie udało się złożyć dokumentu."""


@dataclass(frozen=True)
class SpliceOptions:
    """Gdzie i jak wstawić strony.

    ``insert``  - wstawia pliki po stronie ``after_page`` (0 = na początku).
    ``replace`` - usuwa strony ``replace_from``-``replace_to`` i wstawia w to miejsce pliki.
    Wszystkie numery stron są 1-based, jak w interfejsie.
    """

    mode: str = "insert"
    after_page: int = 0
    replace_from: int = 1
    replace_to: int = 1

    def __post_init__(self) -> None:
        if self.mode not in SPLICE_MODES:
            raise AssembleError(f"Nieznany tryb: {self.mode!r}.")
        for name in ("after_page", "replace_from", "replace_to"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise AssembleError(f"{name} musi być liczbą całkowitą nieujemną.")
        if self.mode == "replace" and self.replace_to < self.replace_from:
            raise AssembleError("Koniec zakresu zastępowania jest przed początkiem.")


@dataclass
class SpliceResult:
    output_path: Path
    page_count_before: int
    page_count_after: int
    inserted_pages: int
    replaced_pages: int
    numbered: NumberingResult

    def describe(self) -> str:
        return (
            f"Zapisano {self.output_path.name}: {self.page_count_before} → "
            f"{self.page_count_after} stron, numeracja {self.numbered.first_number}-"
            f"{self.numbered.last_number}."
        )


def splice_pdfs(
    main: str | Path,
    inserts: list[str | Path],
    options: NumberOptions | None = None,
    spec: SpliceOptions | None = None,
) -> SpliceResult:
    """Składa dokument (wstawia/zastępuje strony), a następnie numeruje wynik."""
    options = options or NumberOptions()
    spec = spec or SpliceOptions()
    main_path = ensure_pdf_source(Path(main))
    insert_paths = [ensure_pdf_source(Path(path)) for path in inserts]
    if not insert_paths:
        raise AssembleError("Dodaj co najmniej jeden plik PDF do wstawienia.")

    doc = _open_pdf(main_path)
    temp_path: Path | None = None
    try:
        before = doc.page_count
        inserted = 0
        replaced = 0

        if spec.mode == "insert":
            # after_page=0 -> na początku; after_page=N -> po stronie N
            if not 0 <= spec.after_page <= before:
                raise AssembleError(
                    f"Nie można wstawić po stronie {spec.after_page} - dokument ma {before} stron."
                )
            position = spec.after_page
            for path in insert_paths:
                source = _open_pdf(path)
                try:
                    inserted += source.page_count
                    doc.insert_pdf(source, start_at=position)
                    position += source.page_count
                finally:
                    source.close()
        else:
            start = spec.replace_from - 1
            end = spec.replace_to - 1
            if not 0 <= start <= end < before:
                raise AssembleError(
                    f"Zakres stron {spec.replace_from}-{spec.replace_to} jest poza dokumentem "
                    f"(dokument ma {before} stron)."
                )
            replaced = end - start + 1
            doc.delete_pages(start, end)
            position = start
            for path in insert_paths:
                source = _open_pdf(path)
                try:
                    inserted += source.page_count
                    doc.insert_pdf(source, start_at=position)
                    position += source.page_count
                finally:
                    source.close()

        page_after = doc.page_count
        handle, name = tempfile.mkstemp(prefix="pdfnum-splice-", suffix=".pdf")
        os.close(handle)
        temp_path = Path(name)
        doc.save(str(temp_path))
    finally:
        doc.close()

    try:
        output_path = resolve_output(
            main_path, suffix=options.suffix, overwrite=options.overwrite
        )
        numbered = number_pdf(temp_path, options, destination=output_path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

    return SpliceResult(
        output_path=numbered.output_path,
        page_count_before=before,
        page_count_after=page_after,
        inserted_pages=inserted,
        replaced_pages=replaced,
        numbered=numbered,
    )
