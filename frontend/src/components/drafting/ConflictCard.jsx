import React, { useState } from 'react';
import { useLanguage } from '../../LanguageContext.jsx';
import { generateConflictPDF } from '../../utils/pdfExport.js';

const IconWarningTriangle = () => (


  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
    <path d="M1 21h22L12 2 1 21Zm12-3h-2v-2h2Zm0-4h-2v-4h2Z" />
  </svg>
);
const IconDownload = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 24 24">
    <path d="M5 20h14v-2H5v2zM19 9h-4V3H9v6H5l7 7 7-7z" />
  </svg>
);
const IconCheckCircle = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 24 24">
    <path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm-1.2 14.6-4.4-4.4 1.4-1.4 3 3 6-6 1.4 1.4-7.4 7.4Z" />
  </svg>
);

export default function ConflictCard({
  conflicts = [],
  loading,
  hasGenerated,
  draftText = '',
  metadata = {},
  templateIssues = [],
  references = [],
  summary = null,
  onResolveAll,
  resolvingAll = false,
  resolveProgress = null,
  resolvedInfo = {},
  onResolveOne,
  resolvingConflictId = null,
}) {
  const { t, siteLanguage } = useLanguage();
  const isMr = siteLanguage === 'mr';
  const [isOpen, setIsOpen] = useState(true);
  const [generatingFull, setGeneratingFull] = useState(false);
  const [generatingIdx, setGeneratingIdx] = useState(null);

  const resolvableConflicts = conflicts.filter(c => c.conflict_id);
  const allResolved = resolvableConflicts.length > 0 &&
    resolvableConflicts.every(c => resolvedInfo[c.conflict_id]);

  const handleDownloadFullReport = async () => {
    if (generatingFull) return;
    setGeneratingFull(true);
    try {
      await generateConflictPDF(draftText, conflicts, {
        ...metadata,
        reportType: 'full',
        templateIssues,
        references,
        summary,
      });
    } catch (err) {
      console.error('Full conflict report PDF generation failed:', err);
    } finally {
      setGeneratingFull(false);
    }
  };

  const handleDownloadOneReport = async (conflict, idx) => {
    if (generatingIdx !== null) return;
    setGeneratingIdx(idx);
    try {
      await generateConflictPDF(draftText, conflict, {
        ...metadata,
        reportType: 'individual',
      });
    } catch (err) {
      console.error('Conflict report PDF generation failed:', err);
    } finally {
      setGeneratingIdx(null);
    }
  };

  if (!hasGenerated) {
    return (
      <div style={{
        background: 'var(--paper)',
        border: '2px solid #d1d5db',
        borderRadius: '12px',
        padding: '16px 20px',
        opacity: 0.6,
        marginBottom: '16px'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', fontWeight: 'bold', fontSize: isMr ? '17px' : '15px', color: '#4b5563' }}>
            <IconWarningTriangle /> Policy Conflicts
          </span>
          <span style={{ fontSize: isMr ? '16px' : '14px', fontWeight: 700, background: '#374151', color: '#fff', padding: '4px 12px', borderRadius: '6px' }}>
            {t('draft_pending')}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div style={{
      background: 'var(--paper)',
      border: '2px solid var(--ink)',
      borderRadius: '12px',
      marginBottom: '16px',
      boxShadow: '0 4px 0 var(--ink)',
      overflow: 'hidden'
    }}>
      {/* Header */}
      <div
        onClick={() => setIsOpen(!isOpen)}
        style={{
          padding: '16px 20px',
          background: conflicts.length > 0 ? '#fff1f0' : '#f0fdf4',
          borderBottom: isOpen ? '2px solid var(--ink)' : 'none',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          cursor: 'pointer'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', fontWeight: 'bold', fontSize: isMr ? '17px' : '15px', color: 'var(--ink)' }}>
            <IconWarningTriangle /> Policy Conflicts
          </span>
          <span style={{
            fontSize: '11px',
            fontWeight: 'bold',
            background: conflicts.length > 0 ? 'var(--red)' : 'var(--blue)',
            color: '#fff',
            padding: '2px 8px',
            borderRadius: '12px',
            border: '1px solid var(--ink)'
          }}>
            {conflicts.length} Conflict{conflicts.length === 1 ? '' : 's'} Detected
          </span>
        </div>
        <span style={{ fontSize: '16px', fontWeight: 'bold' }}>{isOpen ? '▲' : '▼'}</span>
      </div>

      {/* Content */}
      {isOpen && (
        <div style={{ padding: '20px' }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '20px' }}>
              <span className="spinner" /> <span style={{ fontSize: '14px' }}>Cross-referencing 98,950+ GRs across departments...</span>
            </div>
          ) : conflicts.length === 0 ? (
            <div style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: '12px',
              padding: '16px',
              borderRadius: '8px',
              background: '#f0fdf4',
              border: '2px solid #bbf7d0',
              color: '#166534'
            }}>
              <span style={{ fontSize: '20px', fontWeight: 'bold' }}>✓</span>
              <div>
                <div style={{ fontWeight: 'bold', fontSize: '15px', marginBottom: '4px' }}>No Conflicts Detected</div>
                <div style={{ fontSize: '13.5px', lineHeight: '1.4', color: '#14532d' }}>
                  This draft is fully aligned with all existing Maharashtra Government policies. No policy overlaps or clashing instructions were found.
                </div>
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  onClick={handleDownloadFullReport}
                  disabled={generatingFull}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    flex: '1 1 220px',
                    padding: '14px 18px',
                    minHeight: '48px',
                    fontSize: isMr ? '16px' : '15px',
                    fontWeight: 'bold',
                    background: 'var(--blue)',
                    color: '#fff',
                    border: '2px solid var(--ink)',
                    borderRadius: '8px',
                    boxShadow: '0 3px 0 var(--ink)',
                    cursor: generatingFull ? 'wait' : 'pointer',
                    opacity: generatingFull ? 0.85 : 1
                  }}
                >
                  <IconDownload />
                  {generatingFull ? t('draft_generating_pdf') : t('draft_download_full_conflict_report')}
                </button>

                {onResolveAll && (
                  <button
                    type="button"
                    onClick={onResolveAll}
                    disabled={resolvingAll || allResolved}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '8px',
                      flex: '1 1 220px',
                      padding: '14px 18px',
                      minHeight: '48px',
                      fontSize: isMr ? '16px' : '15px',
                      fontWeight: 'bold',
                      background: '#16a34a',
                      color: '#fff',
                      border: '2px solid var(--ink)',
                      borderRadius: '8px',
                      boxShadow: '0 3px 0 var(--ink)',
                      cursor: resolvingAll ? 'wait' : (allResolved ? 'default' : 'pointer'),
                      opacity: resolvingAll ? 0.85 : (allResolved ? 0.9 : 1)
                    }}
                  >
                    <IconCheckCircle />
                    {resolvingAll
                      ? `${t('draft_resolving_conflicts')}${resolveProgress ? ` (${resolveProgress.done}/${resolveProgress.total})` : '...'}`
                      : allResolved
                        ? t('draft_all_conflicts_resolved')
                        : t('draft_resolve_all_conflicts')}
                  </button>
                )}
              </div>

              {conflicts.map((item, idx) => {
                const resolution = item.conflict_id ? resolvedInfo[item.conflict_id] : null;
                return (
                  <div key={idx} style={{
                    border: '2px solid var(--ink)',
                    borderRadius: '8px',
                    padding: '16px',
                    background: '#fff',
                    boxShadow: '0 2px 0 var(--ink)'
                  }}>
                    {/* Header: Conflict Category Type and GR ID */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', flexWrap: 'wrap', gap: '8px' }}>
                      <span style={{
                        fontSize: '13px',
                        fontWeight: 'bold',
                        background: 'var(--ink)',
                        color: '#fff',
                        padding: '3px 8px',
                        borderRadius: '4px',
                        border: '1px solid var(--ink)'
                      }}>
                        {item.conflict_type || 'Policy Conflict'}
                      </span>
                      {item.source_ocr_low_confidence && (
                        <span
                          title={isMr
                            ? 'हा संघर्ष कमी-विश्वासार्हतेच्या OCR मजकुरावर आधारित आहे — कदाचित चुकीचे वाचन असू शकते.'
                            : "This conflict's source clause came from a low-confidence OCR block — it may be a misread, not a real match."}
                          style={{
                            fontSize: '12px',
                            fontWeight: 'bold',
                            background: '#fff7ed',
                            color: '#92400e',
                            padding: '3px 10px',
                            borderRadius: '12px',
                            border: '1.5px solid var(--yellow)'
                          }}
                        >
                          ⚠ {isMr ? 'कमी-विश्वासार्हता OCR' : 'Low-confidence OCR'}
                        </span>
                      )}
                      {resolution && (
                        <span style={{
                          fontSize: '12px',
                          fontWeight: 'bold',
                          background: '#16a34a',
                          color: '#fff',
                          padding: '3px 10px',
                          borderRadius: '12px',
                          border: '1px solid var(--ink)'
                        }}>
                          ✓ {t('draft_resolved_badge')}
                        </span>
                      )}
                    </div>

                    {resolution && (
                      <div style={{
                        fontSize: '13.5px',
                        fontWeight: 'bold',
                        background: '#f0fdf4',
                        border: '1.5px solid #86efac',
                        color: '#166534',
                        padding: '8px 12px',
                        borderRadius: '6px',
                        marginBottom: '10px'
                      }}>
                        ✓ {t('draft_resolved_conflict_with')} {resolution.grLabel}
                      </div>
                    )}

                    {/* Department and Conflicting GR Metadata */}
                    <div style={{ fontSize: '14.5px', fontWeight: 'bold', marginBottom: '8px', color: '#1f2937' }}>
                      {item.existing_department?.replace(/_/g, ' ')} ({item.existing_gr_id})
                    </div>

                    {/* Conflicting Text Comparison */}
                    <div style={{
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '8px',
                      background: '#f9fafb',
                      padding: '12px',
                      border: '1px solid #d1d5db',
                      borderRadius: '6px',
                      marginBottom: '10px'
                    }}>
                      <div style={{ fontSize: '13.5px', lineHeight: '1.4' }}>
                        <span style={{ fontWeight: 'bold', color: 'var(--ink)' }}>
                          {resolution ? t('draft_updated_clause_text') : 'Draft Clause Text:'}
                        </span>
                        <div style={{
                          background: resolution ? '#dcfce7' : '#fffbe6',
                          padding: '6px 8px',
                          borderLeft: resolution ? '3px solid #16a34a' : '3px solid var(--yellow)',
                          marginTop: '4px',
                          borderRadius: '3px',
                          fontStyle: 'italic'
                        }}>
                          "{resolution ? resolution.revisedClause : item.draft_clause}"
                        </div>
                        {resolution && (
                          <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '4px', fontStyle: 'italic' }}>
                            {t('draft_original_clause_text')} "{resolution.originalClause}"
                          </div>
                        )}
                      </div>
                      <div style={{ fontSize: '13.5px', lineHeight: '1.4' }}>
                        <span style={{ fontWeight: 'bold', color: 'var(--ink)' }}>Conflicting Reference Text (GR #{item.existing_gr_id}):</span>
                        <div style={{ background: '#fff1f0', padding: '6px 8px', borderLeft: '3px solid var(--red)', marginTop: '4px', borderRadius: '3px', fontStyle: 'italic' }}>
                          "{item.existing_clause}"
                        </div>
                      </div>
                    </div>

                    {/* Contradiction Justification & Recommendation */}
                    <div style={{ fontSize: '14.5px', color: '#374151', marginBottom: '8px', lineHeight: '1.4' }}>
                      <strong>Reason:</strong> {item.justification}
                    </div>

                    <div style={{
                      fontSize: '14.5px',
                      background: '#fef3c7',
                      border: '1px solid #f59e0b',
                      padding: '10px 12px',
                      borderRadius: '6px',
                      color: '#92400e',
                      lineHeight: '1.4',
                      marginBottom: '12px'
                    }}>
                      <strong>Recommendation:</strong> Refer to GAD guidelines or align the drafting clause parameters.
                    </div>

                    {!resolution && item.resolution_status === 'attempted_still_conflicting' && (
                      <div style={{
                        fontSize: '13px',
                        fontWeight: 600,
                        color: '#92400e',
                        marginBottom: '10px'
                      }}>
                        ⚠ {t('draft_still_conflicting')}
                      </div>
                    )}
                    {!resolution && item.resolution_status === 'attempted_error' && (
                      <div style={{
                        fontSize: '13px',
                        fontWeight: 600,
                        color: 'var(--red)',
                        marginBottom: '10px'
                      }}>
                        ⚠ {t('draft_resolve_error')}
                      </div>
                    )}

                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', flexWrap: 'wrap' }}>
                      {!resolution && onResolveOne && item.conflict_id && (
                        <button
                          type="button"
                          onClick={() => onResolveOne(item)}
                          disabled={resolvingConflictId === item.conflict_id}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '6px',
                            padding: '7px 12px',
                            minHeight: '32px',
                            fontSize: '12.5px',
                            fontWeight: 700,
                            background: '#16a34a',
                            color: '#fff',
                            border: '1.5px solid var(--ink)',
                            borderRadius: '6px',
                            cursor: resolvingConflictId === item.conflict_id ? 'wait' : 'pointer',
                            opacity: resolvingConflictId === item.conflict_id ? 0.7 : 1
                          }}
                        >
                          <IconCheckCircle />
                          {resolvingConflictId === item.conflict_id ? t('draft_resolving_conflicts') : t('draft_resolve_one')}
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => handleDownloadOneReport(item, idx)}
                        disabled={generatingIdx === idx}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '7px 12px',
                          minHeight: '32px',
                          fontSize: '12.5px',
                          fontWeight: 600,
                          background: '#fff',
                          color: 'var(--ink)',
                          border: '1.5px solid var(--ink)',
                          borderRadius: '6px',
                          cursor: generatingIdx === idx ? 'wait' : 'pointer',
                          opacity: generatingIdx === idx ? 0.7 : 1
                        }}
                      >
                        <IconDownload />
                        {generatingIdx === idx ? t('draft_generating_pdf') : t('draft_download_conflict_report')}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );


}
