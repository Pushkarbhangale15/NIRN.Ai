import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api.js";

export default function Search() {
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState(params.get("q") ?? "");
  const [hits, setHits] = useState(null);
  const [tookMs, setTookMs] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const runSearch = async (q) => {
    const text = (q ?? query).trim();
    if (text.length < 3) return;
    setLoading(true);
    setError("");
    try {
      const res = await api.searchCorpus(text);
      setHits(res.hits);
      setTookMs(res.took_ms);
      setParams({ q: text });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // If the home page sent us here with ?q=..., run it immediately.
  useEffect(() => {
    const q = params.get("q");
    if (q) runSearch(q);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="container search-page">
      <header className="page-head">
        <div className="eyebrow">Semantic Search</div>
        <h1 className="page-title">Search the Corpus</h1>
        <p className="page-sub">
          Search past Government Resolutions by meaning, not keywords —
          a query about “late admission” finds “delayed enrolment procedure”.
        </p>
      </header>

      <form
        className="searchbar" style={{ marginTop: 28 }}
        onSubmit={(e) => { e.preventDefault(); runSearch(); }}
      >
        <span className="lead">🔍</span>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. lateral entry intake in technical institutions"
          aria-label="Search the GR corpus"
        />
        <button className="go" type="submit" aria-label="Search">→</button>
      </form>

      <div style={{ marginTop: 30 }}>
        {error && <div className="error-box">{error}</div>}

        {loading && (
          <div className="empty-state">
            <div className="big"><span className="spinner" /></div>
            <p>Searching the corpus…</p>
          </div>
        )}

        {!loading && hits === null && !error && (
          <div className="empty-state">
            <div className="big">🗂️</div>
            <p>Results appear here. Try one of the suggestions on the home page.</p>
          </div>
        )}

        {!loading && hits !== null && (
          <>
            <p className="ri-sub" style={{ marginBottom: 14 }}>
              {hits.length} result{hits.length === 1 ? "" : "s"} · {tookMs} ms
            </p>
            {hits.map((h) => (
              <div className="result-item" key={h.gr_id}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 14 }}>
                  <div>
                    <div className="hit-title">{h.title}</div>
                    <div className="hit-meta">
                      {h.department} · <span className="mono">{h.gr_id}</span>
                      {h.issued_on ? ` · ${h.issued_on}` : ""}
                    </div>
                  </div>
                  <div className="hit-score">{(h.score * 100).toFixed(0)}%</div>
                </div>
                <div className="ri-sub" style={{ marginTop: 10 }}>{h.snippet}</div>
                {h.source_url && (
                  <a className="f-link" style={{ marginTop: 10, display: "inline-flex" }}
                     href={h.source_url} target="_blank" rel="noreferrer">
                    View source →
                  </a>
                )}
              </div>
            ))}
          </>
        )}
      </div>
    </main>
  );
}
