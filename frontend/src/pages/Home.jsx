import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

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

const TRY_QUERIES = [
  "GR about work from home policy",
  "Leave rules for government employees",
  "Latest circulars on procurement",
];

const FEATURES = [
  {
    icon: <IconSearch />, color: "c-blue", underline: "c-blue",
    title: "Semantic Search",
    desc: "Understand natural language and find relevant GRs instantly.",
    link: "/search", label: "Search now",
  },
  {
    icon: <IconUpload />, color: "c-yellow", underline: "c-yellow",
    title: "Upload & Analyze",
    desc: "Submit a draft GR and get AI-powered alignment checks instantly.",
    link: "/analyze", label: "Upload GR",
  },
  {
    icon: <IconConflict />, color: "c-red", underline: "c-red",
    title: "Conflict Detection",
    desc: "Flag clashes with existing resolutions across departments.",
    link: "/analyze", label: "Explore",
  },
  {
    icon: <IconTemplate />, color: "c-ink", underline: "c-ink",
    title: "Template Checks",
    desc: "Enforce the Manual of Office Procedure rule by rule.",
    link: "/analyze", label: "View checks",
  },
];

export default function Home() {
  const [query, setQuery] = useState("");
  const navigate = useNavigate();

  const goSearch = (q) => {
    const text = (q ?? query).trim();
    if (text) navigate(`/search?q=${encodeURIComponent(text)}`);
    else navigate("/search");
  };

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
                NIRN.AI for
                <span className="accent">Governance</span>
              </h1>
              <div className="underline-blue" />
              <p className="hero-sub">
                NIRN.AI is your intelligent assistant for drafting, aligning
                and verifying Government Resolutions of Maharashtra.
              </p>
            </div>

            <div className="hero-stat">
              <div className="stat-icon"><IconResolutions /></div>
              <div className="stat-number">98,950+</div>
              <div className="stat-label">Government Resolutions</div>
              <div className="stat-sub">Across departments. At your fingertips.</div>
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
              placeholder="Ask anything about Government Resolutions..."
              aria-label="Search Government Resolutions"
            />
            <button className="go" type="submit" aria-label="Search">→</button>
          </form>

          <div className="try-row">
            <span className="try-label">Try asking:</span>
            {TRY_QUERIES.map((q) => (
              <button key={q} className="chip" onClick={() => goSearch(q)}>
                {q} <span className="arr">↗</span>
              </button>
            ))}
          </div>

          <div className="features">
            {FEATURES.map((f) => (
              <div className="feature" key={f.title}>
                <div className={`f-icon ${f.color}`}>{f.icon}</div>
                <div className={`f-underline ${f.underline}`} />
                <div className="f-title">{f.title}</div>
                <p className="f-desc">{f.desc}</p>
                <Link className="f-link" to={f.link}>
                  {f.label} <span>→</span>
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}