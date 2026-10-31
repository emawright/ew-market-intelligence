# EW Market Intelligence (EWMI)

EWMI is being developed in two layers:

- **GitHub Pages dashboard:** visual workspace and user interface.
- **Private backend:** a Windows-hosted Python service running beside the MetaTrader 5 terminal.

## Current dashboard
The current Pages interface still includes TradingView embeds, a browser-local trade journal, supply/demand register, analysis notes, checklist and chart-symbol settings. It does not yet consume the new backend API.

## Backend milestone 1
The new backend scaffold is in /backend. It provides authenticated read-only MT5 data endpoints, a first deterministic confirmed-swing BOS/CHOCH candidate detector, and a broker-specification-based risk preview.

**Assisted execution is the selected product mode, but order placement is deliberately locked in this first milestone.** Every future order must have a valid stop-loss and pass configured risk limits. No AI output can bypass these checks.

See [backend setup and API documentation](backend/README.md).

## Deploy the dashboard with GitHub Pages
1. Open repository Settings → Pages.
2. Under Build and deployment, choose Deploy from a branch.
3. Select branch main and folder /(root), then Save.
4. The intended site URL is https://emawright.github.io/ew-market-intelligence/.

## Important limitations
- GitHub Pages cannot host the Python API or securely store secrets.
- Run the MT5 bridge on the same Windows PC/VPS as the MT5 terminal.
- Broker symbols and contract specifications differ; configure and verify them on a demo account.
- The structure detector is an initial rule set, not a proven profitable strategy or standalone signal.
- Risk preview excludes commission, slippage, gaps and price movement.
- No live order placement, scheduled email reports, Gemini/news integration or cloud trade database is enabled yet.
- Never commit broker passwords, API keys, access tokens or .env files.
