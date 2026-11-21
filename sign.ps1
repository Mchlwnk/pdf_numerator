# Podpisuje PDFNumerator.exe podpisem Authenticode (Windows).
#
# Trzy warianty:
#   1) certyfikat z pliku .pfx        -> .\sign.ps1 -Pfx cert.pfx -PfxPassword "..."
#   2) certyfikat z magazynu Windows  -> .\sign.ps1 -Thumbprint ABC123...
#      (tak działa m.in. Certum SimplySign i inne usługi z kluczem w chmurze)
#   3) certyfikat testowy (self-signed) -> .\sign.ps1 -SelfSigned
#
# Wartości można też podać przez zmienne środowiskowe:
#   PDFN_SIGN_PFX, PDFN_SIGN_PASSWORD, PDFN_SIGN_THUMBPRINT
#
# Podpis NIE daje uprawnień administratora i nie omija polityk firmy
# (AppLocker / WDAC / Defender). Usuwa ostrzeżenie "Nieznany wydawca"
# i pozwala sprawdzić, kto wydał plik oraz czy nikt go nie zmienił.

param(
    [string]$Exe = "dist\PDFNumerator.exe",
    [string]$Pfx = $env:PDFN_SIGN_PFX,
    [string]$PfxPassword = $env:PDFN_SIGN_PASSWORD,
    [string]$Thumbprint = $env:PDFN_SIGN_THUMBPRINT,
    [switch]$SelfSigned,
    [string]$TimestampServer = "http://timestamp.digicert.com",
    [string]$Description = "PDF Numerator - numerowanie stron PDF",
    [string]$Url = "https://github.com/Mchlwnk/pdf_numerator",
    [switch]$VerifyOnly
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if (-not (Test-Path $Exe)) { throw "Nie znaleziono pliku $Exe - najpierw uruchom build.ps1" }
$exePath = (Resolve-Path $Exe).Path

function Show-Signature([string]$path) {
    $sig = Get-AuthenticodeSignature -FilePath $path
    Write-Host ""
    Write-Host "Status podpisu:  $($sig.Status) $($sig.StatusMessage)" -ForegroundColor Cyan
    if ($sig.SignerCertificate) {
        Write-Host "Wydawca:         $($sig.SignerCertificate.Subject)"
        Write-Host "Wystawca:        $($sig.SignerCertificate.Issuer)"
        Write-Host "Odcisk (SHA1):   $($sig.SignerCertificate.Thumbprint)"
        Write-Host "Ważny do:        $($sig.SignerCertificate.NotAfter)"
    } else {
        Write-Host "Plik nie jest podpisany." -ForegroundColor Yellow
    }
    if ($sig.TimeStamperCertificate) {
        Write-Host "Znacznik czasu:  $($sig.TimeStamperCertificate.Subject)"
    }
    return $sig
}

if ($VerifyOnly) {
    $signature = Show-Signature $exePath
    exit ($(if ($signature.Status -eq "Valid") { 0 } else { 1 }))
}

# -- wybór certyfikatu --------------------------------------------------------
$certificate = $null
$importedThumbprint = $null

if ($SelfSigned) {
    $subject = "CN=PDF Numerator (test), O=PDF Numerator"
    $certificate = Get-ChildItem Cert:\CurrentUser\My |
        Where-Object { $_.Subject -eq $subject -and $_.HasPrivateKey } |
        Select-Object -First 1
    if (-not $certificate) {
        Write-Host "Tworzę testowy certyfikat w magazynie użytkownika..." -ForegroundColor Yellow
        $certificate = New-SelfSignedCertificate `
            -Type CodeSigningCert `
            -Subject $subject `
            -CertStoreLocation Cert:\CurrentUser\My `
            -NotAfter (Get-Date).AddYears(3)
    }
    Write-Host "UWAGA: certyfikat testowy nie jest zaufany na innych komputerach." -ForegroundColor Yellow
    Write-Host "       Ostrzeżenie SmartScreen pozostanie, dopóki certyfikat nie trafi" -ForegroundColor Yellow
    Write-Host "       do zaufanych wydawców (wymaga administratora)." -ForegroundColor Yellow
}
elseif ($Pfx) {
    if (-not (Test-Path $Pfx)) { throw "Nie znaleziono pliku certyfikatu: $Pfx" }
    if ($PfxPassword) {
        $secure = ConvertTo-SecureString $PfxPassword -AsPlainText -Force
    } else {
        $secure = New-Object System.Security.SecureString
    }
    Write-Host "Importuję certyfikat z $Pfx ..."
    $imported = Import-PfxCertificate -FilePath ((Resolve-Path $Pfx).Path) `
        -CertStoreLocation Cert:\CurrentUser\My -Password $secure
    $importedThumbprint = $imported.Thumbprint
    $certificate = Get-Item "Cert:\CurrentUser\My\$importedThumbprint"
}
elseif ($Thumbprint) {
    $certificate = Get-ChildItem Cert:\CurrentUser\My, Cert:\LocalMachine\My -ErrorAction SilentlyContinue |
        Where-Object { $_.Thumbprint -eq $Thumbprint } |
        Select-Object -First 1
    if (-not $certificate) {
        throw "Nie znalazłem certyfikatu o odcisku $Thumbprint w magazynie użytkownika ani komputera."
    }
}
else {
    Write-Host "Nie wybrano certyfikatu." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Przykłady:"
    Write-Host "  .\sign.ps1 -Pfx cert.pfx -PfxPassword \"haslo\""
    Write-Host "  .\sign.ps1 -Thumbprint 0123456789ABCDEF..."
    Write-Host "  .\sign.ps1 -SelfSigned          # tylko testy"
    Write-Host "  .\sign.ps1 -VerifyOnly          # sprawdzenie podpisu"
    exit 1
}

if (-not $certificate.HasPrivateKey) {
    throw "Certyfikat nie ma klucza prywatnego - nie da się nim podpisać."
}

# -- podpisywanie -------------------------------------------------------------
Write-Host "Podpisuję $exePath ..."
$result = Set-AuthenticodeSignature -FilePath $exePath -Certificate $certificate `
    -TimestampServer $TimestampServer -HashAlgorithm SHA256 -IncludeChain All

if ($importedThumbprint) {
    Remove-Item "Cert:\CurrentUser\My\$importedThumbprint" -Force -ErrorAction SilentlyContinue
}

$signature = Show-Signature $exePath
$hash = (Get-FileHash $exePath -Algorithm SHA256).Hash
Write-Host "SHA256 pliku:    $hash"
Write-Host ""

if ($signature.Status -eq "Valid") {
    Write-Host "Gotowe - podpis jest ważny i zaufany." -ForegroundColor Green
    exit 0
}
if ($SelfSigned) {
    Write-Host "Podpis dodany, ale certyfikat jest testowy (Status: $($signature.Status))." -ForegroundColor Yellow
    Write-Host "Do dystrybucji użyj certyfikatu z zaufanego urzędu (CA)." -ForegroundColor Yellow
    exit 0
}
Write-Host "Podpis nie został zweryfikowany jako zaufany: $($result.StatusMessage)" -ForegroundColor Yellow
exit 1
