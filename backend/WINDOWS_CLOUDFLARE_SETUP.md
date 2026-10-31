# EWMI on your Windows PC with Cloudflare HTTPS Tunnel

This is the local-PC setup. Your computer must be powered on, connected to the internet, and running both the API and tunnel for TradingView alerts, MT5 reads, Gemini briefings and scheduled reports to work.

## 1. Install prerequisites
- Install 64-bit Python 3.11 or newer.
- Install the official Exness MT5 and Deriv MT5 terminals if you want account monitoring.
- Download the Windows 64-bit `cloudflared` executable from https://developers.cloudflare.com/tunnel/downloads/, rename it `cloudflared.exe`, and place it in this `backend` folder.
- Open each broker's own MT5 terminal and sign in there. Never put broker passwords in EWMI's `.env`.

## 2. Configure the backend
Open PowerShell in this folder and run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\start-local-backend.ps1
```

The first run creates `.venv`, installs dependencies and copies `.env.example` to `.env`. It then stops so you can configure the private file.

Generate two different secrets:

```powershell
py -c "import secrets; print(secrets.token_urlsafe(40))"
py -c "import secrets; print(secrets.token_urlsafe(40))"
```

Edit `.env`:
- Set `EWMI_API_TOKEN` to the first generated value.
- Set `EWMI_WEBHOOK_SECRET` to the second generated value.
- Add `GEMINI_API_KEY` for Google Gemini.
- Add SMTP values only if you want email reports.
- Configure `EWMI_BROKER_PROFILES_JSON` only after confirming actual terminal paths and symbol names. Use separate MT5 terminal installations/instances for simultaneous Exness and Deriv monitoring.

Save `.env`. Run `start-local-backend.ps1` again. Keep this PowerShell window open. Test locally at `http://127.0.0.1:8000/docs`; the protected endpoints require the bearer token.

## 3. Start the HTTPS tunnel
Open a second PowerShell window in this folder and run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\start-cloudflare-quick-tunnel.ps1
```

Cloudflare prints a URL similar to `https://random-words.trycloudflare.com`. Copy the HTTPS origin only, without a trailing slash. This Quick Tunnel is temporary and the URL changes after a restart. Keep the tunnel window open.

## 4. Connect the dashboard
Open https://emawright.github.io/ew-market-intelligence/ and go to **Connections**:
- Backend HTTPS URL: paste the `https://....trycloudflare.com` URL.
- API token: paste the value of `EWMI_API_TOKEN`.
- Select **Test connection**.

The browser sends the token in an Authorization header. The dashboard keeps it in memory for that browser session; do not share the token or publish screenshots containing it.

## 5. Connect TradingView
In the EWMI Pine indicator settings, set its private webhook secret to the exact `EWMI_WEBHOOK_SECRET` value. Create a TradingView alert:
- Condition: EWMI indicator → **Any alert() function call**.
- Webhook URL: `https://YOUR-TRY-CLOUDFLARE-URL/webhooks/tradingview`.
- The Pine alert body contains the secret field; do not put the secret in a public GitHub file or send it to anyone.

After the alert fires, check the EWMI Sessions page. It is emitted at the first chart bar's close, not the exact second of the session open.

## 6. Verify
- Local API docs: `http://127.0.0.1:8000/docs`.
- Dashboard: Connections → Test connection.
- Dashboard: Sessions → refresh events after an alert arrives.
- Reports: check schedule status; test email only after SMTP and Gemini are configured.

## Security and availability
- The tunnel exposes the API hostname publicly. API endpoints require the private bearer token; the TradingView webhook requires its separate secret. Do not disable either check.
- Do not use a public Quick Tunnel as a permanent production endpoint. Cloudflare says Quick Tunnels are for development/testing, have no uptime guarantee, and their hostname changes on restart. Use a named Cloudflare Tunnel with a domain on Cloudflare for a stable hostname.
- Do not expose MT5 terminal ports or Windows Remote Desktop through this tunnel.
- The PC must remain awake and online. Windows sleep, internet loss, closing either window, or rebooting stops the local service unless you configure Windows startup services.
- Keep `.env`, MT5 credentials, tunnel tokens and API keys out of GitHub. The repository's `.gitignore` must exclude `.env` and `.venv`.
