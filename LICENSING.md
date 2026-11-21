# Licencjonowanie

## W skrócie (dla działu IT)

- Program jest **darmowy**. Można go używać w firmie bez opłat i bez rejestracji.
- **Kod źródłowy jest publiczny** (repozytorium GitHub) i dołączany do każdego wydania
  jako `source-<wersja>.zip`, więc wymóg udostępnienia źródeł jest spełniony.
- Kod autorski: **MIT** (użycie, zmiany, publikacja — także komercyjna).
- Całość zawiera bibliotekę **PyMuPDF** na licencji **AGPL-3.0**, dlatego program jako
  całość jest udostępniany na AGPL-3.0.
- **Brak gwarancji** — program dostarczany jest „tak jak jest" (AS IS).
- Program **nie wymaga instalacji, uprawnień administratora ani dostępu do internetu**;
  pliki PDF są przetwarzane wyłącznie lokalnie.

Praktyczny wniosek: używanie programu w firmie (także przez kilka osób) jest dozwolone.
Nie ma opłat licencyjnych ani obowiązku zgłaszania czegokolwiek, o ile źródła pozostają
dostępne — a są, publicznie i w każdym wydaniu.

## Kod autorski — MIT

Cały kod napisany na potrzeby tego projektu (katalog `numerator/`, `tests/`,
skrypty `build.ps1`, `sign.ps1`, `release.ps1`) jest udostępniany na licencji
**MIT** — plik [`LICENSE`](LICENSE). Możesz go używać, zmieniać, publikować
i sprzedawać, zachowując informację o prawach autorskich.

## Całość (program z PyMuPDF) — AGPL-3.0

Gotowy program zawiera **PyMuPDF / MuPDF** (Artifex Software), dostępny na
**GNU AGPL-3.0**. Dlatego **dystrybuowana całość** (np. plik EXE albo spakowane
źródła) podlega AGPL-3.0:

- udostępniając program innym, musisz dać im **dostęp do kodu źródłowego**
  (tutaj: publiczne repozytorium + `source-<wersja>.zip` w każdym wydaniu),
- odbiorca ma prawo do modyfikacji i dalszej dystrybucji na zasadach AGPL,
- nie możesz z tego zrobić zamkniętego produktu bez wykupienia licencji
  komercyjnej PyMuPDF.

Pełny tekst: [`LICENSES/AGPL-3.0.txt`](LICENSES/AGPL-3.0.txt).

**Użycie bez dystrybucji** (np. u siebie, w rodzinie, w jednej firmie — bez
przekazywania pliku na zewnątrz) nie uruchamia obowiązków AGPL.

## Chcesz czystego MIT?

Wystarczy zastąpić PyMuPDF bibliotekami na licencji permissywnej:

- `pypdf` (BSD) do składania stron i zapisu,
- `reportlab` (BSD) do rysowania numerów na nakładce.

To zmiana w `numerator/core.py` i `fonts.py` (ok. 200 linii) — efekt: całość
może być wtedy udostępniona wyłącznie na MIT. Daj znać, jeśli chcesz tę wersję.

## Pozostałe komponenty

- Czcionka DejaVu — Bitstream Vera / Arev, tekst w `LICENSES/DejaVu-Fonts.txt`,
- Python — PSF License,
- Tcl/Tk — BSD-style,
- PyInstaller — GPL z wyjątkiem dla bootloadera.

Szczegóły: [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md).
