/**
 * api.js — every backend call in one place.
 *
 * The Vite proxy (vite.config.js) forwards /api and /health to
 * FastAPI on port 8000, so these paths work with no CORS setup
 * and no hardcoded URLs.
 */

async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body.detail) {
        detail = typeof body.detail === "string"
          ? body.detail
          : "Validation error — check every field is filled in.";
      }
    } catch { /* keep default detail */ }
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  health: () => request("/health"),

  createDraft: (draft) =>
    request("/api/drafts", { method: "POST", body: JSON.stringify(draft) }),

  listDrafts: () => request("/api/drafts"),

  // The full report: template + references + conflicts + terminology
  analyze: (draftId) =>
    request(`/api/analysis/${draftId}`, { method: "POST" }),

  runFullAnalysis: (draftId) =>
    request(`/api/analysis/${draftId}`, { method: "POST" }),

  searchCorpus: (q, topK = 8) =>
    request(`/api/corpus/search?q=${encodeURIComponent(q)}&top_k=${topK}`),

  getCorpusOcr: (grId, language = "") =>
    request(`/api/corpus/${grId}/ocr?language=${language}`),

  getOfficialSource: (grId, department, date = "", subject = "") =>
    request(`/api/official-source/${grId}?department=${encodeURIComponent(department)}&date=${encodeURIComponent(date)}&subject=${encodeURIComponent(subject)}`),

  getOfficialGr: (grId, department, date = "", subject = "") =>
    request(`/api/official-gr/${grId}?department=${encodeURIComponent(department)}&date=${encodeURIComponent(date)}&subject=${encodeURIComponent(subject)}`),

  // ── Copilot ──────────────────────────────────────────────────
  copilotChat: (query, sessionId = null) =>
    request("/api/copilot/chat", {
      method: "POST",
      body: JSON.stringify({ query, session_id: sessionId }),
    }),

  copilotDraft: (prompt, language = "english", department = null) =>
    request("/api/copilot/draft", {
      method: "POST",
      body: JSON.stringify({ prompt, language, department }),
    }),

  copilotCompare: (grId1, grId2) =>
    request("/api/copilot/compare", {
      method: "POST",
      body: JSON.stringify({ gr_id_1: grId1, gr_id_2: grId2 }),
    }),

  copilotExplain: (clauseText, language = "en") =>
    request("/api/copilot/explain-clause", {
      method: "POST",
      body: JSON.stringify({ clause_text: clauseText, language }),
    }),
};
