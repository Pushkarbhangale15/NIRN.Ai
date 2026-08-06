import { useCallback, useEffect, useRef, useState } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";

import { api } from "../api.js";
import { useLanguage } from "../LanguageContext.jsx";
import { useAuth } from "../AuthContext.jsx";
import { statusBadgeClass, statusLabel } from "../constants/workflowStatus.js";
import DraftDiffView from "../components/drafting/DraftDiffView.jsx";
import { TiptapToolbar } from "../components/drafting/DraftViewer.jsx";
import { IconSave, IconPrint, IconCopy, IconCheck, IconDownload } from "../components/drafting/DraftViewer.jsx";
import { generateGRDocumentPDF } from "../utils/pdfExport.js";
import { convertGRToHTML } from "../utils/grFormat.js";
import HashBadge from "../components/HashBadge.jsx";

import TextAlign from '@tiptap/extension-text-align';
import { TextStyle } from '@tiptap/extension-text-style';
import { FontFamily } from '@tiptap/extension-font-family';
import { Color } from '@tiptap/extension-color';
import { FontSize } from '../utils/fontSizeExtension.js';

// Mirrored locally rather than shared, matching this codebase's existing
// convention (see History.jsx / Admin.jsx) of duplicating this one small
// helper instead of adding a shared-util dependency between pages.
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

function ErrorBanner({ message }) {
  if (!message) return null;
  return (
    <div className="error-box" style={{ marginBottom: 16 }}>
      {message}
    </div>
  );
}

const formatDepartmentName = (value) => {
  if (!value) return 'Government of Maharashtra';
  return value
    .replace(/_/g, ' ')
    .split(' ')
    .map((word) => (word ? word[0].toUpperCase() + word.slice(1).toLowerCase() : word))
    .join(' ');
};

