import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { useLanguage } from "../LanguageContext.jsx";
import { DEPARTMENTS } from "../constants/departments.js";

const STATUS_OPTIONS = ["draft", "under_review", "finalised", "archived"];
const SOURCE_OPTIONS = ["generated", "uploaded"];

const CFL_RE = /^CFL-\d{4}-\d{6}$/i;
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function useDebouncedValue(value, delayMs) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

function formatIst(isoString) {
  // Backend stores TIMESTAMPTZ (UTC); convert to IST for display —
  // "30 Jul 2026, 6:41 PM".
  const date = new Date(isoString);
  return date.toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

function downloadDraftPdf(draft) {
  const printWin = window.open("", "_blank");
  printWin.document.write(`
    <html>
      <head>
        <title>${draft.title || "Government Resolution"}</title>
        <style>
          body { font-family: 'Times New Roman', serif; padding: 40px; line-height: 1.6; }
          h1 { text-align: center; font-size: 18pt; text-decoration: underline; margin-bottom: 20px; }
          .dept { text-align: center; font-weight: bold; font-size: 14pt; margin-bottom: 30px; }
          .content p, .content h2 { margin: 0 0 14px 0; }
        </style>
      </head>
      <body>
        <div class="dept">GOVERNMENT OF MAHARASHTRA<br/>${(draft.department || "").replace(/_/g, " ").toUpperCase()}</div>
        <h1>GOVERNMENT RESOLUTION</h1>
        <div class="content">${draft.content}</div>
      </body>
    </html>
  `);
  printWin.document.close();
  printWin.focus();
  setTimeout(() => { printWin.print(); }, 500);
}

function SkeletonRows() {
  return (
    <>
      {[0, 1, 2, 3].map((i) => (
        <div className="admin-table-row" key={i}>
          {Array.from({ length: 8 }).map((_, j) => (
            <span key={j} className="skeleton-line" />
          ))}
        </div>
      ))}
    </>
  );
}

function severityBadgeClass(severity) {
  if (severity === "high") return "badge-error";
  if (severity === "medium") return "badge-warning";
  return "badge-info";
}

// Longest common substring between two excerpts, capped so the DP table
// never grows unbounded on very long clauses. Returns null when nothing
// long enough to be meaningful overlaps (avoids highlighting a shared
// "the" or "shall").
function longestCommonSubstring(a, b) {
  const MAX_LEN = 1000;
  const MIN_MATCH = 15;
  const s1 = (a || "").slice(0, MAX_LEN);
  const s2 = (b || "").slice(0, MAX_LEN);
  if (!s1 || !s2) return null;

  let best = { len: 0, endA: 0, endB: 0 };
  let prev = new Array(s2.length + 1).fill(0);
  for (let i = 1; i <= s1.length; i++) {
    const curr = new Array(s2.length + 1).fill(0);
    for (let j = 1; j <= s2.length; j++) {
      if (s1[i - 1] === s2[j - 1]) {
        curr[j] = prev[j - 1] + 1;
        if (curr[j] > best.len) best = { len: curr[j], endA: i, endB: j };
      }
    }
    prev = curr;
  }
  if (best.len < MIN_MATCH) return null;
  return {
    a: [s1.slice(0, best.endA - best.len), s1.slice(best.endA - best.len, best.endA), s1.slice(best.endA)],
    b: [s2.slice(0, best.endB - best.len), s2.slice(best.endB - best.len, best.endB), s2.slice(best.endB)],
  };
}

function ConflictItemRow({ conflict }) {
  const { t } = useLanguage();
  const [copied, setCopied] = useState(false);

  const copyRef = () => {
    navigator.clipboard.writeText(conflict.conflict_ref).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  const draftSide = conflict.draft_clause_ref
    ? `${conflict.draft_clause_ref} ${t("conflict_of_this_draft")}`
    : t("conflict_this_draft").toLowerCase();
  const sourceSide = conflict.conflicting_gr_id
    ? (conflict.source_clause_ref
        ? `${conflict.source_clause_ref} ${t("conflict_of_gr")} ${conflict.conflicting_gr_id}`
        : `GR ${conflict.conflicting_gr_id}`)
    : t("conflict_the_referenced_gr");
  const match = longestCommonSubstring(conflict.draft_excerpt, conflict.conflicting_text);

  return (
    <div className="conflict-item">
      <div className="conflict-item-head">
        <span className="mono conflict-ref-code">{conflict.conflict_ref}</span>
        <button type="button" className="btn btn-ghost btn-sm" onClick={copyRef}>
          {copied ? t("conflict_copied") : t("conflict_copy")}
        </button>
        <span className={`badge ${severityBadgeClass(conflict.severity)}`}>{conflict.severity}</span>
        {conflict.is_dismissed && <span className="badge badge-unknown">Dismissed</span>}
      </div>
      <div className="conflict-item-line">{draftSide} ↔ {sourceSide}</div>
      <div className="conflict-compare-grid">
        <div>
          <div className="conflict-compare-heading">{t("conflict_this_draft")}</div>
          <div className="conflict-excerpt-text">
            {conflict.draft_excerpt
              ? (match ? <>{match.a[0]}<mark className="highlight-mark">{match.a[1]}</mark>{match.a[2]}</> : conflict.draft_excerpt)
              : "—"}
          </div>
        </div>
        <div>
          <div className="conflict-compare-heading">{t("conflict_existing_gr")}</div>
          <div className="conflict-excerpt-text">
            {match ? <>{match.b[0]}<mark className="highlight-mark">{match.b[1]}</mark>{match.b[2]}</> : conflict.conflicting_text}
          </div>
        </div>
      </div>
      <div className="conflict-item-justification"><strong>{t("conflict_justification")}:</strong> {conflict.justification}</div>
      {conflict.is_dismissed && (
        <div className="conflict-item-dismissed">
          Dismissed{conflict.dismissed_reason ? `: ${conflict.dismissed_reason}` : ""}
        </div>
      )}
    </div>
  );
}

function ConflictExpansionSkeleton() {
  return (
    <div className="conflict-expansion">
      {[0, 1].map((i) => (
        <div key={i} className="conflict-item">
          <span className="skeleton-line" style={{ width: "30%", marginBottom: 8 }} />
          <span className="skeleton-line" style={{ width: "90%", marginBottom: 6 }} />
          <span className="skeleton-line" style={{ width: "70%" }} />
        </div>
      ))}
    </div>
  );
}

function ConflictExpansion({ loading, error, conflicts, showDismissed, onToggleDismissed }) {
  const { t } = useLanguage();
  if (loading) return <ConflictExpansionSkeleton />;
  if (error) return <div className="error-box">{error}</div>;
  if (!conflicts || conflicts.length === 0) return <div className="ri-sub">{t("conflict_none_on_draft")}</div>;

  const active = conflicts.filter((c) => !c.is_dismissed);
  const dismissed = conflicts.filter((c) => c.is_dismissed);

  return (
    <div className="conflict-expansion">
      {active.length === 0 && dismissed.length > 0 && (
        <div className="ri-sub" style={{ marginBottom: 10 }}>{t("conflict_all_dismissed")}</div>
      )}
      {active.map((c) => <ConflictItemRow key={c.conflict_id} conflict={c} />)}
      {dismissed.length > 0 && (
        <>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onToggleDismissed}>
            {showDismissed ? t("conflict_hide_dismissed") : `${t("conflict_show_dismissed")} (${dismissed.length})`}
          </button>
          {showDismissed && dismissed.map((c) => <ConflictItemRow key={c.conflict_id} conflict={c} />)}
        </>
      )}
    </div>
  );
}

function ConflictLookupBox({ onFound }) {
  const { t } = useLanguage();
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed) return;
    if (!CFL_RE.test(trimmed) && !UUID_RE.test(trimmed)) {
      setError(t("conflict_lookup_invalid"));
      return;
    }
    setError("");
    setLoading(true);
    try {
      const result = await api.lookupConflict(trimmed);
      onFound(result);
    } catch (err) {
      setError(err.message || "No conflict found with that reference.");
      // Deliberately not clearing `value` — the officer shouldn't have to retype it.
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="gr-lookup-section" style={{ marginTop: 0, paddingTop: 0, borderTop: "none" }}>
      <div className="gr-lookup-label-row">
        <span className="gr-lookup-label">{t("conflict_lookup_label")}</span>
      </div>
      <form
        className="searchbar gr-number-searchbar"
        onSubmit={submit}
        style={{ marginTop: 0 }}
      >
        <span className="lead lead--ink">#</span>
        <input
          value={value}
          onChange={(e) => { setValue(e.target.value); if (error) setError(""); }}
          placeholder={t("conflict_lookup_placeholder")}
          aria-label="Conflict reference code"
        />
        <button className="go" type="submit" aria-label="Look up conflict">
          {loading ? "…" : "→"}
        </button>
      </form>
      <p className="ri-sub" style={{ marginTop: 6 }}>{t("conflict_lookup_helper")}</p>
      {error && <div className="error-box" style={{ marginTop: 10 }}>{error}</div>}
    </div>
  );
}

