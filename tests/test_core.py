"""Testy rdzenia numerowania - uruchamiane bez pytest: python tests/test_core.py"""

from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from numerator import (  # noqa: E402
    NumberOptions,
    NumberingError,
    OptionsError,
    PathError,
    build_plan,
    number_pdf,
    parse_hex_color,
    render_label_sample,
    render_preview,
    to_alpha,
    to_roman,
)
from numerator.batch import number_folder  # noqa: E402


def make_pdf(path: Path, pages: int = 3, width: float = 300, height: float = 200,
             rotation: int = 0) -> Path:
    doc = pymupdf.open()
    for index in range(pages):
        page = doc.new_page(width=width, height=height)
        page.insert_text((20, 30), "Strona testowa", fontsize=10)
        if rotation:
            page.set_rotation(rotation)
    doc.save(path)
    doc.close()
    return path


def snapshot(path: Path) -> list[bytes]:
    """Piksele stron przed numerowaniem (do wykrycia wyłącznie dodanych znaków)."""
    shots = []
    with pymupdf.open(path) as doc:
        for page in doc:
            shots.append(bytes(page.get_pixmap(dpi=72).samples))
    return shots


def added_ink(page: pymupdf.Page, reference: bytes | None):
    """Bbox pikseli ciemniejszych niż tło, których nie było przed numerowaniem."""
    pix = page.get_pixmap(dpi=72)
    width, height, channels = pix.width, pix.height, pix.n
    samples, stride = pix.samples, pix.stride
    min_x = min_y = 10**9
    max_x = max_y = -1
    for y in range(height):
        for x in range(width):
            offset = y * stride + x * channels
            if min(samples[offset:offset + 3]) >= 200:
                continue
            if reference is not None and min(reference[offset:offset + 3]) < 200:
                continue
            min_x, max_x = min(min_x, x), max(max_x, x)
            min_y, max_y = min(min_y, y), max(max_y, y)
    return min_x, min_y, max_x, max_y


def _count_pixels(page: pymupdf.Page, predicate, dpi: int = 72) -> int:
    """Liczy piksele strony spełniające warunek koloru (RGB 0-255)."""
    pix = page.get_pixmap(dpi=dpi)
    width, height, channels = pix.width, pix.height, pix.n
    samples, stride = pix.samples, pix.stride
    count = 0
    for y in range(height):
        for x in range(width):
            offset = y * stride + x * channels
            if predicate(samples[offset], samples[offset + 1], samples[offset + 2]):
                count += 1
    return count


def _region_bytes(page: pymupdf.Page, rect: tuple[float, float, float, float],
                  dpi: int = 72) -> bytes:
    """Piksele wycinka strony (do porównania „przed/po" bez obszaru numeru)."""
    pix = page.get_pixmap(dpi=dpi, clip=pymupdf.Rect(*rect))
    return bytes(pix.samples)


def _png_count(data: bytes, predicate) -> int:
    """Liczy piksele w obrazie PNG spełniające warunek koloru."""
    doc = pymupdf.open("png", data)
    try:
        pix = doc[0].get_pixmap()
        samples, stride, channels = pix.samples, pix.stride, pix.n
        count = 0
        for y in range(pix.height):
            for x in range(pix.width):
                offset = y * stride + x * channels
                if predicate(samples[offset], samples[offset + 1], samples[offset + 2]):
                    count += 1
        return count
    finally:
        doc.close()


def labels_in_band(page: pymupdf.Page, low: float = 0.65, high: float = 1.0) -> str:
    """Tekst linii leżących w dolnej (albo wskazanej) części strony."""
    height = page.rect.height
    found = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            y = (line["bbox"][1] + line["bbox"][3]) / 2
            if height * low <= y <= height * high:
                text = "".join(span["text"] for span in line["spans"]).strip()
                if text:
                    found.append(text)
    return " | ".join(found)


