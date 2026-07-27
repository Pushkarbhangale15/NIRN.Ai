import { useState, useRef, useEffect } from "react";
import { api } from "../api.js";
import { useLanguage } from "../LanguageContext.jsx";
import { motion } from "framer-motion";

import WorkflowStepper from "../components/drafting/WorkflowStepper.jsx";
import DraftInputCard from "../components/drafting/DraftInputCard.jsx";
import DraftViewer from "../components/drafting/DraftViewer.jsx";
import ComplianceCard from "../components/drafting/ComplianceCard.jsx";
import ConflictCard from "../components/drafting/ConflictCard.jsx";
import ReferencesCard from "../components/drafting/ReferencesCard.jsx";
import TerminologyCard from "../components/drafting/TerminologyCard.jsx";
import SuggestionsCard from "../components/drafting/SuggestionsCard.jsx";

/* ─── Tab config ──────────────────────────────────────────────── */
const TABS = [
  { id: "chat",    label: "Chat",         eyebrow: "Ask anything" },
  { id: "draft",   label: "Draft a GR",   eyebrow: "AI drafting" },
  { id: "compare", label: "Compare GRs",  eyebrow: "Side-by-side" },
  { id: "explain", label: "Explain Clause", eyebrow: "Plain language" },
];

/* ─── Inline SVG icons ───────────────────────────────────────── */
const IconSend = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="currentColor" viewBox="0 0 24 24">
    <path d="M2.01 21 23 12 2.01 3 2 10l15 2-15 2z"/>
  </svg>
);
const IconBot = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="currentColor" viewBox="0 0 24 24">
    <path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7H3a7 7 0 0 1 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2M7.5 13A2.5 2.5 0 0 0 5 15.5 2.5 2.5 0 0 0 7.5 18a2.5 2.5 0 0 0 2.5-2.5A2.5 2.5 0 0 0 7.5 13m9 0a2.5 2.5 0 0 0-2.5 2.5 2.5 2.5 0 0 0 2.5 2.5 2.5 2.5 0 0 0 2.5-2.5A2.5 2.5 0 0 0 16.5 13M3 21v-2h18v2z"/>
  </svg>
);
const IconUser = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="currentColor" viewBox="0 0 24 24">
    <path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12m0 2.4c-3.2 0-9.6 1.6-9.6 4.8v2.4h19.2v-2.4c0-3.2-6.4-4.8-9.6-4.8"/>
  </svg>
);
const IconCopy = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" fill="currentColor" viewBox="0 0 24 24">
    <path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>
  </svg>
);

/* ─── Shared: copy-to-clipboard button ───────────────────────── */
function CopyBtn({ text }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  };
  return (
    <button className="copilot-copy-btn" onClick={copy} title="Copy to clipboard">
      {copied ? "✓ Copied" : <><IconCopy /> Copy</>}
    </button>
  );
}

