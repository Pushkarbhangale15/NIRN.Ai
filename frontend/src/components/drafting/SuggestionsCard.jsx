import React from 'react';

const IconLightbulb = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="currentColor" viewBox="0 0 24 24">
    <path d="M9 21h6v-1H9zm3-19a7 7 0 0 0-4 12.74V17a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-2.26A7 7 0 0 0 12 2Z" />
  </svg>
);
const IconCheckSmall = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
    <path d="M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
  </svg>
);
const IconWarnSmall = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
    <path d="M1 21h22L12 2 1 21Zm12-3h-2v-2h2Zm0-4h-2v-4h2Z" />
  </svg>
);

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
      <h3 style={{ margin: '0 0 12px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <IconLightbulb /> AI Review Suggestions
      </h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
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
                fontSize: '15px',
                padding: '10px 14px',
                borderRadius: '6px',
                background: isPass ? '#f0fdf4' : '#fffbe6',
                border: isPass ? '1px solid #bbf7d0' : '1px solid #ffe58f'
              }}
            >
              <span style={{ fontWeight: 'bold', color: isPass ? '#166534' : '#854d0e', display: 'inline-flex' }}>
                {isPass ? <IconCheckSmall /> : <IconWarnSmall />}
              </span>
              <span style={{ color: isPass ? '#166534' : '#854d0e', lineHeight: '1.5' }}>
                {textStr}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
