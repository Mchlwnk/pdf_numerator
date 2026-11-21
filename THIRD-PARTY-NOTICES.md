# Licencje i komponenty zewnętrzne

Projekt jest udostępniany na licencji **MIT** (plik `LICENSE`). Poniżej lista
komponentów, z których korzysta program, wraz z ich licencjami.

## PyMuPDF / MuPDF — **AGPL-3.0** (najważniejsze)

Program używa biblioteki **PyMuPDF** (opakowanie MuPDF, Artifex Software).
Jest ona dostępna na licencji **GNU AGPL-3.0** albo na licencji komercyjnej.

Co to oznacza w praktyce:

- Jeśli przekazujesz komuś gotowy plik `PDFNumerator.exe`, osoba ta **musi mieć
  możliwość uzyskania kodu źródłowego** programu (AGPL, art. 13).
  Dlatego do każdego wydania dołączamy `source.zip` (komplet źródeł z tego samego
  commita) — to wystarcza do zachowania zgodności.
- Kod źródłowy musi pozostać na tej samej licencji (AGPL) dla osób, które go
  otrzymują. Nasz kod jest dodatkowo udostępniony na MIT, więc odbiorca ma
  wybór: może korzystać z całości na AGPL.
- Użycie **wewnątrz jednej firmy/rodziny**, bez przekazywania pliku dalej, nie
  jest „dystrybucją" w rozumieniu AGPL — obowiązki pojawiają się przy
  przekazywaniu programu osobom trzecim.
- Alternatywa: **licencja komercyjna PyMuPDF** od Artifex (płatna, usuwa
  obowiązki AGPL) — <https://artifex.com/licensing>.
- Alternatywa techniczna: zamiana PyMuPDF na biblioteki permissywne
  (pypdf + reportlab) — większa zmiana w kodzie, ale bez AGPL.

## DejaVu Fonts

Czcionka `numerator/fonts/DejaVuSans.ttf` — licencja Bitstream Vera / Arev
(permissywna, wymaga zachowania informacji o prawach autorskich).
Pełny tekst: `LICENSES/DejaVu-Fonts.txt`.

## Python, Tcl/Tk, PyInstaller

- **Python** — PSF License (permissywna).
- **Tcl/Tk** — BSD-style (załączane przez PyInstaller, bez zmian).
- **PyInstaller** — GPL z wyjątkiem dla bootloadera: pakowanie własnych
  programów nim nie powoduje obowiązków GPL dla pakowanego kodu.

## Brak telemetrii i przesyłania danych

Program nie wysyła żadnych danych do internetu. Jedyny ruch sieciowy to
serwer lokalny na `127.0.0.1` (interfejs w przeglądarce). Pliki PDF są
przetwarzane wyłącznie na komputerze użytkownika.
