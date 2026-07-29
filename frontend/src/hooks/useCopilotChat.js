import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";

const MESSAGES_KEY = "nirn_chat_messages";
const SESSION_KEY = "nirn_chat_session_id";

export function useCopilotChat() {
  const [messages, setMessages] = useState(() => {
    try { return JSON.parse(localStorage.getItem(MESSAGES_KEY) || "[]"); }
    catch { return []; }
  });
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(() => localStorage.getItem(SESSION_KEY) || null);
  const [error, setError] = useState("");

  useEffect(() => {
    try { localStorage.setItem(MESSAGES_KEY, JSON.stringify(messages)); } catch {}
  }, [messages]);

  useEffect(() => {
    if (sessionId) {
      try { localStorage.setItem(SESSION_KEY, sessionId); } catch {}
    } else {
      localStorage.removeItem(SESSION_KEY);
    }
  }, [sessionId]);

  const send = useCallback(async (text) => {
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
  }, [input, loading, sessionId]);

  const clearChat = useCallback(() => {
    setMessages([]);
    setSessionId(null);
    setError("");
    try {
      localStorage.removeItem(MESSAGES_KEY);
      localStorage.removeItem(SESSION_KEY);
    } catch {}
  }, []);

  return { messages, input, setInput, loading, error, send, clearChat };
}
