import React, { useState, useEffect, useRef } from 'react';

// ─── Print-only CSS injected once into the document head ────────────────────
const PRINT_STYLE = `
@media print {
  body > * { display: none !important; }
  #gr-print-document { display: block !important; }
  #gr-print-document {
    position: fixed;
    top: 0; left: 0;
    width: 100%;
    height: auto;
    background: #fff;
    z-index: 99999;
    padding: 40px 60px;
    font-family: 'Times New Roman', Georgia, serif;
    font-size: 12pt;
    color: #000;
    line-height: 1.7;
  }
}
`;

function injectPrintStyle() {
  if (document.getElementById('gr-print-css')) return;
  const s = document.createElement('style');
  s.id = 'gr-print-css';
  s.textContent = PRINT_STYLE;
  document.head.appendChild(s);
}

// ─── Detects the language of the GR text ────────────────────────────────────
function detectLanguage(text = '') {
  const devanagariCount = (text.match(/[\u0900-\u097F]/g) || []).length;
  return devanagariCount > 20 ? 'mr' : 'en';
}

// ─── Parses the GR body into structured sections for display ────────────────
function parseGRSections(text = '', lang = 'en') {
  const lines = text.split('\n');
  const sections = [];
  let buffer = [];
  let currentType = 'body';

  const isHeader = (line) => {
    const t = line.trim();
    if (!t) return false;
    if (/महाराष्ट्र\s*शासन/i.test(t)) return true;
    if (/government\s+of\s+maharashtra/i.test(t)) return true;
    if (/विभाग/i.test(t) && t.length < 80) return true;
    if (/department/i.test(t) && t.length < 80) return true;
    if (/शासन\s*परिपत्रक\s*क्रमांक/i.test(t)) return true;
    if (/government\s+(resolution|circular)\s+no/i.test(t)) return true;
    if (/क्रमांक\s*:/i.test(t)) return true;
    if (/हुतात्मा|मादाम\s*कामा|मंत्रालय\s*मुंबई/i.test(t)) return true;
    if (/mantralaya|hutatma\s+rajguru/i.test(t)) return true;
    if (/दिनांक\s*:|dated?\s*:/i.test(t)) return true;
    return false;
  };

  const isReadSection = (line) =>
    /^\s*वाचा\s*:/i.test(line) || /^\s*read\s*:/i.test(line);
  const isPreambleSection = (line) =>
    /^\s*शासन\s*परिपत्रक\s*:/i.test(line) ||
    /^\s*शासन\s*निर्णय\s*:/i.test(line) ||
    /^\s*government\s+resolution\s*:/i.test(line);
  const isClosing = (line) =>
    /महाराष्ट्राचे\s+राज्यपाल/i.test(line) ||
    /by\s+order\s+and\s+in\s+the\s+name\s+of\s+the\s+governor/i.test(line);
  const isDistribution = (line) =>
    /^\s*प्रत\s*[,:]/.test(line) || /^\s*copy\s+to\s*[,:]/i.test(line);

  const flush = (type) => {
    if (buffer.length > 0) {
      sections.push({ type: currentType, lines: [...buffer] });
      buffer = [];
    }
    currentType = type;
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (isHeader(line)) {
      if (currentType !== 'header') flush('header');
      buffer.push(line);
    } else if (isReadSection(line)) {
      flush('read');
      buffer.push(line);
    } else if (isPreambleSection(line)) {
      flush('preamble');
      buffer.push(line);
    } else if (isClosing(line)) {
      flush('closing');
      buffer.push(line);
    } else if (isDistribution(line)) {
      flush('distribution');
      buffer.push(line);
    } else {
      if (currentType === 'header' && line.trim() !== '') {
        // If we're past the header section markers, switch to body
        if (!isHeader(line)) {
          flush('body');
        }
      }
      buffer.push(line);
    }
  }
  if (buffer.length > 0) {
    sections.push({ type: currentType, lines: buffer });
  }

  return sections;
}

