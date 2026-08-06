import React, { useState, useEffect, useCallback } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api.js";
import { useLanguage } from "../LanguageContext.jsx";
import { useAuth } from "../AuthContext.jsx";
import { useDraft } from "../DraftContext.jsx";
import { generateGRDocumentPDF } from "../utils/pdfExport.js";
import { DRAFT_STATUSES, statusBadgeClass, statusLabel } from "../constants/workflowStatus.js";
import HashBadge from "../components/HashBadge.jsx";

// Same department list used by DraftInputCard.jsx (not exported there, so
// mirrored locally to avoid touching a file another agent may be editing).
const DEPARTMENTS = [
  { value: "Agriculture,_Dairy_Development,_Animal_Husbandry_and_Fisheries_Department", label: "Agriculture, Dairy Development, Animal Husbandry & Fisheries" },
  { value: "Co-operation,_Textiles_and_Marketing_Department", label: "Co-operation, Textiles & Marketing" },
  { value: "Environment_Department", label: "Environment Department" },
  { value: "Finance_Department", label: "Finance Department" },
  { value: "Food,_Civil_Supplies_and_Consumer_Protection_Department", label: "Food, Civil Supplies & Consumer Protection" },
  { value: "General_Administration_Department", label: "General Administration Department" },
  { value: "Higher_and_Technical_Education_Department", label: "Higher & Technical Education" },
  { value: "Home_Department", label: "Home Department" },
  { value: "Housing_Department", label: "Housing Department" },
  { value: "Industries,_Energy_and_Labour_Department", label: "Industries, Energy & Labour" },
  { value: "Information_Technology_Department", label: "Information Technology Department" },
  { value: "Law_and_Judiciary_Department", label: "Law & Judiciary Department" },
  { value: "Marathi_Language_Department", label: "Marathi Language Department" },
  { value: "Medical_Education_and_Drugs_Department", label: "Medical Education & Drugs" },
  { value: "Minorities_Development_Department", label: "Minorities Development Department" },
  { value: "Other_Backward_Bahujan_Welfare_Department", label: "Other Backward Bahujan Welfare" },
  { value: "Parliamentary_Affairs_Department", label: "Parliamentary Affairs Department" },
  { value: "Persons_with_Disabilities_Welfare_Department", label: "Persons with Disabilities Welfare" },
  { value: "Planning_Department", label: "Planning Department" },
  { value: "Public_Health_Department", label: "Public Health Department" },
  { value: "Public_Works_Department", label: "Public Works Department" },
  { value: "Revenue_and_Forest_Department", label: "Revenue & Forest Department" },
  { value: "Rural_Development_Department", label: "Rural Development Department" },
  { value: "Skill_Development_and_Entrepreneurship_Department", label: "Skill Development & Entrepreneurship" },
  { value: "School_Education_and_Sports_Department", label: "School Education & Sports" },
  { value: "Social_Justice_and_Special_Assistance_Department", label: "Social Justice & Special Assistance" },
  { value: "Soil_and_Water_Conservation_Department", label: "Soil & Water Conservation" },
  { value: "Tourism_and_Cultural_Affairs_Department", label: "Tourism & Cultural Affairs" },
  { value: "Tribal_Development_Department", label: "Tribal Development Department" },
  { value: "Urban_Development_Department", label: "Urban Development Department" },
  { value: "Water_Resources_Department", label: "Water Resources Department" },
  { value: "Water_Supply_and_Sanitation_Department", label: "Water Supply & Sanitation" },
  { value: "Women_and_Child_Development_Department", label: "Women & Child Development" },
];

const STATUS_OPTIONS = DRAFT_STATUSES;

function departmentLabel(value) {
  if (!value) return "—";
  const found = DEPARTMENTS.find((d) => d.value === value);
  return found ? found.label : value.replace(/_/g, " ");
}

