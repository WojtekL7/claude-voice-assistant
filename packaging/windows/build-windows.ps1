<#
  build-windows.ps1 — buduje wersję Windows Claude Voice Assistant (Etap W2/W4).

  Robi po kolei:
    1) instaluje zależności (requirements + pyinstaller + pillow),
    2) generuje ikonę .ico z src/assets/icon.png,
    3) składa aplikację PyInstallerem (onedir -> dist\Claude Voice Assistant\),
    4) buduje instalator Inno Setup -> dist\ClaudeVoiceAssistant-Setup-<wersja>.exe.

  Uruchom NA Windows (PowerShell), z dowolnego katalogu:
    powershell -ExecutionPolicy Bypass -File packaging\windows\build-windows.ps1

  Wymaga: Python 3.12 na PATH oraz Inno Setup 6 (iscc.exe). W CI instalujemy je
  w workflow build-windows.yml. .exe da się zbudować TYLKO na Windows.
#>
$ErrorActionPreference = "Stop"

# Korzeń repo = dwa katalogi powyżej tego skryptu (packaging\windows).
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $Root
Write-Host "== Korzeń repo: $Root =="

# 1) Wersja z JEDYNEGO źródła prawdy (src/config.py).
$configText = Get-Content -Raw "src\config.py"
if ($configText -match 'APP_VERSION\s*=\s*["'']([^"'']+)["'']') {
    $Version = $Matches[1]
} else {
    throw "Nie znaleziono APP_VERSION w src\config.py"
}
Write-Host "== Wersja aplikacji: $Version =="

# 2) Zależności.
Write-Host "== Instaluję zależności =="
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller pillow

# 3) Ikona .ico z .png (Windows wymaga .ico).
Write-Host "== Generuję src\assets\icon.ico =="
python -c "from PIL import Image; Image.open('src/assets/icon.png').save('src/assets/icon.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"

# 4) Czyszczę poprzedni build i składam aplikację.
Write-Host "== PyInstaller (onedir) =="
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist")  { Remove-Item -Recurse -Force "dist" }
python -m PyInstaller --noconfirm --clean packaging\windows\ClaudeVoiceAssistant.spec

$AppDir = "dist\Claude Voice Assistant"
if (-not (Test-Path (Join-Path $AppDir "Claude Voice Assistant.exe"))) {
    throw "Build nie powiódł się — brak $AppDir\Claude Voice Assistant.exe"
}

# 5) Instalator Inno Setup. Szukamy iscc na PATH, potem w domyślnych lokalizacjach.
Write-Host "== Inno Setup (instalator) =="
$iscc = (Get-Command iscc.exe -ErrorAction SilentlyContinue).Source
if (-not $iscc) {
    foreach ($p in @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe")) {
        if (Test-Path $p) { $iscc = $p; break }
    }
}
if (-not $iscc) { throw "Nie znaleziono iscc.exe (Inno Setup 6). Zainstaluj: choco install innosetup" }

& $iscc "/DAppVersion=$Version" "packaging\windows\installer.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup zwrócił błąd ($LASTEXITCODE)" }

$Setup = "dist\ClaudeVoiceAssistant-Setup-$Version.exe"
if (-not (Test-Path $Setup)) { throw "Brak pliku instalatora: $Setup" }

Write-Host ""
Write-Host "✅ GOTOWE:"
Write-Host "   Aplikacja (folder): $AppDir"
Write-Host "   Instalator:         $Setup"
