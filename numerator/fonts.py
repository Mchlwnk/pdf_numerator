"""Wybór czcionki do numeracji: pakowana DejaVu Sans, awaryjnie font systemowy lub helv."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pymupdf

BUNDLED_FONT_NAME = "DejaVuSans.ttf"

# Kolejność awaryjna: fonty systemowe Windows z pełną obsługą polskich znaków.
SYSTEM_FONTS = ("segoeui.ttf", "arial.ttf", "tahoma.ttf", "calibri.ttf")

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
    """Usuwa polskie znaki - dla bazowego fontu PDF bez pełnego zestawu glifów."""
    converted = text.translate(_POLISH_MAP)
    return "".join(ch for ch in converted if 32 <= ord(ch) < 127)


@dataclass
class TextRenderer:
    """Rysuje tekst numeru, radząc sobie z brakiem czcionki Unicode."""

    font_size: float
    color: tuple[float, float, float] = (0.0, 0.0, 0.0)
    opacity: float = 1.0

    def __post_init__(self) -> None:
        self._candidates = font_candidates()
        self._font_file: Path | None = None
        self._font_name = "helv"
        self._font = pymupdf.Font("helv")
        self.used_fallback = False
        self._select()

    def _select(self) -> None:
        for path in self._candidates:
            try:
                font = pymupdf.Font(fontfile=str(path))
                # Test osadzenia na tymczasowej stronie - odrzuca fonty z zakazem osadzania.
                probe = pymupdf.open()
                page = probe.new_page()
                page.insert_text((10, 10), "Test 0/0", fontname="Probe", fontfile=str(path))
                probe.close()
            except Exception:
                continue
            self._font_file = path
            self._font_name = "PDFNumerator"
            self._font = font
            return
        # Ostatnia deska ratunku: bazowy Helvetica (tylko ASCII).
        self.used_fallback = True

    @property
    def supports_unicode(self) -> bool:
        return not self.used_fallback

    @property
    def ascender(self) -> float:
        return self._font.ascender

    @property
    def descender(self) -> float:
        """Wysokość części znaków poniżej linii bazowej (wartość dodatnia)."""
        return max(0.0, -self._font.descender)

    def measure(self, text: str) -> float:
        return self._font.text_length(self._sanitize(text, measure=True), fontsize=self.font_size)

    def _sanitize(self, text: str, *, measure: bool = False) -> str:
        if self.supports_unicode:
            return text
        return to_ascii(text)

    def draw(self, page: pymupdf.Page, point: pymupdf.Point, text: str) -> None:
        kwargs = {
            "fontsize": self.font_size,
            "rotate": page.rotation,
            "fill": self.color,
            "fill_opacity": self.opacity,
            "fontname": self._font_name,
        }
        if self._font_file is not None:
            kwargs["fontfile"] = str(self._font_file)
        page.insert_text(point, self._sanitize(text), **kwargs)
