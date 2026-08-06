import React, { useState, useEffect } from "react";
import { api } from "../api.js";
import { useLanguage } from "../LanguageContext.jsx";
import ConflictCard from "../components/drafting/ConflictCard.jsx";

const IconAlert = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="currentColor" viewBox="0 0 24 24">
    <path d="M1 21h22L12 2 1 21Zm12-3h-2v-2h2Zm0-4h-2v-4h2Z" />
  </svg>
);

export default function UploadGR() {
  const { t, siteLanguage } = useLanguage();
  const isMr = siteLanguage === 'mr';

  const [bodyText, setBodyText] = useState("");
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisReport, setAnalysisReport] = useState(null);
  const [hasAnalyzed, setHasAnalyzed] = useState(false);
  const [error, setError] = useState("");
  const [uploadingPdf, setUploadingPdf] = useState(false);
  const [uploadWarning, setUploadWarning] = useState("");
  const [draftId, setDraftId] = useState(null);
  const [resolvingConflictId, setResolvingConflictId] = useState(null);
  const [resolvedInfo, setResolvedInfo] = useState({});

  // Scanned GR (OCR) upload — separate from the text-based PDF path above:
  // this one is async (background OCR job) rather than instant, so it gets
  // its own control and a poll-driven status instead of populating the
  // textarea synchronously.
  const [ocrUploading, setOcrUploading] = useState(false);
  const [ocrUploadId, setOcrUploadId] = useState(null);
  const [ocrStatus, setOcrStatus] = useState(null); // null | pending | processing | needs_review | complete | failed
  const [ocrError, setOcrError] = useState("");
  const [ocrBlockConfidences, setOcrBlockConfidences] = useState([]);

  // Source of truth for "is this conflict resolved": the persisted
  // resolution_status field on each conflict, not a client-only flag —
  // mirrors Draft.jsx so resolved state here also survives a page reload.
  useEffect(() => {
    const conflicts = analysisReport?.conflicts || [];
    const derived = {};
    for (const c of conflicts) {
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
  }, [analysisReport]);

  // Poll the OCR job while it's pending/processing. Stops itself once the
  // status is terminal (complete/needs_review/failed) or the upload is
  // cleared.
  useEffect(() => {
    if (!ocrUploadId || (ocrStatus !== "pending" && ocrStatus !== "processing")) return;

    const interval = setInterval(async () => {
      try {
        const result = await api.getGrUploadStatus(ocrUploadId);
        setOcrStatus(result.status);
        setOcrBlockConfidences(result.block_confidences || []);

        if (result.status === "complete" || result.status === "needs_review") {
          clearInterval(interval);
          const draft = await api.getDraftDetail(result.generated_draft_id);
          setBodyText(draft.content);
          setDraftId(result.generated_draft_id);
          setHasAnalyzed(true);
          const report = await api.runFullAnalysis(result.generated_draft_id);
          setAnalysisReport(report);
        } else if (result.status === "failed") {
          clearInterval(interval);
          setOcrError(result.error_message || "OCR processing failed.");
        }
      } catch (err) {
        console.warn("OCR status poll failed:", err);
      }
    }, 2500);

    return () => clearInterval(interval);
  }, [ocrUploadId, ocrStatus]);

  const handleScannedUpload = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;

    setError("");
    setOcrError("");
    setUploadWarning("");
    setOcrBlockConfidences([]);
    setOcrUploading(true);
    try {
      const result = await api.uploadScannedGr(file);
      setOcrUploadId(result.upload_id);
      setOcrStatus(result.status);
      if (result.status === "complete" || result.status === "needs_review") {
        // Dedup hit on an already-fully-processed upload — same terminal
        // handling as the poll loop above, just reached immediately.
        const draft = await api.getDraftDetail(result.generated_draft_id);
        setBodyText(draft.content);
        setDraftId(result.generated_draft_id);
        setHasAnalyzed(true);
        setOcrBlockConfidences(result.block_confidences || []);
        const report = await api.runFullAnalysis(result.generated_draft_id);
        setAnalysisReport(report);
      } else if (result.status === "failed") {
        setOcrError(result.error_message || "OCR processing failed.");
      }
    } catch (err) {
      setOcrError(err.message || "Failed to upload scanned document.");
    } finally {
      setOcrUploading(false);
    }
  };

  // Unsaved changes protection
  const isDirty = bodyText.trim().length > 0 && !hasAnalyzed;
  useEffect(() => {
    const handleBeforeUnload = (e) => {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = t('upload_unsaved_warning');
        return t('upload_unsaved_warning');
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [isDirty, t]);

  const handleClear = () => {
    setBodyText("");
    setAnalysisReport(null);
    setHasAnalyzed(false);
    setError("");
    setUploadWarning("");
    setDraftId(null);
    setOcrUploadId(null);
    setOcrStatus(null);
    setOcrError("");
    setOcrBlockConfidences([]);
  };

  const handleRunAnalysis = async (e) => {
    e.preventDefault();
    if (!bodyText.trim()) {
      setError("Please enter or paste the GR text before running analysis.");
      return;
    }

    setError("");
    setAnalysisLoading(true);
    setAnalysisReport(null);
    setHasAnalyzed(true);

    try {
      const firstLine = bodyText.trim().split("\n")[0] || "";
      const draftTitle = firstLine.length > 5 ? firstLine.slice(0, 60) : "Submitted GR Resolution";

      const draft = await api.createDraft({
        title: draftTitle,
        department: "Higher_and_Technical_Education_Department",
        body_text: bodyText,
        language: siteLanguage === "mr" ? "mr" : "en",
      });
      setDraftId(draft.id);

      const report = await api.runFullAnalysis(draft.id);
      setAnalysisReport(report);
    } catch (err) {
      setError(err.message || "Conflict analysis failed.");
    } finally {
      setAnalysisLoading(false);
    }
  };

  // Text-based PDFs only (scope-limited): server extracts embedded text via
  // pypdf. If extraction comes back empty/near-empty, that's a strong
  // signal it's a scanned image with no text layer — surfaced as a clear
  // warning rather than silently feeding empty text into analysis.
  const handlePdfUpload = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-selecting the same file later
    if (!file) return;

    setUploadWarning("");
    setError("");
    setUploadingPdf(true);
    try {
      const result = await api.uploadGrFile(file);
      const text = result.text || "";
      const wordCount = result.word_count ?? (text.trim() ? text.trim().split(/\s+/).length : 0);
      if (!text.trim() || wordCount < 20) {
        setUploadWarning(t('upload_pdf_scanned_warning'));
      } else {
        setBodyText(text);
      }
    } catch (err) {
      const msg = err.message || "";
      if (/no readable text/i.test(msg)) {
        setUploadWarning(t('upload_pdf_scanned_warning'));
      } else {
        setError(msg || "Failed to process the uploaded PDF.");
      }
    } finally {
      setUploadingPdf(false);
    }
  };

  const handleResolveOneConflict = async (conflict) => {
    if (!draftId || !conflict.conflict_id || resolvingConflictId) return;
    setResolvingConflictId(conflict.conflict_id);

    // "reword" alone often can't fix a substantive funding/scope conflict —
    // fall back to "add_carve_out" before giving up, same as the bulk-resolve
    // flow on the Draft page.
    const STRATEGIES = ["reword", "add_carve_out"];
    try {
      for (const strategy of STRATEGIES) {
        const result = await api.resolveConflict(conflict.conflict_id, strategy);
        if (result.cleared) {
          await api.acceptConflictResolution(conflict.conflict_id, result.revised_clause);
          break;
        }
      }
    } catch (err) {
      console.warn("Resolve conflict failed:", conflict.conflict_id, err);
    }

    try {
      const updatedDraft = await api.getDraftDetail(draftId);
      setBodyText(updatedDraft.content);
      const report = await api.runFullAnalysis(draftId);
      setAnalysisReport(report);
    } catch (err) {
      console.warn("Post-resolve refresh warning:", err);
    } finally {
      setResolvingConflictId(null);
    }
  };

  const wordCount = bodyText.trim() ? bodyText.trim().split(/\s+/).length : 0;
  const charCount = bodyText.length;

  return (
    <main className="container" style={{ paddingBottom: '60px' }}>
      <header className="page-head">
        <div className="eyebrow">{t('upload_eyebrow')}</div>
        <h1 className="page-title">{t('upload_title')}</h1>
      </header>

      {error && (
        <div style={{
          background: '#fee2e2',
          border: '2px solid var(--red)',
          color: 'var(--red)',
          padding: '14px 18px',
          borderRadius: '8px',
          fontWeight: 'bold',
          marginBottom: '20px',
          display: 'flex',
          alignItems: 'center',
          gap: '10px'
        }}>
          <IconAlert /> {error}
        </div>
      )}

      {/* Side-by-Side 2-Column Half Screen Layout */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(460px, 1fr))',
        gap: '24px',
        marginTop: '20px',
        alignItems: 'start'
      }}>

        {/* Left Half: Paste GR Text Module */}
        <form onSubmit={handleRunAnalysis} style={{
          background: 'var(--paper)',
          border: '2px solid var(--ink)',
          borderRadius: '12px',
          padding: '24px',
          boxShadow: '0 4px 0 var(--ink)',
          display: 'flex',
          flexDirection: 'column',
          minHeight: '520px'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '10px' }}>
            <h2 style={{ fontSize: isMr ? '20px' : '18px', fontWeight: 'bold', color: 'var(--ink)', margin: 0 }}>
              {isMr ? 'तुमचा जीआर मजकूर येथे पेस्ट करा' : 'Paste your GR text here'}
            </h2>
            {bodyText && (
              <button
                type="button"
                onClick={handleClear}
                style={{
                  background: '#f3f4f6',
                  border: '1px solid var(--ink)',
                  borderRadius: '6px',
                  padding: '6px 12px',
                  fontSize: '13px',
                  fontWeight: 'bold',
                  cursor: 'pointer'
                }}
              >
                {t('upload_clear_btn')}
              </button>
            )}
          </div>

          {/* Upload OR paste — both input methods coexist. Uploading just
              populates the same textarea below, so the rest of the flow
              (edit, then Analyze) is unchanged. */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            flexWrap: 'wrap',
            marginBottom: '16px',
            padding: '12px 14px',
            background: '#f9fafb',
            border: '1.5px dashed #9ca3af',
            borderRadius: '8px'
          }}>
            <label
              htmlFor="upload-pdf-input"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '9px 14px',
                fontSize: '13.5px',
                fontWeight: 'bold',
                background: uploadingPdf ? '#e5e7eb' : '#fff',
                color: 'var(--ink)',
                border: '1.5px solid var(--ink)',
                borderRadius: '6px',
                cursor: uploadingPdf ? 'wait' : 'pointer',
                opacity: uploadingPdf ? 0.7 : 1
              }}
            >
              {uploadingPdf ? <span className="spinner-small" /> : null}
              {uploadingPdf ? t('upload_pdf_uploading') : t('upload_pdf_label')}
            </label>
            <input
              id="upload-pdf-input"
              type="file"
              accept=".pdf"
              onChange={handlePdfUpload}
              disabled={uploadingPdf}
              style={{ display: 'none' }}
            />
            <span style={{ fontSize: '12.5px', color: '#6b7280' }}>
              {isMr ? 'फक्त निवडण्यायोग्य मजकूर असलेल्या पीडीएफसाठी' : 'Text-based PDFs only (no scanned/image PDFs)'}
            </span>
          </div>

          {/* Scanned GR (OCR) — a separate, async path: an image or a
              scanned PDF with no text layer. Distinct control from the
              text-PDF one above since this one runs a background OCR job
              (30s-3min) instead of returning instantly. */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            flexWrap: 'wrap',
            marginBottom: '16px',
            padding: '12px 14px',
            background: '#f0f9ff',
            border: '1.5px dashed #7dd3fc',
            borderRadius: '8px'
          }}>
            <label
              htmlFor="upload-scanned-input"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '9px 14px',
                fontSize: '13.5px',
                fontWeight: 'bold',
                background: ocrUploading ? '#e5e7eb' : '#fff',
                color: 'var(--ink)',
                border: '1.5px solid var(--ink)',
                borderRadius: '6px',
                cursor: ocrUploading ? 'wait' : 'pointer',
                opacity: ocrUploading ? 0.7 : 1
              }}
            >
              {ocrUploading ? <span className="spinner-small" /> : null}
              {ocrUploading ? t('upload_ocr_uploading') : t('upload_ocr_label')}
            </label>
            <input
              id="upload-scanned-input"
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.tiff,.tif"
              onChange={handleScannedUpload}
              disabled={ocrUploading}
              style={{ display: 'none' }}
            />
            <span style={{ fontSize: '12.5px', color: '#6b7280' }}>
              {isMr ? 'स्कॅन केलेल्या प्रतिमा/पीडीएफसाठी (OCR)' : 'For scanned images/PDFs (OCR)'}
            </span>
          </div>

          {ocrUploadId && (ocrStatus === "pending" || ocrStatus === "processing") && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              background: '#eff6ff',
              border: '1.5px solid var(--blue)',
              color: '#1e40af',
              padding: '10px 14px',
              borderRadius: '8px',
              fontSize: '13.5px',
              fontWeight: 600,
              marginBottom: '16px'
            }}>
              <span className="spinner-small" />
              {ocrStatus === "pending" ? t('upload_ocr_status_pending') : t('upload_ocr_status_processing')}
            </div>
          )}

          {ocrError && (
            <div style={{
              background: '#fee2e2',
              border: '1.5px solid var(--red)',
              color: 'var(--red)',
              padding: '10px 14px',
              borderRadius: '8px',
              fontSize: '13.5px',
              fontWeight: 600,
              marginBottom: '16px'
            }}>
              ⚠️ {ocrError}
            </div>
          )}

          {ocrBlockConfidences.filter(b => b.needs_review).length > 0 && (
            <div style={{
              background: '#fff7ed',
              border: '1.5px solid var(--yellow)',
              color: '#92400e',
              padding: '12px 14px',
              borderRadius: '8px',
              fontSize: '13px',
              marginBottom: '16px'
            }}>
              <div style={{ fontWeight: 700, marginBottom: '6px' }}>
                ⚠️ {t('upload_ocr_low_confidence_title')} ({ocrBlockConfidences.filter(b => b.needs_review).length})
              </div>
              <ul style={{ margin: 0, paddingLeft: '18px', lineHeight: '1.6' }}>
                {ocrBlockConfidences.filter(b => b.needs_review).slice(0, 8).map((b, i) => (
                  <li key={i}>
                    "{b.text_preview}{b.text_preview?.length >= 80 ? '…' : ''}" — {Math.round(b.confidence)}%
                  </li>
                ))}
              </ul>
            </div>
          )}

          {uploadWarning && (
            <div style={{
              background: '#fff7ed',
              border: '1.5px solid var(--yellow)',
              color: '#92400e',
              padding: '10px 14px',
              borderRadius: '8px',
              fontSize: '13.5px',
              fontWeight: 600,
              marginBottom: '16px'
            }}>
              ⚠️ {uploadWarning}
            </div>
          )}

          <div className="field" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
              <label htmlFor="upload-body" style={{ fontWeight: 'bold', fontSize: '13.5px' }}>{t('upload_text_label')}</label>
              <span style={{ fontSize: '12.5px', color: '#6b7280', fontWeight: 'bold' }}>
                {wordCount.toLocaleString()} words | {charCount.toLocaleString()} characters
              </span>
            </div>
            <textarea
              id="upload-body"
              value={bodyText}
              onChange={(e) => setBodyText(e.target.value)}
              placeholder="Paste resolution text here to analyze policy conflicts..."
              rows={16}
              style={{
                width: '100%',
                flex: 1,
                padding: '14px',
                borderRadius: '8px',
                border: '2px solid var(--ink)',
                fontFamily: 'monospace',
                fontSize: '13.5px',
                lineHeight: '1.5',
                background: '#fff',
                resize: 'vertical',
                minHeight: '340px'
              }}
              required
            />
          </div>

          <div style={{ marginTop: '20px' }}>
            <button
              type="submit"
              disabled={analysisLoading || !bodyText.trim()}
              style={{
                width: '100%',
                padding: '14px 20px',
                minHeight: '48px',
                fontSize: isMr ? '17px' : '16px',
                fontWeight: 'bold',
                background: 'var(--red)',
                color: '#fff',
                border: '2px solid var(--ink)',
                borderRadius: '8px',
                boxShadow: '0 4px 0 var(--ink)',
                cursor: (analysisLoading || !bodyText.trim()) ? 'not-allowed' : 'pointer',
                opacity: (analysisLoading || !bodyText.trim()) ? 0.7 : 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '10px'
              }}
            >
              {analysisLoading ? (
                <>
                  <span className="spinner" /> {t('upload_btn_analyzing')}
                </>
              ) : (
                t('upload_btn_analyze')
              )}
            </button>
          </div>
        </form>

        {/* Right Half: Policy Conflicts Dashboard Module */}
        <div style={{
          background: 'var(--paper)',
          border: '2px solid var(--ink)',
          borderRadius: '12px',
          padding: '24px',
          boxShadow: '0 4px 0 var(--ink)',
          minHeight: '520px'
        }}>
          <h2 style={{ fontSize: isMr ? '20px' : '18px', fontWeight: 'bold', marginBottom: '16px', color: 'var(--ink)' }}>
            ⚠️ {isMr ? 'धोरण विरोध विश्लेषण' : 'Policy Conflicts'}
          </h2>

          <ConflictCard
            conflicts={analysisReport?.conflicts || []}
            loading={analysisLoading}
            hasGenerated={hasAnalyzed}
            draftText={bodyText}
            metadata={{
              title: "Submitted GR Resolution",
              department: "Higher_and_Technical_Education_Department",
              language: siteLanguage
            }}
            templateIssues={analysisReport?.template_issues || []}
            references={analysisReport?.references || []}
            summary={analysisReport?.summary || null}
            onResolveOne={handleResolveOneConflict}
            resolvingConflictId={resolvingConflictId}
            resolvedInfo={resolvedInfo}
          />
        </div>

      </div>
    </main>
  );
}
