$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
.\.venv\Scripts\python.exe -m ytdubber.cli doctor
