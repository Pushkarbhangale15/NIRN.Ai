import { useEffect, useState, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api.js";
import { useLanguage } from "../LanguageContext.jsx";
import { motion } from "framer-motion";

const IconSearch = (props) => (
  <svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" fill="currentColor" viewBox="0 0 24 24" {...props}>
    <path d="M18 10c0-4.41-3.59-8-8-8s-8 3.59-8 8 3.59 8 8 8c1.85 0 3.54-.63 4.9-1.69l5.1 5.1L21.41 20l-5.1-5.1A8 8 0 0 0 18 10M4 10c0-3.31 2.69-6 6-6s6 2.69 6 6-2.69 6-6 6-6-2.69-6-6" />
  </svg>
);

export default function Search() {
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState(params.get("q") ?? "");
  const [hits, setHits] = useState(null);
  const [tookMs, setTookMs] = useState(0);
  const [loading, setLoading] = useState(false);
  const [k, setK] = useState(8);
  const [error, setError] = useState("");

  // OCR Viewer state
  const [selectedGr, setSelectedGr] = useState(null);
  const [ocrText, setOcrText] = useState("");
  const [ocrLoading, setOcrLoading] = useState(false);
  const contentRef = useRef(null);

  const [openDropdown, setOpenDropdown] = useState(null);

  useEffect(() => {
    const handleClick = () => setOpenDropdown(null);
    document.addEventListener("click", handleClick);
    return () => document.removeEventListener("click", handleClick);
  }, []);

  const { t } = useLanguage();

  const runSearch = async (q) => {
    const text = (q ?? query).trim();
    if (text.length < 3) return;
    setLoading(true);
    setError("");
    try {
      const res = await api.searchCorpus(text, k);
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

  const openSource = async (h, language = "", e) => {
    if (e && e.preventDefault) {
      e.preventDefault();
    } else if (language && language.preventDefault) {
      e = language;
      language = "";
      e.preventDefault();
    }
    setSelectedGr(h);
    setOcrLoading(true);
    setOcrText("");
    try {
      const res = await api.getCorpusOcr(h.gr_id, language);
      setOcrText(res.text || "");
    } catch (err) {
      setOcrText("Error loading full text for this GR.");
    } finally {
      setOcrLoading(false);
    }
  };

  const openOfficialPdf = async (h, e) => {
    e.preventDefault();
    try {
      const res = await api.getOfficialGr(h.gr_id, h.department, h.issued_on || "", h.title || "");
      if (res.status === "found" && res.url) {
        window.open(res.url, '_blank');
      } else {
        alert("Official Government Resolution could not be located. Displaying the archived OCR version.");
        openSource(h, 'mr', e);
      }
    } catch (err) {
      alert("Official Government Resolution could not be located. Displaying the archived OCR version.");
      openSource(h, 'mr', e);
    }
  };

  useEffect(() => {
    if (ocrText && contentRef.current) {
      const marks = contentRef.current.getElementsByTagName("mark");
      if (marks.length > 0) {
        marks[0].scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }
  }, [ocrText]);

  const renderHighlightedText = (text, highlightQuery) => {
    if (!highlightQuery || !text) return text;
    const parts = text.split(new RegExp(`(${highlightQuery.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&')})`, 'gi'));
    return parts.map((part, i) =>
      part.toLowerCase() === highlightQuery.toLowerCase() ? (
        <mark key={i} className="highlight-mark">{part}</mark>
      ) : (
        part
      )
    );
  };

  return (
    <main className="container search-page">
      <header className="page-head">
        <div className="eyebrow">{t('search_eyebrow')}</div>
        <h1 className="page-title">{t('search_title')}</h1>
        <p className="page-sub">
          {t('search_sub')}
        </p>
      </header>

      <form
        className="searchbar" style={{ marginTop: 28 }}
        onSubmit={(e) => { e.preventDefault(); runSearch(); }}
      >
        <span className="lead" style={{ display: 'flex', alignItems: 'center' }}><IconSearch width="22" height="22" /></span>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t('search_placeholder')}
          aria-label={t('search_title')}
        />
        <motion.button 
          whileTap={{ scale: 0.9 }} 
          className="go" 
          type="submit" 
          aria-label="Search"
        >
          →
        </motion.button>
      </form>

      <div className="retrieve-row">
        <div>
          <div className="retrieve-label">Results to retrieve</div>
          <div className="retrieve-hint">Default 8 · Range 1–50</div>
        </div>

        <div className="stepper">
          <button
            type="button"
            className="stepper-btn stepper-minus"
            onClick={() => setK((prev) => Math.max(1, (prev || 8) - 1))}
            aria-label="Decrease"
          >
            −
          </button>

          <input
            type="number"
            min="1"
            max="50"
            className="stepper-input"
            value={k}
            onChange={(e) => {
              const value = e.target.value;
              if (value === "") { setK(""); return; }
              const num = Number(value);
              if (num >= 1 && num <= 50) setK(num);
            }}
            onBlur={() => { if (k === "") setK(8); }}
          />

          <button
            type="button"
            className="stepper-btn stepper-plus"
            onClick={() => setK((prev) => Math.min(50, (prev || 8) + 1))}
            aria-label="Increase"
          >
            +
          </button>
        </div>
      </div>

      <div style={{ marginTop: 30 }}>
        {error && <div className="error-box">{error}</div>}

        {loading && (
          <div className="empty-state">
            <div className="big"><span className="spinner" /></div>
            <p>{t('search_searching')}</p>
          </div>
        )}

        {!loading && hits === null && !error && (
          <div className="empty-state">
            <div className="big">🗂️</div>
            <p>{t('search_empty')}</p>
          </div>
        )}

        {!loading && hits !== null && (
          <>
            <p className="ri-sub" style={{ marginBottom: 14 }}>
              {hits.length} {hits.length === 1 ? t('search_result') : t('search_results')} · {tookMs} ms
            </p>
             {hits.map((h, idx) => {
               const uniqueId = `${h.gr_id}_${idx}`;
               return (
                 <div className="result-item" key={uniqueId}>
                   <div style={{ display: "flex", justifyContent: "space-between", gap: 14 }}>
                     <div>
                       <div className="hit-title">{h.title}</div>
                       <div className="hit-meta">
                         {h.department} · <span className="mono">{h.gr_id}</span>
                         {h.issued_on ? ` · ${h.issued_on}` : ""}
                       </div>
                     </div>
                   </div>
                   <div className="ri-sub" style={{ marginTop: 10 }}>{h.snippet}</div>
                   <div className="source-dropdown" onClick={(e) => e.stopPropagation()}>
                     <button 
                       className="source-dropdown-btn" 
                       onClick={() => setOpenDropdown(openDropdown === uniqueId ? null : uniqueId)}
                     >
                       {t('search_view_source')}
                     </button>
                     {openDropdown === uniqueId && (
                       <div className="source-menu">
                         <button onClick={(e) => { setOpenDropdown(null); openSource(h, 'mr', e); }}>View Marathi OCR</button>
                         <button onClick={(e) => { setOpenDropdown(null); openSource(h, 'en', e); }}>View English OCR</button>
                         <button onClick={(e) => { setOpenDropdown(null); openOfficialPdf(h, e); }}>View Official Government Resolution</button>
                       </div>
                     )}
                   </div>
                 </div>
               );
             })}
          </>
        )}
      </div>

      {selectedGr && (
        <>
          <div className="ocr-sidepanel-overlay" onClick={() => setSelectedGr(null)} />
          <div className="ocr-sidepanel">
            <div className="ocr-sidepanel-header">
              <div>
                <h2>{selectedGr.title}</h2>
                <div className="ocr-sidepanel-meta">
                  {selectedGr.department} · <span className="mono">{selectedGr.gr_id}</span>
                  {selectedGr.issued_on ? ` · ${selectedGr.issued_on}` : ""}
                </div>
              </div>
              <button className="ocr-sidepanel-close" onClick={() => setSelectedGr(null)}>×</button>
            </div>
            <div className="ocr-sidepanel-content" ref={contentRef}>
              {ocrLoading ? (
                <div style={{ textAlign: "center", marginTop: "40px" }}>
                  <div className="big"><span className="spinner" /></div>
                  <p>Loading GR text...</p>
                </div>
              ) : (
                renderHighlightedText(ocrText, query)
              )}
            </div>
          </div>
        </>
      )}
    </main>
  );
}