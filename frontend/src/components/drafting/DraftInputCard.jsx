import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useLanguage } from '../../LanguageContext.jsx';

const IconLightbulb = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 24 24">
    <path d="M9 21h6v-1H9zm3-19a7 7 0 0 0-4 12.74V17a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-2.26A7 7 0 0 0 12 2Z" />
  </svg>
);

const EXAMPLE_PROMPTS = [
  "Policy on remote work and flexible hours for IT department staff",
  "Revised grant allocation for higher education research labs in state universities",
  "Scholarship scheme for economically weaker students pursuing technical degrees"
];

const DEPARTMENTS = [
  { value: "Agriculture,_Dairy_Development,_Animal_Husbandry_and_Fisheries_Department", label: "Agriculture, Dairy Development, Animal Husbandry & Fisheries" },
  { value: "Co-operation,_Textiles_and_Marketing_Department", label: "Co-operation, Textiles & Marketing" },
  { value: "Environment_Department", label: "Environment Department" },
  { value: "Finance_Department", label: "Finance Department" },
  { value: "Food,_Civil_Supplies_and_Consumer_Protection_Department", label: "Food, Civil Supplies & Consumer Protection" },
  { value: "General_Administration_Department", label: "General Administration Department" },
  { value: "Higher_and_Technical_Education_Department", label: "Higher & Technical Education" },
  { value: "Home_Department", label: "Home Department" },
  { value: "Housing_Department", label: "Housing Department" },
  { value: "Industries,_Energy_and_Labour_Department", label: "Industries, Energy & Labour" },
  { value: "Information_Technology_Department", label: "Information Technology Department" },
  { value: "Law_and_Judiciary_Department", label: "Law & Judiciary Department" },
  { value: "Marathi_Language_Department", label: "Marathi Language Department" },
  { value: "Medical_Education_and_Drugs_Department", label: "Medical Education & Drugs" },
  { value: "Minorities_Development_Department", label: "Minorities Development Department" },
  { value: "Other_Backward_Bahujan_Welfare_Department", label: "Other Backward Bahujan Welfare" },
  { value: "Parliamentary_Affairs_Department", label: "Parliamentary Affairs Department" },
  { value: "Persons_with_Disabilities_Welfare_Department", label: "Persons with Disabilities Welfare" },
  { value: "Planning_Department", label: "Planning Department" },
  { value: "Public_Health_Department", label: "Public Health Department" },
  { value: "Public_Works_Department", label: "Public Works Department" },
  { value: "Revenue_and_Forest_Department", label: "Revenue & Forest Department" },
  { value: "Rural_Development_Department", label: "Rural Development Department" },
  { value: "Skill_Development_and_Entrepreneurship_Department", label: "Skill Development & Entrepreneurship" },
  { value: "School_Education_and_Sports_Department", label: "School Education & Sports" },
  { value: "Social_Justice_and_Special_Assistance_Department", label: "Social Justice & Special Assistance" },
  { value: "Soil_and_Water_Conservation_Department", label: "Soil & Water Conservation" },
  { value: "Tourism_and_Cultural_Affairs_Department", label: "Tourism & Cultural Affairs" },
  { value: "Tribal_Development_Department", label: "Tribal Development Department" },
  { value: "Urban_Development_Department", label: "Urban Development Department" },
  { value: "Water_Resources_Department", label: "Water Resources Department" },
  { value: "Water_Supply_and_Sanitation_Department", label: "Water Supply & Sanitation" },
  { value: "Women_and_Child_Development_Department", label: "Women & Child Development" }
];

