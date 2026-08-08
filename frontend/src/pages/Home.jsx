import { useState, useEffect, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import CountUp from "react-countup";
import { motion } from "framer-motion";

const IconSearch = (props) => (
  <svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" fill="currentColor" viewBox="0 0 24 24" {...props}>
    <path d="M18 10c0-4.41-3.59-8-8-8s-8 3.59-8 8 3.59 8 8 8c1.85 0 3.54-.63 4.9-1.69l5.1 5.1L21.41 20l-5.1-5.1A8 8 0 0 0 18 10M4 10c0-3.31 2.69-6 6-6s6 2.69 6 6-2.69 6-6 6-6-2.69-6-6" />
  </svg>
);

const IconUpload = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" fill="currentColor" viewBox="0 0 24 24">
    <path d="m19.94 7.68-.03-.09a.8.8 0 0 0-.2-.29l-5-5a1 1 0 0 0-.3-.2l-.09-.03a.9.9 0 0 0-.27-.05c-.02 0-.04-.01-.05-.01H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2v-12s-.01-.04-.01-.06c0-.09-.02-.17-.05-.26ZM6 20V4h7v4c0 .55.45 1 1 1h4v11z" />
    <path d="M8 12h2v6H8zm3-2h2v8h-2zm3 4h2v4h-2z" />
  </svg>
);

const IconConflict = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" fill="currentColor" viewBox="0 0 24 24">
    <path d="m21.49 7.13-9-5a.99.99 0 0 0-.97 0l-9.01 5C2.19 7.31 2 7.64 2 8v3c0 .55.45 1 1 1h2v4H3c-.55 0-1 .45-1 1v4c0 .55.45 1 1 1h18c.55 0 1-.45 1-1v-4c0-.55-.45-1-1-1h-2v-4h2c.55 0 1-.45 1-1V8a1 1 0 0 0-.51-.87M7 12h2v4H7zm6 0v4h-2v-4zm7 6v2H4v-2zm-3-2h-2v-4h2zm3-6H4V8.59l8-4.44 8 4.44z" />
    <path d="M12 6a1.5 1.5 0 1 0 0 3 1.5 1.5 0 1 0 0-3" />
  </svg>
);

const IconTemplate = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" fill="currentColor" viewBox="0 0 24 24">
    <path d="M21 7h-5V3c0-.55-.45-1-1-1H9c-.55 0-1 .45-1 1v8H3c-.55 0-1 .45-1 1v9c0 .55.45 1 1 1h18c.55 0 1-.45 1-1V8c0-.55-.45-1-1-1M4 13h4v7H4zm6-1V4h4v16h-4zm10 8h-4V9h4z" />
  </svg>
);

const IconResolutions = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" fill="currentColor" viewBox="0 0 24 24">
    <path d="M5 7h5v6H5zm0 8h10v2H5zm7-4h3v2h-3zm0-4h3v2h-3z" />
    <path d="M21 18c0 .55-.45 1-1 1s-1-.45-1-1V5c0-1.1-.9-2-2-2H3c-1.1 0-2 .9-2 2v13c0 1.65 1.35 3 3 3h16c1.65 0 3-1.35 3-3V6h-2zM4 19c-.55 0-1-.45-1-1V5h14v13c0 .35.07.69.18 1z" />
  </svg>
);

const IconWarning = (props) => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 24 24" {...props}>
    <path d="M1 21h22L12 2 1 21Zm12-3h-2v-2h2Zm0-4h-2v-4h2Z" />
  </svg>
);

const IconGlobe = (props) => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 24 24" {...props}>
    <path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm6.93 6h-2.95a15.7 15.7 0 0 0-1.38-3.56A8.03 8.03 0 0 1 18.93 8ZM12 4.04c.83 1.2 1.48 2.53 1.91 3.96h-3.82c.43-1.43 1.08-2.76 1.91-3.96ZM4.26 14a7.9 7.9 0 0 1 0-4h3.38a16.5 16.5 0 0 0 0 4Zm.81 2h2.95c.35 1.25.8 2.45 1.38 3.56A8.03 8.03 0 0 1 5.07 16Zm2.95-8H5.07a8.03 8.03 0 0 1 4.33-3.56A15.7 15.7 0 0 0 8.02 8ZM12 19.96A15.7 15.7 0 0 1 10.09 16h3.82a15.7 15.7 0 0 1-1.91 3.96ZM14.4 14H9.6a14.5 14.5 0 0 1 0-4h4.8a14.5 14.5 0 0 1 0 4Zm.19 5.56c.58-1.11 1.03-2.31 1.38-3.56h2.95a8.03 8.03 0 0 1-4.33 3.56ZM16.36 14a16.5 16.5 0 0 0 0-4h3.38a7.9 7.9 0 0 1 0 4Z" />
  </svg>
);

