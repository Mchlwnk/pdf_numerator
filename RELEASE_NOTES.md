# PDF Numerator {{VERSION}}

Program do numerowania stron w plikach PDF. Działa w całości lokalnie — **żaden plik nie
opuszcza komputera**. Jeden plik EXE, bez instalacji i bez Pythona.

## Instalacja

1. Pobierz `PDFNumerator.exe` ({{SIZE}} MB) z sekcji **Assets** poniżej.
2. Uruchom plik dwukrotnym kliknięciem — otworzy się interfejs w przeglądarce.
3. Po skończonej pracy kliknij **Zamknij** w prawym górnym rogu strony.

Windows może pokazać ostrzeżenie SmartScreen („Nieznany wydawca") przy pierwszym
uruchomieniu — to normalne dla niepodpisanych programów. Wybierz **Więcej informacji**
→ **Uruchom mimo to**.

## Weryfikacja pliku

```powershell
Get-FileHash .\PDFNumerator.exe -Algorithm SHA256
```

Oczekiwana suma:

```
{{SHA256}}
```

## Co nowego w {{VERSION}}

- porządki w repozytorium: usunięte wcześniejsze wydania, uproszczony README,
- program bez zmian funkcjonalnych względem 0.4.4.

## Najważniejsze funkcje

- numerowanie wszystkich stron lub wybranych zakresów (`1-10,15,20-`),
- podgląd na żywo z naniesionym numerem i nawigacją po stronach,
- style cyfr: arabskie, rzymskie (`i, ii, III`), litery; osobna numeracja dodatku,
- maskowanie istniejącej numeracji, kolor, krycie, tło pod numerem,
- pozycja 3×3, margines, rozmiar czcionki, własny szablon (`{n}`, `{n} / {total}`),
- tryb folderu (opcjonalnie z podfolderami) z raportem,
- zapis kopii obok oryginału (`nazwa_numerowany.pdf`), oryginał zawsze nietknięty,
- presety ustawień pamiętane między uruchomieniami,
- obsługa polskich znaków, stron obróconych (90/180/270°) i przyciętych (CropBox).

## Wymagania

- Windows 10/11 (64-bit),
- przeglądarka internetowa (domyślna w systemie).

## Uwagi

- PDF zabezpieczony hasłem: program poprosi o usunięcie zabezpieczenia.
- PDF/A i dokumenty tagowane: dodana warstwa tekstowa może naruszyć zgodność z PDF/A.
- Maskowanie zakrywa obraz starego numeru; tekst pozostaje w treści (jest niewidoczny).

Pełny opis i tryb CLI: [README](https://github.com/Mchlwnk/pdf_numerator#readme).
