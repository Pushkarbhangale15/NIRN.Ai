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
  const totalSteps = STAGE_KEYS.length;
  const clampedStage = Math.min(Math.max(currentStage, 0), totalSteps - 1);
  const progressPct = ((clampedStage + 1) / totalSteps) * 100;

  return (
    <div className="workflow-stepper-container">
      {/* Desktop / tablet: full stepper with circles + connectors */}
      <div className="workflow-stepper-desktop">
        {STAGE_KEYS.map((stageKey, idx) => {
          const isCompleted = idx < currentStage;
          const isActive = idx === currentStage;
          const isPending = idx > currentStage;

          let circleClass = "workflow-step-circle";
          if (isCompleted) circleClass += " workflow-step-circle--completed";
          else if (isActive) circleClass += isGenerating
            ? " workflow-step-circle--active-generating"
            : " workflow-step-circle--active";
          else circleClass += " workflow-step-circle--pending";

          let labelClass = "workflow-step-label";
          if (isActive) labelClass += " workflow-step-label--active";
          else if (isCompleted) labelClass += " workflow-step-label--completed";

          return (
            <React.Fragment key={stageKey}>
              <div className={`workflow-step${isPending ? ' workflow-step--pending' : ''}`}>
                <div className={circleClass}>
                  {isCompleted ? '✓' : idx + 1}
                </div>
                <span className={labelClass}>{t(stageKey)}</span>
              </div>
              {idx < STAGE_KEYS.length - 1 && (
                <div className={`workflow-step-connector${isCompleted ? ' workflow-step-connector--completed' : ''}`} />
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Mobile: compact "Step X of N — Label" with a thin progress bar */}
      <div className="workflow-stepper-mobile">
        <div className="workflow-stepper-mobile-label">
          {t('draft_stage_mobile_prefix')} {clampedStage + 1} {t('draft_stage_mobile_of')} {totalSteps} — {t(STAGE_KEYS[clampedStage])}
        </div>
        <div className="workflow-stepper-mobile-track">
          <div className="workflow-stepper-mobile-fill" style={{ width: `${progressPct}%` }} />
        </div>
      </div>
    </div>
  );
}
