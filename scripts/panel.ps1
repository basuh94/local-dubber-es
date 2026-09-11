$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "No existe .venv. Ejecuta primero: .\scripts\setup_windows.ps1"
}

# The panel shells out to Ollama for translation; starting it here saves a confusing
# failure four stages into a dub.
try {
    Invoke-WebRequest "http://127.0.0.1:11434/api/version" -UseBasicParsing -TimeoutSec 3 | Out-Null
    Write-Host "Ollama: en marcha." -ForegroundColor Green
} catch {
    Write-Host "Ollama no responde; arrancandolo..." -ForegroundColor Yellow
    $exe = (Get-Command ollama -ErrorAction SilentlyContinue).Source
    if (-not $exe) { $exe = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" }
    if (-not (Test-Path $exe)) { throw "No encuentro ollama.exe. Instalalo o arrancalo a mano." }
    Start-Process $exe -ArgumentList "serve" -WindowStyle Hidden
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Milliseconds 500
        try { Invoke-WebRequest "http://127.0.0.1:11434/api/version" -UseBasicParsing -TimeoutSec 2 | Out-Null; break } catch {}
    }
}

Write-Host "Panel: http://127.0.0.1:8765  (Ctrl+C para pararlo)" -ForegroundColor Cyan
$env:PYTHONIOENCODING = "utf-8"
& $Python -m ytdubber.cli web @args
