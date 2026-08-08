import React, { useState } from 'react';
import { useLanguage } from '../../LanguageContext.jsx';
import { api } from '../../api.js';

const IconLink = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
    <path d="M3.9 12a5 5 0 0 1 5-5H13v2H8.9a3 3 0 0 0 0 6H13v2H8.9a5 5 0 0 1-5-5Zm7.1 1h2v-2h-2v-2H8.9a5 5 0 0 0 0 10H11v-2h-2.1a3 3 0 0 1 0-6H11Zm4.1-6H15v2h4.1a3 3 0 0 1 0 6H15v2h4.1a5 5 0 0 0 0-10Z" />
  </svg>
);

export default function ReferencesCard({ references = [], loading, hasGenerated }) {
  const { t, siteLanguage } = useLanguage();
  const isMr = siteLanguage === 'mr';
  const [isOpen, setIsOpen] = useState(true);
  const [expandedIndex, setExpandedIndex] = useState(0);
  const [downloadingIndex, setDownloadingIndex] = useState(null);

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
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', fontWeight: 'bold', fontSize: isMr ? '17px' : '15px', color: '#4b5563' }}>
            <IconLink /> Card 3 — References Used
          </span>
          <span style={{ fontSize: isMr ? '16px' : '14px', fontWeight: 700, background: '#374151', color: '#fff', padding: '4px 12px', borderRadius: '6px' }}>
            {t('draft_pending')}
          </span>
        </div>
      </div>
    );
  }

  // Downloads the corpus OCR text for a resolved reference. Only works for the
  // freshly-generated draft still held in this session — corpus_gr_id/corpus_title
  // are not yet persisted to the database, so this breaks after reopening from History.
  const handleDownload = async (ref, idx) => {
    if (!ref.corpus_gr_id || downloadingIndex !== null) return;
    setDownloadingIndex(idx);
    try {
      const res = await api.getCorpusOcr(ref.corpus_gr_id);
      const text = res?.text || '';
      const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${ref.corpus_gr_id}.txt`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Reference download error:', err);
    } finally {
      setDownloadingIndex(null);
    }
  };

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
          background: '#eff6ff',
          borderBottom: isOpen ? '2px solid var(--ink)' : 'none',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          cursor: 'pointer'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', fontWeight: 'bold', fontSize: isMr ? '17px' : '15px', color: 'var(--ink)' }}>
            <IconLink /> Card 3 — References Used
          </span>
          <span style={{
            fontSize: '11px',
            fontWeight: 'bold',
            background: 'var(--blue)',
            color: '#fff',
            padding: '2px 8px',
            borderRadius: '12px',
            border: '1px solid var(--ink)'
          }}>
            {references.length} Citation{references.length === 1 ? '' : 's'}
          </span>
        </div>
        <span style={{ fontSize: '16px', fontWeight: 'bold' }}>{isOpen ? '▲' : '▼'}</span>
      </div>

      {/* Content */}
      {isOpen && (
        <div style={{ padding: '20px' }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '20px' }}>
              <span className="spinner" /> <span style={{ fontSize: '14px' }}>Resolving GR citations...</span>
            </div>
          ) : references.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '20px', color: '#6b7280', fontSize: '14px' }}>
              No citations detected in this draft.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {references.map((ref, idx) => {
                const isExpanded = expandedIndex === idx;

                return (
                  <div
                    key={idx}
                    style={{
                      border: '1px solid var(--ink)',
                      borderRadius: '8px',
                      background: '#fff',
                      overflow: 'hidden',
                      boxShadow: '0 2px 0 var(--ink)'
                    }}
                  >
                    <div
                      onClick={() => setExpandedIndex(isExpanded ? null : idx)}
                      style={{
                        padding: '12px 14px',
                        background: isExpanded ? '#f3f4f6' : '#fff',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        cursor: 'pointer',
                        gap: '10px'
                      }}
                    >
                      <div>
                        <div style={{ fontSize: '15px', fontWeight: 'bold' }}>
                          {ref.raw_text}
                        </div>
                        {ref.found_in_corpus ? (
                          <div style={{ fontSize: '13.5px', color: '#6b7280' }}>
                            {ref.corpus_title || 'Matched GR'} {ref.corpus_gr_id ? `· ${ref.corpus_gr_id}` : ''}
                          </div>
                        ) : (
                          <div style={{ fontSize: '13.5px', color: '#b91c1c' }}>
                            Not found in corpus
                          </div>
                        )}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                        <span style={{
                          fontSize: '13px',
                          fontWeight: 'bold',
                          color: ref.found_in_corpus ? 'var(--blue)' : '#b91c1c',
                          background: ref.found_in_corpus ? '#dbeafe' : '#fee2e2',
                          padding: '3px 8px',
                          borderRadius: '4px'
                        }}>
                          {ref.found_in_corpus ? 'Resolved' : 'Unresolved'}
                        </span>
                        <span style={{ fontSize: '14px', fontWeight: 'bold' }}>{isExpanded ? '−' : '+'}</span>
                      </div>
                    </div>

                    {isExpanded && (
                      <div style={{ padding: '16px', borderTop: '1px solid #e5e7eb', background: '#fafafa', fontSize: '15px', lineHeight: '1.5' }}>
                        <div style={{ marginBottom: '8px', color: '#374151' }}>
                          <strong>Cited text:</strong> "{ref.raw_text}"
                        </div>
                        {ref.gr_number && (
                          <div style={{ marginBottom: '8px', color: '#374151', fontSize: '13.5px' }}>
                            <strong>GR number:</strong> {ref.gr_number}{ref.year ? ` (${ref.year})` : ''}
                          </div>
                        )}
                        {ref.found_in_corpus ? (
                          <button
                            type="button"
                            onClick={() => handleDownload(ref, idx)}
                            disabled={downloadingIndex === idx}
                            style={{
                              fontSize: '13px',
                              fontWeight: 'bold',
                              color: '#fff',
                              background: 'var(--blue)',
                              border: '1px solid var(--ink)',
                              borderRadius: '4px',
                              padding: '6px 12px',
                              cursor: downloadingIndex === idx ? 'default' : 'pointer',
                              opacity: downloadingIndex === idx ? 0.6 : 1
                            }}
                          >
                            {downloadingIndex === idx ? 'Downloading…' : 'Download source text'}
                          </button>
                        ) : (
                          <div style={{ fontSize: '14px', color: '#1f2937', background: '#f3f4f6', padding: '8px 10px', borderRadius: '4px' }}>
                            This citation could not be matched to a GR in the corpus.
                          </div>
                        )}
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
