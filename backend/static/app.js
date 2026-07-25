// =====================================================================
// NIRN.Ai Client Application Logic — Vanilla ES6 JavaScript
// =====================================================================

const API_BASE = "";
let currentSessionId = null;

// On Page Load
document.addEventListener("DOMContentLoaded", () => {
    // Initialize Lucide icons
    lucide.createIcons();
    
    // Check Backend connection status
    checkHealth();
    
    // Set standard mock text into editor as starter
    generateMockDraft();
});

// Health check to verify connection to FastAPI backend
async function checkHealth() {
    try {
        const response = await fetch(`${API_BASE}/health`);
        const data = await response.json();
        
        const dot = document.getElementById("status-dot");
        const label = document.getElementById("status-text");
        
        if (data.status === "ok") {
            dot.className = "status-indicator active";
            label.innerText = `Vector DB: Connected | LLM: Connected`;
        } else {
            dot.className = "status-indicator";
            label.innerText = "System Offline";
        }
    } catch (e) {
        console.error("Status check failed:", e);
        document.getElementById("status-dot").className = "status-indicator";
        document.getElementById("status-text").innerText = "Connection Failed";
    }
}

// =====================================================================
// Workspace Tab Navigation
// =====================================================================
function switchTab(tabId) {
    // Deactivate all navigation buttons and tab content blocks
    document.querySelectorAll(".nav-btn").forEach(btn => btn.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(tab => tab.classList.remove("active"));
    
    // Activate clicked navigation button and tab block
    document.getElementById(`tab-${tabId}-btn`).classList.add("active");
    document.getElementById(`tab-${tabId}`).classList.add("active");
}

function switchResultTab(tabName) {
    document.querySelectorAll(".results-tab-btn").forEach(btn => btn.classList.remove("active"));
    document.querySelectorAll(".results-section").forEach(sec => sec.classList.remove("active"));
    
    // Activate target sub-tab
    event.currentTarget.classList.add("active");
    document.getElementById(`sec-${tabName}`).classList.add("active");
}

// =====================================================================
// Tab 1: Draft Editor & Real-time RAG Alignment Analysis
// =====================================================================
function generateMockDraft() {
    const defaultText = `GOVERNMENT OF MAHARASHTRA
Higher and Technical Education Department
Government Resolution No. TE-2026/Lateral-09/Desk-12
Mantralaya, Mumbai 400032.
Dated: 24-07-2026

Preamble:
In recent years, the demand for technology education in Maharashtra has grown. It is necessary to align the rules for lateral admission in undergraduate professional courses. High-performing students from polytechnics seek admissions directly in the second year. To clarify the process and resolve the discrepancies with earlier departmental policies, the government announces this resolution.

Government Resolution:
1. The sanctioned intake capacity for lateral entry (direct second-year admission) in all engineering colleges shall be set at twenty percent of the first-year intake.
2. An officer from the Rural Development Department shall approve the recruitment of faculty.
3. This regulation is aligned with GR No TEM-2021/CR-45/TE-1 which remains in force.
4. Any student who fails to secure fifty percent marks in polytechnic shall not be allowed to apply.

By order and in the name of the Governor of Maharashtra.

Under Secretary, Government of Maharashtra.`;

    document.getElementById("draft-title").value = "Revision of lateral entry intake limits";
    document.getElementById("draft-dept").value = "Higher and Technical Education Department";
    document.getElementById("draft-body").value = defaultText;
}

async function analyzeDraft() {
    const title = document.getElementById("draft-title").value;
    const department = document.getElementById("draft-dept").value;
    const body_text = document.getElementById("draft-body").value;
    
    // 1. Submit the draft to the CRUD store first
    try {
        const createRes = await fetch(`${API_BASE}/api/drafts`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                title,
                department,
                body_text,
                language: "en"
            })
        });
        
        if (!createRes.ok) throw new Error("Failed to save draft");
        const draft = await createRes.json();
        
        // 2. Fetch the analysis report
        const reportRes = await fetch(`${API_BASE}/api/analysis/${draft.id}`, {
            method: "POST"
        });
        
        if (!reportRes.ok) throw new Error("Failed to analyze draft");
        const report = await reportRes.json();
        
        // Update Metrics Cards
        document.getElementById("count-errors").innerText = report.summary.template_error_count;
        document.getElementById("count-conflicts").innerText = report.summary.conflict_count;
        document.getElementById("count-references").innerText = report.summary.reference_count;
        
        // Update Overall Status Badge
        const badge = document.getElementById("overall-status-badge");
        badge.className = `status-badge ${report.summary.overall_status}`;
        badge.innerText = report.summary.overall_status.replace("_", " ");
        
        // Update Sections lists
        renderTemplateIssues(report.template_issues);
        renderConflicts(report.conflicts);
        renderCitations(report.references);
        renderTerminology(report.terms);
        
    } catch (e) {
        console.error(e);
        alert("Draft analysis failed. Make sure FastAPI server is running.");
    }
}

