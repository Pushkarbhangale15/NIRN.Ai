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


  return (
    <div style={{
      background: 'var(--paper)',
      border: '2px solid var(--ink)',
      borderRadius: '12px',
      padding: '24px',
      boxShadow: '0 4px 0 var(--ink)',
      display: 'flex',
      flexDirection: 'column',
      gap: '24px',
      width: '100%',
      boxSizing: 'border-box',
      marginBottom: '28px'
    }}>
      {/* Title */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '2px solid var(--ink)', paddingBottom: '14px' }}>
        <div>
          <h3 style={{ margin: '0 0 4px 0', fontSize: '18px', fontWeight: 'bold' }}>
            Draft Brief & Parameters
          </h3>
          <p style={{ margin: 0, fontSize: '13px', color: '#666' }}>
            Describe the Government Resolution you need. NIRN.Ai will handle alignment, templates, and conflict checks.
          </p>
        </div>
        {onReset && (
          <button
            type="button"
            onClick={onReset}
            style={{
              padding: '8px 16px',
              background: '#fff',
              color: 'var(--ink)',
              border: '2px solid var(--ink)',
              borderRadius: '6px',
              fontWeight: 'bold',
              fontSize: '13px',
              cursor: 'pointer',
              boxShadow: '0 2px 0 var(--ink)'
            }}
          >
            Clear Fields
          </button>
        )}
      </div>

      {/* Main Form Fields Layout: Two Columns (Left: Textarea & Examples, Right: Parameters) */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '28px' }}>
        {/* Left Sub-Column: Textarea and Example Briefs */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ display: 'block', fontSize: '13px', fontWeight: 'bold' }}>
              Describe the Resolution Brief
            </label>
            <textarea
              rows={4}
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
                resize: 'none',
                boxSizing: 'border-box'
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 'bold', color: '#666', marginBottom: '8px' }}>
              Try Example Briefs:
            </label>
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
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
                    padding: '6px 10px',
                    fontSize: '12px',
                    cursor: 'pointer',
                    color: 'var(--ink)',
                    transition: 'background 0.15s',
                    maxWidth: '32%'
                  }}
                  onMouseEnter={(e) => e.target.style.background = '#f3f4f6'}
                  onMouseLeave={(e) => e.target.style.background = '#f9fafb'}
                >
                  💡 {ex.slice(0, 45)}...
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Right Sub-Column: Language, Reference File, and Action Buttons */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '18px', justifyContent: 'space-between' }}>
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



          {/* Generate Action Button */}
          <motion.button
            whileTap={{ scale: 0.98 }}
            type="button"
            onClick={onGenerate}
            disabled={loading || !prompt.trim()}
            style={{
              width: '100%',
              padding: '12px',
              background: loading || !prompt.trim() ? '#9ca3af' : 'var(--blue)',
              color: '#fff',
              border: '2px solid var(--ink)',
              borderRadius: '8px',
              fontWeight: 'bold',
              fontSize: '14px',
              cursor: loading || !prompt.trim() ? 'not-allowed' : 'pointer',
              boxShadow: loading || !prompt.trim() ? 'none' : '0 3px 0 var(--ink)'
            }}
          >
            {loading ? 'Generating GR & Running Analysis...' : 'Generate Draft GR →'}
          </motion.button>
        </div>
      </div>
    </div>
  );
}
