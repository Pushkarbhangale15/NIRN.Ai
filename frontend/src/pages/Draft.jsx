import { useState, useEffect, useCallback } from "react";
import { api } from "../api.js";
import { useLanguage } from "../LanguageContext.jsx";

import WorkflowStepper from "../components/drafting/WorkflowStepper.jsx";
import DraftInputCard from "../components/drafting/DraftInputCard.jsx";
import DraftViewer from "../components/drafting/DraftViewer.jsx";
import ComplianceCard from "../components/drafting/ComplianceCard.jsx";
import ConflictCard from "../components/drafting/ConflictCard.jsx";
import ReferencesCard from "../components/drafting/ReferencesCard.jsx";
import TerminologyCard from "../components/drafting/TerminologyCard.jsx";
import SuggestionsCard from "../components/drafting/SuggestionsCard.jsx";

export default function Draft() {
  const { t, siteLanguage } = useLanguage();
  const [prompt, setPrompt] = useState("");
  const [language, setLanguage] = useState(siteLanguage === 'mr' ? 'Marathi' : 'English');
  const [department, setDepartment] = useState("Higher_and_Technical_Education_Department");
  const [loading, setLoading] = useState(false);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [reAnalysisLoading, setReAnalysisLoading] = useState(false);
  const [currentStage, setCurrentStage] = useState(0);
  const [draftResult, setDraftResult] = useState(null);
  const [analysisReport, setAnalysisReport] = useState(null);
  const [error, setError] = useState("");
  const [activeReviewTab, setActiveReviewTab] = useState("compliance");

  // Track user edits to the GR body text
  const [editedBodyText, setEditedBodyText] = useState("");
  // Whether the user has made edits since the last analysis
  const [hasUnanalyzedEdits, setHasUnanalyzedEdits] = useState(false);

  const handleGenerate = async () => {
    if (!prompt.trim()) return;
    setLoading(true);
    setError("");
    setDraftResult(null);
    setAnalysisReport(null);
    setEditedBodyText("");
    setHasUnanalyzedEdits(false);
    setCurrentStage(1);

    try {
      // Step 1: LLM Draft Generation
      const res = await api.copilotDraft(prompt, language.toLowerCase(), department);
      setDraftResult(res);
      setEditedBodyText(res.body_text);
      setCurrentStage(2);

      // Step 2: AI Review & Conflict Analysis
      setAnalysisLoading(true);
      if (res && res.draft_id) {
        try {
          setCurrentStage(3);
          const report = await api.runFullAnalysis(res.draft_id);
          setCurrentStage(4);
          setAnalysisReport(report);
        } catch (err) {
          console.warn("Analysis call warning:", err);
        }
      }
      setCurrentStage(5);
    } catch (err) {
      setError(err.message || "Draft generation failed.");
      setCurrentStage(0);
    } finally {
      setLoading(false);
      setAnalysisLoading(false);
    }
  };

  // Called by DraftViewer whenever the user edits the textarea
  const handleTextChange = useCallback((newText) => {
    setEditedBodyText(newText);
    if (draftResult && newText !== draftResult.body_text) {
      setHasUnanalyzedEdits(true);
    } else {
      setHasUnanalyzedEdits(false);
    }
  }, [draftResult]);

  // Re-analyze using edited text: PATCH the draft first, then re-run analysis
  const handleReAnalyze = async () => {
    if (!draftResult?.draft_id || !editedBodyText.trim()) return;
    setReAnalysisLoading(true);
    setError("");
    setAnalysisReport(null);

    try {
      // 1. Push edited text to backend
      await api.patchDraft(draftResult.draft_id, editedBodyText);

      // 2. Re-run full analysis on the updated draft
      const report = await api.runFullAnalysis(draftResult.draft_id);
      setAnalysisReport(report);
      setHasUnanalyzedEdits(false);

      // 3. Update draftResult to reflect the new body text
      setDraftResult((prev) => prev ? { ...prev, body_text: editedBodyText } : prev);
    } catch (err) {
      setError(err.message || "Re-analysis failed.");
    } finally {
      setReAnalysisLoading(false);
    }
  };

  const handleReset = () => {
    setPrompt("");
    setDepartment("Higher_and_Technical_Education_Department");
    setDraftResult(null);
    setAnalysisReport(null);
    setCurrentStage(0);
    setError("");
    setEditedBodyText("");
    setHasUnanalyzedEdits(false);
  };

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
        <div className="eyebrow">AI drafting</div>
        <h1 className="page-title">Draft a GR</h1>
        <p className="page-sub">
          Your intelligent assistant for drafting, querying, and auditing
          Government Resolutions of Maharashtra.
        </p>
      </header>

      <div className="copilot-panel-area" style={{ marginTop: '20px' }}>
        <div style={{ width: '100%' }}>
          {/* 1. Workflow Stepper at the very top */}
          <WorkflowStepper currentStage={currentStage} isGenerating={loading} />

          {/* 2. Horizontal Parameter & Brief Header */}
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

          {/* Re-analyze banner — shown when user has made edits */}
          {hasUnanalyzedEdits && draftResult && (
            <div style={{
              background: '#fffbeb',
              border: '1px solid #f59e0b',
              borderRadius: '8px',
              padding: '12px 20px',
              marginBottom: '16px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '12px',
              flexWrap: 'wrap',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '18px' }}>✏️</span>
                <div>
                  <div style={{ fontWeight: '700', fontSize: '13px', color: '#92400e' }}>
                    You have unsaved edits
                  </div>
                  <div style={{ fontSize: '12px', color: '#b45309' }}>
                    Click "Re-Analyze Edits" to run template & conflict checks against your updated text.
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={handleReAnalyze}
                disabled={reAnalysisLoading}
                style={{
                  padding: '8px 20px',
                  fontSize: '13px',
                  fontWeight: '700',
                  background: reAnalysisLoading ? '#d1d5db' : '#f59e0b',
                  color: reAnalysisLoading ? '#6b7280' : '#fff',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: reAnalysisLoading ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  whiteSpace: 'nowrap',
                  boxShadow: reAnalysisLoading ? 'none' : '0 2px 4px rgba(245,158,11,0.3)',
                  transition: 'all 0.15s',
                }}
              >
                {reAnalysisLoading ? (
                  <><span className="spinner" style={{ width: '14px', height: '14px', borderWidth: '2px' }} /> Analyzing...</>
                ) : (
                  <>🔄 Re-Analyze Edits</>
                )}
              </button>
            </div>
          )}

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
                  marginBottom: '16px'
                }}>
                  ⚠️ {error}
                </div>
              )}
              <DraftViewer
                draft={draftResult}
                loading={loading}
                onTextChange={handleTextChange}
              />
            </div>

            {/* Right Column: Legible & Tabbed Compliance/Review Dashboard */}
            <div style={{
              background: 'var(--paper)',
              border: '2px solid var(--ink)',
              borderRadius: '12px',
              padding: '24px',
              boxShadow: '0 4px 0 var(--ink)',
              minHeight: '550px',
              display: 'flex',
              flexDirection: 'column'
            }}>
              {/* Tab Selection Header */}
              <div style={{
                display: 'flex',
                gap: '8px',
                borderBottom: '2px solid var(--ink)',
                paddingBottom: '12px',
                marginBottom: '20px',
                flexWrap: 'wrap'
              }}>
                {[
                  { id: "compliance", label: "📌 MOP Rules" },
                  { id: "conflicts", label: "⚠️ Policy Conflicts" },
                  { id: "references", label: "🔗 References" },
                  { id: "terminology", label: "🔤 Terminology" },
                  { id: "suggestions", label: "💡 Suggestions" }
                ].map(tab => {
                  const isActive = activeReviewTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      onClick={() => setActiveReviewTab(tab.id)}
                      style={{
                        background: isActive ? 'var(--blue)' : '#fff',
                        color: isActive ? '#fff' : 'var(--ink)',
                        border: '2px solid var(--ink)',
                        borderRadius: '6px',
                        padding: '8px 14px',
                        fontWeight: 'bold',
                        fontSize: '15px',
                        cursor: 'pointer',
                        boxShadow: isActive ? 'none' : '0 2px 0 var(--ink)',
                        transform: isActive ? 'translateY(2px)' : 'none',
                        transition: 'all 0.1s'
                      }}
                    >
                      {tab.label}
                    </button>
                  );
                })}
              </div>

              {/* Active Tab Content Section */}
              <div style={{ flex: 1 }}>
                {activeReviewTab === "compliance" && (
                  <ComplianceCard
                    report={analysisReport}
                    loading={analysisLoading || reAnalysisLoading}
                    hasGenerated={Boolean(draftResult)}
                  />
                )}
                {activeReviewTab === "conflicts" && (
                  <ConflictCard
                    conflicts={allConflicts}
                    loading={analysisLoading || reAnalysisLoading}
                    hasGenerated={Boolean(draftResult)}
                  />
                )}
                {activeReviewTab === "references" && (
                  <ReferencesCard
                    references={analysisReport?.references || draftResult?.references}
                    loading={analysisLoading || reAnalysisLoading}
                    hasGenerated={Boolean(draftResult)}
                  />
                )}
                {activeReviewTab === "terminology" && (
                  <TerminologyCard
                    terms={analysisReport?.terms}
                    loading={analysisLoading || reAnalysisLoading}
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
