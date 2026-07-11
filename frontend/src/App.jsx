import { useEffect, useState, useCallback, useRef } from "react";
import {
  fetchIndices,
  fetchTopStocks,
  fetchNews,
  fetchHistory,
  analyzeTicker,
  fetchModelInfo,
  fetchScheduler,
  fetchForecast,
  openSignalSocket,
} from "./api.js";
import SignalCard, { displayTicker } from "./components/SignalCard.jsx";
import NewsFeed from "./components/NewsFeed.jsx";
import SearchBar from "./components/SearchBar.jsx";
import TopPick from "./components/TopPick.jsx";
import DetailView from "./components/DetailView.jsx";

export default function App() {
  const [indices, setIndices] = useState([]);
  const [topStocks, setTopStocks] = useState([]);
  const [extraSignals, setExtraSignals] = useState([]); // searched tickers
  const [news, setNews] = useState([]);
  const [selected, setSelected] = useState(null);
  const [history, setHistory] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [live, setLive] = useState(false);
  const [error, setError] = useState(null);
  const [searching, setSearching] = useState(false);
  const [searchMsg, setSearchMsg] = useState(null);
  const [modelInfo, setModelInfo] = useState(null);
  const [sched, setSched] = useState(null);
  const detailRef = useRef(null);

  const scrollToDetail = useCallback(() => {
    requestAnimationFrame(() =>
      detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })
    );
  }, []);

  const handleSelect = useCallback(
    (ticker) => {
      setSelected(ticker);
      scrollToDetail();
    },
    [scrollToDetail]
  );

  // Search any ticker -> pull its predictive snapshot and drill into it.
  const handleSearch = useCallback(
    async (ticker, pickedName) => {
      setSearching(true);
      setSearchMsg(null);
      try {
        const res = await analyzeTicker(ticker);
        if (!res.found) {
          setSearchMsg(`No NSE data for "${ticker}".`);
          return;
        }
        const symbol = res.ticker;
        const sig = { ...res.signal, name: pickedName || res.name };
        setExtraSignals((prev) => [sig, ...prev.filter((s) => s.ticker !== symbol)]);
        setNews((prev) => [...res.news, ...prev.filter((a) => a.ticker !== symbol)]);
        setSelected(symbol);
        setSearchMsg(`Showing ${sig.name}`);
        scrollToDetail();
      } catch (e) {
        setSearchMsg(`Could not analyze "${ticker}".`);
      } finally {
        setSearching(false);
      }
    },
    [scrollToDetail]
  );

  // Initial load.
  useEffect(() => {
    (async () => {
      try {
        const [ix, ts, nw] = await Promise.all([
          fetchIndices(),
          fetchTopStocks(10),
          fetchNews(20),
        ]);
        setIndices(ix);
        setTopStocks(ts);
        setNews(nw);
        setSelected(ix[0]?.ticker ?? null); // no scroll on first load
      } catch (e) {
        setError("Cannot reach the API. Is the backend running on :8000?");
      }
    })();
    fetchModelInfo().then(setModelInfo).catch(() => setModelInfo(null));
  }, []);

  // Live index updates over WebSocket.
  useEffect(() => {
    const ws = openSignalSocket((data) => {
      setIndices(data);
      setLive(true);
    });
    ws.onclose = () => setLive(false);
    ws.onerror = () => setLive(false);
    return () => ws.close();
  }, []);

  // Periodically refresh the ranked stock list.
  useEffect(() => {
    const id = setInterval(() => {
      fetchTopStocks(10).then(setTopStocks).catch(() => {});
    }, 30000);
    return () => clearInterval(id);
  }, []);

  // Refresh chart + forecast whenever the selected symbol changes.
  useEffect(() => {
    if (!selected) return;
    setHistory(null);
    setForecast(null);
    fetchHistory(selected).then(setHistory).catch(() => setHistory(null));
    fetchForecast(selected).then(setForecast).catch(() => setForecast(null));
  }, [selected]);

  // Periodically refresh the news feed.
  useEffect(() => {
    const id = setInterval(() => {
      fetchNews(20).then(setNews).catch(() => {});
    }, 15000);
    return () => clearInterval(id);
  }, []);

  // Poll the background scheduler for the "synced" badge.
  useEffect(() => {
    const tick = () => fetchScheduler().then(setSched).catch(() => {});
    tick();
    const id = setInterval(tick, 30000);
    return () => clearInterval(id);
  }, []);

  const syncedText = (() => {
    const iso = sched?.last_run;
    const every = sched?.interval_minutes ? ` · every ${sched.interval_minutes}m` : "";
    if (!iso) return live ? "Live" : sched?.enabled ? "Sync pending…" : "Connecting…";
    const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
    const when = mins < 1 ? "just now" : mins < 60 ? `${mins}m ago` : `${Math.round(mins / 60)}h ago`;
    return `Synced ${when}${every}`;
  })();

  const selectedSignal = [...indices, ...topStocks, ...extraSignals].find(
    (s) => s.ticker === selected
  );
  const selectedName = selectedSignal?.name || (selected ? displayTicker(selected) : "");

  return (
    <>
      <header className="topbar">
        <div className="header-inner">
          <div className="brand">
            <span className="brand-mark" />
            <span className="brand-name">Signal Desk</span>
          </div>
          <SearchBar onSearch={handleSearch} busy={searching} />
          <div className="header-right">
            {searchMsg && <span className="search-msg">{searchMsg}</span>}
            <div className="sync-badge">
              <span className={`pulse ${live ? "" : "off"}`} />
              {syncedText}
            </div>
          </div>
        </div>
      </header>

      <div className="wrap">
        {error && <div className="banner error">{error}</div>}

        <TopPick signals={indices} onSelect={handleSelect} />

        <section className="section">
          <div className="eyebrow">Live signals · indices</div>
          <p className="section-desc">
            NIFTY 50, BANK NIFTY, SENSEX and FIN NIFTY, refreshed over WebSocket. Click an index to
            drill into its price forecast and backtest.
            {modelInfo?.available &&
              ` Model: trained XGBoost (5-day), out-of-sample AUC ${modelInfo.oos_auc ?? "—"}.`}
          </p>
          <div className="signals-grid">
            {indices.length === 0 && <p className="section-desc">Loading indices…</p>}
            {indices.map((s) => (
              <SignalCard
                key={s.ticker}
                signal={s}
                name={s.name}
                selected={s.ticker === selected}
                onSelect={handleSelect}
              />
            ))}
          </div>
        </section>

        <section className="section">
          <div className="eyebrow">Top suggested stocks</div>
          <p className="section-desc">
            The strongest-ranked names from the tracked NSE universe (heuristic ranking of model
            signals — not advice). Click any card to analyse it.
          </p>
          <div className="signals-grid">
            {topStocks.length === 0 && <p className="section-desc">Loading stocks…</p>}
            {topStocks.map((s) => (
              <SignalCard
                key={s.ticker}
                signal={s}
                name={s.name}
                selected={s.ticker === selected}
                onSelect={handleSelect}
              />
            ))}
          </div>
        </section>

        <section className="section">
          <div className="eyebrow">Live news feed</div>
          <p className="section-desc">
            Headlines from NewsAPI, scored by FinBERT as they arrive. Click a headline's ticker to
            jump to its analysis.
          </p>
          <NewsFeed articles={news} onSelectTicker={handleSelect} />
        </section>

        <DetailView
          ref={detailRef}
          selected={selected}
          name={selectedName}
          signal={selectedSignal}
          history={history}
          forecast={forecast}
        />
      </div>
    </>
  );
}
