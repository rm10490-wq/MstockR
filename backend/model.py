"""
Trained-model inference (Phase 4).

Loads the XGBoost classifier saved by train_model.py and produces a signal in the
EXACT shape momentum_signal() emits, so the API and frontend are unchanged. The
model's P(up) drives direction/confidence; the momentum baseline is carried
alongside (baseline_direction) so the UI can honestly show "model vs baseline".

If the model file is missing or inference fails, we fall back to the momentum
baseline — the dashboard always returns a signal.
"""

from __future__ import annotations

import json
import os
import threading
import time

import market_data
import features as F

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "signal_xgb.json")
META_PATH = os.path.join(MODEL_DIR, "model_meta.json")

_LOCK = threading.Lock()
_MODEL = None
_META: dict = {}
_LOAD_FAILED = False

# Signal cache so the 5s WebSocket push doesn't re-fetch yfinance every tick.
_SIG_CACHE: dict[str, tuple[float, dict]] = {}
_SIG_TTL = 60.0


def _ensure_loaded() -> bool:
    global _MODEL, _META, _LOAD_FAILED
    if _MODEL is not None:
        return True
    if _LOAD_FAILED:
        return False
    with _LOCK:
        if _MODEL is not None:
            return True
        if _LOAD_FAILED:
            return False
        try:
            if not os.path.exists(MODEL_PATH):
                _LOAD_FAILED = True
                return False
            from xgboost import XGBClassifier

            m = XGBClassifier()
            m.load_model(MODEL_PATH)
            _MODEL = m
            if os.path.exists(META_PATH):
                with open(META_PATH) as fh:
                    _META = json.load(fh)
            return True
        except Exception:
            _LOAD_FAILED = True
            return False


def is_available() -> bool:
    return _ensure_loaded()


def meta() -> dict:
    _ensure_loaded()
    return dict(_META)


_OHLCV_CACHE: dict[str, tuple[float, object]] = {}
_OHLCV_TTL = 60.0


def _fetch_ohlcv(symbol: str, period: str = "6mo"):
    """Raw OHLCV frame for feature building (cached ~60s to bound multi-symbol loads)."""
    key = f"{symbol}:{period}"
    hit = _OHLCV_CACHE.get(key)
    if hit and hit[0] > time.time():
        return hit[1]
    import yfinance as yf

    df = yf.Ticker(symbol).history(period=period, interval="1d", auto_adjust=True)
    _OHLCV_CACHE[key] = (time.time() + _OHLCV_TTL, df)
    return df


def predict_signal(symbol: str) -> dict:
    """Model-based signal for one ticker, same shape as momentum_signal()."""
    symbol = market_data.normalize_symbol(symbol)
    hit = _SIG_CACHE.get(symbol)
    if hit and hit[0] > time.time():
        return hit[1]
    result = _predict_signal_uncached(symbol)
    _SIG_CACHE[symbol] = (time.time() + _SIG_TTL, result)
    return result


def _predict_signal_uncached(symbol: str) -> dict:
    baseline = market_data.momentum_signal(symbol)  # always compute for comparison

    if not _ensure_loaded():
        baseline["model"] = "unavailable"
        return baseline

    try:
        df = _fetch_ohlcv(symbol)
        feats = F.build_features(df)
        latest = feats[F.FEATURE_COLUMNS].dropna()
        if latest.empty:
            baseline["model"] = "insufficient-data"
            return baseline
        p_up = float(_MODEL.predict_proba(latest.iloc[[-1]])[:, 1][0])
    except Exception:
        baseline["model"] = "error"
        return baseline

    # Map probability -> the UI's three states with a neutral deadband.
    if p_up >= 0.55:
        direction = "up"
    elif p_up <= 0.45:
        direction = "down"
    else:
        direction = "flat"

    # Confidence = distance from a coin flip, rescaled to [0.5, ~0.95].
    confidence = round(0.5 + abs(p_up - 0.5), 3)
    # Expected move: lean on the horizon, scaled by conviction. Illustrative only.
    expected = round((p_up - 0.5) * 6.0, 2)  # +/- up to ~3% at the extremes

    return {
        "ticker": symbol,
        "name": market_data.name_for(symbol),
        "direction": direction,
        "confidence": confidence,
        "expected_change_pct": expected,
        "horizon": "1w",
        "last_price": baseline.get("last_price"),
        "currency": market_data.CURRENCY,
        "prob_up": round(p_up, 3),
        "basis": f"XGBoost classifier (trained, {F.HORIZON}d horizon)",
        "model": "xgboost",
        "baseline_direction": baseline.get("direction"),
    }


def watchlist_signals() -> list[dict]:
    return [predict_signal(item["ticker"]) for item in market_data.WATCHLIST]
