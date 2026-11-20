# Publikuje wydanie na GitHubie: buduje EXE, liczy SHA-256 i tworzy Release.
#
# Wymaga jednorazowego logowania:
#   gh auth login
#
# Użycie:
#   .\release.ps1              # wersja z numerator\__init__.py
#   .\release.ps1 -Version 0.4.1
#   .\release.ps1 -SkipBuild   # użyj istniejącego dist\PDFNumerator.exe

param(
    [string]$Version = "",
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if (-not $Version) {
    $match = Select-String -Path "numerator\__init__.py" -Pattern '__version__ = "([^"]+)"'
    if (-not $match) { throw "Nie znalazłem wersji w numerator\__init__.py" }
    $Version = $match.Matches[0].Groups[1].Value
}
$tag = "v$Version"
$exe = Join-Path $PSScriptRoot "dist\PDFNumerator.exe"

if (-not $SkipBuild) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "build.ps1")
    if ($LASTEXITCODE -ne 0) { throw "Budowanie nie powiodło się." }
}
if (-not (Test-Path $exe)) { throw "Brak pliku $exe - uruchom build.ps1" }

$hash = (Get-FileHash $exe -Algorithm SHA256).Hash
$sizeMb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host "Wersja: $Version  ($sizeMb MB)" -ForegroundColor Cyan
Write-Host "SHA256: $hash" -ForegroundColor Cyan

$notes = Get-Content "RELEASE_NOTES.md" -Raw
$notes = $notes.Replace("{{VERSION}}", $Version).Replace("{{SHA256}}", $hash).Replace("{{SIZE}}", "$sizeMb")
$notesPath = Join-Path $env:TEMP "pdfnumerator-notes-$tag.md"
$utf8 = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText($notesPath, $notes, $utf8)

$gh = Get-Command gh -ErrorAction SilentlyContinue
if (-not $gh) {
    Write-Host ""
    Write-Host "Brak GitHub CLI (gh). Zainstaluj: winget install --id GitHub.cli -e" -ForegroundColor Yellow
    Write-Host "Notatki wydania zapisane w: $notesPath" -ForegroundColor Yellow
    Write-Host "Release utworzysz ręcznie na https://github.com/Mchlwnk/pdf_numerator/releases/new" -ForegroundColor Yellow
    exit 1
}

& gh auth status *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Nie jesteś zalogowany. Uruchom najpierw: gh auth login" -ForegroundColor Yellow
    exit 1
}

& gh release view $tag *> $null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Wydanie $tag już istnieje - podmieniam plik." -ForegroundColor Yellow
    & gh release upload $tag $exe --clobber
} else {
    & gh release create $tag $exe --title "PDF Numerator $Version" --notes-file $notesPath
}
if ($LASTEXITCODE -ne 0) { throw "Publikacja wydania nie powiodła się." }

Write-Host ""
Write-Host "Gotowe: https://github.com/Mchlwnk/pdf_numerator/releases/tag/$tag" -ForegroundColor Green
