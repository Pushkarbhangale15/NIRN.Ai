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

  searchCorpus: (q, topK = 8) =>
    request(`/api/corpus/search?q=${encodeURIComponent(q)}&top_k=${topK}`),
};