function ConflictDetailModal({ conflict, onClose, onOpenDraft }) {
  const { t } = useLanguage();
  const match = longestCommonSubstring(conflict.draft_excerpt, conflict.conflicting_text);

  return (
    <div className="admin-modal-overlay" onClick={onClose}>
      <div className="admin-modal conflict-detail-modal" onClick={(e) => e.stopPropagation()}>
        <div className="panel-head">
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <span className="panel-title mono">{conflict.conflict_ref}</span>
            <span className={`badge ${severityBadgeClass(conflict.severity)}`}>{conflict.severity}</span>
            {conflict.is_dismissed && <span className="badge badge-unknown">Dismissed</span>}
          </div>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>Close</button>
        </div>
        <div className="panel-body">
          <div className="ri-sub" style={{ marginBottom: 14 }}>
            {t("conflict_from_draft")} <strong>{conflict.draft.title}</strong>
            {conflict.draft.gr_number ? ` (${conflict.draft.gr_number})` : ""}
          </div>

          <div className="conflict-compare-grid">
            <div>
              <div className="conflict-compare-heading">{t("conflict_this_draft")}</div>
              <div className="ri-sub" style={{ marginBottom: 4 }}>{conflict.draft_clause_ref || t("conflict_clause_unidentified")}</div>
              <div className="conflict-excerpt-text">
                {conflict.draft_excerpt
                  ? (match ? <>{match.a[0]}<mark className="highlight-mark">{match.a[1]}</mark>{match.a[2]}</> : conflict.draft_excerpt)
                  : "—"}
              </div>
            </div>
            <div>
              <div className="conflict-compare-heading">{t("conflict_existing_gr")}</div>
              <div className="ri-sub" style={{ marginBottom: 4 }}>
                {conflict.conflicting_gr_id || "—"}
                {conflict.source_gr_title ? ` — ${conflict.source_gr_title}` : ""}
                {conflict.source_gr_date ? ` (${conflict.source_gr_date})` : ""}
                {conflict.source_clause_ref ? ` · ${conflict.source_clause_ref}` : ""}
              </div>
              <div className="conflict-excerpt-text">
                {match ? <>{match.b[0]}<mark className="highlight-mark">{match.b[1]}</mark>{match.b[2]}</> : conflict.conflicting_text}
              </div>
            </div>
          </div>

          <div style={{ marginTop: 16 }}>
            <div className="conflict-compare-heading">{t("conflict_justification")}</div>
            <p style={{ margin: "4px 0 0" }}>{conflict.justification}</p>
          </div>

          <div className="ri-sub" style={{ marginTop: 14 }}>
            {t("conflict_detected_prefix")} {conflict.detected_by === "rule_engine" ? t("conflict_detected_by_rule") : t("conflict_detected_by_llm")} {t("conflict_detected_on")} {formatIst(conflict.created_at)}
          </div>

          {conflict.is_dismissed && (
            <div className="ri-sub" style={{ marginTop: 6 }}>
              Dismissed{conflict.dismissed_reason ? `: ${conflict.dismissed_reason}` : ""}
            </div>
          )}

          <div className="btn-row" style={{ marginTop: 18 }}>
            <button type="button" className="btn btn-primary btn-sm" onClick={() => onOpenDraft(conflict)}>
              {t("conflict_open_draft")} →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function History() {
  const navigate = useNavigate();
  const { t } = useLanguage();

  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [searchInput, setSearchInput] = useState("");
  const search = useDebouncedValue(searchInput, 300);
  const [department, setDepartment] = useState("");
  const [status, setStatus] = useState("");
  const [source, setSource] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 20;

  // Per-draft conflict expansion — lazy-loaded and cached by draft id so
  // re-expanding a row never refetches.
  const [expandedConflictsFor, setExpandedConflictsFor] = useState(null);
  const [conflictsByDraft, setConflictsByDraft] = useState({});
  const [conflictErrorByDraft, setConflictErrorByDraft] = useState({});
  const [conflictsLoadingFor, setConflictsLoadingFor] = useState(null);
  const [showDismissedFor, setShowDismissedFor] = useState({});

  // Conflict lookup box + detail modal.
  const [lookupResult, setLookupResult] = useState(null);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.listDrafts({
        search: search || undefined,
        department: department || undefined,
        status: status || undefined,
        source: source || undefined,
        page,
        pageSize,
      });
      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [search, department, status, source, page]);
  useEffect(() => { setPage(1); }, [search, department, status, source]);

  const openInEditor = (item) => {
    navigate("/draft", { state: { openDraftId: item.generated_draft_id } });
  };

  const toggleConflictsRow = async (item) => {
    const id = item.generated_draft_id;
    if (expandedConflictsFor === id) {
      setExpandedConflictsFor(null);
      return;
    }
    setExpandedConflictsFor(id);
    if (conflictsByDraft[id]) return; // already cached — no refetch
    setConflictsLoadingFor(id);
    setConflictErrorByDraft((prev) => ({ ...prev, [id]: "" }));
    try {
      const rows = await api.getDraftConflicts(id);
      setConflictsByDraft((prev) => ({ ...prev, [id]: rows }));
    } catch (err) {
      setConflictErrorByDraft((prev) => ({ ...prev, [id]: err.message || "Failed to load conflicts." }));
    } finally {
      setConflictsLoadingFor(null);
    }
  };

  const openConflictDraft = (conflict) => {
    setLookupResult(null);
    navigate("/draft", {
      state: {
        openDraftId: conflict.draft.draft_id,
        scrollToClauseIndex: conflict.draft_clause_index ?? null,
      },
    });
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <main className="container" style={{ marginTop: 48, marginBottom: 80 }}>
      <header className="page-head">
        <div className="eyebrow">{t("history_eyebrow") || "History"}</div>
        <h1 className="page-title">{t("history_title") || "Your GR drafts"}</h1>
        <p className="page-sub">{t("history_sub") || "Every draft you've generated or uploaded, in one place."}</p>
      </header>

      <ConflictLookupBox onFound={setLookupResult} />

      <div className="panel" style={{ marginTop: 32 }}>
        <div className="panel-body">
          <div className="admin-toolbar">
            <div className="field">
              <label htmlFor="history-search">Search</label>
              <input
                id="history-search"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search title or content"
              />
            </div>
            <div className="field">
              <label htmlFor="history-dept">Department</label>
              <select id="history-dept" value={department} onChange={(e) => setDepartment(e.target.value)}>
                <option value="">All</option>
                {DEPARTMENTS.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="history-status">Status</label>
              <select id="history-status" value={status} onChange={(e) => setStatus(e.target.value)}>
                <option value="">All</option>
                {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="history-source">Source</label>
              <select id="history-source" value={source} onChange={(e) => setSource(e.target.value)}>
                <option value="">All</option>
                {SOURCE_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>

          {error && <div className="error-box">{error}</div>}

          {!loading && items.length === 0 ? (
            <div className="panel" style={{ textAlign: "center", padding: "40px 20px" }}>
              <p style={{ marginBottom: 16 }}>
                {total === 0 && !search && !department && !status && !source
                  ? "You haven't drafted or uploaded any GRs yet."
                  : "No drafts match these filters."}
              </p>
              <button type="button" className="btn btn-primary btn-sm" onClick={() => navigate("/draft")}>
                Draft a GR
              </button>
            </div>
          ) : (
            <div className="admin-table admin-table--history">
              <div className="admin-table-row admin-table-head">
                <span>GR Number</span>
                <span>Title</span>
                <span>Department</span>
                <span>Language</span>
                <span>Source</span>
                <span>Status</span>
                <span>Conflicts</span>
                <span>Created</span>
                <span>Actions</span>
              </div>

              {loading ? (
                <SkeletonRows />
              ) : (
                items.map((item) => (
                  <div key={item.generated_draft_id}>
                    <div className="admin-table-row">
                      <span className="mono">{item.gr_number || "—"}</span>
                      <span>{item.title}</span>
                      <span>{(item.department || "").replace(/_/g, " ")}</span>
                      <span>{item.language === "mr" ? "Marathi" : "English"}</span>
                      <span>
                        <span className={`badge ${item.source === "uploaded" ? "badge-warning" : "badge-info"}`}>
                          {item.source === "uploaded" ? "Uploaded" : "Generated"}
                        </span>
                      </span>
                      <span>
                        <span className={`badge ${item.status === "archived" ? "badge-unknown" : "badge-ok"}`}>
                          {item.status}
                        </span>
                      </span>
                      <span>
                        <button
                          type="button"
                          className={`badge-btn badge ${item.conflict_count > 0 ? "badge-error" : "badge-ok"}`}
                          onClick={() => toggleConflictsRow(item)}
                          disabled={item.conflict_count === 0}
                          title={item.conflict_count === 0 ? "No conflicts on this draft" : "View conflicts"}
                        >
                          {item.conflict_count}
                        </button>
                      </span>
                      <span className="ri-sub">{formatIst(item.created_at)}</span>
                      <span style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                        <button type="button" className="btn btn-ghost btn-sm" onClick={() => openInEditor(item)}>Open</button>
                        <button type="button" className="btn btn-secondary btn-sm" onClick={() => downloadDraftPdf(item)}>PDF</button>
                      </span>
                    </div>
                    {expandedConflictsFor === item.generated_draft_id && (
                      <div className="admin-table-row admin-table-row--detail">
                        <ConflictExpansion
                          loading={conflictsLoadingFor === item.generated_draft_id}
                          error={conflictErrorByDraft[item.generated_draft_id]}
                          conflicts={conflictsByDraft[item.generated_draft_id]}
                          showDismissed={Boolean(showDismissedFor[item.generated_draft_id])}
                          onToggleDismissed={() =>
                            setShowDismissedFor((prev) => ({
                              ...prev,
                              [item.generated_draft_id]: !prev[item.generated_draft_id],
                            }))
                          }
                        />
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          )}

          {total > pageSize && (
            <div className="admin-pagination">
              <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                ← Prev
              </button>
              <span>Page {page} of {totalPages}</span>
              <button className="btn btn-ghost btn-sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
                Next →
              </button>
            </div>
          )}
        </div>
      </div>

      {lookupResult && (
        <ConflictDetailModal
          conflict={lookupResult}
          onClose={() => setLookupResult(null)}
          onOpenDraft={openConflictDraft}
        />
      )}
    </main>
  );
}
