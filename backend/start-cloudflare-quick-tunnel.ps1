$ErrorActionPreference = "Stop"
$cloudflared = Join-Path $PSScriptRoot "cloudflared.exe"
if (-not (Test-Path $cloudflared)) {
    throw "Download the Windows 64-bit cloudflared executable from https://developers.cloudflare.com/tunnel/downloads/, rename it cloudflared.exe and place it in this backend folder."
}
Write-Host "Starting temporary HTTPS tunnel to local EWMI API..." -ForegroundColor Cyan
Write-Host "Keep this window open. The trycloudflare.com URL changes when restarted." -ForegroundColor Yellow
& $cloudflared tunnel --url http://127.0.0.1:8000
