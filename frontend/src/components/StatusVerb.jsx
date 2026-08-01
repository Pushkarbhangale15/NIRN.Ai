import { useEffect, useState } from 'react';
import { useLanguage } from '../LanguageContext.jsx';

const STAGE_VERB_KEYS = {
  retrieval: [
    'status_verb_searching_corpus',
    'status_verb_retrieving_precedents',
    'status_verb_scanning_records',
  ],
  drafting: [
    'status_verb_thinking',
    'status_verb_drafting',
    'status_verb_composing',
  ],
  validation: [
    'status_verb_validating',
    'status_verb_checking_compliance',
  ],
  conflict: [
    'status_verb_contemplating',
    'status_verb_cross_referencing',
  ],
  references: [
    'status_verb_extracting_references',
  ],
  extracting: [
    'status_verb_reading_document',
    'status_verb_extracting_text',
    'status_verb_recognising_script',
  ],
};

const CYCLE_MS = 2500;
const FADE_MS = 200;
const DOT_MS = 500;

export default function StatusVerb({ stage = 'drafting', className = '' }) {
  const { t } = useLanguage();
  const verbKeys = STAGE_VERB_KEYS[stage] || STAGE_VERB_KEYS.drafting;
  const [index, setIndex] = useState(0);
  const [visible, setVisible] = useState(true);
  const [dotCount, setDotCount] = useState(1);

  useEffect(() => {
    setIndex(0);
    setVisible(true);
  }, [stage]);

  useEffect(() => {
    const cycle = setInterval(() => {
      setVisible(false);
      setTimeout(() => {
        setIndex((prev) => (prev + 1) % verbKeys.length);
        setVisible(true);
      }, FADE_MS);
    }, CYCLE_MS);
    return () => clearInterval(cycle);
  }, [verbKeys.length]);

  useEffect(() => {
    const dots = setInterval(() => {
      setDotCount((prev) => (prev % 3) + 1);
    }, DOT_MS);
    return () => clearInterval(dots);
  }, []);

  const verb = t(verbKeys[index] || verbKeys[0]);
  const ellipsis = '.'.repeat(dotCount);

  return (
    <span className={`status-verb ${className}`}>
      <span className="status-verb-text" style={{ opacity: visible ? 1 : 0 }}>
        {verb}
      </span>
      <span className="status-verb-dots">{ellipsis}</span>
    </span>
  );
}
