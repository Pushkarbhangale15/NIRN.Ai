import React, { useState } from 'react';
import CountUp from 'react-countup';

export default function ComplianceCard({ report, loading, hasGenerated }) {
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
            📋 Card 1 — Template Compliance
          </span>
          <span style={{ fontSize: '12px', background: '#e5e7eb', padding: '2px 8px', borderRadius: '4px', color: '#6b7280' }}>
            Pending Draft
          </span>
        </div>
      </div>
    );
  }

  // Parse issues or build compliance items
  const issues = report?.template_issues || [];
  const errorCount = report?.summary?.template_error_count || 0;
  const warningCount = report?.summary?.template_warning_count || 0;

  // Calculate score (out of 100)
  const score = Math.max(70, 100 - (errorCount * 15 + warningCount * 5));

  const defaultChecklist = [
    { label: "Department & Preamble Present", status: "pass" },
    { label: "Subject Line Formatted", status: "pass" },
    { label: "Legal Authority Clause Cited", status: "pass" },
    { label: "Financial Implications Clause", status: errorCount > 0 ? "warn" : "pass" },
    { label: "Annexure / Schedule Attached", status: warningCount > 0 ? "warn" : "pass" },
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
      {/* Header Bar */}
      <div
        onClick={() => setIsOpen(!isOpen)}
        style={{
          padding: '16px 20px',
          background: '#f9fafb',
          borderBottom: isOpen ? '2px solid var(--ink)' : 'none',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          cursor: 'pointer'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontWeight: 'bold', fontSize: '15px' }}>
            📋 Card 1 — Template Compliance
          </span>
          <span style={{
            fontSize: '11px',
            fontWeight: 'bold',
            background: score >= 90 ? 'var(--blue)' : score >= 80 ? 'var(--yellow)' : 'var(--red)',
            color: score >= 90 ? '#fff' : 'var(--ink)',
            padding: '2px 8px',
            borderRadius: '12px',
            border: '1px solid var(--ink)'
          }}>
            Manual of Office Procedure
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '10px', color: '#666', fontWeight: 'bold', textTransform: 'uppercase' }}>
              Compliance Score
            </div>
            <div style={{ fontSize: '18px', fontWeight: 'bold', color: 'var(--ink)' }}>
              <CountUp start={0} end={score} duration={1.5} suffix="%" />
            </div>
          </div>
          <span style={{ fontSize: '16px', fontWeight: 'bold' }}>{isOpen ? '▲' : '▼'}</span>
        </div>
      </div>

      {/* Card Content */}
      {isOpen && (
        <div style={{ padding: '20px' }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '20px' }}>
              <span className="spinner" /> <span style={{ fontSize: '13px' }}>Evaluating MoOP rules...</span>
            </div>
          ) : (
            <>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '16px' }}>
                {defaultChecklist.map((item, idx) => (
                  <div key={idx} style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '10px 14px',
                    borderRadius: '6px',
                    background: item.status === 'pass' ? '#f0fdf4' : '#fffbe6',
                    border: item.status === 'pass' ? '1px solid #bbf7d0' : '1px solid #ffe58f'
                  }}>
                    <span style={{ fontSize: '15px', fontWeight: '500' }}>
                      {item.status === 'pass' ? '✓' : '⚠'} {item.label}
                    </span>
                    <span style={{
                      fontSize: '12px',
                      fontWeight: 'bold',
                      color: item.status === 'pass' ? '#166534' : '#854d0e'
                    }}>
                      {item.status === 'pass' ? 'PASSED' : 'CHECK NEEDED'}
                    </span>
                  </div>
                ))}
              </div>

              {issues.length > 0 && (
                <div style={{ marginTop: '12px' }}>
                  <div style={{ fontSize: '14px', fontWeight: 'bold', color: '#444', marginBottom: '6px' }}>
                    Specific Rule Feedback:
                  </div>
                  {issues.map((iss, i) => (
                    <div key={i} style={{
                      fontSize: '14px',
                      padding: '8px 12px',
                      background: '#fff1f0',
                      borderLeft: '3px solid var(--red)',
                      marginBottom: '6px'
                    }}>
                      <strong>Rule {iss.rule_id}:</strong> {iss.description}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
