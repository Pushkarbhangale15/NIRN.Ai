import { useState, useEffect } from "react";
import { api } from "../api.js";
import { useLanguage } from "../LanguageContext.jsx";
import { useDraft } from "../DraftContext.jsx";
import { conflictOutToHit } from "../utils/conflictMapping.js";

import WorkflowStepper from "../components/drafting/WorkflowStepper.jsx";
import DraftInputCard from "../components/drafting/DraftInputCard.jsx";
import DraftViewer from "../components/drafting/DraftViewer.jsx";
import ComplianceCard from "../components/drafting/ComplianceCard.jsx";
import ConflictCard from "../components/drafting/ConflictCard.jsx";
import ReferencesCard from "../components/drafting/ReferencesCard.jsx";
import TerminologyCard from "../components/drafting/TerminologyCard.jsx";
import SuggestionsCard from "../components/drafting/SuggestionsCard.jsx";

const IconChecklist = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
    <path d="M3 5h2v2H3zm4 0h14v2H7zM3 11h2v2H3zm4 0h14v2H7zM3 17h2v2H3zm4 0h14v2H7z" />
  </svg>
);
const IconWarningTriangle = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
    <path d="M1 21h22L12 2 1 21Zm12-3h-2v-2h2Zm0-4h-2v-4h2Z" />
  </svg>
);
const IconLink = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
    <path d="M3.9 12a5 5 0 0 1 5-5H13v2H8.9a3 3 0 0 0 0 6H13v2H8.9a5 5 0 0 1-5-5Zm7.1 1h2v-2h-2v-2H8.9a5 5 0 0 0 0 10H11v-2h-2.1a3 3 0 0 1 0-6H11Zm4.1-6H15v2h4.1a3 3 0 0 1 0 6H15v2h4.1a5 5 0 0 0 0-10Z" />
  </svg>
);
const IconTranslate = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
    <path d="M12.87 15.07-2.54-2.51.03-.03A17.5 17.5 0 0 0 8.36 6H10v2H7.75l-.09.34a15.3 15.3 0 0 1-2.1 4.06 12.34 12.34 0 0 0 3.8-2.13Zm5.63-1.53H16l-4.5 12h1.75l1.13-3h5.24l1.13 3H22ZM14.9 15h4.2L17 10.35Z" />
    <path d="M11 4H2v2h2.5v1H2v2h2.5A9.5 9.5 0 0 0 2 14h2c.15-.63.36-1.24.63-1.8A11 11 0 0 0 6 14h2a10 10 0 0 1-1.9-2.4A8.4 8.4 0 0 0 6.5 9H11Z" />
  </svg>
);
const IconLightbulb = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
    <path d="M9 21h6v-1H9zm3-19a7 7 0 0 0-4 12.74V17a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-2.26A7 7 0 0 0 12 2Z" />
  </svg>
);
const IconAlert = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="currentColor" viewBox="0 0 24 24">
    <path d="M1 21h22L12 2 1 21Zm12-3h-2v-2h2Zm0-4h-2v-4h2Z" />
  </svg>
);

const REVIEW_TABS = [
  { id: "compliance", labelKey: "draft_tab_mop", Icon: IconChecklist },
  { id: "conflicts", labelKey: "draft_tab_conflicts", Icon: IconWarningTriangle },
  { id: "references", labelKey: "draft_tab_references", Icon: IconLink },
  { id: "terminology", labelKey: "draft_tab_terminology", Icon: IconTranslate },
  { id: "suggestions", labelKey: "draft_tab_suggestions", Icon: IconLightbulb },
];

