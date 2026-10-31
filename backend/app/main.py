from __future__ import annotations
import os
from datetime import datetime, timezone
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from .structure import analyse_structure

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

APP_TOKEN = os.getenv("EWMI_API_TOKEN", "")
ALLOWED_ORIGINS = [x.strip() for x in os.getenv("EWMI_ALLOWED_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500").split(",") if x.strip()]
SYMBOLS = {"EURUSD": os.getenv("EWMI_SYMBOL_EURUSD", "EURUSD"),
           "GBPUSD": os.getenv("EWMI_SYMBOL_GBPUSD", "GBPUSD"),
           "XAUUSD": os.getenv("EWMI_SYMBOL_XAUUSD", "XAUUSD")}
TIMEFRAMES = {"M5": "TIMEFRAME_M5", "M15": "TIMEFRAME_M15", "H1": "TIMEFRAME_H1",
              "H4": "TIMEFRAME_H4", "D1": "TIMEFRAME_D1", "W1": "TIMEFRAME_W1"}

app = FastAPI(title="EWMI API", version="0.1.0",
              description="Read-only MT5 bridge and risk preview. Order execution is disabled in this milestone.")
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
    api, symbol = terminal(), resolve_symbol(market)
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
    api, = (terminal(),)
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

class RiskPreview(BaseModel):
    market: str
    side: str = Field(pattern="^(buy|sell)$")
    entry: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    take_profit: float | None = Field(default=None, gt=0)
    risk_percent: float = Field(gt=0, le=2.0)

@app.post("/risk/preview")
def risk_preview(order: RiskPreview, _: None = Depends(require_token)):
    if order.side == "buy" and order.stop_loss >= order.entry:
        raise HTTPException(status_code=422, detail="For a buy, stop-loss must be below entry.")
    if order.side == "sell" and order.stop_loss <= order.entry:
        raise HTTPException(status_code=422, detail="For a sell, stop-loss must be above entry.")
    if order.take_profit is not None:
        valid = order.take_profit > order.entry if order.side == "buy" else order.take_profit < order.entry
        if not valid:
            raise HTTPException(status_code=422, detail="Take-profit must be on the profit side of entry.")
    api, symbol = terminal(), resolve_symbol(order.market)
    info, account = api.symbol_info(symbol), api.account_info()
    if info is None or account is None:
        api.shutdown()
        raise HTTPException(status_code=502, detail="Could not read broker symbol/account specifications.")
    risk_cash = float(account.equity) * order.risk_percent / 100.0
    distance = abs(order.entry - order.stop_loss)
    if not info.trade_tick_size or not info.trade_tick_value or distance <= 0:
        api.shutdown()
        raise HTTPException(status_code=422, detail="Broker tick specifications invalid; cannot size safely.")
    loss_per_lot = (distance / float(info.trade_tick_size)) * float(info.trade_tick_value)
    raw_volume, step = risk_cash / loss_per_lot, float(info.volume_step)
    volume = round((raw_volume // step) * step, 8)
    if volume < float(info.volume_min):
        api.shutdown()
        raise HTTPException(status_code=422, detail="Calculated volume is below broker minimum. Do not increase lot size to force this trade.")
    if volume > float(info.volume_max):
        api.shutdown()
        raise HTTPException(status_code=422, detail="Calculated volume exceeds broker maximum; reassess trade.")
    result = {"market": order.market, "broker_symbol": symbol, "side": order.side,
              "entry": order.entry, "stop_loss": order.stop_loss, "take_profit": order.take_profit,
              "risk_percent": order.risk_percent, "equity": float(account.equity),
              "risk_cash_estimate": round(loss_per_lot * volume, 2), "volume": volume,
              "volume_min": float(info.volume_min), "volume_step": step,
              "note": "Estimate excludes commission, slippage, gaps and changing prices. Recheck at execution time."}
    api.shutdown()
    return result

@app.post("/orders/confirm")
def confirm_order(_: None = Depends(require_token)):
    raise HTTPException(status_code=423, detail="Execution is locked in milestone 1. Read-only MT5 data and risk preview are available. Execution requires demo validation, broker-specific checks, duplicate protection, daily-loss limits and explicit UI confirmation.")
