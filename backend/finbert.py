"""
FinBERT sentiment scoring (Phase 3, model half).

Wraps ProsusAI/finbert — a BERT model fine-tuned on financial text — to score a
headline as positive / negative / neutral. Replaces the keyword-lexicon stand-in
in news_api.py.

Design notes:
  * The model (~420MB) is loaded LAZILY on first score() call and cached as a
    process-wide singleton, so importing this module is cheap and the backend
    still starts instantly. The first news request after startup pays the load.
  * score() returns (sentiment_float_in_[-1,1], label) so it drops straight into
    the article shape the frontend already expects.
  * If torch/transformers aren't installed or the model can't load, is_available()
    returns False and news_api falls back to the lexicon — the app never breaks.

First run downloads the weights from HuggingFace (needs internet once); after that
it runs fully offline from the local cache.
"""

from __future__ import annotations

import threading

_LOCK = threading.Lock()
_MODEL = None
_TOKENIZER = None
_ID2LABEL: dict[int, str] = {}
_LOAD_FAILED = False

_MODEL_NAME = "ProsusAI/finbert"


def _ensure_loaded() -> bool:
    """Load the model once. Returns True if usable, False if unavailable."""
    global _MODEL, _TOKENIZER, _ID2LABEL, _LOAD_FAILED
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
            import torch  # noqa: F401
            from transformers import (
                AutoModelForSequenceClassification,
                AutoTokenizer,
            )

            tok = AutoTokenizer.from_pretrained(_MODEL_NAME)
            model = AutoModelForSequenceClassification.from_pretrained(_MODEL_NAME)
            model.eval()
            _TOKENIZER = tok
            _MODEL = model
            # e.g. {0: 'positive', 1: 'negative', 2: 'neutral'} — read from config
            _ID2LABEL = {int(k): v.lower() for k, v in model.config.id2label.items()}
            return True
        except Exception:
            _LOAD_FAILED = True
            return False


def is_available() -> bool:
    return _ensure_loaded()


def score(text: str) -> tuple[float, str]:
    """Return (sentiment in [-1, 1], label). Raises if the model is unavailable."""
    if not _ensure_loaded():
        raise RuntimeError("FinBERT unavailable")

    import torch

    inputs = _TOKENIZER(
        text, return_tensors="pt", truncation=True, max_length=128, padding=True
    )
    with torch.no_grad():
        logits = _MODEL(**inputs).logits
    probs = torch.softmax(logits, dim=-1)[0]

    by_label = {_ID2LABEL[i]: float(probs[i]) for i in range(len(probs))}
    p_pos = by_label.get("positive", 0.0)
    p_neg = by_label.get("negative", 0.0)

    sentiment = round(p_pos - p_neg, 2)
    label = max(by_label, key=by_label.get)  # 'positive' | 'negative' | 'neutral'
    return sentiment, label