function formatIST(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("en-IN", {
      timeZone: "Asia/Kolkata",
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function conflictLinkLine(c, t) {
  const gr = c.conflicting_gr_id || "—";
  if (c.draft_clause_ref && c.source_clause_ref) {
    return t("history_conflict_link_with_clauses")
      .replace("{draftClause}", c.draft_clause_ref)
      .replace("{sourceClause}", c.source_clause_ref)
      .replace("{gr}", gr);
  }
  return t("history_conflict_link_no_clauses").replace("{gr}", gr);
}

function useDebouncedValue(value, delayMs) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

function ConflictRow({ conflict, draftId, t, onDismiss, copiedRef, onCopyRef }) {
  const isCopied = copiedRef === conflict.conflict_ref;
  return (
    <div
      style={{
        border: "1.5px solid var(--ink)",
        borderRadius: "8px",
        background: "#fff",
        padding: "14px 16px",
        marginBottom: "12px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap", marginBottom: "8px" }}>
        <code
          style={{
            fontFamily: "monospace",
            fontSize: "12.5px",
            background: "#efece5",
            border: "1px solid var(--line)",
            borderRadius: "4px",
            padding: "3px 8px",
          }}
        >
          {conflict.conflict_ref}
        </code>
        <button
          type="button"
          onClick={() => onCopyRef(conflict.conflict_ref)}
          style={{
            border: "1px solid var(--ink)",
            background: "var(--paper)",
            borderRadius: "5px",
            padding: "3px 8px",
            fontSize: "11px",
            fontWeight: 700,
            cursor: "pointer",
          }}
        >
          {isCopied ? "Copied" : "Copy"}
        </button>
        <span className={`badge badge-severity-${conflict.severity}`}>{t(`severity_${conflict.severity}`)}</span>
        {conflict.is_dismissed && <span className="badge badge-inactive">{t("history_dismissed_label")}</span>}
      </div>

      <div style={{ fontSize: "13.5px", fontWeight: 600, marginBottom: "10px", color: "var(--ink)" }}>
        {conflictLinkLine(conflict, t)}
      </div>

      <div
        className="conflict-text-grid"
        style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px", marginBottom: "10px" }}
      >
        <div>
          <div style={{ fontSize: "11px", fontWeight: 700, textTransform: "uppercase", color: "var(--ink-soft)", marginBottom: "4px" }}>
            {t("history_conflicting_text")}
          </div>
          <div style={{ fontSize: "13.5px", background: "#faf9f6", border: "1px solid var(--line)", borderRadius: "6px", padding: "10px", lineHeight: 1.5 }}>
            {conflict.conflicting_text || "—"}
          </div>
        </div>
        <div>
          <div style={{ fontSize: "11px", fontWeight: 700, textTransform: "uppercase", color: "var(--ink-soft)", marginBottom: "4px" }}>
            {t("history_draft_excerpt")}
          </div>
          <div style={{ fontSize: "13.5px", background: "#faf9f6", border: "1px solid var(--line)", borderRadius: "6px", padding: "10px", lineHeight: 1.5 }}>
            {conflict.draft_excerpt || "—"}
          </div>
        </div>
      </div>

      {conflict.justification && (
        <div style={{ fontSize: "13px", color: "var(--ink-soft)", marginBottom: "10px" }}>
          <strong style={{ color: "var(--ink)" }}>{t("history_justification")}</strong> {conflict.justification}
        </div>
      )}

      {conflict.is_dismissed ? (
        conflict.dismissed_reason && (
          <div style={{ fontSize: "12.5px", color: "var(--ink-soft)", fontStyle: "italic" }}>
            {conflict.dismissed_reason}
          </div>
        )
      ) : (
        <button
          type="button"
          onClick={() => onDismiss(draftId, conflict)}
          style={{
            border: "1.5px solid var(--ink)",
            background: "var(--paper)",
            borderRadius: "6px",
            padding: "6px 12px",
            fontSize: "12px",
            fontWeight: 700,
            cursor: "pointer",
          }}
        >
          {t("history_dismiss_action")}
        </button>
      )}
    </div>
  );
}

function ConflictPanel({ draftId, conflicts, loading, t, onDismiss, copiedRef, onCopyRef, showDismissed, onToggleDismissed }) {
  if (loading) {
    return (
      <div style={{ padding: "16px 4px", display: "flex", flexDirection: "column", gap: "8px" }}>
        {[0, 1, 2].map((i) => (
          <div key={i} style={{ height: "14px", width: `${88 - i * 14}%`, background: "#e5e3dc", borderRadius: "4px" }} />
        ))}
      </div>
    );
  }

  const all = conflicts || [];
  if (all.length === 0) {
    return <div style={{ padding: "16px 4px", fontSize: "13.5px", color: "var(--ink-soft)" }}>{t("history_no_conflicts")}</div>;
  }

  const active = all.filter((c) => !c.is_dismissed);
  const dismissed = all.filter((c) => c.is_dismissed);
  const visible = showDismissed ? all : active;

  return (
    <div style={{ padding: "16px 4px" }}>
      {dismissed.length > 0 && (
        <button
          type="button"
          onClick={onToggleDismissed}
          style={{
            border: "1.5px solid var(--ink)",
            background: showDismissed ? "var(--ink)" : "var(--paper)",
            color: showDismissed ? "var(--cream)" : "var(--ink)",
            borderRadius: "6px",
            padding: "6px 12px",
            fontSize: "12px",
            fontWeight: 700,
            cursor: "pointer",
            marginBottom: "14px",
          }}
        >
          {`${t("history_show_dismissed")} (${dismissed.length})`}
        </button>
      )}
      {visible.length === 0 ? (
        <div style={{ fontSize: "13.5px", color: "var(--ink-soft)" }}>{t("history_no_conflicts")}</div>
      ) : (
        visible.map((c) => (
          <ConflictRow
            key={c.conflict_id}
            conflict={c}
            draftId={draftId}
            t={t}
            onDismiss={onDismiss}
            copiedRef={copiedRef}
            onCopyRef={onCopyRef}
          />
        ))
      )}
    </div>
  );
}

// The "History version list" (Task 1): the append-only workflow_events
// trail for a draft, each row showing a truncated content_sha256 with
// copy + Verify affordances (see HashBadge) — reuses the same
// GET .../workflow-history and GET .../versions/{n}/verify endpoints
// the Approval tab uses, rather than a separate versions-listing route.
function VersionsPanel({ draftId, events, loading, t }) {
  if (loading) {
    return (
      <div style={{ padding: "16px 4px", display: "flex", flexDirection: "column", gap: "8px" }}>
        {[0, 1].map((i) => (
          <div key={i} style={{ height: "14px", width: `${70 - i * 14}%`, background: "#e5e3dc", borderRadius: "4px" }} />
        ))}
      </div>
    );
  }

  const all = events || [];
  if (all.length === 0) {
    return <div style={{ padding: "16px 4px", fontSize: "13.5px", color: "var(--ink-soft)" }}>{t("history_versions_empty")}</div>;
  }

  return (
    <div style={{ padding: "16px 4px" }}>
      {all.map((e) => (
        <div
          key={e.event_id}
          style={{
            border: "1.5px solid var(--ink)",
            borderRadius: "8px",
            background: "#fff",
            padding: "12px 16px",
            marginBottom: "10px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8, marginBottom: 8 }}>
            <div style={{ fontSize: 13.5, fontWeight: 700 }}>
              {t(`workflow_event_${e.decision}`) || e.decision}
              <span style={{ fontWeight: 500, color: "var(--ink-soft)" }}>
                {" "}
                — {e.actor_name || "—"} ({e.actor_role})
              </span>
            </div>
            <div style={{ fontSize: 12, color: "var(--ink-soft)" }}>{formatIST(e.created_at)}</div>
          </div>
          {e.content_version_after != null && <HashBadge draftId={draftId} versionNumber={e.content_version_after} />}
        </div>
      ))}
    </div>
  );
}

export default function History() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const { setDraftResult, setAnalysisReport } = useDraft();

  // Admin drill-down: /history?officer_id=<id>&officer_name=<name>, set
  // by the "View History" button on the Admin officers table. Reuses
  // this entire page (conflict expansion/dismiss, exports, archive)
  // instead of a second read-only view — every draft-scoped endpoint
  // below already allows admin access to any officer's drafts.
  const [searchParams] = useSearchParams();
  const viewingOfficerId = isAdmin ? searchParams.get("officer_id") : null;
  const viewingOfficerName = searchParams.get("officer_name") || "";

  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search, 300);
  const [department, setDepartment] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  // Conflict expansion — cached per draft id so re-expanding is instant.
  const [expandedDraftId, setExpandedDraftId] = useState(null);
  const [conflictsByDraft, setConflictsByDraft] = useState({});
  const [conflictsLoadingId, setConflictsLoadingId] = useState(null);
  const [showDismissedByDraft, setShowDismissedByDraft] = useState({});
  const [copiedRef, setCopiedRef] = useState(null);

  // Version/workflow-history expansion (Task 1: "the History version
  // list") — independent of the conflicts expansion above, cached the
  // same way. Each row shows the append-only workflow_events trail with
  // a hash + Verify affordance per content version.
  const [expandedVersionsId, setExpandedVersionsId] = useState(null);
  const [versionsByDraft, setVersionsByDraft] = useState({});
  const [versionsLoadingId, setVersionsLoadingId] = useState(null);

  const [exportingKey, setExportingKey] = useState(null); // `${draftId}:pdf` | `${draftId}:docx`
  const [archivingId, setArchivingId] = useState(null);
  const [actionError, setActionError] = useState("");

  // Reset to page 1 whenever a filter changes.
  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, department, status]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadError("");

    // The officer-scoped admin endpoint only supports pagination — no
    // search/department/status filters — so those controls are hidden
    // in this mode (see the toolbar below) rather than silently doing
    // nothing.
    const fetchPromise = viewingOfficerId
      ? api.adminGetOfficerDrafts(viewingOfficerId, { page, page_size: pageSize })
      : api.getDraftHistory({
          search: debouncedSearch,
          department,
          status,
          sort_by: "created_at",
          sort_desc: true,
          page,
          page_size: pageSize,
        });

    fetchPromise
      .then((res) => {
        if (cancelled) return;
        setItems(res.items || []);
        setTotal(res.total || 0);
      })
      .catch((err) => {
        if (cancelled) return;
        setLoadError(err.message || "Failed to load draft history.");
        setItems([]);
        setTotal(0);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [debouncedSearch, department, status, page, viewingOfficerId]);

  const toggleVersions = useCallback(
    async (draftId) => {
      if (expandedVersionsId === draftId) {
        setExpandedVersionsId(null);
        return;
      }
      setExpandedVersionsId(draftId);
      if (versionsByDraft[draftId]) return; // already cached
      setVersionsLoadingId(draftId);
      try {
        const events = await api.getWorkflowHistory(draftId);
        setVersionsByDraft((prev) => ({ ...prev, [draftId]: events || [] }));
      } catch {
        setVersionsByDraft((prev) => ({ ...prev, [draftId]: [] }));
      } finally {
        setVersionsLoadingId(null);
      }
    },
    [expandedVersionsId, versionsByDraft]
  );

  const toggleConflicts = useCallback(
    async (draftId) => {
      if (expandedDraftId === draftId) {
        setExpandedDraftId(null);
        return;
      }
      setExpandedDraftId(draftId);
      if (conflictsByDraft[draftId]) return; // already cached
      setConflictsLoadingId(draftId);
      try {
        const conflicts = await api.getDraftConflicts(draftId, true);
        setConflictsByDraft((prev) => ({ ...prev, [draftId]: conflicts || [] }));
      } catch {
        setConflictsByDraft((prev) => ({ ...prev, [draftId]: [] }));
      } finally {
        setConflictsLoadingId(null);
      }
    },
    [expandedDraftId, conflictsByDraft]
  );

  const handleDismiss = useCallback(
    async (draftId, conflict) => {
      const reason = window.prompt(t("history_dismiss_prompt"));
      if (reason === null) return; // user cancelled the prompt
      try {
        const updated = await api.dismissConflict(conflict.conflict_id, reason || null);
        setConflictsByDraft((prev) => ({
          ...prev,
          [draftId]: (prev[draftId] || []).map((c) => (c.conflict_id === conflict.conflict_id ? updated : c)),
        }));
      } catch (err) {
        window.alert(err.message || "Failed to dismiss conflict.");
      }
    },
    [t]
  );

  const handleCopyRef = useCallback((ref) => {
    navigator.clipboard.writeText(ref).then(() => {
      setCopiedRef(ref);
      setTimeout(() => setCopiedRef(null), 2000);
    });
  }, []);

  const handleOpen = async (draftId) => {
    setActionError("");
    try {
      const detail = await api.getDraftDetail(draftId);
      const fullDraftObj = {
        draft_id: detail.generated_draft_id,
        title: detail.title,
        department: detail.department,
        body_text: detail.content,
        language: detail.language,
        created_at: detail.created_at,
        gr_number: detail.gr_number,
        references: detail.references || [],
        status: detail.status,
        returned_reason: detail.returned_reason,
      };
      setDraftResult(fullDraftObj);
      setAnalysisReport({
        conflicts: detail.conflicts || [],
        references: detail.references || [],
        template_issues: [],
      });
      navigate("/draft");
    } catch (err) {
      setActionError(err.message || "Failed to open this draft.");
    }
  };

  const handleDownloadPdf = async (draftId) => {
    const key = `${draftId}:pdf`;
    setActionError("");
    setExportingKey(key);
    try {
      const detail = await api.getDraftDetail(draftId);
      await generateGRDocumentPDF(
        {
          title: detail.title,
          gr_number: detail.gr_number,
          language: detail.language,
          draft_id: detail.generated_draft_id,
        },
        detail.content
      );
    } catch (err) {
      setActionError(err.message || "PDF export failed.");
    } finally {
      setExportingKey(null);
    }
  };

  const handleDownloadDocx = async (draftId) => {
    const key = `${draftId}:docx`;
    setActionError("");
    setExportingKey(key);
    try {
      const { blob, filename } = await api.exportDocx(draftId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setActionError(err.message || "DOCX export failed.");
    } finally {
      setExportingKey(null);
    }
  };

  const handleArchive = async (draftId) => {
    if (!window.confirm(t("history_confirm_archive"))) return;
    setActionError("");
    setArchivingId(draftId);
    try {
      await api.archiveDraft(draftId);
      setItems((prev) => prev.map((it) => (it.generated_draft_id === draftId ? { ...it, status: "archived" } : it)));
    } catch (err) {
      setActionError(err.message || "Failed to archive this draft.");
    } finally {
      setArchivingId(null);
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <main className="container history-page">
      <style>{`
        @media (max-width: 720px) {
          .history-page .data-table-wrap {
            overflow-x: visible;
            border: none;
            box-shadow: none;
            background: transparent;
          }
          .history-page .data-table { min-width: 0; display: block; }
          .history-page .data-table thead { display: none; }
          .history-page .data-table tbody { display: block; }
          .history-page .data-table tr {
            display: block;
            margin-bottom: 16px;
            border: 2px solid var(--ink);
            border-radius: var(--radius);
            background: var(--paper);
            box-shadow: 0 3px 0 var(--ink);
          }
          .history-page .data-table td {
            display: block;
            border-bottom: 1px solid var(--line);
            padding: 10px 14px;
            text-align: right;
          }
          .history-page .data-table td::before {
            content: attr(data-label);
            float: left;
            font-weight: 700;
            font-size: 11px;
            text-transform: uppercase;
            color: var(--ink-soft);
            margin-right: 10px;
          }
          .history-page .data-table td:last-child { border-bottom: none; }
          .history-page .data-table td.conflict-panel-cell {
            text-align: left;
            padding: 4px;
          }
          .history-page .data-table td.conflict-panel-cell::before { content: none; }
          .history-page .icon-btn-row { justify-content: flex-end; }
          .history-page .conflict-text-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>

      <header className="page-head">
        <div className="eyebrow">{t("history_eyebrow")}</div>
        <h1 className="page-title">{t("history_title")}</h1>
      </header>

      {viewingOfficerId && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: 12,
            background: "#eef2ff",
            border: "2px solid var(--ink)",
            borderRadius: 8,
            padding: "10px 16px",
            marginBottom: 20,
            fontWeight: 700,
            fontSize: 14,
          }}
        >
          <span>{t("history_admin_viewing_banner").replace("{name}", viewingOfficerName || viewingOfficerId)}</span>
          <button type="button" className="btn btn-outline-warn" style={{ minHeight: 34, padding: "0 12px" }} onClick={() => navigate("/admin")}>
            {t("history_admin_back_to_admin")}
          </button>
        </div>
      )}

      {!viewingOfficerId && (
      <div className="data-toolbar">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t("history_search_placeholder")}
        />
        <select
          aria-label={t("history_filter_department")}
          value={department}
          onChange={(e) => setDepartment(e.target.value)}
        >
          <option value="">{t("history_filter_department")}: {t("admin_filter_all")}</option>
          {DEPARTMENTS.map((d) => (
            <option key={d.value} value={d.value}>
              {d.label}
            </option>
          ))}
        </select>
        <select aria-label={t("history_filter_status")} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">{t("history_filter_status")}: {t("admin_filter_all")}</option>
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {t(`status_${s}`)}
            </option>
          ))}
        </select>
      </div>
      )}

      {(loadError || actionError) && (
        <div className="error-box" style={{ marginBottom: "16px" }}>
          {loadError || actionError}
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: "center", padding: "70px 0" }}>
          <span className="spinner" />
        </div>
      ) : items.length === 0 ? (
        <div className="empty-panel">
          <h3 style={{ marginTop: 0 }}>{t("history_empty_title")}</h3>
          <p style={{ marginBottom: "20px" }}>{t("history_empty_desc")}</p>
          <Link to="/draft" className="btn btn-red" style={{ textDecoration: "none", display: "inline-flex" }}>
            {t("draft_generate_btn")}
          </Link>
        </div>
      ) : (
        <>
          <div className="data-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("history_col_gr_number")}</th>
                  <th>{t("history_col_title")}</th>
                  <th>{t("history_col_department")}</th>
                  <th>{t("history_col_language")}</th>
                  <th>{t("history_col_status")}</th>
                  <th>{t("history_col_conflicts")}</th>
                  <th>{t("history_col_created")}</th>
                  <th>{t("history_col_actions")}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const draftId = item.generated_draft_id;
                  const isExpanded = expandedDraftId === draftId;
                  const isVersionsExpanded = expandedVersionsId === draftId;
                  return (
                    <React.Fragment key={draftId}>
                      <tr>
                        <td data-label={t("history_col_gr_number")}>
                          <span title="Internal draft reference — not an official Government GR number">
                            {item.gr_number || "—"}
                          </span>
                        </td>
                        <td data-label={t("history_col_title")}>
                          {item.title}
                          {item.status === "draft" && item.returned_reason && (
                            <div
                              title={item.returned_reason}
                              style={{
                                marginTop: 4,
                                fontSize: 11.5,
                                fontWeight: 700,
                                color: "#92400e",
                                display: "flex",
                                alignItems: "center",
                                gap: 4,
                              }}
                            >
                              ⚠ {t("draft_returned_banner_title")}
                            </div>
                          )}
                        </td>
                        <td data-label={t("history_col_department")}>{departmentLabel(item.department)}</td>
                        <td data-label={t("history_col_language")}>{item.language === "mr" ? "मराठी" : "English"}</td>
                        <td data-label={t("history_col_status")}>
                          <span className={statusBadgeClass(item.status)}>{statusLabel(item.status, t)}</span>
                        </td>
                        <td data-label={t("history_col_conflicts")}>
                          <button
                            type="button"
                            onClick={() => toggleConflicts(draftId)}
                            className={`conflict-count-badge ${item.unresolved_conflict_count > 0 ? "has-conflicts" : ""}`}
                            style={{ cursor: "pointer", border: "1.5px solid var(--ink)" }}
                            title={isExpanded ? "Hide conflicts" : "Show conflicts"}
                          >
                            {item.unresolved_conflict_count}
                          </button>
                        </td>
                        <td data-label={t("history_col_created")}>{formatIST(item.created_at)}</td>
                        <td data-label={t("history_col_actions")}>
                          <div className="icon-btn-row">
                            <button type="button" onClick={() => handleOpen(draftId)}>
                              {t("history_action_open")}
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDownloadPdf(draftId)}
                              disabled={exportingKey === `${draftId}:pdf`}
                            >
                              {exportingKey === `${draftId}:pdf` ? <span className="spinner-small" /> : t("history_action_pdf")}
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDownloadDocx(draftId)}
                              disabled={exportingKey === `${draftId}:docx`}
                            >
                              {exportingKey === `${draftId}:docx` ? <span className="spinner-small" /> : t("history_action_docx")}
                            </button>
                            <button
                              type="button"
                              onClick={() => toggleVersions(draftId)}
                              title={isVersionsExpanded ? "Hide versions" : "Show version history"}
                            >
                              {t("history_versions_action")}
                            </button>
                            <button
                              type="button"
                              className="danger"
                              onClick={() => handleArchive(draftId)}
                              disabled={archivingId === draftId || item.status === "archived"}
                            >
                              {t("history_action_archive")}
                            </button>
                          </div>
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr>
                          <td colSpan={8} className="conflict-panel-cell" style={{ background: "#faf9f6" }}>
                            <ConflictPanel
                              draftId={draftId}
                              conflicts={conflictsByDraft[draftId]}
                              loading={conflictsLoadingId === draftId}
                              t={t}
                              onDismiss={handleDismiss}
                              copiedRef={copiedRef}
                              onCopyRef={handleCopyRef}
                              showDismissed={Boolean(showDismissedByDraft[draftId])}
                              onToggleDismissed={() =>
                                setShowDismissedByDraft((prev) => ({ ...prev, [draftId]: !prev[draftId] }))
                              }
                            />
                          </td>
                        </tr>
                      )}
                      {isVersionsExpanded && (
                        <tr>
                          <td colSpan={8} className="conflict-panel-cell" style={{ background: "#faf9f6" }}>
                            <VersionsPanel
                              draftId={draftId}
                              events={versionsByDraft[draftId]}
                              loading={versionsLoadingId === draftId}
                              t={t}
                            />
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: "16px", marginTop: "24px" }}>
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              style={{
                border: "1.5px solid var(--ink)",
                background: "var(--paper)",
                borderRadius: "6px",
                padding: "8px 16px",
                fontSize: "13px",
                fontWeight: 700,
                cursor: page <= 1 ? "not-allowed" : "pointer",
                opacity: page <= 1 ? 0.5 : 1,
              }}
            >
              ← Prev
            </button>
            <span style={{ fontSize: "13.5px", fontWeight: 700, color: "var(--ink-soft)" }}>
              {page} / {totalPages} ({total})
            </span>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              style={{
                border: "1.5px solid var(--ink)",
                background: "var(--paper)",
                borderRadius: "6px",
                padding: "8px 16px",
                fontSize: "13px",
                fontWeight: 700,
                cursor: page >= totalPages ? "not-allowed" : "pointer",
                opacity: page >= totalPages ? 0.5 : 1,
              }}
            >
              Next →
            </button>
          </div>
        </>
      )}
    </main>
  );
}
