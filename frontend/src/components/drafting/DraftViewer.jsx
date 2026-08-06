import React, { useState, useEffect, useRef } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import TextAlign from '@tiptap/extension-text-align';
import { TextStyle } from '@tiptap/extension-text-style';
import { FontFamily } from '@tiptap/extension-font-family';
import { Color } from '@tiptap/extension-color';

import { useLanguage } from '../../LanguageContext.jsx';
import { api } from '../../api.js';
import { convertGRToHTML } from '../../utils/grFormat.js';
import { FontSize } from '../../utils/fontSizeExtension.js';
import { generateGRDocumentPDF } from '../../utils/pdfExport.js';

const ESTIMATE_STORAGE_KEY = 'nirn_draft_gen_estimate_ms';
const DEFAULT_ESTIMATE_MS = 45000;

const toDevanagariDigits = (value) => String(value).replace(/\d/g, (d) => '०१२३४५६७८९'[d]);
const roundToNearest = (value, step) => Math.max(step, Math.round(value / step) * step);

// The stored department value is machine-formatted
// ("Higher_and_Technical_Education_Department"); display-only.
const formatDepartmentName = (value) => {
  if (!value) return 'Government of Maharashtra';
  return value
    .replace(/_/g, ' ')
    .split(' ')
    .map((word) => (word ? word[0].toUpperCase() + word.slice(1).toLowerCase() : word))
    .join(' ');
};

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
  onSaveDraft,
  onSubmitForReview
}) {
  const { t, siteLanguage } = useLanguage();
  const isMr = siteLanguage === 'mr';
  const [copied, setCopied] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isSubmittingForReview, setIsSubmittingForReview] = useState(false);
  const [toast, setToast] = useState(null); // { message, type: 'success' | 'error' }

  // Dirty/saved state (Task 5c): compares current editor HTML against
  // the last content we know is persisted server-side.
  const [isDirty, setIsDirty] = useState(false);
  const [lastSavedAt, setLastSavedAt] = useState(null);
  const savedHtmlRef = useRef(null);

  // Export state (Task 5b) — both buttons disabled while either export
  // is in flight, to prevent double-clicks.
  const [exporting, setExporting] = useState(null); // null | 'pdf' | 'docx'
  const [exportError, setExportError] = useState('');

  // Track draft ID to prevent overwriting user edits on parent state updates
  const loadedDraftIdRef = useRef(null);

  // Adaptive estimation state
  const [elapsedMs, setElapsedMs] = useState(0);
  const [hasStoredEstimate, setHasStoredEstimate] = useState(() => {
    try { return !!localStorage.getItem(ESTIMATE_STORAGE_KEY); } catch { return false; }
  });
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
          setHasStoredEstimate(true);
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
    onUpdate: ({ editor: ed }) => {
      setIsDirty(savedHtmlRef.current !== null && ed.getHTML() !== savedHtmlRef.current);
    },
  });

  // Only load initial document content when a NEW draft is passed in
  useEffect(() => {
    if (!editor || !draft?.body_text) return;

    // Including _rev means a server-driven content overwrite (e.g. accepting
    // a conflict resolution) forces a reload even though draft_id is
    // unchanged — see handleResolveAllConflicts in Draft.jsx.
    const currentDraftKey = `${draft.draft_id || draft.title || draft.body_text.slice(0, 30)}:${draft._rev || 0}`;
    if (loadedDraftIdRef.current !== currentDraftKey) {
      loadedDraftIdRef.current = currentDraftKey;
      const formattedHtml = convertGRToHTML(draft.body_text, draft.language);
      editor.commands.setContent(formattedHtml);
      savedHtmlRef.current = formattedHtml;
      setIsDirty(false);
      setLastSavedAt(null);
    }
  }, [draft, editor]);

  // Warn on navigating away with unsaved changes — covers tab close,
  // refresh, and typing a new URL. In-app SPA navigation isn't
  // interceptable here (this app uses a plain BrowserRouter, not a
  // data router with useBlocker), so this is the browser-level net.
  useEffect(() => {
    const handler = (e) => {
      if (!isDirty) return;
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [isDirty]);

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
      savedHtmlRef.current = htmlContent;
      setIsDirty(false);
      setLastSavedAt(new Date());
      setToast({ message: 'Document saved successfully! ✓', type: 'success' });
    } catch (err) {
      console.error("Save error:", err);
      setToast({ message: 'Failed to save document.', type: 'error' });
    } finally {
      setIsSaving(false);
      setTimeout(() => setToast(null), 3000);
    }
  };

  // Submit for Review (Task 5c): visible only while status === 'draft'.
  // Waits for the server response before reflecting anything — no
  // optimistic UI, consistent with the rest of the approval workflow.
  const handleSubmitForReview = async () => {
    if (!onSubmitForReview || isSubmittingForReview) return;
    setIsSubmittingForReview(true);
    setToast(null);
    try {
      await onSubmitForReview();
      setToast({ message: t('draft_submit_for_review_btn') + ' ✓', type: 'success' });
    } catch (err) {
      console.error('Submit for review error:', err);
      setToast({ message: err.message || t('draft_submit_for_review_error'), type: 'error' });
    } finally {
      setIsSubmittingForReview(false);
      setTimeout(() => setToast(null), 3000);
    }
  };

  const rawEstSeconds = Math.round(estimateMsRef.current / 1000);
  const estimateSeconds = rawEstSeconds < 20 ? 35 : rawEstSeconds;
  const estimateLowSec = Math.max(25, roundToNearest(estimateSeconds * 0.8, 5));
  const estimateHighSec = Math.max(45, roundToNearest(estimateSeconds * 1.25, 5));
  const isTakingLonger = elapsedMs > Math.max(35000, estimateMsRef.current);

  const estimateText = {
    mr: `अंदाजे वेळ: ~${toDevanagariDigits(estimateLowSec)}-${toDevanagariDigits(estimateHighSec)} सेकंद (सरासरी अपेक्षित वेळ)`,
    en: `Estimated time: ~${estimateLowSec}-${estimateHighSec} seconds (average expected time)`,
  };

  const handleCopy = () => {
    if (!editor) return;
    const text = editor.getText();
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const handlePrint = () => {
    window.print();
  };

  // Exports the CURRENT editor content (editor.getHTML()), not the
  // original AI output, so the officer's edits are always included.
  const handleExportPdf = async () => {
    if (!editor || exporting) return;
    setExportError('');
    setExporting('pdf');
    try {
      await generateGRDocumentPDF(draft, editor.getHTML());
    } catch (err) {
      console.error('PDF export error:', err);
      setExportError(t('export_error'));
    } finally {
      setExporting(null);
    }
  };

  const handleExportDocx = async () => {
    if (!draft?.draft_id || exporting) return;
    setExportError('');
    setExporting('docx');
    try {
      const { blob, filename } = await api.exportDocx(draft.draft_id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('DOCX export error:', err);
      setExportError(err.message || t('export_error'));
    } finally {
      setExporting(null);
    }
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
          {isTakingLonger ? (
            <h4 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--red)' }}>
              {t('draft_loading_taking_longer')}
            </h4>
          ) : (
            <h4 style={{ fontSize: '18px', fontWeight: 700 }}>
              {t('draft_loading_generating')}
            </h4>
          )}
        </div>
        <div style={{ marginTop: '10px' }}>
          <p style={{ color: '#666', fontSize: '16px', maxWidth: '440px' }}>{isMr ? estimateText.mr : estimateText.en}</p>
        </div>

        <div style={{ marginTop: '10px' }}>
          <p style={{ color: '#8a8a8a', fontSize: '14px', maxWidth: '440px' }}>
            {t('draft_loading_retrieving')}
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
        <h3 style={{ margin: '0 0 8px 0', fontSize: '18px', color: 'var(--ink)' }}>
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
          <span className="gr-editor-dept-name">
            {formatDepartmentName(draft.department)}
          </span>
        </div>

        <div className="gr-editor-header-actions">
          {toast && (
            <span className={toast.type === 'success' ? 'saved-badge' : 'error-badge'}>
              {toast.message}
            </span>
          )}
          {!toast && isDirty && (
            <span className="error-badge" style={{ background: '#fff3d6', color: '#9a6b00', borderColor: 'var(--yellow)' }}>
              {t('save_unsaved_indicator')}
            </span>
          )}
          {!toast && !isDirty && lastSavedAt && (
            <span className="saved-badge">
              {t('save_saved_at')} {lastSavedAt.toLocaleTimeString(isMr ? 'mr-IN' : 'en-IN', { hour: '2-digit', minute: '2-digit' })}
            </span>
          )}
          {exportError && <span className="error-badge">{exportError}</span>}

          <div className="gr-editor-btn-group">
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

            {/* Submit for Review — only while this draft hasn't entered
                the approval workflow yet (status === 'draft'); once
                submitted/reviewed/approved this button disappears. */}
            {onSubmitForReview && draft?.status === 'draft' && draft?.draft_id && (
              <button
                type="button"
                onClick={handleSubmitForReview}
                disabled={isSubmittingForReview}
                className="action-btn"
                style={{ background: 'var(--blue)', color: '#fff', borderColor: 'var(--ink)' }}
                title={t('draft_submit_for_review_btn')}
              >
                {isSubmittingForReview ? (
                  <>
                    <span className="spinner-small" /> {t('draft_submitting_for_review')}
                  </>
                ) : (
                  t('draft_submit_for_review_btn')
                )}
              </button>
            )}

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
              onClick={handleCopy}
              className="action-btn"
            >
              {copied ? <><IconCheck /> {t('draft_copied')}</> : <><IconCopy /> {t('draft_copy')}</>}
            </button>

            <button
              type="button"
              onClick={handleExportPdf}
              disabled={Boolean(exporting)}
              className="action-btn"
              title={t('export_download_pdf')}
            >
              {exporting === 'pdf' ? <><span className="spinner-small" /> {t('export_exporting')}</> : <><IconDownload /> {t('export_download_pdf')}</>}
            </button>

            <button
              type="button"
              onClick={handleExportDocx}
              disabled={Boolean(exporting)}
              className="action-btn"
              title={t('export_download_docx')}
            >
              {exporting === 'docx' ? <><span className="spinner-small" /> {t('export_exporting')}</> : <><IconDownload /> {t('export_download_docx')}</>}
            </button>
          </div>
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
