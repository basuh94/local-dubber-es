$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

# Built in its own venv on purpose: the runtime .venv holds a pinned torch/Chatterbox
# stack that took real effort to validate, and a build tool has no business touching it.
$BuildPy = Join-Path $Root ".venv-build\Scripts\python.exe"
if (-not (Test-Path $BuildPy)) {
    Write-Host "Creando el entorno de compilacion (.venv-build)..." -ForegroundColor Cyan
    & py -3.11 -m venv .venv-build
    & $BuildPy -m pip install --upgrade pip | Out-Null
    & $BuildPy -m pip install pyinstaller | Out-Null
}

Write-Host "Compilando 'YouTube Dubber.exe'..." -ForegroundColor Cyan
& $BuildPy -m PyInstaller `
    --onefile `
    --console `
    --name "YouTube Dubber" `
    --distpath $Root `
    --workpath (Join-Path $Root "work\pyinstaller") `
    --specpath (Join-Path $Root "work") `
    --noconfirm `
    (Join-Path $Root "scripts\launcher.py")

$Exe = Join-Path $Root "YouTube Dubber.exe"
if (-not (Test-Path $Exe)) { throw "La compilacion no produjo $Exe" }
$KB = [math]::Round((Get-Item $Exe).Length / 1KB)
Write-Host "Listo: $Exe ($KB KB)" -ForegroundColor Green
Write-Host "Haz doble clic en el .exe para abrir el panel."
