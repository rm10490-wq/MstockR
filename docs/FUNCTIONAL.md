# Signal Desk — Functional & Feature Document

**Product:** Signal Desk — a news-driven stock dashboard for Indian markets (NSE)
**Version:** 0.6 (all six roadmap phases delivered)
**Audience:** product stakeholders, analysts, evaluators, end users

---

## 1. What it is

Signal Desk is a live web dashboard that brings four things onto one screen for
Indian large-cap stocks:

1. **Real prices** and charts (NSE, in ₹)
2. **Real news** with automatic sentiment scoring
3. A **direction signal** (up / flat / down) per stock
4. An honest **backtest** that shows whether the signal actually works

It is built as a transparent research tool: it uses genuinely live data and a
genuinely trained model, and it is deliberately honest about what the model can
and cannot do.

> **The core value proposition:** most "stock prediction" demos quietly overstate
> their accuracy. Signal Desk does the opposite — it puts real data and a real
> model in front of you, then *proves with a backtest* whether the signal has any
> edge. That intellectual honesty is the feature.

---

## 2. Who it's for

| User | How they use it |
|------|-----------------|
| **Retail investor / enthusiast** | Glance at live signals + news sentiment for watchlist stocks; search any NSE name |
| **Analyst / researcher** | Study the walk-forward backtest; export data from MySQL for their own analysis |
| **Student / learner** | See a complete, honest ML pipeline (features → train → serve → backtest) end to end |
| **Developer** | Extend it — swap the model, add features, wire new data sources |

---

## 3. Feature catalogue (with benefits)

### 3.1 Live signals dashboard
**What:** A card per watchlist stock showing direction (up/flat/down),
confidence, expected move, and last price — refreshing live over a WebSocket
every few seconds.
**How to use:** Open the app; the Signals panel is front and centre. Click a card
to focus that stock across the chart, news, and backtest.
**Benefit:** One glance tells you the model's current read on every tracked stock,
always current, with no manual refresh.

### 3.2 Real NSE prices & interactive charts
**What:** Genuine daily closing prices from Yahoo Finance (NSE, in ₹) with a
5-day moving average, rendered as an interactive 6-month chart.
**How to use:** Select any stock to load its chart; hover for exact values.
**Benefit:** You're looking at **real market data**, not a simulation — a
trustworthy basis for everything else on screen.

