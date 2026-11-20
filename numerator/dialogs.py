"""Natywne okna Windows obsługiwane w wątku Tk (serwer HTTP działa w tle)."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import filedialog, messagebox

POLL_INTERVAL_MS = 60


class DialogUnavailable(RuntimeError):
    """Brak możliwości pokazania okna (np. tkinter niedostępny)."""


@dataclass
class _Job:
    kind: str
    kwargs: dict
    event: threading.Event = field(default_factory=threading.Event)
    result: object = None
    error: BaseException | None = None


class DialogHost:
    """Kolejka żądań z wątku serwera do wątku Tk.

    Tk musi działać w wątku głównym, dlatego serwer HTTP tylko odkłada zadania,
    a ten obiekt wykonuje je w pętli ``run()``.
    """

    def __init__(self) -> None:
        self.available = False
        self._root: tk.Tk | None = None
        self._queue: queue.Queue[_Job] = queue.Queue()
        self._mainloop_running = False

    # -- cykl życia -----------------------------------------------------------

    def create(self) -> None:
        try:
            root = tk.Tk()
        except Exception:
            self.available = False
            return
        root.withdraw()
        root.title("PDF Numerator")
        try:
            root.iconbitmap(default="")
        except Exception:
            pass
        self._root = root
        self.available = True
        root.after(POLL_INTERVAL_MS, self._pump)

    def run(self) -> None:
        if self._root is None:
            raise DialogUnavailable("Tk nie został zainicjalizowany.")
        self._mainloop_running = True
        try:
            self._root.mainloop()
        finally:
            self._mainloop_running = False

    def close(self) -> None:
        if self._root is not None:
            try:
                self._root.quit()
                self._root.destroy()
            except Exception:
                pass
            self._root = None
            self.available = False

    def _pump(self) -> None:
        root = self._root
        if root is None:
            return
        while True:
            try:
                job = self._queue.get_nowait()
            except queue.Empty:
                break
            try:
                job.result = self._execute(job)
            except BaseException as exc:  # noqa: BLE001 - przekazujemy błąd do wątku serwera
                job.error = exc
            finally:
                job.event.set()
        try:
            root.after(POLL_INTERVAL_MS, self._pump)
        except tk.TclError:
            pass

    def _execute(self, job: _Job):
        if job.kind == "open_pdf":
            return self._pick_pdf()
        if job.kind == "open_dir":
            return self._pick_folder()
        if job.kind == "close":
            if self._root is not None:
                self._root.after(0, self._root.quit)
            return None
        if job.kind == "message":
            return self._message(**job.kwargs)
        raise ValueError(f"Nieznane zadanie: {job.kind}")

    # -- wywołania z innych wątków -------------------------------------------

    def _submit(self, action: str, timeout: float, **kwargs):
        if not self.available or self._root is None:
            raise DialogUnavailable("Okno systemowe jest niedostępne.")
        job = _Job(kind=action, kwargs=kwargs)
        if not self._mainloop_running and threading.current_thread() is threading.main_thread():
            # Tryb wsadowy: nie ma pętli zdarzeń, więc okno pokazujemy od razu.
            job.result = self._execute(job)
            return job.result
        self._queue.put(job)
        if not job.event.wait(timeout):
            raise DialogUnavailable("Przekroczono czas oczekiwania na okno.")
        if job.error is not None:
            raise job.error
        return job.result

    def ask_pdf_path(self, timeout: float = 600.0) -> Path | None:
        result = self._submit("open_pdf", timeout)
        return Path(result) if result else None

    def ask_directory(self, timeout: float = 600.0) -> Path | None:
        result = self._submit("open_dir", timeout)
        return Path(result) if result else None

    def request_close(self, timeout: float = 10.0) -> None:
        """Zamyka pętlę Tk z wątku serwera (bezpiecznie, przez kolejkę)."""
        try:
            self._submit("close", timeout)
        except DialogUnavailable:
            self.close()

    def show_info(self, text: str, title: str = "PDF Numerator", timeout: float = 120.0) -> None:
        self._submit("message", timeout, text=text, title=title, kind="info")

    def show_error(self, text: str, title: str = "PDF Numerator", timeout: float = 120.0) -> None:
        self._submit("message", timeout, text=text, title=title, kind="error")

    # -- wykonanie w wątku Tk -------------------------------------------------

    def _foreground(self) -> None:
        try:
            self._root.attributes("-topmost", True)
            self._root.update()
        except tk.TclError:
            pass

    def _hide(self) -> None:
        try:
            self._root.attributes("-topmost", False)
            self._root.withdraw()
        except tk.TclError:
            pass

    def _pick_pdf(self) -> str:
        self._foreground()
        try:
            chosen = filedialog.askopenfilename(
                parent=self._root,
                title="Wybierz dokument PDF do ponumerowania",
                filetypes=[("Dokumenty PDF", "*.pdf"), ("Wszystkie pliki", "*.*")],
            )
        finally:
            self._hide()
        return chosen or ""

    def _pick_folder(self) -> str:
        self._foreground()
        try:
            chosen = filedialog.askdirectory(
                parent=self._root,
                title="Wybierz folder z dokumentami PDF",
                mustexist=True,
            )
        finally:
            self._hide()
        return chosen or ""

    def _message(self, text: str, title: str, kind: str = "info") -> None:
        root = self._root
        try:
            root.attributes("-topmost", True)
            root.update()
        except tk.TclError:
            pass
        try:
            if kind == "error":
                messagebox.showerror(title, text, parent=root)
            else:
                messagebox.showinfo(title, text, parent=root)
        finally:
            try:
                root.attributes("-topmost", False)
            except tk.TclError:
                pass
        return None