// ─── Renders the parsed sections as an official-looking document ─────────────
function OfficialDocumentView({ text }) {
  const lang = detectLanguage(text);
  const sections = parseGRSections(text, lang);

  return (
    <div style={{
      fontFamily: "'Times New Roman', Georgia, 'Noto Serif Devanagari', serif",
      fontSize: '14px',
      lineHeight: 1.8,
      color: '#1a1a1a',
      position: 'relative',
    }}>
      {/* Subtle DRAFT watermark */}
      <div style={{
        position: 'absolute',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%) rotate(-35deg)',
        fontSize: '80px',
        fontWeight: 900,
        color: 'rgba(0,0,0,0.04)',
        letterSpacing: '8px',
        pointerEvents: 'none',
        userSelect: 'none',
        fontFamily: 'Georgia, serif',
        whiteSpace: 'nowrap',
        zIndex: 0,
      }}>
        DRAFT
      </div>

      <div style={{ position: 'relative', zIndex: 1 }}>
        {sections.map((section, idx) => {
          if (section.type === 'header') {
            return (
              <div key={idx} style={{ textAlign: 'center', marginBottom: '20px' }}>
                {section.lines.map((line, li) => {
                  const t = line.trim();
                  if (!t) return <div key={li} style={{ height: '6px' }} />;

                  const isMahShasan = /महाराष्ट्र\s*शासन/i.test(t) || /government\s+of\s+maharashtra/i.test(t);
                  const isDept = (/विभाग/i.test(t) || /department/i.test(t)) && t.length < 100;
                  const isGRNum = /क्रमांक|GR\s*No|Resolution\s+No/i.test(t);
                  const isAddr = /हुतात्मा|मादाम|मंत्रालय\s*मुंबई|mantralaya|hutatma/i.test(t);
                  const isDate = /दिनांक|dated?/i.test(t);

                  if (isMahShasan) return (
                    <div key={li} style={{ fontSize: '16px', fontWeight: 'bold', letterSpacing: '0.5px', textTransform: 'uppercase' }}>
                      {t}
                    </div>
                  );
                  if (isDept) return (
                    <div key={li} style={{ fontSize: '14px', fontWeight: 'bold', marginTop: '2px' }}>
                      {t}
                    </div>
                  );
                  if (isGRNum) return (
                    <div key={li} style={{ fontSize: '13px', marginTop: '6px', color: '#333' }}>
                      {t}
                    </div>
                  );
                  if (isAddr) return (
                    <div key={li} style={{ fontSize: '12px', color: '#555', marginTop: '4px' }}>
                      {t}
                    </div>
                  );
                  if (isDate) return (
                    <div key={li} style={{ fontSize: '13px', marginTop: '4px', fontWeight: '600' }}>
                      {t}
                    </div>
                  );
                  return <div key={li} style={{ fontSize: '13px' }}>{t}</div>;
                })}
                {/* Horizontal rule after header block */}
                <div style={{ borderBottom: '2px double #333', marginTop: '16px', marginBottom: '4px' }} />
              </div>
            );
          }

          if (section.type === 'read') {
            return (
              <div key={idx} style={{ marginBottom: '16px' }}>
                {section.lines.map((line, li) => {
                  const t = line.trim();
                  if (!t) return <div key={li} style={{ height: '4px' }} />;
                  const isHeading = /^\s*(वाचा|read)\s*:/i.test(line);
                  if (isHeading) return (
                    <div key={li} style={{ fontWeight: 'bold', textDecoration: 'underline', marginBottom: '6px' }}>
                      {t}
                    </div>
                  );
                  return (
                    <div key={li} style={{ paddingLeft: '24px', textAlign: 'left' }}>
                      {t}
                    </div>
                  );
                })}
              </div>
            );
          }

          if (section.type === 'preamble') {
            return (
              <div key={idx} style={{ marginBottom: '16px' }}>
                {section.lines.map((line, li) => {
                  const t = line.trim();
                  if (!t) return <div key={li} style={{ height: '8px' }} />;
                  const isHeading = /^\s*(शासन\s*परिपत्रक|शासन\s*निर्णय|government\s+resolution)\s*:/i.test(line);
                  if (isHeading) return (
                    <div key={li} style={{ fontWeight: 'bold', textDecoration: 'underline', marginBottom: '8px' }}>
                      {t}
                    </div>
                  );
                  return (
                    <p key={li} style={{ margin: '0 0 8px 0', textAlign: 'justify', textIndent: '2em' }}>
                      {t}
                    </p>
                  );
                })}
              </div>
            );
          }

          if (section.type === 'closing') {
            return (
              <div key={idx} style={{ marginTop: '24px', marginBottom: '16px' }}>
                {section.lines.map((line, li) => {
                  const t = line.trim();
                  if (!t) return <div key={li} style={{ height: '6px' }} />;
                  return <div key={li} style={{ fontStyle: 'normal' }}>{t}</div>;
                })}
              </div>
            );
          }

          if (section.type === 'distribution') {
            return (
              <div key={idx} style={{ marginTop: '24px', borderTop: '1px solid #ccc', paddingTop: '12px' }}>
                {section.lines.map((line, li) => {
                  const t = line.trim();
                  if (!t) return <div key={li} style={{ height: '4px' }} />;
                  const isHeading = /^\s*(प्रत|copy\s+to)\s*[,:]/i.test(line);
                  if (isHeading) return (
                    <div key={li} style={{ fontWeight: 'bold', marginBottom: '4px' }}>{t}</div>
                  );
                  return <div key={li} style={{ paddingLeft: '24px' }}>{t}</div>;
                })}
              </div>
            );
          }

          // Default body section
          return (
            <div key={idx} style={{ marginBottom: '12px' }}>
              {section.lines.map((line, li) => {
                const t = line.trim();
                if (!t) return <div key={li} style={{ height: '8px' }} />;

                // Operative clause (starts with 0X. or X.) — bold number
                const clauseMatch = t.match(/^(0?[0-9]+|[०-९]+)[.)]\s+(.*)/);
                if (clauseMatch) {
                  return (
                    <div key={li} style={{ display: 'flex', gap: '8px', marginBottom: '8px', paddingLeft: '8px' }}>
                      <span style={{ fontWeight: 'bold', minWidth: '28px', flexShrink: 0 }}>
                        {clauseMatch[1]}.
                      </span>
                      <span style={{ textAlign: 'justify' }}>{clauseMatch[2]}</span>
                    </div>
                  );
                }

                return (
                  <p key={li} style={{ margin: '0 0 6px 0', textAlign: 'justify', textIndent: '1.5em' }}>
                    {t}
                  </p>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Main DraftViewer component ───────────────────────────────────────────────
export default function DraftViewer({ draft, loading, onTextChange }) {
  const [copied, setCopied] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editedText, setEditedText] = useState('');
  const textareaRef = useRef(null);

  // Inject print CSS once
  useEffect(() => { injectPrintStyle(); }, []);

  // Sync editedText whenever a new draft arrives
  useEffect(() => {
    if (draft?.body_text) {
      setEditedText(draft.body_text);
      setIsEditing(false);
    }
  }, [draft?.body_text]);

  // Auto-resize textarea
  useEffect(() => {
    if (isEditing && textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
      textareaRef.current.focus();
    }
  }, [isEditing]);

  const handleTextChange = (e) => {
    setEditedText(e.target.value);
    // Auto-resize
    e.target.style.height = 'auto';
    e.target.style.height = e.target.scrollHeight + 'px';
    // Notify parent
    if (onTextChange) onTextChange(e.target.value);
  };

  const handleToggleEdit = () => {
    if (isEditing) {
      // Switching to view mode — notify parent of final text
      if (onTextChange) onTextChange(editedText);
    }
    setIsEditing((prev) => !prev);
  };

  const displayText = editedText || draft?.body_text || '';

  const handleCopy = () => {
    if (!displayText) return;
    navigator.clipboard.writeText(displayText).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const handleDownloadTxt = () => {
    if (!displayText) return;
    const blob = new Blob([displayText], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `GR_Draft_${draft?.gr_id || draft?.draft_id || 'NIRN'}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handlePrint = () => {
    if (!displayText) return;
    const lang = detectLanguage(displayText);
    const printWin = window.open('', '_blank');
    printWin.document.write(`
      <html>
        <head>
          <title>${draft?.title || 'Government Resolution'}</title>
          <style>
            @import url('https://fonts.googleapis.com/css2?family=Noto+Serif+Devanagari:wght@400;700&display=swap');
            body {
              font-family: 'Noto Serif Devanagari', 'Times New Roman', Georgia, serif;
              padding: 60px 70px;
              line-height: 1.8;
              color: #000;
              font-size: 12pt;
            }
            .gr-header { text-align: center; margin-bottom: 24px; }
            .gr-title { font-size: 16pt; font-weight: bold; text-transform: uppercase; }
            .gr-dept { font-size: 13pt; font-weight: bold; margin: 4px 0; }
            .gr-grnum { font-size: 11pt; margin-top: 6px; }
            .gr-addr { font-size: 10pt; color: #444; margin-top: 4px; }
            .gr-date { font-size: 11pt; font-weight: 600; margin-top: 4px; }
            hr.header-rule { border: none; border-bottom: 2px double #000; margin: 16px 0 8px; }
            .section-heading { font-weight: bold; text-decoration: underline; margin-bottom: 8px; }
            .gr-body { white-space: pre-wrap; text-align: justify; }
            .clause { display: flex; gap: 8px; margin-bottom: 8px; }
            .clause-num { font-weight: bold; min-width: 30px; }
            .closing { margin-top: 24px; }
            .distribution { margin-top: 24px; padding-top: 12px; border-top: 1px solid #ccc; }
          </style>
        </head>
        <body>
          <div class="gr-body">${displayText.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</div>
        </body>
      </html>
    `);
    printWin.document.close();
    printWin.focus();
    setTimeout(() => { printWin.print(); }, 600);
  };

  // ── Loading state ──────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div style={{
        background: '#fff',
        border: '1px solid #d1d5db',
        borderRadius: '4px',
        padding: '60px 20px',
        boxShadow: '0 2px 12px rgba(0,0,0,0.08), 0 8px 32px rgba(0,0,0,0.04)',
        textAlign: 'center',
        minHeight: '500px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        <div className="big"><span className="spinner" /></div>
        <h4 style={{ marginTop: '20px', fontSize: '18px', fontFamily: 'Georgia, serif' }}>
          Drafting Government Resolution...
        </h4>
        <p style={{ color: '#666', fontSize: '14px', maxWidth: '400px' }}>
          Synthesizing retrieved GR templates, enforcing legal formatting, and performing conflict verification.
        </p>
      </div>
    );
  }

  // ── Empty state ────────────────────────────────────────────────────────────
  if (!draft || !draft.body_text) {
    return (
      <div style={{
        background: '#fff',
        border: '2px dashed #9ca3af',
        borderRadius: '4px',
        padding: '60px 20px',
        textAlign: 'center',
        minHeight: '500px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#6b7280',
      }}>
        <div style={{ fontSize: '48px', marginBottom: '16px' }}>📜</div>
        <h3 style={{ margin: '0 0 8px 0', fontSize: '18px', color: 'var(--ink)', fontFamily: 'Georgia, serif' }}>
          Your generated Government Resolution will appear here.
        </h3>
        <p style={{ margin: 0, fontSize: '14px', maxWidth: '420px' }}>
          Fill in the brief description on the left and click <strong>Generate Draft GR</strong> to begin the AI-assisted drafting workflow.
        </p>
      </div>
    );
  }

  // ── Main document view ─────────────────────────────────────────────────────
  return (
    <div style={{
      background: '#fff',
      border: '1px solid #d1d5db',
      borderRadius: '4px',
      boxShadow: '0 2px 12px rgba(0,0,0,0.10), 0 8px 32px rgba(0,0,0,0.05)',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      // Simulate paper with subtle inner shadow
      backgroundImage: 'linear-gradient(to bottom, #fafafa 0%, #fff 20px)',
    }}>
      {/* ── Toolbar ─────────────────────────────────────────────────────────── */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '10px 16px',
        background: '#f8f9fa',
        borderBottom: '1px solid #e5e7eb',
        flexWrap: 'wrap',
        gap: '8px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{
            fontSize: '11px',
            fontWeight: 'bold',
            background: '#1e40af',
            color: '#fff',
            padding: '2px 8px',
            borderRadius: '3px',
            letterSpacing: '0.5px',
          }}>
            OFFICIAL DRAFT
          </span>
          <span style={{ fontSize: '12px', color: '#6b7280' }}>
            {draft.department?.replace(/_/g, ' ') || 'Government of Maharashtra'}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
          {/* Edit/Done toggle */}
          <button
            id="gr-edit-toggle"
            type="button"
            onClick={handleToggleEdit}
            style={{
              padding: '5px 12px',
              fontSize: '12px',
              fontWeight: '600',
              background: isEditing ? '#059669' : '#fff',
              color: isEditing ? '#fff' : '#374151',
              border: `1px solid ${isEditing ? '#059669' : '#d1d5db'}`,
              borderRadius: '4px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              transition: 'all 0.15s',
            }}
          >
            {isEditing ? '✓ Done Editing' : '✏️ Edit'}
          </button>
          <button
            type="button"
            onClick={handleCopy}
            style={{
              padding: '5px 10px',
              fontSize: '12px',
              fontWeight: '600',
              background: '#fff',
              color: '#374151',
              border: '1px solid #d1d5db',
              borderRadius: '4px',
              cursor: 'pointer',
            }}
          >
            {copied ? '✓ Copied' : '📋 Copy'}
          </button>
          <button
            type="button"
            onClick={handleDownloadTxt}
            style={{
              padding: '5px 10px',
              fontSize: '12px',
              fontWeight: '600',
              background: '#fff',
              color: '#374151',
              border: '1px solid #d1d5db',
              borderRadius: '4px',
              cursor: 'pointer',
            }}
          >
            ⬇ .txt
          </button>
          <button
            type="button"
            onClick={handlePrint}
            style={{
              padding: '5px 10px',
              fontSize: '12px',
              fontWeight: '600',
              background: '#dc2626',
              color: '#fff',
              border: '1px solid #dc2626',
              borderRadius: '4px',
              cursor: 'pointer',
            }}
          >
            🖨️ Print
          </button>
        </div>
      </div>

      {/* ── Edit hint banner (shown when not editing) ────────────────────── */}
      {!isEditing && (
        <div
          onClick={handleToggleEdit}
          style={{
            padding: '5px 16px',
            background: '#fffbeb',
            borderBottom: '1px solid #fcd34d',
            fontSize: '12px',
            color: '#92400e',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            userSelect: 'none',
          }}
        >
          ✏️ <span>Click to edit this document — any changes will be used in re-analysis.</span>
        </div>
      )}

      {/* ── Document content area ────────────────────────────────────────── */}
      <div
        id="gr-print-document"
        style={{
          padding: '40px 48px',
          maxHeight: '720px',
          overflowY: 'auto',
          background: '#fff',
          // Subtle page-edge shadow on the sides
          boxShadow: 'inset 6px 0 12px -6px rgba(0,0,0,0.04), inset -6px 0 12px -6px rgba(0,0,0,0.04)',
        }}
      >
        {isEditing ? (
          /* ── Editable textarea ──────────────────────────────────────────── */
          <div style={{ position: 'relative' }}>
            <div style={{
              position: 'absolute',
              top: '-28px',
              left: 0,
              fontSize: '11px',
              color: '#059669',
              fontWeight: '600',
              letterSpacing: '0.3px',
            }}>
              ✏️ EDITING MODE — changes are tracked
            </div>
            <textarea
              ref={textareaRef}
              value={editedText}
              onChange={handleTextChange}
              spellCheck={false}
              style={{
                width: '100%',
                minHeight: '600px',
                fontFamily: "'Courier New', 'Courier', 'Noto Sans Mono', monospace",
                fontSize: '13px',
                lineHeight: 1.8,
                color: '#1a1a1a',
                border: '2px dashed #059669',
                borderRadius: '4px',
                padding: '16px',
                resize: 'vertical',
                outline: 'none',
                background: '#f0fdf4',
                boxSizing: 'border-box',
                whiteSpace: 'pre',
                overflowX: 'auto',
              }}
            />
          </div>
        ) : (
          /* ── Official document view ─────────────────────────────────────── */
          <OfficialDocumentView text={displayText} />
        )}
      </div>

      {/* ── Edit mode footer ─────────────────────────────────────────────── */}
      {isEditing && (
        <div style={{
          padding: '10px 16px',
          background: '#f0fdf4',
          borderTop: '1px solid #86efac',
          fontSize: '12px',
          color: '#166534',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <span>
            {editedText.split('\n').length} lines · {editedText.length} characters
          </span>
          <button
            type="button"
            onClick={handleToggleEdit}
            style={{
              padding: '4px 14px',
              fontSize: '12px',
              fontWeight: '700',
              background: '#059669',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
            }}
          >
            ✓ Done Editing
          </button>
        </div>
      )}
    </div>
  );
}
