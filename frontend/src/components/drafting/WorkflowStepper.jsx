import React from 'react';
import { useLanguage } from '../../LanguageContext.jsx';

const STAGE_KEYS = [
  "draft_stage_brief",
  "draft_stage_generate",
  "draft_stage_template",
  "draft_stage_conflict",
  "draft_stage_reference",
  "draft_stage_ready"
];

export default function WorkflowStepper({ currentStage = 0, isGenerating = false }) {
  const { t, siteLanguage } = useLanguage();
  const isMr = siteLanguage === 'mr';

  return (
    <div className="workflow-stepper-container" style={{
      background: 'var(--paper)',
      border: '2px solid var(--ink)',
      borderRadius: '12px',
      padding: '28px 32px',
      marginBottom: '28px',
      boxShadow: '0 4px 0 var(--ink)',
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        position: 'relative',
        flexWrap: 'wrap',
        gap: '20px'
      }}>
        {STAGE_KEYS.map((stageKey, idx) => {
          const isCompleted = idx < currentStage;
          const isActive = idx === currentStage;
          const isPending = idx > currentStage;

          let badgeBg = '#e5e7eb';
          let badgeColor = '#374151';
          let borderColor = '#9ca3af';

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
            <React.Fragment key={stageKey}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                zIndex: 2,
                opacity: isPending ? 0.4 : 1,
                transition: 'all 0.2s ease'
              }}>
                <div style={{
                  width: isActive ? '36px' : '30px',
                  height: isActive ? '36px' : '30px',
                  borderRadius: '50%',
                  background: badgeBg,
                  color: badgeColor,
                  border: `${isActive ? 3 : 2}px solid ${borderColor}`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: isActive ? '15px' : '13px',
                  fontWeight: 800,
                  boxShadow: isActive || isCompleted ? '0 2px 0 var(--ink)' : 'none',
                  transition: 'all 0.2s ease'
                }}>
                  {isCompleted ? '✓' : idx + 1}
                </div>
                <span style={{
                  fontSize: isMr ? '17px' : '15px',
                  fontWeight: isActive ? 800 : isCompleted ? 700 : 600,
                  color: isActive || isCompleted ? 'var(--ink)' : '#4b5563'
                }}>
                  {t(stageKey)}
                </span>
              </div>
              {idx < STAGE_KEYS.length - 1 && (
                <div style={{
                  flex: 1,
                  height: '5px',
                  minWidth: '24px',
                  borderRadius: '3px',
                  background: isCompleted ? 'var(--blue)' : '#d1d5db',
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
