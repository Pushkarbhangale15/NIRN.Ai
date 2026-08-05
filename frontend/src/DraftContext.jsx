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
    if (!draftResult || !draftResult.draft_id) return;
    // Snapshots the previous content into draft_versions server-side
    // before overwriting (Task 5c) — wait for the response rather than
    // updating optimistically, so a rejected save never looks saved.
    await api.saveDraftContent(draftResult.draft_id, htmlContent, textContent);
    setDraftResult(prev => prev ? { ...prev, body_text: htmlContent } : prev);
    try {
      const updatedTemplateIssues = await api.runTemplateCheck(draftResult.draft_id);
      setAnalysisReport(prev => prev ? { ...prev, template_issues: updatedTemplateIssues } : prev);
    } catch (err) {
      console.warn("Post-save template re-check warning:", err);
    }
  };

  const handleAnalyzeCustomGR = async (bodyText, customDepartment = null, customTitle = null, customLang = null) => {
    if (!bodyText || !bodyText.trim()) return;
    setLoading(true);
    setAnalysisLoading(true);
    setError("");
    setDraftResult(null);
    setAnalysisReport(null);
    setCurrentStage(1);
    setActiveReviewTab("conflicts");

    const deptToUse = customDepartment || department || "Higher_and_Technical_Education_Department";
    const langToUse = customLang || language || "English";

    try {
      const firstLine = bodyText.trim().split("\n")[0] || "";
      const draftTitle = customTitle || (firstLine.length > 5 ? firstLine.slice(0, 60) : "Uploaded Government Resolution");

      // 1. Create draft via API
      const draft = await api.createDraft({
        title: draftTitle,
        department: deptToUse,
        body_text: bodyText,
        language: langToUse.toLowerCase() === "marathi" || langToUse.toLowerCase() === "mr" ? "mr" : "en",
      });

      const fullDraftObj = {
        draft_id: draft.id,
        title: draft.title,
        department: draft.department,
        body_text: draft.body_text,
        language: draft.language,
        created_at: draft.created_at
      };

      setDraftResult(fullDraftObj);
      setCurrentStage(2);

      // 2. Run full policy analysis
      setCurrentStage(3);
      const report = await api.runFullAnalysis(draft.id);
      setCurrentStage(4);
      setAnalysisReport(report);
      setCurrentStage(5);
      return draft.id;
    } catch (err) {
      setError(err.message || "Policy conflict analysis failed.");
      setCurrentStage(0);
      throw err;
    } finally {
      setLoading(false);
      setAnalysisLoading(false);
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
    handleSaveDraft,
    handleAnalyzeCustomGR
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
