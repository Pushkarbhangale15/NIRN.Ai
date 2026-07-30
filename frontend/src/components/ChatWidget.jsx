import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useLanguage } from "../LanguageContext.jsx";
import { useCopilotChat } from "../hooks/useCopilotChat.js";
import StatusVerb from "./StatusVerb.jsx";

const IconChatBubble = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" fill="currentColor" viewBox="0 0 24 24">
    <path d="M4 4h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H8l-4 4V6a2 2 0 0 1 2-2z" />
  </svg>
);
const IconClose = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="currentColor" viewBox="0 0 24 24">
    <path d="M18.3 5.71 12 12.01l-6.3-6.3-1.4 1.41 6.29 6.3-6.3 6.29 1.41 1.41 6.3-6.3 6.29 6.3 1.41-1.41-6.3-6.29 6.3-6.3z" />
  </svg>
);
const IconSend = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="currentColor" viewBox="0 0 24 24">
    <path d="M2.01 21 23 12 2.01 3 2 10l15 2-15 2z" />
  </svg>
);
const IconBot = (props) => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 24 24" {...props}>
    <path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7H3a7 7 0 0 1 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2M7.5 13A2.5 2.5 0 0 0 5 15.5 2.5 2.5 0 0 0 7.5 18a2.5 2.5 0 0 0 2.5-2.5A2.5 2.5 0 0 0 7.5 13m9 0a2.5 2.5 0 0 0-2.5 2.5 2.5 2.5 0 0 0 2.5 2.5 2.5 2.5 0 0 0 2.5-2.5A2.5 2.5 0 0 0 16.5 13M3 21v-2h18v2z" />
  </svg>
);
const IconUser = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
    <path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12m0 2.4c-3.2 0-9.6 1.6-9.6 4.8v2.4h19.2v-2.4c0-3.2-6.4-4.8-9.6-4.8" />
  </svg>
);
const IconExpand = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
    <path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z" />
  </svg>
);

// Routes that already provide the full copilot chat experience — no need
// for a redundant floating bubble on top of it.
const HIDDEN_ON = ["/chat", "/copilot"];

export default function ChatWidget() {
  const { t } = useLanguage();
  const location = useLocation();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const { messages, input, setInput, loading, error, send } = useCopilotChat();
  const bottomRef = useRef(null);
  const panelRef = useRef(null);

  useEffect(() => {
    if (open) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, loading, open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open]);

  if (HIDDEN_ON.includes(location.pathname)) return null;

  return (
    <>
      <button
        type="button"
        className="chat-widget-fab"
        onClick={() => setOpen((prev) => !prev)}
        aria-label={t('chat_widget_tooltip')}
        aria-expanded={open}
        title={t('chat_widget_tooltip')}
      >
        {open ? <IconClose /> : <IconChatBubble />}
      </button>

      {open && (
        <div className="chat-widget-panel" ref={panelRef} role="dialog" aria-label={t('chat_widget_title')}>
          <div className="chat-widget-header">
            <span className="chat-widget-header-title">{t('chat_widget_title')}</span>
            <div className="chat-widget-header-actions">
              <button
                type="button"
                className="chat-widget-expand"
                onClick={() => { setOpen(false); navigate("/chat"); }}
                aria-label={t('chat_widget_expand')}
                title={t('chat_widget_expand')}
              >
                <IconExpand />
              </button>
              <button
                type="button"
                className="chat-widget-close"
                onClick={() => setOpen(false)}
                aria-label={t('chat_widget_close')}
              >
                <IconClose />
              </button>
            </div>
          </div>

          <div className="chat-widget-messages">
            {messages.length === 0 && (
              <div className="chat-widget-empty">
                <IconBot width="32" height="32" />
                <p>{t('chat_empty_sub')}</p>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} className={`copilot-msg copilot-msg--${msg.role}`}>
                <div className="copilot-msg-avatar">
                  {msg.role === "user" ? <IconUser /> : <IconBot />}
                </div>
                <div className="copilot-msg-body">
                  <div className="copilot-msg-text" style={{ whiteSpace: "pre-wrap" }}>{msg.content}</div>
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
                    <StatusVerb stage="retrieval" className="copilot-typing-verb" />
                  </div>
                </div>
              </div>
            )}

            {error && <div className="error-box">{error}</div>}
            <div ref={bottomRef} />
          </div>

          <form
            className="chat-widget-inputbar"
            onSubmit={(e) => { e.preventDefault(); send(); }}
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={t('copilot_chat_placeholder')}
              disabled={loading}
              autoComplete="off"
              aria-label={t('copilot_chat_placeholder')}
            />
            <button className="btn btn-red btn-sm" type="submit" disabled={loading || !input.trim()}>
              {loading ? <span className="spinner" /> : <IconSend />}
            </button>
          </form>
        </div>
      )}
    </>
  );
}
