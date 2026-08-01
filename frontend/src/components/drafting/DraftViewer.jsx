import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import TextAlign from '@tiptap/extension-text-align';
import { TextStyle } from '@tiptap/extension-text-style';
import { FontFamily } from '@tiptap/extension-font-family';
import { Color } from '@tiptap/extension-color';
import { useLanguage } from '../../LanguageContext.jsx';
import { convertGRToHTML } from '../../utils/grFormat.js';
import { FontSize } from '../../utils/fontSizeExtension.js';
import StatusVerb from '../StatusVerb.jsx';

const ESTIMATE_STORAGE_KEY = 'nirn_draft_gen_estimate_ms';
const DEFAULT_ESTIMATE_MS = 45000;

const toDevanagariDigits = (value) => String(value).replace(/\d/g, (d) => '०१२३४५६७८९'[d]);
const roundToNearest = (value, step) => Math.max(step, Math.round(value / step) * step);

const IconSave = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 24 24">
    <path d="M17 3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V7l-4-4zm-5 16c-1.66 0-3-1.34-3-3s1.34-3 3-3 3 1.34 3 3-1.34 3-3 3zm3-10H5V5h10v4z"/>
  </svg>
);
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
const IconPrint = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 24 24">
    <path d="M19 8H5c-1.66 0-3 1.34-3 3v6h4v4h12v-4h4v-6c0-1.66-1.34-3-3-3zm-3 11H8v-5h8v5zm3-7c-.55 0-1-.45-1-1s.45-1 1-1 1 .45 1 1-.45 1-1 1zm-1-9H6v4h12V3z"/>
  </svg>
);
const IconDocument = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" fill="currentColor" viewBox="0 0 24 24">
    <path d="M6 2c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm7 7V3.5L18.5 9zM8 13h8v2H8zm0 4h8v2H8zm0-8h5v2H8z"/>
  </svg>
);
const IconSave = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 24 24">
    <path d="M17 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V7zm-5 16c-1.66 0-3-1.34-3-3s1.34-3 3-3 3 1.34 3 3-1.34 3-3 3zm3-10H5V5h10z"/>
  </svg>
);

// Uploaded/converted drafts arrive as block-level HTML (see
// document_extraction/html_convert.py); LLM-generated drafts are still
// plain text today. A cheap, reliable-enough test: does it open with
// an HTML block tag?
function isHtmlContent(text) {
  return typeof text === "string" && /^\s*<(p|h[1-6]|ol|ul|div)[\s>]/i.test(text);
}

const FONT_SIZES = ['12px', '14px', '16px', '18px', '20px', '24px', '30px', '36px'];