function renderTemplateIssues(issues) {
    const container = document.getElementById("sec-errors");
    if (!issues || issues.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i data-lucide="check-circle" style="color: var(--color-success)"></i>
                <p>Perfect! The draft complies fully with the Maharashtra Manual of Office Procedure.</p>
            </div>`;
        lucide.createIcons();
        return;
    }
    
    let html = "";
    issues.forEach(issue => {
        html += `
            <div class="issue-item">
                <div class="issue-title ${issue.severity}">
                    <i data-lucide="alert-triangle"></i> [${issue.rule_id}] ${issue.message}
                </div>
                ${issue.suggestion ? `<div class="issue-suggestion">Suggestion: ${issue.suggestion}</div>` : ""}
            </div>`;
    });
    container.innerHTML = html;
    lucide.createIcons();
}

function renderConflicts(conflicts) {
    const container = document.getElementById("sec-conflicts");
    if (!conflicts || conflicts.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i data-lucide="shield-check" style="color: var(--color-success)"></i>
                <p>No policy conflicts or regulatory contradictions detected in this draft.</p>
            </div>`;
        lucide.createIcons();
        return;
    }
    
    let html = "";
    conflicts.forEach(c => {
        html += `
            <div class="issue-item">
                <div class="issue-title error">
                    <i data-lucide="shield-alert"></i> ${c.relation.toUpperCase()}: Contradiction Found
                </div>
                <div class="issue-desc">
                    <strong>Draft Clause:</strong> "${c.draft_clause}"
                    <br><br>
                    <strong>Contradicts resolution:</strong> <span class="citation-chip" onclick="viewGr('${c.existing_gr_id}')">${c.existing_gr_id}</span> (${c.existing_department})
                    <br>
                    <strong>Existing Clause:</strong> "${c.existing_clause}"
                    <br><br>
                    <strong>Justification:</strong> ${c.justification}
                </div>
            </div>`;
    });
    container.innerHTML = html;
    lucide.createIcons();
}

function renderCitations(references) {
    const container = document.getElementById("sec-citations");
    if (!references || references.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i data-lucide="link"></i>
                <p>No citations or external GR numbers found in the text.</p>
            </div>`;
        lucide.createIcons();
        return;
    }
    
    let html = "";
    references.forEach(ref => {
        const found = ref.found_in_corpus;
        const color = found ? "success" : "error";
        html += `
            <div class="issue-item">
                <div class="issue-title ${found ? "info" : "error"}">
                    <i data-lucide="${found ? "link-2" : "link-2-off"}"></i> ${ref.raw_text}
                </div>
                <div class="issue-desc">
                    Status in Corpus: <strong style="color: var(--color-${color})">${found ? "RESOLVED (In Force)" : "UNRESOLVED / DEPRECATED"}</strong>
                    ${found ? `<br>Title: ${ref.corpus_title}` : "<br>This GR is either missing or has been superseded."}
                </div>
            </div>`;
    });
    container.innerHTML = html;
    lucide.createIcons();
}

function renderTerminology(terms) {
    const container = document.getElementById("sec-terminology");
    if (!terms || terms.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i data-lucide="languages"></i>
                <p>No bilingual legal term inconsistencies found.</p>
            </div>`;
        lucide.createIcons();
        return;
    }
    
    let html = "";
    terms.forEach(term => {
        html += `
            <div class="issue-item">
                <div class="issue-title info">
                    <i data-lucide="check-circle"></i> "${term.source_term}"
                </div>
                <div class="issue-desc">
                    Marathi equivalent: <strong>${term.target_term}</strong>
                    ${term.note ? `<br><small class="text-muted">${term.note}</small>` : ""}
                </div>
            </div>`;
    });
    container.innerHTML = html;
    lucide.createIcons();
}

