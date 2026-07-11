// Thin API layer. All paths go through Vite's dev proxy to FastAPI on :8000.

async function getJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

export const fetchWatchlist = () => getJSON("/api/watchlist");
export const fetchSignals = () => getJSON("/api/signals");
export const fetchIndices = () => getJSON("/api/indices");
export const fetchTopStocks = (limit = 10) => getJSON(`/api/top-stocks?limit=${limit}`);
export const fetchNews = (limit = 12) => getJSON(`/api/news?limit=${limit}`);
export const fetchHistory = (ticker, period = "6mo") =>
  getJSON(`/api/history/${encodeURIComponent(ticker)}?period=${period}`);
export const fetchSuggestions = () => getJSON("/api/suggestions");
export const analyzeTicker = (ticker, period = "6mo") =>
  getJSON(`/api/analyze/${encodeURIComponent(ticker)}?period=${period}`);
export const fetchModelInfo = () => getJSON("/api/model");
export const fetchBacktest = (ticker) =>
  getJSON(`/api/backtest/${encodeURIComponent(ticker)}`);
export const fetchScheduler = () => getJSON("/api/scheduler");
export const searchSymbols = (q) =>
  getJSON(`/api/search?q=${encodeURIComponent(q)}`);
export const fetchForecast = (ticker) =>
  getJSON(`/api/forecast/${encodeURIComponent(ticker)}`);

// Open the live-signals WebSocket. Returns the socket so the caller can close it.
export function openSignalSocket(onSignals) {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onmessage = (evt) => {
    try {
      const msg = JSON.parse(evt.data);
      if (msg.type === "signals") onSignals(msg.data);
    } catch {
      /* ignore malformed frames */
    }
  };
  return ws;
}
