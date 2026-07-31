/**
 * api.js — every backend call in one place.
 *
 * The Vite proxy (vite.config.js) forwards /api and /health to
 * FastAPI on port 8000, so these paths work with no CORS setup
 * and no hardcoded URLs.
 */

const TOKEN_STORAGE_KEY = "nirn_access_token";

export function getStoredToken() {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setStoredToken(token) {
  if (token) localStorage.setItem(TOKEN_STORAGE_KEY, token);
  else localStorage.removeItem(TOKEN_STORAGE_KEY);
}

async function request(path, options = {}) {
  const token = getStoredToken();
  const res = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...options,
  });
  
  // Extract and print performance profile if present
  const profileHeader = res.headers.get("X-Performance-Profile");
  if (profileHeader) {
    try {
      const decodedProfile = atob(profileHeader);
      console.log("%c" + decodedProfile, "color: #4CAF50; font-family: monospace;");
    } catch (e) {
      console.error("Failed to decode performance profile", e);
    }
  }

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
    if (res.status === 401) setStoredToken(null);
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  health: () => request("/health"),

  // ── Auth ─────────────────────────────────────────────────────
  login: (loginId, password) =>
    request("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ login_id: loginId, password }),
    }),

  register: (payload) =>
    request("/api/auth/register", { method: "POST", body: JSON.stringify(payload) }),

  me: () => request("/api/officers/me"),

  createDraft: (draft) =>
    request("/api/drafts", { method: "POST", body: JSON.stringify(draft) }),

  // Paginated: { items, total, limit, offset }. Admins/reviewers see every
  // officer's drafts; plain officers only see their own (enforced server-side).
  listDrafts: ({ department, status, sortBy, sortDir, limit = 20, offset = 0 } = {}) => {
    const params = new URLSearchParams({ limit, offset });
    if (department) params.set("department", department);
    if (status) params.set("status", status);
    if (sortBy) params.set("sort_by", sortBy);
    if (sortDir) params.set("sort_dir", sortDir);
    return request(`/api/drafts?${params.toString()}`);
  },

  getDraft: (draftId) => request(`/api/drafts/${draftId}`),

  // Soft delete — sets status to 'archived', never removes the row.
  archiveDraft: (draftId) => request(`/api/drafts/${draftId}`, { method: "DELETE" }),

  dismissConflict: (conflictId, reason = null) =>
    request(`/api/conflicts/${conflictId}/dismiss`, {
      method: "PATCH",
      body: JSON.stringify({ reason }),
    }),

  // ── Admin ────────────────────────────────────────────────────
  listOfficers: () => request("/api/admin/officers"),

  updateOfficer: (officerId, payload) =>
    request(`/api/admin/officers/${officerId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  // Unlike api.register(), this lets an admin set the new officer's role
  // directly (backend only honours `role` here because the caller is
  // already authenticated as admin — public registration always forces
  // role=officer).
  createOfficerAdmin: (payload) =>
    request("/api/admin/officers", { method: "POST", body: JSON.stringify(payload) }),

  updateDraft: (draftId, bodyText) =>
    request(`/api/drafts/${draftId}`, {
      method: "PATCH",
      body: JSON.stringify({ body_text: bodyText }),
    }),

  runTemplateCheck: (draftId) =>
    request(`/api/analysis/${draftId}/template`, { method: "POST" }),

  runConflictDetection: (draftId) =>
    request(`/api/analysis/${draftId}/conflicts`, { method: "POST" }),

  runReferenceTracking: (draftId) =>
    request(`/api/analysis/${draftId}/references`, { method: "POST" }),

  runTerminology: (draftId) =>
    request(`/api/analysis/${draftId}/terminology`, { method: "POST" }),

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

  searchKnowledge: (query, limit = 10) =>
    request(`/api/knowledge/search?q=${encodeURIComponent(query)}&limit=${limit}`),
};

