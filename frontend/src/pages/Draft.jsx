import { useState, useEffect } from "react";
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
  const [currentStage, setCurrentStage] = useState(0);
  const [draftResult, setDraftResult] = useState(null);
  const [analysisReport, setAnalysisReport] = useState(null);
  const [error, setError] = useState("");
  const [activeReviewTab, setActiveReviewTab] = useState("compliance");

  const handleGenerate = async () => {
    if (!prompt.trim()) return;
    setLoading(true);
    setError("");
    setDraftResult(null);
    setAnalysisReport(null);
    setCurrentStage(1);

    try {
      // Step 1: LLM Draft Generation
      const res = await api.copilotDraft(prompt, language.toLowerCase(), department);
      setDraftResult(res);
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

  const handleReset = () => {
    setPrompt("");
    setDepartment("Higher_and_Technical_Education_Department");
    setDraftResult(null);
    setAnalysisReport(null);
    setCurrentStage(0);
    setError("");
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
                onRegenerate={handleGenerate}
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
                  { id: "cross_conflicts", label: "⚠️ Cross-Dept Conflicts" },
                  { id: "own_conflicts", label: "🏢 Own Dept Conflicts" },
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
                    loading={analysisLoading}
                    hasGenerated={Boolean(draftResult)}
                  />
                )}
                {activeReviewTab === "cross_conflicts" && (
                  <ConflictCard
                    conflicts={crossDeptConflicts}
                    loading={analysisLoading}
                    hasGenerated={Boolean(draftResult)}
                    isOwnDept={false}
                  />
                )}
                {activeReviewTab === "own_conflicts" && (
                  <ConflictCard
                    conflicts={ownDeptConflicts}
                    loading={analysisLoading}
                    hasGenerated={Boolean(draftResult)}
                    isOwnDept={true}
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