export default function DraftInputCard({
  prompt,
  setPrompt,
  language,
  setLanguage,
  department,
  setDepartment,
  onGenerate,
  loading,
  onReset
}) {
  const { t, siteLanguage } = useLanguage();
  const isMr = siteLanguage === 'mr';

  const handleClear = () => {
    if (window.confirm(t('draft_clear_confirm'))) {
      onReset();
    }
  };

  return (
    <div style={{
      background: 'var(--paper)',
      border: '2px solid var(--ink)',
      borderRadius: '12px',
      padding: '29px',
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
          <h3 style={{ margin: '0 0 4px 0' }}>
            {t('draft_brief_title')}
          </h3>
          <p style={{ margin: 0, fontSize: isMr ? '17px' : '15px', color: '#666' }}>
            {t('draft_brief_desc')}
          </p>
        </div>
        {onReset && (
          <button
            type="button"
            onClick={handleClear}
            className="btn btn-sm btn-ghost"
          >
            {t('draft_clear_fields')}
          </button>
        )}
      </div>

      {/* Main Form Fields Layout: Two Columns (Left: Textarea & Examples, Right: Parameters) */}
      <div className="draft-input-grid">
        {/* Left Sub-Column: Textarea and Example Briefs */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label style={{ display: 'block', fontSize: isMr ? '18px' : '16px', fontWeight: 700 }}>
              {t('draft_describe_label')}
            </label>
            <textarea
              rows={4}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder={t('draft_describe_placeholder')}
              style={{
                width: '100%',
                padding: '14px',
                border: '2px solid var(--ink)',
                borderRadius: '8px',
                fontFamily: 'inherit',
                fontSize: isMr ? '18px' : '16px',
                resize: 'none',
                boxSizing: 'border-box'
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: isMr ? '16px' : '14px', fontWeight: 700, color: '#666', marginBottom: '10px' }}>
              {t('draft_try_examples')}
            </label>
            <div className="example-brief-grid">
              {EXAMPLE_PROMPTS.map((ex, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => setPrompt(ex)}
                  className="example-brief-card"
                >
                  <IconLightbulb />
                  <span className="example-brief-card-text">{ex}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Right Sub-Column: Language, Reference File, and Action Buttons */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Department Selector */}
          <div>
            <label style={{ display: 'block', fontSize: isMr ? '18px' : '16px', fontWeight: 700, marginBottom: '8px' }}>
              {t('draft_issuing_dept')}
            </label>
            <select
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              style={{
                width: '100%',
                padding: '12px 14px',
                borderRadius: '8px',
                border: '2px solid var(--ink)',
                background: '#fff',
                color: department ? 'var(--ink)' : '#6b7280',
                fontWeight: 'bold',
                fontSize: isMr ? '17px' : '15px',
                cursor: 'pointer',
                outline: 'none',
                boxShadow: '0 2px 0 var(--ink)'
              }}
            >
              <option value="" disabled>{t('draft_select_dept')}</option>
              {DEPARTMENTS.map((dept) => (
                <option key={dept.value} value={dept.value}>
                  {dept.label}
                </option>
              ))}
            </select>
          </div>

          {/* Language Selector — grouped tightly with its label to read as one control */}
          <div style={{
            border: '1.5px solid var(--line)',
            borderRadius: '10px',
            padding: '14px',
            background: '#fbfaf7'
          }}>
            <label style={{ display: 'block', fontSize: isMr ? '18px' : '16px', fontWeight: 700, marginBottom: '10px' }}>
              {t('draft_output_lang')}
            </label>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                type="button"
                onClick={() => setLanguage('English')}
                className={`btn btn-sm ${language === 'English' ? 'btn-primary' : 'btn-secondary'}`}
                style={{ flex: 1 }}
              >
                {t('draft_lang_english')}
              </button>
              <button
                type="button"
                onClick={() => setLanguage('Marathi')}
                className={`btn btn-sm ${language === 'Marathi' ? 'btn-primary' : 'btn-secondary'}`}
                style={{ flex: 1 }}
              >
                {t('draft_lang_marathi')}
              </button>
            </div>
          </div>

          {/* Generate Action Button — heaviest element on the panel */}
          <motion.button
            whileTap={{ scale: 0.98 }}
            type="button"
            onClick={onGenerate}
            disabled={loading || !prompt.trim() || !department}
            className="btn btn-primary"
            style={{ width: '100%', minHeight: '56px', fontSize: '15px' }}
          >
            {loading ? t('draft_generating') : t('draft_generate_btn')}
          </motion.button>
        </div>
      </div>
    </div>
  );
}