// Helper to look up and display a specific GR text
async function viewGr(grId) {
    switchTab("search");
    document.getElementById("search-input").value = grId;
    searchCorpus();
}

// =====================================================================
// Tab 2: Semantic Corpus Search
// =====================================================================
async function searchCorpus() {
    const query = document.getElementById("search-input").value;
    if (query.trim().length < 3) return;
    
    const container = document.getElementById("search-results-list");
    const meta = document.getElementById("search-metrics");
    
    container.innerHTML = `<div class="empty-state"><i class="spin" data-lucide="loader"></i><p>Searching vector space...</p></div>`;
    lucide.createIcons();
    
    try {
        const response = await fetch(`${API_BASE}/api/corpus/search?q=${encodeURIComponent(query)}`);
        if (!response.ok) throw new Error("Search request failed");
        
        const data = await response.json();
        meta.innerText = `Found ${data.hits.length} relevant passages in ${data.took_ms}ms (using upgraded multilingual-e5-base index).`;
        
        if (data.hits.length === 0) {
            container.innerHTML = `<div class="empty-state"><i data-lucide="meh"></i><p>No matches found in the corpus.</p></div>`;
            lucide.createIcons();
            return;
        }
        
        let html = "";
        data.hits.forEach(hit => {
            html += `
                <div class="search-result-card">
                    <div class="result-card-header">
                        <div class="result-title">${hit.title || "GR Reference"}</div>
                        <div class="result-score">Score: ${(hit.score * 100).toFixed(1)}%</div>
                    </div>
                    <div class="result-dept">${hit.department}</div>
                    <div class="result-snippet">${marked.parse(hit.snippet)}</div>
                </div>`;
        });
        container.innerHTML = html;
        lucide.createIcons();
    } catch (e) {
        console.error(e);
        container.innerHTML = `<div class="empty-state"><i data-lucide="x-circle" style="color: var(--color-error)"></i><p>Search failed. Check your connection.</p></div>`;
        lucide.createIcons();
    }
}

function handleSearchKeyDown(event) {
    if (event.key === "Enter") {
        searchCorpus();
    }
}

// =====================================================================
// Tab 3: GR Copilot Conversational Assistant & Drafting AI
// =====================================================================
async function sendQuickPrompt(promptText) {
    document.getElementById("chat-input").value = promptText;
    sendMessage();
}