const IconClose = (props) => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="currentColor" viewBox="0 0 24 24" {...props}>
    <path d="M18.3 5.71 12 12.01l-6.3-6.3-1.4 1.41 6.29 6.3-6.3 6.29 1.41 1.41 6.3-6.3 6.29 6.3 1.41-1.41-6.3-6.29 6.3-6.3z" />
  </svg>
);

const FEATURES = [
  {
    icon: <IconSearch />, color: "c-blue", underline: "c-blue",
    titleKey: "feat_search_title",
    descKey: "feat_search_desc",
    link: "#search-box", labelKey: "feat_search_label",
    isScroll: true,
  },
  {
    icon: <IconUpload />, color: "c-yellow", underline: "c-yellow",
    titleKey: "feat_upload_title",
    descKey: "feat_upload_desc",
    link: "/draft", labelKey: "feat_upload_label",
  },
  {
    icon: <IconConflict />, color: "c-red", underline: "c-red",
    titleKey: "feat_conflict_title",
    descKey: "feat_conflict_desc",
    link: "/draft", labelKey: "feat_conflict_label",
  },
  {
    icon: <IconTemplate />, color: "c-ink", underline: "c-ink",
    titleKey: "feat_template_title",
    descKey: "feat_template_desc",
    link: "/draft", labelKey: "feat_template_label",
  },
];

import { useLanguage } from "../LanguageContext.jsx";
import { api } from "../api.js";

