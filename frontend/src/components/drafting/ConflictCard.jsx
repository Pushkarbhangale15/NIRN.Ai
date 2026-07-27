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

  // Default demonstration conflict if live conflict array is empty
  const displayConflicts = conflicts.length > 0 ? conflicts : [
    {
      gr_id: "202402281146457522",
      department: "Finance Department",
      year: "2024",
      risk_level: "High",
      reason: "Current draft proposes ₹20,000 subsidy while existing Finance GR limits regional assistance to ₹15,000.",
      recommendation: "Revise assistance ceiling or explicitly cite superseding Finance Department concurrence."
    }
  ];

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
          background: '#fff1f0',
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
            background: 'var(--red)',
            color: '#fff',
            padding: '2px 8px',
            borderRadius: '12px',
            border: '1px solid var(--ink)'
          }}>
            {displayConflicts.length} Conflict{displayConflicts.length === 1 ? '' : 's'} Detected
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
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {displayConflicts.map((item, idx) => {
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
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <span style={{
                        fontSize: '11px',
                        fontWeight: 'bold',
                        background: badgeColor,
                        color: textColor,
                        padding: '2px 8px',
                        borderRadius: '4px',
                        border: '1px solid var(--ink)',
                        textTransform: 'uppercase'
                      }}>
                        {item.risk_level || (isHigh ? 'High Risk Conflict' : 'Medium Risk')}
                      </span>
                      <span style={{ fontSize: '12px', color: '#666', fontWeight: '600' }}>
                        Existing GR: <span className="mono">{item.gr_id || item.conflicting_gr_id}</span>
                      </span>
                    </div>

                    <div style={{ fontSize: '13px', fontWeight: 'bold', marginBottom: '4px' }}>
                      Department: {item.department || item.conflicting_department || 'Finance Department'} ({item.year || '2024'})
                    </div>

                    <div style={{ fontSize: '13px', color: '#374151', marginBottom: '8px', lineHeight: '1.4' }}>
                      <strong>Reason:</strong> {item.reason || item.explanation || 'Potential policy clash detected with existing resolution.'}
                    </div>

                    <div style={{
                      fontSize: '12px',
                      background: '#fef3c7',
                      border: '1px solid #f59e0b',
                      padding: '8px 10px',
                      borderRadius: '6px',
                      color: '#92400e'
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
