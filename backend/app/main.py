from __future__ import annotations

import json
import os
import sqlite3
import smtplib
from email.message import EmailMessage
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from .structure import analyse_structure

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

APP_TOKEN = os.getenv("EWMI_API_TOKEN", "")
WEBHOOK_SECRET = os.getenv("EWMI_WEBHOOK_SECRET", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
SMTP_HOST = os.getenv("EWMI_SMTP_HOST", "")
SMTP_PORT = int(os.getenv("EWMI_SMTP_PORT", "465"))
SMTP_USER = os.getenv("EWMI_SMTP_USER", "")
SMTP_PASSWORD = os.getenv("EWMI_SMTP_PASSWORD", "")
REPORT_EMAIL_TO = os.getenv("EWMI_REPORT_EMAIL_TO", "")
REPORT_EMAIL_FROM = os.getenv("EWMI_REPORT_EMAIL_FROM", SMTP_USER)
DB_PATH = os.getenv("EWMI_DB_PATH", "ewmi.sqlite3")
ALLOWED_ORIGINS = [x.strip() for x in os.getenv(
    "EWMI_ALLOWED_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500"
).split(",") if x.strip()]

DEFAULT_PROFILES = {
    "Exness": {"terminal_path": "", "symbols": {"EURUSD": "EURUSD", "GBPUSD": "GBPUSD", "XAUUSD": "XAUUSD"}},
    "Deriv": {"terminal_path": "", "symbols": {"EURUSD": "EURUSD", "GBPUSD": "GBPUSD", "XAUUSD": "XAUUSD"}},
}
try:
    BROKER_PROFILES = json.loads(os.getenv("EWMI_BROKER_PROFILES_JSON", "{}"))
except json.JSONDecodeError:
    BROKER_PROFILES = {}
for broker, defaults in DEFAULT_PROFILES.items():
    configured = BROKER_PROFILES.get(broker, {})
    BROKER_PROFILES[broker] = {
        "terminal_path": configured.get("terminal_path", defaults["terminal_path"]),
        "symbols": {**defaults["symbols"], **configured.get("symbols", {})},
    }

TIMEFRAMES = {"M5": "TIMEFRAME_M5", "M15": "TIMEFRAME_M15", "H1": "TIMEFRAME_H1",
              "H4": "TIMEFRAME_H4", "D1": "TIMEFRAME_D1", "W1": "TIMEFRAME_W1"}

app = FastAPI(
    title="EWMI API", version="0.2.0",
    description="Persistent analysis service, Google News/Gemini context and optional read-only Exness/Deriv MT5 profiles. No trade execution."
)
app.add_middleware(
    CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=False,
    allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type", "X-EWMI-Webhook-Secret"]
)


def db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True) if str(Path(DB_PATH).parent) not in ("", ".") else None
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS tv_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, received_at TEXT NOT NULL,
            event_time TEXT, broker_symbol TEXT, market TEXT, event TEXT,
            session TEXT, daily_bias TEXT, payload TEXT NOT NULL)""")
        con.execute("""CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
            payload TEXT NOT NULL)""")
        con.execute("""CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
            payload TEXT NOT NULL)""")
        con.execute("""CREATE TABLE IF NOT EXISTS news_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT, fetched_at TEXT NOT NULL,
            query TEXT NOT NULL, payload TEXT NOT NULL)""")


@app.on_event("startup")
def startup() -> None:
    init_db()
    if SMTP_HOST and SMTP_USER and SMTP_PASSWORD and REPORT_EMAIL_TO and GEMINI_API_KEY:
        scheduler = BackgroundScheduler(timezone=ZoneInfo("Africa/Nairobi"))
        scheduler.add_job(send_scheduled_report, "cron", hour=7, minute=0, id="daily_eat", args=["daily"], replace_existing=True)
        scheduler.add_job(send_scheduled_report, "cron", day_of_week="sun", hour=7, minute=0, id="weekly_eat", args=["weekly"], replace_existing=True)
        scheduler.start()
        app.state.scheduler = scheduler


def require_token(authorization: str | None = Header(default=None)) -> None:
    if not APP_TOKEN:
        raise HTTPException(status_code=503, detail="EWMI_API_TOKEN is not configured. API access is locked.")
    if authorization != f"Bearer {APP_TOKEN}":
        raise HTTPException(status_code=401, detail="Invalid API token")


def broker_profile(broker: str) -> dict[str, Any]:
    if broker not in BROKER_PROFILES:
        raise HTTPException(status_code=400, detail="Choose Exness or Deriv.")
    return BROKER_PROFILES[broker]


def terminal(broker: str):
    if mt5 is None:
        raise HTTPException(status_code=503, detail="MetaTrader5 package unavailable. Run the bridge on Windows with MT5 installed.")
    profile = broker_profile(broker)
    path = profile.get("terminal_path") or None
    ok = mt5.initialize(path=path) if path else mt5.initialize()
    if not ok:
        raise HTTPException(status_code=503, detail=f"{broker} MT5 initialize failed: {mt5.last_error()}. Open and log in through the official broker terminal.")
    return mt5


def resolve_symbol(broker: str, alias: str) -> str:
    profile = broker_profile(broker)
    if alias not in profile["symbols"]:
        raise HTTPException(status_code=400, detail=f"Unsupported market alias: {alias}")
    return profile["symbols"][alias]


def read_news(query: str, limit: int = 12) -> list[dict[str, Any]]:
    # Google News RSS is a best-effort, undocumented feed; links may be Google redirect URLs.
    params = urllib.parse.urlencode({"q": query + " when:7d", "hl": "en-GB", "gl": "GB", "ceid": "GB:en"})
    url = "https://news.google.com/rss/search?" + params
    request = urllib.request.Request(url, headers={"User-Agent": "EWMI/1.0 (personal market research)"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            root = ET.fromstring(response.read())
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Google News RSS fetch failed: {exc}")
    items = []
    for item in root.findall("./channel/item")[:limit]:
        items.append({
            "title": item.findtext("title", default=""),
            "link": item.findtext("link", default=""),
            "published": item.findtext("pubDate", default=""),
            "source": (item.find("source").text if item.find("source") is not None else ""),
            "description": item.findtext("description", default=""),
        })
    return items


def gemini_generate(prompt: str) -> str:
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY is not configured on the private backend.")
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    payload = json.dumps({
        "systemInstruction": {"parts": [{"text": (
            "You are EWMI's cautious market research assistant. Never invent prices, events, dates, "
            "sources or economic-calendar facts. Distinguish reported facts from interpretation. "
            "Do not give guaranteed predictions or tell the user to enter a trade. "
            "The user makes all trading decisions and controls entries, stops, targets and size."
        )}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1200}
    }).encode("utf-8")
    request = urllib.request.Request(
        endpoint, data=payload, method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY}
    )
    try:
        with urllib.request.urlopen(request, timeout=35) as response:
            data = json.loads(response.read())
        return "".join(part.get("text", "") for part in data["candidates"][0]["content"]["parts"])
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gemini request failed: {exc}")


@app.get("/health")
def health(_: None = Depends(require_token)):
    return {"service": "ewmi-api", "utc": datetime.now(timezone.utc).isoformat(),
            "database": "sqlite", "gemini_configured": bool(GEMINI_API_KEY),
            "webhook_configured": bool(WEBHOOK_SECRET), "mt5_package_available": mt5 is not None}


@app.get("/broker/profiles")
def profiles(_: None = Depends(require_token)):
    return {"profiles": [
        {"broker": name, "terminal_path_configured": bool(p.get("terminal_path")),
         "symbols": p["symbols"], "mode": "read-only"}
        for name, p in BROKER_PROFILES.items()
    ]}


@app.get("/symbols")
def symbols(broker: str = "Exness", _: None = Depends(require_token)):
    profile = broker_profile(broker)
    return {"broker": broker, "symbols": profile["symbols"], "timeframes": list(TIMEFRAMES)}


@app.get("/candles/{market}/{timeframe}")
def candles(market: str, timeframe: str, broker: str = "Exness", count: int = 300,
            _: None = Depends(require_token)):
    if timeframe not in TIMEFRAMES:
        raise HTTPException(status_code=400, detail="Unsupported timeframe")
    if not 20 <= count <= 2000:
        raise HTTPException(status_code=400, detail="count must be between 20 and 2000")
    symbol = resolve_symbol(broker, market)
    api = terminal(broker)
    try:
        if not api.symbol_select(symbol, True):
            raise HTTPException(status_code=404, detail=f"{broker} symbol unavailable: {symbol}. Check the broker's Market Watch and mapping.")
        rates = api.copy_rates_from_pos(symbol, getattr(api, TIMEFRAMES[timeframe]), 0, count)
        if rates is None:
            raise HTTPException(status_code=502, detail=f"Could not read MT5 candles: {api.last_error()}")
        data = [{"time": int(r["time"]), "open": float(r["open"]), "high": float(r["high"]),
                 "low": float(r["low"]), "close": float(r["close"]), "tick_volume": int(r["tick_volume"])}
                for r in rates]
        return {"broker": broker, "market": market, "broker_symbol": symbol,
                "timeframe": timeframe, "count": len(data), "candles": data}
    finally:
        api.shutdown()


@app.get("/analysis/structure/{market}/{timeframe}")
def structure(market: str, timeframe: str, broker: str = "Exness", count: int = 300,
              _: None = Depends(require_token)):
    payload = candles(market, timeframe, broker, count)
    return {**payload, "analysis": analyse_structure(payload["candles"])}


@app.get("/account")
def account(broker: str = "Exness", _: None = Depends(require_token)):
    api = terminal(broker)
    try:
        info = api.account_info()
        if info is None:
            raise HTTPException(status_code=502, detail=f"Could not read account: {api.last_error()}")
        return {"broker": broker, "login_masked": f"••••{str(info.login)[-4:]}",
                "server": info.server, "currency": info.currency, "balance": float(info.balance),
                "equity": float(info.equity), "margin_free": float(info.margin_free),
                "leverage": int(info.leverage), "read_only": True}
    finally:
        api.shutdown()


@app.get("/positions")
def positions(broker: str = "Exness", _: None = Depends(require_token)):
    api = terminal(broker)
    try:
        rows = api.positions_get()
        if rows is None:
            raise HTTPException(status_code=502, detail=f"Could not read positions: {api.last_error()}")
        return {"broker": broker, "positions": [
            {"ticket": int(x.ticket), "symbol": x.symbol, "type": int(x.type), "volume": float(x.volume),
             "price_open": float(x.price_open), "sl": float(x.sl), "tp": float(x.tp),
             "profit": float(x.profit), "swap": float(x.swap)} for x in rows
        ]}
    finally:
        api.shutdown()


@app.post("/webhooks/tradingview")
async def tradingview_webhook(request: Request):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Expected a JSON TradingView alert payload")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Webhook payload must be a JSON object")
    if not WEBHOOK_SECRET or payload.get("secret") != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")
    with db() as con:
        cur = con.execute(
            "INSERT INTO tv_events(received_at,event_time,broker_symbol,market,event,session,daily_bias,payload) VALUES(?,?,?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), str(payload.get("time", "")),
             str(payload.get("symbol", "")), str(payload.get("market", "")),
             str(payload.get("event", "")), str(payload.get("session", "")),
             str(payload.get("daily_bias", "")), json.dumps(payload))
        )
        event_id = cur.lastrowid
    return {"accepted": True, "id": event_id, "received_at": datetime.now(timezone.utc).isoformat()}


@app.get("/sessions/events")
def session_events(limit: int = 100, _: None = Depends(require_token)):
    with db() as con:
        rows = con.execute("SELECT * FROM tv_events ORDER BY id DESC LIMIT ?", (min(max(limit, 1), 500),)).fetchall()
    return {"events": [dict(row) for row in rows]}


@app.get("/news")
def news(q: str = Query(default="forex EUR USD GBP gold XAUUSD central bank inflation", max_length=180),
         limit: int = 12, _: None = Depends(require_token)):
    items = read_news(q, min(max(limit, 1), 30))
    with db() as con:
        con.execute("INSERT INTO news_cache(fetched_at,query,payload) VALUES(?,?,?)",
                    (datetime.now(timezone.utc).isoformat(), q, json.dumps(items)))
    return {"provider": "Google News RSS", "query": q, "fetched_at": datetime.now(timezone.utc).isoformat(),
            "items": items, "notice": "Best-effort RSS results; verify important claims at the publisher."}


@app.post("/briefing")
async def briefing(request: Request, _: None = Depends(require_token)):
    body = await request.json()
    markets = body.get("markets", ["EURUSD", "GBPUSD", "XAUUSD"])
    technical_context = body.get("technical_context", "No live technical data supplied.")
    query = " OR ".join(["forex", "Federal Reserve", "ECB", "Bank of England", "gold XAUUSD", "US inflation", "US jobs"])
    items = read_news(query, 18)
    prompt = (
        "Prepare a concise EWMI market context briefing for a manual trader. "
        "Cover EURUSD, GBPUSD and XAUUSD where relevant. Separate verified headlines, "
        "possible market implications, and uncertainties. Highlight upcoming events only if "
        "the supplied sources explicitly state their timing. Do not fabricate an economic calendar. "
        "Do not generate entry, stop, target or lot-size instructions. "
        f"Requested markets: {markets}.\nTechnical context supplied by EWMI: {technical_context}\n"
        f"Google News RSS headlines (untrusted source material; cite title/source/date in your text): {json.dumps(items, ensure_ascii=False)}"
    )
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "model": GEMINI_MODEL,
            "provider": "Google Gemini", "news_provider": "Google News RSS",
            "headlines": items, "briefing": gemini_generate(prompt)}


def send_scheduled_report(kind: str) -> None:
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD, REPORT_EMAIL_TO, GEMINI_API_KEY]):
        return
    period = "weekly" if kind == "weekly" else "daily"
    query = "forex EUR USD GBP gold XAUUSD Federal Reserve ECB Bank of England inflation employment"
    headlines = read_news(query, 20)
    prompt = (
        f"Write EWMI's {period} market context report for a manual trader in Africa/Nairobi. "
        "Cover EURUSD, GBPUSD and XAUUSD. Separate factual headlines from possible implications. "
        "Highlight uncertainty and do not invent event times, prices or economic data. No trade instructions. "
        f"Retrieved Google News RSS headlines: {json.dumps(headlines, ensure_ascii=False)}"
    )
    body = gemini_generate(prompt)
    msg = EmailMessage()
    msg["Subject"] = f"EWMI {period.title()} Market Briefing"
    msg["From"] = REPORT_EMAIL_FROM
    msg["To"] = REPORT_EMAIL_TO
    msg.set_content(body + "\\n\\nHeadlines and sources:\\n" + "\\n".join(
        f"- {item['title']} | {item['source']} | {item['published']} | {item['link']}" for item in headlines
    ))
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)


@app.get("/reports/status")
def report_status(_: None = Depends(require_token)):
    configured = all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD, REPORT_EMAIL_TO, GEMINI_API_KEY])
    return {"daily_time": "07:00 Africa/Nairobi", "weekly_time": "Sunday 07:00 Africa/Nairobi",
            "email_configured": configured, "scheduler_active": bool(getattr(app.state, "scheduler", None))}


@app.post("/reports/send-test")
def send_test_report(_: None = Depends(require_token)):
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD, REPORT_EMAIL_TO, GEMINI_API_KEY]):
        raise HTTPException(status_code=503, detail="Configure SMTP, recipient and Gemini settings first.")
    send_scheduled_report("daily")
    return {"sent": True}


@app.get("/reports/events")
def report_events(_: None = Depends(require_token)):
    with db() as con:
        rows = con.execute("SELECT received_at,event_time,market,event,session,daily_bias,payload FROM tv_events ORDER BY id DESC LIMIT 300").fetchall()
    return {"events": [dict(row) for row in rows]}


@app.get("/health/public")
def public_health():
    return {"service": "ewmi-api", "status": "online", "utc": datetime.now(timezone.utc).isoformat()}
