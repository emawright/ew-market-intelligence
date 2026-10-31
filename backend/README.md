# EWMI backend — milestone 1

This is a Windows-hosted FastAPI bridge to a locally installed MetaTrader 5 terminal. It provides authenticated, read-only candle/account/position endpoints and a risk preview. It does not place, modify or close orders.

## Why a separate backend is required
GitHub Pages serves static files. It cannot safely hold broker/API secrets, run a Python process, read a local MT5 terminal, or schedule jobs. Run this service on the same Windows PC or Windows VPS as the MT5 terminal. Keep the API private and authenticated.

## Windows setup
1. Install Python 3.11+ and MetaTrader 5 from your broker. Log in to a demo account and keep the terminal open.
2. In this folder run: py -m venv .venv
3. Activate: .venv\\Scripts\\Activate.ps1
4. Install: pip install -r requirements.txt
5. Copy .env.example to .env, set a long random EWMI_API_TOKEN, set EWMI_MAX_RISK_PERCENT (default 1.0; hard ceiling 2.0), and adjust symbol names to match your broker (for example EURUSD.a or GOLD).
6. Set those environment variables in your PowerShell session and run: uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8000
7. Open http://127.0.0.1:8000/docs and authorize with the bearer token.

Do not expose port 8000 directly to the public internet. For remote access, use a properly authenticated VPN/private tunnel, TLS and firewall restrictions.

## Endpoints
- GET /health — bridge and terminal health.
- GET /symbols — configured broker symbol mapping.
- GET /candles/{market}/{timeframe}?count=300 — MT5 OHLC candles.
- GET /analysis/structure/{market}/{timeframe} — confirmed swings and close-based BOS/CHOCH candidate.
- GET /account and GET /positions — account and open-position snapshots.

## Analysis and trade-control limitations
The structure detector uses confirmed fractal pivots and candle closes. Pivots are delayed by the right-hand confirmation bars; this reduces premature swing labeling but does not eliminate false breaks. BOS/CHOCH labels are context-dependent and are not standalone entry signals.

This connector is read-only. You choose and manage your own entries, stop-loss, take-profit, position size and execution platform. No trade is opened or closed by EWMI.
