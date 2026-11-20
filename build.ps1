# Buduje jednoplikowy PDFNumerator.exe (bez konsoli).
# Wymaga: python -m pip install pymupdf pyinstaller

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$python = (Get-Command python).Source
& $python -m PyInstaller `
    --noconfirm --clean --onefile --noconsole `
    --name PDFNumerator `
    --additional-hooks-dir hooks `
    --add-data "numerator/web;numerator/web" `
    --add-data "numerator/fonts;numerator/fonts" `
    --hidden-import tkinter `
    --exclude-module pymupdf.layout `
    --exclude-module cv2 `
    --exclude-module onnxruntime `
    --exclude-module scipy `
    --exclude-module numpy `
    --exclude-module pandas `
    --exclude-module matplotlib `
    --exclude-module PIL `
    launcher.py

if ($LASTEXITCODE -ne 0) { throw "PyInstaller zakończył się błędem." }

$exe = Join-Path $PSScriptRoot "dist\PDFNumerator.exe"
if (-not (Test-Path $exe)) { throw "Nie znaleziono $exe" }

$sizeMb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host ""
Write-Host "Gotowe: $exe ($sizeMb MB)" -ForegroundColor Green
