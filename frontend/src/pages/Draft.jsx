import { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import { api } from "../api.js";
import { useLanguage } from "../LanguageContext.jsx";
import { useDraft } from "../DraftContext.jsx";

import WorkflowStepper from "../components/drafting/WorkflowStepper.jsx";
import DraftInputCard from "../components/drafting/DraftInputCard.jsx";
import UploadGrCard from "../components/drafting/UploadGrCard.jsx";
import DraftViewer from "../components/drafting/DraftViewer.jsx";
import StatusVerb from "../components/StatusVerb.jsx";
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
  const { t, siteLanguage } = useLanguage();
  const location = useLocation();
  const {
    prompt, setPrompt,
    language, setLanguage,
    department, setDepartment,
    loading, setLoading,
    analysisLoading, setAnalysisLoading,
    currentStage, setCurrentStage,
    draftResult, setDraftResult,
    analysisReport, setAnalysisReport,
    error, setError,
    activeReviewTab, setActiveReviewTab,
    handleGenerate,
    handleReset,
    handleSaveDraft
  } = useDraft();
  
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [scrollToClauseIndex, setScrollToClauseIndex] = useState(null);
  const [activeReviewTab, setActiveReviewTab] = useState("compliance");
  // The persisted, CFL-coded conflicts for this draft (draft_conflicts
  // rows) — what the Policy Conflicts tab now shows, so every conflict
  // an officer sees there is the same addressable record History and
  // the lookup box use. Independent of analysisReport.conflicts (the
  // ephemeral live-recomputed list still used for the overall
  // clean/needs_review/blocked status) and fetched separately since the
  // conflicts are already in the database the moment the draft exists —
  // no need to wait on the slower live-analysis LLM call.
  const [draftConflicts, setDraftConflicts] = useState([]);
  const [draftConflictsLoading, setDraftConflictsLoading] = useState(false);

  const [uploadLoading, setUploadLoading] = useState(false);
  const [lowConfidenceWarning, setLowConfidenceWarning] = useState(false);

  const loadDraftConflicts = async (draftId) => {
    setDraftConflictsLoading(true);
    try {
      setDraftConflicts(await api.getDraftConflicts(draftId));
    } catch (err) {
      console.warn("Conflict registry fetch warning:", err);
    } finally {
      setDraftConflictsLoading(false);
    }
  };

  const runAnalysisFor = async (draftId) => {
    setAnalysisLoading(true);
    try {
      setCurrentStage(3);
      const report = await api.runFullAnalysis(draftId);
      setCurrentStage(4);
      setAnalysisReport(report);
    } catch (err) {
      console.warn("Analysis call warning:", err);
    } finally {
      setAnalysisLoading(false);
    }
  };

  // Arriving from History's "Open" action, or a conflict lookup's "Open
  // draft" link: load that draft into the editor and re-run analysis,
  // same as a freshly generated one. scrollToClauseIndex (conflict
  // lookups only) is best-effort — see DraftViewer, which scrolls to
  // the Nth <li> of an uploaded/converted draft's rendered HTML and
  // silently no-ops for plain-text LLM-generated drafts or a null index,
  // rather than guessing a location it can't back up.
  useEffect(() => {
    const openDraftId = location.state?.openDraftId;
    if (!openDraftId) return;

    setLoading(true);
    setError("");
    setLowConfidenceWarning(false);
    setScrollToClauseIndex(location.state?.scrollToClauseIndex ?? null);
    api.getDraft(openDraftId)
      .then((detail) => {
        setDraftResult({
          draft_id: detail.generated_draft_id,
          title: detail.title,
          department: detail.department,
          body_text: detail.content,
          references: [],
        });
        // Only reachable via History's "Open", which only lists saved
        // drafts (see is_saved) — so this is always already saved.
        setSaved(true);
        setDepartment(detail.department);
        setLanguage(detail.language === "mr" ? "Marathi" : "English");
        setCurrentStage(2);
        loadDraftConflicts(detail.generated_draft_id);
        return runAnalysisFor(detail.generated_draft_id);
      })
      .catch((err) => setError(err.message))
      .finally(() => {
        setLoading(false);
        setCurrentStage(5);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state?.openDraftId]);

  const handleUpload = async (file) => {
    setUploadLoading(true);
    setError("");
    setDraftResult(null);
    setAnalysisReport(null);
    setLowConfidenceWarning(false);
    setSaved(false);
    setScrollToClauseIndex(null);
    setDraftConflicts([]);
    setCurrentStage(1);

    try {
      const res = await api.uploadDraft({
        file, department, language: language.toLowerCase() === "marathi" ? "mr" : "en",
      });
      setDraftResult({
        draft_id: res.generated_draft_id,
        title: res.title,
        department: res.department,
        body_text: res.content,
        references: [],
      });
      setLowConfidenceWarning(Boolean(res.low_confidence));
      setCurrentStage(2);
      loadDraftConflicts(res.generated_draft_id);
      await runAnalysisFor(res.generated_draft_id);
      setCurrentStage(5);
    } catch (err) {
      setError(err.message || "Upload failed.");
      setCurrentStage(0);
      throw err;
    } finally {
      setUploadLoading(false);
    }
  };

  const handleGenerate = async () => {
    if (!prompt.trim() || !department) return;
    setLoading(true);
    setError("");
    setDraftResult(null);
    setAnalysisReport(null);
    setLowConfidenceWarning(false);
    setSaved(false);
    setScrollToClauseIndex(null);
    setDraftConflicts([]);
    setCurrentStage(1);

    try {
      // Step 1: LLM Draft Generation
      const res = await api.copilotDraft(prompt, language.toLowerCase(), department);
      setDraftResult(res);
      setCurrentStage(2);

      // Step 2: AI Review & Conflict Analysis
      if (res && res.draft_id) {
        loadDraftConflicts(res.draft_id);
        await runAnalysisFor(res.draft_id);
      }
      setCurrentStage(5);
    } catch (err) {
      setError(err.message || "Draft generation failed.");
      setCurrentStage(0);
    } finally {
      setLoading(false);
    }
  };

  // Generating/uploading only persists a scratch row (conflict detection
  // needs one to attach to) — it stays out of History until the officer
  // confirms it's worth keeping. See is_saved on GeneratedDraft.
  const handleSave = async () => {
    if (!draftResult?.draft_id || saved) return;
    setSaving(true);
    setError("");
    try {
      await api.saveDraft(draftResult.draft_id);
      setSaved(true);
    } catch (err) {
      setError(err.message || "Failed to save draft.");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setPrompt("");
    setDepartment("");
    setDraftResult(null);
    setAnalysisReport(null);
    setCurrentStage(0);
    setError("");
    setLowConfidenceWarning(false);
    setSaved(false);
    setScrollToClauseIndex(null);
    setDraftConflicts([]);
  };
>>>>>>> origin/kumar-db

  // Filter conflicts into cross-departmental vs own-department
  const allConflicts = analysisReport?.conflicts || [];
  const normDraft = (draftResult?.department || department || "").toLowerCase().replace(/_/g, " ").trim();
  
  const ownDeptConflicts = allConflicts.filter(c => {
    const normExist = (c.existing_department || "").toLowerCase().replace(/_/g, " ").trim();
    return normDraft && normExist && normDraft === normExist;
  });
  
  const crossDeptConflicts = allConflicts.filter(c => {
    const normExist = (c.existing_department || "").toLowerCase().replace(/_/g, " ").trim();
    return normDraft && normExist && normDraft !== normExist;
  });

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

          {/* 1b. Upload an existing GR instead of generating one */}
          <UploadGrCard
            department={department}
            setDepartment={setDepartment}
            language={language}
            setLanguage={setLanguage}
            onUpload={handleUpload}
            loading={uploadLoading}
          />
          {uploadLoading && (
            <p style={{ margin: '-16px 0 24px', fontSize: 14, color: 'var(--ink-soft)' }}>
              <StatusVerb stage="extracting" />
            </p>
          )}

          {/* 2. Workflow Stepper directly under the Generate Draft block */}
          <WorkflowStepper currentStage={currentStage} isGenerating={loading || analysisLoading} />

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
              {lowConfidenceWarning && (
                <div style={{
                  background: '#fff7e6',
                  border: '2px solid #f2b01d',
                  color: '#92400e',
                  padding: '12px 16px',
                  borderRadius: '8px',
                  fontWeight: 600,
                  marginBottom: '16px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}>
                  <IconAlert /> {t('upload_low_confidence_warning')}
                </div>
              )}
              <DraftViewer
                draft={draftResult}
                loading={loading}
                onSaveDraft={handleSaveDraft}
              />
            </div>

            {/* Right Column: Legible & Tabbed Compliance/Review Dashboard */}
            <div style={{
              background: 'var(--paper)',
              border: '2px solid var(--ink)',
              borderRadius: '12px',
              padding: '28px',
              boxShadow: '0 4px 0 var(--ink)',
              minHeight: '550px',
              display: 'flex',
              flexDirection: 'column'
            }}>
              {/* Tab Selection Header */}
              <div className="draft-review-tabs">
                {REVIEW_TABS.map(tab => {
                  const isActive = activeReviewTab === tab.id;
                  const Icon = tab.Icon;
                  return (
                    <button
                      key={tab.id}
                      onClick={() => setActiveReviewTab(tab.id)}
                      className={`draft-review-tab${isActive ? ' draft-review-tab--active' : ''}`}
                    >
                      <Icon /> {t(tab.labelKey)}
                      {tab.id === "conflicts" && allConflicts.length > 0 && (
                        <span style={{
                          background: '#dc2626',
                          color: '#ffffff',
                          fontSize: '12px',
                          fontWeight: 'bold',
                          borderRadius: '12px',
                          padding: '2px 8px',
                          marginLeft: '4px',
                          border: '1px solid var(--ink)',
                          boxShadow: '0 1px 0 var(--ink)'
                        }}>
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
                    conflicts={draftConflicts}
                    loading={draftConflictsLoading}
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