### 3.3 Real news feed with AI sentiment
**What:** Live headlines from NewsAPI, each tagged to the relevant company and
scored for sentiment (positive / neutral / negative) by **FinBERT**, a model
purpose-built for financial text.
**How to use:** Read the News panel; click a stock to filter its news. Each item
shows source, sentiment, and a novelty ("surprise") score.
**Benefit:** You instantly see not just *what* the news says but *how the market
should feel about it* — and FinBERT reads finance nuance (e.g. "no let-up in
caution") that keyword tools miss.

### 3.4 Keyword search / typeahead *(new)*
**What:** Type a company name or partial keyword ("tata", "reliance", "maruti")
and get a live dropdown of matching NSE/BSE stocks to select.
**How to use:** Start typing in the search box; pick a match with mouse or
↑/↓ + Enter. The full analysis (signal, chart, news, backtest) loads for it.
**Benefit:** You don't need to know exact ticker symbols. Search by the name you
know and drill into **any** listed Indian stock, not just the watchlist.

### 3.5 Trained model signal + baseline comparison
**What:** The signal is produced by a trained **XGBoost** classifier over
technical features, with a transparent **momentum baseline** shown alongside for
comparison.
**How to use:** Each signal card shows the model's call; the baseline is carried
in the data for honest side-by-side comparison.
**Benefit:** You see a real machine-learning prediction *and* the simple benchmark
it's meant to beat — no black box, no unearned trust.

### 3.6 Walk-forward backtest *(the honesty engine)*
**What:** For any selected stock, a rigorous **walk-forward** backtest (no
look-ahead) that retrains as it steps through history, then charts a strategy
equity curve vs buy-&-hold with accuracy and return stats.
**How to use:** Select a stock; the Backtest panel runs automatically (~6 s) and
shows the model's historical performance.
**Benefit:** This is what separates Signal Desk from hype — **you can verify
whether the signal ever worked**, on real history, with the same integrity a
professional quant would demand.

### 3.7 Automatic data sync (scheduled polling) *(new)*
**What:** A background scheduler refreshes signals and news and writes fresh
snapshots to the database on an interval (default every 30 minutes), unattended.
**How to use:** Nothing to do — a "synced Xm ago" badge in the header shows it's
working. Cadence is configurable.
**Benefit:** Your data and history stay current on their own, and a **time series
of signals accumulates automatically** for later analysis — no manual runs.

### 3.8 MySQL analysis store *(bonus)*
**What:** Prices, signal snapshots, and scored news are persisted to a local
MySQL database (`stockdash`) in clean, query-ready tables.
**How to use:** Query `prices`, `signals`, `news` with any SQL/BI tool; re-runs
are safe (deduplicated).
**Benefit:** Take the data **beyond the dashboard** — build your own charts,
correlations, or reports in Excel, Power BI, or pandas, on your own machine.

### 3.9 Suggested idea ("top pick")
**What:** A ranked view that surfaces the strongest current signal as a
highlighted idea.
**Benefit:** A fast, opinionated starting point — clearly labelled as a heuristic
ranking, **not advice**.

### 3.10 Resilience & graceful fallback
**What:** Every live source has a safety net — FinBERT→lexicon, NewsAPI→mock,
model→baseline, DB-off→cache-only.
**Benefit:** The dashboard **never breaks** in front of you. A rate-limited API or
an offline model degrades quietly instead of showing an error screen.

---

## 4. A typical session

1. Open the dashboard → live signals and real news are already there.
2. Search **"tata"** → pick **TATA TECHNOLOGIES** from the dropdown.
3. Its chart, model signal, and company news load instantly.
4. The **backtest** runs → you see the strategy vs buy-&-hold curve and the
   model's historical accuracy for that stock.
5. In the background, the scheduler keeps everything synced and logs a fresh
   snapshot to MySQL for you to analyse later.

---

## 5. Benefits at a glance

| Benefit | Delivered by |
|---------|--------------|
| Trustworthy, real market data | Live yfinance prices + charts |
| Understand the *why* behind moves | Real news + FinBERT sentiment |
| Search by name, analyse any stock | Keyword typeahead |
| A real ML prediction, not a toy | Trained XGBoost signal |
| Proof of whether it works | Walk-forward backtest |
| Effortless, always-current data | Scheduled auto-sync |
| Your data, your tools | MySQL analysis store |
| Never a broken screen | Graceful fallbacks everywhere |
| No false promises | Honest metrics surfaced at every layer |

---

## 6. Honest scope & limitations (by design)

Signal Desk is a **research and educational tool**, not investment advice and not
a profitable trading system:

- **The model has no proven edge.** Out-of-sample it performs at roughly a coin
  flip (AUC ≈ 0.50) — no better than the simple momentum baseline. The backtest
  is included precisely so you can *see* this, per stock.
- **Backtests can flatter.** A "sit in cash when bearish" strategy can beat
  buy-&-hold just by dodging downturns; that is not the same as predictive skill.
  Trading costs are not modelled.
- **News sentiment is informational**, and (currently) not yet an input to the
  signal — it's shown for context.
- **Free news tier limits apply** (~100 requests/day, possible ~24 h lag).

This candour is intentional: the product's job is to give you an **honest**
picture, including of its own uncertainty.

---

## 7. Roadmap status

| Phase | Feature | Status |
|-------|---------|--------|
| 1 · 1b | Signal definition + UI | ✅ Delivered |
| 2 | Real NSE prices + momentum baseline | ✅ Delivered |
| 3 | Real news + FinBERT sentiment | ✅ Delivered |
| 4 | Trained XGBoost model | ✅ Delivered (honest: no edge yet) |
| 5 | Walk-forward backtest view | ✅ Delivered |
| 6 | Scheduled live polling | ✅ Delivered |
| bonus | MySQL analysis store + keyword search | ✅ Delivered |

**All roadmap phases complete.** The highest-value future enhancement is feeding
FinBERT news sentiment into the model as a feature — the most likely path to a
real, measurable edge.
