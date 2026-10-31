from __future__ import annotations
import os
from datetime import datetime, timezone
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .structure import analyse_structure

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

APP_TOKEN = os.getenv("EWMI_API_TOKEN", "")
MAX_RISK_PERCENT = float(os.getenv("EWMI_MAX_RISK_PERCENT", "1.0"))
ALLOWED_ORIGINS = [x.strip() for x in os.getenv("EWMI_ALLOWED_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500").split(",") if x.strip()]
SYMBOLS = {"EURUSD": os.getenv("EWMI_SYMBOL_EURUSD", "EURUSD"),
           "GBPUSD": os.getenv("EWMI_SYMBOL_GBPUSD", "GBPUSD"),
           "XAUUSD": os.getenv("EWMI_SYMBOL_XAUUSD", "XAUUSD")}
TIMEFRAMES = {"M5": "TIMEFRAME_M5", "M15": "TIMEFRAME_M15", "H1": "TIMEFRAME_H1",
              "H4": "TIMEFRAME_H4", "D1": "TIMEFRAME_D1", "W1": "TIMEFRAME_W1"}

app = FastAPI(title="EWMI API", version="0.1.0",
              description="Optional read-only MT5 data connector. No trade execution or risk enforcement.")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=False,
                   allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])

def require_token(authorization: str | None = Header(default=None)) -> None:
    if not APP_TOKEN:
        raise HTTPException(status_code=503, detail="EWMI_API_TOKEN is not configured. API access is locked.")
    if authorization != f"Bearer {APP_TOKEN}":
        raise HTTPException(status_code=401, detail="Invalid API token")

def terminal():
    if mt5 is None:
        raise HTTPException(status_code=503, detail="MetaTrader5 package unavailable. Run this bridge on Windows with MT5 installed.")
    if not mt5.initialize():
        raise HTTPException(status_code=503, detail=f"MT5 initialize failed: {mt5.last_error()}")
    return mt5

def resolve_symbol(alias: str) -> str:
    if alias not in SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Unsupported market alias: {alias}")
    return SYMBOLS[alias]

@app.get("/health")
def health(_: None = Depends(require_token)):
    connected, error = False, None
    if mt5 is not None and mt5.initialize():
        connected = mt5.terminal_info() is not None
        mt5.shutdown()
    else:
        error = "MT5 package or terminal unavailable"
    return {"service": "ewmi-api", "utc": datetime.now(timezone.utc).isoformat(),
            "mt5_connected": connected, "error": error}

@app.get("/symbols")
def symbols(_: None = Depends(require_token)):
    return {"symbols": SYMBOLS, "timeframes": list(TIMEFRAMES)}

@app.get("/candles/{market}/{timeframe}")
def candles(market: str, timeframe: str, count: int = 300, _: None = Depends(require_token)):
    if timeframe not in TIMEFRAMES:
        raise HTTPException(status_code=400, detail="Unsupported timeframe")
    if not 20 <= count <= 2000:
        raise HTTPException(status_code=400, detail="count must be between 20 and 2000")
    symbol = resolve_symbol(market)
    api = terminal()
    if not api.symbol_select(symbol, True):
        api.shutdown()
        raise HTTPException(status_code=404, detail=f"MT5 symbol unavailable: {symbol}")
    rates = api.copy_rates_from_pos(symbol, getattr(api, TIMEFRAMES[timeframe]), 0, count)
    if rates is None:
        error = api.last_error()
        api.shutdown()
        raise HTTPException(status_code=502, detail=f"Could not read MT5 candles: {error}")
    data = [{"time": int(r["time"]), "open": float(r["open"]), "high": float(r["high"]),
             "low": float(r["low"]), "close": float(r["close"]), "tick_volume": int(r["tick_volume"])}
            for r in rates]
    api.shutdown()
    return {"market": market, "broker_symbol": symbol, "timeframe": timeframe, "count": len(data), "candles": data}

@app.get("/analysis/structure/{market}/{timeframe}")
def structure(market: str, timeframe: str, count: int = 300, _: None = Depends(require_token)):
    payload = candles(market, timeframe, count)
    return {**payload, "analysis": analyse_structure(payload["candles"])}

@app.get("/account")
def account(_: None = Depends(require_token)):
    api = terminal()
    info = api.account_info()
    if info is None:
        error = api.last_error()
        api.shutdown()
        raise HTTPException(status_code=502, detail=f"Could not read account: {error}")
    result = {"login": int(info.login), "server": info.server, "currency": info.currency,
              "balance": float(info.balance), "equity": float(info.equity),
              "margin_free": float(info.margin_free), "leverage": int(info.leverage)}
    api.shutdown()
    return result

@app.get("/positions")
def positions(_: None = Depends(require_token)):
    api = terminal()
    rows = api.positions_get()
    if rows is None:
        error = api.last_error()
        api.shutdown()
        raise HTTPException(status_code=502, detail=f"Could not read positions: {error}")
    result = [{"ticket": int(x.ticket), "symbol": x.symbol, "type": int(x.type), "volume": float(x.volume),
               "price_open": float(x.price_open), "sl": float(x.sl), "tp": float(x.tp),
               "profit": float(x.profit), "swap": float(x.swap)} for x in rows]
    api.shutdown()
    return {"positions": result}