async function sendMessage() {
    const input = document.getElementById("chat-input");
    const query = input.value.trim();
    if (!query) return;
    
    input.value = "";
    
    const messagesContainer = document.getElementById("chat-messages");
    
    // Add user message to UI
    messagesContainer.innerHTML += `
        <div class="message user">
            <div class="message-bubble">${query}</div>
        </div>`;
    
    // Add loading placeholder for assistant
    const loaderId = "loader-" + Date.now();
    messagesContainer.innerHTML += `
        <div class="message model" id="${loaderId}">
            <div class="message-bubble">
                <i class="spin" data-lucide="loader" style="width: 16px; height: 16px; margin-right: 8px;"></i> Analyzing policy...
            </div>
        </div>`;
    
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    lucide.createIcons();
    
    try {
        const res = await fetch(`${API_BASE}/api/copilot/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                query,
                session_id: currentSessionId
            })
        });
        
        if (!res.ok) throw new Error("Chat request failed");
        const data = await res.json();
        
        // Save current session ID
        currentSessionId = data.session_id;
        
        // Remove loader bubble
        document.getElementById(loaderId).remove();
        
        // Handle drafting intent output injection (if response returns a draft GR code)
        let docLinkHtml = "";
        if (data.references && data.references.length > 0) {
            docLinkHtml = `<div class="message-citation">`;
            data.references.forEach(ref => {
                docLinkHtml += `<span class="citation-chip" onclick="viewGr('${ref.gr_id}')"><i data-lucide="link" style="width:10px; height:10px; display:inline-block; margin-right:4px;"></i>${ref.gr_id}</span>`;
            });
            docLinkHtml += `</div>`;
        }
        
        // Add model message to UI
        messagesContainer.innerHTML += `
            <div class="message model">
                <div class="message-bubble">
                    ${marked.parse(data.answer)}
                    ${docLinkHtml}
                </div>
            </div>`;
            
        // Render new follow-up questions suggestions
        const promptBar = document.getElementById("quick-prompts");
        if (data.follow_up_suggestions && data.follow_up_suggestions.length > 0) {
            let suggestHtml = "";
            data.follow_up_suggestions.slice(0, 3).forEach(s => {
                suggestHtml += `<button class="quick-prompt-btn" onclick="sendQuickPrompt('${s.replace(/'/g, "\\'")}')">${s}</button>`;
            });
            promptBar.innerHTML = suggestHtml;
        }
        
        // Special case: If user asked to "Draft a GR", check if we can populate it in Editor!
        if (query.toLowerCase().includes("draft")) {
            // Trigger automatic background drafting workflow
            generateAIDraft(query);
        }
        
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        lucide.createIcons();
        
    } catch (e) {
        console.error(e);
        document.getElementById(loaderId).innerHTML = `
            <div class="message-bubble" style="color: var(--color-error)">
                Failed to retrieve policy response. Please ensure API key is set in .env.
            </div>`;
    }
}

// Automatically pulls draft generation route if user prompts AI to create a draft
async function generateAIDraft(prompt) {
    try {
        const res = await fetch(`${API_BASE}/api/copilot/draft`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt })
        });
        if (!res.ok) return;
        const data = await res.json();
        
        // Put the generated document directly inside the Editor
        document.getElementById("draft-title").value = data.title;
        document.getElementById("draft-dept").value = data.department;
        document.getElementById("draft-body").value = data.body_text;
        
        // Notify user inside chat
        const messagesContainer = document.getElementById("chat-messages");
        messagesContainer.innerHTML += `
            <div class="message model">
                <div class="message-bubble" style="border-color: var(--color-success)">
                    <i data-lucide="check" style="color: var(--color-success); width: 14px; height: 14px; vertical-align: middle; margin-right: 6px;"></i>
                    I have populated the <strong>Draft Editor</strong> tab with the newly generated Government Resolution draft! You can switch tabs to view it and run compliance checks.
                </div>
            </div>`;
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        lucide.createIcons();
    } catch (e) {
        console.error("Auto drafting failed:", e);
    }
}

function handleChatKeyDown(event) {
    if (event.key === "Enter") {
        sendMessage();
    }
}

function resetChat() {
    currentSessionId = null;
    document.getElementById("chat-messages").innerHTML = `
        <div class="message model">
            <div class="message-bubble">
                Session reset successfully. Ask me any policy questions!
            </div>
        </div>`;
    document.getElementById("quick-prompts").innerHTML = `
        <button class="quick-prompt-btn" onclick="sendQuickPrompt('What is the standard retirement age?')">What is the retirement age?</button>
        <button class="quick-prompt-btn" onclick="sendQuickPrompt('Draft a GR for setting up a state AI laboratory')">Draft an AI Lab GR</button>
        <button class="quick-prompt-btn" onclick="sendQuickPrompt('Compare GR 202308071453439810 and 201805071126259310')">Compare Resolutions</button>`;
}