/* ─── Shared: reference GR pill list ─────────────────────────── */
function RefPills({ refs }) {
  if (!refs || refs.length === 0) return null;
  return (
    <div className="copilot-refs">
      <span className="copilot-refs-label">Sources used:</span>
      {refs.slice(0, 5).map((h) => (
        <span className="copilot-ref-pill" key={h.gr_id}>
          {h.gr_id} · <span className="ri-sub" style={{ display: "inline" }}>{h.department}</span>
        </span>
      ))}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   TAB 1 — CHAT
═══════════════════════════════════════════════════════════════ */
const CHAT_STARTERS = [
  "What is the policy on lateral entry in technical colleges?",
  "Summarise the rules for government employee leave.",
  "Which department handles scholarship grievances?",
];

function ChatTab() {
  const { t } = useLanguage();
  const [messages, setMessages] = useState(() => {
    try { return JSON.parse(localStorage.getItem("nirn_chat_messages") || "[]"); }
    catch { return []; }
  });
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(() => {
    return localStorage.getItem("nirn_chat_session_id") || null;
  });
  const [error, setError] = useState("");
  const bottomRef = useRef(null);

  useEffect(() => {
    try { localStorage.setItem("nirn_chat_messages", JSON.stringify(messages)); } catch {}
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    if (sessionId) {
      try { localStorage.setItem("nirn_chat_session_id", sessionId); } catch {}
    } else {
      localStorage.removeItem("nirn_chat_session_id");
    }
  }, [sessionId]);

  const send = async (text) => {
    const q = (text ?? input).trim();
    if (!q || loading) return;
    setInput("");
    setError("");
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setLoading(true);
    try {
      const res = await api.copilotChat(q, sessionId);
      setSessionId(res.session_id);
      setMessages((prev) => [
        ...prev,
        { role: "model", content: res.answer, refs: res.references, suggestions: res.follow_up_suggestions },
      ]);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const clearChat = () => {
    setMessages([]);
    setSessionId(null);
    setError("");
    try {
      localStorage.removeItem("nirn_chat_messages");
      localStorage.removeItem("nirn_chat_session_id");
    } catch {}
  };

  return (
    <div className="copilot-chat-layout">
      {/* Message list */}
      <div className="copilot-messages">
        {messages.length === 0 && (
          <div className="copilot-empty">
            <div className="copilot-empty-icon">🤖</div>
            <div className="copilot-empty-title">NIRN.Ai Copilot</div>
            <p className="copilot-empty-sub">
              Ask any question about Maharashtra Government Resolutions.<br />
              I ground every answer in the actual GR corpus.
            </p>
            <div className="copilot-starters">
              {CHAT_STARTERS.map((s) => (
                <button key={s} className="chip" onClick={() => send(s)}>{s} <span className="arr">↗</span></button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`copilot-msg copilot-msg--${msg.role}`}>
            <div className="copilot-msg-avatar">
              {msg.role === "user" ? <IconUser /> : <IconBot />}
            </div>
            <div className="copilot-msg-body">
              <div className="copilot-msg-text" style={{ whiteSpace: "pre-wrap" }}>{msg.content}</div>
              {msg.refs && <RefPills refs={msg.refs} />}
              {msg.suggestions && msg.suggestions.length > 0 && (
                <div className="copilot-suggestions">
                  {msg.suggestions.map((s, si) => (
                    <button key={si} className="chip" onClick={() => send(s)}>
                      {s} <span className="arr">↗</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="copilot-msg copilot-msg--model">
            <div className="copilot-msg-avatar"><IconBot /></div>
            <div className="copilot-msg-body">
              <div className="copilot-typing">
                <span /><span /><span />
              </div>
            </div>
          </div>
        )}

        {error && <div className="error-box">{error}</div>}
        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="copilot-inputbar">
        {messages.length > 0 && (
          <button className="btn btn-ghost copilot-clear" onClick={clearChat} style={{ fontSize: 12, padding: "8px 14px" }}>
            {t('copilot_clear_chat')}
          </button>
        )}
        <form className="copilot-input-form" onSubmit={(e) => { e.preventDefault(); send(); }}>
          <input
            id="copilot-chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={t('copilot_chat_placeholder')}
            disabled={loading}
            autoComplete="off"
          />
          <button className="btn btn-red copilot-send" type="submit" disabled={loading || !input.trim()}>
            {loading ? <span className="spinner" /> : <IconSend />}
          </button>
        </form>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   TAB 2 — DRAFT A GR WORKSPACE (3-COLUMN WORKSPACE)
═══════════════════════════════════════════════════════════════ */
function DraftTab() {
  const { t, siteLanguage } = useLanguage();
  const [prompt, setPrompt] = useState("");
  const [language, setLanguage] = useState(siteLanguage === 'mr' ? 'Marathi' : 'English');
  const [loading, setLoading] = useState(false);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [currentStage, setCurrentStage] = useState(0);
  const [draftResult, setDraftResult] = useState(null);
  const [analysisReport, setAnalysisReport] = useState(null);
  const [error, setError] = useState("");

  const handleGenerate = async () => {
    if (!prompt.trim()) return;
    setLoading(true);
    setError("");
    setDraftResult(null);
    setAnalysisReport(null);
    setCurrentStage(1);

    try {
      // Step 1: LLM Draft Generation
      const res = await api.copilotDraft(prompt, language.toLowerCase());
      setDraftResult(res);
      setCurrentStage(2);

      // Step 2: AI Review & Conflict Analysis
      setAnalysisLoading(true);
      if (res && res.draft_id) {
        try {
          setCurrentStage(3);
          const report = await api.runFullAnalysis(res.draft_id);
          setCurrentStage(4);
          setAnalysisReport(report);
        } catch (err) {
          console.warn("Analysis call warning:", err);
        }
      }
      setCurrentStage(5);
    } catch (err) {
      setError(err.message || "Draft generation failed.");
      setCurrentStage(0);
    } finally {
      setLoading(false);
      setAnalysisLoading(false);
    }
  };

  const handleReset = () => {
    setPrompt("");
    setDraftResult(null);
    setAnalysisReport(null);
    setCurrentStage(0);
    setError("");
  };

  return (
    <div style={{ width: '100%' }}>
      {/* 3-Column Workspace Grid */}
      <div className="draft-workspace-grid">
        
        {/* LEFT PANEL: Input & Brief */}
        <div>
          <DraftInputCard
            prompt={prompt}
            setPrompt={setPrompt}
            language={language}
            setLanguage={setLanguage}
            onGenerate={handleGenerate}
            loading={loading}
            onReset={handleReset}
          />
        </div>

        {/* CENTER PANEL: Stepper & Official Document Viewer */}
        <div>
          <WorkflowStepper currentStage={currentStage} isGenerating={loading} />
          {error && (
            <div style={{
              background: '#fee2e2',
              border: '2px solid var(--red)',
              color: 'var(--red)',
              padding: '12px 16px',
              borderRadius: '8px',
              fontWeight: 'bold',
              marginBottom: '16px'
            }}>
              ⚠️ {error}
            </div>
          )}
          <DraftViewer
            draft={draftResult}
            loading={loading}
            onRegenerate={handleGenerate}
            onTranslate={() => setLanguage(l => l === 'English' ? 'Marathi' : 'English')}
          />
        </div>

        {/* RIGHT PANEL: AI Review Dashboard */}
        <div>
          <ComplianceCard
            report={analysisReport}
            loading={analysisLoading}
            hasGenerated={Boolean(draftResult)}
          />
          <ConflictCard
            report={analysisReport}
            loading={analysisLoading}
            hasGenerated={Boolean(draftResult)}
          />
          <ReferencesCard
            references={analysisReport?.references || draftResult?.references}
            loading={analysisLoading}
            hasGenerated={Boolean(draftResult)}
          />
          <TerminologyCard
            terms={analysisReport?.terms}
            loading={analysisLoading}
            hasGenerated={Boolean(draftResult)}
          />
          <SuggestionsCard
            suggestions={analysisReport?.suggestions}
            hasGenerated={Boolean(draftResult)}
          />
        </div>

      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   TAB 3 — COMPARE GRs
═══════════════════════════════════════════════════════════════ */
function CompareTab() {
  const [grId1, setGrId1] = useState("");
  const [grId2, setGrId2] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const compare = async (e) => {
    e?.preventDefault();
    if (!grId1.trim() || !grId2.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await api.copilotCompare(grId1.trim(), grId2.trim());
      setResult(res);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="copilot-tool-layout">
      {/* Left: input */}
      <div className="panel">
        <div className="panel-head">
          <span className="panel-title">Select GRs to compare</span>
        </div>
        <div className="panel-body">
          <div className="field">
            <label htmlFor="gr-id-1">First GR ID or keyword</label>
            <input
              id="gr-id-1"
              value={grId1}
              onChange={(e) => setGrId1(e.target.value)}
              placeholder="e.g. CTC-2019/Pr.Kra.252/TE-04"
            />
          </div>
          <div className="field">
            <label htmlFor="gr-id-2">Second GR ID or keyword</label>
            <input
              id="gr-id-2"
              value={grId2}
              onChange={(e) => setGrId2(e.target.value)}
              placeholder="e.g. TEM-2024/CR-118/TE-1"
            />
          </div>
          <p className="ri-sub" style={{ marginBottom: 18 }}>
            Enter GR reference numbers or descriptive keywords. The AI will locate relevant GR chunks and compare them for you.
          </p>
          <div className="btn-row">
            <button className="btn btn-red" onClick={compare} disabled={loading || !grId1.trim() || !grId2.trim()}>
              {loading ? <span className="spinner" /> : "Compare →"}
            </button>
          </div>
          {error && <div className="error-box" style={{ marginTop: 16 }}>{error}</div>}
        </div>
      </div>

      {/* Right: comparison report */}
      <div>
        {!result && !loading && (
          <div className="empty-state">
            <div className="big">⚖️</div>
            <p>Enter two GR IDs or topics on the left.<br />The AI will generate a side-by-side comparison.</p>
          </div>
        )}
        {loading && (
          <div className="empty-state">
            <div className="big"><span className="spinner" /></div>
            <p>Comparing both GRs…<br />Analysing eligibility, scope, and jurisdiction.</p>
          </div>
        )}
        {result && (
          <div className="panel">
            <div className="panel-head">
              <span className="panel-title">Comparison Report</span>
              <CopyBtn text={result.comparison_report} />
            </div>
            <div className="panel-body">
              <div className="copilot-compare-ids">
                <span className="copilot-ref-pill">{result.gr_id_1}</span>
                <span style={{ color: "var(--ink-soft)", fontWeight: 700 }}>vs</span>
                <span className="copilot-ref-pill">{result.gr_id_2}</span>
              </div>
              {/* Render Markdown-like content */}
              <MarkdownBlock text={result.comparison_report} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   TAB 4 — EXPLAIN CLAUSE
═══════════════════════════════════════════════════════════════ */
const SAMPLE_CLAUSE = "The lateral entry intake in Government and aided technical institutions shall be fixed at fifteen percent of the sanctioned intake of the first-year course. Institutions shall report compliance to the Directorate within thirty days.";

function ExplainTab() {
  const [clause, setClause] = useState("");
  const [language, setLanguage] = useState("en");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const explain = async (e) => {
    e?.preventDefault();
    if (!clause.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await api.copilotExplain(clause.trim(), language);
      setResult(res.explanation);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="copilot-tool-layout">
      {/* Left: input */}
      <div className="panel">
        <div className="panel-head">
          <span className="panel-title">Clause Input</span>
          <button className="btn btn-ghost" style={{ fontSize: 12, padding: "6px 12px" }}
            onClick={() => { setClause(SAMPLE_CLAUSE); setResult(null); }}>
            Load sample
          </button>
        </div>
        <div className="panel-body">
          <div className="field">
            <label htmlFor="clause-text">Paste GR clause here</label>
            <textarea
              id="clause-text"
              value={clause}
              onChange={(e) => setClause(e.target.value)}
              placeholder="Paste any clause from a Government Resolution..."
              style={{ minHeight: 180 }}
            />
          </div>
          <div className="field-row">
            <div className="field" style={{ marginBottom: 0 }}>
              <label htmlFor="explain-lang">Explain in</label>
              <select id="explain-lang" value={language} onChange={(e) => setLanguage(e.target.value)}>
                <option value="en">English</option>
                <option value="mr">Marathi (मराठी)</option>
              </select>
            </div>
          </div>
          <div className="btn-row" style={{ marginTop: 18 }}>
            <button className="btn btn-red" onClick={explain} disabled={loading || !clause.trim()}>
              {loading ? <span className="spinner" /> : "Explain →"}
            </button>
          </div>
          {error && <div className="error-box" style={{ marginTop: 16 }}>{error}</div>}
        </div>
      </div>

      {/* Right: explanation */}
      <div>
        {!result && !loading && (
          <div className="empty-state">
            <div className="big">💬</div>
            <p>Paste any GR clause on the left.<br />The AI will explain it in plain, jargon-free language.</p>
          </div>
        )}
        {loading && (
          <div className="empty-state">
            <div className="big"><span className="spinner" /></div>
            <p>Generating plain-language explanation…</p>
          </div>
        )}
        {result && (
          <div className="panel">
            <div className="panel-head">
              <span className="panel-title">Plain Language Explanation</span>
              <CopyBtn text={result} />
            </div>
            <div className="panel-body">
              <div className="copilot-explanation">{result}</div>
              <div className="ri-sub" style={{ marginTop: 16 }}>
                Language: <strong>{language === "mr" ? "Marathi" : "English"}</strong>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── Minimal markdown renderer (tables + bold + paragraphs) ─── */
function MarkdownBlock({ text }) {
  if (!text) return null;
  const lines = text.split("\n");
  const elements = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Table: lines containing |
    if (line.includes("|") && lines[i + 1]?.includes("---")) {
      const headers = line.split("|").filter(Boolean).map((h) => h.trim());
      const rows = [];
      i += 2; // skip header + separator
      while (i < lines.length && lines[i].includes("|")) {
        rows.push(lines[i].split("|").filter(Boolean).map((c) => c.trim()));
        i++;
      }
      elements.push(
        <div key={i} className="copilot-table-wrap">
          <table className="copilot-table">
            <thead>
              <tr>{headers.map((h, hi) => <th key={hi}>{h}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((row, ri) => (
                <tr key={ri}>{row.map((cell, ci) => <td key={ci}>{cell}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      continue;
    }

    // Heading: ## or ###
    if (line.startsWith("### ")) {
      elements.push(<h4 key={i} className="copilot-md-h3">{line.slice(4)}</h4>);
    } else if (line.startsWith("## ")) {
      elements.push(<h3 key={i} className="copilot-md-h2">{line.slice(3)}</h3>);
    } else if (line.startsWith("# ")) {
      elements.push(<h2 key={i} className="copilot-md-h1">{line.slice(2)}</h2>);
    } else if (line.startsWith("- ") || line.startsWith("* ")) {
      elements.push(<p key={i} className="copilot-md-li">• {line.slice(2)}</p>);
    } else if (line.trim() === "") {
      elements.push(<div key={i} style={{ height: 10 }} />);
    } else {
      elements.push(<p key={i} className="copilot-md-p">{line}</p>);
    }
    i++;
  }

  return <div className="copilot-md">{elements}</div>;
}

/* ═══════════════════════════════════════════════════════════════
   ROOT — Copilot page
═══════════════════════════════════════════════════════════════ */
export default function Copilot({ defaultTab }) {
  const [activeTab, setActiveTab] = useState(defaultTab || "chat");

  useEffect(() => {
    if (defaultTab) {
      setActiveTab(defaultTab);
    }
  }, [defaultTab]);

  const tab = TABS.find((t) => t.id === activeTab);

  return (
    <main className="container">
      <header className="page-head">
        <div className="eyebrow">{tab.eyebrow}</div>
        <h1 className="page-title">
          {activeTab === "chat" ? "NIRN.Ai Chat" : activeTab === "draft" ? "Draft a GR" : "AI Copilot"}
        </h1>
        <p className="page-sub">
          Your intelligent assistant for drafting, querying, and understanding
          Government Resolutions of Maharashtra.
        </p>
      </header>

      {/* Tab panels */}
      <div className="copilot-panel-area" style={{ marginTop: '20px' }}>
        {activeTab === "chat"    && <ChatTab />}
        {activeTab === "draft"   && <DraftTab />}
      </div>
    </main>
  );
}
