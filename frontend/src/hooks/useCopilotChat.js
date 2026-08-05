import { useEffect, useState } from "react";
import { api } from "../api.js";

const STORAGE_MESSAGES = "nirn_chat_messages";
const STORAGE_SESSION = "nirn_chat_session_id";

// Shared by the floating ChatWidget and the standalone /chat page so
// there is exactly one place that talks to /api/copilot/chat. Both
// consumers read/write the same localStorage keys, so a fresh mount
// of either one picks up the other's last-known conversation.
export function useCopilotChat() {
  const [messages, setMessages] = useState(() => {
    try { return JSON.parse(localStorage.getItem(STORAGE_MESSAGES) || "[]"); }
    catch { return []; }
  });
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [sessionId, setSessionId] = useState(() => localStorage.getItem(STORAGE_SESSION) || null);

  useEffect(() => {
    try { localStorage.setItem(STORAGE_MESSAGES, JSON.stringify(messages)); } catch { /* ignore */ }
  }, [messages]);

  useEffect(() => {
    if (sessionId) {
      try { localStorage.setItem(STORAGE_SESSION, sessionId); } catch { /* ignore */ }
    } else {
      localStorage.removeItem(STORAGE_SESSION);
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
      localStorage.removeItem(STORAGE_MESSAGES);
      localStorage.removeItem(STORAGE_SESSION);
    } catch { /* ignore */ }
  };

  return { messages, input, setInput, loading, error, send, clearChat };
}
