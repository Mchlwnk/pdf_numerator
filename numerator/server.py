"""Lokalny serwer HTTP (tylko 127.0.0.1) obsługujący interfejs użytkownika."""

from __future__ import annotations

import copy
import json
import logging
import os
import re
import secrets
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from . import __version__
from .assemble import AssembleError, SpliceOperation, splice_pdfs
from .batch import MAX_FILES, BatchError, find_pdfs, number_folder, read_folder
from .core import (
    NumberingError,
    inspect_pdf,
    number_pdf,
    render_label_sample,
    render_preview,
)
from .dialogs import DialogHost, DialogUnavailable
from .fonts import app_resource_dir
from .options import NumberOptions, OptionsError
from .paths import PathError, ensure_pdf_source, is_writable_directory

log = logging.getLogger(__name__)

MAX_JSON_BODY = 1 << 20  # 1 MB
MAX_UPLOAD_BODY = 400 << 20  # 400 MB
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
_INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _safe_filename(name: str) -> str:
    """Nazwa pliku bez ścieżek i znaków niedozwolonych w Windows."""
    base = Path(name or "dokument.pdf").name
    base = _INVALID_FILENAME.sub("_", base).strip(" .") or "dokument.pdf"
    if not base.lower().endswith(".pdf"):
        base += ".pdf"
    return base[:180]


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


