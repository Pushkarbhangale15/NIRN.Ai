import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import CountUp from "react-countup";

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

const FEATURES = [
  {
    icon: <IconSearch />, color: "c-blue", underline: "c-blue",
    titleKey: "feat_search_title",
    descKey: "feat_search_desc",
    link: "/search", labelKey: "feat_search_label",
  },
  {
    icon: <IconUpload />, color: "c-yellow", underline: "c-yellow",
    titleKey: "feat_upload_title",
    descKey: "feat_upload_desc",
    link: "/analyze", labelKey: "feat_upload_label",
  },
  {
    icon: <IconConflict />, color: "c-red", underline: "c-red",
    titleKey: "feat_conflict_title",
    descKey: "feat_conflict_desc",
    link: "/analyze", labelKey: "feat_conflict_label",
  },
  {
    icon: <IconTemplate />, color: "c-ink", underline: "c-ink",
    titleKey: "feat_template_title",
    descKey: "feat_template_desc",
    link: "/analyze", labelKey: "feat_template_label",
  },
];

import { useLanguage } from "../LanguageContext.jsx";
import { api } from "../api.js";

export default function Home() {
  const [query, setQuery] = useState("");
  const navigate = useNavigate();
  const { t, siteLanguage } = useLanguage();

  const [grNumber, setGrNumber] = useState("");
  const [foundGr, setFoundGr] = useState(null);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupError, setLookupError] = useState("");
  const [promptOfficial, setPromptOfficial] = useState(false);
  const [pendingGrNumber, setPendingGrNumber] = useState("");

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

  const goSearch = (q) => {
    const text = (q ?? query).trim();
    if (text) navigate(`/search?q=${encodeURIComponent(text)}`);
    else navigate("/search");
  };

  const tryQueries = [
    t('home_sug_1'),
    t('home_sug_2'),
    t('home_sug_3'),
  ];

  return (
    <main>
      <section className="hero">
        <span className="geo geo-half-blue" />
        <span className="geo geo-sq-red" />
        <span className="geo geo-bar-yellow" />
        <span className="geo geo-circle-tan" />

        <div className="container">
          <div className="hero-grid">
            <div className="hero-copy">
              <h1 className="display">
                <span className="brand-red">NIRN.Ai</span> {t('home_title_2')}
              </h1>
              <div className="underline-blue" />

            </div>

            <div className="hero-stat">
              <div className="stat-icon"><IconResolutions /></div>
              <div className="stat-number">
                <CountUp
                  start={95000}
                  end={98950}
                  duration={2.5}
                  separator=","
                  suffix="+"
                  enableScrollSpy
                  scrollSpyOnce
                />
              </div>
              <div className="stat-label">Government Resolutions</div>
              <div className="stat-sub">Across departments. At your fingertips.</div>
              {/* <div className="stat-number">{t('home_stat_num')}</div>
              <div className="stat-label">{t('home_stat_label')}</div>
              <div className="stat-sub">{t('home_stat_sub')}</div> */}
            </div>
          </div>

          <form
            className="searchbar"
            onSubmit={(e) => { e.preventDefault(); goSearch(); }}
          >
            <span className="lead"><IconSearch width="24" height="24" /></span>
            <input
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
              <button key={q} className="chip" onClick={() => goSearch(q)}>
                {q} <span className="arr">↗</span>
              </button>
            ))}
          </div>

          {/* GR ID lookup searchbar */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap', marginTop: '24px' }}>
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
                🌐 View Official GR ↗
              </button>
            )}
          </div>

          {lookupError && (
            <div className="lookup-error" style={{ color: 'var(--red)', marginTop: '12px', fontSize: '15px' }}>
              ⚠️ {lookupError}
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
              <p style={{ margin: '0 0 16px 0', fontSize: '16px', fontWeight: 'bold' }}>
                ⚠️ {pendingGrNumber} could not be found locally. Would you like to view the official PDF?
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
                ✕
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

          <div className="features">
            {FEATURES.map((f) => (
              <div className="feature" key={f.titleKey}>
                <div className={`f-icon ${f.color}`}>{f.icon}</div>
                <div className={`f-underline ${f.underline}`} />
                <div className="f-title">{t(f.titleKey)}</div>
                <p className="f-desc">{t(f.descKey)}</p>
                <Link className="f-link" to={f.link}>
                  {t(f.labelKey)} <span>→</span>
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}