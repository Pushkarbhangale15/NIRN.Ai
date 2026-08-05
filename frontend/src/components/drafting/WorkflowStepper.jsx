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
  const { t } = useLanguage();
  const clampedStage = Math.min(Math.max(currentStage, 0), STAGE_KEYS.length - 1);
  const progressPct = Math.round((clampedStage / (STAGE_KEYS.length - 1)) * 100);

  return (
    <div className="workflow-stepper-container">
      {/* Full step row — hidden below the mobile breakpoint in favour
          of the compact form beneath. */}
      <div className="workflow-stepper-row">
        {STAGE_KEYS.map((stageKey, idx) => {
          const isCompleted = idx < currentStage;
          const isActive = idx === currentStage;
          const isPending = idx > currentStage;

          return (
            <React.Fragment key={stageKey}>
              <div className={`workflow-step${isPending ? ' is-pending' : ''}`}>
                <div
                  className={
                    'workflow-step-badge' +
                    (isCompleted ? ' is-completed' : '') +
                    (isActive ? ' is-active' : '') +
                    (isActive && isGenerating ? ' is-pulsing' : '')
                  }
                >
                  {isCompleted ? '✓' : idx + 1}
                </div>
                <span
                  className={
                    'workflow-step-label' +
                    (isActive ? ' is-active' : '') +
                    (isCompleted ? ' is-completed' : '')
                  }
                >
                  {t(stageKey)}
                </span>
              </div>
              {idx < STAGE_KEYS.length - 1 && (
                <div className={`workflow-step-connector${isCompleted ? ' is-completed' : ''}`} />
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Compact mobile form: "Step N of 6 — Stage name" + thin bar. */}
      <div className="workflow-stepper-compact">
        <div className="workflow-stepper-compact-label">
          {t('draft_stage_compact_prefix')} {clampedStage + 1} {t('draft_stage_compact_of')} {STAGE_KEYS.length}
          {' — '}
          {t(STAGE_KEYS[clampedStage])}
        </div>
        <div className="workflow-stepper-compact-bar">
          <div className="workflow-stepper-compact-fill" style={{ width: `${progressPct}%` }} />
        </div>
      </div>
    </div>
  );
}