class LocalApp:
    """Serwer aplikacji wraz z tokenem chroniącym przed obcymi stronami."""

    def __init__(self, dialogs: DialogHost, token: str | None = None,
                 preferred_port: int = 8765) -> None:
        self.dialogs = dialogs
        self.token = token or secrets.token_urlsafe(24)
        self.preferred_port = preferred_port
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.port = 0
        self._html = self._load_html()
        self._stop_event = threading.Event()
        self.last_activity = time.monotonic()
        self._stage_lock = threading.RLock()
        self._stage_dir: Path | None = None
        self._job_lock = threading.RLock()
        self._job: dict | None = None

    def touch(self) -> None:
        self.last_activity = time.monotonic()

    def wait(self) -> None:
        """Blokuje wątek główny, gdy nie ma pętli Tk."""
        self._stop_event.wait()

    # -- pliki przesłane przez przeglądarkę -----------------------------------

    def stage_pdf(self, filename: str, data: bytes, replace: bool = False) -> Path:
        """Zapisuje przesłany plik w katalogu tymczasowym i zwraca jego ścieżkę."""
        with self._stage_lock:
            if replace or self._stage_dir is None:
                self.clear_stage()
                self._stage_dir = Path(tempfile.mkdtemp(prefix="pdfnum-stage-"))
            directory = self._stage_dir
            safe = _safe_filename(filename)
            stem, _, extension = safe.rpartition(".")
            stem = stem or "dokument"
            path = directory / safe
            index = 1
            while path.exists():
                index += 1
                path = directory / f"{stem}_{index}.{extension}"
            path.write_bytes(data)
            return path

    def clear_stage(self) -> None:
        with self._stage_lock:
            if self._stage_dir is not None:
                shutil.rmtree(self._stage_dir, ignore_errors=True)
                self._stage_dir = None

    def is_staged(self, path: Path) -> bool:
        """Czy plik leży w katalogu tymczasowym tej sesji (tylko takie można pobierać)."""
        if self._stage_dir is None:
            return False
        try:
            return path.resolve().is_relative_to(self._stage_dir.resolve())
        except (OSError, ValueError):
            return False

    # -- numerowanie folderu w tle (postęp plik po pliku) ----------------------

    def start_folder_job(self, folder: str | Path, options: NumberOptions,
                         recursive: bool) -> dict:
        with self._job_lock:
            if self._job is not None and self._job.get("state") == "running":
                raise BatchError(
                    "Trwa już numerowanie folderu - poczekaj na zakończenie."
                )

        root = read_folder(folder, recursive)
        if not is_writable_directory(root):
            raise BatchError(f"Brak prawa zapisu w folderze: {root}")
        files = find_pdfs(root, recursive, options.suffix)
        if not files:
            raise BatchError("W tym folderze nie ma plików PDF do ponumerowania.")
        if len(files) > MAX_FILES:
            raise BatchError(
                f"W folderze jest {len(files)} plików PDF, a limit to {MAX_FILES}. "
                "Podziel pracę na mniejsze foldery."
            )

        job = {
            "id": secrets.token_hex(8),
            "state": "running",
            "folder": str(root),
            "total": len(files),
            "processed": 0,
            "current": None,
            "files": [{"name": path.name, "status": "pending"} for path in files],
            "summary": None,
            "error": None,
            "started": time.time(),
        }
        with self._job_lock:
            self._job = job
        threading.Thread(
            target=self._run_folder_job, args=(job, root, options, recursive),
            name="folder-job", daemon=True,
        ).start()
        log.info("Start numerowania folderu %s (%s plików)", root, len(files))
        return self._job_snapshot(job)

    def _run_folder_job(self, job: dict, root: Path, options: NumberOptions,
                        recursive: bool) -> None:
        def on_event(event: dict) -> None:
            index = int(event["index"]) - 1
            with self._job_lock:
                entries = job["files"]
                if not 0 <= index < len(entries):
                    return
                entry = entries[index]
                if entry["name"] != event["name"]:
                    return
                entry["status"] = "ok" if event["type"] == "ok" else "error"
                if event["type"] == "ok":
                    entry["output"] = event.get("output")
                elif event["type"] == "error":
                    entry["error"] = event.get("error")
                job["current"] = event["name"]
                job["processed"] = index + (1 if event["type"] in ("ok", "error") else 0)

        try:
            summary = number_folder(root, options, recursive=recursive, on_event=on_event)
        except BatchError as exc:
            with self._job_lock:
                job["state"] = "error"
                job["error"] = str(exc)
            return
        except Exception as exc:  # noqa: BLE001
            log.exception("Nieoczekiwany błąd numerowania folderu")
            with self._job_lock:
                job["state"] = "error"
                job["error"] = f"Nieoczekiwany błąd: {exc}"
            return

        with self._job_lock:
            job["summary"] = summary.as_dict()
            job["state"] = "done"
            job["current"] = None
            job["processed"] = job["total"]
        log.info("Folder %s: %s", root, summary.describe())

    def _job_snapshot(self, job: dict) -> dict:
        with self._job_lock:
            return copy.deepcopy(job)

    def folder_job_status(self, job_id: str) -> dict:
        with self._job_lock:
            if self._job is None or self._job.get("id") != job_id:
                raise BatchError("Nie znaleziono zadania numerowania - uruchom je ponownie.")
            return copy.deepcopy(self._job)

    # -- uruchomienie ---------------------------------------------------------

    def start(self) -> str:
        handler = _make_handler(self)
        self.port = _find_free_port(self.preferred_port)
        self._httpd = ThreadingHTTPServer(("127.0.0.1", self.port), handler)
        self._httpd.daemon_threads = True
        self._thread = threading.Thread(
            target=self._httpd.serve_forever, kwargs={"poll_interval": 0.2},
            name="http-server", daemon=True,
        )
        self._thread.start()
        log.info("Serwer wystartował na porcie %s", self.port)
        return self.url

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/?t={self.token}"

    def stop(self) -> None:
        if self._httpd is not None:
            threading.Thread(target=self._httpd.shutdown, daemon=True).start()
            self._httpd = None
        self.clear_stage()
        self._stop_event.set()
        log.info("Serwer zatrzymany")

    # -- zasoby ---------------------------------------------------------------

    def _load_html(self) -> bytes:
        path = app_resource_dir() / "web" / "index.html"
        try:
            html = path.read_text(encoding="utf-8")
        except OSError:
            log.exception("Brak pliku interfejsu: %s", path)
            html = "<h1>Brak pliku interfejsu (web/index.html)</h1>"
        html = html.replace("{{TOKEN}}", self.token).replace("{{VERSION}}", __version__)
        return html.encode("utf-8")


