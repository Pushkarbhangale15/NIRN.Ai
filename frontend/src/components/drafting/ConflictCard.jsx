import React, { useState } from 'react';
import { useLanguage } from '../../LanguageContext.jsx';

const IconWarningTriangle = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
    <path d="M1 21h22L12 2 1 21Zm12-3h-2v-2h2Zm0-4h-2v-4h2Z" />
  </svg>
);

export default function ConflictCard({ conflicts = [], loading, hasGenerated }) {
  const { t, siteLanguage } = useLanguage();
  const isMr = siteLanguage === 'mr';
  const [isOpen, setIsOpen] = useState(true);

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
              {conflicts.map((item, idx) => {
                const isHigh = item.severity === 'Critical' || item.severity === 'High' || item.confidence >= 0.8;
                const isMed = item.severity === 'Medium' || (item.confidence >= 0.6 && item.confidence < 0.8);
                const badgeColor = isHigh ? 'var(--red)' : isMed ? 'var(--yellow)' : 'var(--blue)';
                const textColor = isHigh ? '#fff' : 'var(--ink)';

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
                      <span style={{
                        fontSize: '12px',
                        fontWeight: 'bold',
                        background: badgeColor,
                        color: textColor,
                        padding: '2px 8px',
                        borderRadius: '4px',
                        border: '1px solid var(--ink)',
                        textTransform: 'uppercase'
                      }}>
                        {item.severity || (isHigh ? 'High Risk' : 'Medium Risk')}
                      </span>
                    </div>

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
                        <span style={{ fontWeight: 'bold', color: 'var(--ink)' }}>Draft Clause Text:</span>
                        <div style={{ background: '#fffbe6', padding: '6px 8px', borderLeft: '3px solid var(--yellow)', marginTop: '4px', borderRadius: '3px', fontStyle: 'italic' }}>
                          "{item.draft_clause}"
                        </div>
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
                      lineHeight: '1.4'
                    }}>
                      <strong>Recommendation:</strong> Refer to GAD guidelines or align the drafting clause parameters.
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
