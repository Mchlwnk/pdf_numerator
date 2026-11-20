"""Publiczne API pakietu numerator."""

from .core import (
    LabelPlan,
    NumberingError,
    NumberingResult,
    PdfInfo,
    PreviewImage,
    build_plan,
    inspect_pdf,
    number_pdf,
    render_preview,
)
from .options import (
    NUMBER_STYLES,
    POSITIONS,
    NumberOptions,
    OptionsError,
    format_label,
    format_number,
    page_indices,
    parse_hex_color,
    parse_page_ranges,
    to_alpha,
    to_roman,
)
from .paths import PathError, resolve_output

__all__ = [
    "LabelPlan",
    "NUMBER_STYLES",
    "POSITIONS",
    "NumberOptions",
    "NumberingError",
    "NumberingResult",
    "OptionsError",
    "PathError",
    "PdfInfo",
    "PreviewImage",
    "build_plan",
    "format_label",
    "format_number",
    "inspect_pdf",
    "number_pdf",
    "page_indices",
    "parse_hex_color",
    "parse_page_ranges",
    "render_preview",
    "resolve_output",
    "to_alpha",
    "to_roman",
]

__version__ = "0.3.0"
