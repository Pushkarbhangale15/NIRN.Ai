import { useState, useRef, useEffect } from "react";
import { api } from "../api.js";
import { useLanguage } from "../LanguageContext.jsx";

/* ─── Inline SVG icons ───────────────────────────────────────── */
const IconSend = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="currentColor" viewBox="0 0 24 24">
    <path d="M2.01 21 23 12 2.01 3 2 10l15 2-15 2z"/>
  </svg>
);
const IconBot = (props) => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="currentColor" viewBox="0 0 24 24" {...props}>
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
function RefPills({ refs, label }) {
  if (!refs || refs.length === 0) return null;
  return (
    <div className="copilot-refs">
      <span className="copilot-refs-label">{label}</span>
      {refs.slice(0, 5).map((h) => (
        <span className="copilot-ref-pill" key={h.gr_id}>
          {h.gr_id} · <span className="ri-sub" style={{ display: "inline" }}>{h.department}</span>
        </span>
      ))}
    </div>
  );
}

export default function Chat() {
  const { t, siteLanguage, toggleLanguage } = useLanguage();
  const CHAT_STARTERS = [
    t('chat_starter_1'),
    t('chat_starter_2'),
    t('chat_starter_3'),
  ];
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
    <main className="container">
      <header className="page-head">
        <div className="eyebrow">{t('chat_eyebrow')}</div>
        <h1 className="page-title">{t('chat_title')}</h1>
        <p className="page-sub">{t('chat_sub')}</p>
      </header>

      <div className="copilot-panel-area" style={{ marginTop: '20px' }}>
        <div className="copilot-chat-layout">
          {/* Message list */}
          <div className="copilot-messages">
            {messages.length === 0 && (
              <div className="copilot-empty">
                <div className="copilot-empty-icon"><IconBot width="48" height="48" /></div>
                <div className="copilot-empty-title">{t('chat_empty_title')}</div>
                <p className="copilot-empty-sub">{t('chat_empty_sub')}</p>
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
                  {msg.refs && <RefPills refs={msg.refs} label={t('chat_sources_used')} />}
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
      </div>
    </main>
  );
}
