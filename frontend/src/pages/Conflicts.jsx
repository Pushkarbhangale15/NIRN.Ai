import React, { useState } from "react";
import { useLanguage } from "../LanguageContext.jsx";
import { api } from "../api.js";

const DEPARTMENTS = [
  "General Administration Department",
  "Higher and Technical Education Department",
  "Revenue and Forest Department",
  "Rural Development Department",
  "Finance Department",
  "School Education and Sports Department",
  "Public Health Department"
];

const SAMPLE_GR_ENGLISH = `Government of Maharashtra
Higher and Technical Education Department
Mantralaya, Mumbai 400 032
Dated: 15.06.2026

Government Resolution No. TE-2026/CR-102/TE-2

Preamble:
To streamline procurement of laboratory instruments, this department has decided to revise funding guidelines...

Government Resolution:
1. All engineering institutions shall prohibit CSR funding entirely from private entities for lab instrumentation.
2. The District Collector shall approve all procurement tenders up to 50 lakhs directly.
3. The project implementation timeline must complete within 30 days of sanction.
4. Active guidelines shall reference Section 12 of the Act 1999.

By order and in the name of the Governor of Maharashtra,
Secretary to Government`;

export default function Conflicts() {
  const { t, siteLanguage } = useLanguage();
  const [title, setTitle] = useState("Revision of Lab Instrumentation Procurement");
  const [dept, setDept] = useState("Higher and Technical Education Department");
  const [lang, setLang] = useState("en");
  const [bodyText, setBodyText] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState([]);
  const [searched, setSearched] = useState(false);

  const loadSample = () => {
    setBodyText(SAMPLE_GR_ENGLISH);
  };

  const handleDetect = async () => {
    if (!bodyText.trim()) return;
    setLoading(true);
    setResults([]);
    setSearched(true);
    try {
      // Direct API call to the new conflicts endpoint
      const response = await fetch("/api/conflicts/detect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          department: dept,
          body_text: bodyText,
          language: lang
        })
      });
      if (response.ok) {
        const data = await response.json();
        setResults(data);
      } else {
        console.error("Conflict Detection API failed");
      }
    } catch (error) {
      console.error("Error during conflict detection:", error);
    } finally {
      setLoading(false);
    }
  };

  const getSeverityColor = (sev) => {
    switch (sev.toLowerCase()) {
      case "critical": return "badge-red";
      case "high": return "badge-red-outline";
      case "medium": return "badge-yellow";
      default: return "badge-blue";
    }
  };

  return (
    <div className="container" style={{ padding: "40px 32px", minHeight: "85vh" }}>
      <div style={{ marginBottom: "34px", borderBottom: "2px solid var(--ink)", paddingBottom: "20px" }}>
        <h1 className="display" style={{ fontSize: "3rem", margin: 0 }}>
          {siteLanguage === 'mr' ? 'संघर्ष शोधन' : 'Cross-Departmental Conflict Detection'}
        </h1>
        <p className="hero-sub" style={{ maxWidth: "800px", marginTop: "12px" }}>
          {siteLanguage === 'mr' 
            ? 'महाराष्ट्र शासनाच्या सर्व विभागांमधील शासन निर्णयांचे परस्परविरोधी नियम किंवा विसंगती स्वयंचलितपणे तपासा.'
            : 'Submit a draft GR to automatically check for regulatory, funding, timeline, or authority contradictions with all previously issued Maharashtra Government Resolutions.'}
        </p>
      </div>

      <div className="draft-workspace-grid" style={{ gap: "32px" }}>
        {/* Left Column - Input Panel */}
        <div className="card" style={{ padding: "24px", display: "flex", flexDirection: "column", gap: "20px", background: "var(--paper)", border: "2px solid var(--ink)", boxShadow: "4px 4px 0 var(--ink)" }}>
          <h3 style={{ margin: 0, fontSize: "1.25rem", borderBottom: "2px solid var(--ink)", paddingBottom: "10px" }}>
            {siteLanguage === 'mr' ? 'मसुदा तपशील' : 'Draft Details'}
          </h3>

          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            <label style={{ fontWeight: 600, fontSize: "12px", textTransform: "uppercase" }}>
              {siteLanguage === 'mr' ? 'शीर्षक' : 'Draft Title'}
            </label>
            <input 
              type="text" 
              value={title} 
              onChange={(e) => setTitle(e.target.value)}
              style={{ padding: "10px", border: "2px solid var(--ink)", borderRadius: "6px", background: "#fff" }}
            />
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            <label style={{ fontWeight: 600, fontSize: "12px", textTransform: "uppercase" }}>
              {siteLanguage === 'mr' ? 'विभाग' : 'Department'}
            </label>
            <select 
              value={dept} 
              onChange={(e) => setDept(e.target.value)}
              style={{ padding: "10px", border: "2px solid var(--ink)", borderRadius: "6px", background: "#fff" }}
            >
              {DEPARTMENTS.map(d => <option key={d} value={d}>{d}</option>)}
            </select>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            <label style={{ fontWeight: 600, fontSize: "12px", textTransform: "uppercase" }}>
              {siteLanguage === 'mr' ? 'भाषा' : 'Language'}
            </label>
            <div style={{ display: "flex", gap: "10px" }}>
              <button 
                className={`btn ${lang === 'en' ? 'btn-red' : 'btn-ghost'}`} 
                onClick={() => setLang('en')}
                style={{ flex: 1 }}
              >
                English
              </button>
              <button 
                className={`btn ${lang === 'mr' ? 'btn-red' : 'btn-ghost'}`} 
                onClick={() => setLang('mr')}
                style={{ flex: 1 }}
              >
                मराठी
              </button>
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <label style={{ fontWeight: 600, fontSize: "12px", textTransform: "uppercase" }}>
                {siteLanguage === 'mr' ? 'मसुदा मजकूर' : 'Draft Text'}
              </label>
              <button 
                className="btn btn-ghost" 
                onClick={loadSample}
                style={{ fontSize: "11px", padding: "4px 8px" }}
              >
                {siteLanguage === 'mr' ? 'नमुना मजकूर लोड करा' : 'Load Sample Draft'}
              </button>
            </div>
            <textarea 
              rows={12}
              value={bodyText}
              onChange={(e) => setBodyText(e.target.value)}
              placeholder={siteLanguage === 'mr' ? 'येथे मसुदा पेस्ट करा...' : 'Paste your draft GR here...'}
              style={{ padding: "12px", border: "2px solid var(--ink)", borderRadius: "6px", background: "#fff", resize: "vertical", fontFamily: "monospace", fontSize: "13px" }}
            />
          </div>

          <button 
            className="btn btn-red" 
            onClick={handleDetect} 
            disabled={loading || !bodyText.trim()}
            style={{ width: "100%", padding: "14px", fontWeight: "bold" }}
          >
            {loading ? (siteLanguage === 'mr' ? 'संघर्ष शोधत आहे...' : 'Detecting Conflicts...') : (siteLanguage === 'mr' ? 'संघर्ष शोधा →' : 'Detect Conflicts →')}
          </button>
        </div>

        {/* Center & Right Column Combined - Results View */}
        <div style={{ gridColumn: "span 2", display: "flex", flexDirection: "column", gap: "24px" }}>
          
          {/* Analysis Pipeline Progress */}
          <div className="card" style={{ padding: "20px", background: "var(--paper)", border: "2px solid var(--ink)", boxShadow: "4px 4px 0 var(--ink)", display: "flex", gap: "24px", alignItems: "center" }}>
            <div style={{ fontWeight: "bold", textTransform: "uppercase", fontSize: "12px", borderRight: "2px solid var(--ink)", paddingRight: "20px" }}>
              Pipeline Status
            </div>
            <div style={{ display: "flex", gap: "34px", flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span className="badge badge-blue" style={{ borderRadius: "50%", width: "20px", height: "20px", display: "inline-flex", alignItems: "center", justifyContent: "center", padding: 0 }}>1</span>
                <span style={{ fontWeight: 600, fontSize: "13px" }}>Rule Engine (Deterministic)</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span className="badge badge-yellow" style={{ borderRadius: "50%", width: "20px", height: "20px", display: "inline-flex", alignItems: "center", justifyContent: "center", padding: 0 }}>2</span>
                <span style={{ fontWeight: 600, fontSize: "13px" }}>LLM Verification (Ambiguous)</span>
              </div>
            </div>
          </div>

          {loading && (
            <div style={{ textAlign: "center", padding: "60px 0" }}>
              <div className="spinner" style={{ width: "40px", height: "40px", margin: "0 auto 20px" }} />
              <p style={{ fontWeight: "bold" }}>Running cross-departmental alignment scan...</p>
            </div>
          )}

          {!loading && !searched && (
            <div className="card" style={{ padding: "60px 0", textAlign: "center", border: "2px dashed var(--line)" }}>
              <div style={{ fontSize: "3rem", marginBottom: "16px" }}>🔍</div>
              <h3>Ready to Scan</h3>
              <p className="hero-sub" style={{ margin: "8px auto 0", maxWidth: "400px" }}>
                Provide a draft GR and launch the compliance scan to identify cross-departmental mismatches.
              </p>
            </div>
          )}

          {!loading && searched && results.length === 0 && (
            <div className="card" style={{ padding: "50px", background: "var(--cream)", border: "2px solid var(--ink)", boxShadow: "4px 4px 0 var(--ink)", textAlign: "center" }}>
              <div style={{ fontSize: "3rem", marginBottom: "16px" }}>✅</div>
              <h3 style={{ color: "green" }}>Clean Audit</h3>
              <p className="hero-sub" style={{ margin: "8px auto 0", maxWidth: "500px" }}>
                No policy, timeline, funding, or departmental conflicts detected across the entire active corpus!
              </p>
            </div>
          )}

          {!loading && searched && results.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={{ margin: 0 }}>
                  Flagged Conflicts ({results.length})
                </h3>
                <span className="badge badge-red" style={{ fontWeight: "bold" }}>Action Required</span>
              </div>

              {results.map((c, idx) => (
                <div 
                  key={idx} 
                  className="card" 
                  style={{ 
                    padding: "24px", 
                    background: "var(--paper)", 
                    border: "2px solid var(--ink)", 
                    boxShadow: "5px 5px 0 var(--ink)",
                    display: "flex",
                    flexDirection: "column",
                    gap: "16px"
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px" }}>
                    <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                      <span className="badge badge-blue" style={{ fontWeight: 600 }}>{c.category}</span>
                      <span className={`badge ${getSeverityColor(c.severity)}`} style={{ fontWeight: "bold" }}>{c.severity}</span>
                    </div>
                    <div style={{ fontSize: "13px", fontWeight: 600 }}>
                      Confidence: {(c.confidence * 100).toFixed(0)}%
                    </div>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px", marginTop: "10px" }}>
                    {/* Draft Clause */}
                    <div style={{ padding: "14px", border: "1.5px solid var(--ink)", borderRadius: "6px", background: "#fff" }}>
                      <div style={{ fontWeight: 600, fontSize: "11px", textTransform: "uppercase", marginBottom: "6px", color: "var(--red)" }}>
                        Draft GR Clause
                      </div>
                      <p style={{ margin: 0, fontSize: "13.5px", fontStyle: "italic" }}>"{c.draft_clause}"</p>
                    </div>

                    {/* Matched Clause */}
                    <div style={{ padding: "14px", border: "1.5px solid var(--ink)", borderRadius: "6px", background: "#fff" }}>
                      <div style={{ fontWeight: 600, fontSize: "11px", textTransform: "uppercase", marginBottom: "6px", color: "var(--blue)" }}>
                        Existing GR: {c.matched_gr}
                      </div>
                      <p style={{ margin: 0, fontSize: "13.5px", fontStyle: "italic" }}>"{c.matched_clause}"</p>
                    </div>
                  </div>

                  <div style={{ borderTop: "1.5px solid var(--line)", paddingTop: "14px", display: "flex", flexDirection: "column", gap: "8px" }}>
                    <div>
                      <span style={{ fontWeight: "bold", fontSize: "13px" }}>Reason: </span>
                      <span style={{ fontSize: "13.5px", color: "var(--ink-soft)" }}>{c.reason}</span>
                    </div>
                    <div>
                      <span style={{ fontWeight: "bold", fontSize: "13px" }}>Recommendation: </span>
                      <span style={{ fontSize: "13.5px", color: "var(--ink)" }}>{c.recommendation}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
