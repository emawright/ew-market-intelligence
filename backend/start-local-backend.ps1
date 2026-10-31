$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "EWMI Windows backend setup" -ForegroundColor Cyan
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    py -3 -m venv .venv
}
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host ""
    Write-Host "Created backend\.env from .env.example." -ForegroundColor Yellow
    Write-Host "STOP: edit .env, set EWMI_API_TOKEN and EWMI_WEBHOOK_SECRET to different long random values, then run this script again." -ForegroundColor Yellow
    Write-Host "Generate values with: py -c \"import secrets; print(secrets.token_urlsafe(40))\""
    exit 0
}

$envText = Get-Content ".env" -Raw
if ($envText -match "replace-with-a-long-random-api-token|replace-with-a-different-long-random-webhook-secret") {
    throw "Replace the example API token and webhook secret in backend\.env before starting."
}
Write-Host "Starting EWMI API on http://127.0.0.1:8000" -ForegroundColor Green
& $python -m uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8000
