import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { useLanguage } from "../LanguageContext.jsx";
import { useAuth } from "../AuthContext.jsx";

// Same department list used on the Draft page — reused here for consistency
// across the app rather than inventing a second copy of the taxonomy.
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
  { value: "Women_and_Child_Development_Department", label: "Women & Child Development" },
];

const ROLES = ["officer", "reviewer", "admin"];
const DRAFT_STATUSES = ["draft", "under_review", "finalised", "archived"];
const PAGE_SIZE = 20;

function formatIST(iso) {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleString("en-IN", {
      timeZone: "Asia/Kolkata",
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function capitalize(s) {
  if (!s) return "";
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function generatePassword(length = 14) {
  const upper = "ABCDEFGHJKLMNPQRSTUVWXYZ";
  const lower = "abcdefghijkmnpqrstuvwxyz";
  const digits = "23456789";
  const symbols = "!@#$%^&*-_=+";
  const all = upper + lower + digits + symbols;
  const chars = [
    upper[Math.floor(Math.random() * upper.length)],
    lower[Math.floor(Math.random() * lower.length)],
    digits[Math.floor(Math.random() * digits.length)],
    symbols[Math.floor(Math.random() * symbols.length)],
  ];
  for (let i = chars.length; i < length; i++) {
    chars.push(all[Math.floor(Math.random() * all.length)]);
  }
  for (let i = chars.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [chars[i], chars[j]] = [chars[j], chars[i]];
  }
  return chars.join("");
}

function RoleBadge({ role }) {
  const cls = role === "admin" ? "badge-admin" : role === "reviewer" ? "badge-reviewer" : "badge-officer";
  return <span className={`badge ${cls}`}>{capitalize(role)}</span>;
}

function ActiveBadge({ isActive, t }) {
  return (
    <span className={`badge ${isActive ? "badge-active" : "badge-inactive"}`}>
      {isActive ? t("admin_status_active") : t("admin_status_inactive")}
    </span>
  );
}

function DraftStatusBadge({ status, t }) {
  return (
    <span className={`badge badge-status-${status}`}>
      {t(`status_${status}`)}
    </span>
  );
}

function ConflictBadge({ count }) {
  return (
    <span className={`conflict-count-badge${count > 0 ? " has-conflicts" : ""}`}>
      {count}
    </span>
  );
}

function Pager({ page, total, pageSize, onChange }) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  if (total === 0) return null;
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(total, page * pageSize);
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 12, marginTop: 14, fontSize: 13, color: "var(--ink-soft)", fontWeight: 600 }}>
      <span>{start}–{end} of {total}</span>
      <button
        type="button"
        onClick={() => onChange(page - 1)}
        disabled={page <= 1}
        style={pagerBtnStyle(page <= 1)}
      >
        ‹ Prev
      </button>
      <span>Page {page} / {totalPages}</span>
      <button
        type="button"
        onClick={() => onChange(page + 1)}
        disabled={page >= totalPages}
        style={pagerBtnStyle(page >= totalPages)}
      >
        Next ›
      </button>
    </div>
  );
}

function pagerBtnStyle(disabled) {
  return {
    border: "1.5px solid var(--ink)",
    background: disabled ? "#efece5" : "var(--paper)",
    borderRadius: 6,
    padding: "6px 12px",
    fontSize: 12,
    fontWeight: 700,
    cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.6 : 1,
  };
}

function tabBtnStyle(active) {
  return {
    background: "none",
    border: "none",
    borderBottom: active ? "3px solid var(--red)" : "3px solid transparent",
    marginBottom: -2,
    padding: "10px 18px",
    fontFamily: "var(--font-body)",
    fontWeight: 800,
    fontSize: 14,
    textTransform: "uppercase",
    letterSpacing: "0.5px",
    color: active ? "var(--red)" : "var(--ink-soft)",
    cursor: "pointer",
  };
}