function QueueCard({ item, onOpen, isOpen, columns, t }) {
  return (
    <div
      onClick={() => onOpen(item.generated_draft_id)}
      style={{
        background: isOpen ? "#eef2ff" : "var(--paper)",
        border: `2px solid ${isOpen ? "var(--blue)" : "var(--ink)"}`,
        borderRadius: 10,
        padding: "14px 16px",
        marginBottom: 12,
        cursor: "pointer",
        boxShadow: isOpen ? "0 3px 0 var(--blue)" : "0 3px 0 var(--ink)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 10, marginBottom: 6 }}>
        <div style={{ fontWeight: 700, fontSize: 14.5 }}>{item.title}</div>
        {item.unresolved_conflict_count > 0 && (
          <span className="conflict-count-badge has-conflicts" title={t("approval_col_conflicts")}>
            {item.unresolved_conflict_count}
          </span>
        )}
      </div>
      <div style={{ fontSize: 12.5, color: "var(--ink-soft)", marginBottom: 4 }}>
        {item.gr_number || "—"} · {(item.department || "").replace(/_/g, " ")}
      </div>
      {columns.map((col) => (
        <div key={col.label} style={{ fontSize: 12, color: "var(--ink-soft)" }}>
          <strong style={{ color: "var(--ink)" }}>{col.label}:</strong> {col.value}
        </div>
      ))}
    </div>
  );
}

// =====================================================================
// 5a — Reviewing Officer view
// =====================================================================

function ReviewingOfficerView() {
  const { t, siteLanguage } = useLanguage();
  const isMr = siteLanguage === 'mr';

  const [queue, setQueue] = useState([]);
  const [queueLoading, setQueueLoading] = useState(true);
  const [queueError, setQueueError] = useState("");

  const [openDraft, setOpenDraft] = useState(null);
  const [openLoading, setOpenLoading] = useState(false);
  const [openError, setOpenError] = useState("");

  const [forwarding, setForwarding] = useState(false);
  const [forwardError, setForwardError] = useState("");
  const [confirmMode, setConfirmMode] = useState(null); // null | 'unchanged' | 'edited'

  const [isSaving, setIsSaving] = useState(false);
  const [toast, setToast] = useState(null);
  const [exporting, setExporting] = useState(null);
  const [exportError, setExportError] = useState("");
  const [copied, setCopied] = useState(false);
  const [lastSavedAt, setLastSavedAt] = useState(null);

  const originalHtmlRef = useRef("");
  const [isDirty, setIsDirty] = useState(false);

  const editor = useEditor({
    extensions: [
      StarterKit, 
      Underline,
      TextAlign.configure({
        types: ['heading', 'paragraph'],
      }),
      TextStyle,
      FontFamily,
      Color,
      FontSize,
    ],
    content: "",
    onUpdate: ({ editor: ed }) => {
      setIsDirty(originalHtmlRef.current !== "" && ed.getHTML() !== originalHtmlRef.current);
    },
  });

  const fetchQueue = useCallback(async () => {
    setQueueLoading(true);
    setQueueError("");
    try {
      const res = await api.getReviewQueue({ page_size: 50 });
      setQueue(res.items || []);
    } catch (err) {
      setQueueError(err.message || "Failed to load the review queue.");
    } finally {
      setQueueLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchQueue();
  }, [fetchQueue]);

  const handleOpen = async (draftId) => {
    setOpenError("");
    setForwardError("");
    setOpenLoading(true);
    try {
      const detail = await api.getDraftDetail(draftId);
      setOpenDraft(detail);
      const formattedHtml = convertGRToHTML(detail.content, detail.language);
      originalHtmlRef.current = formattedHtml;
      setIsDirty(false);
      setLastSavedAt(null);
      editor?.commands.setContent(formattedHtml);
    } catch (err) {
      setOpenError(err.message || "Failed to open this draft.");
    } finally {
      setOpenLoading(false);
    }
  };

  const runForward = async (withEdits) => {
    if (!openDraft || forwarding) return;
    setForwarding(true);
    setForwardError("");
    try {
      if (withEdits) {
        await api.forwardToApproval(openDraft.generated_draft_id, editor.getHTML(), editor.getText());
      } else {
        await api.forwardToApproval(openDraft.generated_draft_id, null, null);
      }
      setConfirmMode(null);
      setOpenDraft(null);
      originalHtmlRef.current = "";
      setIsDirty(false);
      editor?.commands.setContent("");
      fetchQueue();
    } catch (err) {
      setForwardError(err.message || t("approval_forward_error"));
    } finally {
      setForwarding(false);
    }
  };

  const handleManualSave = async () => {
    if (!editor || isSaving) return;
    setIsSaving(true);
    setToast(null);
    try {
      const htmlContent = editor.getHTML();
      await api.saveDraftContent(openDraft.generated_draft_id, htmlContent, editor.getText());
      originalHtmlRef.current = htmlContent;
      setIsDirty(false);
      setLastSavedAt(new Date());
      setToast({ message: 'Document saved successfully! ✓', type: 'success' });
    } catch (err) {
      setToast({ message: 'Failed to save document.', type: 'error' });
    } finally {
      setIsSaving(false);
      setTimeout(() => setToast(null), 3000);
    }
  };

  const handleCopy = () => {
    if (!editor) return;
    navigator.clipboard.writeText(editor.getText()).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const handlePrint = () => window.print();

  const handleExportPdf = async () => {
    if (!editor || exporting) return;
    setExportError('');
    setExporting('pdf');
    try {
      await generateGRDocumentPDF(openDraft, editor.getHTML());
    } catch (err) {
      setExportError(t('export_error') || 'Export failed');
    } finally {
      setExporting(null);
    }
  };

  const handleExportDocx = async () => {
    if (!openDraft?.generated_draft_id || exporting) return;
    setExportError('');
    setExporting('docx');
    try {
      const { blob, filename } = await api.exportDocx(openDraft.generated_draft_id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(err.message || 'Export failed');
    } finally {
      setExporting(null);
    }
  };

  return (
    <div style={{ display: "grid", gridTemplateColumns: "360px 1fr", gap: 28, alignItems: "start" }} className="approval-grid">
      <div>
        <h2 style={{ fontFamily: "var(--font-display)", fontSize: 15, textTransform: "uppercase", marginBottom: 14 }}>
          {t("approval_tab_review_queue")} ({queue.length})
        </h2>
        <ErrorBanner message={queueError} />
        {queueLoading ? (
          <div style={{ textAlign: "center", padding: "30px 0" }}>
            <span className="spinner" />
          </div>
        ) : queue.length === 0 ? (
          <div className="empty-panel">{t("approval_queue_empty")}</div>
        ) : (
          queue.map((item) => (
            <QueueCard
              key={item.generated_draft_id}
              item={item}
              isOpen={openDraft?.generated_draft_id === item.generated_draft_id}
              onOpen={handleOpen}
              t={t}
              columns={[
                { label: t("approval_col_drafted_by"), value: item.drafted_by_name || "—" },
                { label: t("approval_col_submitted"), value: formatIST(item.created_at) },
              ]}
            />
          ))
        )}
      </div>

      <div>
        {openLoading && (
          <div style={{ textAlign: "center", padding: "60px 0" }}>
            <span className="spinner" />
          </div>
        )}
        <ErrorBanner message={openError} />
        {!openLoading && openDraft && (
          <>
            <div
              style={{
                background: "#eff6ff",
                border: "1.5px solid var(--blue)",
                color: "#1e40af",
                borderRadius: 8,
                padding: "12px 16px",
                fontSize: 13.5,
                fontWeight: 600,
                marginBottom: 16,
              }}
            >
              {t("approval_reviewing_banner").replace("{name}", openDraft.drafted_by_name || "—")}
            </div>

            <ErrorBanner message={forwardError} />

            <div className="gr-editor-card" style={{ marginBottom: 18 }}>
              {/* Top Header & Actions Bar */}
              <div className="gr-editor-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="official-badge">{t('draft_official')}</span>
                  <span className="gr-editor-dept-name">
                    {formatDepartmentName(openDraft.department)}
                  </span>
                </div>

                <div className="gr-editor-header-actions">
                  {toast && (
                    <span className={toast.type === 'success' ? 'saved-badge' : 'error-badge'}>
                      {toast.message}
                    </span>
                  )}
                  {!toast && isDirty && (
                    <span className="error-badge" style={{ background: '#fff3d6', color: '#9a6b00', borderColor: 'var(--yellow)' }}>
                      {t('save_unsaved_indicator')}
                    </span>
                  )}
                  {!toast && !isDirty && lastSavedAt && (
                    <span className="saved-badge">
                      {t('save_saved_at')} {lastSavedAt.toLocaleTimeString(isMr ? 'mr-IN' : 'en-IN', { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  )}
                  {exportError && <span className="error-badge">{exportError}</span>}

                  <div className="gr-editor-btn-group">
                    <button
                      type="button"
                      onClick={handleManualSave}
                      disabled={isSaving}
                      className="action-btn save-btn"
                      title="Save Document"
                    >
                      {isSaving ? <><span className="spinner-small" /> Saving...</> : <><IconSave /> Save</>}
                    </button>

                    <button
                      type="button"
                      onClick={handlePrint}
                      className="action-btn print-btn"
                      title="Print Document"
                    >
                      <IconPrint /> Print
                    </button>

                    <button
                      type="button"
                      onClick={handleCopy}
                      className="action-btn"
                    >
                      {copied ? <><IconCheck /> {t('draft_copied')}</> : <><IconCopy /> {t('draft_copy')}</>}
                    </button>

                    <button
                      type="button"
                      onClick={handleExportPdf}
                      disabled={Boolean(exporting)}
                      className="action-btn"
                      title={t('export_download_pdf')}
                    >
                      {exporting === 'pdf' ? <><span className="spinner-small" /> {t('export_exporting')}</> : <><IconDownload /> {t('export_download_pdf')}</>}
                    </button>

                    <button
                      type="button"
                      onClick={handleExportDocx}
                      disabled={Boolean(exporting)}
                      className="action-btn"
                      title={t('export_download_docx')}
                    >
                      {exporting === 'docx' ? <><span className="spinner-small" /> {t('export_exporting')}</> : <><IconDownload /> {t('export_download_docx')}</>}
                    </button>
                  </div>
                </div>
              </div>

              <TiptapToolbar editor={editor} />
              <div className={`a4-paper-wrapper ${isMr ? 'lang-marathi' : 'lang-english'}`} style={{ maxHeight: 480 }}>
                <div className="ProseMirror-print-wrapper">
                  <EditorContent editor={editor} />
                </div>
              </div>
            </div>

            <div className="btn-row">
              <button
                type="button"
                className="btn btn-ghost"
                style={{ border: "1.5px solid var(--ink)" }}
                disabled={forwarding}
                onClick={() => setConfirmMode("unchanged")}
              >
                {t("approval_forward_unchanged_btn")}
              </button>
              <button
                type="button"
                className="btn btn-red"
                disabled={forwarding || !isDirty}
                onClick={() => setConfirmMode("edited")}
              >
                {t("approval_forward_edited_btn")}
              </button>
            </div>
          </>
        )}
      </div>

      {confirmMode && (
        <div className="modal-overlay" onClick={forwarding ? undefined : () => setConfirmMode(null)}>
          <div className="modal-card" style={{ maxWidth: 460 }} onClick={(e) => e.stopPropagation()}>
            <h2>{t("approval_forward_confirm_title")}</h2>
            <p style={{ marginBottom: 20 }}>
              {confirmMode === "edited" ? t("approval_forward_confirm_edited") : t("approval_forward_confirm_unchanged")}
            </p>
            <div className="btn-row">
              <button
                type="button"
                className="btn btn-red"
                disabled={forwarding}
                onClick={() => runForward(confirmMode === "edited")}
              >
                {forwarding ? <span className="spinner-small" /> : t("approval_forward_confirm_btn")}
              </button>
              <button type="button" className="btn btn-outline-warn" disabled={forwarding} onClick={() => setConfirmMode(null)}>
                {t("admin_cancel")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// =====================================================================
// 5b — Approving Authority view
// =====================================================================

function WorkflowHistoryList({ events, t }) {
  if (!events || events.length === 0) {
    return <div style={{ fontSize: 13, color: "var(--ink-soft)" }}>{t("workflow_history_empty")}</div>;
  }
  return (
    <div>
      {events.map((e) => (
        <div
          key={e.event_id}
          style={{
            display: "flex",
            justifyContent: "space-between",
            gap: 12,
            fontSize: 12.5,
            padding: "8px 0",
            borderBottom: "1px solid var(--line)",
          }}
        >
          <div>
            <strong>{t(`workflow_event_${e.decision}`) || e.decision}</strong>
            <span style={{ color: "var(--ink-soft)" }}>
              {" "}
              — {e.actor_name || "—"} ({e.actor_role})
            </span>
            {e.note && <div style={{ color: "var(--ink-soft)", fontStyle: "italic", marginTop: 2 }}>{e.note}</div>}
          </div>
          <div style={{ color: "var(--ink-soft)", whiteSpace: "nowrap" }}>{formatIST(e.created_at)}</div>
        </div>
      ))}
    </div>
  );
}

function ApprovingAuthorityView() {
  const { t } = useLanguage();

  const [queue, setQueue] = useState([]);
  const [queueLoading, setQueueLoading] = useState(true);
  const [queueError, setQueueError] = useState("");

  const [selectedId, setSelectedId] = useState(null);
  const [view, setView] = useState(null);
  const [viewLoading, setViewLoading] = useState(false);
  const [viewError, setViewError] = useState("");

  const [confirmDecision, setConfirmDecision] = useState(null); // null | 'accept_reviewer_version' | 'keep_original'
  const [approving, setApproving] = useState(false);
  const [approveError, setApproveError] = useState("");

  const [returning, setReturning] = useState(false);
  const [returnError, setReturnError] = useState("");
  const [returnReason, setReturnReason] = useState("");
  const [showReturnForm, setShowReturnForm] = useState(false);

  const fetchQueue = useCallback(async () => {
    setQueueLoading(true);
    setQueueError("");
    try {
      const res = await api.getApprovalQueue({ page_size: 50 });
      setQueue(res.items || []);
    } catch (err) {
      setQueueError(err.message || "Failed to load the approval queue.");
    } finally {
      setQueueLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchQueue();
  }, [fetchQueue]);

  const handleOpen = async (draftId) => {
    setSelectedId(draftId);
    setViewError("");
    setApproveError("");
    setReturnError("");
    setShowReturnForm(false);
    setReturnReason("");
    setViewLoading(true);
    setView(null);
    try {
      const res = await api.getApprovalView(draftId);
      setView(res);
    } catch (err) {
      setViewError(err.message || "Failed to load this draft's approval view.");
    } finally {
      setViewLoading(false);
    }
  };

  const runApprove = async () => {
    if (!confirmDecision || !view || approving) return;
    setApproving(true);
    setApproveError("");
    try {
      await api.approveDraft(view.generated_draft_id, confirmDecision);
      setConfirmDecision(null);
      setSelectedId(null);
      setView(null);
      fetchQueue();
    } catch (err) {
      setApproveError(err.message || t("approval_approve_error"));
    } finally {
      setApproving(false);
    }
  };

  const runReturn = async (e) => {
    e.preventDefault();
    if (!view || returning) return;
    if (returnReason.trim().length < 20) {
      setReturnError(t("approval_return_reason_too_short"));
      return;
    }
    setReturning(true);
    setReturnError("");
    try {
      await api.returnDraft(view.generated_draft_id, returnReason.trim());
      setShowReturnForm(false);
      setSelectedId(null);
      setView(null);
      fetchQueue();
    } catch (err) {
      setReturnError(err.message || t("approval_return_error"));
    } finally {
      setReturning(false);
    }
  };

  return (
    <div style={{ display: "grid", gridTemplateColumns: "340px 1fr", gap: 28, alignItems: "start" }} className="approval-grid">
      <div>
        <h2 style={{ fontFamily: "var(--font-display)", fontSize: 15, textTransform: "uppercase", marginBottom: 14 }}>
          {t("approval_tab_approval_queue")} ({queue.length})
        </h2>
        <ErrorBanner message={queueError} />
        {queueLoading ? (
          <div style={{ textAlign: "center", padding: "30px 0" }}>
            <span className="spinner" />
          </div>
        ) : queue.length === 0 ? (
          <div className="empty-panel">{t("approval_queue_empty")}</div>
        ) : (
          queue.map((item) => (
            <QueueCard
              key={item.generated_draft_id}
              item={item}
              isOpen={selectedId === item.generated_draft_id}
              onOpen={handleOpen}
              t={t}
              columns={[
                { label: t("approval_col_drafted_by"), value: item.drafted_by_name || "—" },
                { label: t("approval_col_reviewed_by"), value: item.reviewed_by_name || "—" },
                { label: t("approval_col_reviewed"), value: formatIST(item.updated_at) },
              ]}
            />
          ))
        )}
      </div>

      <div>
        {viewLoading && (
          <div style={{ textAlign: "center", padding: "60px 0" }}>
            <span className="spinner" />
          </div>
        )}
        <ErrorBanner message={viewError} />
        {!viewLoading && view && (
          <>
            <div style={{ marginBottom: 16 }}>
              <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 4 }}>{view.title}</h3>
              <div style={{ fontSize: 12.5, color: "var(--ink-soft)" }}>
                {view.gr_number || "—"} · {(view.department || "").replace(/_/g, " ")} ·{" "}
                <span className={statusBadgeClass(view.status)}>{statusLabel(view.status, t)}</span>
              </div>
            </div>

            <DraftDiffView
              segments={view.diff.segments}
              additions={view.diff.additions}
              deletions={view.diff.deletions}
              unchanged={view.diff.unchanged}
            />

            <div style={{ display: "flex", flexWrap: "wrap", gap: 12, margin: "16px 0" }}>
              <HashBadge
                draftId={view.generated_draft_id}
                versionNumber={view.submitted_version_number}
                hash={view.submitted_content_sha256}
                label={`${t("diff_before_label")} — ${t("integrity_hash_label")}`}
              />
              <HashBadge
                draftId={view.generated_draft_id}
                versionNumber={view.reviewed_version_number}
                hash={view.reviewed_content_sha256}
                label={`${t("diff_after_label")} — ${t("integrity_hash_label")}`}
              />
            </div>

            <div style={{ marginBottom: 20 }}>
              <h4 style={{ fontSize: 13, fontWeight: 700, textTransform: "uppercase", marginBottom: 8, color: "var(--ink-soft)" }}>
                {t("workflow_history_title")}
              </h4>
              <WorkflowHistoryList events={view.workflow_history} t={t} />
            </div>

            <ErrorBanner message={approveError} />
            <ErrorBanner message={returnError} />

            {!showReturnForm ? (
              <div className="btn-row">
                <button type="button" className="btn btn-red" onClick={() => setConfirmDecision("accept_reviewer_version")}>
                  {t("approval_accept_btn")}
                </button>
                <button
                  type="button"
                  className="btn"
                  style={{ border: "1.5px solid var(--ink)", background: "var(--paper)" }}
                  onClick={() => setConfirmDecision("keep_original")}
                >
                  {t("approval_keep_original_btn")}
                </button>
                <button type="button" className="btn btn-outline-warn" onClick={() => setShowReturnForm(true)}>
                  {t("approval_return_btn")}
                </button>
              </div>
            ) : (
              <form onSubmit={runReturn} className="panel" style={{ padding: 20 }}>
                <div className="field">
                  <label htmlFor="return-reason">{t("approval_return_reason_label")}</label>
                  <textarea
                    id="return-reason"
                    value={returnReason}
                    onChange={(e) => setReturnReason(e.target.value)}
                    placeholder={t("approval_return_reason_placeholder")}
                    style={{ minHeight: 100 }}
                    required
                  />
                </div>
                <div className="btn-row">
                  <button type="submit" className="btn btn-red" disabled={returning}>
                    {returning ? <span className="spinner-small" /> : t("approval_return_confirm_btn")}
                  </button>
                  <button
                    type="button"
                    className="btn btn-outline-warn"
                    disabled={returning}
                    onClick={() => setShowReturnForm(false)}
                  >
                    {t("admin_cancel")}
                  </button>
                </div>
              </form>
            )}
          </>
        )}
      </div>

      {confirmDecision && (
        <div className="modal-overlay" onClick={approving ? undefined : () => setConfirmDecision(null)}>
          <div className="modal-card" style={{ maxWidth: 460 }} onClick={(e) => e.stopPropagation()}>
            <h2>{t("approval_approve_confirm_title")}</h2>
            <p style={{ marginBottom: 20 }}>{t("approval_approve_confirm_body")}</p>
            <div className="btn-row">
              <button type="button" className="btn btn-red" disabled={approving} onClick={runApprove}>
                {approving ? <span className="spinner-small" /> : t("approval_approve_confirm_btn")}
              </button>
              <button
                type="button"
                className="btn btn-outline-warn"
                disabled={approving}
                onClick={() => setConfirmDecision(null)}
              >
                {t("admin_cancel")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// =====================================================================
// Entry point — route already guards non-reviewer/non-admin visitors
// (see App.jsx's RequireReviewerOrAdmin); role is a single enum value
// per officer, so exactly one of these two views ever renders.
// =====================================================================

export default function Approval() {
  const { t } = useLanguage();
  const { isAdmin, isReviewer } = useAuth();

  return (
    <main className="container" style={{ paddingBottom: 60 }}>
      <style>{`
        @media (max-width: 960px) {
          .approval-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
      <header className="page-head">
        <div className="eyebrow">{t("approval_eyebrow")}</div>
        <h1 className="page-title">{t("approval_title")}</h1>
      </header>
      <div style={{ marginTop: 20 }}>{isAdmin ? <ApprovingAuthorityView /> : isReviewer ? <ReviewingOfficerView /> : null}</div>
    </main>
  );
}