failures = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global failures
    if condition:
        print(f"  OK   {name}")
    else:
        failures += 1
        print(f"  FAIL {name} {detail}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pdfnum-test-") as raw_tmp:
        tmp = Path(raw_tmp)

        print("[1] domyślne numerowanie 3 stron")
        src = make_pdf(tmp / "prosty.pdf")
        before = snapshot(src)
        digest = hashlib.sha256(src.read_bytes()).hexdigest()
        result = number_pdf(src)
        check("nazwa wyniku", result.output_path.name == "prosty_numerowany.pdf",
              result.output_path.name)
        check("oryginał nietknięty", hashlib.sha256(src.read_bytes()).hexdigest() == digest)
        with pymupdf.open(result.output_path) as doc:
            check("liczba stron", doc.page_count == 3, str(doc.page_count))
            for index, page in enumerate(doc):
                bbox = added_ink(page, before[index])
                width, height = page.rect.width, page.rect.height
                center_x = (bbox[0] + bbox[2]) / 2
                check(f"strona {index + 1}: numer na dole", bbox[1] > height / 2,
                      f"bbox={bbox}")
                check(f"strona {index + 1}: wyśrodkowany", abs(center_x - width / 2) <= 3,
                      f"center={center_x:.1f} vs {width / 2:.1f}")
                check(f"strona {index + 1}: margines dolny",
                      abs(height - bbox[3] - 28) <= 3, f"dystans={height - bbox[3]}")
                check(f"strona {index + 1}: właściwy numer",
                      labels_in_band(page) == str(index + 1), labels_in_band(page))

        print("[2] pominięcie pierwszej strony i start od 5")
        result = number_pdf(src, NumberOptions(skip_first=1, start_at=5, template="{n} / {total}"))
        with pymupdf.open(result.output_path) as doc:
            check("strona 1 bez numeru", labels_in_band(doc[0]) == "", labels_in_band(doc[0]))
            check("numeracja 5-6",
                  [labels_in_band(p) for p in doc] == ["", "5 / 6", "6 / 6"],
                  str([labels_in_band(p) for p in doc]))
        check("wynik: pierwszy numer", result.first_number == 5)
        check("wynik: ostatni numer", result.last_number == 6)
        check("wynik: numerowanych stron", result.pages_numbered == 2)

        print("[3] strony obrócone 90/180/270")
        for rotation in (90, 180, 270):
            rot_src = make_pdf(tmp / f"obrot-{rotation}.pdf", pages=1, rotation=rotation)
            rot_before = snapshot(rot_src)
            rot_result = number_pdf(
                rot_src,
                NumberOptions(margin=20, font_size=12, template="{n} / {total}"),
            )
            with pymupdf.open(rot_result.output_path) as doc:
                page = doc[0]
                bbox = added_ink(page, rot_before[0])
                width, height = page.rect.width, page.rect.height
                check(f"rot {rotation}: numer w kadrze",
                      0 <= bbox[0] and bbox[2] < width and bbox[3] < height,
                      f"bbox={bbox} page=({width},{height})")
                check(f"rot {rotation}: na dole", bbox[3] > height * 0.6, f"bbox={bbox}")
                check(f"rot {rotation}: poziomy", (bbox[2] - bbox[0]) > (bbox[3] - bbox[1]),
                      f"bbox={bbox}")

        print("[4] polskie znaki w szablonie")
        result = number_pdf(src, NumberOptions(template="Strona {n} z {total} — żąćęłńóśź"))
        with pymupdf.open(result.output_path) as doc:
            text = doc[0].get_text()
            check("diakrytyki zachowane", "Strona 1 z 3 — żąćęłńóśź" in text, repr(text))
        check("font nie awaryjny", result.font_fallback is False)

        print("[5] kolizja nazw")
        fresh = make_pdf(tmp / "kolizja.pdf", pages=1)
        check("pierwsza kopia", number_pdf(fresh).output_path.name == "kolizja_numerowany.pdf")
        check("druga kopia", number_pdf(fresh).output_path.name == "kolizja_numerowany_2.pdf")
        check("trzecia kopia", number_pdf(fresh).output_path.name == "kolizja_numerowany_3.pdf")

        print("[6] błędy")
        try:
            number_pdf(src, NumberOptions(skip_first=10))
            check("pominięcie większe niż strony", False, "brak wyjątku")
        except NumberingError:
            check("pominięcie większe niż strony", True)
        nie_pdf = tmp / "notatka.txt"
        nie_pdf.write_text("to nie jest pdf")
        try:
            number_pdf(nie_pdf)
            check("odrzucenie nie-PDF", False, "brak wyjątku")
        except PathError:
            check("odrzucenie nie-PDF", True)

        print("[7] mała strona - zmniejszenie czcionki")
        tiny = make_pdf(tmp / "maly.pdf", pages=1, width=90, height=50)
        result = number_pdf(tiny, NumberOptions(font_size=40, template="Strona {n} z {total}"))
        check("oznaczono zmniejszenie", result.font_shrunk is True)
        with pymupdf.open(result.output_path) as doc:
            page = doc[0]
            rects = page.search_for("Strona")
            check("tekst mieści się na stronie",
                  bool(rects) and rects[0].x1 <= page.rect.width + 0.5, str(rects))

        print("[8] nazwa docelowa")
        target = tmp / "wynik" / "moj.pdf"
        target.parent.mkdir()
        check("zapis do wskazanego pliku",
              number_pdf(src, NumberOptions(), destination=target).output_path == target)
        try:
            number_pdf(src, NumberOptions(), destination=src)
            check("blokada nadpisania źródła", False, "brak wyjątku")
        except PathError:
            check("blokada nadpisania źródła", True)

        print("[9] zakresy stron")
        four = make_pdf(tmp / "zakresy.pdf", pages=4)
        result = number_pdf(four, NumberOptions(pages="2-3", start_at=10))
        with pymupdf.open(result.output_path) as doc:
            labels = [labels_in_band(p) for p in doc]
            check("numer tylko na 2 i 3", labels == ["", "10", "11", ""], str(labels))
        check("numerowanych stron", result.pages_numbered == 2, str(result.pages_numbered))
        check("ostatni numer", result.last_number == 11, str(result.last_number))

        result = number_pdf(four, NumberOptions(pages="3-", start_at=1))
        with pymupdf.open(result.output_path) as doc:
            check("zakres otwarty 3-", [labels_in_band(p) for p in doc] == ["", "", "1", "2"],
                  str([labels_in_band(p) for p in doc]))

        result = number_pdf(four, NumberOptions(pages="2-3", skip_first=2))
        with pymupdf.open(result.output_path) as doc:
            check("zakres + pominięcie", [labels_in_band(p) for p in doc] == ["", "", "1", ""],
                  str([labels_in_band(p) for p in doc]))

        for bad in ("0-3", "5-2", "abc", "1-x"):
            try:
                NumberOptions(pages=bad)
                check(f"odrzucenie zakresu {bad!r}", False, "brak wyjątku")
            except OptionsError:
                check(f"odrzucenie zakresu {bad!r}", True)

        try:
            number_pdf(four, NumberOptions(pages="10-12"))
            check("pusty wybór stron", False, "brak wyjątku")
        except NumberingError:
            check("pusty wybór stron", True)

        print("[10] kolor, krycie i tło")
        dark = pymupdf.open()
        dark_page = dark.new_page(width=200, height=100)
        dark_page.draw_rect(dark_page.rect, fill=(0.1, 0.1, 0.1), color=None)
        dark.save(tmp / "ciemna.pdf")
        dark.close()

        result = number_pdf(tmp / "ciemna.pdf", NumberOptions(color=(1, 0, 0), font_size=16, margin=10))
        with pymupdf.open(result.output_path) as doc:
            red = _count_pixels(doc[0], lambda r, g, b: r > 140 and g < 110 and b < 110)
            check("czerwony numer widoczny", red > 10, f"czerwonych pikseli: {red}")

        result = number_pdf(tmp / "ciemna.pdf", NumberOptions(background=True, font_size=16,
                                                              margin=10, template="{n}"))
        with pymupdf.open(result.output_path) as doc:
            white = _count_pixels(doc[0], lambda r, g, b: r > 240 and g > 240 and b > 240)
            check("białe tło pod numerem", white > 200, f"białych pikseli: {white}")

        result = number_pdf(tmp / "ciemna.pdf", NumberOptions(background=False, font_size=16,
                                                              margin=10, template="{n}"))
        with pymupdf.open(result.output_path) as doc:
            white = _count_pixels(doc[0], lambda r, g, b: r > 240 and g > 240 and b > 240)
            check("bez tła brak białego prostokąta", white < 20, f"białych pikseli: {white}")

        result = number_pdf(tmp / "ciemna.pdf", NumberOptions(opacity=0.25, color=(1, 1, 1),
                                                              font_size=16, margin=10))
        with pymupdf.open(result.output_path) as doc:
            faint = _count_pixels(doc[0], lambda r, g, b: 60 < r < 150 and abs(r - g) < 12)
            check("krycie 25% daje szary numer", faint > 10, f"pikseli: {faint}")

        print("[11] podgląd")
        preview = render_preview(four, NumberOptions(pages="2-3", start_at=7), max_width=200)
        check("PNG", preview.data[:8] == b"\x89PNG\r\n\x1a\n", repr(preview.data[:8]))
        check("pierwsza numerowana strona", preview.page_number == 2, str(preview.page_number))
        check("strona jest numerowana", preview.is_numbered is True)
        check("liczba stron dokumentu", preview.page_count == 4, str(preview.page_count))
        check("liczba numerowanych", preview.numbered_pages == 2, str(preview.numbered_pages))
        preview2 = render_preview(four, NumberOptions(pages="2-3"), page_number=1)
        check("pominięta strona bez numeru", preview2.is_numbered is False)
        preview3 = render_preview(four, NumberOptions(), page_number=4)
        check("wskazana strona", preview3.page_number == 4, str(preview3.page_number))
        check("szerokość obrazu ograniczona", len(preview.data) > 100)

        styled_preview = render_preview(
            four, NumberOptions(template="Strona {n} z {total}", appendix_from=3), page_number=3
        )
        check("etykieta podgladu z dodatkiem", styled_preview.label == "Strona i z ii",
              repr(styled_preview.label))
        skipped_preview = render_preview(four, NumberOptions(skip_first=2), page_number=1)
        check("brak etykiety na pominiętej stronie", skipped_preview.label is None,
              repr(skipped_preview.label))

        try:
            render_preview(four, NumberOptions(), page_number=99)
            check("nieistniejąca strona podglądu", False, "brak wyjątku")
        except NumberingError:
            check("nieistniejąca strona podglądu", True)

        print("[12] kolory w zapisie hex")
        check("hex 6 znaków", parse_hex_color("#c0392b")[0] > 0.7, str(parse_hex_color("#c0392b")))
        check("hex skrócony", parse_hex_color("f00") == (1.0, 0.0, 0.0), str(parse_hex_color("f00")))
        check("hex bez kratki", parse_hex_color("000000") == (0.0, 0.0, 0.0))
        try:
            parse_hex_color("czerwony")
            check("odrzucenie złego koloru", False, "brak wyjątku")
        except OptionsError:
            check("odrzucenie złego koloru", True)

        print("[13] cyfry rzymskie i dodatek")
        check("rzymskie małe", to_roman(4) == "iv" and to_roman(1994) == "mcmxciv", to_roman(1994))
        check("litery", to_alpha(1) == "a" and to_alpha(27) == "aa", to_alpha(27))

        plan = build_plan(4, NumberOptions(appendix_from=3, appendix_style="roman"))
        check("dodatek od strony 3",
              list(plan.labels.items()) == [(0, "1"), (1, "2"), (2, "i"), (3, "ii")],
              str(plan.labels))
        check("licznik dodatku", plan.appendix_count == 2, str(plan.appendix_count))

        result = number_pdf(four, NumberOptions(appendix_from=3, appendix_style="ROMAN"))
        with pymupdf.open(result.output_path) as doc:
            check("rzymskie w PDF", [labels_in_band(p) for p in doc] == ["1", "2", "I", "II"],
                  str([labels_in_band(p) for p in doc]))
        check("wynik: stron dodatku", result.appendix_pages == 2, str(result.appendix_pages))

        result = number_pdf(four, NumberOptions(style="roman", start_at=5))
        with pymupdf.open(result.output_path) as doc:
            check("rzymska numeracja całości",
                  [labels_in_band(p) for p in doc] == ["v", "vi", "vii", "viii"],
                  str([labels_in_band(p) for p in doc]))

        result = number_pdf(four, NumberOptions(template="{n} / {total}", appendix_from=3,
                                                appendix_style="alpha"))
        with pymupdf.open(result.output_path) as doc:
            check("szablon z dodatkiem literowym",
                  [labels_in_band(p) for p in doc] == ["1 / 2", "2 / 2", "a / b", "b / b"],
                  str([labels_in_band(p) for p in doc]))

        print("[14] maskowanie starej numeracji")
        old = pymupdf.open()
        old_page = old.new_page(width=300, height=200)
        old_page.insert_text((135, 175), "999", fontsize=12, color=(0, 0, 1))
        old.save(tmp / "stary-numer.pdf")
        old.close()

        with pymupdf.open(tmp / "stary-numer.pdf") as doc:
            blue_before = _count_pixels(doc[0], lambda r, g, b: b > 150 and r < 120 and g < 120)
        check("stary numer widoczny", blue_before > 5, f"niebieskich: {blue_before}")

        result = number_pdf(tmp / "stary-numer.pdf", NumberOptions(
            mask_existing=True, mask_width=60, mask_height=22, margin=20, font_size=12))
        with pymupdf.open(result.output_path) as doc:
            blue_after = _count_pixels(doc[0], lambda r, g, b: b > 150 and r < 120 and g < 120)
        check("stary numer zamalowany", blue_after == 0, f"niebieskich: {blue_after}")

        result = number_pdf(tmp / "stary-numer.pdf", NumberOptions(
            mask_existing=False, margin=20, font_size=12))
        with pymupdf.open(result.output_path) as doc:
            blue_keep = _count_pixels(doc[0], lambda r, g, b: b > 150 and r < 120 and g < 120)
        check("bez maski numer zostaje", blue_keep > 5, f"niebieskich: {blue_keep}")

        print("[15] numeracja naprzemienna")
        mirror_src = make_pdf(tmp / "lustro.pdf", pages=4, width=300, height=200)
        mirror_before = snapshot(mirror_src)
        result = number_pdf(mirror_src, NumberOptions(position="bottom-right", mirror=True, margin=20))
        with pymupdf.open(result.output_path) as doc:
            for index, page in enumerate(doc):
                bbox = added_ink(page, mirror_before[index])
                center = (bbox[0] + bbox[2]) / 2
                right = center > page.rect.width * 0.6
                left = center < page.rect.width * 0.4
                if index % 2 == 0:
                    check(f"strona {index + 1} (nieparzysta): prawa strona", right,
                          f"center={center:.1f}")
                else:
                    check(f"strona {index + 1} (parzysta): lewa strona", left,
                          f"center={center:.1f}")

        result = number_pdf(mirror_src, NumberOptions(position="bottom-center", mirror=True, margin=20))
        with pymupdf.open(result.output_path) as doc:
            centers = []
            for index, page in enumerate(doc):
                bbox = added_ink(page, mirror_before[index])
                centers.append((bbox[0] + bbox[2]) / 2)
            ok_center = all(abs(value - 150) <= 6 for value in centers)
        check("lustro nie rusza numeru wyśrodkowanego", ok_center, str(centers))

        print("[16] integralność czcionek oryginału")
        dejavu = Path("numerator") / "fonts" / "DejaVuSans.ttf"
        rich = pymupdf.open()
        rich_page = rich.new_page(width=400, height=300)
        rich_page.insert_text((40, 60), "Zażółć gęślą jaźń", fontsize=14,
                              fontname="DJ", fontfile=str(dejavu))
        rich_page.insert_text((40, 100), "Original text ABC 123", fontsize=12)
        rich.save(tmp / "bogaty.pdf")
        rich.close()

        with pymupdf.open(tmp / "bogaty.pdf") as doc:
            fonts_before = [entry[3] for entry in doc[0].get_fonts()]
            text_before = doc[0].get_text()
            pixels_before = _region_bytes(doc[0], (0, 0, 400, 200))
        check("oryginał ma osadzoną czcionkę", len(fonts_before) >= 2, str(fonts_before))

        result = number_pdf(tmp / "bogaty.pdf", NumberOptions(template="{n}"))
        with pymupdf.open(result.output_path) as doc:
            fonts_after = [entry[3] for entry in doc[0].get_fonts()]
            text_after = doc[0].get_text()
            pixels_after = _region_bytes(doc[0], (0, 0, 400, 200))
        check("czcionki oryginału bez zmian", fonts_after == fonts_before,
              f"{fonts_before} -> {fonts_after}")
        check("tekst oryginału bez zmian", text_after.startswith(text_before.strip()),
              repr(text_after[:80]))
        check("piksele oryginału bez zmian", pixels_before == pixels_after)

        result = number_pdf(tmp / "bogaty.pdf", NumberOptions(
            template="Strona {n} z {total} — żąćęłńóśź"))
        with pymupdf.open(result.output_path) as doc:
            text_pl = doc[0].get_text()
            fonts_pl = [entry[3] for entry in doc[0].get_fonts()]
        check("polski szablon zapisany", "Strona 1 z 1 — żąćęłńóśź" in text_pl, repr(text_pl[-60:]))
        check("czcionka Unicode tylko gdy potrzebna",
              any("DejaVu" in name for name in fonts_pl), str(fonts_pl))

        print("[17] probka napisu pod podglądem")
        sample = render_label_sample(
            four,
            NumberOptions(template="Strona {n} z {total}", appendix_from=3),
            page_number=3,
        )
        check("probka to PNG", sample.data[:8] == b"\x89PNG\r\n\x1a\n", repr(sample.data[:8]))
        check("etykieta probki", sample.label == "Strona i z ii", repr(sample.label))
        check("probka jest lekka", len(sample.data) < 80_000, str(len(sample.data)))
        check("probka ma ciemny tekst", _png_count(sample.data, lambda r, g, b: r < 60) > 50,
              "brak ciemnych pikseli")
        white_sample = render_label_sample(
            four, NumberOptions(color=(1.0, 1.0, 1.0), font_size=14), page_number=1
        )
        check("jasny napis na ciemnym tle",
              _png_count(white_sample.data,
                         lambda r, g, b: r > 200 and g > 200 and b > 200) > 20,
              "brak jasnych pikseli")

        try:
            render_label_sample(four, NumberOptions(skip_first=2), page_number=1)
            check("probka dla pominiętej strony", False, "brak wyjątku")
        except NumberingError:
            check("probka dla pominiętej strony", True)

        print("[18] numerowanie folderu: zdarzenia i odporność")
        batch_folder = tmp / "batch-events"
        batch_folder.mkdir()
        make_pdf(batch_folder / "a.pdf", pages=1)
        make_pdf(batch_folder / "b.pdf", pages=1)
        (batch_folder / "zly.pdf").write_bytes(b"%PDF-1.4\nzepsuty")
        events: list[dict] = []
        summary = number_folder(batch_folder, NumberOptions(), on_event=events.append)
        check("trzy pliki znalezione", summary.found == 3, str(summary.found))
        check("dwa ponumerowane", len(summary.done) == 2, str(summary.done))
        check("jeden błąd", len(summary.failed) == 1, str(summary.failed))
        check("błąd nie zatrzymuje pętli",
              sum(1 for event in events if event["type"] in ("ok", "error")) == 3,
              str(events))
        check("kolejność zdarzeń",
              [event["index"] for event in events if event["type"] == "start"] == [1, 2, 3],
              str([event["index"] for event in events if event["type"] == "start"]))
        check("zdarzenia niosą nazwę pliku",
              all(event.get("name") for event in events), str(events))

    print()
    if failures:
        print(f"NIEPOWODZENIA: {failures}")
        return 1
    print("Wszystkie testy przeszły.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
