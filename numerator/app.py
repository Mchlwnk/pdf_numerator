"""Punkt startowy PDF Numerator.

Domyślnie uruchamia lokalny serwer i otwiera interfejs w przeglądarce.
Pliki podane w argumentach (np. przeciągnięte na ikonę programu) są numerowane
od razu, bez otwierania okna.
"""

from __future__ import annotations

import argparse
import logging
import sys
import threading
import time
import webbrowser

from . import __version__
from .batch import BatchError, number_folder
from .core import NumberingError, number_pdf
from .dialogs import DialogHost
from .logsetup import setup_logging
from .options import NumberOptions, OptionsError, parse_hex_color
from .paths import PathError
from .server import LocalApp

log = logging.getLogger("numerator.launcher")

IDLE_CHECK_SECONDS = 30


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="PDF Numerator",
        description="Numeruje strony w plikach PDF, zapisując kopię obok oryginału.",
    )
    parser.add_argument("files", nargs="*", help="pliki PDF do ponumerowania (tryb wsadowy)")
    parser.add_argument("--folder", default="", help="ponumeruj wszystkie PDF-y w podanym folderze")
    parser.add_argument("--recursive", action="store_true", help="z folderu również podfoldery")
    parser.add_argument("--cli", action="store_true", help="wymuś tryb wsadowy")
    parser.add_argument("--port", type=int, default=8765, help="port lokalnego serwera")
    parser.add_argument("--no-browser", action="store_true", help="nie otwieraj przeglądarki")
    parser.add_argument("--no-tk", action="store_true", help="bez natywnych okien systemowych")
    parser.add_argument(
        "--quiet", action="store_true",
        help="tryb wsadowy bez okien i podsumowania (tylko kod wyjścia)",
    )
    parser.add_argument("--token", default=None, help=argparse.SUPPRESS)
    parser.add_argument(
        "--idle-exit", type=int, default=180,
        help="zamknij serwer po tylu minutach bezczynności (0 = nigdy)",
    )

    group = parser.add_argument_group("numeracja")
    group.add_argument("--position", default="bottom-center", help="pozycja numeru, np. bottom-center")
    group.add_argument("--margin", type=float, default=10.0, help="margines w milimetrach")
    group.add_argument("--font-size", type=float, default=11.0, help="rozmiar czcionki w punktach")
    group.add_argument("--template", default="{n}", help="format numeru, np. '{n} / {total}'")
    group.add_argument("--skip", type=int, default=0, help="pomiń tyle pierwszych stron")
    group.add_argument("--pages", default="", help="zakresy stron, np. '1-10,15,20-'")
    group.add_argument("--start", type=int, default=1, help="pierwszy numer")
    group.add_argument("--style", default="arabic",
                       help="styl numeracji: arabic, roman, ROMAN, alpha, ALPHA")
    group.add_argument("--appendix-from", type=int, default=0,
                       help="od której strony numerować dodatek od nowa (0 = brak)")
    group.add_argument("--appendix-style", default="roman",
                       help="styl numeracji dodatku (domyślnie roman)")
    group.add_argument("--mask", action="store_true", help="zamaluj istniejący numer")
    group.add_argument("--mask-width", type=float, default=14.0, help="szerokość maski w mm")
    group.add_argument("--mask-height", type=float, default=5.0, help="wysokość maski w mm")
    group.add_argument("--color", default="#000000", help="kolor numeru, np. '#c0392b'")
    group.add_argument("--opacity", type=float, default=1.0, help="krycie numeru (0.15-1)")
    group.add_argument("--background", action="store_true", help="biały prostokąt pod numerem")
    group.add_argument("--suffix", default="_numerowany", help="końcówka nazwy pliku wynikowego")
    group.add_argument("--overwrite", action="store_true", help="nadpisz istniejący plik wynikowy")
    return parser


def options_from_args(args: argparse.Namespace) -> NumberOptions:
    return NumberOptions(
        position=args.position,
        margin=args.margin * 72 / 25.4,
        font_size=args.font_size,
        template=args.template,
        skip_first=args.skip,
        pages=args.pages,
        start_at=args.start,
        style=args.style,
        appendix_from=args.appendix_from,
        appendix_style=args.appendix_style,
        mask_existing=args.mask,
        mask_width=args.mask_width * 72 / 25.4,
        mask_height=args.mask_height * 72 / 25.4,
        color=parse_hex_color(args.color),
        opacity=args.opacity,
        background=args.background,
        suffix=args.suffix,
        overwrite=args.overwrite,
    )


def is_windowed() -> bool:
    """Program spakowany bez konsoli (--noconsole) nie ma sys.stdout."""
    return sys.stdout is None


