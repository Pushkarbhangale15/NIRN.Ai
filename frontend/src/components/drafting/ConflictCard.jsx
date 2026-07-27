import React, { useState } from 'react';

export default function ConflictCard({ report, loading, hasGenerated }) {
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
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontWeight: 'bold', fontSize: '15px', color: '#6b7280' }}>
            ⚠️ Card 2 — Conflict Detection
          </span>
          <span style={{ fontSize: '12px', background: '#e5e7eb', padding: '2px 8px', borderRadius: '4px', color: '#6b7280' }}>
            Pending Draft
          </span>
        </div>
      </div>
    );
  }

  const conflicts = report?.conflicts || [];

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
          <span style={{ fontWeight: 'bold', fontSize: '15px', color: 'var(--ink)' }}>
            ⚠️ Card 2 — Conflict Detection
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
              <span className="spinner" /> <span style={{ fontSize: '13px' }}>Cross-referencing 98,950+ GRs across departments...</span>
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
                  This draft is fully aligned with all existing Maharashtra Government Department policies and resolutions. No overlap or financial clashes were found.
                </div>
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {conflicts.map((item, idx) => {
                const isHigh = item.risk_level === 'High' || item.confidence >= 0.8;
                const isMed = item.risk_level === 'Medium' || (item.confidence >= 0.6 && item.confidence < 0.8);
                const badgeColor = isHigh ? 'var(--red)' : isMed ? 'var(--yellow)' : 'var(--blue)';
                const textColor = isHigh ? '#fff' : 'var(--ink)';

                return (
                  <div key={idx} style={{
                    border: '2px solid var(--ink)',
                    borderRadius: '8px',
                    padding: '14px',
                    background: '#fff',
                    boxShadow: '0 2px 0 var(--ink)'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                      <span style={{
                        fontSize: '13px',
                        fontWeight: 'bold',
                        background: badgeColor,
                        color: textColor,
                        padding: '3px 8px',
                        borderRadius: '4px',
                        border: '1px solid var(--ink)',
                        textTransform: 'uppercase'
                      }}>
                        {item.risk_level || (isHigh ? 'High Risk Conflict' : 'Medium Risk')}
                      </span>
                      <span style={{ fontSize: '14px', color: '#666', fontWeight: '600' }}>
                        Existing GR: <span className="mono">{item.gr_id || item.conflicting_gr_id}</span>
                      </span>
                    </div>

                    <div style={{ fontSize: '15px', fontWeight: 'bold', marginBottom: '6px' }}>
                      Department: {item.department || item.conflicting_department || 'Finance Department'} ({item.year || '2024'})
                    </div>

                    <div style={{ fontSize: '15.5px', color: '#374151', marginBottom: '10px', lineHeight: '1.5' }}>
                      <strong>Reason:</strong> {item.reason || item.explanation || 'Potential policy clash detected with existing resolution.'}
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
                      <strong>💡 Recommendation:</strong> {item.recommendation || 'Revise subsidy amount or explicitly cite superseding department authority.'}
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
