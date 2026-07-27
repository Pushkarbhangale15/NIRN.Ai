import { useState } from "react";
import { api } from "../api.js";

const SAMPLE_GR = `Government of Maharashtra
Higher and Technical Education Department
Government Resolution No. TEM-2024/CR-118/TE-1
Mantralaya, Mumbai 400 032
Dated: 14.03.2024

Preamble:
In pursuance of GR No CTC-2019/Pr.Kra.252/TE-04, dated 02.07.2019, and having
regard to representations received from institutions, the Government has
reconsidered the matter of lateral entry intake.

Government Resolution:
1. The lateral entry intake in Government and aided technical institutions shall
   be fixed at fifteen percent of the sanctioned intake of the first-year course.
2. Institutions shall report compliance to the Directorate within thirty days.

By order and in the name of the Governor of Maharashtra,
Under Secretary to Government`;

const STATUS_TEXT = {
  clean: "Clean — ready to issue",
  needs_review: "Needs review",
  blocked: "Blocked — resolve issues before issuing",
};

import { useLanguage } from "../LanguageContext.jsx";

export default function Analyze() {
  const [title, setTitle] = useState("");
  const [department, setDepartment] = useState("Higher and Technical Education Department");
  const [language, setLanguage] = useState("en");
  const [bodyText, setBodyText] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [report, setReport] = useState(null);
  const { t } = useLanguage();

  const loadSample = () => {
    setTitle("Revision of lateral entry intake");
    setBodyText(SAMPLE_GR);
    setError("");
  };

  const runAnalysis = async (e) => {
    e.preventDefault();
    setError("");
    setReport(null);
    setLoading(true);
    try {
      const draft = await api.createDraft({
        title, department, body_text: bodyText, language,
      });
      const result = await api.analyze(draft.id);
      setReport(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="container">
      <header className="page-head">
        <div className="eyebrow">{t('analyze_eyebrow')}</div>
        <h1 className="page-title">{t('analyze_title')}</h1>
        <p className="page-sub">
          {t('analyze_sub')}
        </p>
      </header>

      <div className="analyze-grid">
        {/* ---------------- Left: the draft form ---------------- */}
        <form className="panel" onSubmit={runAnalysis} style={{ position: "sticky", top: "100px", height: "fit-content" }}>
          <div className="panel-head">
            <span className="panel-title">{t('analyze_draft_title')}</span>
            <button type="button" className="btn btn-ghost" onClick={loadSample}
                    style={{ padding: "8px 14px", fontSize: 12 }}>
              {t('analyze_load_sample')}
            </button>
          </div>
          <div className="panel-body">
            <div className="field">
              <label htmlFor="title">{t('analyze_label_title')}</label>
              <input id="title" value={title}
                     onChange={(e) => setTitle(e.target.value)}
                     placeholder="e.g. Revision of lateral entry intake" required />
            </div>

            <div className="field-row">
              <div className="field">
                <label htmlFor="dept">{t('analyze_label_dept')}</label>
                <input id="dept" value={department}
                       onChange={(e) => setDepartment(e.target.value)} required />
              </div>
              <div className="field">
                <label htmlFor="lang">{t('analyze_label_lang')}</label>
                <select id="lang" value={language}
                        onChange={(e) => setLanguage(e.target.value)}>
                  <option value="en">English</option>
                  <option value="mr">Marathi</option>
                </select>
              </div>
            </div>

            <div className="field">
              <label htmlFor="body">{t('analyze_label_body')}</label>
              <textarea id="body" value={bodyText}
                        onChange={(e) => setBodyText(e.target.value)}
                        placeholder="Paste the full draft GR here..." required />
            </div>

            <div className="btn-row">
              <button className="btn btn-red" type="submit" disabled={loading}>
                {loading ? <span className="spinner" /> : t('analyze_btn')}
              </button>
            </div>
          </div>
        </form>

        {/* ---------------- Right: the report ---------------- */}
        <section>
          {error && <div className="error-box">{error}</div>}

          {!report && !loading && !error && (
            <div className="empty-state">
              <div className="big">📋</div>
              <p>{t('analyze_empty')}</p>
            </div>
          )}

          {loading && (
            <div className="empty-state">
              <div className="big"><span className="spinner" /></div>
              <p>{t('analyze_running')}</p>
            </div>
          )}

          {report && <Report report={report} t={t} />}
        </section>
      </div>
    </main>
  );
}

function Report({ report, t }) {
  const s = report.summary;
  
  const getStatusText = (status) => {
    if (status === 'clean') return t('analyze_status_clean');
    if (status === 'needs_review') return t('analyze_status_review');
    if (status === 'blocked') return t('analyze_status_blocked');
    return status;
  };

  return (
    <>
      <div className={`status-banner status-${s.overall_status}`}>
        <span className="status-dot" />
        {getStatusText(s.overall_status)}
      </div>

      <div className="summary-cards">
        <SummaryCard num={s.template_error_count + s.template_warning_count} label={t('analyze_card_template')} />
        <SummaryCard num={s.reference_count} label={t('analyze_card_ref')} />
        <SummaryCard num={s.unresolved_reference_count} label={t('analyze_card_unresolved')} />
        <SummaryCard num={s.conflict_count} label={t('analyze_card_conflict')} />
      </div>

      <ResultSection title={t('analyze_sec_template')} items={report.template_issues}
                     emptyText={t('analyze_sec_template_empty')}
                     render={(issue) => (
        <div className="result-item" key={issue.rule_id}>
          <span className={`badge badge-${issue.severity}`}>{issue.severity}</span>
          <span className="mono">{issue.rule_id}</span>
          <div className="ri-msg">{issue.message}</div>
          {issue.suggestion && <div className="ri-sub">{t('analyze_fix')} {issue.suggestion}</div>}
        </div>
      )} />

      <ResultSection title={t('analyze_sec_ref')} items={report.references}
                     emptyText={t('analyze_sec_ref_empty')}
                     render={(ref, i) => (
        <div className="result-item" key={i}>
          <span className={`badge badge-${ref.found_in_corpus ? ref.status : "unknown"}`}>
            {ref.found_in_corpus ? ref.status.replace("_", " ") : "not found"}
          </span>
          <span className="mono">{ref.raw_text}</span>
          {ref.corpus_title && <div className="ri-sub">{ref.corpus_title}</div>}
        </div>
      )} />

      <ResultSection title={t('analyze_sec_conflict')} items={report.conflicts}
                     emptyText={t('analyze_sec_conflict_empty')}
                     render={(c, i) => (
        <div className="result-item" key={i}>
          <span className={`badge badge-${c.relation}`}>{c.relation}</span>
          <strong>{c.existing_gr_title}</strong>
          <div className="ri-sub">{c.existing_department} · <span className="mono">{c.existing_gr_id}</span></div>

          <div className="clause-pair">
            <div className="clause">
              <span className="clause-tag">Draft clause</span>
              {c.draft_clause}
            </div>
            <div className="clause">
              <span className="clause-tag">Existing clause</span>
              {c.existing_clause}
            </div>
          </div>

          <div className="ri-sub" style={{ marginTop: 10 }}>{c.justification}</div>
          <div className="confidence-bar">
            <div className="confidence-fill" style={{ width: `${c.confidence * 100}%` }} />
          </div>
          <div className="ri-sub">Confidence: {(c.confidence * 100).toFixed(0)}%</div>
        </div>
      )} />

      <ResultSection title={t('analyze_sec_terms')} items={report.terms}
                     emptyText={t('analyze_sec_terms_empty')}
                     render={(tInfo, i) => (
        <div className="result-item" key={i}>
          <span className={`badge ${tInfo.consistent_with_corpus ? "badge-ok" : "badge-warning"}`}>
            {tInfo.consistent_with_corpus ? "consistent" : "check"}
          </span>
          <strong>{tInfo.source_term}</strong> → {tInfo.target_term}
          {tInfo.note && <div className="ri-sub">{tInfo.note}</div>}
        </div>
      )} />
    </>
  );
}

function SummaryCard({ num, label }) {
  return (
    <div className="s-card">
      <div className="s-num">{num}</div>
      <div className="s-label">{label}</div>
    </div>
  );
}

function ResultSection({ title, items, emptyText, render }) {
  return (
    <div className="result-section panel">
      <div className="panel-head">
        <span className="panel-title">{title}</span>
        <span className="mono">{items.length}</span>
      </div>
      <div className="panel-body">
        {items.length === 0
          ? <div className="ri-sub">{emptyText}</div>
          : items.map(render)}
      </div>
    </div>
  );
}