export default function Draft() {
  const { t } = useLanguage();
  const {
    prompt, setPrompt,
    language, setLanguage,
    department, setDepartment,
    loading,
    analysisLoading,
    currentStage,
    draftResult, setDraftResult,
    analysisReport, setAnalysisReport,
    error,
    activeReviewTab, setActiveReviewTab,
    handleGenerate,
    handleReset,
    handleSaveDraft,
    handleSubmitForReview
  } = useDraft();

  // Shared across "Resolve All" and "Resolve Selected" — both run the same
  // sequential batch, and a single in-flight flag naturally prevents the two
  // entry points from ever running two batches concurrently.
  const [resolvingBatch, setResolvingBatch] = useState(false);
  const [batchProgress, setBatchProgress] = useState(null);
  const [ignoringSelected, setIgnoringSelected] = useState(false);
  // The single conflict currently being fixed by hand in the editor (see
  // handleManualEditSelected) — drives DraftViewer's highlightTarget prop.
  // null means "not in manual-edit mode".
  const [editingConflict, setEditingConflict] = useState(null);
  // conflict_id -> { revisedClause, originalClause, grLabel }. Derived from
  // the server's persisted resolution_status/resolved_clause_text on every
  // analysisReport change below — NOT recomputed locally-only — so a page
  // reload shows the same resolved state without re-running resolution.
  const [resolvedInfo, setResolvedInfo] = useState({});

  // Filter conflicts into cross-departmental vs own-department
  const allConflicts = analysisReport?.conflicts || [];

  // Source of truth for "is this conflict resolved": the persisted
  // resolution_status field on each conflict, not a client-only flag —
  // this is what makes resolved state survive a page reload.
  useEffect(() => {
    const derived = {};
    for (const c of allConflicts) {
      if (c.conflict_id && c.resolution_status === "resolved") {
        derived[c.conflict_id] = {
          revisedClause: c.resolved_clause_text || "",
          originalClause: c.draft_clause,
          grLabel: c.existing_gr_title || c.existing_gr_id,
          grId: c.existing_gr_id,
        };
      }
    }
    setResolvedInfo(derived);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analysisReport]);
  const normDraft = (draftResult?.department || department || "").toLowerCase().replace(/_/g, " ").trim();

  const ownDeptConflicts = allConflicts.filter(c => {
    const normExist = (c.existing_department || "").toLowerCase().replace(/_/g, " ").trim();
    return normDraft && normExist && normDraft === normExist;
  });

  const crossDeptConflicts = allConflicts.filter(c => {
    const normExist = (c.existing_department || "").toLowerCase().replace(/_/g, " ").trim();
    return normDraft && normExist && normDraft !== normExist;
  });

  const resolveConflictBatch = async (conflictsToResolve) => {
    const draftId = draftResult?.draft_id;
    // Skip conflicts the server already durably marked resolved (retrying
    // these would regenerate against stale original-clause text and fail
    // every time) and any that were ignored — dismissed conflicts are never
    // auto-resolved.
    const resolvable = conflictsToResolve.filter(
      c => c.conflict_id && c.resolution_status !== "resolved" && !c.is_dismissed
    );
    if (!draftId || resolvingBatch || resolvable.length === 0) return;

    setResolvingBatch(true);
    setBatchProgress({ done: 0, total: resolvable.length });
    let failedCount = 0;

    // "reword" alone often can't fix a substantive funding/scope conflict —
    // it only rephrases wording. Fall back to "add_carve_out" (explicitly
    // excludes the overlapping scope), then "defer_to_existing" (explicitly
    // subordinates this clause to the existing GR) before giving up on a
    // conflict, since each is progressively more likely to genuinely clear it.
    const STRATEGIES = ["reword", "add_carve_out", "defer_to_existing"];

    // _rev is a server-driven-overwrite marker: DraftViewer only reloads
    // Tiptap's content when this changes, so an accepted resolution shows up
    // in the editor without resetting cursor/undo on every unrelated
    // re-render (e.g. after the user's own manual save).
    const refreshEditorContent = async () => {
      try {
        const updatedDraft = await api.getDraftDetail(draftId);
        setDraftResult(prev => prev ? {
          ...prev,
          body_text: updatedDraft.content,
          _rev: (prev._rev || 0) + 1,
        } : prev);
      } catch (err) {
        console.warn("Editor refresh failed:", err);
      }
    };

    for (const conflict of resolvable) {
      let clearedThisConflict = false;
      try {
        for (const strategy of STRATEGIES) {
          const result = await api.resolveConflict(conflict.conflict_id, strategy);
          if (result.cleared) {
            await api.acceptConflictResolution(conflict.conflict_id, result.revised_clause);
            clearedThisConflict = true;
            setResolvedInfo(prev => ({
              ...prev,
              [conflict.conflict_id]: {
                revisedClause: result.revised_clause,
                originalClause: result.original_clause,
                grLabel: conflict.existing_gr_title || conflict.existing_gr_id,
                grId: conflict.existing_gr_id,
              },
            }));
            // Reflect this resolution in the editor immediately — don't
            // wait for the rest of the batch to finish.
            await refreshEditorContent();
            break;
          }
        }
      } catch (err) {
        console.warn("Resolve conflict failed:", conflict.conflict_id, err);
      }
      if (!clearedThisConflict) failedCount += 1;
      setBatchProgress(prev => ({ done: (prev?.done || 0) + 1, total: resolvable.length }));
    }

    // Refresh from what's already persisted rather than re-running detection:
    // detection is a fresh, non-deterministic LLM pass, so calling it here
    // (just to refresh the displayed list after a resolve) could surface a
    // different set of conflicts each time and inflate the shown count on
    // repeated resolve batches. A plain read reflects exactly what resolving
    // just changed, nothing more.
    try {
      const conflicts = await api.getDraftConflicts(draftId, true);
      setAnalysisReport(prev => prev ? { ...prev, conflicts: conflicts.map(conflictOutToHit) } : prev);
    } catch (err) {
      console.warn("Post-resolve conflict refresh warning:", err);
    }

    setResolvingBatch(false);
    setBatchProgress(null);

    if (failedCount > 0) {
      window.alert(
        `${resolvable.length - failedCount} of ${resolvable.length} conflicts resolved automatically. ` +
        `${failedCount} could not be cleared and still need manual review.`
      );
    }
  };

  const handleResolveAllConflicts = () => resolveConflictBatch(allConflicts);
  const handleResolveSelected = (selected) => resolveConflictBatch(selected);

  const handleIgnoreSelected = async (selected) => {
    const draftId = draftResult?.draft_id;
    const toIgnore = selected.filter(c => c.conflict_id && !c.is_dismissed);
    if (!draftId || ignoringSelected || toIgnore.length === 0) return;

    // One shared reason for the whole batch — prompting per-item would mean
    // N popups for an N-conflict selection.
    const reason = window.prompt(
      `Why are you ignoring ${toIgnore.length === 1 ? "this conflict" : `these ${toIgnore.length} conflicts`}?`,
      ""
    );
    if (reason === null) return; // user cancelled

    setIgnoringSelected(true);
    for (const conflict of toIgnore) {
      try {
        await api.dismissConflict(conflict.conflict_id, reason || null);
      } catch (err) {
        console.warn("Dismiss failed:", conflict.conflict_id, err);
      }
    }

    try {
      const conflicts = await api.getDraftConflicts(draftId, true);
      setAnalysisReport(prev => prev ? { ...prev, conflicts: conflicts.map(conflictOutToHit) } : prev);
    } catch (err) {
      console.warn("Post-ignore conflict refresh warning:", err);
    }

    setIgnoringSelected(false);
  };

  const handleManualEditSelected = (conflict) => setEditingConflict(conflict);
  const handleCancelManualEdit = () => setEditingConflict(null);

  const handleMarkResolved = async (revisedText) => {
    const draftId = draftResult?.draft_id;
    if (!editingConflict || !draftId) return;

    await api.markConflictResolved(editingConflict.conflict_id, revisedText);
    setEditingConflict(null);

    try {
      const conflicts = await api.getDraftConflicts(draftId, true);
      setAnalysisReport(prev => prev ? { ...prev, conflicts: conflicts.map(conflictOutToHit) } : prev);
    } catch (err) {
      console.warn("Post-mark-resolved conflict refresh warning:", err);
    }
  };

  return (
    <main className="container">
      <header className="page-head">
        <div className="eyebrow">{t('draft_eyebrow')}</div>
        <h1 className="page-title">{t('draft_title')}</h1>
        <p className="page-sub">{t('draft_sub')}</p>
      </header>

      <div className="copilot-panel-area" style={{ marginTop: '20px' }}>
        <div style={{ width: '100%' }}>
          {/* 1. Horizontal Parameter & Brief Header */}
          <DraftInputCard
            prompt={prompt}
            setPrompt={setPrompt}
            language={language}
            setLanguage={setLanguage}
            department={department}
            setDepartment={setDepartment}
            onGenerate={handleGenerate}
            loading={loading}
            onReset={handleReset}
          />

          {/* 2. Workflow Stepper — directly below the brief/generate
              action it tracks, above the generated result. */}
          <WorkflowStepper currentStage={currentStage} isGenerating={loading} />

          {/* 3. 2-Column Side-by-Side Workspace */}
          <div className="draft-workspace-two-col">

            {/* Left Column: Official Document Viewer */}
            <div>
              {error && (
                <div style={{
                  background: '#fee2e2',
                  border: '2px solid var(--red)',
                  color: 'var(--red)',
                  padding: '12px 16px',
                  borderRadius: '8px',
                  fontWeight: 'bold',
                  marginBottom: '16px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}>
                  <IconAlert /> {error}
                </div>
              )}
              {draftResult?.status === 'draft' && draftResult?.returned_reason && (
                <div className="returned-banner">
                  <strong>⚠ {t('draft_returned_banner_title')}</strong>
                  <span>{draftResult.returned_reason}</span>
                </div>
              )}
              <DraftViewer
                draft={draftResult}
                loading={loading}
                onSaveDraft={handleSaveDraft}
                onSubmitForReview={handleSubmitForReview}
                highlightTarget={editingConflict?.draft_clause}
                onMarkResolved={handleMarkResolved}
                onCancelManualEdit={editingConflict ? handleCancelManualEdit : undefined}
              />
            </div>

            {/* Right Column: Legible & Tabbed Compliance/Review Dashboard */}
            <div className="draft-review-panel" style={{
              background: 'var(--paper)',
              border: '2px solid var(--ink)',
              borderRadius: '12px',
              padding: '28px',
              boxShadow: '0 4px 0 var(--ink)',
              minHeight: '550px',
              display: 'flex',
              flexDirection: 'column'
            }}>
              {/* Tab Selection Header — nowrap + horizontal scroll so
                  all five tabs stay on one line instead of wrapping. */}
              <div className="draft-tabs-row">
                {REVIEW_TABS.map(tab => {
                  const isActive = activeReviewTab === tab.id;
                  const Icon = tab.Icon;
                  return (
                    <button
                      key={tab.id}
                      onClick={() => setActiveReviewTab(tab.id)}
                      className={`draft-tab-btn${isActive ? ' is-active' : ''}`}
                    >
                      <Icon /> {t(tab.labelKey)}
                      {tab.id === "conflicts" && allConflicts.length > 0 && (
                        <span className="draft-tab-badge">
                          {allConflicts.length}
                        </span>
                      )}
                    </button>

                  );
                })}
              </div>

              {/* Active Tab Content Section */}
              <div style={{ flex: 1 }}>
                {activeReviewTab === "compliance" && (
                  <ComplianceCard
                    report={analysisReport}
                    loading={analysisLoading}
                    hasGenerated={Boolean(draftResult)}
                  />
                )}
                {activeReviewTab === "conflicts" && (
                  <ConflictCard
                    conflicts={allConflicts}
                    loading={analysisLoading}
                    hasGenerated={Boolean(draftResult)}
                    draftText={draftResult?.body_text}
                    metadata={{
                      title: draftResult?.title,
                      department: draftResult?.department || department,
                      language,
                      grId: draftResult?.draft_id,
                    }}
                    templateIssues={analysisReport?.template_issues}
                    references={analysisReport?.references}
                    summary={analysisReport?.summary}
                    onResolveAll={handleResolveAllConflicts}
                    resolvingAll={resolvingBatch}
                    resolveProgress={batchProgress}
                    resolvedInfo={resolvedInfo}
                    onResolveSelected={handleResolveSelected}
                    resolvingSelected={resolvingBatch}
                    resolveSelectedProgress={batchProgress}
                    onIgnoreSelected={handleIgnoreSelected}
                    ignoringSelected={ignoringSelected}
                    onManualEditSelected={handleManualEditSelected}
                  />
                )}
                {activeReviewTab === "references" && (
                  <ReferencesCard
                    references={analysisReport?.references || draftResult?.references}
                    loading={analysisLoading}
                    hasGenerated={Boolean(draftResult)}
                  />
                )}
                {activeReviewTab === "terminology" && (
                  <TerminologyCard
                    terms={analysisReport?.terms}
                    loading={analysisLoading}
                    hasGenerated={Boolean(draftResult)}
                  />
                )}
                {activeReviewTab === "suggestions" && (
                  <SuggestionsCard
                    suggestions={analysisReport?.suggestions}
                    hasGenerated={Boolean(draftResult)}
                  />
                )}
              </div>
            </div>

          </div>
        </div>
      </div>
    </main>
  );
}
