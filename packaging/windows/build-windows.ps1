<#
  build-windows.ps1 - buduje wersje Windows Vibe Coding Assistant (Etap W2/W4).

  WAZNE: ten plik jest CELOWO w czystym ASCII (bez polskich znakow i emoji).
  Windows PowerShell 5.1 czyta .ps1 bez BOM jako ANSI i wielobajtowe znaki UTF-8
  rozbijaja parser (ParserError / MissingTypename). Nie dodawaj tu znakow spoza ASCII.

  Robi po kolei:
    1) instaluje zaleznosci (requirements + pyinstaller + pillow),
    2) generuje ikone .ico z src/assets/icon.png (make_ico.py),
    3) sklada aplikacje PyInstallerem (onedir -> dist\Vibe Coding Assistant\),
    4) buduje instalator Inno Setup -> dist\VibeCodingAssistant-Setup-<wersja>.exe.

  Uruchom NA Windows (PowerShell), z dowolnego katalogu:
    powershell -ExecutionPolicy Bypass -File packaging\windows\build-windows.ps1

  Wymaga: Python 3.12 na PATH oraz Inno Setup 6 (iscc.exe). .exe da sie zbudowac
  TYLKO na Windows.
#>
$ErrorActionPreference = "Stop"

# Korzen repo = dwa katalogi powyzej tego skryptu (packaging\windows).
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $Root
Write-Host "== Korzen repo: $Root =="

# 1) Wersja z JEDYNEGO zrodla prawdy (src/config.py).
$configText = Get-Content -Raw "src\config.py"
if ($configText -match 'APP_VERSION\s*=\s*"([^"]+)"') {
    $Version = $Matches[1]
} else {
    throw "Nie znaleziono APP_VERSION w src\config.py"
}
Write-Host "== Wersja aplikacji: $Version =="

# 2) Zaleznosci.
Write-Host "== Instaluje zaleznosci =="
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller pillow

# 3) Ikona .ico z .png (Windows wymaga .ico) - osobny skrypt python.
Write-Host "== Generuje src\assets\icon.ico =="
python packaging\windows\make_ico.py

# 4) Czyszcze poprzedni build i skladam aplikacje.
Write-Host "== PyInstaller (onedir) =="
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist")  { Remove-Item -Recurse -Force "dist" }
python -m PyInstaller --noconfirm --clean packaging\windows\ClaudeVoiceAssistant.spec

$AppDir = "dist\Vibe Coding Assistant"
$AppExe = Join-Path $AppDir "Vibe Coding Assistant.exe"
if (-not (Test-Path $AppExe)) {
    throw "Build nie powiodl sie - brak pliku: $AppExe"
}

# 5) Instalator Inno Setup. Szukamy iscc na PATH, potem w domyslnych lokalizacjach.
Write-Host "== Inno Setup (instalator) =="
$iscc = (Get-Command iscc.exe -ErrorAction SilentlyContinue).Source
if (-not $iscc) {
    $candidates = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe")
    foreach ($p in $candidates) {
        if (Test-Path $p) { $iscc = $p; break }
    }
}
if (-not $iscc) { throw "Nie znaleziono iscc.exe (Inno Setup 6). Zainstaluj: choco install innosetup" }

& $iscc "/DAppVersion=$Version" "packaging\windows\installer.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup zwrocil blad ($LASTEXITCODE)" }

$Setup = "dist\VibeCodingAssistant-Setup-$Version.exe"
if (-not (Test-Path $Setup)) { throw "Brak pliku instalatora: $Setup" }

Write-Host ""
Write-Host "[OK] GOTOWE:"
Write-Host "   Aplikacja (folder): $AppDir"
Write-Host "   Instalator:         $Setup"
