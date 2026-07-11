import { useEffect, useRef, useState } from "react";
import { searchSymbols } from "../api.js";
import { displayTicker } from "./SignalCard.jsx";

// Keyword typeahead -> pick a matched NSE/BSE stock, then run its analysis.
export default function SearchBar({ onSearch, busy }) {
  const [value, setValue] = useState("");
  const [matches, setMatches] = useState([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [loading, setLoading] = useState(false);
  const boxRef = useRef(null);

  useEffect(() => {
    const q = value.trim();
    if (q.length < 2) {
      setMatches([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    const id = setTimeout(() => {
      searchSymbols(q)
        .then((res) => {
          setMatches(res);
          setOpen(true);
          setActive(-1);
        })
        .catch(() => setMatches([]))
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(id);
  }, [value]);

  useEffect(() => {
    const onClick = (e) => {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  function choose(item) {
    setValue("");
    setMatches([]);
    setOpen(false);
    setActive(-1);
    onSearch(item.symbol, item.name);
  }

  function submit(e) {
    e.preventDefault();
    if (open && active >= 0 && matches[active]) return choose(matches[active]);
    if (matches.length > 0) return choose(matches[0]);
    const t = value.trim().toUpperCase();
    if (t) onSearch(t);
  }

  function onKeyDown(e) {
    if (!open || matches.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, matches.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div className="search-wrap" ref={boxRef}>
      <form className="search-box" onSubmit={submit} autoComplete="off">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="11" cy="11" r="7" />
          <path d="M21 21l-4.3-4.3" />
        </svg>
        <input
          type="text"
          placeholder="Search any NSE stock — try “tata”"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onFocus={() => matches.length && setOpen(true)}
          onKeyDown={onKeyDown}
          spellCheck="false"
          aria-label="Search a stock"
          role="combobox"
          aria-expanded={open}
        />
        <button className="search-btn" type="submit" disabled={busy}>
          {busy ? "…" : "Analyze"}
        </button>
      </form>

      {open && (loading || matches.length > 0) && (
        <ul className="typeahead" role="listbox">
          {loading && matches.length === 0 && <li className="ta-item muted">Searching…</li>}
          {matches.map((m, i) => (
            <li
              key={m.symbol}
              role="option"
              aria-selected={i === active}
              className={`ta-item ${i === active ? "active" : ""}`}
              onMouseEnter={() => setActive(i)}
              onMouseDown={(e) => {
                e.preventDefault();
                choose(m);
              }}
            >
              <b>{m.name}</b>
              <span>
                {displayTicker(m.symbol)} · {m.exchange === "NSI" ? "NSE" : m.exchange}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
