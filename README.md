# PDF Numerator

[![Release](https://img.shields.io/github/v/release/Mchlwnk/pdf_numerator?display_name=tag)](https://github.com/Mchlwnk/pdf_numerator/releases)
[![Licencja](https://img.shields.io/badge/licencja-MIT%20%2B%20AGPL--3.0-blue)](LICENSING.md)
[![Platforma](https://img.shields.io/badge/platforma-Windows%2010%2F11-lightgrey)](https://github.com/Mchlwnk/pdf_numerator/releases)

Program do automatycznego numerowania stron w plikach PDF. Działa w całości lokalnie:
uruchamia mały serwer na `127.0.0.1` i otwiera interfejs w przeglądarce. Żaden plik nie
opuszcza komputera.

Kod na licencji MIT, całość (z PyMuPDF) na AGPL-3.0 — szczegóły w [LICENSING.md](LICENSING.md).

## Co robi

- numeruje wszystkie strony dokumentu (albo wszystkie poza pierwszymi _N_),
- **zakresy stron** w zapisie jak w drukarce: `1-10,15,20-`,
- **podgląd na żywo** - miniaturka strony z naniesionym numerem, pole z dokładnym tekstem
  (`Strona iv z xii`) oraz powiększona próbka samego napisu (czcionka, kolor, krycie),
- **tryb folderu** - numeruje wszystkie PDF-y w katalogu (opcjonalnie z podfolderami),
  jedne ustawienia dla wszystkich plików, lista z postępem „plik po pliku",
- **wstawianie i zastępowanie stron** - dołóż jeden lub kilka PDF-ów w wybrane miejsce
  głównego dokumentu albo zastąp nimi wybrane strony; numerację wyniku możesz włączyć
  lub wyłączyć,
- **style cyfr** - arabskie, rzymskie (`i, ii, III`) i litery (`a, b`), także **osobna
  numeracja dodatku** (np. treść 1–20, dodatek i–v),
- **maskowanie starego numeru** - biały prostokąt w miejscu nowego numeru,
- **numeracja naprzemienna** - na stronach parzystych numer przechodzi na przeciwną stronę,
- **kolor, krycie i tło** pod numerem,
- **presety** - ustawienia są pamiętane między uruchomieniami,
- zapisuje **kopię** obok oryginału jako `nazwa_numerowany.pdf` — oryginał zostaje nietknięty,
- przy kolejnych uruchomieniach dokłada `_2`, `_3`, ... zamiast nadpisywać,
- obsługuje polskie znaki, strony obrócone (90/180/270°), strony przycięte (CropBox),
- zachowuje metadane dokumentu i nie rekompresuje obrazów.

## Szybki start (ze źródeł)

```powershell
python -m pip install pymupdf
python launcher.py
```

Program otworzy przeglądarkę z interfejsem. Zamknięcie: przycisk **Zamknij** w prawym
górnym rogu strony.

Numerowanie bez interfejsu (np. przeciągnięcie pliku na `launcher.py`):

```powershell
python launcher.py "C:\dokumenty\umowa.pdf"
python launcher.py "raport.pdf" --template "Strona {n} z {total}" --skip 2 --margin 15
python launcher.py "raport.pdf" --pages "2-10,15-" --start 5 --font-size 9
python launcher.py "raport.pdf" --style roman --appendix-from 12 --appendix-style ROMAN
python launcher.py "raport.pdf" --mask --mask-width 16 --mask-height 6
python launcher.py "raport.pdf" --position bottom-right --mirror
python launcher.py --folder "C:\dokumenty\umowy" --recursive --template "{n} / {total}"
python launcher.py "raport.pdf" --quiet   # bez okien, tylko kod wyjścia
```

## Interfejs

Dwa tryby pracy (przełącznik u góry):

- **Jeden plik** — wybór z dysku lub przeciągnięcie. Wynik zapisywany jest obok oryginału,
  a plik przeciągnięty (bez znanej ścieżki) trafia do folderu **Pobrane**.
- **Cały folder** — systemowe okno wyboru katalogu (albo ręcznie wpisana ścieżka).
  Jeden zestaw ustawień obowiązuje wszystkie pliki; po prawej widać listę plików
  ze statusem (✓ gotowe / ✗ błąd) i postęp „3 / 12 · nazwa.pdf". Opcja „uwzględnij
  podfoldery" podpowiada, gdy w podfolderach są jeszcze pliki PDF. Kopie powstają
  obok oryginałów (kolejne uruchomienie dodaje `_2`, `_3`...), pliki `*_numerowany`
  są pomijane, a błąd jednego pliku nie przerywa reszty.
- **Wstaw / zastąp strony** — przeciągasz dokument główny (albo klikasz i wybierasz),
  a potem jeden lub kilka PDF-ów. **Dla każdego pliku osobno** wybierasz, czy ma być
  wstawiony po wskazanej stronie, czy zastąpić zakres stron — numery odnoszą się do
  oryginalnego dokumentu. Checkbox „numeruj strony po złożeniu" decyduje, czy wynik
  dostanie numery: z numeracją powstaje `nazwa_numerowany.pdf`, bez niej
  `nazwa_zlozony.pdf`. Oryginał zostaje nietknięty.

Uruchomienie nowej wersji programu **zamyka poprzednią kopię** (jeśli jeszcze działała),
więc zawsze otwiera się aktualna wersja. Numer wersji widać w tytule karty przeglądarki
i w stopce strony.

Opcje: pozycja numeru (siatka 3×3), numeracja naprzemienna, format (`{n}`, `{n} / {total}`,
`Strona {n} z {total}`), styl cyfr, dodatek od wskazanej strony, zakresy stron,
pominięcie pierwszych stron, pierwszy numer, rozmiar czcionki, margines, kolor, krycie,
tło pod numerem, maskowanie starego numeru, końcówka nazwy pliku.

## Pobieranie gotowego programu

Gotowe wydania są na [stronie Releases](https://github.com/Mchlwnk/pdf_numerator/releases).

1. Pobierz `PDFNumerator.exe` (ok. 30 MB, bez instalacji i bez Pythona).
2. Uruchom plik — otworzy się interfejs w przeglądarce.
3. Po skończonej pracy kliknij **Zamknij** w prawym górnym rogu strony.

Weryfikacja pliku (PowerShell):

```powershell
Get-FileHash .\PDFNumerator.exe -Algorithm SHA256
```

Suma kontrolna jest podana w opisie wydania (dla 0.5.2:
`AEE4576C627C645F2B98E2595559D28DB840073BCC3B90EE9783D2C2B0D28DCB`).

## Budowanie pliku EXE

```powershell
python -m pip install pyinstaller
.\build.ps1
```

Wynik: `dist\PDFNumerator.exe` (~30 MB, jeden plik, bez instalacji i bez Pythona u odbiorcy).
Uruchomienie bez argumentów otwiera interfejs; przeciągnięcie PDF na ikonę numeruje go
od razu i pokazuje podsumowanie.

## Struktura projektu

```
numerator/
  core.py      # numerowanie (PyMuPDF), plan numeracji, podgląd, zapis atomowy
  assemble.py  # wstawianie i zastępowanie stron (składanie dokumentu)
  options.py   # NumberOptions, zakresy stron, style cyfr, walidacja i szablony
  paths.py     # nazwy plików wynikowych, ochrona oryginału
  batch.py     # numerowanie całego folderu + raport
  fonts.py     # czcionki numeru (bazowa PDF + DejaVu Sans dla diakrytyków)
  server.py    # lokalny serwer HTTP na stdlib (bez Flaska), staging plików
  dialogs.py   # natywne okna Windows w wątku Tk
  instance.py  # jedna instancja programu (zamykanie poprzedniej kopii)
  app.py       # tryb UI, tryb wsadowy, tryb folderu
  web/index.html
hooks/
  hook-pymupdf.py  # wycina z paczki EXE modele ONNX i nagłówki (173 MB -> 30 MB)
LICENSES/
  AGPL-3.0.txt     # licencja PyMuPDF (całość)
  DejaVu-Fonts.txt # licencja osadzonej czcionki
tests/
  test_core.py     # rdzeń: pozycje, obroty, zakresy, style, dodatek, maska, podgląd, składanie
  test_server.py   # API: token, staging, podgląd, folder, składanie, pobieranie
  test_dialogs.py  # okna podsumowania i błędów w trybie "przeciągnij na EXE"
  test_instance.py # zamykanie poprzedniej kopii programu
build.ps1          # buduje dist\PDFNumerator.exe
release.ps1        # wydanie na GitHubie + source.zip
LICENSE            # licencja MIT dla kodu
```

Testy:

```powershell
python tests\test_core.py
python tests\test_server.py
python tests\test_dialogs.py
python tests\test_instance.py
```

## Bezpieczeństwo

- serwer słucha wyłącznie na `127.0.0.1`,
- każde żądanie API wymaga losowego tokenu generowanego przy starcie (token jest w adresie
  strony, więc obca witryna nie może wywołać API),
- żądania z obcym nagłówkiem `Origin` są odrzucane,
- pliki przesłane przez przeglądarkę trafiają do katalogu tymczasowego sesji; pobrać można
  tylko pliki z tego katalogu, a cały katalog jest usuwany przy zamknięciu programu.

## Ograniczenia

- PDF zabezpieczony hasłem — program zgłasza błąd i prosi o usunięcie zabezpieczenia.
- Dokumenty PDF/A i tagowane: dodana warstwa tekstowa może naruszyć zgodność z PDF/A.
- Maskowanie zakrywa **obraz** starego numeru; tekst pozostaje w treści PDF (jest tylko
  niewidoczny), więc wyszukiwanie może go jeszcze znaleźć.
- Niepodpisany plik EXE może przy pierwszym uruchomieniu wywołać ostrzeżenie SmartScreen.

## Logi

`%LOCALAPPDATA%\PDFNumerator\logs\pdf-numerator.log` (rotacja: 3 × 1 MB).

## Rozwiązywanie problemów

- **Program jest blokowany na komputerze służbowym** — skontaktuj się z działem IT.
- **Okno z błędem po przeciągnięciu pliku na EXE** — zajrzyj do logu
  `%LOCALAPPDATA%\PDFNumerator\logs\pdf-numerator.log`; program zapisuje tam pełny ślad błędu.
- **Numer wygląda jak puste prostokąty** — użyj aktualnej wersji (od 0.4.2 program nie
  przycina czcionek dokumentu, co powodowało ten efekt).
- **Brak numeru na niektórych stronach** — sprawdź „Zakresy stron", „Pomiń pierwsze strony"
  i „Dodatek od strony"; pole pod podglądem pokazuje dokładnie, co trafi na stronę.

## Plan rozwoju

- własne presety nazwane (np. „umowy", „raporty") zamiast jednego zestawu ustawień,
- podgląd kilku stron naraz (siatka miniatur),
- numeracja sekcji z wieloma dodatkami (Aneks A, B, ...).
