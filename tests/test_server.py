"""Testy lokalnego serwera HTTP - python tests/test_server.py"""

from __future__ import annotations

import json
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from numerator.dialogs import DialogHost  # noqa: E402
from numerator.server import LocalApp  # noqa: E402

TOKEN = "test-token-123"
failures = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global failures
    if condition:
        print(f"  OK   {name}")
    else:
        failures += 1
        print(f"  FAIL {name} {detail}")


def call(url: str, *, payload=None, raw: bytes | None = None,
         token: str | None = TOKEN, content_type: str = "application/json"):
    data = raw
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST" if data is not None else "GET")
    if data is not None:
        request.add_header("Content-Type", content_type)
    if token:
        request.add_header("X-Token", token)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
            return response.status, dict(response.headers), body
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


def make_pdf(path: Path, pages: int = 2) -> Path:
    doc = pymupdf.open()
    for _ in range(pages):
        page = doc.new_page(width=300, height=200)
        page.insert_text((20, 30), "Tresc", fontsize=10)
    doc.save(path)
    doc.close()
    return path


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pdfnum-srv-") as raw_tmp:
        tmp = Path(raw_tmp)
        source = make_pdf(tmp / "serwer.pdf")

        dialogs = DialogHost()  # bez Tk - can_pick ma być False
        app = LocalApp(dialogs, token=TOKEN, preferred_port=8877)
        app.start()
        base = f"http://127.0.0.1:{app.port}"

        try:
            print("[1] strona i zdrowie")
            status, _, body = call(base + "/")
            check("GET / dziala", status == 200, str(status))
            check("token wstrzykniety", b"{{TOKEN}}" not in body and TOKEN.encode() in body)
            status, _, body = call(base + "/api/health")
            health = json.loads(body)
            check("health ok", status == 200 and health["ok"] is True, body[:120])
            check("bez natywnego wyboru", health["can_pick"] is False)

            print("[2] numerowanie po sciezce")
            status, _, body = call(base + "/api/number", payload={
                "path": str(source),
                "options": {"template": "{n} / {total}", "skip_first": 1, "start_at": 1},
            })
            data = json.loads(body)
            check("status 200", status == 200, body[:200])
            check("wynik zapisany", data.get("ok") is True and Path(data["output"]).is_file())
            check("nazwa kopii", data["output_name"] == "serwer_numerowany.pdf", data.get("output_name"))
            check("liczba stron", data["pages_numbered"] == 1, str(data.get("pages_numbered")))
            with pymupdf.open(data["output"]) as doc:
                check("strona 1 bez numeru", doc[0].get_text().strip() == "Tresc")
                check("strona 2 z numerem", "1 / 1" in doc[1].get_text())

            print("[3] bezpieczenstwo")
            status, _, body = call(base + "/api/number", payload={"path": str(source)}, token="zle")
            check("zly token odrzucony", status == 403, str(status))
            status, _, body = call(base + "/api/number", payload={"path": "C:/nie/ma.pdf"})
            check("brak pliku", status == 400 and "Nie znaleziono" in json.loads(body)["error"], body[:150])
            status, _, body = call(base + "/api/number", payload={"path": str(source),
                                                                  "options": {"template": "{x}"}})
            check("zly szablon", status == 400 and "znacznik" in json.loads(body)["error"].lower(),
                  body[:150])

            print("[4] przeslany plik, podglad i pobieranie")
            pdf_bytes = source.read_bytes()
            status, _, body = call(
                base + "/api/stage?name=" + urllib.parse.quote("przeslany raport.pdf"),
                raw=pdf_bytes, content_type="application/pdf",
            )
            staged = json.loads(body)
            check("stage ok", status == 200 and staged.get("ok") is True, body[:150])
            staged_path = Path(staged["path"])
            check("plik w katalogu tymczasowym", staged_path.is_file() and staged_path.name == "przeslany raport.pdf")
            check("liczba stron po stage", staged["page_count"] == 2)

            status, headers, body = call(base + "/api/preview", payload={
                "path": str(staged_path),
                "options": {"template": "{n} / {total}"},
            })
            check("podglad to PNG", status == 200 and body[:8] == b"\x89PNG\r\n\x1a\n", repr(body[:20]))
            check("naglowek strony podgladu", headers.get("X-Preview-Page") == "1",
                  str(headers.get("X-Preview-Page")))
            check("strona numerowana", headers.get("X-Is-Numbered") == "1")

            status, headers, body = call(base + "/api/preview", payload={
                "path": str(staged_path), "options": {"skip_first": 1},
            })
            check("podglad startuje od pierwszej numerowanej",
                  headers.get("X-Preview-Page") == "2" and headers.get("X-Is-Numbered") == "1",
                  f"{headers.get('X-Preview-Page')}/{headers.get('X-Is-Numbered')}")

            status, headers, body = call(base + "/api/preview", payload={
                "path": str(staged_path), "options": {"skip_first": 1}, "page": 1,
            })
            check("pominieta strona bez numeru", headers.get("X-Is-Numbered") == "0")

            status, headers, body = call(base + "/api/preview", payload={
                "path": str(staged_path), "page": 2,
            })
            check("wskazana strona podgladu", headers.get("X-Preview-Page") == "2",
                  str(headers.get("X-Preview-Page")))

            status, _, body = call(base + "/api/number", payload={
                "path": str(staged_path), "options": {"pages": "2"},
            })
            numbered = json.loads(body)
            check("wynik oznaczony jako staged", numbered.get("staged") is True, body[:150])
            check("numerowana jedna strona", numbered.get("pages_numbered") == 1)

            status, headers, body = call(base + "/api/download", payload={"path": numbered["output"]})
            check("pobieranie PDF", status == 200 and body[:5] == b"%PDF-", str(status))
            downloaded = tmp / "pobrany.pdf"
            downloaded.write_bytes(body)
            with pymupdf.open(downloaded) as doc:
                check("pobrany plik ma numer", "1" in doc[1].get_text())

            status, _, body = call(base + "/api/download", payload={"path": str(source)})
            check("pobieranie spoza sesji zablokowane", status == 403, str(status))

            status, _, body = call(base + "/api/number", payload={"path": str(source)})
            check("zwykly plik nie jest staged", json.loads(body).get("staged") is False)

            status, _, body = call(base + "/api/stage?name=zly.pdf", raw=b"to nie pdf",
                                   content_type="application/pdf")
            check("stage odrzuca nie-PDF", status == 400, str(status))

            print("[7] numerowanie folderu w tle (postęp plik po pliku)")
            job_folder = tmp / "folder-job"
            job_folder.mkdir()
            for name in ("j1.pdf", "j2.pdf", "j3.pdf"):
                make_pdf(job_folder / name, pages=2)
            (job_folder / "uszkodzony.pdf").write_bytes(b"%PDF-1.4\nzepsuty")

            status, _, body = call(base + "/api/folder-start", payload={
                "path": str(job_folder), "options": {"template": "{n}"},
            })
            job = json.loads(body)["job"]
            check("start zadania", status == 200 and job["total"] == 4, str(job.get("total")))
            check("lista plikow w zadaniu",
                  [entry["name"] for entry in job["files"]] ==
                  ["j1.pdf", "j2.pdf", "j3.pdf", "uszkodzony.pdf"],
                  str(job.get("files")))
            check("stan poczatkowy", job["state"] == "running" and job["processed"] == 0,
                  str(job["state"]))

            final = job
            deadline = time.time() + 30
            while time.time() < deadline:
                status, _, body = call(base + "/api/folder-status", payload={"id": job["id"]})
                final = json.loads(body)["job"]
                if final["state"] != "running":
                    break
                time.sleep(0.15)

            check("zadanie zakonczone", final["state"] == "done", str(final["state"]))
            check("postep 4/4", final["processed"] == 4, str(final["processed"]))
            check("trzy pliki gotowe", final["summary"]["numbered"] == 3,
                  str(final["summary"]))
            check("jeden blad", final["summary"]["errors"] == 1, str(final["summary"]))
            check("statusy per plik",
                  [entry["status"] for entry in final["files"]] ==
                  ["ok", "ok", "ok", "error"], str(final["files"]))
            check("blad wskazuje plik", final["files"][3]["name"] == "uszkodzony.pdf",
                  str(final["files"][3]))
            check("nieznane zadanie", call(base + "/api/folder-status",
                                           payload={"id": "nie-ma"})[0] == 400)

            print("[5] tryb folderu")
            folder = tmp / "folder"
            folder.mkdir()
            make_pdf(folder / "a.pdf", pages=2)
            make_pdf(folder / "b.pdf", pages=3)
            (folder / "c_numerowany.pdf").write_bytes((folder / "a.pdf").read_bytes())
            (folder / "notatka.txt").write_text("x")
            sub = folder / "podfolder"
            sub.mkdir()
            make_pdf(sub / "d.pdf", pages=1)

            status, _, body = call(base + "/api/scan", payload={"path": str(folder)})
            scanned = json.loads(body)
            check("scan folderu", status == 200 and scanned["pdf_count"] == 2,
                  str(scanned.get("pdf_count")))
            check("pomija kopie programu", "c_numerowany.pdf" not in scanned["examples"],
                  str(scanned.get("examples")))
            check("lista nazw w scanie", scanned["files"] == ["a.pdf", "b.pdf"],
                  str(scanned.get("files")))
            check("licznik podfolderow", scanned["subfolder_count"] == 1,
                  str(scanned.get("subfolder_count")))
            check("podglad z pierwszego pliku", scanned["preview_name"] == "a.pdf",
                  str(scanned.get("preview_name")))

            status, _, body = call(base + "/api/scan", payload={"path": str(folder), "recursive": True})
            check("scan z podfolderami", json.loads(body)["pdf_count"] == 3,
                  str(json.loads(body).get("pdf_count")))

            status, _, body = call(base + "/api/folder-number", payload={
                "path": str(folder),
                "options": {"template": "{n} / {total}"},
            })
            summary = json.loads(body)
            check("folder-number ok", status == 200 and summary["numbered"] == 2, body[:200])
            check("nazwy wynikow", sorted(e["output"] for e in summary["done"]) ==
                  ["a_numerowany.pdf", "b_numerowany.pdf"], str(summary.get("done")))
            with pymupdf.open(folder / "a_numerowany.pdf") as doc:
                check("plik z folderu ma numer", "1 / 2" in doc[0].get_text())

            status, _, body = call(base + "/api/folder-number", payload={"path": str(tmp / "brak")})
            check("folder-number zly folder", status == 400, str(status))

            broken_folder = tmp / "folder-z-bledem"
            broken_folder.mkdir()
            make_pdf(broken_folder / "dobry.pdf", pages=1)
            (broken_folder / "uszkodzony.pdf").write_bytes(b"%PDF-1.4\nuszkodzony")
            status, _, body = call(base + "/api/folder-number", payload={"path": str(broken_folder)})
            broken = json.loads(body)
            check("blad pliku nie przerywa folderu",
                  status == 200 and broken["numbered"] == 1 and broken["errors"] == 1,
                  body[:200])
            check("nazwa uszkodzonego pliku w bledach",
                  broken["failed"][0]["name"] == "uszkodzony.pdf", str(broken["failed"]))

            print("[6] style i maskowanie przez API")
            style_src = make_pdf(tmp / "style.pdf", pages=3)
            status, _, body = call(base + "/api/number", payload={
                "path": str(style_src),
                "options": {"style": "roman", "appendix_from": 3, "appendix_style": "ALPHA"},
            })
            check("styl rzymski przyjety", status == 200, body[:150])
            styled = json.loads(body)
            with pymupdf.open(styled["output"]) as doc:
                labels = [doc[i].get_text().strip().splitlines()[-1] for i in range(3)]
            check("etykiety stylu", labels == ["i", "ii", "A"], str(labels))
            check("stron dodatku w odpowiedzi", styled["appendix_pages"] == 1,
                  str(styled.get("appendix_pages")))

            status, _, body = call(base + "/api/preview", payload={
                "path": str(style_src),
                "options": {"mask_existing": True, "mask_width": 40, "mask_height": 12,
                            "style": "roman"},
            })
            check("podglad z maska i stylem",
                  status == 200 and body[:8] == b"\x89PNG\r\n\x1a\n", str(status))

            status, headers, body = call(base + "/api/preview", payload={
                "path": str(style_src),
                "options": {"style": "roman", "appendix_from": 3, "appendix_style": "ROMAN"},
                "page": 3,
            })
            check("etykieta numeru w naglowku",
                  urllib.parse.unquote(headers.get("X-Preview-Label", "")) == "I",
                  repr(headers.get("X-Preview-Label")))

            status, headers, body = call(base + "/api/preview", payload={
                "path": str(style_src),
                "options": {"skip_first": 1},
                "page": 1,
            })
            check("pusta etykieta dla pominiętej strony",
                  headers.get("X-Preview-Label") == "", repr(headers.get("X-Preview-Label")))

            print("[8] probka napisu")
            status, headers, body = call(base + "/api/label-sample", payload={
                "path": str(style_src),
                "options": {"style": "roman", "template": "Strona {n} z {total}"},
                "page": 2,
            })
            check("probka to PNG", status == 200 and body[:8] == b"\x89PNG\r\n\x1a\n", str(status))
            check("etykieta probki",
                  urllib.parse.unquote(headers.get("X-Preview-Label", "")) == "Strona ii z iii",
                  repr(headers.get("X-Preview-Label")))

            status, _, body = call(base + "/api/label-sample", payload={
                "path": str(style_src), "options": {"skip_first": 1}, "page": 1,
            })
            check("probka dla pominiętej strony to blad", status == 400, str(status))

            print("[9] wybor pliku bez Tk i 404")
            status, _, body = call(base + "/api/pick", payload={})
            check("pick bez Tk -> 501", status == 501, str(status))
            status, _, body = call(base + "/api/nieznany", payload={})
            check("nieznany endpoint", status == 404, str(status))

            print("[10] zamkniecie")
            status, _, body = call(base + "/api/quit", payload={})
            check("quit ok", status == 200 and json.loads(body)["ok"] is True)
        finally:
            app.stop()

    print()
    if failures:
        print(f"NIEPOWODZENIA: {failures}")
        return 1
    print("Wszystkie testy serwera przeszły.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