def run_batch(files: list[str], options: NumberOptions, dialogs: DialogHost | None,
              quiet: bool = False) -> int:
    """Numeruje wszystkie podane pliki. Zwraca kod wyjścia."""
    done: list[str] = []
    failed: list[str] = []
    for name in files:
        try:
            result = number_pdf(name, options)
            done.append(result.describe())
            log.info("OK: %s", result.output_path)
        except (NumberingError, PathError, OptionsError) as exc:
            failed.append(f"{name}: {exc}")
            log.warning("Błąd dla %s: %s", name, exc)

    if quiet:
        pass
    elif dialogs is not None and dialogs.available:
        if failed:
            dialogs.show_error("\n\n".join(failed + done), "PDF Numerator - błędy")
        else:
            dialogs.show_info("\n\n".join(done), "PDF Numerator - gotowe")
    else:
        for line in done:
            safe_print(line)
        for line in failed:
            safe_print(f"BŁĄD: {line}")

    return 0 if not failed else 1


def safe_print(*parts: object) -> None:
    """Pisze do konsoli, jeśli istnieje (EXE bez konsoli ma sys.stdout = None)."""
    if sys.stdout is None:
        return
    try:
        print(*parts)
    except (OSError, ValueError):
        pass


def run_folder_batch(folder: str, options: NumberOptions, recursive: bool,
                     dialogs: DialogHost | None, quiet: bool = False) -> int:
    """Numeruje cały folder. Zwraca kod wyjścia."""
    try:
        summary = number_folder(folder, options, recursive=recursive)
    except BatchError as exc:
        if quiet:
            pass
        elif dialogs is not None and dialogs.available:
            dialogs.show_error(str(exc), "PDF Numerator - błąd")
        else:
            safe_print(f"BŁĄD: {exc}")
        return 1

    lines = [summary.describe()]
    for entry in summary.failed[:20]:
        lines.append(f"  ✗ {entry['name']}: {entry['error']}")

    if quiet:
        pass
    elif dialogs is not None and dialogs.available:
        (dialogs.show_error if summary.failed else dialogs.show_info)(
            "\n".join(lines), "PDF Numerator - folder"
        )
    else:
        for line in lines:
            safe_print(line)

    return 0 if not summary.failed else 1


def start_watchdog(app: LocalApp, dialogs: DialogHost, minutes: int) -> None:
    if minutes <= 0:
        return

    def loop() -> None:
        while True:
            time.sleep(IDLE_CHECK_SECONDS)
            idle = time.monotonic() - app.last_activity
            if idle > minutes * 60:
                log.info("Zamykanie po %s minutach bezczynności", minutes)
                app.stop()
                dialogs.request_close()
                return

    threading.Thread(target=loop, name="idle-watchdog", daemon=True).start()


def run_ui(args: argparse.Namespace) -> int:
    dialogs = DialogHost()
    if not args.no_tk:
        dialogs.create()

    app = LocalApp(dialogs, token=args.token, preferred_port=args.port)
    url = app.start()
    safe_print(f"PDF Numerator {__version__} - interfejs: {url}")
    safe_print("Zamknij okno przyciskiem „Zamknij” w przeglądarce lub Ctrl+C tutaj.")

    opened = True
    if not args.no_browser:
        def open_browser() -> None:
            nonlocal opened
            try:
                opened = webbrowser.open(url)
            except Exception:
                opened = False
            if not opened and dialogs.available:
                dialogs.show_info(
                    "Nie mogłem otworzyć przeglądarki.\n\n"
                    f"Otwórz ręcznie adres:\n{url}",
                    "PDF Numerator",
                )

        threading.Timer(0.5, open_browser).start()
    start_watchdog(app, dialogs, args.idle_exit)

    try:
        if dialogs.available:
            dialogs.run()
        else:
            app.wait()
    except KeyboardInterrupt:
        log.info("Przerwano z klawiatury")
    finally:
        app.stop()
        dialogs.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    log_path = setup_logging()
    log.info("Start PDF Numerator %s, log: %s", __version__, log_path)

    try:
        options = options_from_args(args)
    except OptionsError as exc:
        safe_print(f"Błąd ustawień: {exc}")
        return 2

    if args.files or args.cli or args.folder:
        dialogs = DialogHost() if is_windowed() and not args.quiet else None
        if dialogs is not None:
            dialogs.create()
        try:
            if args.folder:
                return run_folder_batch(args.folder, options, args.recursive, dialogs,
                                        quiet=args.quiet)
            return run_batch(args.files, options, dialogs, quiet=args.quiet)
        finally:
            if dialogs is not None:
                dialogs.close()

    return run_ui(args)


if __name__ == "__main__":
    raise SystemExit(main())
