import { useRef, useState } from 'react';
import { useLanguage } from '../../LanguageContext.jsx';
import { DEPARTMENTS } from '../../constants/departments.js';

const ACCEPTED_EXTENSIONS = ['.docx', '.pdf', '.png', '.jpg', '.jpeg', '.webp', '.txt'];
const MAX_SIZE_BYTES = 15 * 1024 * 1024;

const IconUpload = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" fill="currentColor" viewBox="0 0 24 24">
    <path d="M5 20h14v-2H5v2zM11 4v9.17l-3.59-3.58L6 11l6 6 6-6-1.41-1.41L13 13.17V4z" transform="rotate(180 12 12)" />
  </svg>
);
const IconFile = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="currentColor" viewBox="0 0 24 24">
    <path d="M6 2c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm7 7V3.5L18.5 9zM8 13h8v2H8zm0 4h8v2H8zm0-8h5v2H8z"/>
  </svg>
);

export default function UploadGrCard({
  department,
  setDepartment,
  language,
  setLanguage,
  onUpload,
  loading,
}) {
  const { t, siteLanguage } = useLanguage();
  const isMr = siteLanguage === 'mr';
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState('');

  const validateAndSet = (candidate) => {
    setError('');
    if (!candidate) return;
    const ext = `.${candidate.name.split('.').pop().toLowerCase()}`;
    if (!ACCEPTED_EXTENSIONS.includes(ext)) {
      setError(`Unsupported file type (${ext}). Accepted: ${ACCEPTED_EXTENSIONS.join(', ')}`);
      return;
    }
    if (candidate.size > MAX_SIZE_BYTES) {
      setError('File is too large — the maximum size is 15 MB.');
      return;
    }
    setFile(candidate);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    validateAndSet(e.dataTransfer.files?.[0]);
  };

  const handleSubmit = () => {
    if (!file || !department) return;
    onUpload(file).catch((err) => setError(err.message));
  };

  return (
    <div style={{
      background: 'var(--paper)',
      border: '2px solid var(--ink)',
      borderRadius: '12px',
      padding: '24px',
      boxShadow: '0 4px 0 var(--ink)',
      display: 'flex',
      flexDirection: 'column',
      gap: '16px',
      marginBottom: '28px',
    }}>
      <div>
        <h3 style={{ margin: '0 0 4px 0' }}>{t('upload_entry_title')}</h3>
        <p style={{ margin: 0, fontSize: isMr ? '16px' : '14px', color: '#666' }}>{t('upload_entry_desc')}</p>
      </div>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        style={{
          border: `2px dashed ${dragOver ? 'var(--red)' : 'var(--ink)'}`,
          borderRadius: '10px',
          padding: '28px 16px',
          textAlign: 'center',
          cursor: 'pointer',
          background: dragOver ? 'rgba(230,57,30,0.06)' : 'transparent',
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_EXTENSIONS.join(',')}
          style={{ display: 'none' }}
          onChange={(e) => validateAndSet(e.target.files?.[0])}
        />
        <div style={{ color: 'var(--ink-soft)', marginBottom: 8, display: 'flex', justifyContent: 'center' }}>
          <IconUpload />
        </div>
        <div style={{ fontWeight: 700 }}>{t('upload_dropzone_text')}</div>
        <div style={{ fontSize: 12.5, color: '#666', marginTop: 6 }}>{t('upload_dropzone_formats')}</div>
        <button type="button" className="btn btn-secondary btn-sm" style={{ marginTop: 12 }} onClick={(e) => { e.stopPropagation(); inputRef.current?.click(); }}>
          {t('upload_browse_btn')}
        </button>
      </div>

      {file && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14 }}>
          <IconFile />
          <span>{t('upload_selected_file')} <strong>{file.name}</strong> ({(file.size / 1024).toFixed(0)} KB)</span>
        </div>
      )}

      <div className="draft-input-grid" style={{ gridTemplateColumns: '1fr 1fr', display: 'grid', gap: 16 }}>
        <div>
          <label style={{ display: 'block', fontSize: isMr ? '16px' : '14px', fontWeight: 700, marginBottom: 6 }}>
            {t('draft_issuing_dept')}
          </label>
          <select
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
            style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '2px solid var(--ink)', fontWeight: 'bold' }}
          >
            <option value="" disabled>{t('draft_select_dept')}</option>
            {DEPARTMENTS.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
          </select>
        </div>
        <div>
          <label style={{ display: 'block', fontSize: isMr ? '16px' : '14px', fontWeight: 700, marginBottom: 6 }}>
            {t('draft_output_lang')}
          </label>
          <div style={{ display: 'flex', gap: 8 }}>
            <button type="button" onClick={() => setLanguage('English')} className={`btn btn-sm ${language === 'English' ? 'btn-primary' : 'btn-secondary'}`} style={{ flex: 1 }}>
              {t('draft_lang_english')}
            </button>
            <button type="button" onClick={() => setLanguage('Marathi')} className={`btn btn-sm ${language === 'Marathi' ? 'btn-primary' : 'btn-secondary'}`} style={{ flex: 1 }}>
              {t('draft_lang_marathi')}
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div style={{ background: '#fee2e2', border: '2px solid var(--red)', color: 'var(--red)', padding: '10px 14px', borderRadius: 8, fontWeight: 600, fontSize: 13.5 }}>
          {error}
        </div>
      )}

      <button
        type="button"
        className="btn btn-primary"
        disabled={!file || !department || loading}
        onClick={handleSubmit}
        style={{ minHeight: 48 }}
      >
        {loading ? t('upload_uploading') : t('upload_btn')}
      </button>
    </div>
  );
}
