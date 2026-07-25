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

export default function Analyze() {
  const [title, setTitle] = useState("");
  const [department, setDepartment] = useState("Higher and Technical Education Department");
  const [language, setLanguage] = useState("en");
  const [bodyText, setBodyText] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [report, setReport] = useState(null);

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
        <div className="eyebrow">Upload &amp; Analyze</div>
        <h1 className="page-title">Draft Analysis</h1>
        <p className="page-sub">
          Paste a draft Government Resolution. NIRN.AI checks it against the
          Manual of Office Procedure, resolves every citation, and flags
          conflicts with existing GRs across departments.
        </p>
      </header>

      <div className="analyze-grid">
        {/* ---------------- Left: the draft form ---------------- */}
        <form className="panel" onSubmit={runAnalysis}>
          <div className="panel-head">
            <span className="panel-title">Draft GR</span>
            <button type="button" className="btn btn-ghost" onClick={loadSample}
                    style={{ padding: "8px 14px", fontSize: 12 }}>
              Load sample
            </button>
          </div>
          <div className="panel-body">
            <div className="field">
              <label htmlFor="title">Title</label>
              <input id="title" value={title}
                     onChange={(e) => setTitle(e.target.value)}
                     placeholder="e.g. Revision of lateral entry intake" required />
            </div>

            <div className="field-row">
              <div className="field">
                <label htmlFor="dept">Department</label>
                <input id="dept" value={department}
                       onChange={(e) => setDepartment(e.target.value)} required />
              </div>
              <div className="field">
                <label htmlFor="lang">Language</label>
                <select id="lang" value={language}
                        onChange={(e) => setLanguage(e.target.value)}>
                  <option value="en">English</option>
                  <option value="mr">Marathi</option>
                </select>
              </div>
            </div>

            <div className="field">
              <label htmlFor="body">Draft text</label>
              <textarea id="body" value={bodyText}
                        onChange={(e) => setBodyText(e.target.value)}
                        placeholder="Paste the full draft GR here..." required />
            </div>

            <div className="btn-row">
              <button className="btn btn-red" type="submit" disabled={loading}>
                {loading ? <span className="spinner" /> : "Analyze draft →"}
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
              <p>The analysis report appears here.<br />
                 Load the sample draft to see it in action.</p>
            </div>
          )}

          {loading && (
            <div className="empty-state">
              <div className="big"><span className="spinner" /></div>
              <p>Running all four checks…</p>
            </div>
          )}

          {report && <Report report={report} />}
        </section>
      </div>
    </main>
  );
}

function Report({ report }) {
  const s = report.summary;
  return (
    <>
      <div className={`status-banner status-${s.overall_status}`}>
        <span className="status-dot" />
        {STATUS_TEXT[s.overall_status] ?? s.overall_status}
      </div>

      <div className="summary-cards">
        <SummaryCard num={s.template_error_count + s.template_warning_count} label="Template issues" />
        <SummaryCard num={s.reference_count} label="References found" />
        <SummaryCard num={s.unresolved_reference_count} label="Unresolved refs" />
        <SummaryCard num={s.conflict_count} label="Conflicts" />
      </div>

      <ResultSection title="Template compliance" items={report.template_issues}
                     emptyText="All Manual of Office Procedure rules passed."
                     render={(issue) => (
        <div className="result-item" key={issue.rule_id}>
          <span className={`badge badge-${issue.severity}`}>{issue.severity}</span>
          <span className="mono">{issue.rule_id}</span>
          <div className="ri-msg">{issue.message}</div>
          {issue.suggestion && <div className="ri-sub">Fix: {issue.suggestion}</div>}
        </div>
      )} />

      <ResultSection title="References" items={report.references}
                     emptyText="No GR citations found in the draft."
                     render={(ref, i) => (
        <div className="result-item" key={i}>
          <span className={`badge badge-${ref.found_in_corpus ? ref.status : "unknown"}`}>
            {ref.found_in_corpus ? ref.status.replace("_", " ") : "not found"}
          </span>
          <span className="mono">{ref.raw_text}</span>
          {ref.corpus_title && <div className="ri-sub">{ref.corpus_title}</div>}
        </div>
      )} />

      <ResultSection title="Cross-departmental conflicts" items={report.conflicts}
                     emptyText="No conflicts detected with existing GRs."
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

      <ResultSection title="Bilingual terminology" items={report.terms}
                     emptyText="No terminology mappings produced."
                     render={(t, i) => (
        <div className="result-item" key={i}>
          <span className={`badge ${t.consistent_with_corpus ? "badge-ok" : "badge-warning"}`}>
            {t.consistent_with_corpus ? "consistent" : "check"}
          </span>
          <strong>{t.source_term}</strong> → {t.target_term}
          {t.note && <div className="ri-sub">{t.note}</div>}
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
