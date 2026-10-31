# EWMI target architecture — user-controlled analysis workspace

## Product decisions
- Manual trading is the default. EWMI does not open, modify, or close trades.
- Stop-loss and take-profit are user-entered fields, not system-enforced risk limits. A user may optionally use a risk calculator, but it must never change or reject the user's manual plan.
- MT5 connection is optional and lives in a separate Connections menu. The analysis workspace must work without MT5.
- TradingView is the charting and analysis reference. Daily bias and session observations are displayed in EWMI.
- The user can journal trades manually even when no broker is connected.

## TradingView integration: important constraint
The current embedded TradingView widget is an isolated widget and does not expose its candle stream to the parent website. Do not attempt to scrape its iframe or claim that EWMI can read those candles.

The first practical integration is a TradingView Pine Script indicator:
- `tradingview/EWMI_Daily_Bias_Sessions.pine` calculates a transparent daily classification using daily EMA 20, EMA 50 and ADX.
- It monitors London 08:00 Europe/London and New York 08:00 America/New_York session opens, which automatically account for daylight-saving changes.
- The user adds the script to their TradingView chart and creates an alert using "Any alert() function call".
- TradingView can POST the alert JSON to an EWMI webhook endpoint. Webhook delivery requires a reachable HTTPS endpoint, TradingView account eligibility/2FA and careful endpoint authentication.
- Alerts are not guaranteed delivery; retain the TradingView alert log and show last received timestamp/connection health in EWMI.
- Pine script values are a rule-based market classification, not a forecast or trade recommendation. ADX threshold and EMA periods must be visible and configurable.

TradingView's Advanced Charts library is another route, but it requires EWMI to supply a datafeed; the library itself does not supply market data. The current widget embed cannot be used as a programmatic candle API. See official TradingView docs for the Datafeed API and webhook alerts.

## Market-state logic
Initial classification:
- CONSOLIDATION when daily ADX is below the configured threshold.
- BULLISH when ADX meets threshold, daily EMA20 > EMA50 and daily close > EMA20.
- BEARISH when ADX meets threshold, daily EMA20 < EMA50 and daily close < EMA20.
- MIXED when conditions conflict.
Always show the rule inputs, timestamp, chart symbol/feed and source. Never silently equate "mixed" with a directional bias.

This is a baseline classification. Future versions should add W1/H4 context, daily range location, previous-day high/low, ATR, structure and volatility regime, then backtest the definitions. Do not market the label as predictive accuracy.

## Session monitor
- London open: 08:00 Europe/London.
- New York open: 08:00 America/New_York.
- Convert to the user's selected display timezone (default Africa/Nairobi) using IANA time zones, not fixed UTC offsets. London and New York change clocks on different dates.
- At each session open, capture the latest daily bias, ADX, W1/D1/H4 context, current price, previous-day high/low and most recent confirmed structure event.
- Show "at open" snapshot separately from the current live state so the record cannot be overwritten as the session develops.
- User may edit session times in settings.

## Optional MT5 connection menu
The MT5 Python package communicates with an installed MT5 terminal on the same Windows machine/VPS. User selects a broker/terminal profile (e.g. Exness, Deriv, IC Markets, Pepperstone, Other), but account login is performed in the official MT5 terminal or a local protected connector. Never ask for or store a trading password in the public GitHub Pages frontend, browser localStorage, source code, or chat.
- User logs into the broker's MT5 server using their own terminal credentials.
- Local connector reads the active terminal's account, symbols, ticks, candles, open positions and history only after the user authorizes it.
- Connection state, broker/company, server, account alias/last digits (mask full login), and last sync time appear in the Connections menu.
- The user can disconnect the data connector. Disconnecting must not log out of or alter the broker account.
- If MT5 is disconnected, manual analysis and journaling remain fully usable.
- Broker-specific symbols must be mapped explicitly (e.g. EURUSD, EURUSD.a, XAUUSD, GOLD); validate contract size, tick size/value, volume step and trading hours before displaying broker-derived metrics.
- This is a read/track connector, not an execution bridge.

## Trade journal and manual plan
Fields: symbol, direction, session (Asia/London/New York/overlap), planned entry, user-entered stop-loss, user-entered take-profit, timeframe, setup rationale, invalidation reason, optional lot size, optional risk note, execution platform, status, screenshots/notes, exit and outcome.
Never auto-close a trade or change a user's SL/TP. If MT5 is connected, offer read-only position/history matching as an optional convenience; user confirms journal matches.

## Dashboard menu
1. Overview — current market state and watchlist.
2. Analysis — daily bullish/bearish/consolidation/mixed, W1/D1/H4/H1/M15/M5 context, BOS/CHOCH, key levels and setup observations.
3. Sessions — countdown/open/close, session snapshots and session review.
4. TradingView — embedded charts and Pine Script setup instructions.
5. Trade journal — manual plans, actual trades, outcomes and performance.
6. Connections — optional MT5 terminal/broker connection and sync status.
7. Reports — daily 07:00 EAT outlook and weekly Sunday review (after persistent backend/scheduler/email provider are configured).
8. Settings — timezone, instruments, session hours, market-state rules, data sources and privacy.

## Deployment
GitHub Pages remains the public static dashboard. A private backend on the user's Windows PC/VPS receives TradingView webhooks, stores snapshots/trades in SQLite/PostgreSQL and talks to the local MT5 terminal. Do not expose a raw local MT5 API to the internet. Use HTTPS webhook endpoint, random secret/signature validation, rate limiting, audit logs and encrypted secrets.
