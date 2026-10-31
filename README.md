# EW Market Intelligence (EWMI)

EWMI is a user-controlled market-analysis and trade-journaling workspace.

## Product design
- Manual trading only. EWMI does not place, modify or close trades.
- You choose your entry, stop-loss, take-profit and position size. EWMI does not impose a 1% risk rule.
- MT5 is an optional connection menu for reading account information and tracking positions. Analysis and manual journaling remain available without MT5.
- TradingView is the charting and analysis reference.
- London and New York session monitoring uses their local time zones so daylight-saving changes are handled.

## New implementation files
- [Architecture and product design](ARCHITECTURE.md)
- [TradingView Pine Script: daily bias and session monitor](tradingview/EWMI_Daily_Bias_Sessions.pine)
- [Backend setup and API documentation](backend/README.md)

## TradingView integration
The Pine Script indicator classifies the developing daily market as BULLISH, BEARISH, CONSOLIDATION or MIXED using daily EMA 20, EMA 50 and ADX. It records the classification at the London and New York session opens and exposes TradingView alert triggers.

To use it:
1. Open TradingView and select the relevant chart (EURUSD, GBPUSD or XAUUSD).
2. Open Pine Editor and paste the contents of the EWMI Pine Script file.
3. Add the indicator to the chart.
4. Create an alert using **Any alert() function call** if you want session events sent to an external webhook. TradingView webhook alerts require an eligible account, 2FA and a reachable HTTPS endpoint.
5. Review the indicator settings and understand the rules; it is a market-state filter, not a proven prediction system.

Important: the standard embedded TradingView widget does not expose its candle data to the parent website. EWMI cannot read that iframe directly. The Pine Script alert route is the initial integration. A TradingView Advanced Charts implementation is a separate option and requires EWMI to provide its own datafeed.

## MT5 connection
The Python MT5 connector is optional and read-only. Run it on the same Windows PC/VPS as the MT5 terminal. Log into Exness, Deriv, IC Markets, Pepperstone or another broker using the official MT5 terminal. EWMI should read the active terminal connection; do not enter broker passwords into the public website, browser storage, GitHub or chat. Broker symbol mappings must be verified individually.

## GitHub Pages
The existing static dashboard remains hosted at:
https://emawright.github.io/ew-market-intelligence/

GitHub Pages cannot run the Python backend or receive private webhooks by itself. A separately hosted private backend is required for persistent session snapshots, optional MT5 sync, scheduled reports and email delivery.

## Current limitations
The new architecture, Pine Script indicator and read-only MT5 backend foundation are committed. The existing dashboard UI has not yet been rebuilt around the new Analysis, Sessions and Connections menus. Webhook ingestion, persistent storage, live dashboard integration, Gemini/news summaries and scheduled email reports remain future implementation work. No automated trade execution is included.
