"""Wybór czcionki do numeracji.

Domyślnie używamy wbudowanej czcionki PDF (Helvetica, kodowanie WinAnsi) - nie wymaga
osadzania, więc pliki wynikowe rosną o kilka kilobajtów i **oryginalne czcionki dokumentu
pozostają nietknięte**. Czcionkę Unicode (DejaVu Sans) osadzamy tylko wtedy, gdy tekst
numeru zawiera znaki spoza WinAnsi (np. polskie diakrytyki w szablonie).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pymupdf

BUNDLED_FONT_NAME = "DejaVuSans.ttf"

# Kolejność awaryjna: fonty systemowe Windows z pełnym zestawem polskich znaków.
SYSTEM_FONTS = ("segoeui.ttf", "arial.ttf", "tahoma.ttf", "calibri.ttf")

ASCII_FONT_NAME = "helv"
UNICODE_FONT_NAME = "PDFNumerator"

_POLISH_MAP = str.maketrans(
    {
        "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n", "ó": "o", "ś": "s",
        "ź": "z", "ż": "z",
        "Ą": "A", "Ć": "C", "Ę": "E", "Ł": "L", "Ń": "N", "Ó": "O", "Ś": "S",
        "Ź": "Z", "Ż": "Z",
    }
)


def app_resource_dir() -> Path:
    """Katalog zasobów, także po spakowaniu PyInstallerem (--onefile)."""
    frozen_dir = getattr(sys, "_MEIPASS", None)
    if frozen_dir:
        return Path(frozen_dir) / "numerator"
    return Path(__file__).resolve().parent


def _system_font_dir() -> Path | None:
    candidate = Path("C:/Windows/Fonts")
    return candidate if candidate.is_dir() else None


def font_candidates() -> list[Path]:
    candidates: list[Path] = []
    bundled = app_resource_dir() / "fonts" / BUNDLED_FONT_NAME
    if bundled.is_file():
        candidates.append(bundled)
    system_dir = _system_font_dir()
    if system_dir:
        for name in SYSTEM_FONTS:
            path = system_dir / name
            if path.is_file():
                candidates.append(path)
    return candidates


def to_ascii(text: str) -> str:
    """Usuwa polskie znaki - dla bazowej czcionki PDF bez pełnego zestawu glifów."""
    converted = text.translate(_POLISH_MAP)
    return "".join(ch for ch in converted if 32 <= ord(ch) < 127)


def fits_winansi(text: str) -> bool:
    """Czy tekst da się zapisać kodowaniem WinAnsi (czcionki bazowe PDF)?"""
    try:
        text.encode("cp1252")
    except UnicodeEncodeError:
        return False
    return True


@dataclass
class TextRenderer:
    """Rysuje tekst numeru, wybierając czcionkę odpowiednio do treści."""

    font_size: float
    color: tuple[float, float, float] = (0.0, 0.0, 0.0)
    opacity: float = 1.0

    def __post_init__(self) -> None:
        self._ascii_font = pymupdf.Font(ASCII_FONT_NAME)
        self._unicode_font: pymupdf.Font | None = None
        self._unicode_path: Path | None = None
        self._unicode_checked = False
        self.used_fallback = False  # True, gdy potrzebne były diakrytyki, a brak fontu

    # -- wybór czcionki -------------------------------------------------------

    def _load_unicode_font(self) -> bool:
        if self._unicode_checked:
            return self._unicode_font is not None
        self._unicode_checked = True
        for path in font_candidates():
            try:
                font = pymupdf.Font(fontfile=str(path))
                # Test osadzenia na tymczasowej stronie - odrzuca fonty z zakazem osadzania.
                probe = pymupdf.open()
                page = probe.new_page()
                page.insert_text((10, 10), "Zażółć", fontname="Probe", fontfile=str(path))
                probe.close()
            except Exception:
                continue
            self._unicode_font = font
            self._unicode_path = path
            return True
        return False

    def _prepare(self, text: str) -> tuple[str, pymupdf.Font, str, Path | None]:
        """Dobiera czcionkę do tekstu: bazowa dla ASCII/WinAnsi, DejaVu dla reszty."""
        if fits_winansi(text):
            return text, self._ascii_font, ASCII_FONT_NAME, None
        if self._load_unicode_font():
            assert self._unicode_font is not None
            return text, self._unicode_font, UNICODE_FONT_NAME, self._unicode_path
        self.used_fallback = True
        return to_ascii(text), self._ascii_font, ASCII_FONT_NAME, None

    # -- miary ---------------------------------------------------------------

    @property
    def supports_unicode(self) -> bool:
        return self._load_unicode_font()

    def metrics(self, text: str) -> tuple[float, float]:
        """(wznios, głębokość) w jednostkach em dla czcionki wybranej dla tekstu."""
        _, font, _, _ = self._prepare(text)
        return font.ascender, max(0.0, -font.descender)

    def measure(self, text: str) -> float:
        prepared, font, _, _ = self._prepare(text)
        return font.text_length(prepared, fontsize=self.font_size)

    def draw(self, page: pymupdf.Page, point: pymupdf.Point, text: str) -> None:
        prepared, _, font_name, font_path = self._prepare(text)
        kwargs = {
            "fontsize": self.font_size,
            "rotate": page.rotation,
            "fill": self.color,
            "fill_opacity": self.opacity,
            "fontname": font_name,
        }
        if font_path is not None:
            kwargs["fontfile"] = str(font_path)
        page.insert_text(point, prepared, **kwargs)
