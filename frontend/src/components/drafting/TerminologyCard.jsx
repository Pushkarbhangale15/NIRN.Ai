import React, { useState } from 'react';

export default function TerminologyCard({ terms = [], loading, hasGenerated }) {
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
            🌐 Card 4 — Legal Terminology Assistance
          </span>
          <span style={{ fontSize: '12px', background: '#e5e7eb', padding: '2px 8px', borderRadius: '4px', color: '#6b7280' }}>
            Pending Draft
          </span>
        </div>
      </div>
    );
  }

  // Demonstration bilingual terms if backend array is empty
  const displayTerms = terms.length > 0 ? terms : [
    {
      english_term: "Administrative Approval",
      marathi_term: "प्रशासकीय मान्यता",
      definition: "Official formal approval from the competent authority before project execution or fund release."
    },
    {
      english_term: "Financial Sanction",
      marathi_term: "वित्तीय मंजुरी",
      definition: "Monetary authorization granted in accordance with standard delegation of financial powers rules."
    },
    {
      english_term: "Eligible Beneficiary",
      marathi_term: "पात्र लाभार्थी",
      definition: "Individual or institution satisfying prescribed eligibility criteria under the government scheme."
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
          background: '#fefce8',
          borderBottom: isOpen ? '2px solid var(--ink)' : 'none',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          cursor: 'pointer'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontWeight: 'bold', fontSize: '15px', color: 'var(--ink)' }}>
            🌐 Card 4 — Legal Terminology
          </span>
          <span style={{
            fontSize: '11px',
            fontWeight: 'bold',
            background: 'var(--yellow)',
            color: 'var(--ink)',
            padding: '2px 8px',
            borderRadius: '12px',
            border: '1px solid var(--ink)'
          }}>
            Bilingual Terms ({displayTerms.length})
          </span>
        </div>
        <span style={{ fontSize: '16px', fontWeight: 'bold' }}>{isOpen ? '▲' : '▼'}</span>
      </div>

      {/* Content */}
      {isOpen && (
        <div style={{ padding: '20px' }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '20px' }}>
              <span className="spinner" /> <span style={{ fontSize: '13px' }}>Mapping administrative Marathi/English legal vocabulary...</span>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {displayTerms.map((t, idx) => (
                <div key={idx} style={{
                  border: '1px solid var(--ink)',
                  borderRadius: '8px',
                  padding: '12px 14px',
                  background: '#fff',
                  boxShadow: '0 2px 0 var(--ink)'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                    <span style={{ fontSize: '15px', fontWeight: 'bold', color: 'var(--ink)' }}>
                      {t.english_term}
                    </span>
                    <span style={{ fontSize: '13px', color: '#6b7280' }}>↓ Marathi</span>
                    <span style={{ fontSize: '16px', fontWeight: 'bold', color: 'var(--blue)', fontFamily: 'marathi, sans-serif' }}>
                      {t.marathi_term}
                    </span>
                  </div>
                  {t.definition && (
                    <div style={{ fontSize: '14px', color: '#4b5563', marginTop: '6px', background: '#f9fafb', padding: '8px 10px', borderRadius: '4px', lineHeight: '1.4' }}>
                      <strong>Definition:</strong> {t.definition}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