def _find_free_port(preferred: int, attempts: int = 25) -> int:
    for port in range(preferred, preferred + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _make_handler(app: LocalApp):
    class Handler(BaseHTTPRequestHandler):
        server_version = f"PDFNumerator/{__version__}"
        protocol_version = "HTTP/1.1"

        # -- pomocnicze -------------------------------------------------------

        def log_message(self, fmt: str, *args) -> None:  # noqa: A003
            log.debug("%s - %s", self.address_string(), fmt % args)

        def _send(self, payload: bytes, status: int = 200, content_type: str = "application/json",
                  extra: dict[str, str] | None = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(payload)

        def _json(self, data, status: int = 200) -> None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self._send(body, status)

        def _error(self, message: str, status: int = 400) -> None:
            self._json({"ok": False, "error": message}, status)

        def _body(self, limit: int) -> bytes:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise ApiError("Niepoprawny nagłówek Content-Length.")
            if length > limit:
                self.close_connection = True
                raise ApiError("Plik jest zbyt duży dla tego narzędzia.", 413)
            return self.rfile.read(length) if length else b""

        def _json_body(self) -> dict:
            raw = self._body(MAX_JSON_BODY)
            if not raw:
                return {}
            try:
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise ApiError("Niepoprawne dane żądania.")
            if not isinstance(data, dict):
                raise ApiError("Niepoprawne dane żądania.")
            return data

        def _authorized(self) -> bool:
            if self.headers.get("X-Token") != app.token:
                return False
            origin = self.headers.get("Origin")
            if origin:
                host = urlparse(origin).hostname
                if host not in LOCAL_HOSTS:
                    return False
            return True

        # -- routing ----------------------------------------------------------

        def do_GET(self) -> None:  # noqa: N802
            app.touch()
            parsed = urlparse(self.path)
            if parsed.path in ("/", "/index.html"):
                return self._send(app._html, content_type="text/html; charset=utf-8")
            if parsed.path == "/api/health":
                return self._json({
                    "ok": True,
                    "can_pick": app.dialogs.available,
                    "version": __version__,
                })
            if parsed.path == "/favicon.ico":
                return self._send(b"", status=204, content_type="image/x-icon")
            return self._error("Nie znaleziono.", 404)

        def do_POST(self) -> None:  # noqa: N802
            app.touch()
            parsed = urlparse(self.path)
            if not self._authorized():
                self.close_connection = True
                return self._error("Brak autoryzacji.", 403)
            try:
                if parsed.path == "/api/pick":
                    return self._handle_pick()
                if parsed.path == "/api/pick-many":
                    return self._handle_pick_many()
                if parsed.path == "/api/pick-folder":
                    return self._handle_pick_folder()
                if parsed.path == "/api/splice":
                    return self._handle_splice()
                if parsed.path == "/api/scan":
                    return self._handle_scan()
                if parsed.path == "/api/folder-number":
                    return self._handle_folder_number()
                if parsed.path == "/api/folder-start":
                    return self._handle_folder_start()
                if parsed.path == "/api/folder-status":
                    return self._handle_folder_status()
                if parsed.path == "/api/inspect":
                    return self._handle_inspect()
                if parsed.path == "/api/number":
                    return self._handle_number()
                if parsed.path == "/api/stage":
                    return self._handle_stage(parse_qs(parsed.query))
                if parsed.path == "/api/preview":
                    return self._handle_preview()
                if parsed.path == "/api/label-sample":
                    return self._handle_label_sample()
                if parsed.path == "/api/download":
                    return self._handle_download()
                if parsed.path == "/api/reveal":
                    return self._handle_reveal(open_file=False)
                if parsed.path == "/api/open":
                    return self._handle_reveal(open_file=True)
                if parsed.path == "/api/quit":
                    return self._handle_quit()
            except (ApiError, PathError, OptionsError, NumberingError, BatchError,
                    AssembleError, DialogUnavailable) as exc:
                message = getattr(exc, "message", None) or str(exc)
                log.warning("Błąd %s: %s", parsed.path, message)
                return self._error(message, getattr(exc, "status", 400))
            except Exception as exc:  # noqa: BLE001
                log.exception("Nieoczekiwany błąd %s", parsed.path)
                return self._error(f"Nieoczekiwany błąd: {exc}", 500)
            return self._error("Nie znaleziono.", 404)

        # -- endpointy --------------------------------------------------------

        def _handle_pick(self) -> None:
            self._json_body()
            if not app.dialogs.available:
                raise ApiError(
                    "Wybór pliku z okna systemowego jest niedostępny. "
                    "Przeciągnij plik na stronę.", 501,
                )
            chosen = app.dialogs.ask_pdf_path()
            if not chosen:
                return self._json({"ok": True, "cancelled": True})
            info = inspect_pdf(chosen)
            if info.needs_password:
                raise ApiError("Ten PDF jest zabezpieczony hasłem.")
            return self._json({"ok": True, "cancelled": False, **file_info(info)})

        def _handle_inspect(self) -> None:
            data = self._json_body()
            path = _require_path(data)
            info = inspect_pdf(path)
            return self._json({"ok": True, **file_info(info)})

        def _handle_pick_many(self) -> None:
            self._json_body()
            if not app.dialogs.available:
                raise ApiError(
                    "Wybór wielu plików z okna systemowego jest niedostępny.", 501
                )
            chosen = app.dialogs.ask_pdf_paths()
            if not chosen:
                return self._json({"ok": True, "cancelled": True, "files": []})
            files = []
            for path in chosen:
                info = inspect_pdf(path)
                files.append({
                    "path": str(info.path),
                    "name": info.path.name,
                    "page_count": info.page_count,
                    "size_bytes": info.size_bytes,
                    "needs_password": info.needs_password,
                })
            return self._json({"ok": True, "cancelled": False, "files": files})

        def _handle_splice(self) -> None:
            data = self._json_body()
            main_value = data.get("main")
            if not isinstance(main_value, str) or not main_value.strip():
                raise ApiError("Brak ścieżki do dokumentu głównego.")
            main = ensure_pdf_source(Path(main_value))

            raw_inserts = data.get("inserts")
            if not isinstance(raw_inserts, list) or not raw_inserts:
                raise ApiError("Dodaj co najmniej jeden plik PDF do wstawienia.")

            operations: list[SpliceOperation] = []
            for entry in raw_inserts:
                if isinstance(entry, str):
                    operations.append(SpliceOperation(path=entry))
                    continue
                if not isinstance(entry, dict):
                    raise ApiError("Niepoprawna lista plików do wstawienia.")
                path = entry.get("path")
                if not isinstance(path, str) or not path.strip():
                    raise ApiError("Brak ścieżki jednego z plików do wstawienia.")
                operations.append(SpliceOperation(
                    path=path,
                    mode=str(entry.get("mode", "insert")),
                    after_page=_int_field(entry, "after_page", 0),
                    replace_from=_int_field(entry, "replace_from", 1),
                    replace_to=_int_field(entry, "replace_to", 1),
                ))

            options = NumberOptions.from_dict(data.get("options"))
            number = bool(data.get("number", True))
            result = splice_pdfs(main, operations, options, number=number)
            log.info("Złożono dokument: %s", result.describe())
            numbered = result.numbered
            return self._json({
                "ok": True,
                "output": str(result.output_path),
                "output_name": result.output_path.name,
                "staged": app.is_staged(result.output_path),
                "page_count_before": result.page_count_before,
                "page_count_after": result.page_count_after,
                "inserted_pages": result.inserted_pages,
                "replaced_pages": result.replaced_pages,
                "numbered": numbered is not None,
                "pages_numbered": numbered.pages_numbered if numbered else 0,
                "first_number": numbered.first_number if numbered else None,
                "last_number": numbered.last_number if numbered else None,
                "warnings": [],
            })

        def _handle_pick_folder(self) -> None:
            self._json_body()
            if not app.dialogs.available:
                raise ApiError(
                    "Wybór folderu z okna systemowego jest niedostępny. "
                    "Wpisz ścieżkę folderu ręcznie.", 501,
                )
            chosen = app.dialogs.ask_directory()
            if not chosen:
                return self._json({"ok": True, "cancelled": True})
            return self._json({"ok": True, "cancelled": False, **_folder_info(chosen, False)})

        def _handle_scan(self) -> None:
            data = self._json_body()
            folder = _require_folder(data)
            recursive = bool(data.get("recursive"))
            return self._json({"ok": True, **_folder_info(folder, recursive)})

        def _handle_folder_number(self) -> None:
            data = self._json_body()
            folder = _require_folder(data)
            options = NumberOptions.from_dict(data.get("options"))
            summary = number_folder(folder, options, recursive=bool(data.get("recursive")))
            log.info("Folder %s: %s", folder, summary.describe())
            return self._json(summary.as_dict())

        def _handle_folder_start(self) -> None:
            data = self._json_body()
            folder = _require_folder(data)
            options = NumberOptions.from_dict(data.get("options"))
            job = app.start_folder_job(folder, options, recursive=bool(data.get("recursive")))
            return self._json({"ok": True, "job": job})

        def _handle_folder_status(self) -> None:
            data = self._json_body()
            job_id = data.get("id")
            if not isinstance(job_id, str) or not job_id:
                raise ApiError("Brak identyfikatora zadania.")
            return self._json({"ok": True, "job": app.folder_job_status(job_id)})

        def _handle_number(self) -> None:
            data = self._json_body()
            path = _require_path(data)
            options = NumberOptions.from_dict(data.get("options"))
            result = number_pdf(path, options)
            log.info("Ponumerowano %s -> %s", path, result.output_path)
            warnings = []
            if result.font_fallback:
                warnings.append("Brak czcionki z polskimi znakami - użyto podstawowej.")
            if result.font_shrunk:
                warnings.append("Numer był szerszy niż strona - czcionka została zmniejszona.")
            return self._json({
                "ok": True,
                "output": str(result.output_path),
                "output_name": result.output_path.name,
                "directory": str(result.output_path.parent),
                "staged": app.is_staged(result.output_path),
                "page_count": result.page_count,
                "pages_numbered": result.pages_numbered,
                "appendix_pages": result.appendix_pages,
                "first_number": result.first_number,
                "last_number": result.last_number,
                "warnings": warnings,
            })

        def _handle_label_sample(self) -> None:
            data = self._json_body()
            path = _require_path(data)
            options = NumberOptions.from_dict(data.get("options"))
            page = data.get("page")
            try:
                page_number = int(page) if page not in (None, "") else None
            except (TypeError, ValueError):
                raise ApiError("Niepoprawny numer strony podglądu.")
            image = render_label_sample(path, options, page_number=page_number)
            self._send(
                image.data,
                content_type="image/png",
                extra={
                    "X-Preview-Label": quote(image.label or "", safe=""),
                    "X-Preview-Page": str(image.page_number),
                },
            )

        def _handle_stage(self, query: dict[str, list[str]]) -> None:
            data = self._body(MAX_UPLOAD_BODY)
            if not data:
                raise ApiError("Nie otrzymałem pliku.")
            if b"%PDF-" not in data[:1024]:
                raise ApiError("Przesłany plik nie jest dokumentem PDF.")
            name = (query.get("name") or ["dokument.pdf"])[0]
            path = app.stage_pdf(name, data)
            try:
                info = inspect_pdf(path)
                if info.needs_password:
                    raise ApiError("Ten PDF jest zabezpieczony hasłem.")
            except Exception:
                path.unlink(missing_ok=True)
                raise
            log.info("Przygotowano plik: %s (%s stron)", path.name, info.page_count)
            return self._json({"ok": True, "staged": True, **file_info(info)})

        def _handle_preview(self) -> None:
            data = self._json_body()
            path = _require_path(data)
            options = NumberOptions.from_dict(data.get("options"))
            page = data.get("page")
            try:
                page_number = int(page) if page not in (None, "") else None
            except (TypeError, ValueError):
                raise ApiError("Niepoprawny numer strony podglądu.")
            preview = render_preview(path, options, page_number=page_number)
            self._send(
                preview.data,
                content_type="image/png",
                extra={
                    "X-Preview-Page": str(preview.page_number),
                    "X-Page-Count": str(preview.page_count),
                    "X-Numbered-Pages": str(preview.numbered_pages),
                    "X-Is-Numbered": "1" if preview.is_numbered else "0",
                    "X-Preview-Label": quote(preview.label or "", safe=""),
                },
            )

        def _handle_download(self) -> None:
            data = self._json_body()
            path = Path(_require_path(data))
            if not app.is_staged(path):
                raise ApiError("Ten plik nie pochodzi z tej sesji.", 403)
            payload = path.read_bytes()
            encoded = quote(path.name)
            self._send(
                payload,
                content_type="application/pdf",
                extra={
                    "Content-Disposition": f"attachment; filename*=UTF-8''{encoded}",
                    "X-Output-Name": encoded,
                },
            )
            log.info("Wydano plik do pobrania: %s", path.name)

        def _handle_reveal(self, *, open_file: bool) -> None:
            data = self._json_body()
            path = Path(_require_path(data)).expanduser()
            if not path.exists():
                raise ApiError(f"Plik nie istnieje: {path}")
            if open_file:
                try:
                    os.startfile(str(path))  # type: ignore[attr-defined]
                except OSError as exc:
                    raise ApiError(f"Nie mogę otworzyć pliku: {exc}") from exc
            else:
                try:
                    subprocess.Popen(["explorer", "/select,", str(path)])
                except OSError as exc:
                    raise ApiError(f"Nie mogę otworzyć folderu: {exc}") from exc
            return self._json({"ok": True})

        def _handle_quit(self) -> None:
            self._json({"ok": True})
            app.stop()
            app.dialogs.request_close()

    return Handler


def _require_path(data: dict) -> str:
    path = data.get("path")
    if not isinstance(path, str) or not path.strip():
        raise ApiError("Brak ścieżki do pliku.")
    ensure_pdf_source(Path(path))
    return path


def _int_field(data: dict, name: str, default: int) -> int:
    value = data.get(name, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ApiError(f"Niepoprawna wartość pola {name}.")


def _require_folder(data: dict) -> Path:
    path = data.get("path")
    if not isinstance(path, str) or not path.strip():
        raise ApiError("Brak ścieżki do folderu.")
    return read_folder(path)


def _folder_info(folder: Path, recursive: bool) -> dict:
    files = find_pdfs(folder, recursive)
    total = 0
    for path in files:
        try:
            total += path.stat().st_size
        except OSError:
            continue
    subfolder_count = 0
    if not recursive:
        try:
            subfolder_count = max(0, len(find_pdfs(folder, True)) - len(files))
        except (BatchError, OSError):
            subfolder_count = 0
    return {
        "path": str(folder),
        "name": folder.name or str(folder),
        "pdf_count": len(files),
        "size_bytes": total,
        "recursive": recursive,
        "examples": [path.name for path in files[:5]],
        "files": [path.name for path in files[:300]],
        "files_truncated": len(files) > 300,
        "subfolder_count": subfolder_count,
        "preview_path": str(files[0]) if files else None,
        "preview_name": files[0].name if files else None,
    }


def file_info(info) -> dict:
    data = asdict(info)
    data["path"] = str(info.path)
    data["name"] = info.path.name
    data["directory"] = str(info.path.parent)
    return data
