"""
Train the XGBoost direction model (Phase 4).

Pools several years of daily data across the NSE watchlist (plus a few extra
large-caps for volume), builds technical features, and trains a binary classifier
for "will the close be higher in HORIZON days?". Reports HONEST out-of-sample
metrics on a chronological hold-out (no shuffling — that would leak the future),
then saves the model + metadata to models/.

Run:
    python train_model.py
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.metrics import accuracy_score, roc_auc_score
from xgboost import XGBClassifier

import features as F

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "signal_xgb.json")
META_PATH = os.path.join(MODEL_DIR, "model_meta.json")

# Watchlist + a few extra liquid NSE names purely to enlarge the training set.
TRAIN_TICKERS = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "SBIN.NS", "WIPRO.NS", "AXISBANK.NS", "LT.NS", "ITC.NS",
    "HINDUNILVR.NS", "BHARTIARTL.NS", "KOTAKBANK.NS", "MARUTI.NS", "SUNPHARMA.NS",
]

PERIOD = "5y"
HOLDOUT_FRAC = 0.2  # last 20% of each ticker's rows = out-of-sample test


def _build_dataset() -> pd.DataFrame:
    frames = []
    for tkr in TRAIN_TICKERS:
        try:
            df = yf.Ticker(tkr).history(period=PERIOD, interval="1d", auto_adjust=True)
        except Exception:
            continue
        if df is None or df.empty or len(df) < 250:
            continue
        feats = F.build_features(df)
        feats["label"] = F.make_label(df)
        feats["ticker"] = tkr
        feats["row"] = range(len(feats))
        feats["n"] = len(feats)
        frames.append(feats)
    if not frames:
        raise RuntimeError("No training data fetched (network?).")
    return pd.concat(frames, ignore_index=True)


def _chronological_split(data: pd.DataFrame):
    """Per-ticker: earliest 80% -> train, latest 20% -> test (no look-ahead)."""
    is_test = data["row"] >= (data["n"] * (1.0 - HOLDOUT_FRAC)).astype(int)
    keep = F.FEATURE_COLUMNS
    train = data[~is_test].dropna(subset=keep + ["label"])
    test = data[is_test].dropna(subset=keep + ["label"])
    return (
        train[keep], train["label"].astype(int),
        test[keep], test["label"].astype(int),
    )


def main() -> None:
    os.makedirs(MODEL_DIR, exist_ok=True)
    print(f"Fetching {PERIOD} of data for {len(TRAIN_TICKERS)} tickers…")
    data = _build_dataset()
    X_tr, y_tr, X_te, y_te = _chronological_split(data)
    print(f"train rows: {len(X_tr):,}  test rows: {len(X_te):,}  "
          f"base rate (train up): {y_tr.mean():.3f}")

    model = XGBClassifier(
        n_estimators=250,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.85,
        colsample_bytree=0.85,
        min_child_weight=3,
        reg_lambda=1.5,
        objective="binary:logistic",
        eval_metric="logloss",
        n_jobs=4,
        random_state=42,
    )
    model.fit(X_tr, y_tr)

    proba_te = model.predict_proba(X_te)[:, 1]
    pred_te = (proba_te > 0.5).astype(int)
    acc = accuracy_score(y_te, pred_te)
    try:
        auc = roc_auc_score(y_te, proba_te)
    except ValueError:
        auc = float("nan")
    base = max(y_te.mean(), 1 - y_te.mean())  # accuracy of always-guess-majority

    print(f"OUT-OF-SAMPLE  accuracy: {acc:.3f}  AUC: {auc:.3f}  "
          f"(majority-class baseline: {base:.3f})")

    model.save_model(MODEL_PATH)
    meta = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "features": F.FEATURE_COLUMNS,
        "horizon": F.HORIZON,
        "period": PERIOD,
        "n_tickers": len(TRAIN_TICKERS),
        "train_rows": int(len(X_tr)),
        "test_rows": int(len(X_te)),
        "oos_accuracy": round(float(acc), 4),
        "oos_auc": round(float(auc), 4) if auc == auc else None,
        "majority_baseline": round(float(base), 4),
        "importances": {
            f: round(float(v), 4)
            for f, v in sorted(
                zip(F.FEATURE_COLUMNS, model.feature_importances_),
                key=lambda kv: kv[1], reverse=True,
            )
        },
    }
    with open(META_PATH, "w") as fh:
        json.dump(meta, fh, indent=2)
    print(f"Saved model -> {MODEL_PATH}")
    print("Top features:", ", ".join(list(meta["importances"])[:5]))


if __name__ == "__main__":
    main()