function ErrorBanner({ message }) {
  if (!message) return null;
  return (
    <div style={{
      background: "#fee2e2",
      border: "2px solid var(--red)",
      color: "var(--red)",
      padding: "12px 16px",
      borderRadius: 8,
      fontWeight: 600,
      marginBottom: 16,
      fontSize: 14,
    }}>
      {message}
    </div>
  );
}

export default function Admin() {
  const { t, siteLanguage } = useLanguage();
  const { officer: currentOfficer } = useAuth();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState("officers");

  // ── Officers tab state ────────────────────────────────────────
  const [officers, setOfficers] = useState([]);
  const [officersTotal, setOfficersTotal] = useState(0);
  const [officersPage, setOfficersPage] = useState(1);
  const [officersLoading, setOfficersLoading] = useState(false);
  const [officersError, setOfficersError] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  // A small, un-paginated officer list used only to populate the
  // "filter by officer" dropdown on the All Drafts tab.
  const [officersForFilter, setOfficersForFilter] = useState([]);

  // Expanding row showing one officer's draft history
  const [expandedOfficerId, setExpandedOfficerId] = useState(null);
  const [expandedDrafts, setExpandedDrafts] = useState(null); // { loading, items, error }

  // Add/Edit officer modal
  const [officerModal, setOfficerModal] = useState(null); // { mode: 'add'|'edit', officer? }
  const [formState, setFormState] = useState({ name: "", login_id: "", department: "", designation: "", role: "officer", password: "" });
  const [formErrors, setFormErrors] = useState({});
  const [formServerError, setFormServerError] = useState("");
  const [formSubmitting, setFormSubmitting] = useState(false);

  // Confirm dialogs (deactivate / delete / reset password)
  const [confirmDialog, setConfirmDialog] = useState(null); // { type, officer, error, status, busy }

  // One-time password reveal after reset
  const [passwordReveal, setPasswordReveal] = useState(null); // { officerName, password, copied }

  // ── All Drafts tab state ────────────────────────────────────────
  const [drafts, setDrafts] = useState([]);
  const [draftsTotal, setDraftsTotal] = useState(0);
  const [draftsPage, setDraftsPage] = useState(1);
  const [draftsLoading, setDraftsLoading] = useState(false);
  const [draftsError, setDraftsError] = useState("");
  const [draftSearchInput, setDraftSearchInput] = useState("");
  const [draftDebouncedSearch, setDraftDebouncedSearch] = useState("");
  const [draftStatusFilter, setDraftStatusFilter] = useState("");
  const [draftDeptFilter, setDraftDeptFilter] = useState("");
  const [draftOfficerFilter, setDraftOfficerFilter] = useState("");

  const [summary, setSummary] = useState(null);

  // ── Debounce search inputs ──────────────────────────────────────
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchInput), 400);
    return () => clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    const timer = setTimeout(() => setDraftDebouncedSearch(draftSearchInput), 400);
    return () => clearTimeout(timer);
  }, [draftSearchInput]);

  // Reset to page 1 whenever a filter changes
  useEffect(() => { setOfficersPage(1); }, [debouncedSearch, roleFilter, statusFilter]);
  useEffect(() => { setDraftsPage(1); }, [draftDebouncedSearch, draftStatusFilter, draftDeptFilter, draftOfficerFilter]);

  // ── Fetchers ─────────────────────────────────────────────────────
  const fetchOfficers = useCallback(async () => {
    setOfficersLoading(true);
    setOfficersError("");
    try {
      const params = {
        search: debouncedSearch || undefined,
        role: roleFilter || undefined,
        is_active: statusFilter === "" ? undefined : statusFilter === "true",
        page: officersPage,
        page_size: PAGE_SIZE,
      };
      const res = await api.adminListOfficers(params);
      setOfficers(res.items || []);
      setOfficersTotal(res.total || 0);
    } catch (err) {
      setOfficersError(err.message || "Failed to load officers.");
    } finally {
      setOfficersLoading(false);
    }
  }, [debouncedSearch, roleFilter, statusFilter, officersPage]);

  useEffect(() => { fetchOfficers(); }, [fetchOfficers]);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.adminListOfficers({ page_size: 100 });
        setOfficersForFilter(res.items || []);
      } catch {
        // Non-fatal — the officer filter dropdown just stays empty.
      }
    })();
  }, []);

  const fetchSummary = useCallback(async () => {
    try {
      const res = await api.adminSummary();
      setSummary(res);
    } catch {
      // Non-fatal — summary cards simply won't render numbers.
    }
  }, []);

  useEffect(() => { fetchSummary(); }, [fetchSummary]);

  const fetchDrafts = useCallback(async () => {
    setDraftsLoading(true);
    setDraftsError("");
    try {
      const params = {
        search: draftDebouncedSearch || undefined,
        status: draftStatusFilter || undefined,
        department: draftDeptFilter || undefined,
        officer_id: draftOfficerFilter || undefined,
        page: draftsPage,
        page_size: PAGE_SIZE,
      };
      const res = await api.adminListAllDrafts(params);
      setDrafts(res.items || []);
      setDraftsTotal(res.total || 0);
    } catch (err) {
      setDraftsError(err.message || "Failed to load drafts.");
    } finally {
      setDraftsLoading(false);
    }
  }, [draftDebouncedSearch, draftStatusFilter, draftDeptFilter, draftOfficerFilter, draftsPage]);

  useEffect(() => {
    if (activeTab === "drafts") fetchDrafts();
  }, [fetchDrafts, activeTab]);

  // ── Officer row expand (draft history) ──────────────────────────
  async function toggleExpand(row) {
    if (expandedOfficerId === row.officer_id) {
      setExpandedOfficerId(null);
      setExpandedDrafts(null);
      return;
    }
    setExpandedOfficerId(row.officer_id);
    setExpandedDrafts({ loading: true, items: [], error: "" });
    try {
      const res = await api.adminGetOfficerDrafts(row.officer_id, { page_size: 50 });
      setExpandedDrafts({ loading: false, items: res.items || [], error: "" });
    } catch (err) {
      setExpandedDrafts({ loading: false, items: [], error: err.message || "Failed to load drafts." });
    }
  }

  // ── Add / Edit officer modal ─────────────────────────────────────
  function openAddModal() {
    setFormState({ name: "", login_id: "", department: "", designation: "", role: "officer", password: generatePassword() });
    setFormErrors({});
    setFormServerError("");
    setOfficerModal({ mode: "add" });
  }

  function openEditModal(row) {
    setFormState({
      name: row.name || "",
      login_id: row.login_id || "",
      department: row.department || "",
      designation: row.designation || "",
      role: row.role || "officer",
      password: "",
    });
    setFormErrors({});
    setFormServerError("");
    setOfficerModal({ mode: "edit", officer: row });
  }

  function closeOfficerModal() {
    setOfficerModal(null);
  }

  function validateForm() {
    const errs = {};
    if (!formState.name || formState.name.trim().length < 2) {
      errs.name = "Name must be at least 2 characters.";
    }
    if (officerModal?.mode === "add") {
      if (!/^[A-Za-z0-9._-]{3,64}$/.test(formState.login_id)) {
        errs.login_id = "Login ID must be 3–64 characters: letters, numbers, dot, underscore, hyphen only.";
      }
      if (!formState.password || formState.password.length < 10) {
        errs.password = "Password must be at least 10 characters.";
      }
    }
    return errs;
  }

  async function handleFormSubmit(e) {
    e.preventDefault();
    const errs = validateForm();
    setFormErrors(errs);
    if (Object.keys(errs).length > 0) return;

    setFormSubmitting(true);
    setFormServerError("");
    try {
      if (officerModal.mode === "add") {
        await api.adminCreateOfficer({
          name: formState.name.trim(),
          login_id: formState.login_id.trim(),
          password: formState.password,
          department: formState.department || undefined,
          designation: formState.designation || undefined,
          role: formState.role,
        });
      } else {
        await api.adminUpdateOfficer(officerModal.officer.officer_id, {
          name: formState.name.trim(),
          department: formState.department || undefined,
          designation: formState.designation || undefined,
          role: formState.role,
        });
      }
      setOfficerModal(null);
      fetchOfficers();
    } catch (err) {
      setFormServerError(err.message || "Failed to save officer.");
    } finally {
      setFormSubmitting(false);
    }
  }

  // ── Activate (no confirmation needed — reversible / non-destructive) ──
  async function handleActivate(row) {
    try {
      await api.adminActivateOfficer(row.officer_id);
      fetchOfficers();
    } catch (err) {
      setOfficersError(err.message || "Failed to activate officer.");
    }
  }

  // ── Confirm dialogs: deactivate / delete / reset password ────────
  function openConfirm(type, row) {
    setConfirmDialog({ type, officer: row, error: "", status: null, busy: false });
  }

  function closeConfirm() {
    setConfirmDialog(null);
  }

  async function runConfirmAction() {
    if (!confirmDialog) return;
    const { type, officer: row } = confirmDialog;
    setConfirmDialog((d) => ({ ...d, busy: true, error: "" }));
    try {
      if (type === "deactivate") {
        await api.adminDeactivateOfficer(row.officer_id);
        setConfirmDialog(null);
        fetchOfficers();
      } else if (type === "delete") {
        await api.adminDeleteOfficer(row.officer_id);
        setConfirmDialog(null);
        fetchOfficers();
      } else if (type === "reset") {
        const res = await api.adminResetPassword(row.officer_id);
        setConfirmDialog(null);
        setPasswordReveal({ officerName: row.name, password: res.new_password, copied: false });
      }
    } catch (err) {
      setConfirmDialog((d) => ({ ...d, busy: false, error: err.message || "Action failed.", status: err.status || null }));
    }
  }

  async function deactivateFromDeleteDialog() {
    if (!confirmDialog?.officer) return;
    setConfirmDialog((d) => ({ ...d, busy: true }));
    try {
      await api.adminDeactivateOfficer(confirmDialog.officer.officer_id);
      setConfirmDialog(null);
      fetchOfficers();
    } catch (err) {
      setConfirmDialog((d) => ({ ...d, busy: false, error: err.message || "Action failed." }));
    }
  }

  function copyRevealedPassword() {
    if (!passwordReveal) return;
    navigator.clipboard.writeText(passwordReveal.password).then(() => {
      setPasswordReveal((pr) => (pr ? { ...pr, copied: true } : pr));
      setTimeout(() => setPasswordReveal((pr) => (pr ? { ...pr, copied: false } : pr)), 2000);
    });
  }

  // ── Render helpers ────────────────────────────────────────────────
  const isSelf = (row) => currentOfficer && row.officer_id === currentOfficer.officer_id;

  // Reuses the officer-facing History page (conflict expansion/dismiss,
  // PDF/DOCX/archive) rather than building a second read-only view —
  // every draft-scoped endpoint it calls already allows admin/reviewer
  // access to any officer's drafts (see routes.py _ensure_can_access_draft).
  function viewOfficerHistory(row) {
    navigate(`/history?officer_id=${row.officer_id}&officer_name=${encodeURIComponent(row.name)}`);
  }

  return (
    <main className="container" style={{ paddingBottom: 60 }}>
      <header className="page-head">
        <div className="eyebrow">{t("admin_eyebrow")}</div>
        <h1 className="page-title">{t("admin_title")}</h1>
      </header>

      <div style={{ display: "flex", gap: 4, borderBottom: "2px solid var(--ink)", marginBottom: 24 }}>
        <button type="button" style={tabBtnStyle(activeTab === "officers")} onClick={() => setActiveTab("officers")}>
          {t("admin_tab_officers")}
        </button>
        <button type="button" style={tabBtnStyle(activeTab === "drafts")} onClick={() => setActiveTab("drafts")}>
          {t("admin_tab_drafts")}
        </button>
      </div>

      {activeTab === "officers" && (
        <section>
          <div className="data-toolbar">
            <input
              type="text"
              placeholder={t("admin_search_placeholder")}
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
            />
            <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)} aria-label={t("admin_filter_role")}>
              <option value="">{t("admin_filter_role")}: {t("admin_filter_all")}</option>
              {ROLES.map((r) => (
                <option key={r} value={r}>{capitalize(r)}</option>
              ))}
            </select>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} aria-label={t("admin_filter_status")}>
              <option value="">{t("admin_filter_status")}: {t("admin_filter_all")}</option>
              <option value="true">{t("admin_status_active")}</option>
              <option value="false">{t("admin_status_inactive")}</option>
            </select>
            <button type="button" className="btn btn-red" onClick={openAddModal} style={{ marginLeft: "auto" }}>
              {t("admin_add_officer")}
            </button>
          </div>

          <ErrorBanner message={officersError} />

          {officersLoading ? (
            <div style={{ textAlign: "center", padding: "40px 0" }}><span className="spinner" /></div>
          ) : officers.length === 0 ? (
            <div className="empty-panel">{t("admin_no_officers")}</div>
          ) : (
            <div className="data-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{t("admin_col_name")}</th>
                    <th>{t("admin_col_login_id")}</th>
                    <th>{t("admin_col_department")}</th>
                    <th>{t("admin_col_designation")}</th>
                    <th>{t("admin_col_role")}</th>
                    <th>{t("admin_col_status")}</th>
                    <th>{t("admin_col_last_login")}</th>
                    <th>{t("admin_col_actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {officers.map((row) => (
                    <React.Fragment key={row.officer_id}>
                      <tr onClick={() => toggleExpand(row)} style={{ cursor: "pointer" }}>
                        <td>{row.name}</td>
                        <td>{row.login_id}</td>
                        <td>{row.department || "—"}</td>
                        <td>{row.designation || "—"}</td>
                        <td><RoleBadge role={row.role} /></td>
                        <td><ActiveBadge isActive={row.is_active} t={t} /></td>
                        <td>{row.last_login_at ? formatIST(row.last_login_at) : t("admin_never_logged_in")}</td>
                        <td onClick={(e) => e.stopPropagation()}>
                          <div className="icon-btn-row">
                            <button type="button" onClick={() => viewOfficerHistory(row)}>{t("admin_action_view_history")}</button>
                            <button type="button" onClick={() => openEditModal(row)}>{t("admin_action_edit")}</button>
                            {row.is_active ? (
                              <button type="button" disabled={isSelf(row)} title={isSelf(row) ? "You cannot deactivate your own account." : undefined} onClick={() => openConfirm("deactivate", row)}>
                                {t("admin_action_deactivate")}
                              </button>
                            ) : (
                              <button type="button" onClick={() => handleActivate(row)}>{t("admin_action_activate")}</button>
                            )}
                            <button type="button" onClick={() => openConfirm("reset", row)}>{t("admin_action_reset_password")}</button>
                            <button type="button" className="danger" disabled={isSelf(row)} title={isSelf(row) ? "You cannot delete your own account." : undefined} onClick={() => openConfirm("delete", row)}>
                              {t("admin_action_delete")}
                            </button>
                          </div>
                        </td>
                      </tr>
                      {expandedOfficerId === row.officer_id && (
                        <tr>
                          <td colSpan={8} style={{ background: "#faf9f6", padding: "16px 20px" }}>
                            {expandedDrafts?.loading ? (
                              <span className="spinner-small" style={{ borderTopColor: "var(--ink)", borderColor: "var(--line)", borderBottomColor: "var(--ink)" }} />
                            ) : expandedDrafts?.error ? (
                              <ErrorBanner message={expandedDrafts.error} />
                            ) : expandedDrafts?.items?.length ? (
                              <table className="data-table" style={{ minWidth: 0 }}>
                                <thead>
                                  <tr>
                                    <th>{t("history_col_gr_number")}</th>
                                    <th>{t("history_col_title")}</th>
                                    <th>{t("history_col_department")}</th>
                                    <th>{t("history_col_status")}</th>
                                    <th>{t("history_col_conflicts")}</th>
                                    <th>{t("history_col_created")}</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {expandedDrafts.items.map((d) => (
                                    <tr key={d.generated_draft_id}>
                                      <td title="Internal/provisional reference — not an official GR number">{d.gr_number || "—"}</td>
                                      <td>{d.title}</td>
                                      <td>{d.department || "—"}</td>
                                      <td><DraftStatusBadge status={d.status} t={t} /></td>
                                      <td><ConflictBadge count={d.unresolved_conflict_count} /></td>
                                      <td>{formatIST(d.created_at)}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            ) : (
                              <div style={{ color: "var(--ink-soft)", fontSize: 13 }}>{t("admin_no_drafts")}</div>
                            )}
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <Pager page={officersPage} total={officersTotal} pageSize={PAGE_SIZE} onChange={setOfficersPage} />
        </section>
      )}

      {activeTab === "drafts" && (
        <section>
          <div className="summary-cards-row">
            <div className="summary-card">
              <div className="summary-number">{summary ? summary.total_drafts : "—"}</div>
              <div className="summary-label">{t("admin_summary_total_drafts")}</div>
            </div>
            <div className="summary-card">
              <div className="summary-number">{summary ? summary.total_unresolved_conflicts : "—"}</div>
              <div className="summary-label">{t("admin_summary_unresolved")}</div>
            </div>
            <div className="summary-card">
              <div className="summary-number">{summary ? summary.active_officers : "—"}</div>
              <div className="summary-label">{t("admin_summary_active_officers")}</div>
            </div>
            <div className="summary-card">
              <div className="summary-number">{summary ? summary.drafts_last_7_days : "—"}</div>
              <div className="summary-label">{t("admin_summary_recent")}</div>
            </div>
          </div>

          <div className="data-toolbar">
            <input
              type="text"
              placeholder={t("history_search_placeholder")}
              value={draftSearchInput}
              onChange={(e) => setDraftSearchInput(e.target.value)}
            />
            <select value={draftOfficerFilter} onChange={(e) => setDraftOfficerFilter(e.target.value)} aria-label={t("admin_filter_officer")}>
              <option value="">{t("admin_filter_officer")}: {t("admin_filter_all")}</option>
              {officersForFilter.map((o) => (
                <option key={o.officer_id} value={o.officer_id}>{o.name} ({o.login_id})</option>
              ))}
            </select>
            <select value={draftDeptFilter} onChange={(e) => setDraftDeptFilter(e.target.value)} aria-label={t("history_filter_department")}>
              <option value="">{t("history_filter_department")}: {t("admin_filter_all")}</option>
              {DEPARTMENTS.map((d) => (
                <option key={d.value} value={d.value}>{d.label}</option>
              ))}
            </select>
            <select value={draftStatusFilter} onChange={(e) => setDraftStatusFilter(e.target.value)} aria-label={t("history_filter_status")}>
              <option value="">{t("history_filter_status")}: {t("admin_filter_all")}</option>
              {DRAFT_STATUSES.map((s) => (
                <option key={s} value={s}>{t(`status_${s}`)}</option>
              ))}
            </select>
          </div>

          <ErrorBanner message={draftsError} />

          {draftsLoading ? (
            <div style={{ textAlign: "center", padding: "40px 0" }}><span className="spinner" /></div>
          ) : drafts.length === 0 ? (
            <div className="empty-panel">{t("admin_no_drafts")}</div>
          ) : (
            <div className="data-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{t("history_col_gr_number")}</th>
                    <th>{t("history_col_title")}</th>
                    <th>{t("history_col_department")}</th>
                    <th>{t("history_col_status")}</th>
                    <th>{t("history_col_conflicts")}</th>
                    <th>{t("history_col_created")}</th>
                  </tr>
                </thead>
                <tbody>
                  {drafts.map((d) => (
                    <tr key={d.generated_draft_id}>
                      <td title="Internal/provisional reference — not an official GR number">{d.gr_number || "—"}</td>
                      <td>{d.title}</td>
                      <td>{d.department || "—"}</td>
                      <td><DraftStatusBadge status={d.status} t={t} /></td>
                      <td><ConflictBadge count={d.unresolved_conflict_count} /></td>
                      <td>{formatIST(d.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <Pager page={draftsPage} total={draftsTotal} pageSize={PAGE_SIZE} onChange={setDraftsPage} />
        </section>
      )}

      {/* ── Add / Edit officer modal ─────────────────────────────── */}
      {officerModal && (
        <div className="modal-overlay" onClick={closeOfficerModal}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h2>{officerModal.mode === "add" ? t("admin_modal_add_title") : t("admin_modal_edit_title")}</h2>
            <ErrorBanner message={formServerError} />
            <form onSubmit={handleFormSubmit}>
              <div className="modal-field">
                <label htmlFor="admin-field-name">{t("admin_field_name")}</label>
                <input
                  id="admin-field-name"
                  type="text"
                  value={formState.name}
                  onChange={(e) => setFormState((f) => ({ ...f, name: e.target.value }))}
                  required
                />
                {formErrors.name && <div style={{ color: "var(--red)", fontSize: 12, marginTop: 4 }}>{formErrors.name}</div>}
              </div>

              <div className="modal-field">
                <label htmlFor="admin-field-login">{t("admin_field_login_id")}</label>
                <input
                  id="admin-field-login"
                  type="text"
                  value={formState.login_id}
                  disabled={officerModal.mode === "edit"}
                  onChange={(e) => setFormState((f) => ({ ...f, login_id: e.target.value }))}
                  required
                  style={officerModal.mode === "edit" ? { background: "#efece5", cursor: "not-allowed" } : undefined}
                />
                {formErrors.login_id && <div style={{ color: "var(--red)", fontSize: 12, marginTop: 4 }}>{formErrors.login_id}</div>}
              </div>

              <div className="modal-field">
                <label htmlFor="admin-field-dept">{t("admin_field_department")}</label>
                <select
                  id="admin-field-dept"
                  value={formState.department}
                  onChange={(e) => setFormState((f) => ({ ...f, department: e.target.value }))}
                >
                  <option value="">—</option>
                  {DEPARTMENTS.map((d) => (
                    <option key={d.value} value={d.value}>{d.label}</option>
                  ))}
                </select>
              </div>

              <div className="modal-field">
                <label htmlFor="admin-field-designation">{t("admin_field_designation")}</label>
                <input
                  id="admin-field-designation"
                  type="text"
                  value={formState.designation}
                  onChange={(e) => setFormState((f) => ({ ...f, designation: e.target.value }))}
                />
              </div>

              <div className="modal-field">
                <label htmlFor="admin-field-role">{t("admin_field_role")}</label>
                <select
                  id="admin-field-role"
                  value={formState.role}
                  onChange={(e) => setFormState((f) => ({ ...f, role: e.target.value }))}
                >
                  {ROLES.map((r) => (
                    <option key={r} value={r}>{capitalize(r)}</option>
                  ))}
                </select>
              </div>

              {officerModal.mode === "add" && (
                <div className="modal-field">
                  <label htmlFor="admin-field-password">{t("admin_field_password")}</label>
                  <div style={{ display: "flex", gap: 8 }}>
                    <input
                      id="admin-field-password"
                      type="text"
                      value={formState.password}
                      onChange={(e) => setFormState((f) => ({ ...f, password: e.target.value }))}
                      style={{ flex: 1 }}
                      required
                    />
                    <button
                      type="button"
                      className="btn-outline-warn btn"
                      style={{ minHeight: 46, padding: "0 14px", whiteSpace: "nowrap" }}
                      onClick={() => setFormState((f) => ({ ...f, password: generatePassword() }))}
                    >
                      {t("admin_generate_password")}
                    </button>
                  </div>
                  {formErrors.password && <div style={{ color: "var(--red)", fontSize: 12, marginTop: 4 }}>{formErrors.password}</div>}
                </div>
              )}

              <div className="btn-row" style={{ marginTop: 24 }}>
                <button type="submit" className="btn btn-red" disabled={formSubmitting}>
                  {formSubmitting ? <span className="spinner-small" /> : t("admin_save")}
                </button>
                <button type="button" className="btn btn-outline-warn" onClick={closeOfficerModal} disabled={formSubmitting}>
                  {t("admin_cancel")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Confirm dialog: deactivate / delete / reset ───────────── */}
      {confirmDialog && (
        <div className="modal-overlay" onClick={confirmDialog.busy ? undefined : closeConfirm}>
          <div className="modal-card" style={{ maxWidth: 420 }} onClick={(e) => e.stopPropagation()}>
            {confirmDialog.type === "deactivate" && (
              <>
                <h2>{t("admin_confirm_deactivate_title")}</h2>
                <p style={{ marginBottom: 20 }}>{t("admin_confirm_deactivate_body")}</p>
              </>
            )}
            {confirmDialog.type === "delete" && (
              <>
                <h2>{t("admin_confirm_delete_title")}</h2>
                <p style={{ marginBottom: 20 }}>{t("admin_confirm_delete_body")}</p>
              </>
            )}
            {confirmDialog.type === "reset" && (
              <>
                <h2>{t("admin_confirm_reset_title")}</h2>
                <p style={{ marginBottom: 20 }}>{t("admin_confirm_reset_body")}</p>
              </>
            )}

            {confirmDialog.error && (
              <ErrorBanner
                message={
                  confirmDialog.type === "delete" && confirmDialog.status === 409
                    ? (() => {
                        const match = confirmDialog.error.match(/(\d+)/);
                        return match
                          ? t("admin_has_drafts_warning").replace("{count}", match[1])
                          : confirmDialog.error;
                      })()
                    : confirmDialog.error
                }
              />
            )}

            <div className="btn-row">
              {confirmDialog.type === "delete" && confirmDialog.status === 409 ? (
                <button type="button" className="btn btn-red" disabled={confirmDialog.busy} onClick={deactivateFromDeleteDialog}>
                  {confirmDialog.busy ? <span className="spinner-small" /> : t("admin_action_deactivate")}
                </button>
              ) : (
                <button type="button" className="btn btn-red" disabled={confirmDialog.busy} onClick={runConfirmAction}>
                  {confirmDialog.busy ? <span className="spinner-small" /> : t(
                    confirmDialog.type === "deactivate" ? "admin_action_deactivate"
                      : confirmDialog.type === "delete" ? "admin_action_delete"
                      : "admin_action_reset_password"
                  )}
                </button>
              )}
              <button type="button" className="btn btn-outline-warn" disabled={confirmDialog.busy} onClick={closeConfirm}>
                {t("admin_cancel")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── One-time password reveal ─────────────────────────────── */}
      {passwordReveal && (
        <div className="modal-overlay" onClick={() => setPasswordReveal(null)}>
          <div className="modal-card" style={{ maxWidth: 420 }} onClick={(e) => e.stopPropagation()}>
            <h2>{t("admin_action_reset_password")}</h2>
            <p style={{ marginBottom: 12, fontWeight: 600 }}>{passwordReveal.officerName}</p>
            <div style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              border: "2px solid var(--ink)",
              borderRadius: 8,
              padding: "10px 14px",
              marginBottom: 10,
              background: "#faf9f6",
            }}>
              <code style={{ flex: 1, fontSize: 15, fontWeight: 700, wordBreak: "break-all" }}>{passwordReveal.password}</code>
              <button type="button" className="btn-outline-warn btn" style={{ minHeight: 38, padding: "0 12px" }} onClick={copyRevealedPassword}>
                {passwordReveal.copied ? t("admin_copied") : t("admin_copy")}
              </button>
            </div>
            <p style={{ fontSize: 13, color: "var(--red)", fontWeight: 600, marginBottom: 20 }}>{t("admin_password_shown_once")}</p>
            <div className="btn-row">
              <button type="button" className="btn btn-red" onClick={() => setPasswordReveal(null)}>{t("admin_cancel")}</button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
