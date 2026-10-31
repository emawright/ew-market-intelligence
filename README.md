# EW Market Intelligence (EWMI)

EWMI is a manual trading analysis workspace for EURUSD, GBPUSD and XAUUSD.

## Operating principles
- You control entries, stop-loss, take-profit, lot size and execution.
- EWMI does not place, modify or close orders and does not enforce a fixed risk percentage.
- Exness and Deriv are separate optional read-only MT5 profiles. Broker passwords stay inside official MT5 terminals.
- Manual analysis and journaling work without a broker connection.
- Google News and Gemini provide market context, not price feeds, economic-calendar guarantees or trade signals.

## Current implementation
- [Dashboard](index.html): Overview, Analysis, Sessions, TradingView, Trade Journal, Connections, Google + News, Reports and Settings.
- [Architecture](ARCHITECTURE.md)
- [Pine Script daily bias and session monitor](tradingview/EWMI_Daily_Bias_Sessions.pine)
- [Private backend setup](backend/README.md)

## TradingView
The Pine indicator uses daily EMA 20, EMA 50 and ADX to label BULLISH, BEARISH, CONSOLIDATION or MIXED. It monitors 08:00 London and 08:00 New York local session opens. The alert is emitted at the first chart bar's close, not at the exact second of the session open.

To send alerts to EWMI:
1. Deploy the private backend at a public HTTPS endpoint reachable by TradingView.
2. Configure a strong `EWMI_WEBHOOK_SECRET` on the backend.
3. Enter the same secret in the Pine indicator's private webhook setting.
4. Create a TradingView alert using **Any alert() function call** and set the webhook URL to `https://YOUR-HOST/webhooks/tradingview`.
5. Check the stored events in EWMI after alert delivery.

The embedded TradingView widget is visual only; it does not expose candles to the parent site.

## Exness and Deriv
Install the official MT5 terminals, log in normally inside each terminal, and configure each terminal executable path and exact symbol names in `EWMI_BROKER_PROFILES_JSON`. To monitor both at once, use separate terminal installations/instances and paths. Some accounts use symbol suffixes or different gold symbols. Verify each in Market Watch.

## Google News and Gemini
The backend retrieves Google News RSS search headlines and can ask Gemini to produce a cautious market-context briefing. Google News RSS is an undocumented best-effort feed; it can be delayed, duplicated or incomplete. Verify important information with the publisher, central bank or statistics agency. Gemini API keys remain on the private backend.

## Daily and weekly reports
When SMTP settings, a recipient and a Gemini key are configured, the backend schedules a daily email at 07:00 Africa/Nairobi and a weekly email on Sunday at 07:00 Africa/Nairobi. The backend must remain running for these jobs to fire. Configure and test delivery using the backend README.

## Deployment status and limitations
The GitHub Pages frontend is committed, but its backend features require the separately deployed FastAPI service and its secrets/configuration. The MT5 connector has not been tested against your actual Exness or Deriv terminals; exact symbol mapping and separate terminal paths still need your local configuration. The Pine script has not been compiled in TradingView's Pine Editor in this session. Treat the initial bias rules as an explainable baseline, not a backtested strategy. No profitability or delivery guarantee is implied.
