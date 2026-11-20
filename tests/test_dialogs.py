"""Test okien dialogowych (bez klikania) - python tests/test_dialogs.py"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numerator.dialogs as dialogs_module  # noqa: E402
from numerator.dialogs import DialogHost  # noqa: E402

failures = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global failures
    if condition:
        print(f"  OK   {name}")
    else:
        failures += 1
        print(f"  FAIL {name} {detail}")


def main() -> int:
    host = DialogHost()
    host.create()
    if not host.available:
        print("POMINIETO: Tk niedostępny w tym środowisku.")
        return 0

    calls: list[tuple[str, tuple]] = []
    dialogs_module.messagebox.showinfo = lambda *args, **kwargs: calls.append(("info", args))
    dialogs_module.messagebox.showerror = lambda *args, **kwargs: calls.append(("error", args))

    try:
        print("[1] podsumowanie po numerowaniu (tryb okienkowy)")
        host.show_info("Zapisano raport_numerowany.pdf", "PDF Numerator - gotowe")
        check("show_info nie rzuca wyjatku", len(calls) == 1, str(calls))
        check("show_info przekazuje tresc", calls and "raport_numerowany" in calls[0][1][1],
              str(calls))

        print("[2] komunikat bledu")
        host.show_error("Nie znaleziono pliku", "PDF Numerator - błędy")
        check("show_error nie rzuca wyjatku", len(calls) == 2, str(calls))
        check("show_error uzywa messagebox.showerror", calls[-1][0] == "error", str(calls))
    finally:
        host.close()

    print()
    if failures:
        print(f"NIEPOWODZENIA: {failures}")
        return 1
    print("Wszystkie testy okien przeszły.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
