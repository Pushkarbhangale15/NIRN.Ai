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
      const res = await api.copilotDraft(prompt, language.toLowerCase(), department);
      setDraftResult(res);
      setCurrentStage(2);

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
