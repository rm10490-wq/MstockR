"""
Walk-forward backtest (Phase 5).

Honestly evaluates the trained-style model on ONE ticker without look-ahead:

  * Build features + a HORIZON-day forward label over ~5y of history.
  * Step forward in non-overlapping HORIZON-day chunks. At each chunk the model is
    (periodically) retrained on ONLY the data whose labels are already realized
    (index <= t - HORIZON), then predicts the next chunk's direction.
  * Simulate a simple long/flat strategy (go long when the model says "up",
    else hold cash) and compare its equity curve to buy-&-hold.

Returns an equity curve + summary stats for the frontend. Results are cached per
ticker because a backtest re-trains the model dozens of times.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

import market_data
import features as F

_PERIOD = "5y"
_INITIAL = 300          # min training rows before the first prediction
_RETRAIN_EVERY = 4      # retrain every N chunks (~ monthly at HORIZON=5)

_CACHE: dict[str, tuple[float, dict]] = {}
_TTL = 1800.0           # 30 min


def _model() -> XGBClassifier:
    return XGBClassifier(
        n_estimators=120, max_depth=3, learning_rate=0.07,
        subsample=0.85, colsample_bytree=0.85, min_child_weight=3,
        reg_lambda=1.5, objective="binary:logistic", eval_metric="logloss",
        n_jobs=2, random_state=42,
    )


def _fetch(symbol: str) -> pd.DataFrame:
    import yfinance as yf

    return yf.Ticker(symbol).history(period=_PERIOD, interval="1d", auto_adjust=True)


def run(symbol: str) -> dict:
    symbol = market_data.normalize_symbol(symbol)
    hit = _CACHE.get(symbol)
    if hit and hit[0] > time.time():
        return hit[1]

    df = _fetch(symbol)
    if df is None or df.empty or len(df) < _INITIAL + 4 * F.HORIZON:
        return {"ticker": symbol, "found": False, "points": [], "stats": {}}

    feats = F.build_features(df)
    label = F.make_label(df).astype("float")
    fwd = F.forward_return(df)
    dates = df.index

    X = feats[F.FEATURE_COLUMNS]
    valid = X.notna().all(axis=1)

    h = F.HORIZON
    n = len(df)
    # Non-overlapping chunk starts, beginning once we have enough history.
    starts = list(range(_INITIAL, n - h, h))

    model = None
    equity_strat, equity_bh = 1.0, 1.0
    points, correct, total, trades = [], 0, 0, 0

    for ci, t in enumerate(starts):
        # (Re)train on rows whose HORIZON-day label is fully realized: idx <= t - h.
        if model is None or ci % _RETRAIN_EVERY == 0:
            train_idx = np.arange(0, t - h)
            m = valid.values[train_idx] & label.iloc[train_idx].notna().values
            if m.sum() < 100:
                continue
            model = _model()
            model.fit(X.iloc[train_idx][m], label.iloc[train_idx][m].astype(int))

        if not valid.iloc[t]:
            continue
        p_up = float(model.predict_proba(X.iloc[[t]])[:, 1][0])
        realized = fwd.iloc[t]
        if pd.isna(realized):
            continue

        went_up = realized > 0
        pred_up = p_up >= 0.5
        total += 1
        if pred_up == went_up:
            correct += 1

        position = 1.0 if pred_up else 0.0   # long when bullish, else cash
        if position > 0:
            trades += 1
        equity_strat *= (1.0 + position * float(realized))
        equity_bh *= (1.0 + float(realized))

        points.append({
            "date": dates[t].date().isoformat(),
            "strategy": round(equity_strat, 4),
            "buyhold": round(equity_bh, 4),
        })

    acc = round(correct / total, 4) if total else None
    stats = {
        "accuracy": acc,
        "n_predictions": total,
        "trades": trades,
        "strategy_return_pct": round((equity_strat - 1.0) * 100.0, 2),
        "buyhold_return_pct": round((equity_bh - 1.0) * 100.0, 2),
        "horizon_days": h,
        "retrains": (len(starts) // _RETRAIN_EVERY) + 1,
        "start": points[0]["date"] if points else None,
        "end": points[-1]["date"] if points else None,
    }
    result = {"ticker": symbol, "found": True, "points": points, "stats": stats,
              "basis": "walk-forward, non-overlapping, periodic retrain, no look-ahead"}
    _CACHE[symbol] = (time.time() + _TTL, result)
    return result
