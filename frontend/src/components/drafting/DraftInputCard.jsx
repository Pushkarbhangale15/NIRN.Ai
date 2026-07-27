import React, { useState } from 'react';
import { motion } from 'framer-motion';

const EXAMPLE_PROMPTS = [
  "Policy on remote work and flexible hours for IT department staff",
  "Revised grant allocation for higher education research labs in state universities",
  "Scholarship scheme for economically weaker students pursuing technical degrees"
];

export default function DraftInputCard({
  prompt,
  setPrompt,
  language,
  setLanguage,
  onGenerate,
  loading,
  onReset
}) {
  const [uploadedFile, setUploadedFile] = useState(null);

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      setUploadedFile(file.name);
      // If user uploads text/markdown file, read its content into prompt if empty
      const reader = new FileReader();
      reader.onload = (evt) => {
        if (!prompt.trim()) {
          setPrompt(evt.target.result.slice(0, 1000));
        }
      };
      reader.readAsText(file);
    }
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
      gap: '20px'
    }}>
      <div>
        <h3 style={{ margin: '0 0 4px 0', fontSize: '18px', fontWeight: 'bold' }}>
          Draft Brief & Parameters
        </h3>
        <p style={{ margin: 0, fontSize: '13px', color: '#666' }}>
          Describe the Government Resolution you need. NIRN.Ai will handle alignment, templates, and conflict checks.
        </p>
      </div>

      {/* Language Selector */}
      <div>
        <label style={{ display: 'block', fontSize: '13px', fontWeight: 'bold', marginBottom: '6px' }}>
          Output Language
        </label>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            type="button"
            onClick={() => setLanguage('English')}
            style={{
              flex: 1,
              padding: '8px 12px',
              borderRadius: '8px',
              border: '2px solid var(--ink)',
              background: language === 'English' ? 'var(--blue)' : '#fff',
              color: language === 'English' ? '#fff' : 'var(--ink)',
              fontWeight: 'bold',
              fontSize: '13px',
              cursor: 'pointer',
              boxShadow: language === 'English' ? '0 2px 0 var(--ink)' : 'none'
            }}
          >
            English
          </button>
          <button
            type="button"
            onClick={() => setLanguage('Marathi')}
            style={{
              flex: 1,
              padding: '8px 12px',
              borderRadius: '8px',
              border: '2px solid var(--ink)',
              background: language === 'Marathi' ? 'var(--blue)' : '#fff',
              color: language === 'Marathi' ? '#fff' : 'var(--ink)',
              fontWeight: 'bold',
              fontSize: '13px',
              cursor: 'pointer',
              boxShadow: language === 'Marathi' ? '0 2px 0 var(--ink)' : 'none'
            }}
          >
            मराठी (Marathi)
          </button>
        </div>
      </div>

      {/* Brief Description Textarea */}
      <div>
        <label style={{ display: 'block', fontSize: '13px', fontWeight: 'bold', marginBottom: '6px' }}>
          Describe the Resolution Brief
        </label>
        <textarea
          rows={6}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="e.g. Issue a Government Resolution regarding financial assistance of ₹25,000 for university research labs..."
          style={{
            width: '100%',
            padding: '12px',
            border: '2px solid var(--ink)',
            borderRadius: '8px',
            fontFamily: 'inherit',
            fontSize: '14px',
            resize: 'vertical',
            boxSizing: 'border-box'
          }}
        />
      </div>

      {/* Example Prompts */}
      <div>
        <label style={{ display: 'block', fontSize: '12px', fontWeight: 'bold', color: '#666', marginBottom: '8px' }}>
          Try Example Briefs:
        </label>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {EXAMPLE_PROMPTS.map((ex, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setPrompt(ex)}
              style={{
                textAlign: 'left',
                background: '#f9fafb',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                padding: '8px 10px',
                fontSize: '12px',
                cursor: 'pointer',
                color: 'var(--ink)',
                transition: 'background 0.15s'
              }}
              onMouseEnter={(e) => e.target.style.background = '#f3f4f6'}
              onMouseLeave={(e) => e.target.style.background = '#f9fafb'}
            >
              💡 {ex}
            </button>
          ))}
        </div>
      </div>

      {/* Upload GR (Optional) */}
      <div>
        <label style={{ display: 'block', fontSize: '12px', fontWeight: 'bold', color: '#444', marginBottom: '4px' }}>
          Upload Base GR / Reference File (Optional)
        </label>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <label style={{
            display: 'inline-block',
            padding: '8px 12px',
            background: '#fff',
            border: '2px solid var(--ink)',
            borderRadius: '6px',
            fontSize: '12px',
            fontWeight: 'bold',
            cursor: 'pointer',
            boxShadow: '0 2px 0 var(--ink)'
          }}>
            📁 {uploadedFile ? 'Change File' : 'Upload File (.txt/.pdf)'}
            <input
              type="file"
              accept=".txt,.pdf,.doc,.docx"
              onChange={handleFileUpload}
              style={{ display: 'none' }}
            />
          </label>
          {uploadedFile && (
            <span style={{ fontSize: '12px', color: 'var(--blue)', fontWeight: '600' }}>
              ✓ {uploadedFile}
            </span>
          )}
        </div>
      </div>

      {/* Action Buttons */}
      <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
        <motion.button
          whileTap={{ scale: 0.96 }}
          type="button"
          onClick={onGenerate}
          disabled={loading || !prompt.trim()}
          style={{
            flex: 1,
            padding: '12px',
            background: loading || !prompt.trim() ? '#9ca3af' : 'var(--blue)',
            color: '#fff',
            border: '2px solid var(--ink)',
            borderRadius: '8px',
            fontWeight: 'bold',
            fontSize: '15px',
            cursor: loading || !prompt.trim() ? 'not-allowed' : 'pointer',
            boxShadow: loading || !prompt.trim() ? 'none' : '0 3px 0 var(--ink)'
          }}
        >
          {loading ? 'Generating GR & Running Analysis...' : 'Generate Draft GR →'}
        </motion.button>

        {onReset && (
          <button
            type="button"
            onClick={onReset}
            style={{
              padding: '12px 16px',
              background: '#fff',
              color: 'var(--ink)',
              border: '2px solid var(--ink)',
              borderRadius: '8px',
              fontWeight: 'bold',
              fontSize: '13px',
              cursor: 'pointer',
              boxShadow: '0 2px 0 var(--ink)'
            }}
          >
            Clear
          </button>
        )}
      </div>
    </div>
  );
}
