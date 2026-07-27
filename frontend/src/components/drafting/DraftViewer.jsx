import React, { useState, useEffect, useRef } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { Underline } from '@tiptap/extension-underline';
import { TextAlign } from '@tiptap/extension-text-align';
import { TextStyle } from '@tiptap/extension-text-style';
import { FontFamily } from '@tiptap/extension-font-family';
import { Color } from '@tiptap/extension-color';

// ─── Custom Font Size Extension ─────────────────────────────────────────────
const FontSize = TextStyle.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      fontSize: {
        default: null,
        parseHTML: element => element.style.fontSize,
        renderHTML: attributes => {
          if (!attributes.fontSize) return {};
          return { style: `font-size: ${attributes.fontSize}` };
        }
      }
    };
  }
});

// ─── Print-only CSS injected once into the document head ────────────────────
const PRINT_STYLE = `
@media print {
  body * {
    visibility: hidden;
  }
  #gr-print-root, #gr-print-root * {
    visibility: visible;
  }
  #gr-print-root {
    position: absolute;
    left: 0;
    top: 0;
    width: 100%;
    margin: 0;
    padding: 0;
    background: #fff;
    color: #000;
  }
  .print-footer-notice {
    display: block !important;
    position: fixed;
    bottom: 20px;
    left: 0;
    right: 0;
    text-align: center;
    font-size: 9pt;
    color: #555;
    border-top: 1px solid #ccc;
    padding-top: 8px;
    visibility: visible;
  }
  .print-footer-notice * {
    visibility: visible;
  }
  /* Hide Tiptap toolbar and save state indicator on print */
  .tiptap-toolbar-wrapper, .tiptap-save-badge, .edit-hint-banner {
    display: none !important;
  }
  .tiptap-editor-container {
    box-shadow: none !important;
    border: none !important;
    padding: 0 !important;
    margin: 0 !important;
    max-width: 100% !important;
  }
}
@media screen {
  .print-footer-notice {
    display: none;
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

// ─── Convert Plain Text GR to Semantic HTML ─────────────────────────────────
export function convertGRToHTML(plainText, language) {
  if (!plainText) return '';
  const lines = plainText.split('\n');
  let html = '';
  let inList = false;
  let listType = null; // 'ol' or 'ul'

  // States: 'header', 'read', 'preamble', 'body', 'closing', 'distribution'
  let state = 'header';

  const isReadHeader = (t) => /^\s*(वाचा|read)\s*:/i.test(t);
  const isPreambleHeader = (t) => /^\s*(शासन\s*परिपत्रक|शासन\s*निर्णय|government\s+resolution)\s*:/i.test(t);
  const isClosing = (t) => /महाराष्ट्राचे\s+राज्यपाल/i.test(t) || /by\s+order\s+and\s+in\s+the\s+name\s+of\s+the\s+governor/i.test(t);
  const isDistributionHeader = (t) => /^\s*(प्रत|copy\s+to)\s*[,:]/i.test(t);

  const closeList = () => {
    if (inList) {
      html += `</${listType}>`;
      inList = false;
      listType = null;
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed) {
      closeList();
      html += '<p></p>';
      continue;
    }

    // Identify headings and perform state transitions
    if (isReadHeader(trimmed)) {
      closeList();
      state = 'read';
      html += `<p><strong><u>${trimmed}</u></strong></p>`;
      continue;
    } else if (isPreambleHeader(trimmed)) {
      closeList();
      state = 'preamble';
      html += `<p><strong><u>${trimmed}</u></strong></p>`;
      continue;
    } else if (isClosing(trimmed)) {
      closeList();
      state = 'closing';
      html += `<p style="text-align: right"><strong>${trimmed}</strong></p>`;
      continue;
    } else if (isDistributionHeader(trimmed)) {
      closeList();
      state = 'distribution';
      html += `<p><strong><u>${trimmed}</u></strong></p>`;
      continue;
    }

    // Process line based on active state
    if (state === 'header') {
      html += `<p style="text-align: center"><strong>${trimmed}</strong></p>`;
    } else if (state === 'read') {
      const listMatch = trimmed.match(/^([०-९\d]+[.)]|\*|-)\s+(.*)/);
      if (listMatch) {
        if (!inList) {
          inList = true;
          listType = (listMatch[1] === '*' || listMatch[1] === '-') ? 'ul' : 'ol';
          const listStyle = listType === 'ol' ? (language === 'mr' ? 'style="list-style-type: devanagari"' : '') : '';
          html += `<${listType} ${listStyle}>`;
        }
        html += `<li>${listMatch[2]}</li>`;
      } else {
        closeList();
        html += `<p style="padding-left: 24px">${trimmed}</p>`;
      }
    } else if (state === 'preamble') {
      const clauseMatch = trimmed.match(/^([०-९\d]+[.)])\s+(.*)/);
      if (clauseMatch) {
        state = 'body';
        inList = true;
        listType = 'ol';
        const listStyle = language === 'mr' ? 'style="list-style-type: devanagari"' : '';
        html += `<ol ${listStyle}><li>${clauseMatch[2]}</li>`;
      } else {
        html += `<p style="text-indent: 2em; text-align: justify">${trimmed}</p>`;
      }
    } else if (state === 'body') {
      const clauseMatch = trimmed.match(/^([०-९\d]+[.)])\s+(.*)/);
      if (clauseMatch) {
        if (!inList) {
          inList = true;
          listType = 'ol';
          const listStyle = language === 'mr' ? 'style="list-style-type: devanagari"' : '';
          html += `<ol ${listStyle}>`;
        }
        html += `<li>${clauseMatch[2]}</li>`;
      } else {
        closeList();
        html += `<p style="text-align: justify">${trimmed}</p>`;
      }
    } else if (state === 'closing') {
      // Name & designation lines following closing statement
      html += `<p style="text-align: right">${trimmed}</p>`;
    } else if (state === 'distribution') {
      const listMatch = trimmed.match(/^([०-९\d]+[.)]|\*|-)\s+(.*)/);
      if (listMatch) {
        if (!inList) {
          inList = true;
          listType = (listMatch[1] === '*' || listMatch[1] === '-') ? 'ul' : 'ol';
          const listStyle = listType === 'ol' ? (language === 'mr' ? 'style="list-style-type: devanagari"' : '') : '';
          html += `<${listType} ${listStyle}>`;
        }
        html += `<li>${listMatch[2]}</li>`;
      } else {
        closeList();
        html += `<p style="padding-left: 24px">${trimmed}</p>`;
      }
    }
  }

  closeList();
  return html;
}

// ─── Convert HTML to Clean Plain Text GR ─────────────────────────────────────
export function convertHTMLToGRText(html, language) {
  if (!html) return '';
  const parser = new DOMParser();
  const doc = parser.parseFromString(html, 'text/html');
  const resultLines = [];

  const devanagariNumerals = ['०', '१', '२', '३', '४', '५', '६', '७', '८', '९'];
  const toDevanagari = (num) => {
    let s = num.toString();
    if (s.length < 2) s = '0' + s;
    return s.split('').map(d => devanagariNumerals[parseInt(d)] || d).join('');
  };

  const traverse = (node) => {
    if (node.nodeType === Node.ELEMENT_NODE) {
      const tag = node.tagName.toLowerCase();
      if (tag === 'p' || tag === 'h1' || tag === 'h2' || tag === 'h3') {
        const text = node.textContent.trim();
        resultLines.push(text);
      } else if (tag === 'ol') {
        const items = node.children;
        let count = 1;
        for (let i = 0; i < items.length; i++) {
          if (items[i].tagName.toLowerCase() === 'li') {
            const numStr = language === 'mr' ? toDevanagari(count) : count.toString().padStart(2, '0');
            resultLines.push(`${numStr}. ${items[i].textContent.trim()}`);
            count++;
          }
        }
      } else if (tag === 'ul') {
        const items = node.children;
        for (let i = 0; i < items.length; i++) {
          if (items[i].tagName.toLowerCase() === 'li') {
            resultLines.push(`- ${items[i].textContent.trim()}`);
          }
        }
      } else {
        for (let i = 0; i < node.childNodes.length; i++) {
          traverse(node.childNodes[i]);
        }
      }
    }
  };

  const bodyChildren = doc.body.childNodes;
  for (let i = 0; i < bodyChildren.length; i++) {
    const child = bodyChildren[i];
    if (child.nodeType === Node.ELEMENT_NODE) {
      traverse(child);
    } else if (child.nodeType === Node.TEXT_NODE) {
      const text = child.textContent.trim();
      if (text) resultLines.push(text);
    }
  }

  return resultLines.join('\n');
}

// ─── Tiptap Toolbar Custom Component ─────────────────────────────────────────
function TiptapToolbar({ editor }) {
  if (!editor) return null;

  const getActiveFontSize = () => {
    const attrs = editor.getAttributes('textStyle');
    return attrs.fontSize || 'normal';
  };

  const handleFontSizeChange = (e) => {
    const size = e.target.value;
    if (size === 'normal') {
      editor.chain().focus().updateAttributes('textStyle', { fontSize: null }).run();
    } else {
      editor.chain().focus().setMark('textStyle', { fontSize: size }).run();
    }
  };

  const getActiveHeading = () => {
    if (editor.isActive('heading', { level: 1 })) return '1';
    if (editor.isActive('heading', { level: 2 })) return '2';
    return 'normal';
  };

  const handleHeadingChange = (e) => {
    const val = e.target.value;
    if (val === 'normal') {
      editor.chain().focus().setParagraph().run();
    } else {
      editor.chain().focus().toggleHeading({ level: parseInt(val, 10) }).run();
    }
  };

  return (
    <div className="tiptap-toolbar-wrapper" style={{
      display: 'flex',
      flexWrap: 'wrap',
      alignItems: 'center',
      gap: '6px',
      padding: '8px 16px',
      background: '#f8f9fa',
      borderBottom: '1px solid #d9d4cb',
    }}>
      {/* Bold */}
      <button
        type="button"
        onClick={() => editor.chain().focus().toggleBold().run()}
        disabled={!editor.can().chain().focus().toggleBold().run()}
        className={editor.isActive('bold') ? 'is-active' : ''}
        style={getButtonStyle(editor.isActive('bold'))}
      >
        <strong>B</strong>
      </button>

      {/* Italic */}
      <button
        type="button"
        onClick={() => editor.chain().focus().toggleItalic().run()}
        disabled={!editor.can().chain().focus().toggleItalic().run()}
        className={editor.isActive('italic') ? 'is-active' : ''}
        style={getButtonStyle(editor.isActive('italic'))}
      >
        <em>I</em>
      </button>

      {/* Underline */}
      <button
        type="button"
        onClick={() => editor.chain().focus().toggleUnderline().run()}
        className={editor.isActive('underline') ? 'is-active' : ''}
        style={getButtonStyle(editor.isActive('underline'))}
      >
        <u>U</u>
      </button>

      <span style={{ width: '1px', height: '20px', background: '#d9d4cb', margin: '0 4px' }} />

      {/* Heading Selector */}
      <select
        value={getActiveHeading()}
        onChange={handleHeadingChange}
        style={getSelectStyle()}
      >
        <option value="normal">Normal Text</option>
        <option value="1">Heading 1</option>
        <option value="2">Heading 2</option>
      </select>

      {/* Font Size Selector */}
      <select
        value={getActiveFontSize()}
        onChange={handleFontSizeChange}
        style={getSelectStyle()}
      >
        <option value="normal">Font Size: Normal</option>
        <option value="12px">Font Size: Small</option>
        <option value="20px">Font Size: Large</option>
        <option value="28px">Font Size: Huge</option>
      </select>

      <span style={{ width: '1px', height: '20px', background: '#d9d4cb', margin: '0 4px' }} />

      {/* Alignments */}
      <button
        type="button"
        onClick={() => editor.chain().focus().setTextAlign('left').run()}
        style={getButtonStyle(editor.isActive({ textAlign: 'left' }))}
      >
        Align Left
      </button>
      <button
        type="button"
        onClick={() => editor.chain().focus().setTextAlign('center').run()}
        style={getButtonStyle(editor.isActive({ textAlign: 'center' }))}
      >
        Align Center
      </button>
      <button
        type="button"
        onClick={() => editor.chain().focus().setTextAlign('right').run()}
        style={getButtonStyle(editor.isActive({ textAlign: 'right' }))}
      >
        Align Right
      </button>

      <span style={{ width: '1px', height: '20px', background: '#d9d4cb', margin: '0 4px' }} />

      {/* Lists */}
      <button
        type="button"
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
        style={getButtonStyle(editor.isActive('orderedList'))}
      >
        Numbered List
      </button>
      <button
        type="button"
        onClick={() => editor.chain().focus().toggleBulletList().run()}
        style={getButtonStyle(editor.isActive('bulletList'))}
      >
        Bullet List
      </button>

      <span style={{ width: '1px', height: '20px', background: '#d9d4cb', margin: '0 4px' }} />

      {/* Undo/Redo */}
      <button
        type="button"
        onClick={() => editor.chain().focus().undo().run()}
        disabled={!editor.can().chain().focus().undo().run()}
        style={getButtonStyle(false)}
      >
        Undo
      </button>
      <button
        type="button"
        onClick={() => editor.chain().focus().redo().run()}
        disabled={!editor.can().chain().focus().redo().run()}
        style={getButtonStyle(false)}
      >
        Redo
      </button>
    </div>
  );
}

function getButtonStyle(isActive) {
  return {
    background: isActive ? '#2b4bc8' : '#fff',
    color: isActive ? '#fff' : '#1d1c1a',
    border: '1px solid #d9d4cb',
    padding: '4px 10px',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '12px',
    fontWeight: '600',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'all 0.1s',
  };
}

function getSelectStyle() {
  return {
    padding: '4px 8px',
    borderRadius: '4px',
    border: '1px solid #d9d4cb',
    background: '#fff',
    fontSize: '12px',
    fontWeight: '600',
    color: '#1d1c1a',
    cursor: 'pointer',
  };
}

// ─── Main DraftViewer Component ──────────────────────────────────────────────
export default function DraftViewer({ draft, loading, onTextChange, saveStatus, onManualSave }) {
  const lang = draft ? detectLanguage(draft.body_text) : 'en';
  const isFirstRender = useRef(true);

  // Inject print styles on mount
  useEffect(() => {
    injectPrintStyle();
  }, []);

  // Initialize Tiptap Editor
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: {
          levels: [1, 2],
        },
      }),
      Underline,
      TextAlign.configure({
        types: ['heading', 'paragraph'],
      }),
      TextStyle,
      FontFamily,
      Color,
      FontSize,
    ],
    content: draft ? convertGRToHTML(draft.body_text, lang) : '',
    editorProps: {
      attributes: {
        class: `ProseMirror ${lang === 'mr' ? 'ProseMirror-marathi' : 'ProseMirror-english'}`,
        style: 'outline: none; min-height: 600px;',
      },
    },
    onUpdate: ({ editor }) => {
      const html = editor.getHTML();
      const plainText = convertHTMLToGRText(html, lang);
      if (onTextChange) {
        onTextChange(plainText);
      }
    },
  });

  // Sync content when draft.body_text updates externally
  useEffect(() => {
    if (editor && draft?.body_text) {
      const currentHTML = editor.getHTML();
      const currentPlain = convertHTMLToGRText(currentHTML, lang);
      if (currentPlain.trim() !== draft.body_text.trim() || isFirstRender.current) {
        const htmlContent = convertGRToHTML(draft.body_text, lang);
        editor.commands.setContent(htmlContent);
        isFirstRender.current = false;
      }
    }
  }, [draft?.body_text, editor, lang]);

  const handlePrint = () => {
    window.print();
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

  return (
    <div id="gr-print-root" style={{
      background: '#fff',
      border: '1px solid #d1d5db',
      borderRadius: '4px',
      boxShadow: '0 2px 12px rgba(0,0,0,0.10), 0 8px 32px rgba(0,0,0,0.05)',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      position: 'relative',
    }}>
      {/* ── Top Header Toolbar Info ────────────────────────────────────────── */}
      <div className="tiptap-toolbar-wrapper" style={{
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

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {onManualSave && (
            <button
              type="button"
              onClick={onManualSave}
              style={{
                padding: '5px 12px',
                fontSize: '12px',
                fontWeight: '600',
                background: '#059669',
                color: '#fff',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
              }}
            >
              💾 Save
            </button>
          )}

          <button
            type="button"
            onClick={handlePrint}
            style={{
              padding: '5px 12px',
              fontSize: '12px',
              fontWeight: '600',
              background: '#dc2626',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
            }}
          >
            🖨️ Print Document
          </button>
        </div>
      </div>

      {/* ── Rich Text Toolbar ────────────────────────────────────────────── */}
      <TiptapToolbar editor={editor} />

      {/* ── Edit status badge ─────────────────────────────────────────────── */}
      {saveStatus === 'saved' && (
        <div className="tiptap-save-badge" style={{
          position: 'absolute',
          top: '90px',
          right: '24px',
          background: '#def7ec',
          color: '#03543f',
          padding: '4px 10px',
          borderRadius: '4px',
          fontSize: '12px',
          fontWeight: 'bold',
          zIndex: 10,
          border: '1px solid #bcf0da',
          boxShadow: '0 2px 8px rgba(0,0,0,0.05)',
        }}>
          Saved ✓
        </div>
      )}
      {saveStatus === 'saving' && (
        <div className="tiptap-save-badge" style={{
          position: 'absolute',
          top: '90px',
          right: '24px',
          background: '#feecdc',
          color: '#b45309',
          padding: '4px 10px',
          borderRadius: '4px',
          fontSize: '12px',
          fontWeight: 'bold',
          zIndex: 10,
          border: '1px solid #fbd5b5',
          boxShadow: '0 2px 8px rgba(0,0,0,0.05)',
        }}>
          Saving...
        </div>
      )}

      {/* ── Document container (A4 look) ─────────────────────────────────── */}
      <div style={{
        background: '#e9ecef',
        padding: '30px 10px',
        maxHeight: '720px',
        overflowY: 'auto',
        display: 'flex',
        justifyContent: 'center',
      }}>
        <div className="tiptap-editor-container" style={{
          background: '#ffffff',
          boxShadow: '0 4px 16px rgba(0,0,0,0.08)',
          padding: '48px 56px',
          width: '100%',
          maxWidth: '780px',
          minHeight: '800px',
          boxSizing: 'border-box',
        }}>
          <EditorContent editor={editor} />
        </div>
      </div>

      {/* ── Print footer notice (only shown in print mode) ───────────────── */}
      <div className="print-footer-notice" style={{ display: 'none' }}>
        <strong>Generated by NIRN.Ai | VJTI Mumbai</strong>
      </div>
    </div>
  );
}
