"""Składanie dokumentów: wstawianie stron z innych PDF-ów i zastępowanie stron.

Każdy plik dodatkowy ma własną operację (wstaw po stronie N albo zastąp zakres stron).
Numery stron odnoszą się do **oryginalnego** dokumentu głównego - operacje są
wykonywane od końca dokumentu, więc wcześniejsze numery pozostają aktualne.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .core import NumberingResult, _open_pdf, _save_atomically, number_pdf
from .options import NumberOptions
from .paths import ensure_pdf_source, resolve_output

SPLICE_MODES = ("insert", "replace")
ASSEMBLED_SUFFIX = "_zlozony"


class AssembleError(RuntimeError):
    """Nie udało się złożyć dokumentu."""


@dataclass(frozen=True)
class SpliceOperation:
    """Jedna operacja: plik źródłowy i miejsce, w które trafia."""

    path: str | Path
    mode: str = "insert"
    after_page: int = 0  # insert: 0 = początek, N = po stronie N (numeracja oryginału)
    replace_from: int = 1  # replace: pierwsza zastępowana strona
    replace_to: int = 1  # replace: ostatnia zastępowana strona

    def __post_init__(self) -> None:
        if self.mode not in SPLICE_MODES:
            raise AssembleError(f"Nieznany tryb operacji: {self.mode!r}.")
        for name in ("after_page", "replace_from", "replace_to"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise AssembleError(f"{name} musi być liczbą całkowitą nieujemną.")
        if self.mode == "replace" and self.replace_to < self.replace_from:
            raise AssembleError("Koniec zakresu zastępowania jest przed początkiem.")

    @property
    def anchor(self) -> int:
        """Pozycja w dokumencie (0-based) używana do sortowania operacji."""
        return self.after_page if self.mode == "insert" else self.replace_from - 1


@dataclass
class SpliceResult:
    output_path: Path
    page_count_before: int
    page_count_after: int
    inserted_pages: int
    replaced_pages: int
    numbered: NumberingResult | None = None

    def describe(self) -> str:
        numbering = (
            f"numeracja {self.numbered.first_number}-{self.numbered.last_number}"
            if self.numbered is not None
            else "bez numeracji"
        )
        return (
            f"Zapisano {self.output_path.name}: {self.page_count_before} → "
            f"{self.page_count_after} stron, {numbering}."
        )


def _validate_operations(operations: list[SpliceOperation], total_pages: int) -> None:
    replacements: list[tuple[int, int]] = []
    for operation in operations:
        if operation.mode == "insert":
            if not 0 <= operation.after_page <= total_pages:
                raise AssembleError(
                    f"Nie można wstawić po stronie {operation.after_page} - "
                    f"dokument ma {total_pages} stron."
                )
        else:
            if not 1 <= operation.replace_from <= operation.replace_to <= total_pages:
                raise AssembleError(
                    f"Zakres {operation.replace_from}-{operation.replace_to} jest poza "
                    f"dokumentem (dokument ma {total_pages} stron)."
                )
            replacements.append((operation.replace_from, operation.replace_to))

    replacements.sort()
    for (start_a, end_a), (start_b, _end_b) in zip(replacements, replacements[1:]):
        if start_b <= end_a:
            raise AssembleError(
                "Zakresy zastępowania nakładają się - popraw strony w plikach dodatkowych."
            )

    for operation in operations:
        if operation.mode != "insert":
            continue
        for start, end in replacements:
            if start - 1 <= operation.after_page <= end - 1:
                raise AssembleError(
                    "Wstawka wypada w obrębie zastępowanego zakresu stron "
                    f"({start}-{end}) - zmień miejsce wstawienia."
                )


def splice_pdfs(
    main: str | Path,
    operations: list[SpliceOperation],
    options: NumberOptions | None = None,
    number: bool = True,
) -> SpliceResult:
    """Składa dokument według listy operacji, opcjonalnie numeruje wynik."""
    options = options or NumberOptions()
    if not operations:
        raise AssembleError("Dodaj co najmniej jeden plik PDF do wstawienia.")

    main_path = ensure_pdf_source(Path(main))
    prepared = [
        SpliceOperation(
            path=ensure_pdf_source(Path(operation.path)),
            mode=operation.mode,
            after_page=operation.after_page,
            replace_from=operation.replace_from,
            replace_to=operation.replace_to,
        )
        for operation in operations
    ]

    doc = _open_pdf(main_path)
    temp_path: Path | None = None
    try:
        before = doc.page_count
        _validate_operations(prepared, before)

        inserted = 0
        replaced = 0
        # Od końca dokumentu, żeby numery stron odnosiły się do oryginału.
        ordered = sorted(
            enumerate(prepared), key=lambda pair: (pair[1].anchor, pair[0]), reverse=True
        )
        for _, operation in ordered:
            source = _open_pdf(Path(operation.path))
            try:
                inserted += source.page_count
                if operation.mode == "insert":
                    doc.insert_pdf(source, start_at=operation.after_page)
                else:
                    start = operation.replace_from - 1
                    end = operation.replace_to - 1
                    replaced += end - start + 1
                    doc.delete_pages(start, end)
                    doc.insert_pdf(source, start_at=start)
            finally:
                source.close()

        page_after = doc.page_count

        if number:
            handle, name = tempfile.mkstemp(prefix="pdfnum-splice-", suffix=".pdf")
            os.close(handle)
            temp_path = Path(name)
            doc.save(str(temp_path))
            output_path = resolve_output(
                main_path, suffix=options.suffix, overwrite=options.overwrite
            )
            numbered = number_pdf(temp_path, options, destination=output_path)
            output = numbered.output_path
        else:
            output = resolve_output(
                main_path, suffix=ASSEMBLED_SUFFIX, overwrite=options.overwrite
            )
            _save_atomically(doc, output)
            numbered = None
    finally:
        doc.close()
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

    return SpliceResult(
        output_path=output,
        page_count_before=before,
        page_count_after=page_after,
        inserted_pages=inserted,
        replaced_pages=replaced,
        numbered=numbered,
    )
