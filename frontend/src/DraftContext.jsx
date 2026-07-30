import React, { createContext, useState, useContext, useEffect } from 'react';
import { api } from './api.js';

const DraftContext = createContext(null);

export function DraftProvider({ children }) {
  const [prompt, setPrompt] = useState(() => localStorage.getItem("nirn_draft_prompt") || "");
  const [language, setLanguage] = useState(() => localStorage.getItem("nirn_draft_lang") || "Marathi");
  const [department, setDepartment] = useState(() => localStorage.getItem("nirn_draft_dept") || "");
  const [loading, setLoading] = useState(false);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [currentStage, setCurrentStage] = useState(() => parseInt(localStorage.getItem("nirn_draft_stage") || "0", 10));
  const [draftResult, setDraftResult] = useState(() => {
    try { return JSON.parse(localStorage.getItem("nirn_draft_result") || "null"); } catch { return null; }
  });
  const [analysisReport, setAnalysisReport] = useState(() => {
    try { return JSON.parse(localStorage.getItem("nirn_draft_analysis") || "null"); } catch { return null; }
  });
  const [error, setError] = useState("");
  const [activeReviewTab, setActiveReviewTab] = useState("compliance");

  useEffect(() => {
    localStorage.setItem("nirn_draft_prompt", prompt);
    localStorage.setItem("nirn_draft_lang", language);
    localStorage.setItem("nirn_draft_dept", department);
    localStorage.setItem("nirn_draft_stage", currentStage.toString());
    if (draftResult) localStorage.setItem("nirn_draft_result", JSON.stringify(draftResult));
    else localStorage.removeItem("nirn_draft_result");
    if (analysisReport) localStorage.setItem("nirn_draft_analysis", JSON.stringify(analysisReport));
    else localStorage.removeItem("nirn_draft_analysis");
  }, [prompt, language, department, draftResult, analysisReport, currentStage]);

  const handleGenerate = async () => {
    if (!prompt.trim() || !department) return;
    setLoading(true);
    setError("");
    setDraftResult(null);
    setAnalysisReport(null);
    setCurrentStage(1);

    try {
      // 1. LLM draft generation -> Display GR text immediately
      const res = await api.copilotDraft(prompt, language.toLowerCase(), department);
      setDraftResult(res);
      setLoading(false);

      if (res && res.draft_id) {
        setAnalysisLoading(true);
        
        let currentReport = {
          draft_id: res.draft_id,
          summary: {
            template_error_count: 0,
            template_warning_count: 0,
            reference_count: 0,
            unresolved_reference_count: 0,
            conflict_count: 0,
            highest_conflict_confidence: 0.0,
            overall_status: "needs_review",
          },
          template_issues: [],
          references: [],
          conflicts: [],
          terms: [],
        };
        setAnalysisReport(currentReport);

        // STEP 1: Immediate Conflict Detection (First Priority)
        setCurrentStage(3);
        setActiveReviewTab("conflicts");
        try {
          const conflicts = await api.runConflictDetection(res.draft_id);
          const topConfidence = (conflicts || []).reduce((max, c) => Math.max(max, c.confidence || 0), 0);
          currentReport = {
            ...currentReport,
            conflicts: conflicts || [],
            summary: {
              ...currentReport.summary,
              conflict_count: (conflicts || []).length,
              highest_conflict_confidence: topConfidence,
              overall_status: (conflicts || []).length > 0 ? "blocked" : currentReport.summary.overall_status,
            },
          };
          setAnalysisReport(currentReport);
        } catch (err) {
          console.warn("Conflict detection warning:", err);
        }

        // STEP 2: MoP Rules / Template Compliance Check (Second Priority)
        setCurrentStage(2);
        try {
          const templateIssues = await api.runTemplateCheck(res.draft_id);
          const issues = templateIssues || [];
          const errors = issues.filter(i => (i.severity || "").toLowerCase() === "error").length;
          const warnings = issues.filter(i => (i.severity || "").toLowerCase() === "warning").length;
          currentReport = {
            ...currentReport,
            template_issues: issues,
            summary: {
              ...currentReport.summary,
              template_error_count: errors,
              template_warning_count: warnings,
              overall_status: (errors > 0 || currentReport.summary.conflict_count > 0) ? "blocked" : "needs_review",
            },
          };
          setAnalysisReport(currentReport);
        } catch (err) {
          console.warn("Template check warning:", err);
        }

        // STEP 3: Reference Tracking & Terminology (Third Priority)
        setCurrentStage(4);
        try {
          const [refs, terms] = await Promise.all([
            api.runReferenceTracking(res.draft_id).catch(() => []),
            api.runTerminology(res.draft_id).catch(() => []),
          ]);
          const referenceList = refs || [];
          const termList = terms || [];
          const unresolved = referenceList.filter(r => !r.found_in_corpus).length;

          const isClean = currentReport.summary.template_error_count === 0 &&
                          currentReport.summary.conflict_count === 0 &&
                          currentReport.summary.template_warning_count === 0 &&
                          unresolved === 0;

          currentReport = {
            ...currentReport,
            references: referenceList,
            terms: termList,
            summary: {
              ...currentReport.summary,
              reference_count: referenceList.length,
              unresolved_reference_count: unresolved,
              overall_status: (currentReport.summary.template_error_count > 0 || currentReport.summary.conflict_count > 0)
                ? "blocked"
                : (isClean ? "clean" : "needs_review"),
            },
          };
          setAnalysisReport(currentReport);
        } catch (err) {
          console.warn("References/Terminology warning:", err);
        } finally {
          setCurrentStage(5);
          setAnalysisLoading(false);
        }
      } else {
        setCurrentStage(5);
      }
    } catch (err) {
      setError(err.message || "Draft generation failed.");
      setCurrentStage(0);
      setLoading(false);
      setAnalysisLoading(false);
    }
  };

  const handleReset = () => {
    setPrompt("");
    setDepartment("");
    setDraftResult(null);
    setAnalysisReport(null);
    setCurrentStage(0);
    setError("");
    localStorage.removeItem("nirn_draft_prompt");
    localStorage.removeItem("nirn_draft_dept");
    localStorage.removeItem("nirn_draft_result");
    localStorage.removeItem("nirn_draft_analysis");
    localStorage.setItem("nirn_draft_stage", "0");
  };

  const handleSaveDraft = async (htmlContent, textContent) => {
    setDraftResult(prev => prev ? { ...prev, body_text: textContent } : prev);
    if (draftResult && draftResult.draft_id) {
      try {
        await api.updateDraft(draftResult.draft_id, textContent);
        const updatedTemplateIssues = await api.runTemplateCheck(draftResult.draft_id);
        setAnalysisReport(prev => prev ? { ...prev, template_issues: updatedTemplateIssues } : prev);
      } catch (err) {
        console.warn("Auto-save sync warning:", err);
      }
    }
  };

  const value = {
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
  };

  return (
    <DraftContext.Provider value={value}>
      {children}
    </DraftContext.Provider>
  );
}

export function useDraft() {
  const context = useContext(DraftContext);
  if (!context) {
    throw new Error('useDraft must be used within a DraftProvider');
  }
  return context;
}
