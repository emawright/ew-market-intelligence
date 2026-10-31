from app.structure import analyse_structure, find_swings

def test_insufficient_data_is_not_a_signal():
    result = analyse_structure([{"open": 1, "high": 2, "low": 0, "close": 1}] * 8)
    assert result["status"] == "insufficient_data"
    assert result["event"] is None

def test_fractal_swing_high_is_confirmed_after_right_bars():
    highs = [1, 2, 5, 3, 2, 1, 2, 3]
    candles = [{"high": h, "low": h - 1, "close": h - 0.5} for h in highs]
    swings = find_swings(candles, left=2, right=2)
    assert any(s["kind"] == "high" and s["index"] == 2 and s["price"] == 5 for s in swings)
