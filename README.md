# PDF Numerator

Program do automatycznego numerowania stron w plikach PDF. Działa w całości lokalnie:
uruchamia mały serwer na `127.0.0.1` i otwiera interfejs w przeglądarce. Żaden plik nie
opuszcza komputera.

## Co robi

- numeruje wszystkie strony dokumentu (albo wszystkie poza pierwszymi _N_),
- **zakresy stron** w zapisie jak w drukarce: `1-10,15,20-`,
- **podgląd na żywo** - miniaturka strony z naniesionym numerem, aktualizowana przy każdej zmianie ustawień,
- **tryb folderu** - numeruje wszystkie PDF-y w katalogu (opcjonalnie z podfolderami) i pokazuje raport,
- **style cyfr** - arabskie, rzymskie (`i, ii, III`) i litery (`a, b`), także **osobna numeracja dodatku** (np. treść 1–20, dodatek i–v),
- **maskowanie starego numeru** - biały prostokąt w miejscu nowego numeru (skany, dokumenty z wydrukowaną numeracją),
- **numeracja naprzemienna** - na stronach parzystych numer przechodzi na przeciwną stronę (klasyczny układ do druku dwustronnego),
- **kolor, krycie i tło** pod numerem (czytelność na skanach i grafikach),
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
python launcher.py "raport.pdf" --template "Strona {n} z {total}" --color "#c0392b" --background
python launcher.py "raport.pdf" --style roman --appendix-from 12 --appendix-style ROMAN
python launcher.py "raport.pdf" --mask --mask-width 16 --mask-height 6
python launcher.py "raport.pdf" --position bottom-right --mirror
python launcher.py --folder "C:\dokumenty\umowy" --recursive --template "{n} / {total}"
python launcher.py "raport.pdf" --quiet   # bez okien, tylko kod wyjścia (np. do harmonogramu zadań)
```

## Interfejs

Dwa tryby pracy (przełącznik u góry):

- **Jeden plik** — wybór z dysku lub przeciągnięcie. Wynik zapisywany jest obok oryginału,
  a plik przeciągnięty (bez znanej ścieżki) trafia do folderu **Pobrane**.
- **Cały folder** — systemowe okno wyboru katalogu (albo ręcznie wpisana ścieżka),
  opcja „uwzględnij podfoldery", podgląd pierwszego pliku i raport po zakończeniu.
  Pliki utworzone wcześniej przez program (końcówka `_numerowany`) są pomijane,
  a błąd jednego pliku nie przerywa reszty.

Opcje: pozycja numeru (siatka 3×3), numeracja naprzemienna, format (`{n}`, `{n} / {total}`,
`Strona {n} z {total}`), styl cyfr, dodatek od wskazanej strony, zakresy stron,
pominięcie pierwszych stron, pierwszy numer, rozmiar czcionki, margines, kolor, krycie,
tło pod numerem, maskowanie starego numeru, końcówka nazwy pliku. Ustawienia są pamiętane
w przeglądarce (localStorage) — „Przywróć domyślne" czyści je.

## Pobieranie gotowego programu (Release)

Wydania z plikiem `PDFNumerator.exe` i sumą kontrolną są na
[stronie Releases](https://github.com/Mchlwnk/pdf_numerator/releases).

1. Pobierz `PDFNumerator.exe` (ok. 30 MB, nie wymaga instalacji ani Pythona).
2. Uruchom plik — otworzy się interfejs w przeglądarce.
3. Windows może pokazać ostrzeżenie SmartScreen („Nieznany wydawca") przy pierwszym
   uruchomieniu — to normalne dla niepodpisanych programów; wybierz „Więcej informacji"
   → „Uruchom mimo to".
4. Po skończonej pracy kliknij **Zamknij** w prawym górnym rogu strony.

Weryfikacja pliku (PowerShell):

```powershell
Get-FileHash .\PDFNumerator.exe -Algorithm SHA256
```

Suma kontrolna jest podana w opisie każdego wydania.

## Budowanie pliku EXE

```powershell
python -m pip install pyinstaller
.\build.ps1
```

Wynik: `dist\PDFNumerator.exe` (~40 MB, jeden plik, bez instalacji i bez Pythona u odbiorcy).
Uruchomienie bez argumentów otwiera interfejs; przeciągnięcie PDF na ikonę numeruje go
od razu i pokazuje podsumowanie.

## Struktura projektu

```
numerator/
  core.py      # numerowanie (PyMuPDF), plan numeracji, podgląd, zapis atomowy
  options.py   # NumberOptions, zakresy stron, style cyfr, walidacja i szablony
  paths.py     # nazwy plików wynikowych, ochrona oryginału
  batch.py     # numerowanie całego folderu + raport
  fonts.py     # DejaVu Sans (polskie znaki) + awaryjne fonty systemowe
  server.py    # lokalny serwer HTTP na stdlib (bez Flaska), staging plików
  dialogs.py   # natywne okna Windows w wątku Tk
  app.py       # tryb UI, tryb wsadowy, tryb folderu
  web/index.html
hooks/
  hook-pymupdf.py  # wycina z paczki EXE modele ONNX i nagłówki (173 MB -> 30 MB)
tests/
  test_core.py     # rdzeń: pozycje, obroty, zakresy, style, dodatek, maska, podgląd
  test_server.py   # API: token, staging, podgląd, folder, pobieranie
```

Testy:

```powershell
python tests\test_core.py
python tests\test_server.py
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

## Plan rozwoju

- własne presety nazwane (np. „umowy", „raporty") zamiast jednego zestawu ustawień,
- podgląd kilku stron naraz (siatka miniatur),
- numeracja sekcji z wieloma dodatkami (Aneks A, B, ...),
- podpis cyfrowy EXE (usuwa ostrzeżenie SmartScreen).
