import React from 'react';

export default function SuggestionsCard({ suggestions = [], hasGenerated }) {
  if (!hasGenerated) {
    return null;
  }

  const defaultSuggestions = suggestions.length > 0 ? suggestions : [
    { type: 'pass', text: 'Uses official legal language and statutory preamble formulation' },
    { type: 'warn', text: 'Include explicit quarterly implementation timeline for grievance redressal' },
    { type: 'warn', text: 'Specify the designated monitoring authority at district level' },
    { type: 'pass', text: 'References existing higher education research grant guidelines' }
  ];

  return (
    <div style={{
      background: 'var(--paper)',
      border: '2px solid var(--ink)',
      borderRadius: '12px',
      padding: '20px',
      boxShadow: '0 4px 0 var(--ink)',
      marginTop: '16px'
    }}>
      <h4 style={{ margin: '0 0 12px 0', fontSize: '15px', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '6px' }}>
        ✨ AI Review Suggestions
      </h4>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {defaultSuggestions.map((item, idx) => {
          const isPass = item.type === 'pass' || (typeof item === 'string' && !item.toLowerCase().includes('add') && !item.toLowerCase().includes('mention'));
          const textStr = typeof item === 'string' ? item : item.text;

          return (
            <div
              key={idx}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '8px',
                fontSize: '13px',
                padding: '8px 12px',
                borderRadius: '6px',
                background: isPass ? '#f0fdf4' : '#fffbe6',
                border: isPass ? '1px solid #bbf7d0' : '1px solid #ffe58f'
              }}
            >
              <span style={{ fontWeight: 'bold', color: isPass ? '#166534' : '#854d0e' }}>
                {isPass ? '✓' : '⚠'}
              </span>
              <span style={{ color: isPass ? '#166534' : '#854d0e', lineHeight: '1.4' }}>
                {textStr}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
