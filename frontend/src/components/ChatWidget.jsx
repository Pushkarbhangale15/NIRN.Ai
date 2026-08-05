import { useEffect, useRef, useState } from "react";
import { useLanguage } from "../LanguageContext.jsx";
import { useCopilotChat } from "../hooks/useCopilotChat.js";

const IconBubble = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 24 24">
    <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z" />
  </svg>
);
const IconClose = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="currentColor" viewBox="0 0 24 24">
    <path d="M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
  </svg>
);
const IconSend = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="currentColor" viewBox="0 0 24 24">
    <path d="M2.01 21 23 12 2.01 3 2 10l15 2-15 2z" />
  </svg>
);
const IconBot = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
    <path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7H3a7 7 0 0 1 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2M7.5 13A2.5 2.5 0 0 0 5 15.5 2.5 2.5 0 0 0 7.5 18a2.5 2.5 0 0 0 2.5-2.5A2.5 2.5 0 0 0 7.5 13m9 0a2.5 2.5 0 0 0-2.5 2.5 2.5 2.5 0 0 0 2.5 2.5 2.5 2.5 0 0 0 2.5-2.5A2.5 2.5 0 0 0 16.5 13M3 21v-2h18v2z" />
  </svg>
);

// Persistent floating corner widget (Task 2). Mounted once in App.jsx
// so it survives route changes and keeps its conversation. Shares its
// fetch/session logic with the standalone /chat page via
// useCopilotChat — this file only owns open/closed UI state.
export default function ChatWidget() {
  const { t } = useLanguage();
  const [isOpen, setIsOpen] = useState(false);
  const { messages, input, setInput, loading, error, send } = useCopilotChat();
  const listRef = useRef(null);

  // Auto-scroll the message list itself, never the page. scrollIntoView()
  // on a message element would drag the whole document with it; setting
  // scrollTop on the list's own container does not.
  useEffect(() => {
    if (!isOpen) return;
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, loading, isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const onKeyDown = (e) => {
      if (e.key === "Escape") setIsOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isOpen]);

  return (
    <>
      <button
        type="button"
        className="chat-widget-fab"
        onClick={() => setIsOpen((v) => !v)}
        title={t("chat_widget_tooltip")}
        aria-label={t("chat_widget_tooltip")}
        aria-expanded={isOpen}
      >
        <IconBubble />
      </button>

      {isOpen && (
        <div className="chat-widget-panel" role="dialog" aria-label={t("chat_title")}>
          <div className="chat-widget-header">
            <span className="chat-widget-header-title">
              <IconBot /> {t("chat_title")}
            </span>
            <button
              type="button"
              className="chat-widget-close"
              onClick={() => setIsOpen(false)}
              aria-label={t("chat_widget_close")}
              title={t("chat_widget_close")}
            >
              <IconClose />
            </button>
          </div>

          <div className="chat-widget-messages" ref={listRef}>
            {messages.length === 0 && (
              <div className="chat-widget-empty">{t("chat_empty_sub")}</div>
            )}
            {messages.map((msg, i) => (
              <div key={i} className={`chat-widget-msg chat-widget-msg--${msg.role}`}>
                <div className="chat-widget-msg-text">{msg.content}</div>
              </div>
            ))}
            {loading && (
              <div className="chat-widget-msg chat-widget-msg--model">
                <div className="chat-widget-typing">
                  <span /><span /><span />
                </div>
              </div>
            )}
            {error && <div className="chat-widget-error">{error}</div>}
          </div>

          <form
            className="chat-widget-inputbar"
            onSubmit={(e) => {
              e.preventDefault();
              send();
            }}
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={t("copilot_chat_placeholder")}
              disabled={loading}
              autoComplete="off"
            />
            <button
              type="submit"
              className="chat-widget-send"
              disabled={loading || !input.trim()}
            >
              {loading ? <span className="spinner-small" /> : <IconSend />}
            </button>
          </form>
        </div>
      )}
    </>
  );
}