/* Custom Tiptap Editor Toolbar Component */
function TiptapToolbar({ editor }) {
  const [, setTick] = useState(0);

  useEffect(() => {
    if (!editor) return;

    const handleUpdate = () => {
      setTick(tick => tick + 1);
    };

    editor.on('selectionUpdate', handleUpdate);
    editor.on('transaction', handleUpdate);

    return () => {
      editor.off('selectionUpdate', handleUpdate);
      editor.off('transaction', handleUpdate);
    };
  }, [editor]);

  if (!editor) return null;

  const currentFontSize = editor.getAttributes('textStyle').fontSize || '16px';

  const handleFontSizeChange = (e) => {
    const val = e.target.value;
    if (val) {
      editor.chain().focus(null, { scrollIntoView: false }).setFontSize(val).run();
    } else {
      editor.chain().focus(null, { scrollIntoView: false }).unsetFontSize().run();
    }
  };

  return (
    <div className="tiptap-toolbar">
      <div className="toolbar-group">
        {/* Bold */}
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => editor.chain().focus(null, { scrollIntoView: false }).toggleBold().run()}
          className={editor.isActive('bold') ? 'active' : ''}
          title="Bold"
        >
          <strong>B</strong>
        </button>

        {/* Italic */}
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => editor.chain().focus(null, { scrollIntoView: false }).toggleItalic().run()}
          className={editor.isActive('italic') ? 'active' : ''}
          title="Italic"
        >
          <em>I</em>
        </button>

        {/* Underline */}
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => editor.chain().focus(null, { scrollIntoView: false }).toggleUnderline().run()}
          className={editor.isActive('underline') ? 'active' : ''}
          title="Underline"
        >
          <u>U</u>
        </button>
      </div>

      <div className="toolbar-divider" />

      {/* Font Size Dropdown */}
      <div className="toolbar-group">
        <select
          className="font-size-select"
          value={currentFontSize}
          onChange={handleFontSizeChange}
          title="Font Size"
        >
          {FONT_SIZES.map(size => (
            <option key={size} value={size}>
              {size} {size === '16px' ? '(Default)' : ''}
            </option>
          ))}
        </select>
      </div>

      <div className="toolbar-divider" />

        {/* Headings / Text Sizing */}
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => {
            if (currentFontSize === '28px') {
              editor.chain().focus(null, { scrollIntoView: false }).unsetFontSize().run();
            } else {
              editor.chain().focus(null, { scrollIntoView: false }).setFontSize('28px').run();
            }
          }}
          className={currentFontSize === '28px' ? 'active' : ''}
          title="Heading 1 (28px - Selected text only)"
        >
          H1
        </button>
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => {
            if (currentFontSize === '22px') {
              editor.chain().focus(null, { scrollIntoView: false }).unsetFontSize().run();
            } else {
              editor.chain().focus(null, { scrollIntoView: false }).setFontSize('22px').run();
            }
          }}
          className={currentFontSize === '22px' ? 'active' : ''}
          title="Heading 2 (22px - Selected text only)"
        >
          H2
        </button>
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => editor.chain().focus(null, { scrollIntoView: false }).unsetFontSize().setParagraph().run()}
          className={(!currentFontSize || currentFontSize === '16px') && !editor.isActive('heading') ? 'active' : ''}
          title="Normal Text Paragraph (16px)"
        >
          Normal
        </button>

      <div className="toolbar-divider" />

      <div className="toolbar-group">
        {/* Align Left */}
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => editor.chain().focus(null, { scrollIntoView: false }).setTextAlign('left').run()}
          className={editor.isActive({ textAlign: 'left' }) ? 'active' : ''}
          title="Align Left"
        >
          Left
        </button>
        {/* Align Center */}
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => editor.chain().focus(null, { scrollIntoView: false }).setTextAlign('center').run()}
          className={editor.isActive({ textAlign: 'center' }) ? 'active' : ''}
          title="Align Center"
        >
          Center
        </button>
        {/* Align Right */}
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => editor.chain().focus(null, { scrollIntoView: false }).setTextAlign('right').run()}
          className={editor.isActive({ textAlign: 'right' }) ? 'active' : ''}
          title="Align Right"
        >
          Right
        </button>
      </div>

      <div className="toolbar-divider" />

      <div className="toolbar-group">
        {/* Lists */}
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => editor.chain().focus(null, { scrollIntoView: false }).toggleOrderedList().run()}
          className={editor.isActive('orderedList') ? 'active' : ''}
          title="Numbered List"
        >
          1. List
        </button>
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => editor.chain().focus(null, { scrollIntoView: false }).toggleBulletList().run()}
          className={editor.isActive('bulletList') ? 'active' : ''}
          title="Bullet List"
        >
          • List
        </button>
      </div>

      <div className="toolbar-divider" />

      <div className="toolbar-group">
        {/* History */}
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => editor.chain().focus(null, { scrollIntoView: false }).undo().run()}
          disabled={!editor.can().undo()}
          title="Undo"
        >
          ↺ Undo
        </button>
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => editor.chain().focus(null, { scrollIntoView: false }).redo().run()}
          disabled={!editor.can().redo()}
          title="Redo"
        >
          ↻ Redo
        </button>
      </div>
    </div>
  );
}

