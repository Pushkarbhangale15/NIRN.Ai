/**
 * api.js — every backend call in one place.
 *
 * The Vite proxy (vite.config.js) forwards /api and /health to
 * FastAPI on port 8000, so these paths work with no CORS setup
 * and no hardcoded URLs.
 */

// Set by AuthContext on login/logout. Kept out of React state so every
// api.js call (including ones fired outside a component) picks up the
// current token without threading it through every function signature.
let _authToken = null;
let _onUnauthorized = null;

export function setAuthToken(token) {
  _authToken = token;
}

export function setOnUnauthorized(callback) {
  _onUnauthorized = callback;
}

async function request(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (_authToken) headers["Authorization"] = `Bearer ${_authToken}`;

  const res = await fetch(path, { ...options, headers });

  if (res.status === 401 && _onUnauthorized) {
    _onUnauthorized();
  }

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body.detail) {
        if (typeof body.detail === "string") {
          detail = body.detail;
        } else if (Array.isArray(body.detail)) {
          detail = body.detail.map(e => `${e.loc ? e.loc.slice(1).join('.') + ': ' : ''}${e.msg}`).join('; ');
        } else if (typeof body.detail === "object" && body.detail.message) {
          detail = body.detail.message;
        } else {
          detail = "Validation error — please check the submitted data.";
        }
      }
    } catch { /* keep default detail */ }
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  health: () => request("/health"),

  createDraft: (draft) =>
    request("/api/drafts", { method: "POST", body: JSON.stringify(draft) }),

  listDrafts: () => request("/api/drafts"),

  runTemplateCheck: (draftId) =>
    request(`/api/analysis/${draftId}/template`, { method: "POST" }),

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

  // ── Auth ─────────────────────────────────────────────────────
  login: (loginId, password) =>
    request("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ login_id: loginId, password }),
    }),

  getMe: () => request("/api/officers/me"),

  changeMyPassword: (currentPassword, newPassword) =>
    request("/api/officers/me/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    }),

  // ── Admin: officers ─────────────────────────────────────────
  adminListOfficers: (params = {}) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") qs.set(k, v);
    });
    return request(`/api/officers?${qs.toString()}`);
  },

  adminCreateOfficer: (payload) =>
    request("/api/officers", { method: "POST", body: JSON.stringify(payload) }),

  adminUpdateOfficer: (officerId, payload) =>
    request(`/api/officers/${officerId}`, { method: "PATCH", body: JSON.stringify(payload) }),

  adminDeactivateOfficer: (officerId) =>
    request(`/api/officers/${officerId}/deactivate`, { method: "PATCH" }),

  adminActivateOfficer: (officerId) =>
    request(`/api/officers/${officerId}/activate`, { method: "PATCH" }),

  adminResetPassword: (officerId) =>
    request(`/api/officers/${officerId}/reset-password`, { method: "POST" }),

  adminDeleteOfficer: (officerId) =>
    request(`/api/officers/${officerId}`, { method: "DELETE" }),

  adminGetOfficerDrafts: (officerId, params = {}) => {
    const qs = new URLSearchParams(params);
    return request(`/api/officers/${officerId}/drafts?${qs.toString()}`);
  },

  adminListAllDrafts: (params = {}) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") qs.set(k, v);
    });
    return request(`/api/admin/drafts?${qs.toString()}`);
  },

  adminSummary: () => request("/api/admin/summary"),

  // ── History (Task 6) ────────────────────────────────────────
  getDraftHistory: (params = {}) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") qs.set(k, v);
    });
    return request(`/api/drafts?${qs.toString()}`);
  },

  getDraftDetail: (draftId) => request(`/api/drafts/${draftId}`),

  getDraftConflicts: (draftId, includeDismissed = true) =>
    request(`/api/drafts/${draftId}/conflicts?include_dismissed=${includeDismissed}`),

  dismissConflict: (conflictId, reason) =>
    request(`/api/conflicts/${conflictId}/dismiss`, {
      method: "PATCH",
      body: JSON.stringify({ reason: reason || null }),
    }),

  resolveConflict: (conflictId, strategy) =>
    request(`/api/conflicts/${conflictId}/resolve`, {
      method: "POST",
      body: JSON.stringify({ strategy }),
    }),

  acceptConflictResolution: (conflictId, revisedClause) =>
    request(`/api/conflicts/${conflictId}/resolve/accept`, {
      method: "POST",
      body: JSON.stringify({ revised_clause: revisedClause }),
    }),

  archiveDraft: (draftId) => request(`/api/drafts/${draftId}`, { method: "DELETE" }),

  saveDraftContent: (draftId, bodyHtml, contentPlain, changeNote) =>
    request(`/api/drafts/${draftId}`, {
      method: "PATCH",
      body: JSON.stringify({ body_text: bodyHtml, content_plain: contentPlain, change_note: changeNote || null }),
    }),

  // ── Export ───────────────────────────────────────────────────
  exportDocx: async (draftId) => {
    const headers = { "Content-Type": "application/json" };
    if (_authToken) headers["Authorization"] = `Bearer ${_authToken}`;
    const res = await fetch("/api/export/docx", {
      method: "POST",
      headers,
      body: JSON.stringify({ draft_id: draftId }),
    });
    if (!res.ok) {
      let detail = `Export failed (${res.status})`;
      try {
        const body = await res.json();
        if (body.detail) detail = typeof body.detail === "string" ? body.detail : "Could not export the document.";
      } catch { /* keep default detail */ }
      throw new Error(detail);
    }
    const disposition = res.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="?([^"]+)"?/);
    const filename = match ? match[1] : `GR_${draftId}.docx`;
    const blob = await res.blob();
    return { blob, filename };
  },

  uploadGrFile: async (file) => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch("/api/upload-gr/parse-file", {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      let detail = `Upload failed (${res.status})`;
      try {
        const body = await res.json();
        if (body.detail) {
          detail = typeof body.detail === "string" ? body.detail : "File upload validation error.";
        }
      } catch {}
      throw new Error(detail);
    }
    return res.json();
  },
};


