from __future__ import annotations
from typing import Any

def find_swings(candles: list[dict[str, Any]], left: int = 3, right: int = 3) -> list[dict[str, Any]]:
    """Find confirmed fractal pivots after the required right-hand bars have closed."""
    if left < 1 or right < 1:
        raise ValueError("left and right must be >= 1")
    swings = []
    for i in range(left, len(candles) - right):
        high, low = float(candles[i]["high"]), float(candles[i]["low"])
        before, after = candles[i-left:i], candles[i+1:i+right+1]
        if all(high > float(x["high"]) for x in before + after):
            swings.append({"index": i, "time": candles[i].get("time"), "kind": "high", "price": high})
        if all(low < float(x["low"]) for x in before + after):
            swings.append({"index": i, "time": candles[i].get("time"), "kind": "low", "price": low})
    return sorted(swings, key=lambda x: x["index"])

def analyse_structure(candles: list[dict[str, Any]], left: int = 3, right: int = 3) -> dict[str, Any]:
    """Conservative close-based structure break detector; this is not a trade signal."""
    if len(candles) < left + right + 5:
        return {"status": "insufficient_data", "bias": "neutral", "event": None, "swings": []}
    swings = find_swings(candles, left, right)
    highs = [s for s in swings if s["kind"] == "high"]
    lows = [s for s in swings if s["kind"] == "low"]
    if len(highs) < 2 or len(lows) < 2:
        return {"status": "insufficient_swings", "bias": "neutral", "event": None, "swings": swings}
    last_close, previous_close = float(candles[-1]["close"]), float(candles[-2]["close"])
    last_high, prior_high, last_low, prior_low = highs[-1], highs[-2], lows[-1], lows[-2]
    if last_high["price"] > prior_high["price"] and last_low["price"] > prior_low["price"]:
        bias = "bullish"
    elif last_high["price"] < prior_high["price"] and last_low["price"] < prior_low["price"]:
        bias = "bearish"
    else:
        bias = "neutral"
    event = None
    if previous_close <= last_high["price"] < last_close:
        event = {"type": "BOS" if bias == "bullish" else "CHOCH", "direction": "bullish",
                 "level": last_high["price"], "bar_time": candles[-1].get("time")}
    elif previous_close >= last_low["price"] > last_close:
        event = {"type": "BOS" if bias == "bearish" else "CHOCH", "direction": "bearish",
                 "level": last_low["price"], "bar_time": candles[-1].get("time")}
    return {"status": "ok", "bias": bias, "event": event, "last_close": last_close,
            "last_confirmed_swing_high": last_high, "last_confirmed_swing_low": last_low,
            "swings": swings, "method": "confirmed_fractal_swings_close_break_v1",
            "warning": "A single timeframe structure event is not an entry signal. Validate higher-timeframe context, spread, news and risk."}
