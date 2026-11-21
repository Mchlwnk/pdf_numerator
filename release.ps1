# Publikuje wydanie na GitHubie: buduje EXE, opcjonalnie podpisuje, liczy SHA-256,
# dołącza źródła (wymóg AGPL) i tworzy Release.
#
# Wymaga jednorazowego logowania:
#   gh auth login
#
# Użycie:
#   .\release.ps1                        # wersja z numerator\__init__.py
#   .\release.ps1 -Version 0.4.5
#   .\release.ps1 -SkipBuild             # użyj istniejącego dist\PDFNumerator.exe
#   .\release.ps1 -Sign                  # podpisz przed publikacją (sign.ps1)
#   .\release.ps1 -Sign -SignThumbprint ABC...   # wskaż certyfikat

param(
    [string]$Version = "",
    [switch]$SkipBuild,
    [switch]$Sign,
    [string]$SignThumbprint = $env:PDFN_SIGN_THUMBPRINT,
    [string]$SignPfx = $env:PDFN_SIGN_PFX,
    [string]$SignPfxPassword = $env:PDFN_SIGN_PASSWORD
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

if ($Sign) {
    $signArgs = @("-Exe", $exe)
    if ($SignPfx) { $signArgs += @("-Pfx", $SignPfx) }
    if ($SignPfxPassword) { $signArgs += @("-PfxPassword", $SignPfxPassword) }
    if ($SignThumbprint) { $signArgs += @("-Thumbprint", $SignThumbprint) }
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "sign.ps1") @signArgs
    if ($LASTEXITCODE -ne 0) { throw "Podpisywanie nie powiodło się." }
}

$hash = (Get-FileHash $exe -Algorithm SHA256).Hash
$sizeMb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host "Wersja: $Version  ($sizeMb MB)" -ForegroundColor Cyan
Write-Host "SHA256: $hash" -ForegroundColor Cyan

# Źródła do wydania (AGPL: odbiorca musi mieć dostęp do kodu).
$sourceZip = Join-Path $PSScriptRoot "dist\source-$tag.zip"
$dirty = git status --porcelain
if ($dirty) {
    Write-Host "UWAGA: w katalogu są niezacommitowane zmiany - źródła pochodzą z HEAD." -ForegroundColor Yellow
}
git archive --format=zip -o $sourceZip HEAD
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $sourceZip)) {
    throw "Nie udało się utworzyć archiwum źródeł."
}
Write-Host "Źródła: $sourceZip" -ForegroundColor Cyan

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

# gh pisze komunikaty na stderr, a PowerShell 5.1 traktuje je jak błędy przy EAP=Stop.
$ErrorActionPreference = "Continue"

& gh auth status *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Nie jesteś zalogowany. Uruchom najpierw: gh auth login" -ForegroundColor Yellow
    exit 1
}

& gh release view $tag *> $null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Wydanie $tag już istnieje - podmieniam pliki." -ForegroundColor Yellow
    & gh release upload $tag $exe $sourceZip --clobber
} else {
    & gh release create $tag $exe $sourceZip --title "PDF Numerator $Version" --notes-file $notesPath
}
if ($LASTEXITCODE -ne 0) { throw "Publikacja wydania nie powiodła się." }

Write-Host ""
Write-Host "Gotowe: https://github.com/Mchlwnk/pdf_numerator/releases/tag/$tag" -ForegroundColor Green
