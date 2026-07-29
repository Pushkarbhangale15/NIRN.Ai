import React, { useState } from 'react';
import { useLanguage } from '../../LanguageContext.jsx';

const IconTranslate = () => (


  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
    <path d="M12.87 15.07-2.54-2.51.03-.03A17.5 17.5 0 0 0 8.36 6H10v2H7.75l-.09.34a15.3 15.3 0 0 1-2.1 4.06 12.34 12.34 0 0 0 3.8-2.13Zm5.63-1.53H16l-4.5 12h1.75l1.13-3h5.24l1.13 3H22ZM14.9 15h4.2L17 10.35Z" />
    <path d="M11 4H2v2h2.5v1H2v2h2.5A9.5 9.5 0 0 0 2 14h2c.15-.63.36-1.24.63-1.8A11 11 0 0 0 6 14h2a10 10 0 0 1-1.9-2.4A8.4 8.4 0 0 0 6.5 9H11Z" />
  </svg>
);

export default function TerminologyCard({ terms = [], loading, hasGenerated }) {
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
          <span style={{ display: 'inline-flex', alignItems: 'center', flexWrap: 'wrap', gap: '8px', minWidth: 0, fontWeight: 'bold', fontSize: isMr ? '17px' : '15px', color: '#4b5563' }}>
            <IconTranslate /> Card 4 — Legal Terminology Assistance
          </span>
          <span style={{ fontSize: isMr ? '16px' : '14px', fontWeight: 700, background: '#374151', color: '#fff', padding: '4px 12px', borderRadius: '6px' }}>
            {t('draft_pending')}
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
          <span style={{ display: 'inline-flex', alignItems: 'center', flexWrap: 'wrap', gap: '8px', minWidth: 0, fontWeight: 'bold', fontSize: isMr ? '17px' : '15px', color: 'var(--ink)' }}>
            <IconTranslate /> Card 4 — Legal Terminology
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
              <span className="spinner" /> <span style={{ fontSize: '14px' }}>Mapping administrative Marathi/English legal vocabulary...</span>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {displayTerms.map((t, idx) => {
                const isMrSource = t.source_language === 'mr' || (t.source_language?.value === 'mr');
                const docWord = t.source_term || (isMrSource ? t.marathi_term : t.english_term) || t.english_term || '';
                const equivWord = t.target_term || (isMrSource ? t.english_term : t.marathi_term) || t.marathi_term || '';
                const noteText = t.note || t.definition || '';

                const srcLangLabel = isMrSource ? 'Marathi' : 'English';
                const tgtLangLabel = isMrSource ? 'English' : 'Marathi';

                return (
                  <div key={idx} style={{
                    border: '1px solid var(--ink)',
                    borderRadius: '8px',
                    padding: '14px 16px',
                    background: '#fff',
                    boxShadow: '0 2px 0 var(--ink)'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
                      {/* Left: Word in Document */}
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: '10px', fontWeight: 'bold', color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '3px' }}>
                          Word in Document ({srcLangLabel})
                        </div>
                        <div style={{ fontSize: '15px', fontWeight: 'bold', color: 'var(--ink)' }}>
                          {docWord}
                        </div>
                      </div>

                      {/* Middle Arrow */}
                      <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#9ca3af', padding: '0 6px' }}>
                        →
                      </div>

                      {/* Right: Approved Translation */}
                      <div style={{ flex: 1, textAlign: 'right' }}>
                        <div style={{ fontSize: '10px', fontWeight: 'bold', color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '3px' }}>
                          Approved Equivalent ({tgtLangLabel})
                        </div>
                        <div style={{ fontSize: '16px', fontWeight: 'bold', color: 'var(--blue)', fontFamily: "'Noto Sans Devanagari', 'Mangal', sans-serif" }}>
                          {equivWord}
                        </div>
                      </div>
                    </div>

                    {noteText && (
                      <div style={{ fontSize: '13px', color: '#4b5563', marginTop: '10px', background: '#f9fafb', padding: '6px 10px', borderRadius: '4px', borderLeft: '3px solid var(--blue)' }}>
                        <strong>Note:</strong> {noteText}
                      </div>
                    )}
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