export default function Home() {
  const [query, setQuery] = useState("");
  const { t, siteLanguage } = useLanguage();

  const [grNumber, setGrNumber] = useState("");
  const [foundGr, setFoundGr] = useState(null);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupError, setLookupError] = useState("");
  const [promptOfficial, setPromptOfficial] = useState(false);
  const [pendingGrNumber, setPendingGrNumber] = useState("");

  // Semantic search states
  const [hits, setHits] = useState(null);
  const [tookMs, setTookMs] = useState(0);
  const [loading, setLoading] = useState(false);
  const [k, setK] = useState(8);
  const [searchError, setSearchError] = useState("");

  // OCR Viewer state
  const [selectedGr, setSelectedGr] = useState(null);
  const [ocrText, setOcrText] = useState("");
  const [ocrLoading, setOcrLoading] = useState(false);
  const contentRef = useRef(null);
  const resultsSectionRef = useRef(null);
  const searchInputRef = useRef(null);

  const [openDropdown, setOpenDropdown] = useState(null);

  useEffect(() => {
    const handleClick = () => setOpenDropdown(null);
    document.addEventListener("click", handleClick);
    return () => document.removeEventListener("click", handleClick);
  }, []);

  const runSearch = async (q) => {
    const text = (q ?? query).trim();
    if (text.length < 3) return;
    setLoading(true);
    setSearchError("");
    if (q) setQuery(q);
    try {
      const res = await api.searchCorpus(text, k);
      setHits(res.hits);
      setTookMs(res.took_ms);
      
      // Scroll to results section smoothly
      setTimeout(() => {
        resultsSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 100);
    } catch (err) {
      setSearchError(err.message || "An error occurred during search.");
    } finally {
      setLoading(false);
    }
  };

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

  const handleGrLookup = async () => {
    const id = grNumber.trim();
    if (!id) return;
    setLookupLoading(true);
    setLookupError("");
    setFoundGr(null);
    setPromptOfficial(false);
    setPendingGrNumber("");
    try {
      const res = await api.getCorpusOcr(id);
      if (res && res.gr_id) {
        setFoundGr(res);
      } else {
        setPendingGrNumber(id);
        setPromptOfficial(true);
      }
    } catch (err) {
      setPendingGrNumber(id);
      setPromptOfficial(true);
    } finally {
      setLookupLoading(false);
    }
  };

  const openOfficialPdfForFoundGr = async () => {
    if (!foundGr) return;
    try {
      const res = await api.getOfficialGr(foundGr.gr_id, foundGr.department, "", foundGr.title || "");
      if (res.status === "found" && res.url) {
        window.open(res.url, '_blank');
      } else {
        alert("Official Government Resolution could not be located.");
      }
    } catch (err) {
      alert("Official Government Resolution could not be located.");
    }
  };

  const tryQueries = [
    t('home_sug_1'),
    t('home_sug_2'),
    t('home_sug_3'),
  ];

  return (
    <main>
      <section className="hero">

        <span className="geo geo-sq-red" />
        <span className="geo geo-bar-yellow" />
        <span className="geo geo-circle-tan" />

        <div className="container">
          <div className="hero-grid">
            <div className="hero-copy">
              <h1 className="display">
                <span className="display-line">{t('home_title_line1')}</span>
                <span className="display-line accent">{t('home_title_line2')}</span>
              </h1>
              <div className="underline-blue" />

            </div>

            <div className="hero-stat">
              <div className="stat-icon"><IconResolutions /></div>
              <div className="stat-number">
                <CountUp
                  start={96000}
                  end={99000}
                  duration={2.5}
                  separator=","
                  suffix="+"
                  enableScrollSpy
                  scrollSpyOnce
                />
              </div>
              <div className="stat-label">Government Resolutions</div>
              <div className="stat-sub">Across departments. At your fingertips.</div>
            </div>
          </div>

          <form
            className="searchbar"
            id="search-box"
            onSubmit={(e) => { e.preventDefault(); runSearch(); }}
          >
            <span className="lead"><IconSearch width="24" height="24" /></span>
            <input
              ref={searchInputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t('home_search_placeholder')}
              aria-label={t('home_search_placeholder')}
            />
            <button className="go" type="submit" aria-label="Search">→</button>
          </form>

          <div className="try-row">
            <span className="try-label">{t('home_try_label')}</span>
            {tryQueries.map((q) => (
              <button key={q} className="chip" onClick={() => runSearch(q)}>
                {q} <span className="arr">↗</span>
              </button>
            ))}
          </div>

          {/* GR ID lookup section */}
          <div className="gr-lookup-section">
            <div className="gr-lookup-label-row">
              <span className="gr-lookup-label">{t('home_gr_lookup_label')}</span>
              <span className="gr-lookup-tooltip-wrap" tabIndex={0}>
                <span className="gr-lookup-tooltip-icon" aria-label={t('home_gr_lookup_tooltip')}>i</span>
                <span className="gr-lookup-tooltip-bubble">{t('home_gr_lookup_tooltip')}</span>
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
              <form
                className="searchbar gr-number-searchbar"
                onSubmit={(e) => { e.preventDefault(); handleGrLookup(); }}
                style={{ marginTop: 0, flex: '1', minWidth: '280px' }}
              >
                <span className="lead" style={{ backgroundColor: 'var(--ink)' }}>#</span>
                <input
                  value={grNumber}
                  onChange={(e) => setGrNumber(e.target.value)}
                  placeholder={t('home_gr_number_placeholder')}
                  aria-label={t('home_gr_number_placeholder')}
                />
                <button className="go" type="submit" style={{ backgroundColor: 'var(--ink)' }} aria-label="Find GR">
                  {lookupLoading ? '...' : '→'}
                </button>
              </form>

              {foundGr && (
                <button
                  type="button"
                  onClick={openOfficialPdfForFoundGr}
                  className="chip"
                  style={{
                    height: '42px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    background: 'var(--red)',
                    color: '#fff',
                    border: '2px solid var(--ink)',
                    borderRadius: '12px',
                    padding: '0 16px',
                    cursor: 'pointer',
                    fontWeight: 'bold',
                    boxShadow: '0 3px 0 var(--ink)',
                    transition: 'transform 0.1s'
                  }}
                >
                  <IconGlobe /> View Official GR ↗
                </button>
              )}
            </div>
          </div>

          {lookupError && (
            <div className="lookup-error" style={{ color: 'var(--red)', marginTop: '12px', fontSize: '15px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <IconWarning /> {lookupError}
            </div>
          )}

          {promptOfficial && (
            <div className="gr-card" style={{
              marginTop: '16px',
              padding: '20px',
              border: '2px solid var(--ink)',
              borderRadius: '12px',
              background: 'var(--paper)',
              boxShadow: '0 4px 0 var(--ink)',
              textAlign: 'left'
            }}>
              <p style={{ margin: '0 0 16px 0', fontSize: '16px', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <IconWarning /> {pendingGrNumber} could not be found locally. Would you like to view the official PDF?
              </p>
              <div style={{ display: 'flex', gap: '12px' }}>
                <button
                  type="button"
                  onClick={async () => {
                    setPromptOfficial(false);
                    try {
                      const res = await api.getOfficialGr(pendingGrNumber, "Default");
                      if (res.status === "found" && res.url) {
                        window.open(res.url, '_blank');
                      } else {
                        window.open(`https://gr.maharashtra.gov.in/Site/Upload/Government%20Resolutions/Marathi/${pendingGrNumber}.pdf`, '_blank');
                      }
                    } catch (err) {
                      window.open(`https://gr.maharashtra.gov.in/Site/Upload/Government%20Resolutions/Marathi/${pendingGrNumber}.pdf`, '_blank');
                    }
                  }}
                  className="chip"
                  style={{
                    background: 'var(--blue)',
                    color: '#fff',
                    border: '2px solid var(--ink)',
                    borderRadius: '8px',
                    padding: '8px 16px',
                    cursor: 'pointer',
                    fontWeight: 'bold',
                    boxShadow: '0 2px 0 var(--ink)'
                  }}
                >
                  Yes
                </button>
                <button
                  type="button"
                  onClick={() => setPromptOfficial(false)}
                  className="chip"
                  style={{
                    background: '#e0e0e0',
                    color: 'var(--ink)',
                    border: '2px solid var(--ink)',
                    borderRadius: '8px',
                    padding: '8px 16px',
                    cursor: 'pointer',
                    fontWeight: 'bold',
                    boxShadow: '0 2px 0 var(--ink)'
                  }}
                >
                  No
                </button>
              </div>
            </div>
          )}


          {foundGr && (
            <div className="gr-card" style={{
              marginTop: '24px',
              padding: '24px',
              border: '2px solid var(--ink)',
              borderRadius: '12px',
              background: 'var(--paper)',
              boxShadow: '0 4px 0 var(--ink)',
              position: 'relative'
            }}>
              <button
                onClick={() => setFoundGr(null)}
                style={{
                  position: 'absolute',
                  top: '16px',
                  right: '16px',
                  background: 'none',
                  border: 'none',
                  fontSize: '20px',
                  cursor: 'pointer',
                  color: 'var(--ink)'
                }}
              >
                <IconClose />
              </button>
              <span className="badge" style={{
                display: 'inline-block',
                padding: '4px 8px',
                background: 'var(--blue)',
                color: '#fff',
                borderRadius: '6px',
                fontSize: '12px',
                fontWeight: 'bold',
                marginBottom: '12px'
              }}>
                {t('home_gr_number_result_title')}
              </span>
              <h3 style={{ margin: '0 0 8px 0', fontSize: '20px', textAlign: 'left' }}>{foundGr.title}</h3>
              <p style={{ margin: '0 0 16px 0', color: '#666', fontSize: '14px', textAlign: 'left' }}>
                <strong>Department:</strong> {foundGr.department.replace(/_/g, ' ')} | <strong>ID:</strong> {foundGr.gr_id}
              </p>
              <div style={{
                maxHeight: '300px',
                overflowY: 'auto',
                padding: '16px',
                background: '#f8f6f2',
                borderRadius: '8px',
                border: '1px solid #ddd',
                fontFamily: 'monospace',
                fontSize: '13px',
                whiteSpace: 'pre-wrap',
                textAlign: 'left'
              }}>
                {foundGr.text}
              </div>
            </div>
          )}

          {/* Semantic Search Results Section */}
          <div ref={resultsSectionRef} style={{ marginTop: '30px', scrollMarginTop: '20px' }}>
            {query.trim().length >= 3 && hits !== null && (
              <div className="retrieve-row" style={{ marginTop: '20px', marginBottom: '20px' }}>
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
            )}

            {searchError && <div className="error-box" style={{ color: 'var(--red)', background: '#fee2e2', border: '1px solid #fca5a5', padding: '12px', borderRadius: '8px', marginBottom: '16px' }}>{searchError}</div>}

            {loading && (
              <div className="empty-state" style={{ padding: '40px 20px', textAlign: 'center' }}>
                <div className="big"><span className="spinner" /></div>
                <p style={{ marginTop: '12px' }}>{t('search_searching')}</p>
              </div>
            )}

            {!loading && hits !== null && (
              <div style={{ marginBottom: '40px' }}>
                <p className="ri-sub" style={{ marginBottom: 14, textAlign: 'left', fontWeight: 'bold' }}>
                  {hits.length} {hits.length === 1 ? t('search_result') : t('search_results')}
                </p>
                {hits.map((h, idx) => {
                  const uniqueId = `${h.gr_id}_${idx}`;
                  return (
                    <div className="result-item" key={uniqueId} style={{ background: 'var(--paper)', border: '2px solid var(--ink)', borderRadius: '12px', padding: '20px', marginBottom: '16px', boxShadow: '0 4px 0 var(--ink)', textAlign: 'left' }}>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 14 }}>
                        <div>
                          <div className="hit-title" style={{ fontSize: '18px', fontWeight: 'bold', marginBottom: '4px' }}>{h.title}</div>
                          <div className="hit-meta" style={{ fontSize: '13px', color: '#666' }}>
                            {h.department} · <span className="mono">{h.gr_id}</span>
                            {h.issued_on ? ` · ${h.issued_on}` : ""}
                          </div>
                        </div>
                      </div>
                      <div className="ri-sub" style={{ marginTop: 10, fontSize: '14px', color: '#444' }}>{h.snippet}</div>
                      <div className="source-dropdown" onClick={(e) => e.stopPropagation()} style={{ marginTop: '12px', position: 'relative', display: 'inline-block' }}>
                        <button 
                          className="source-dropdown-btn" 
                          onClick={() => setOpenDropdown(openDropdown === uniqueId ? null : uniqueId)}
                          style={{
                            background: '#f3f4f6',
                            border: '1px solid #d1d5db',
                            borderRadius: '6px',
                            padding: '6px 12px',
                            fontSize: '13px',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px'
                          }}
                        >
                          {t('search_view_source')}
                        </button>
                        {openDropdown === uniqueId && (
                          <div className="source-menu" style={{
                            position: 'absolute',
                            top: '100%',
                            left: 0,
                            zIndex: 100,
                            background: '#fff',
                            border: '1px solid #d1d5db',
                            borderRadius: '6px',
                            boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)',
                            marginTop: '4px',
                            display: 'flex',
                            flexDirection: 'column',
                            minWidth: '220px'
                          }}>
                            <button 
                              onClick={(e) => { setOpenDropdown(null); openSource(h, 'mr', e); }}
                              style={{ padding: '8px 12px', background: 'none', border: 'none', textAlign: 'left', cursor: 'pointer', fontSize: '13px', borderBottom: '1px solid #f3f4f6' }}
                            >
                              View Marathi OCR
                            </button>
                            <button 
                              onClick={(e) => { setOpenDropdown(null); openSource(h, 'en', e); }}
                              style={{ padding: '8px 12px', background: 'none', border: 'none', textAlign: 'left', cursor: 'pointer', fontSize: '13px', borderBottom: '1px solid #f3f4f6' }}
                            >
                              View English OCR
                            </button>
                            <button 
                              onClick={(e) => { setOpenDropdown(null); openOfficialPdf(h, e); }}
                              style={{ padding: '8px 12px', background: 'none', border: 'none', textAlign: 'left', cursor: 'pointer', fontSize: '13px' }}
                            >
                              View Official Government Resolution
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {selectedGr && (
            <>
              <div className="ocr-sidepanel-overlay" onClick={() => setSelectedGr(null)} />
              <div className="ocr-sidepanel" style={{ zIndex: 1000 }}>
                <div className="ocr-sidepanel-header">
                  <div>
                    <h2 style={{ fontSize: '20px', margin: '0 0 8px 0', textAlign: 'left' }}>{selectedGr.title}</h2>
                    <div className="ocr-sidepanel-meta" style={{ fontSize: '13px', color: '#666', textAlign: 'left' }}>
                      {selectedGr.department} · <span className="mono">{selectedGr.gr_id}</span>
                      {selectedGr.issued_on ? ` · ${selectedGr.issued_on}` : ""}
                    </div>
                  </div>
                  <button className="ocr-sidepanel-close" onClick={() => setSelectedGr(null)}>×</button>
                </div>
                <div className="ocr-sidepanel-content" ref={contentRef} style={{ padding: '20px', maxHeight: '70vh', overflowY: 'auto', textAlign: 'left' }}>
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

          <div className="features">
            {FEATURES.map((f) => {
              const handleClick = (e) => {
                if (f.isScroll) {
                  e.preventDefault();
                  searchInputRef.current?.focus();
                  document.getElementById("search-box")?.scrollIntoView({ behavior: "smooth" });
                }
              };
              return (
                <div className="feature" key={f.titleKey}>
                  <div className={`f-icon ${f.color}`}>{f.icon}</div>
                  <div className={`f-underline ${f.underline}`} />
                  <div className="f-title">{t(f.titleKey)}</div>
                  <p className="f-desc">{t(f.descKey)}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>
    </main>
  );
}