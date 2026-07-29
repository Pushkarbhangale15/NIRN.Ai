import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useLanguage } from '../../LanguageContext.jsx';
import StatusVerb from '../StatusVerb.jsx';

const IconCopy = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 24 24">
    <path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>
  </svg>
);
const IconCheck = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 24 24">
    <path d="M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
  </svg>
);
const IconDownload = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 24 24">
    <path d="M5 20h14v-2H5v2zM19 9h-4V3H9v6H5l7 7 7-7z"/>
  </svg>
);
const IconPdf = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 24 24">
    <path d="M6 2c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm7 7V3.5L18.5 9zM8 12h2a2 2 0 0 1 2 2v1a2 2 0 0 1-2 2H9v2H8zm2 1H9v2h1a1 1 0 0 0 1-1 1 1 0 0 0-1-1z"/>
  </svg>
);
const IconDocument = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" fill="currentColor" viewBox="0 0 24 24">
    <path d="M6 2c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm7 7V3.5L18.5 9zM8 13h8v2H8zm0 4h8v2H8zm0-8h5v2H8z"/>
  </svg>
);

export default function DraftViewer({
  draft,
  loading
}) {
  const { t } = useLanguage();
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (!draft || !draft.body_text) return;
    navigator.clipboard.writeText(draft.body_text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const handleDownloadTxt = () => {
    if (!draft || !draft.body_text) return;
    const blob = new Blob([draft.body_text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `GR_Draft_${draft.gr_id || 'NIRN'}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDownloadPdf = () => {
    if (!draft || !draft.body_text) return;
    // Simple window print fallback formatted for official GR export
    const printWin = window.open('', '_blank');
    printWin.document.write(`
      <html>
        <head>
          <title>${draft.title || 'Government Resolution'}</title>
          <style>
            body { font-family: 'Times New Roman', serif; padding: 40px; line-height: 1.6; }
            h1 { text-align: center; font-size: 18pt; text-decoration: underline; margin-bottom: 20px; }
            .dept { text-align: center; font-weight: bold; font-size: 14pt; margin-bottom: 30px; }
            .content { font-size: 12pt; white-space: pre-wrap; }
          </style>
        </head>
        <body>
          <div class="dept">GOVERNMENT OF MAHARASHTRA<br/>${(draft.department || 'Higher and Technical Education Department').toUpperCase()}</div>
          <h1>GOVERNMENT RESOLUTION</h1>
          <div class="content">${draft.body_text}</div>
        </body>
      </html>
    `);
    printWin.document.close();
    printWin.focus();
    setTimeout(() => { printWin.print(); }, 500);
  };

  if (loading) {
    return (
      <div style={{
        background: 'var(--paper)',
        border: '2px solid var(--ink)',
        borderRadius: '12px',
        padding: '60px 20px',
        boxShadow: '0 4px 0 var(--ink)',
        textAlign: 'center',
        minHeight: '500px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center'
      }}>
        <div className="big"><span className="spinner" /></div>

        <div style={{ marginTop: '20px' }}>
          <h3>{t('draft_loading_generating')}</h3>
        </div>

        <div style={{ marginTop: '10px' }}>
          <p style={{ color: '#666', fontSize: '16px', maxWidth: '440px' }}>
            <StatusVerb stage="drafting" />
          </p>
        </div>
      </div>
    );
  }

  if (!draft || !draft.body_text) {
    return (
      <div style={{
        background: 'var(--paper)',
        border: '2px dashed #9ca3af',
        borderRadius: '12px',
        padding: '60px 20px',
        textAlign: 'center',
        minHeight: '500px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#6b7280'
      }}>
        <div style={{ marginBottom: '16px', color: 'var(--ink-soft)' }}><IconDocument /></div>
        <h3 style={{ margin: '0 0 8px 0' }}>
          {t('draft_viewer_empty_title')}
        </h3>
        <p style={{ margin: 0, fontSize: '14px', maxWidth: '420px' }}>
          {t('draft_viewer_empty_desc')}
        </p>
      </div>
    );
  }

  return (
    <div style={{
      background: 'var(--paper)',
      border: '2px solid var(--ink)',
      borderRadius: '12px',
      boxShadow: '0 4px 0 var(--ink)',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden'
    }}>
      {/* Toolbar Above Document */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '12px 20px',
        background: '#f3f4f6',
        borderBottom: '2px solid var(--ink)',
        flexWrap: 'wrap',
        gap: '10px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{
            fontSize: '12px',
            fontWeight: 'bold',
            background: 'var(--blue)',
            color: '#fff',
            padding: '3px 8px',
            borderRadius: '4px'
          }}>
            {t('draft_official')}
          </span>
          <span style={{ fontSize: '13px', fontWeight: 'bold', color: 'var(--ink)' }}>
            {draft.department || 'Government of Maharashtra'}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            type="button"
            onClick={handleCopy}
            className="btn btn-sm btn-secondary"
          >
            {copied ? <><IconCheck /> {t('draft_copied')}</> : <><IconCopy /> {t('draft_copy')}</>}
          </button>
          <button
            type="button"
            onClick={handleDownloadTxt}
            className="btn btn-sm btn-secondary"
          >
            <IconDownload /> {t('draft_download_txt')}
          </button>
          <button
            type="button"
            onClick={handleDownloadPdf}
            className="btn btn-sm btn-red"
          >
            <IconPdf /> {t('draft_download_pdf')}
          </button>
        </div>
      </div>

      {/* Official Government Resolution Scrollable Viewer */}
      <div style={{
        padding: '32px 40px',
        maxHeight: '680px',
        overflowY: 'auto',
        background: '#fff',
        fontFamily: "'Georgia', 'Times New Roman', serif",
        color: '#111827',
        lineHeight: 1.7
      }}>
        {/* GR Header Header */}
        <div style={{ textAlign: 'center', marginBottom: '24px', borderBottom: '2px double #111827', paddingBottom: '16px' }}>
          <div style={{ fontSize: '13px', fontWeight: 'bold', letterSpacing: '1px', color: '#4b5563', textTransform: 'uppercase' }}>
            Government of Maharashtra
          </div>
          <div style={{ fontSize: '15px', fontWeight: 'bold', margin: '4px 0', textTransform: 'uppercase' }}>
            {draft.department || 'Higher and Technical Education Department'}
          </div>
          <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '4px' }}>
            Mantralaya, Mumbai - 400 032 | Resolution No: {draft.gr_id || 'NIRN/2026/DRAFT-01'}
          </div>
        </div>

        {/* GR Body Content */}
        <div style={{ whiteSpace: 'pre-wrap', fontSize: '17px', textAlign: 'justify', lineHeight: 1.8 }}>
          {draft.body_text}
        </div>
      </div>
    </div>
  );
}
