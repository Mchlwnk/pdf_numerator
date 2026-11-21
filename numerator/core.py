"""Rdzeń: nakładanie numerów stron na kopię dokumentu PDF."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from .fonts import TextRenderer
from .options import POSITIONS, NumberOptions, format_label, page_indices
from .paths import PathError, ensure_pdf_source, is_writable_directory, resolve_output

PDF_MAGIC = b"%PDF-"


class NumberingError(RuntimeError):
    """Nie udało się ponumerować dokumentu."""


@dataclass
class NumberingResult:
    output_path: Path
    page_count: int
    pages_numbered: int
    first_number: int
    last_number: int
    font_fallback: bool = False
    font_shrunk: bool = False
    appendix_pages: int = 0

    def describe(self) -> str:
        pages = f"{self.pages_numbered} z {self.page_count} stron"
        extra = f", w tym dodatek: {self.appendix_pages}" if self.appendix_pages else ""
        return (
            f"Zapisano {self.output_path.name} "
            f"({pages}, numery {self.first_number}-{self.last_number}{extra})."
        )


@dataclass
class PdfInfo:
    path: Path
    page_count: int
    size_bytes: int
    encrypted: bool
    title: str | None
    needs_password: bool


@dataclass
class PreviewImage:
    data: bytes
    page_index: int  # 0-based
    page_number: int  # 1-based
    page_count: int
    numbered_pages: int
    is_numbered: bool
    label: str | None = None  # dokładny tekst numeru na tej stronie


@dataclass
class LabelPlan:
    """Gotowe etykiety numerów dla poszczególnych stron (indeks 0-based -> tekst)."""

    labels: dict[int, str]
    main_count: int
    appendix_count: int
    first_number: int
    last_number: int

    @property
    def total(self) -> int:
        return len(self.labels)


def build_plan(total_pages: int, options: NumberOptions) -> LabelPlan:
    """Wylicza, które strony dostaną numer i jaki dokładnie tekst.

    Strony przed ``appendix_from`` numerowane są od ``start_at`` stylem ``style``,
    strony od ``appendix_from`` - od nowa, stylem ``appendix_style``.
    """
    indices = page_indices(total_pages, options.skip_first, options.pages)
    if not indices:
        raise NumberingError(
            "Wybrane zakresy stron nie obejmują żadnej strony tego dokumentu."
        )

    appendix_start = options.appendix_from - 1 if options.appendix_from > 0 else None
    if appendix_start is None:
        main_pages, appendix_pages = indices, []
    else:
        main_pages = [index for index in indices if index < appendix_start]
        appendix_pages = [index for index in indices if index >= appendix_start]

    labels: dict[int, str] = {}
    main_total = options.start_at + len(main_pages) - 1
    for ordinal, page_index in enumerate(main_pages):
        labels[page_index] = format_label(
            options.template, options.start_at + ordinal, main_total, options.style
        )
    for ordinal, page_index in enumerate(appendix_pages):
        labels[page_index] = format_label(
            options.template, 1 + ordinal, len(appendix_pages), options.appendix_style
        )

    if not labels:
        raise NumberingError("Nie ma strony, którą można ponumerować.")

    return LabelPlan(
        labels=labels,
        main_count=len(main_pages),
        appendix_count=len(appendix_pages),
        first_number=options.start_at if main_pages else 1,
        last_number=main_total if main_pages else len(appendix_pages),
    )


def _open_pdf(path: Path) -> pymupdf.Document:
    try:
        doc = pymupdf.open(path)
    except Exception as exc:  # pymupdf rzuca różne typy przy uszkodzonych plikach
        raise NumberingError(f"Nie mogę otworzyć pliku PDF: {exc}") from exc
    if doc.needs_pass:
        if not doc.authenticate(""):
            doc.close()
            raise NumberingError(
                "Ten PDF jest zabezpieczony hasłem. Usuń zabezpieczenie i spróbuj ponownie."
            )
    if doc.page_count == 0:
        doc.close()
        raise NumberingError("Dokument nie zawiera żadnych stron.")
    return doc


def inspect_pdf(path: str | Path) -> PdfInfo:
    source = ensure_pdf_source(Path(path))
    doc = pymupdf.open(source)
    try:
        metadata = doc.metadata or {}
        return PdfInfo(
            path=source,
            page_count=doc.page_count,
            size_bytes=source.stat().st_size,
            encrypted=bool(doc.is_encrypted),
            title=(metadata.get("title") or None),
            needs_password=bool(doc.needs_pass),
        )
    finally:
        doc.close()


def number_pdf(
    source: str | Path,
    options: NumberOptions | None = None,
    destination: str | Path | None = None,
) -> NumberingResult:
    """Tworzy nowy plik PDF z numerami stron. Oryginał pozostaje nietknięty."""
    options = options or NumberOptions()
    source_path = ensure_pdf_source(Path(source))

    doc = _open_pdf(source_path)
    try:
        total_pages = doc.page_count
        if options.skip_first >= total_pages:
            raise NumberingError(
                f"Pominięto {options.skip_first} stron, a dokument ma ich tylko {total_pages}. "
                "Nie ma czego numerować."
            )

        indices = page_indices(total_pages, options.skip_first, options.pages)
        if not indices:
            raise NumberingError(
                "Wybrane zakresy stron nie obejmują żadnej strony tego dokumentu."
            )

        plan = build_plan(total_pages, options)

        output_path = resolve_output(
            source_path,
            suffix=options.suffix,
            destination=Path(destination) if destination else None,
            overwrite=options.overwrite,
        )
        if not is_writable_directory(output_path.parent):
            raise PathError(
                f"Brak prawa zapisu w katalogu docelowym: {output_path.parent}"
            )

        renderer = TextRenderer(
            font_size=options.font_size,
            color=tuple(options.color),
            opacity=options.opacity,
        )
        font_shrunk = False

        for page_index, label in plan.labels.items():
            shrunk = _draw_number(doc[page_index], label, options, renderer, page_index + 1)
            font_shrunk = font_shrunk or shrunk

        _save_atomically(doc, output_path)

        return NumberingResult(
            output_path=output_path,
            page_count=total_pages,
            pages_numbered=plan.total,
            first_number=plan.first_number,
            last_number=plan.last_number,
            font_fallback=renderer.used_fallback,
            font_shrunk=font_shrunk,
            appendix_pages=plan.appendix_count,
        )
    finally:
        doc.close()


def render_preview(
    source: str | Path,
    options: NumberOptions | None = None,
    page_number: int | None = None,
    max_width: int = 760,
    max_height: int = 1000,
) -> PreviewImage:
    """Renderuje pojedynczą stronę z naniesionym numerem (bez zapisu na dysk)."""
    options = options or NumberOptions()
    source_path = ensure_pdf_source(Path(source))
    doc = _open_pdf(source_path)
    try:
        total_pages = doc.page_count
        plan = build_plan(total_pages, options)
        numbered_indices = list(plan.labels)

        if page_number is None:
            target = numbered_indices[0]
        else:
            target = int(page_number) - 1
            if not 0 <= target < total_pages:
                raise NumberingError(
                    f"Strona {page_number} nie istnieje (dokument ma {total_pages} stron)."
                )

        label = plan.labels.get(target)
        if label is not None:
            renderer = TextRenderer(
                font_size=options.font_size,
                color=tuple(options.color),
                opacity=options.opacity,
            )
            _draw_number(doc[target], label, options, renderer, target + 1)

        page = doc[target]
        zoom = min(
            max_width / max(page.rect.width, 1.0),
            max_height / max(page.rect.height, 1.0),
            2.0,
        )
        zoom = max(zoom, 0.2)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        return PreviewImage(
            data=pix.tobytes("png"),
            page_index=target,
            page_number=target + 1,
            page_count=total_pages,
            numbered_pages=plan.total,
            is_numbered=label is not None,
            label=label,
        )
    finally:
        doc.close()


def render_label_sample(
    source: str | Path,
    options: NumberOptions | None = None,
    page_number: int | None = None,
    zoom: float = 3.0,
    max_width: float = 720.0,
) -> PreviewImage:
    """Renderuje sam napis numeru (bez strony) - podgląd wyglądu czcionki i koloru."""
    options = options or NumberOptions()
    source_path = ensure_pdf_source(Path(source))
    doc = _open_pdf(source_path)
    try:
        total_pages = doc.page_count
        plan = build_plan(total_pages, options)
        if page_number is None:
            target = min(plan.labels)
        else:
            target = int(page_number) - 1
            if not 0 <= target < total_pages:
                raise NumberingError(
                    f"Strona {page_number} nie istnieje (dokument ma {total_pages} stron)."
                )
        label = plan.labels.get(target)
        if label is None:
            raise NumberingError("Ta strona nie będzie numerowana.")
    finally:
        doc.close()

    renderer = TextRenderer(
        font_size=options.font_size,
        color=tuple(options.color),
        opacity=options.opacity,
    )
    ascent_em, descent_em = renderer.metrics(label)
    text_width = max(renderer.measure(label), 1.0)
    text_height = max((ascent_em + descent_em) * options.font_size, 1.0)
    pad = max(4.0, options.font_size * 0.45)

    sample = pymupdf.open()
    try:
        page = sample.new_page(width=text_width + 2 * pad, height=text_height + 2 * pad)
        # Jasne tło dla ciemnych numerów, ciemniejsze dla jasnych - żeby napis było widać.
        red, green, blue = (float(channel) for channel in options.color)
        luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
        background = (0.42, 0.45, 0.52) if luminance > 0.75 else (0.97, 0.975, 0.985)
        page.draw_rect(page.rect, color=None, fill=background, width=0)

        baseline = pad + ascent_em * options.font_size
        renderer.draw(page, pymupdf.Point(pad, baseline), label)

        scale = min(zoom, max_width / max(page.rect.width, 1.0))
        scale = max(scale, 0.5)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
        data = pix.tobytes("png")
    finally:
        sample.close()

    return PreviewImage(
        data=data,
        page_index=target,
        page_number=target + 1,
        page_count=total_pages,
        numbered_pages=plan.total,
        is_numbered=True,
        label=label,
    )


def _draw_number(
    page: pymupdf.Page,
    label: str,
    options: NumberOptions,
    renderer: TextRenderer,
    page_number: int = 1,
) -> bool:
    """Rysuje numer na stronie. Zwraca True, jeśli trzeba było zmniejszyć czcionkę."""
    visible = page.rect
    margin = options.margin
    shrank = False
    original_size = renderer.font_size

    width = renderer.measure(label)
    available = visible.width - 2 * margin
    if width > available > 0:
        renderer.font_size = max(original_size * (available / width), 4.0)
        width = renderer.measure(label)
        shrank = True

    horizontal, vertical = POSITIONS[options.position]
    if options.mirror and page_number % 2 == 0:
        # Strony parzyste dostają numer po przeciwnej stronie (lewa <-> prawa).
        horizontal = {"left": "right", "right": "left", "center": "center"}[horizontal]
    if horizontal == "left":
        x = margin
    elif horizontal == "right":
        x = visible.width - margin - width
    else:
        x = (visible.width - width) / 2

    ascent_em, descent_em = renderer.metrics(label)
    ascent = ascent_em * renderer.font_size
    if vertical == "top":
        y = margin + ascent
    elif vertical == "bottom":
        y = visible.height - margin
    else:
        y = visible.height / 2 + ascent / 2.5

    x = min(max(x, 0.0), max(visible.width - width, 0.0))
    y = min(max(y, ascent * 0.9), visible.height)

    if options.mask_existing:
        mask_width = min(options.mask_width, visible.width)
        mask_height = min(options.mask_height, visible.height)
        if horizontal == "left":
            mask_x = margin
        elif horizontal == "right":
            mask_x = visible.width - margin - mask_width
        else:
            mask_x = (visible.width - mask_width) / 2
        if vertical == "top":
            mask_y = margin
        elif vertical == "bottom":
            mask_y = visible.height - margin - mask_height
        else:
            mask_y = (visible.height - mask_height) / 2
        mask_rect = pymupdf.Rect(
            mask_x, mask_y, mask_x + mask_width, mask_y + mask_height
        ) * page.derotation_matrix
        page.draw_rect(mask_rect, color=None, fill=(1.0, 1.0, 1.0), width=0, overlay=True)

    if options.background:
        pad = max(1.5, renderer.font_size * 0.18)
        box = pymupdf.Rect(
            x - pad,
            y - ascent - pad,
            x + width + pad,
            y + descent_em * renderer.font_size + pad,
        ) * page.derotation_matrix
        page.draw_rect(box, color=None, fill=(1.0, 1.0, 1.0), width=0, overlay=True)

    point = pymupdf.Point(x, y) * page.derotation_matrix
    renderer.draw(page, point, label)
    renderer.font_size = original_size
    return shrank


def _save_atomically(doc: pymupdf.Document, output_path: Path) -> None:
    """Zapisuje do pliku tymczasowego i podmienia, żeby nie zostawić uszkodzonej kopii."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(
        prefix=output_path.stem + ".", suffix=".part", dir=str(output_path.parent)
    )
    os.close(handle)
    temp_path = Path(temp_name)
    try:
        # Celowo bez doc.subset_fonts(): przycinanie czcionek potrafi uszkodzić
        # oryginalne fonty dokumentu (tekst zamienia się w puste prostokąty).
        # Nasze numery korzystają z czcionki bazowej, więc nie ma czego przycinać.
        doc.save(str(temp_path), garbage=3, deflate=True)
        _verify_pdf(temp_path, doc.page_count)
        os.replace(temp_path, output_path)
    except Exception as exc:
        temp_path.unlink(missing_ok=True)
        if isinstance(exc, NumberingError):
            raise
        raise NumberingError(f"Nie udało się zapisać pliku: {exc}") from exc


def _verify_pdf(path: Path, expected_pages: int) -> None:
    with path.open("rb") as handle:
        if handle.read(5) != PDF_MAGIC:
            raise NumberingError("Zapisany plik nie jest poprawnym PDF-em.")
    with pymupdf.open(path) as check:
        if check.page_count != expected_pages:
            raise NumberingError(
                f"Zapisany plik ma {check.page_count} stron zamiast {expected_pages}."
            )
