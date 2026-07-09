$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
$env:PORT = "5001"
$env:OPUS_MT_MODEL_DIR = "scratch/models/opus-mt-en-mt"
$env:TRANSLATION_LOCAL_FILES_ONLY = "true"
Write-Host "Starting server on http://127.0.0.1:5001 - keep this window open." -ForegroundColor Cyan
.\.venv\Scripts\python.exe app.py 2>&1 | Tee-Object -FilePath ".\server-live.log"