export default function DraftViewer({
  draft,
  loading,
  onSaveDraft
}) {
  const { t } = useLanguage();
  const [copied, setCopied] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [toast, setToast] = useState(null); // { message, type: 'success' | 'error' }

  // Track draft ID to prevent overwriting user edits on parent state updates
  const loadedDraftIdRef = useRef(null);

  // Adaptive estimation state
  const [elapsedMs, setElapsedMs] = useState(0);
  const startRef = useRef(null);
  const estimateMsRef = useRef(DEFAULT_ESTIMATE_MS);

  useEffect(() => {
    if (loading) {
      startRef.current = Date.now();
      setElapsedMs(0);
      try {
        const stored = localStorage.getItem(ESTIMATE_STORAGE_KEY);
        if (stored) {
          estimateMsRef.current = parseInt(stored, 10);
        }
      } catch { /* ignore */ }

      const interval = setInterval(() => {
        setElapsedMs(Date.now() - (startRef.current || Date.now()));
      }, 1000);
      return () => clearInterval(interval);
    }

    if (startRef.current) {
      const duration = Date.now() - startRef.current;
      startRef.current = null;
      try { localStorage.setItem(ESTIMATE_STORAGE_KEY, String(duration)); } catch { /* ignore */ }
    }
  }, [loading]);

  const editor = useEditor({
    extensions: [
      StarterKit,
      Underline,
      TextAlign.configure({
        types: ['heading', 'paragraph'],
      }),
      TextStyle,
      FontFamily,
      Color,
      FontSize,
    ],
    content: '',
  });

  // Only load initial document content when a NEW draft is passed in
  useEffect(() => {
    if (!editor || !draft?.body_text) return;

    const currentDraftKey = draft.draft_id || draft.title || draft.body_text.slice(0, 30);
    if (loadedDraftIdRef.current !== currentDraftKey) {
      loadedDraftIdRef.current = currentDraftKey;
      const formattedHtml = convertGRToHTML(draft.body_text, draft.language);
      editor.commands.setContent(formattedHtml);
    }
  }, [draft, editor]);

  // Explicit Manual Save Click Handler
  const handleManualSave = async () => {
    if (!editor || isSaving) return;

    setIsSaving(true);
    setToast(null);

    const htmlContent = editor.getHTML();
    const textContent = editor.getText();

    try {
      if (onSaveDraft) {
        await onSaveDraft(htmlContent, textContent);
      }
      setToast({ message: 'Document saved successfully! ✓', type: 'success' });
    } catch (err) {
      console.error("Save error:", err);
      setToast({ message: 'Failed to save document.', type: 'error' });
    } finally {
      setIsSaving(false);
      setTimeout(() => setToast(null), 3000);
    }
  };

  const handleCopy = () => {
    if (!editor) return;
    const text = editor.getText();
    navigator.clipboard.writeText(text).then(() => {
=======
  saved,
  saving,
  onSave,
  scrollToClauseIndex
}) {
  const { t } = useLanguage();
  const [copied, setCopied] = useState(false);
  const bodyRef = useRef(null);

  // Best-effort deep-link from a conflict lookup's "Open draft" link.
  // draft_clause_index is the Nth clause split.py.split_into_clauses()
  // saw — that only lines up with a DOM element for uploaded/converted
  // drafts, whose numbered clauses render as <li> (see
  // document_extraction/html_convert.py). LLM-generated drafts are
  // still plain text with no addressable blocks, so there's nothing to
  // scroll to there — silently do nothing rather than guess a position.
  useEffect(() => {
    // bodyRef only exists once the loaded (non-loading) branch below has
    // mounted — without `loading` in the dependency array, this can fire
    // once while still loading (ref null, no-op) and never get a second
    // chance to run once the content actually mounts.
    if (loading || scrollToClauseIndex == null || !bodyRef.current) return;
    const items = bodyRef.current.querySelectorAll('li');
    const target = items[scrollToClauseIndex];
    if (!target) return;
    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    target.classList.add('clause-highlight');
    const timer = setTimeout(() => target.classList.remove('clause-highlight'), 3000);
    return () => clearTimeout(timer);
  }, [scrollToClauseIndex, draft, loading]);

  const plainBodyText = () => {
    if (!draft?.body_text) return '';
    if (!isHtmlContent(draft.body_text)) return draft.body_text;
    const el = document.createElement('div');
    el.innerHTML = draft.body_text;
    return el.textContent || '';
  };

  const handleCopy = () => {
    if (!draft || !draft.body_text) return;
    navigator.clipboard.writeText(plainBodyText()).then(() => {
>>>>>>> origin/kumar-db
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const handleDownloadTxt = () => {
    const text = editor ? editor.getText() : plainBodyText();
    if (!text) return;
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `GR_Draft_${draft?.gr_id || 'NIRN'}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handlePrint = () => {
    window.print();
  };

  const isMarathi = draft?.language?.toLowerCase().includes('marathi') || draft?.language === 'mr';

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
    <div className="gr-editor-card">
      {/* Top Header & Actions Bar */}
      <div className="gr-editor-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className="official-badge">{t('draft_official')}</span>
          <span style={{ fontSize: '13px', fontWeight: 'bold', color: 'var(--ink)' }}>
            {draft.department || 'Government of Maharashtra'}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', position: 'relative' }}>
          {toast && (
            <span className={toast.type === 'success' ? 'saved-badge' : 'error-badge'}>
              {toast.message}
            </span>
          )}

          {/* EXPLICIT MANUAL SAVE BUTTON */}
          <button
            type="button"
            onClick={handleManualSave}
            disabled={isSaving}
            className="action-btn save-btn"
            title="Save Document"
          >
            {isSaving ? (
              <>
                <span className="spinner-small" /> Saving...
              </>
            ) : (
              <>
                <IconSave /> Save
              </>
            )}
          </button>

          <button
            type="button"
            onClick={handlePrint}
            className="action-btn print-btn"
            title="Print Document"
          >
            <IconPrint /> Print
          </button>

          <button
            type="button"
            onClick={onSave}
            disabled={saved || saving}
            className={`btn btn-sm ${saved ? 'btn-secondary' : 'btn-primary'}`}
          >
            {saved ? <><IconCheck /> Saved</> : saving ? 'Saving…' : <><IconSave /> Save to History</>}
          </button>
          <button
            type="button"
            onClick={handleCopy}
            className="action-btn"
          >
            {copied ? <><IconCheck /> {t('draft_copied')}</> : <><IconCopy /> {t('draft_copy')}</>}
          </button>

          <button
            type="button"
            onClick={handleDownloadTxt}
            className="action-btn"
          >
            <IconDownload /> {t('draft_download_txt')}
          </button>
        </div>
      </div>

      {/* Custom Tiptap Editor Toolbar */}
      <TiptapToolbar editor={editor} />

      {/* Editor Printable Paper Sheet Area */}
      <div className={`a4-paper-wrapper ${isMarathi ? 'lang-marathi' : 'lang-english'}`}>
        <div className="ProseMirror-print-wrapper">
          <EditorContent editor={editor} />
        </div>
      </div>

      {/* Footer for print layout */}
      <div className="print-only-footer">
        Generated by NIRN.Ai | VJTI Mumbai
      </div>
    </div>
  );
}
