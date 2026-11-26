"""Test pojedynczej instancji - python tests/test_instance.py"""

from __future__ import annotations

import os
import sys
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numerator.instance as instance  # noqa: E402
from numerator.dialogs import DialogHost  # noqa: E402
from numerator.server import LocalApp  # noqa: E402

failures = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global failures
    if condition:
        print(f"  OK   {name}")
    else:
        failures += 1
        print(f"  FAIL {name} {detail}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pdfnum-instance-") as folder:
        path = Path(folder) / "instance.json"
        os.environ["PDFN_INSTANCE_FILE"] = str(path)

        dialogs = DialogHost()
        app = LocalApp(dialogs, token="instance-token", preferred_port=8899)
        app.start()
        try:
            instance.write_instance(app.port, app.token)
            saved = instance.read_instance()
            check("zapis pliku instancji", bool(saved), str(saved))
            check("port i token w pliku",
                  saved.get("port") == app.port and saved.get("token") == app.token,
                  str(saved))
            check("znacznik aplikacji", saved.get("app") == "pdf-numerator", str(saved))

            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{app.port}/api/health", timeout=2
                ) as response:
                    health = response.read().decode("utf-8")
                check("health ma znacznik", '"app": "pdf-numerator"' in health, health)
            except Exception as error:  # noqa: BLE001
                check("health ma znacznik", False, str(error))

            print("[2] zamykanie poprzedniej kopii")
            check("stop_previous zwraca True", instance.stop_previous() is True)
            try:
                urllib.request.urlopen(
                    f"http://127.0.0.1:{app.port}/api/health", timeout=1
                )
                check("poprzedni serwer zatrzymany", False, "serwer nadal odpowiada")
            except Exception:  # noqa: BLE001
                check("poprzedni serwer zatrzymany", True)

            print("[3] porzadki")
            instance.clear_instance()
            check("plik usuniety", not path.exists())
            check("brak pliku to brak instancji", instance.stop_previous() is False)
        finally:
            app.stop()

    print()
    if failures:
        print(f"NIEPOWODZENIA: {failures}")
        return 1
    print("Wszystkie testy instancji przeszły.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
