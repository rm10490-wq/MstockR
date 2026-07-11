"""
Feature engineering for the trained signal model (Phase 4).

Turns a raw OHLCV price frame (as returned by yfinance) into a fixed, ordered set
of technical features. The SAME function is used for training (train_model.py),
live inference (model.py), and backtesting (backtest.py) so there is never a
train/serve skew.

All features are scale-free (returns, ratios, oscillators) so a single pooled
model can learn across tickers of very different price levels.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Fixed, ordered feature list. Order matters — the model is trained on this order.
FEATURE_COLUMNS = [
    "ret_1", "ret_5", "ret_10", "ret_20",
    "close_ma5", "close_ma10", "close_ma20", "ma5_ma20",
    "vol_10", "vol_20",
    "rsi_14", "mom_10",
    "vol_chg_5",
]

# How many trading days ahead the label looks. 5 ≈ "1 week", matching the UI horizon.
HORIZON = 5


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """OHLCV frame -> feature frame (same index). Columns == FEATURE_COLUMNS."""
    close = df["Close"].astype(float)
    daily = close.pct_change()

    out = pd.DataFrame(index=df.index)
    out["ret_1"] = daily
    out["ret_5"] = close.pct_change(5)
    out["ret_10"] = close.pct_change(10)
    out["ret_20"] = close.pct_change(20)

    ma5 = close.rolling(5).mean()
    ma10 = close.rolling(10).mean()
    ma20 = close.rolling(20).mean()
    out["close_ma5"] = close / ma5 - 1.0
    out["close_ma10"] = close / ma10 - 1.0
    out["close_ma20"] = close / ma20 - 1.0
    out["ma5_ma20"] = ma5 / ma20 - 1.0

    out["vol_10"] = daily.rolling(10).std()
    out["vol_20"] = daily.rolling(20).std()

    out["rsi_14"] = _rsi(close, 14) / 100.0  # scale to ~[0,1]
    out["mom_10"] = close / close.shift(10) - 1.0

    if "Volume" in df and df["Volume"].fillna(0).sum() > 0:
        vol = df["Volume"].astype(float).replace(0, np.nan)
        out["vol_chg_5"] = (vol / vol.shift(5) - 1.0).replace([np.inf, -np.inf], np.nan)
    else:
        out["vol_chg_5"] = 0.0

    return out[FEATURE_COLUMNS]


def make_label(df: pd.DataFrame, horizon: int = HORIZON) -> pd.Series:
    """Binary label: 1 if the close `horizon` days ahead is higher, else 0."""
    future_ret = df["Close"].shift(-horizon) / df["Close"] - 1.0
    return (future_ret > 0).astype("Int64").rename("label")


def forward_return(df: pd.DataFrame, horizon: int = HORIZON) -> pd.Series:
    """Realized `horizon`-day forward return (used by the backtest equity curve)."""
    return (df["Close"].shift(-horizon) / df["Close"] - 1.0).rename("fwd_ret")
