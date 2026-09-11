$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "== YouTube Dubber Windows setup ==" -ForegroundColor Cyan

function Ensure-WingetPackage($Id, $Command) {
    if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) {
        Write-Host "Installing $Id..."
        winget install --id $Id --exact --accept-source-agreements --accept-package-agreements
    } else {
        Write-Host "$Command already available."
    }
}

Ensure-WingetPackage "Git.Git" "git"
Ensure-WingetPackage "Gyan.FFmpeg" "ffmpeg"
Ensure-WingetPackage "DenoLand.Deno" "deno"
Ensure-WingetPackage "7zip.7zip" "7z"
Ensure-WingetPackage "Ollama.Ollama" "ollama"

# Refresh PATH after winget installs so this same shell can usually continue.
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    winget install --id Python.Python.3.11 --exact --accept-source-agreements --accept-package-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
}
try { $pyv = & py -3.11 --version } catch { throw "Python 3.11 is required. Install it and rerun this script." }
Write-Host $pyv

if (-not (Test-Path ".venv")) { & py -3.11 -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Chatterbox 0.1.7 pins torch 2.6.0. Force the matching NVIDIA CUDA 12.6 wheels.
& .\.venv\Scripts\python.exe -m pip install --force-reinstall `
  torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 `
  --index-url https://download.pytorch.org/whl/cu126

# CTranslate2/faster-whisper on Windows needs cuBLAS CUDA 12 + cuDNN 9 DLLs.
$CudaDir = Join-Path $Root "vendor\cuda12"
New-Item -ItemType Directory -Force $CudaDir | Out-Null
if (-not (Test-Path (Join-Path $CudaDir "cublas64_12.dll"))) {
    # winget installs 7-Zip without putting it on PATH, so resolve the exe explicitly.
    $SevenZip = (Get-Command 7z -ErrorAction SilentlyContinue).Source
    if (-not $SevenZip) {
        $SevenZip = @("$env:ProgramFiles-Zipz.exe", "${env:ProgramFiles(x86)}-Zipz.exe") |
                    Where-Object { Test-Path $_ } | Select-Object -First 1
    }
    if (-not $SevenZip) { throw "7-Zip not found. Install it (winget install 7zip.7zip) and rerun this script." }

    $Archive = Join-Path $Root "vendor\cuda12-libs.7z"
    $Tmp = Join-Path $Root "vendor\cuda12-extract"
    $Url = "https://github.com/Purfview/whisper-standalone-win/releases/download/libs/cuBLAS.and.cuDNN_CUDA12_win_v3.7z"

    # An interrupted download leaves a truncated archive that extracts to nothing, which
    # later surfaces as the confusing "cublas64_12.dll is not found" at transcription time.
    # Verify the archive and re-download once before trusting it.
    $NeedsDownload = $true
    if (Test-Path $Archive) {
        & $SevenZip t $Archive | Out-Null
        if ($LASTEXITCODE -eq 0) { $NeedsDownload = $false }
        else { Write-Warning "Existing cuda12-libs.7z is incomplete; downloading again." }
    }
    if ($NeedsDownload) {
        Write-Host "Downloading CUDA 12 cuBLAS/cuDNN runtime for faster-whisper (~810 MB)..."
        Remove-Item $Archive -Force -ErrorAction SilentlyContinue
        $ProgressPreference = "SilentlyContinue"   # Invoke-WebRequest is very slow with the progress bar
        Invoke-WebRequest -Uri $Url -OutFile $Archive
        & $SevenZip t $Archive | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Downloaded $Archive is corrupt. Delete it and rerun this script." }
    }

    Remove-Item $Tmp -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force $Tmp | Out-Null
    & $SevenZip x $Archive "-o$Tmp" -y | Out-Null
    Get-ChildItem $Tmp -Recurse -Filter *.dll | Copy-Item -Destination $CudaDir -Force
    Remove-Item $Tmp -Recurse -Force
    if (-not (Test-Path (Join-Path $CudaDir "cublas64_12.dll"))) {
        throw "cublas64_12.dll was not extracted into $CudaDir. faster-whisper will not find CUDA."
    }
}

Write-Host "Pulling recommended translator (qwen3:8b)..." -ForegroundColor Cyan
try { & ollama pull qwen3:8b } catch { Write-Warning "Could not pull qwen3:8b. Start Ollama and run: ollama pull qwen3:8b" }

Write-Host "Installing project editable..."
& .\.venv\Scripts\python.exe -m pip install -e . --no-deps

Write-Host "Running unit tests..."
& .\.venv\Scripts\python.exe -m pytest -q

Write-Host "Setup complete. Open a NEW PowerShell, then:" -ForegroundColor Green
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "  ytdubber doctor"
Write-Host "  ytdubber dub 'https://www.youtube.com/watch?v=...' --profile balanced"
