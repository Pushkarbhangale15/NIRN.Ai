import React from 'react';

const STAGES = [
  "Brief",
  "Generate Draft",
  "Template Validation",
  "Conflict Detection",
  "Reference Tracking",
  "Ready for Review"
];

export default function WorkflowStepper({ currentStage = 0, isGenerating = false }) {
  return (
    <div className="workflow-stepper-container" style={{
      background: 'var(--paper)',
      border: '2px solid var(--ink)',
      borderRadius: '12px',
      padding: '16px 20px',
      marginBottom: '20px',
      boxShadow: '0 4px 0 var(--ink)',
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        position: 'relative',
        flexWrap: 'wrap',
        gap: '12px'
      }}>
        {STAGES.map((stage, idx) => {
          const isCompleted = idx < currentStage;
          const isActive = idx === currentStage;
          const isPending = idx > currentStage;

          let badgeBg = '#e5e7eb';
          let badgeColor = '#6b7280';
          let borderColor = '#d1d5db';

          if (isCompleted) {
            badgeBg = 'var(--blue)';
            badgeColor = '#ffffff';
            borderColor = 'var(--ink)';
          } else if (isActive) {
            badgeBg = isGenerating ? 'var(--yellow)' : 'var(--blue)';
            badgeColor = 'var(--ink)';
            borderColor = 'var(--ink)';
          }

          return (
            <React.Fragment key={stage}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                zIndex: 2,
                opacity: isPending && !isGenerating && currentStage === 0 ? 0.6 : 1,
                transition: 'all 0.2s ease'
              }}>
                <div style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: '50%',
                  background: badgeBg,
                  color: badgeColor,
                  border: `2px solid ${borderColor}`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '13px',
                  fontWeight: 'bold',
                  boxShadow: isActive || isCompleted ? '0 2px 0 var(--ink)' : 'none'
                }}>
                  {isCompleted ? '✓' : idx + 1}
                </div>
                <span style={{
                  fontSize: '13px',
                  fontWeight: isActive ? 'bold' : isCompleted ? '600' : '500',
                  color: isActive ? 'var(--ink)' : isCompleted ? 'var(--ink)' : '#6b7280'
                }}>
                  {stage}
                </span>
              </div>
              {idx < STAGES.length - 1 && (
                <div style={{
                  flex: 1,
                  height: '2px',
                  minWidth: '16px',
                  background: isCompleted ? 'var(--ink)' : '#e5e7eb',
                  transition: 'background 0.3s ease'
                }} />
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}
