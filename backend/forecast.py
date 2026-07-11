"""
Forward price forecast (the visible "prediction").

Turns the model's signal into a forward-looking price projection you can see on
the chart: a predicted path from today's price to a HORIZON-day target, wrapped
in a volatility-based confidence cone. This is the quant forecast — derived from
the trained XGBoost / momentum signal and the stock's own volatility, NOT a
crystal ball. Educational only, not advice.

Design:
  * target   = last_price * (1 + expected_change_pct/100), from the signal.
  * the cone half-width grows with sqrt(day) using the stock's realized daily
    volatility (a standard random-walk uncertainty band), so the band fans out
    the further ahead we project — an honest picture of rising uncertainty.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import market_data
import model as signal_model

HORIZON_DAYS = 5          # matches the model's 5-day signal
_BAND_Z = 1.0             # ~1 std-dev cone (~68%); widen for a wider band


def _next_business_days(last_date_iso: str, n: int) -> list[str]:
    """n trading-day dates after the last history date (skips weekends)."""
    try:
        d = datetime.fromisoformat(last_date_iso)
    except Exception:
        d = datetime.utcnow()
    out: list[str] = []
    while len(out) < n:
        d = d + timedelta(days=1)
        if d.weekday() < 5:  # Mon–Fri
            out.append(d.date().isoformat())
    return out


def _daily_volatility(points: list[dict]) -> float:
    """Std-dev of daily returns from recent closes (fallback 1.5%)."""
    closes = [p["close"] for p in points][-30:]
    if len(closes) < 5:
        return 0.015
    rets = [(closes[i] / closes[i - 1] - 1.0) for i in range(1, len(closes))]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / max(1, len(rets) - 1)
    return math.sqrt(var) or 0.015


def forecast(symbol: str) -> dict:
    symbol = market_data.normalize_symbol(symbol)

    # Signal (model when available, else momentum baseline) drives the target.
    if signal_model.is_available():
        sig = signal_model.predict_signal(symbol)
    else:
        sig = market_data.momentum_signal(symbol)

    history = market_data.fetch_history(symbol)
    if not history or sig.get("last_price") is None:
        return {"ticker": symbol, "found": False, "points": [], "target": None}

    last_price = float(sig["last_price"])
    last_date = history[-1]["date"]
    exp_pct = float(sig.get("expected_change_pct") or 0.0)
    target = last_price * (1.0 + exp_pct / 100.0)

    vol = _daily_volatility(history)
    dates = _next_business_days(last_date, HORIZON_DAYS)

    # Build the forward path + widening cone. Anchor day 0 at the last close.
    points = [{"date": last_date, "forecast": round(last_price, 2),
               "low": round(last_price, 2), "high": round(last_price, 2)}]
    for i, dt in enumerate(dates, start=1):
        frac = i / HORIZON_DAYS
        mid = last_price + (target - last_price) * frac          # linear glide to target
        band = last_price * vol * _BAND_Z * math.sqrt(i)         # sqrt-time uncertainty
        points.append({
            "date": dt,
            "forecast": round(mid, 2),
            "low": round(mid - band, 2),
            "high": round(mid + band, 2),
        })

    final = points[-1]
    return {
        "ticker": symbol,
        "name": market_data.name_for(symbol),
        "found": True,
        "currency": market_data.CURRENCY,
        "last_price": round(last_price, 2),
        "direction": sig.get("direction"),
        "prob_up": sig.get("prob_up"),
        "confidence": sig.get("confidence"),
        "expected_change_pct": round(exp_pct, 2),
        "horizon_days": HORIZON_DAYS,
        "target": round(target, 2),
        "target_low": final["low"],
        "target_high": final["high"],
        "daily_vol_pct": round(vol * 100.0, 2),
        "basis": sig.get("basis", "signal-based projection"),
        "model": sig.get("model", "momentum"),
        "points": points,
        "disclaimer": "Projection from the model signal + volatility. Not advice.",
    }
