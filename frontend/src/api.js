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

async function handleResponse(res) {
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

async function request(path, options = {}) {
  const token = getStoredToken();
  const res = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...options,
  });
  return handleResponse(res);
}

// Multipart upload — deliberately does NOT set Content-Type so the
// browser can add the multipart boundary itself; setting it manually
// on a FormData body breaks the boundary and the server can't parse it.
async function requestMultipart(path, formData, options = {}) {
  const token = getStoredToken();
  const res = await fetch(path, {
    method: "POST",
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: formData,
    ...options,
  });
  return handleResponse(res);
}

export const api = {
  health: () => request("/health"),

  // ── Auth ─────────────────────────────────────────────────────
  // No public self-registration — officer accounts are created by an
  // admin only (see the Admin functions below).
  login: (loginId, password) =>
    request("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ login_id: loginId, password }),
    }),

  me: () => request("/api/officers/me"),

  createDraft: (draft) =>
    request("/api/drafts", { method: "POST", body: JSON.stringify(draft) }),

  uploadDraft: ({ file, department, language, title }) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("department", department);
    formData.append("language", language);
    if (title) formData.append("title", title);
    return requestMultipart("/api/drafts/upload", formData);
  },

  // Paginated (page/page_size), searchable, filterable by department /
  // status / source. Admins/reviewers see every officer's drafts; plain
  // officers only see their own (enforced server-side).
  listDrafts: ({ department, status, source, search, authorId, sortBy, sortDir, page = 1, pageSize = 20 } = {}) => {
    const params = new URLSearchParams({ page, page_size: pageSize });
    if (department) params.set("department", department);
    if (status) params.set("status", status);
    if (source) params.set("source", source);
    if (search) params.set("search", search);
    if (authorId) params.set("author_id", authorId);
    if (sortBy) params.set("sort_by", sortBy);
    if (sortDir) params.set("sort_dir", sortDir);
    return request(`/api/drafts?${params.toString()}`);
  },

  getDraft: (draftId) => request(`/api/drafts/${draftId}`),

  // Confirms a freshly generated/uploaded draft is worth keeping — until
  // this is called it stays invisible in History (see is_saved).
  saveDraft: (draftId) => request(`/api/drafts/${draftId}/save`, { method: "PATCH" }),

  dismissConflict: (conflictId, reason = null) =>
    request(`/api/conflicts/${conflictId}/dismiss`, {
      method: "PATCH",
      body: JSON.stringify({ reason }),
    }),

  // ── Conflict registry ────────────────────────────────────────
  // Every conflict on one draft — the History expansion row.
  getDraftConflicts: (draftId, { severity, isDismissed } = {}) => {
    const params = new URLSearchParams();
    if (severity) params.set("severity", severity);
    if (isDismissed !== undefined && isDismissed !== null) params.set("is_dismissed", isDismissed);
    const qs = params.toString();
    return request(`/api/drafts/${draftId}/conflicts${qs ? `?${qs}` : ""}`);
  },

  // Accepts either a CFL-YYYY-NNNNNN code or a raw conflict UUID.
  lookupConflict: (ref) =>
    request(`/api/conflicts/lookup?ref=${encodeURIComponent(ref)}`),

  listConflicts: ({ severity, isDismissed, department, dateFrom, dateTo, detectedBy, search, sortBy, sortDir, page = 1, pageSize = 20 } = {}) => {
    const params = new URLSearchParams({ page, page_size: pageSize });
    if (severity) params.set("severity", severity);
    if (isDismissed !== undefined && isDismissed !== null) params.set("is_dismissed", isDismissed);
    if (department) params.set("department", department);
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    if (detectedBy) params.set("detected_by", detectedBy);
    if (search) params.set("search", search);
    if (sortBy) params.set("sort_by", sortBy);
    if (sortDir) params.set("sort_dir", sortDir);
    return request(`/api/conflicts?${params.toString()}`);
  },

  // ── Admin: officer management ───────────────────────────────
  listOfficers: ({ search, role, department, isActive, limit = 20, offset = 0 } = {}) => {
    const params = new URLSearchParams({ limit, offset });
    if (search) params.set("search", search);
    if (role) params.set("role", role);
    if (department) params.set("department", department);
    if (isActive !== undefined && isActive !== null) params.set("is_active", isActive);
    return request(`/api/officers?${params.toString()}`);
  },

  createOfficer: (payload) =>
    request("/api/officers", { method: "POST", body: JSON.stringify(payload) }),

  editOfficer: (officerId, payload) =>
    request(`/api/officers/${officerId}`, { method: "PATCH", body: JSON.stringify(payload) }),

  deactivateOfficer: (officerId) =>
    request(`/api/officers/${officerId}/deactivate`, { method: "PATCH" }),

  activateOfficer: (officerId) =>
    request(`/api/officers/${officerId}/activate`, { method: "PATCH" }),

  resetOfficerPassword: (officerId) =>
    request(`/api/officers/${officerId}/reset-password`, { method: "POST" }),

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

