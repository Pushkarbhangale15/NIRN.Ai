import React, { useState, useEffect, useRef } from 'react';
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
  onResolveSelected,
  onManualEditSelected,
  onIgnoreSelected,
  resolvingSelected = false,
  resolveSelectedProgress = null,
  ignoringSelected = false,
}) {
  const { t, siteLanguage } = useLanguage();
  const isMr = siteLanguage === 'mr';
  const [isOpen, setIsOpen] = useState(true);
  const [ignoredOpen, setIgnoredOpen] = useState(false);
  const [generatingFull, setGeneratingFull] = useState(false);
  const [generatingIdx, setGeneratingIdx] = useState(null);
  const [selectedIds, setSelectedIds] = useState(() => new Set());

  const toggleSelected = (conflictId) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(conflictId)) next.delete(conflictId);
      else next.add(conflictId);
      return next;
    });
  };

  // Selection stays visible (with progress) for the whole batch — cleared
  // only once the parent reports the batch actually finished, not the
  // instant the button is clicked, so the toolbar's progress readout
  // doesn't disappear before the LLM/API calls it represents are done.
  const wasResolvingSelected = useRef(false);
  const wasIgnoringSelected = useRef(false);
  useEffect(() => {
    if (wasResolvingSelected.current && !resolvingSelected) {
      setSelectedIds(new Set());
    }
    wasResolvingSelected.current = resolvingSelected;
  }, [resolvingSelected]);
  useEffect(() => {
    if (wasIgnoringSelected.current && !ignoringSelected) {
      setSelectedIds(new Set());
    }
    wasIgnoringSelected.current = ignoringSelected;
  }, [ignoringSelected]);

  // Ignored (dismissed) conflicts are excluded from the active list, all
  // counts, and every resolve/select operation — they're shown separately
  // below, read-only, with the reason they were ignored.
  const activeConflicts = conflicts.filter(c => !c.is_dismissed);
  const dismissedConflicts = conflicts.filter(c => c.is_dismissed);

  const resolvableConflicts = activeConflicts.filter(c => c.conflict_id);
  const allResolved = resolvableConflicts.length > 0 &&
    resolvableConflicts.every(c => resolvedInfo[c.conflict_id]);

  const handleDownloadFullReport = async () => {
    if (generatingFull) return;
    setGeneratingFull(true);
    try {
      await generateConflictPDF(draftText, activeConflicts, {
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
          background: activeConflicts.length > 0 ? '#fff1f0' : '#f0fdf4',
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
            background: activeConflicts.length > 0 ? 'var(--red)' : 'var(--blue)',
            color: '#fff',
            padding: '2px 8px',
            borderRadius: '12px',
            border: '1px solid var(--ink)'
          }}>
            {activeConflicts.length} Conflict{activeConflicts.length === 1 ? '' : 's'} Detected
          </span>
          {dismissedConflicts.length > 0 && (
            <span style={{
              fontSize: '11px',
              fontWeight: 'bold',
              background: '#9ca3af',
              color: '#fff',
              padding: '2px 8px',
              borderRadius: '12px',
              border: '1px solid var(--ink)'
            }}>
              {dismissedConflicts.length} Ignored
            </span>
          )}
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
          ) : activeConflicts.length === 0 ? (
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

              {selectedIds.size > 0 && (
                <div style={{
                  display: 'flex',
                  gap: '10px',
                  flexWrap: 'wrap',
                  alignItems: 'center',
                  padding: '10px 14px',
                  background: '#eff6ff',
                  border: '2px solid var(--ink)',
                  borderRadius: '8px'
                }}>
                  <span style={{ fontSize: '13.5px', fontWeight: 'bold', color: 'var(--ink)', marginRight: '4px' }}>
                    {selectedIds.size} selected
                  </span>
                  <button
                    type="button"
                    onClick={() => onResolveSelected && onResolveSelected(activeConflicts.filter(c => selectedIds.has(c.conflict_id)))}
                    disabled={resolvingSelected}
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: '6px',
                      padding: '9px 14px', fontSize: '13px', fontWeight: 700,
                      background: '#16a34a', color: '#fff', border: '1.5px solid var(--ink)',
                      borderRadius: '6px', cursor: resolvingSelected ? 'wait' : 'pointer',
                      opacity: resolvingSelected ? 0.7 : 1
                    }}
                  >
                    <IconCheckCircle />
                    {resolvingSelected
                      ? `Resolving...${resolveSelectedProgress ? ` (${resolveSelectedProgress.done}/${resolveSelectedProgress.total})` : ''}`
                      : 'Resolve Selected'}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      const only = activeConflicts.find(c => selectedIds.has(c.conflict_id));
                      if (only && onManualEditSelected) {
                        onManualEditSelected(only);
                        setSelectedIds(new Set());
                      }
                    }}
                    disabled={selectedIds.size !== 1}
                    title={selectedIds.size !== 1 ? 'Select exactly one conflict to manually edit' : undefined}
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: '6px',
                      padding: '9px 14px', fontSize: '13px', fontWeight: 700,
                      background: selectedIds.size === 1 ? '#f59e0b' : '#d1d5db',
                      color: '#fff', border: '1.5px solid var(--ink)',
                      borderRadius: '6px', cursor: selectedIds.size === 1 ? 'pointer' : 'not-allowed',
                      opacity: selectedIds.size === 1 ? 1 : 0.7
                    }}
                  >
                    ✎ Manually Edit Selected
                  </button>
                  <button
                    type="button"
                    onClick={() => onIgnoreSelected && onIgnoreSelected(activeConflicts.filter(c => selectedIds.has(c.conflict_id)))}
                    disabled={ignoringSelected}
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: '6px',
                      padding: '9px 14px', fontSize: '13px', fontWeight: 700,
                      background: '#6b7280', color: '#fff', border: '1.5px solid var(--ink)',
                      borderRadius: '6px', cursor: ignoringSelected ? 'wait' : 'pointer',
                      opacity: ignoringSelected ? 0.7 : 1
                    }}
                  >
                    ✕ {ignoringSelected ? 'Ignoring...' : 'Ignore Selected'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedIds(new Set())}
                    style={{
                      marginLeft: 'auto', padding: '9px 14px', fontSize: '13px', fontWeight: 600,
                      background: 'transparent', color: 'var(--ink)', border: '1.5px solid var(--ink)',
                      borderRadius: '6px', cursor: 'pointer'
                    }}
                  >
                    Clear selection
                  </button>
                </div>
              )}

              {activeConflicts.map((item, idx) => {
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
                      {item.conflict_id && (
                        <input
                          type="checkbox"
                          checked={selectedIds.has(item.conflict_id)}
                          onChange={() => toggleSelected(item.conflict_id)}
                          disabled={resolvingSelected || ignoringSelected}
                          aria-label="Select this conflict"
                          style={{ width: '18px', height: '18px', cursor: 'pointer', accentColor: 'var(--ink)' }}
                        />
                      )}
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

          {dismissedConflicts.length > 0 && (
            <div style={{ marginTop: '16px', border: '1.5px solid #d1d5db', borderRadius: '8px', overflow: 'hidden' }}>
              <div
                onClick={() => setIgnoredOpen(!ignoredOpen)}
                style={{
                  padding: '10px 16px',
                  background: '#f3f4f6',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  cursor: 'pointer'
                }}
              >
                <span style={{ fontSize: '13.5px', fontWeight: 'bold', color: '#4b5563' }}>
                  Ignored Conflicts ({dismissedConflicts.length})
                </span>
                <span style={{ fontSize: '13px', fontWeight: 'bold', color: '#6b7280' }}>{ignoredOpen ? '▲' : '▼'}</span>
              </div>
              {ignoredOpen && (
                <div style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {dismissedConflicts.map((item, idx) => (
                    <div key={item.conflict_id || idx} style={{
                      border: '1.5px solid #e5e7eb',
                      borderRadius: '6px',
                      padding: '12px 14px',
                      background: '#fafafa',
                      opacity: 0.75
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px', flexWrap: 'wrap' }}>
                        <span style={{
                          fontSize: '11.5px',
                          fontWeight: 'bold',
                          background: '#9ca3af',
                          color: '#fff',
                          padding: '2px 8px',
                          borderRadius: '10px'
                        }}>
                          Ignored
                        </span>
                        <span style={{ fontSize: '13px', fontWeight: 600, color: '#6b7280', textDecoration: 'line-through' }}>
                          {item.conflict_type || 'Policy Conflict'}
                        </span>
                      </div>
                      <div style={{ fontSize: '13px', color: '#6b7280', marginBottom: '6px' }}>
                        {item.existing_department?.replace(/_/g, ' ')} ({item.existing_gr_id})
                      </div>
                      <div style={{ fontSize: '13px', color: '#6b7280', fontStyle: 'italic', marginBottom: item.dismissed_reason ? '6px' : 0 }}>
                        "{item.draft_clause}"
                      </div>
                      {item.dismissed_reason && (
                        <div style={{ fontSize: '12.5px', color: '#78716c' }}>
                          <strong>Reason:</strong> {item.dismissed_reason}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );


}
