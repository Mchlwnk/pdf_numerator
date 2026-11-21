# PDF Numerator

[![Release](https://img.shields.io/github/v/release/Mchlwnk/pdf_numerator?display_name=tag)](https://github.com/Mchlwnk/pdf_numerator/releases)
[![Licencja](https://img.shields.io/badge/licencja-MIT%20%2B%20AGPL--3.0-blue)](LICENSING.md)
[![Platforma](https://img.shields.io/badge/platforma-Windows%2010%2F11-lightgrey)](https://github.com/Mchlwnk/pdf_numerator/releases)

Program do automatycznego numerowania stron w plikach PDF. Działa w całości lokalnie:
uruchamia mały serwer na `127.0.0.1` i otwiera interfejs w przeglądarce. Żaden plik nie
opuszcza komputera.

**Wolne oprogramowanie** — kod na licencji MIT, całość (z PyMuPDF) na AGPL-3.0.
Szczegóły: [LICENSING.md](LICENSING.md).

## Co robi

- numeruje wszystkie strony dokumentu (albo wszystkie poza pierwszymi _N_),
- **zakresy stron** w zapisie jak w drukarce: `1-10,15,20-`,
- **podgląd na żywo** - miniaturka strony z naniesionym numerem, pole z dokładnym tekstem (`Strona iv z xii`) oraz powiększona próbka samego napisu (czcionka, kolor, krycie),
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

Gotowe wydania są na [stronie Releases](https://github.com/Mchlwnk/pdf_numerator/releases) —
publicznie, bez logowania. Każde wydanie zawiera:

- `PDFNumerator.exe` (ok. 30 MB, bez instalacji i bez Pythona),
- `source-<wersja>.zip` — komplet źródeł z tego samego commita.

1. Pobierz `PDFNumerator.exe`.
2. Uruchom plik — otworzy się interfejs w przeglądarce.
3. Windows może pokazać ostrzeżenie SmartScreen („Nieznany wydawca") przy pierwszym
   uruchomieniu — to normalne dla niepodpisanych programów; wybierz „Więcej informacji"
   → „Uruchom mimo to".
4. Po skończonej pracy kliknij **Zamknij** w prawym górnym rogu strony.

Weryfikacja pliku (PowerShell):

```powershell
Get-FileHash .\PDFNumerator.exe -Algorithm SHA256
```

Suma kontrolna jest podana w opisie każdego wydania (dla 0.4.4:
`8DEBF8A43849E7C7D801C808B7D632FFCCD1122B14B57C656C86B73EB97E7B3F`).

Nowe wydanie publikujesz jedną komendą (wymaga `gh auth login`):

```powershell
.\release.ps1
```

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
LICENSES/
  DejaVu-Fonts.txt # licencja osadzonej czcionki
tests/
  test_core.py     # rdzeń: pozycje, obroty, zakresy, style, dodatek, maska, podgląd
  test_server.py   # API: token, staging, podgląd, folder, pobieranie
  test_dialogs.py  # okna podsumowania i błędów w trybie "przeciągnij na EXE"
build.ps1          # buduje dist\PDFNumerator.exe
sign.ps1           # podpis Authenticode (-Pfx / -Thumbprint / -VerifyOnly)
release.ps1        # wydanie na GitHubie + source.zip (AGPL)
LICENSE            # licencja MIT dla kodu
THIRD-PARTY-NOTICES.md
```

Testy:

```powershell
python tests\test_core.py
python tests\test_server.py
python tests\test_dialogs.py
```

## Rozwiązywanie problemów
- **Okno z błędem po przeciągnięciu pliku na EXE** — zajrzyj do logu
  `%LOCALAPPDATA%\PDFNumerator\logs\pdf-numerator.log`; program zapisuje tam pełny ślad błędu.
- **Numer wygląda jak puste prostokąty** — użyj aktualnej wersji (od 0.4.2 program nie
  przycina czcionek dokumentu, co powodowało ten efekt).
- **Brak numeru na niektórych stronach** — sprawdź „Zakresy stron", „Pomiń pierwsze strony"
  i „Dodatek od strony"; pole pod podglądem pokazuje dokładnie, co trafi na stronę.

## Podpis cyfrowy i użycie w firmie

### Co daje podpis, a czego nie daje

**Daje:** nazwę wydawcy zamiast „Nieznany wydawca", możliwość sprawdzenia, że pliku nikt
nie zmienił (hash w podpisie) oraz mniej ostrzeżeń SmartScreen.

**Nie daje:** uprawnień administratora, obejścia firmowych polityk (AppLocker / WDAC /
Defender Application Control) ani gwarancji, że antywirus nie zgłosi fałszywego alarmu.

Program **nie potrzebuje administratora** ani instalacji: to jeden plik EXE, który zapisuje
wyniki obok PDF-a i logi w `%LOCALAPPDATA%`. Nie instaluje usług, sterowników ani nie
wymaga UAC.

### Opcje podpisu (ceny orientacyjne, 2026)

| Opcja | Koszt | Kto może | Uwagi |
|---|---|---|---|
| **Azure Artifact Signing** (dawniej Trusted Signing) | ~9,99 USD/mies. | organizacje (US/CA/UE), indywidualni w podglądzie | klucz w chmurze Microsoftu, bez tokena, dobre relacje ze SmartScreen |
| **Certum Cloud Code Signing** | ~100–180 USD/rok | osoby fizyczne i firmy | klucz w chmurze (SimplySign), bez tokena USB |
| OV Code Signing (inni wystawcy) | 99–300 USD/rok | firmy, osoby | wymaga weryfikacji tożsamości; często token/HSM |
| EV Code Signing | 300–900 USD/rok | firmy | natychmiastowa reputacja, token sprzętowy |
| **SignPath Foundation** | bezpłatnie | projekty open source (publiczne repo) | certyfikat OV Fundacji |
| Self-signed | bezpłatnie | testy / firma wewnętrzna | zaufany tylko tam, gdzie administrator wgra certyfikat |

**Dla programu używanego przez jedną osobę w pracy** najprostsze i sensowne warianty to:
1. **bez podpisu** + zgoda działu IT na uruchomienie pliku (najczęściej wystarcza),
2. **Certum Cloud** lub **Azure Artifact Signing** — jeśli ma zniknąć „Nieznany wydawca",
3. **self-signed + certyfikat wgrany przez IT** — gdy firma ma własny magazyn zaufanych
   wydawców (bez kosztów, ale wymaga administratora po stronie IT).

### Podpisywanie w tym projekcie

```powershell
# certyfikat z pliku .pfx (np. wyeksportowany z tokena/cloud)
.\sign.ps1 -Pfx cert.pfx -PfxPassword "haslo"

# certyfikat z magazynu Windows (tak działa Certum SimplySign i inne chmury)
.\sign.ps1 -Thumbprint 0123456789ABCDEF...

# sprawdzenie podpisu
.\sign.ps1 -VerifyOnly

# podpisanie i publikacja w jednym kroku
.\release.ps1 -Sign
```

Parametry można też podać przez zmienne środowiskowe: `PDFN_SIGN_PFX`,
`PDFN_SIGN_PASSWORD`, `PDFN_SIGN_THUMBPRINT`. Skrypt dodaje znacznik czasu (DigiCert),
więc podpis pozostaje ważny po wygaśnięciu certyfikatu.

### Gdy w firmie nie ma uprawnień administratora

1. Program działa bez instalacji — wystarczy skopiować EXE i uruchomić.
2. Jeśli polityka blokuje nieznane pliki, **dział IT** może dopuścić aplikację po
   SHA-256 lub ścieżce. Przekaż im: plik EXE, sumę SHA-256 z opisu wydania, link do
   repozytorium i informację, że program nie łączy się z internetem.
3. SmartScreen: „Więcej informacji" → „Uruchom mimo to" (o ile polityka pozwala).
4. Antywirus: pojedyncze fałszywe alarmy dla PyInstaller-a można zgłosić do Microsoftu
   (<https://www.microsoft.com/en-us/wdsi/filesubmission>) lub użyć wersji `onedir`.

### Licencje i zgodność

- Kod programu: **MIT** (`LICENSE`); całość z PyMuPDF: **AGPL-3.0** (`LICENSES/AGPL-3.0.txt`).
- **Repozytorium jest publiczne**, więc dostęp do źródeł jest stały; dodatkowo każde
  wydanie zawiera `source-<wersja>.zip` (wymóg AGPL przy przekazywaniu programu dalej).
- Szczegóły i droga do „czystego MIT": `LICENSING.md`.
- Czcionka DejaVu: licencja permissywna, tekst w `LICENSES/DejaVu-Fonts.txt`.
- Program nie wysyła danych na zewnątrz (tylko `127.0.0.1`), co ułatwia zgodność z RODO
  w firmie.

## Licencja

- **Kod autorski — MIT**: używaj, zmieniaj, publikuj, także komercyjnie.
- **Całość z PyMuPDF — AGPL-3.0**: przy udostępnianiu programu daj dostęp do źródeł
  (publiczne repo + `source-*.zip` w wydaniach).

Pełne wyjaśnienie i alternatywa (czyste MIT po zamianie PyMuPDF na pypdf + reportlab):
[LICENSING.md](LICENSING.md).

## Współpraca

Repozytorium jest publiczne — zgłoszenia i propozycje zmian przez
[Issues](https://github.com/Mchlwnk/pdf_numerator/issues). Projekt jest darmowy;
nie ma gwarancji i nie zbiera danych.

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
- **darmowe podpisywanie przez [SignPath Foundation](https://signpath.org/)** — projekt
  open source kwalifikuje się do certyfikatu OV Fundacji (bez kosztów),
- podpis komercyjny (Azure Artifact Signing / Certum) dla pełnej reputacji SmartScreen.
