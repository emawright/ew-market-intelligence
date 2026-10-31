# EWMI private backend

FastAPI service for persistent TradingView session events, Google News headlines, Google Gemini market-context briefings and optional read-only MetaTrader 5 data for Exness and Deriv.

## Safety model
- No order placement, modification or closure endpoints exist.
- User chooses and enters entries, stop-loss, take-profit, lot size and execution.
- Broker credentials are entered only into the official MT5 terminal. They are never sent to this API.
- Use separate installed MT5 terminal instances and distinct terminal paths if you want to monitor Exness and Deriv at the same time. A single terminal instance has one active account session at a time.
- Do not expose this service directly to the public internet. Put it behind a private VPN/tunnel or a properly secured HTTPS deployment.

## Setup (Windows)
1. Install Python 3.11+ and both broker MT5 terminals if needed.
2. Open each official terminal and sign in normally. Verify the desired instruments appear in Market Watch.
3. Create and activate a virtual environment:
   `py -m venv .venv`
   `.venv\\Scripts\\Activate.ps1`
4. Install dependencies: `pip install -r requirements.txt`
5. Copy `.env.example` to `.env`. Generate different long random values for `EWMI_API_TOKEN` and `EWMI_WEBHOOK_SECRET`; add a Gemini API key from Google AI Studio if you want AI briefings.
6. Configure terminal paths and broker-specific symbol aliases in `EWMI_BROKER_PROFILES_JSON`. Common symbols are only examples: Exness/Deriv account suffixes and gold naming differ by server/account. Confirm each exact name in Market Watch.
7. Set environment variables from the private `.env` file and run:
   `uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8000`
8. Open `http://127.0.0.1:8000/docs`.

## API
- `GET /health` — protected service configuration health.
- `GET /broker/profiles` — configured Exness/Deriv profiles (no secrets).
- `GET /symbols?broker=Exness` — broker symbol mappings.
- `GET /candles/{market}/{timeframe}?broker=Exness&count=300` — read-only OHLC.
- `GET /analysis/structure/{market}/{timeframe}?broker=Exness` — confirmed swing / BOS / CHOCH candidates.
- `GET /account?broker=Exness` and `GET /positions?broker=Exness` — read-only snapshots.
- `POST /webhooks/tradingview` — authenticated Pine alert receiver (secret in JSON body).
- `GET /sessions/events` — stored TradingView events.
- `GET /news?q=EURUSD%20gold` — Google News RSS headlines.
- `POST /briefing` — Google Gemini summary grounded in retrieved headlines and optional supplied technical context.
- `GET /reports/events` — recent stored session events.

All protected endpoints use `Authorization: Bearer <EWMI_API_TOKEN>`. The webhook uses the separate `secret` field in the JSON body and `EWMI_WEBHOOK_SECRET`. Do not put secrets in public source code or commit real `.env` files.

## Google News and Gemini
Google News RSS is a best-effort feed, not a documented Google News API and has no service-level guarantee. Results can be incomplete, delayed, duplicated, or use Google redirect URLs. Each headline should be checked at its publisher before acting. Gemini summarizes supplied headlines; it is not a price feed, economic-calendar authority, or trade signal generator. Configure a separate trusted economic-calendar provider before treating event times as complete.

## TradingView alerts
Add `tradingview/EWMI_Daily_Bias_Sessions.pine` to a chart. Enter the same webhook secret in the indicator's secret input and the backend environment. Create a TradingView alert using **Any alert() function call**, with the HTTPS webhook URL pointing to `/webhooks/tradingview`. The receiver requires a public HTTPS endpoint reachable by TradingView; a localhost-only backend cannot receive cloud webhooks. Use a reverse proxy/tunnel with TLS, request-size limits and rate limiting. Never expose the MT5 terminal API publicly.

The Pine script currently emits on the first session bar's close, not at the exact instant of the open. Use a 5-minute or 15-minute chart and interpret the timestamp accordingly. Validate the script in TradingView's Pine Editor before relying on it.

## Scheduled reports
The API stores events, but daily 07:00 EAT and Sunday reports are not sent automatically by this service yet. Add a trusted scheduler and email provider only after the backend is deployed persistently. GitHub Pages cannot run scheduled Python jobs.
