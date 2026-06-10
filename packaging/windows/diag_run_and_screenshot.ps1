<#
  diag_run_and_screenshot.ps1 - diagnostyka GUI na maszynie Windows (CI).

  WAZNE: plik celowo w czystym ASCII (PowerShell 5.1 czyta .ps1 bez BOM jako
  ANSI - znaki spoza ASCII rozbijaja parser). Nie dodawac polskich znakow.

  Uruchamia podany program (aplikacje z kodu albo spakowane .exe), czeka az
  okno wstanie, robi zrzut calego ekranu i zbiera logi diagnostyczne aplikacji
  (webterminal.log + log Chromium) do katalogu diag\ pod podanym prefiksem.

  Przyklad:
    powershell -File diag_run_and_screenshot.ps1 -Exe python -ArgList "src\main.py" -OutPrefix dev
#>
param(
    [Parameter(Mandatory=$true)][string]$Exe,
    [string]$ArgList = "",
    [Parameter(Mandatory=$true)][string]$OutPrefix,
    [int]$WaitSeconds = 35
)
$ErrorActionPreference = "Continue"
New-Item -ItemType Directory -Force -Path diag | Out-Null

# Czyste logi na te faze (kazda faza diagnozy zbiera wlasne).
$cfg = Join-Path $env:USERPROFILE ".claude-voice-assistant"
Remove-Item (Join-Path $cfg "webterminal.log") -ErrorAction SilentlyContinue
Remove-Item (Join-Path $cfg "webengine_chromium.log") -ErrorAction SilentlyContinue

$outLog = "diag\$OutPrefix-stdout.txt"
$errLog = "diag\$OutPrefix-stderr.txt"
Write-Host "== Start: $Exe $ArgList (czekam $WaitSeconds s) =="
if ($ArgList -ne "") {
    $p = Start-Process -FilePath $Exe -ArgumentList $ArgList -PassThru `
        -RedirectStandardOutput $outLog -RedirectStandardError $errLog
} else {
    $p = Start-Process -FilePath $Exe -PassThru `
        -RedirectStandardOutput $outLog -RedirectStandardError $errLog
}
Start-Sleep -Seconds $WaitSeconds

if ($p.HasExited) {
    Write-Host "UWAGA: proces zakonczyl sie przed zrzutem (kod: $($p.ExitCode))"
}

# Zrzut calego wirtualnego ekranu.
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$vs = [System.Windows.Forms.SystemInformation]::VirtualScreen
$bmp = New-Object System.Drawing.Bitmap($vs.Width, $vs.Height)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($vs.X, $vs.Y, 0, 0, $bmp.Size)
$shot = "diag\$OutPrefix-screenshot.png"
$bmp.Save($shot)
Write-Host "Zrzut ekranu: $shot"

# Sprzatanie procesow (aplikacja + procesy potomne QtWebEngine).
Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
Get-Process -ErrorAction SilentlyContinue | Where-Object {
    $_.ProcessName -like "*Claude*" -or $_.ProcessName -like "QtWebEngineProcess*"
} | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Zbierz logi aplikacji pod prefiksem fazy.
Copy-Item (Join-Path $cfg "webterminal.log") "diag\$OutPrefix-webterminal.log" -ErrorAction SilentlyContinue
Copy-Item (Join-Path $cfg "webengine_chromium.log") "diag\$OutPrefix-chromium.log" -ErrorAction SilentlyContinue

Write-Host "== Zawartosc diag\ =="
Get-ChildItem diag | Format-Table Name,Length -AutoSize
