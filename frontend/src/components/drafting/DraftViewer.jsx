import React, { useState } from 'react';
import { motion } from 'framer-motion';

export default function DraftViewer({
  draft,
  loading,
  onRegenerate
}) {
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
        <h4 style={{ marginTop: '20px', fontSize: '18px' }}>Drafting Government Resolution...</h4>
        <p style={{ color: '#666', fontSize: '14px', maxWidth: '400px' }}>
          Synthesizing retrieved GR templates, enforcing legal formatting, and performing conflict verification.
        </p>
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
        <div style={{ fontSize: '48px', marginBottom: '16px' }}>📜</div>
        <h3 style={{ margin: '0 0 8px 0', fontSize: '18px', color: 'var(--ink)' }}>
          Your generated Government Resolution will appear here.
        </h3>
        <p style={{ margin: 0, fontSize: '14px', maxWidth: '420px' }}>
          Fill in the brief description on the left and click <strong>Generate Draft GR</strong> to begin the AI-assisted drafting workflow.
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
            OFFICIAL DRAFT
          </span>
          <span style={{ fontSize: '13px', fontWeight: 'bold', color: 'var(--ink)' }}>
            {draft.department || 'Government of Maharashtra'}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            type="button"
            onClick={handleCopy}
            style={{
              padding: '6px 12px',
              fontSize: '12px',
              fontWeight: 'bold',
              background: '#fff',
              border: '1px solid var(--ink)',
              borderRadius: '6px',
              cursor: 'pointer'
            }}
          >
            {copied ? '✓ Copied' : '📋 Copy'}
          </button>
          <button
            type="button"
            onClick={handleDownloadTxt}
            style={{
              padding: '6px 12px',
              fontSize: '12px',
              fontWeight: 'bold',
              background: '#fff',
              border: '1px solid var(--ink)',
              borderRadius: '6px',
              cursor: 'pointer'
            }}
          >
            ⬇ .txt
          </button>
          <button
            type="button"
            onClick={handleDownloadPdf}
            style={{
              padding: '6px 12px',
              fontSize: '12px',
              fontWeight: 'bold',
              background: 'var(--red)',
              color: '#fff',
              border: '1px solid var(--ink)',
              borderRadius: '6px',
              cursor: 'pointer'
            }}
          >
            📄 PDF Print
          </button>

          {onRegenerate && (
            <button
              type="button"
              onClick={onRegenerate}
              style={{
                padding: '6px 12px',
                fontSize: '12px',
                fontWeight: 'bold',
                background: '#fff',
                border: '1px solid var(--ink)',
                borderRadius: '6px',
                cursor: 'pointer'
              }}
            >
              🔄 Regenerate
            </button>
          )}
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
