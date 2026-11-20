# Lokalny hook: w pakiecie PyMuPDF 2.x znajdują się modele ONNX do analizy układu
# stron (~50 MB) oraz nagłówki deweloperskie. Nasze narzędzie ich nie używa, więc
# odfiltrowujemy je z paczki, żeby EXE był znacznie mniejszy.

from PyInstaller.utils.hooks import collect_data_files

_SKIP = ("layout", "mupdf-devel", ".onnx")

datas = [
    entry
    for entry in collect_data_files("pymupdf")
    if not any(part in entry[0].replace("\\", "/").lower() for part in _SKIP)
]
