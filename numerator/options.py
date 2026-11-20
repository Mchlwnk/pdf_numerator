"""Opcje numerowania stron - jedno miejsce z prawdą dla UI, CLI i rdzenia."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any

# Pozycje w siatce 3x3: (poziomo, pionowo)
POSITIONS = {
    "top-left": ("left", "top"),
    "top-center": ("center", "top"),
    "top-right": ("right", "top"),
    "middle-left": ("left", "middle"),
    "middle-center": ("center", "middle"),
    "middle-right": ("right", "middle"),
    "bottom-left": ("left", "bottom"),
    "bottom-center": ("center", "bottom"),
    "bottom-right": ("right", "bottom"),
}

DEFAULT_POSITION = "bottom-center"
DEFAULT_SUFFIX = "_numerowany"
MAX_FONT_SIZE = 72.0
MIN_FONT_SIZE = 4.0
NUMBER_STYLES = ("arabic", "roman", "ROMAN", "alpha", "ALPHA")


class OptionsError(ValueError):
    """Niepoprawne ustawienia numerowania."""


@dataclass(frozen=True)
class NumberOptions:
    """Ustawienia numerowania. Wszystkie wymiary w punktach typograficznych (1/72 cala)."""

    position: str = DEFAULT_POSITION
    margin: float = 28.0  # ~10 mm od krawędzi
    font_size: float = 11.0
    template: str = "{n}"
    skip_first: int = 0  # ile pierwszych stron zostawić bez numeru
    start_at: int = 1  # jaki numer dostać na pierwszej numerowanej stronie
    color: tuple[float, float, float] = (0.0, 0.0, 0.0)
    opacity: float = 1.0
    background: bool = False  # jasny prostokąt pod numerem (czytelność na grafikach)
    pages: str = ""  # zakresy stron, np. "1-10,15,20-"; puste = wszystkie
    style: str = "arabic"  # styl numeracji: arabic / roman / ROMAN / alpha / ALPHA
    appendix_from: int = 0  # od której strony (1-based) zaczyna się dodatek; 0 = brak
    appendix_style: str = "roman"  # styl numeracji dodatku
    mask_existing: bool = False  # zamaluj stary numer przed wstawieniem nowego
    mask_width: float = 40.0  # szerokość maski w punktach
    mask_height: float = 14.0  # wysokość maski w punktach
    suffix: str = DEFAULT_SUFFIX
    overwrite: bool = False

    def __post_init__(self) -> None:
        if self.position not in POSITIONS:
            raise OptionsError(
                f"Nieznana pozycja numeru: {self.position!r}. "
                f"Dozwolone: {', '.join(sorted(POSITIONS))}."
            )
        try:
            margin = float(self.margin)
            size = float(self.font_size)
            opacity = float(self.opacity)
        except (TypeError, ValueError) as exc:
            raise OptionsError("Margines, rozmiar i krycie muszą być liczbami.") from exc

        if not 0 <= margin <= 500:
            raise OptionsError("Margines musi mieścić się w zakresie 0-500 pt.")
        if not MIN_FONT_SIZE <= size <= MAX_FONT_SIZE:
            raise OptionsError(
                f"Rozmiar czcionki musi mieścić się w zakresie "
                f"{MIN_FONT_SIZE:g}-{MAX_FONT_SIZE:g} pt."
            )
        if not 0.0 < opacity <= 1.0:
            raise OptionsError("Krycie musi być w zakresie (0, 1].")

        for name in ("skip_first", "start_at"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise OptionsError(f"{name} musi być liczbą całkowitą.")
            if value < 0:
                raise OptionsError(f"{name} nie może być ujemne.")
        if self.start_at > 999_999:
            raise OptionsError("Numer początkowy jest zbyt duży.")

        if not isinstance(self.template, str) or not self.template.strip():
            raise OptionsError("Szablon numeru nie może być pusty.")
        if "{n" not in self.template:
            raise OptionsError("Szablon musi zawierać znacznik {n} (numer strony).")
        _validate_template(self.template)

        if not isinstance(self.color, (tuple, list)) or len(self.color) != 3:
            raise OptionsError("Kolor musi być trójką wartości RGB.")
        for channel in self.color:
            if not 0.0 <= float(channel) <= 1.0:
                raise OptionsError("Wartości koloru muszą mieścić się w zakresie 0-1.")

        if not isinstance(self.suffix, str):
            raise OptionsError("Końcówka nazwy pliku musi być tekstem.")

        if not isinstance(self.pages, str):
            raise OptionsError("Zakres stron musi być tekstem, np. \"1-10,15\".")
        if not isinstance(self.background, bool):
            raise OptionsError("Opcja tła musi być wartością logiczną.")
        parse_page_ranges(self.pages)  # walidacja składni

        if self.style not in NUMBER_STYLES:
            raise OptionsError(
                f"Nieznany styl numeracji: {self.style!r}. "
                f"Dozwolone: {', '.join(NUMBER_STYLES)}."
            )
        if self.appendix_style not in NUMBER_STYLES:
            raise OptionsError(
                f"Nieznany styl numeracji dodatku: {self.appendix_style!r}."
            )
        if not isinstance(self.appendix_from, int) or isinstance(self.appendix_from, bool):
            raise OptionsError("Początek dodatku musi być liczbą całkowitą.")
        if self.appendix_from < 0:
            raise OptionsError("Początek dodatku nie może być ujemny.")

        if not isinstance(self.mask_existing, bool):
            raise OptionsError("Opcja maskowania musi być wartością logiczną.")
        try:
            mask_width = float(self.mask_width)
            mask_height = float(self.mask_height)
        except (TypeError, ValueError) as exc:
            raise OptionsError("Wymiary maski muszą być liczbami.") from exc
        if not 2 <= mask_width <= 2000 or not 2 <= mask_height <= 2000:
            raise OptionsError("Wymiary maski muszą mieścić się w zakresie 2-2000 pt.")

    # -- wygodne konstruktory -------------------------------------------------

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None, **defaults: Any) -> "NumberOptions":
        """Buduje opcje z danych przysłanych przez UI/CLI, ignorując nieznane pola."""
        base = cls(**defaults)
        if not data:
            return base
        payload = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        if "color" in payload and isinstance(payload["color"], list):
            payload["color"] = tuple(payload["color"])
        return replace(base, **payload)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["color"] = list(self.color)
        return data


_ALLOWED_FIELDS = {"n", "total"}

MAX_PAGE_NUMBER = 100_000


def parse_page_ranges(spec: str) -> list[tuple[int, int | None]]:
    """Zamienia zapis typu "1-10,15,20-" na listę zakresów (koniec None = do końca)."""
    text = (spec or "").strip()
    if not text:
        return []

    ranges: list[tuple[int, int | None]] = []
    for raw_chunk in text.replace(";", ",").split(","):
        chunk = raw_chunk.strip().replace(" ", "")
        if not chunk:
            continue
        start_text, separator, end_text = chunk.partition("-")
        if not start_text.isdigit():
            raise OptionsError(
                f"Niepoprawny zakres stron: {raw_chunk.strip()!r}. "
                "Użyj zapisu np. 1-10,15,20-."
            )
        start = int(start_text)
        end: int | None = start
        if separator:
            if not end_text:
                end = None
            elif end_text.isdigit():
                end = int(end_text)
            else:
                raise OptionsError(f"Niepoprawny koniec zakresu: {raw_chunk.strip()!r}.")
        if start < 1 or (end is not None and end < start):
            raise OptionsError(f"Zakres stron jest odwrócony lub zaczyna się od zera: {chunk!r}.")
        if start > MAX_PAGE_NUMBER or (end or 0) > MAX_PAGE_NUMBER:
            raise OptionsError("Numer strony w zakresie jest zbyt duży.")
        ranges.append((start, end))
    return ranges


def page_indices(page_count: int, skip_first: int = 0, pages: str = "") -> list[int]:
    """Lista indeksów stron (0-based) do ponumerowania.

    ``skip_first`` odcina początek dokumentu, ``pages`` dodatkowo filtruje strony
    numerami fizycznymi (1-based). Obie reguły muszą być spełnione.
    """
    indices = [index for index in range(page_count) if index >= skip_first]
    ranges = parse_page_ranges(pages)
    if not ranges:
        return indices

    selected: set[int] = set()
    for start, end in ranges:
        stop = page_count if end is None else min(end, page_count)
        selected.update(range(start, stop + 1))
    return [index for index in indices if (index + 1) in selected]


def _validate_template(template: str) -> None:
    """Sprawdza, czy szablon da się sformatować i nie zawiera nieznanych znaczników."""
    try:
        template.format_map({"n": 1, "total": 1})
    except KeyError as exc:
        raise OptionsError(
            f"Nieznany znacznik {exc.args[0]!r} w szablonie. "
            "Dostępne: {n} - numer strony, {total} - liczba stron."
        ) from exc
    except (ValueError, IndexError) as exc:
        raise OptionsError(f"Niepoprawny szablon numeru: {exc}") from exc


def parse_hex_color(value: str) -> tuple[float, float, float]:
    """Zamienia '#rrggbb' (lub '#rgb') na trójkę 0-1."""
    text = (value or "").strip().lstrip("#")
    if len(text) == 3:
        text = "".join(channel * 2 for channel in text)
    if len(text) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in text):
        raise OptionsError(f"Niepoprawny kolor: {value!r}. Użyj zapisu #rrggbb.")
    return tuple(int(text[index:index + 2], 16) / 255 for index in (0, 2, 4))  # type: ignore[return-value]


def format_label(template: str, number: int, total: int, style: str = "arabic") -> str:
    """Zwraca gotowy tekst numeru dla danej strony, w wybranym stylu cyfr."""
    return template.format_map(
        {"n": format_number(number, style), "total": format_number(total, style)}
    )


_ROMAN_PAIRS = (
    (1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"),
    (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i"),
)


def to_roman(number: int) -> str:
    """Liczba arabska -> małe cyfry rzymskie (1 -> i, 1994 -> mcmxciv)."""
    if number <= 0:
        return str(number)
    parts: list[str] = []
    remaining = number
    for value, glyph in _ROMAN_PAIRS:
        while remaining >= value:
            parts.append(glyph)
            remaining -= value
    return "".join(parts)


def to_alpha(number: int) -> str:
    """Liczba -> litery jak w arkuszach: 1 -> a, 26 -> z, 27 -> aa."""
    if number <= 0:
        return str(number)
    letters = ""
    value = number
    while value > 0:
        value, remainder = divmod(value - 1, 26)
        letters = chr(ord("a") + remainder) + letters
    return letters


def format_number(number: int, style: str = "arabic") -> str:
    """Formatuje numer strony zgodnie ze stylem (arabskie, rzymskie, litery)."""
    if style == "roman":
        return to_roman(number)
    if style == "ROMAN":
        return to_roman(number).upper()
    if style == "alpha":
        return to_alpha(number)
    if style == "ALPHA":
        return to_alpha(number).upper()
    return str(number)
