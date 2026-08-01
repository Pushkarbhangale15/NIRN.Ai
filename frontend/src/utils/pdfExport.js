/**
 * pdfExport.js — builds and downloads Conflict Detection Report PDFs.
 *
 * Renders a hidden, formally-styled HTML document and rasterizes it with
 * html2pdf.js (html2canvas + jsPDF under the hood). Going through the DOM
 * instead of jsPDF's text API means Devanagari (Marathi) text renders
 * correctly with zero font embedding — the browser's own font stack
 * handles the glyphs.
 */

import html2pdf from "html2pdf.js";

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));
}



function formatDateTime(date) {
  return date.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function filenameTimestamp(date) {
  return date.toISOString().replace(/[:.]/g, "-").slice(0, 19);
}

const REPORT_STYLES = `
  * { box-sizing: border-box; }
  .nirn-pdf-report {
    font-family: Georgia, 'Times New Roman', 'Noto Sans Devanagari', 'Nirmala UI', 'Mangal', serif;
    color: #1a1a1a;
    width: 720px;
    padding: 8px 4px;
    line-height: 1.55;
    font-size: 13px;
  }
  .nirn-pdf-report h1.nirn-title {
    font-size: 21px;
    text-align: center;
    margin: 0 0 4px 0;
    border-bottom: 3px double #1a1a1a;
    padding-bottom: 14px;
  }
  .nirn-pdf-report .nirn-meta-line {
    text-align: center;
    font-size: 12px;
    color: #444;
    margin-bottom: 18px;
  }
  .nirn-pdf-report .nirn-meta-table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 18px;
    font-size: 12.5px;
  }
  .nirn-pdf-report .nirn-meta-table td {
    border: 1px solid #cbd5e1;
    padding: 6px 10px;
  }
  .nirn-pdf-report .nirn-meta-table td.nirn-meta-label {
    font-weight: bold;
    background: #f3f4f6;
    width: 160px;
  }
  .nirn-pdf-report h2.nirn-section {
    font-size: 15px;
    background: #1a1a1a;
    color: #fff;
    padding: 7px 12px;
    margin: 22px 0 10px 0;
    border-radius: 3px;
  }
  .nirn-pdf-report .nirn-body-text {
    white-space: pre-wrap;
    background: #fafafa;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    padding: 14px 16px;
    font-size: 13px;
    text-align: justify;
  }
  .nirn-pdf-report .nirn-summary-row {
    display: flex;
    gap: 14px;
    margin-bottom: 6px;
  }
  .nirn-pdf-report .nirn-summary-box {
    flex: 1;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 10px 12px;
    text-align: center;
  }
  .nirn-pdf-report .nirn-summary-box .nirn-num {
    font-size: 20px;
    font-weight: bold;
  }
  .nirn-pdf-report .nirn-summary-box .nirn-label {
    font-size: 11px;
    color: #555;
    text-transform: uppercase;
    letter-spacing: 0.4px;
  }
  .nirn-pdf-report .nirn-conflict-block {
    border: 1px solid #9ca3af;
    border-left: 5px solid #e6391e;
    border-radius: 4px;
    padding: 12px 14px;
    margin-bottom: 14px;
    page-break-inside: avoid;
  }
  .nirn-pdf-report .nirn-conflict-block .nirn-conflict-heading {
    font-weight: bold;
    font-size: 13.5px;
    margin-bottom: 8px;
    display: flex;
    justify-content: space-between;
  }
  .nirn-pdf-report .nirn-field-label {
    font-weight: bold;
    font-size: 11.5px;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    color: #444;
    margin-top: 8px;
  }
  .nirn-pdf-report .nirn-clause-box {
    padding: 6px 9px;
    border-radius: 3px;
    font-style: italic;
    font-size: 12.5px;
    margin-top: 2px;
  }
  .nirn-pdf-report .nirn-clause-box.nirn-draft-clause {
    background: #fffbe6;
    border-left: 3px solid #f2b01d;
  }
  .nirn-pdf-report .nirn-clause-box.nirn-existing-clause {
    background: #fff1f0;
    border-left: 3px solid #e6391e;
  }
  .nirn-pdf-report .nirn-tag-row {
    display: flex;
    gap: 8px;
    margin-top: 6px;
    flex-wrap: wrap;
  }
  .nirn-pdf-report .nirn-tag {
    font-size: 11px;
    font-weight: bold;
    padding: 3px 9px;
    border-radius: 10px;
    border: 1px solid #1a1a1a;
  }
  .nirn-pdf-report table.nirn-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    margin-bottom: 10px;
  }
  .nirn-pdf-report table.nirn-table th,
  .nirn-pdf-report table.nirn-table td {
    border: 1px solid #d1d5db;
    padding: 6px 8px;
    text-align: left;
    vertical-align: top;
  }
  .nirn-pdf-report table.nirn-table th {
    background: #f3f4f6;
  }
  .nirn-pdf-report .nirn-pass { color: #166534; font-weight: bold; }
  .nirn-pdf-report .nirn-fail { color: #b91c1c; font-weight: bold; }
  .nirn-pdf-report .nirn-warn { color: #92400e; font-weight: bold; }
  .nirn-pdf-report .nirn-footer {
    margin-top: 24px;
    padding-top: 10px;
    border-top: 1px solid #9ca3af;
    text-align: center;
    font-size: 11px;
    color: #666;
  }
`;

function conflictBlockHtml(conflict, index, headingPrefix = "Conflict") {
  const draftSide = conflict.draft_clause_ref ? `${conflict.draft_clause_ref} of this draft` : "this draft";
  const sourceSide = conflict.conflicting_gr_id
    ? (conflict.source_clause_ref ? `${conflict.source_clause_ref} of GR ${conflict.conflicting_gr_id}` : `GR ${conflict.conflicting_gr_id}`)
    : "the referenced GR";

  return `
    <div class="nirn-conflict-block">
      <div class="nirn-conflict-heading">
        <span>${escapeHtml(headingPrefix)} ${index != null ? `#${index + 1}` : ""} — <span style="font-family:monospace;">${escapeHtml(conflict.conflict_ref || "—")}</span></span>
        <span>GR ${escapeHtml(conflict.conflicting_gr_id || "—")}</span>
      </div>

      <div class="nirn-field-label">Location</div>
      <div>${escapeHtml(draftSide)} &harr; ${escapeHtml(sourceSide)}</div>

      <div class="nirn-field-label">Draft Clause (source of conflict)</div>
      <div class="nirn-clause-box nirn-draft-clause">${escapeHtml(conflict.draft_excerpt || "—")}</div>

      <div class="nirn-field-label">Existing GR</div>
      <div>${escapeHtml(conflict.source_gr_title || "Untitled")}${conflict.source_gr_date ? ` — ${escapeHtml(conflict.source_gr_date)}` : ""} (GR #${escapeHtml(conflict.conflicting_gr_id || "—")})</div>

      <div class="nirn-field-label">Existing Clause (conflicting text)</div>
      <div class="nirn-clause-box nirn-existing-clause">${escapeHtml(conflict.conflicting_text)}</div>

      <div class="nirn-tag-row">
        <span class="nirn-tag">Detected by: ${escapeHtml(conflict.detected_by === "rule_engine" ? "Rule Engine" : "LLM Verifier")}</span>
        ${conflict.severity ? `<span class="nirn-tag">Severity: ${escapeHtml(conflict.severity)}</span>` : ""}
        ${conflict.relation ? `<span class="nirn-tag">Relation: ${escapeHtml(conflict.relation)}</span>` : ""}
      </div>

      <div class="nirn-field-label">Justification</div>
      <div>${escapeHtml(conflict.justification)}</div>
    </div>
  `;
}

function templateComplianceTableHtml(templateIssues = []) {
  if (!templateIssues.length) {
    return `<p style="font-size:12.5px;">All Manual of Office Procedure rules passed — no template issues found.</p>`;
  }
  const rows = templateIssues.map((issue) => `
    <tr>
      <td>${escapeHtml(issue.rule_id)}</td>
      <td class="${issue.severity === "error" ? "nirn-fail" : "nirn-warn"}">
        ${issue.severity === "error" ? "FAIL" : "WARN"}
      </td>
      <td>${escapeHtml(issue.message)}</td>
      <td>${escapeHtml(issue.suggestion || "—")}</td>
    </tr>
  `).join("");
  return `
    <table class="nirn-table">
      <thead>
        <tr><th>Rule</th><th>Status</th><th>Description</th><th>Suggestion</th></tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function referencesTableHtml(references = []) {
  if (!references.length) {
    return `<p style="font-size:12.5px;">No GR citations were found in this draft.</p>`;
  }
  const rows = references.map((ref) => `
    <tr>
      <td>${escapeHtml(ref.raw_text)}</td>
      <td class="${ref.found_in_corpus ? "nirn-pass" : "nirn-fail"}">
        ${ref.found_in_corpus ? "Resolved" : "Unresolved"}
      </td>
      <td>${escapeHtml(ref.corpus_gr_id || ref.gr_number || "—")}</td>
      <td>${escapeHtml(ref.corpus_title || "—")}</td>
    </tr>
  `).join("");
  return `
    <table class="nirn-table">
      <thead>
        <tr><th>Citation</th><th>Status</th><th>Matched GR ID</th><th>Matched Title</th></tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function buildIndividualReportHtml(draftText, conflict, metadata, now) {
  return `
    <div class="nirn-pdf-report">
      <style>${REPORT_STYLES}</style>
      <h1 class="nirn-title">NIRN.Ai — Conflict Detection Report</h1>
      <div class="nirn-meta-line">Analysis performed on ${formatDateTime(now)}</div>

      <table class="nirn-meta-table">
        <tr><td class="nirn-meta-label">Draft Title</td><td>${escapeHtml(metadata.title || "Untitled Draft")}</td></tr>
        <tr><td class="nirn-meta-label">Department</td><td>${escapeHtml((metadata.department || "").replace(/_/g, " "))}</td></tr>
        <tr><td class="nirn-meta-label">Language</td><td>${escapeHtml(metadata.language || "English")}</td></tr>
        ${metadata.grId ? `<tr><td class="nirn-meta-label">Draft ID</td><td>${escapeHtml(metadata.grId)}</td></tr>` : ""}
      </table>

      <h2 class="nirn-section">Section 1 — Draft Government Resolution</h2>
      <div class="nirn-body-text">${escapeHtml(draftText || "No draft text available.")}</div>

      <h2 class="nirn-section">Section 2 — Conflict Detected</h2>
      ${conflictBlockHtml(conflict, null, "Conflict")}

      <div class="nirn-footer">Generated by NIRN.Ai | VJTI Mumbai | ${formatDateTime(now)}</div>
    </div>
  `;
}

function buildFullReportHtml(draftText, conflicts, metadata, now) {
  return `
    <div class="nirn-pdf-report">
      <style>${REPORT_STYLES}</style>
      <h1 class="nirn-title">NIRN.Ai — Government Resolution Conflict Analysis Report</h1>
      <div class="nirn-meta-line">Report generated on ${formatDateTime(now)}</div>

      <table class="nirn-meta-table">
        <tr><td class="nirn-meta-label">Draft Title</td><td>${escapeHtml(metadata.title || "Untitled Draft")}</td></tr>
        <tr><td class="nirn-meta-label">Department</td><td>${escapeHtml((metadata.department || "").replace(/_/g, " "))}</td></tr>
        <tr><td class="nirn-meta-label">Language</td><td>${escapeHtml(metadata.language || "English")}</td></tr>
        <tr><td class="nirn-meta-label">Date Generated</td><td>${formatDateTime(now)}</td></tr>
        ${metadata.grId ? `<tr><td class="nirn-meta-label">Draft ID</td><td>${escapeHtml(metadata.grId)}</td></tr>` : ""}
      </table>

      <h2 class="nirn-section">Complete Draft Government Resolution</h2>
      <div class="nirn-body-text">${escapeHtml(draftText || "No draft text available.")}</div>

      <h2 class="nirn-section">Summary</h2>
      <div class="nirn-summary-row">
        <div class="nirn-summary-box">
          <div class="nirn-num">${conflicts.length}</div>
          <div class="nirn-label">Total Conflicts Found</div>
        </div>
      </div>

      <h2 class="nirn-section">All Detected Conflicts</h2>
      ${conflicts.length
        ? conflicts.map((c, i) => conflictBlockHtml(c, i)).join("")
        : `<p style="font-size:12.5px;">No conflicts were detected against the existing GR corpus.</p>`}

      <h2 class="nirn-section">MOP Template Compliance Summary</h2>
      ${templateComplianceTableHtml(metadata.templateIssues)}

      <h2 class="nirn-section">References Found &amp; Resolution Status</h2>
      ${referencesTableHtml(metadata.references)}
    </div>
  `;
}

async function renderHtmlToPdf(html, filename, repeatingFooter) {
  // Deliberately left detached from document.body. html2pdf.js clones
  // whatever node is passed to .from() into its own hidden capture
  // wrapper (position: absolute, height: auto, opacity: 0 ancestor) and
  // renders that clone — it never needs the source node to be attached,
  // and structural cloning + the embedded <style> tag still work once
  // the clone itself lands in the live document. Building it in memory
  // means nothing ever flashes on screen, and — critically — this
  // element carries no position/offset styling of its own, so nothing
  // conflicts with html2pdf's internal layout when it's cloned in.
  const container = document.createElement("div");
  container.style.background = "#fff";
  container.innerHTML = html;

  let chain = html2pdf()
    .set({
      margin: [12, 10, 16, 10],
      filename,
      image: { type: "jpeg", quality: 0.98 },
      html2canvas: { scale: 2, useCORS: true, backgroundColor: "#ffffff" },
      jsPDF: { unit: "mm", format: "a4", orientation: "portrait" },
      pagebreak: { mode: ["css", "legacy"], avoid: ".nirn-conflict-block" },
    })
    .from(container);

  if (repeatingFooter) {
    chain = chain.toPdf().get("pdf").then((pdf) => {
      const pageCount = pdf.internal.getNumberOfPages();
      const { width, height } = pdf.internal.pageSize;
      for (let i = 1; i <= pageCount; i++) {
        pdf.setPage(i);
        pdf.setFontSize(9);
        pdf.setTextColor(120, 120, 120);
        pdf.text(repeatingFooter, width / 2, height - 6, { align: "center" });
      }
    });
  }

  await chain.save();
}

/**
 * Generates and downloads a Conflict Detection Report PDF.
 *
 * @param {string} draftText - the full generated draft GR body text.
 * @param {object|object[]} conflicts - a single ConflictHit for an
 *   individual report, or the full array of ConflictHit for a full report.
 * @param {object} metadata
 * @param {"individual"|"full"} [metadata.reportType="individual"]
 * @param {string} [metadata.title] - draft title.
 * @param {string} [metadata.department] - issuing department.
 * @param {string} [metadata.language] - "English" | "Marathi".
 * @param {string} [metadata.grId] - draft/GR id.
 * @param {object[]} [metadata.templateIssues] - MOP issues (full report only).
 * @param {object[]} [metadata.references] - reference hits (full report only).
 * @param {object} [metadata.summary] - AnalysisSummary (full report only).
 */
export async function generateConflictPDF(draftText, conflicts, metadata = {}) {
  const now = new Date();
  const isFull = metadata.reportType === "full";

  const html = isFull
    ? buildFullReportHtml(draftText, Array.isArray(conflicts) ? conflicts : [conflicts].filter(Boolean), metadata, now)
    : buildIndividualReportHtml(draftText, Array.isArray(conflicts) ? conflicts[0] : conflicts, metadata, now);

  const filename = isFull
    ? `NIRN-Full-Conflict-Report-${filenameTimestamp(now)}.pdf`
    : `NIRN-${(Array.isArray(conflicts) ? conflicts[0] : conflicts)?.conflict_ref || "Conflict"}-${filenameTimestamp(now)}.pdf`;

  await renderHtmlToPdf(html, filename, isFull ? "NIRN.Ai | Confidential Draft Analysis" : null);
  return filename;
}

export default generateConflictPDF;
