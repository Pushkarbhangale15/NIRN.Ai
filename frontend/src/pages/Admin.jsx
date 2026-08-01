import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../AuthContext.jsx";
import { DEPARTMENTS } from "../constants/departments.js";

const STATUS_OPTIONS = ["draft", "under_review", "finalised", "archived"];
const SOURCE_OPTIONS = ["generated", "uploaded"];
const ROLE_OPTIONS = ["officer", "reviewer", "admin"];

function generatePassword() {
  const bytes = new Uint8Array(12);
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes)).replace(/[+/=]/g, "").slice(0, 16);
}

function useDebouncedValue(value, delayMs) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

function Modal({ title, onClose, narrow, children }) {
  return (
    <div className="admin-modal-overlay" onClick={onClose}>
      <div
        className={`admin-modal panel${narrow ? " admin-modal--narrow" : ""}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="panel-head">
          <span className="panel-title">{title}</span>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>Close</button>
        </div>
        <div className="panel-body">{children}</div>
      </div>
    </div>
  );
}

function OfficerFormModal({ officer, onClose, onSaved }) {
  const isEdit = Boolean(officer);
  const [name, setName] = useState(officer?.name || "");
  const [loginId, setLoginId] = useState(officer?.login_id || "");
  const [password, setPassword] = useState("");
  const [department, setDepartment] = useState(officer?.department || "");
  const [designation, setDesignation] = useState(officer?.designation || "");
  const [role, setRole] = useState(officer?.role || "officer");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      let saved;
      if (isEdit) {
        saved = await api.editOfficer(officer.officer_id, {
          name, department: department || null, designation: designation || null, role,
        });
      } else {
        saved = await api.createOfficer({
          name, login_id: loginId, password,
          department: department || null, designation: designation || null, role,
        });
      }
      onSaved(saved);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal title={isEdit ? "Edit officer" : "Add officer"} onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="officer-name">Full name</label>
          <input id="officer-name" value={name} onChange={(e) => setName(e.target.value)} required />
        </div>

        <div className="field">
          <label htmlFor="officer-login">Login ID {isEdit && "(fixed after creation)"}</label>
          <input
            id="officer-login"
            value={loginId}
            onChange={(e) => setLoginId(e.target.value)}
            pattern="^[A-Za-z0-9._-]+$"
            minLength={3}
            maxLength={64}
            title="3-64 chars: letters, numbers, dots, underscores, hyphens"
            disabled={isEdit}
            required
          />
        </div>

        {!isEdit && (
          <div className="field">
            <label htmlFor="officer-password">Initial password</label>
            <div style={{ display: "flex", gap: 8 }}>
              <input
                id="officer-password"
                type="text"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={10}
                maxLength={128}
                title="At least 10 characters"
                required
                style={{ flex: 1 }}
              />
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setPassword(generatePassword())}
              >
                Generate
              </button>
            </div>
            {password && (
              <p className="ri-sub" style={{ marginTop: 6 }}>
                Share this password with the officer now — it will not be shown again after creation.
              </p>
            )}
          </div>
        )}

        <div className="field-row">
          <div className="field">
            <label htmlFor="officer-dept">Department</label>
            <select id="officer-dept" value={department} onChange={(e) => setDepartment(e.target.value)}>
              <option value="">— None —</option>
              {DEPARTMENTS.map((d) => (
                <option key={d.value} value={d.value}>{d.label}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="officer-designation">Designation</label>
            <input id="officer-designation" value={designation} onChange={(e) => setDesignation(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="officer-role">Role</label>
            <select id="officer-role" value={role} onChange={(e) => setRole(e.target.value)}>
              {ROLE_OPTIONS.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
        </div>

        {error && <div className="error-box">{error}</div>}

        <div className="btn-row" style={{ gap: 10, marginTop: 14 }}>
          <button type="submit" className="btn btn-primary btn-sm" disabled={loading}>
            {loading ? "Saving…" : isEdit ? "Save changes" : "Create officer"}
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose} disabled={loading}>
            Cancel
          </button>
        </div>
      </form>
    </Modal>
  );
}

function ResetPasswordModal({ officer, onClose }) {
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const doReset = async () => {
    setError("");
    setLoading(true);
    try {
      setResult(await api.resetOfficerPassword(officer.officer_id));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const copy = () => {
    navigator.clipboard.writeText(result.temporary_password).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <Modal title={`Reset password — ${officer.name}`} onClose={onClose} narrow>
      {!result ? (
        <>
          <p>This immediately invalidates {officer.name}'s current password and generates a new temporary one.</p>
          {error && <div className="error-box">{error}</div>}
          <div className="btn-row" style={{ gap: 10, marginTop: 14 }}>
            <button type="button" className="btn btn-primary btn-sm" onClick={doReset} disabled={loading}>
              {loading ? "Resetting…" : "Reset password"}
            </button>
            <button type="button" className="btn btn-ghost btn-sm" onClick={onClose} disabled={loading}>
              Cancel
            </button>
          </div>
        </>
      ) : (
        <>
          <p>Share this temporary password with {officer.name} now — it will not be shown again.</p>
          <div className="admin-generated-password">
            <span style={{ flex: 1 }}>{result.temporary_password}</span>
            <button type="button" className="btn btn-ghost btn-sm" onClick={copy}>
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <div className="btn-row" style={{ marginTop: 14 }}>
            <button type="button" className="btn btn-secondary btn-sm" onClick={onClose}>Done</button>
          </div>
        </>
      )}
    </Modal>
  );
}

function OfficersPanel({ onViewHistory }) {
  const [officers, setOfficers] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);

  const [searchInput, setSearchInput] = useState("");
  const search = useDebouncedValue(searchInput, 300);
  const [role, setRole] = useState("");
  const [isActive, setIsActive] = useState("");
  const [offset, setOffset] = useState(0);
  const limit = 20;

  const [showForm, setShowForm] = useState(false);
  const [editingOfficer, setEditingOfficer] = useState(null);
  const [resettingOfficer, setResettingOfficer] = useState(null);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.listOfficers({
        search: search || undefined,
        role: role || undefined,
        isActive: isActive === "" ? undefined : isActive === "true",
        limit,
        offset,
      });
      setOfficers(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [search, role, isActive, offset]);

  const toggleActive = async (officer) => {
    setBusyId(officer.officer_id);
    try {
      const updated = officer.is_active
        ? await api.deactivateOfficer(officer.officer_id)
        : await api.activateOfficer(officer.officer_id);
      setOfficers((prev) => prev.map((o) => (o.officer_id === updated.officer_id ? updated : o)));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  };

  const handleSaved = (saved) => {
    setShowForm(false);
    setEditingOfficer(null);
    load();
  };

  return (
    <div className="panel">
      <div className="panel-head">
        <span className="panel-title">Officers</span>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span className="mono">{total}</span>
          <button type="button" className="btn btn-primary btn-sm" onClick={() => setShowForm(true)}>
            + Add Officer
          </button>
        </div>
      </div>
      <div className="panel-body">
        <div className="admin-toolbar">
          <div className="field">
            <label htmlFor="officer-search">Search</label>
            <input
              id="officer-search"
              value={searchInput}
              onChange={(e) => { setSearchInput(e.target.value); setOffset(0); }}
              placeholder="Name or login ID"
            />
          </div>
          <div className="field">
            <label htmlFor="officer-role-filter">Role</label>
            <select id="officer-role-filter" value={role} onChange={(e) => { setRole(e.target.value); setOffset(0); }}>
              <option value="">All</option>
              {ROLE_OPTIONS.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="officer-status-filter">Status</label>
            <select id="officer-status-filter" value={isActive} onChange={(e) => { setIsActive(e.target.value); setOffset(0); }}>
              <option value="">All</option>
              <option value="true">Active</option>
              <option value="false">Inactive</option>
            </select>
          </div>
        </div>

        {error && <div className="error-box">{error}</div>}
        {loading ? (
          <div className="admin-table admin-table--officers">
            <div className="admin-table-row admin-table-head">
              <span>Name</span><span>Login ID</span><span>Department</span><span>Designation</span>
              <span>Role</span><span>Status</span><span>Last Login</span><span>Action</span>
            </div>
            {[0, 1, 2].map((i) => (
              <div className="admin-table-row" key={i}>
                {Array.from({ length: 8 }).map((_, j) => (
                  <span key={j} className="skeleton-line" />
                ))}
              </div>
            ))}
          </div>
        ) : officers.length === 0 ? (
          <div className="ri-sub">No officers match these filters.</div>
        ) : (
          <div className="admin-table admin-table--officers">
            <div className="admin-table-row admin-table-head">
              <span>Name</span><span>Login ID</span><span>Department</span><span>Designation</span>
              <span>Role</span><span>Status</span><span>Last Login</span><span>Action</span>
            </div>
            {officers.map((o) => (
              <div className="admin-table-row" key={o.officer_id}>
                <span>{o.name}</span>
                <span className="mono">{o.login_id}</span>
                <span>{o.department || "—"}</span>
                <span>{o.designation || "—"}</span>
                <span><span className="badge badge-info">{o.role}</span></span>
                <span>
                  <span className={`badge ${o.is_active ? "badge-ok" : "badge-error"}`}>
                    {o.is_active ? "Active" : "Inactive"}
                  </span>
                </span>
                <span className="ri-sub">
                  {o.last_login_at ? new Date(o.last_login_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "Never"}
                </span>
                <span style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditingOfficer(o)}>Edit</button>
                  <button
                    type="button"
                    className="btn btn-outline-warn btn-sm"
                    disabled={busyId === o.officer_id}
                    onClick={() => toggleActive(o)}
                  >
                    {o.is_active ? "Deactivate" : "Activate"}
                  </button>
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => setResettingOfficer(o)}>Reset PW</button>
                  <button type="button" className="btn btn-secondary btn-sm" onClick={() => onViewHistory(o)}>History</button>
                </span>
              </div>
            ))}
          </div>
        )}

        {total > limit && (
          <div className="admin-pagination">
            <button className="btn btn-ghost btn-sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>
              ← Prev
            </button>
            <span>{offset + 1}–{Math.min(offset + limit, total)} of {total}</span>
            <button className="btn btn-ghost btn-sm" disabled={offset + limit >= total} onClick={() => setOffset(offset + limit)}>
              Next →
            </button>
          </div>
        )}
      </div>

      {showForm && (
        <OfficerFormModal onClose={() => setShowForm(false)} onSaved={handleSaved} />
      )}
      {editingOfficer && (
        <OfficerFormModal officer={editingOfficer} onClose={() => setEditingOfficer(null)} onSaved={handleSaved} />
      )}
      {resettingOfficer && (
        <ResetPasswordModal officer={resettingOfficer} onClose={() => setResettingOfficer(null)} />
      )}
    </div>
  );
}

function DraftDetail({ draftId }) {
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api.getDraft(draftId)
      .then((d) => { if (!cancelled) setDetail(d); })
      .catch((err) => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [draftId]);

  if (error) return <div className="error-box">{error}</div>;
  if (!detail) return <div className="ri-sub">Loading draft…</div>;

  const plainContent = detail.content.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();

  return (
    <div className="admin-draft-detail">
      <div><strong>GR Number:</strong> <span className="mono">{detail.gr_number || "—"}</span> (provisional)</div>
      <div><strong>Brief:</strong> {detail.brief || "—"}</div>
      {detail.source === "uploaded" && (
        <div><strong>Original file:</strong> {detail.original_filename || "—"}</div>
      )}
      <div style={{ marginTop: 8 }}>
        <strong>Content:</strong>
        <p className="ri-sub" style={{ marginTop: 4 }}>
          {plainContent.length > 600 ? `${plainContent.slice(0, 600)}…` : plainContent || "(empty)"}
        </p>
      </div>

      <div style={{ marginTop: 12 }}>
        <strong>Conflicts ({detail.conflicts.length})</strong>
        {detail.conflicts.length === 0 ? (
          <p className="ri-sub">None detected.</p>
        ) : (
          detail.conflicts.map((c) => (
            <div key={c.conflict_id} className="admin-conflict-row">
              <span className={`badge badge-${c.severity === "high" ? "error" : c.severity === "medium" ? "warning" : "info"}`}>
                {c.severity}
              </span>
              <div>
                <div style={{ fontWeight: 600 }}>{c.source_of_conflict}</div>
                <div className="ri-sub">{c.justification}</div>
                {c.is_dismissed && <div className="ri-sub">Dismissed: {c.dismissed_reason || "no reason given"}</div>}
              </div>
            </div>
          ))
        )}
      </div>

      <div style={{ marginTop: 12 }}>
        <strong>References ({detail.references.length})</strong>
        {detail.references.length === 0 ? (
          <p className="ri-sub">None extracted.</p>
        ) : (
          <ul style={{ marginTop: 4 }}>
            {detail.references.map((r) => (
              <li key={r.reference_id} className="ri-sub">
                {r.reference_text} {r.resolved ? "(resolved)" : "(unresolved)"}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function DraftsPanel({ authorFilter, onClearAuthorFilter }) {
  const [drafts, setDrafts] = useState([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState("");
  const [source, setSource] = useState("");
  const [department, setDepartment] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expandedId, setExpandedId] = useState(null);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.listDrafts({
        status: status || undefined,
        source: source || undefined,
        department: department || undefined,
        authorId: authorFilter?.officer_id,
        page: 1,
        pageSize: 50,
      });
      setDrafts(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [status, source, department, authorFilter]);

  return (
    <div className="panel">
      <div className="panel-head">
        <span className="panel-title">All Drafts</span>
        <span className="mono">{total}</span>
      </div>
      <div className="panel-body">
        {authorFilter && (
          <div className="admin-toolbar" style={{ alignItems: "center", marginBottom: 12 }}>
            <span>
              Showing history for <strong>{authorFilter.name}</strong> ({authorFilter.login_id})
            </span>
            <button type="button" className="btn btn-ghost btn-sm" onClick={onClearAuthorFilter}>
              Clear
            </button>
          </div>
        )}
        <div className="admin-toolbar">
          <div className="field">
            <label htmlFor="admin-dept-filter">Department</label>
            <input
              id="admin-dept-filter"
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              placeholder="Filter by department"
            />
          </div>
          <div className="field">
            <label htmlFor="admin-status-filter">Status</label>
            <select id="admin-status-filter" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">All</option>
              {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="admin-source-filter">Source</label>
            <select id="admin-source-filter" value={source} onChange={(e) => setSource(e.target.value)}>
              <option value="">All</option>
              {SOURCE_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        </div>

        {error && <div className="error-box">{error}</div>}
        {loading ? (
          <div className="ri-sub">Loading…</div>
        ) : drafts.length === 0 ? (
          <div className="ri-sub">No drafts match these filters.</div>
        ) : (
          <div className="admin-table admin-table--drafts">
            <div className="admin-table-row admin-table-head">
              <span>Title</span>
              <span>Officer</span>
              <span>Department</span>
              <span>Status</span>
              <span>Version</span>
              <span>Action</span>
            </div>
            {drafts.map((d) => (
              <div key={d.generated_draft_id}>
                <div className="admin-table-row">
                  <span>{d.title}</span>
                  <span>
                    {d.officer_name || "—"}
                    {d.officer_login_id && <span className="ri-sub"> ({d.officer_login_id})</span>}
                  </span>
                  <span>{d.department}</span>
                  <span>
                    <span className={`badge ${d.status === "archived" ? "badge-unknown" : "badge-info"}`}>
                      {d.status}
                    </span>
                    {" "}
                    <span className="badge badge-warning">{d.source}</span>
                  </span>
                  <span className="mono">v{d.version}</span>
                  <span style={{ display: "flex", gap: 8 }}>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => setExpandedId(expandedId === d.generated_draft_id ? null : d.generated_draft_id)}
                    >
                      {expandedId === d.generated_draft_id ? "Hide" : "View"}
                    </button>
                  </span>
                </div>
                {expandedId === d.generated_draft_id && (
                  <div className="admin-table-row admin-table-row--detail">
                    <DraftDetail draftId={d.generated_draft_id} />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function Admin() {
  const { officer } = useAuth();
  const navigate = useNavigate();
  const isAdmin = officer?.role === "admin";
  const draftsPanelRef = useRef(null);
  const [authorFilter, setAuthorFilter] = useState(null);

  useEffect(() => {
    if (officer && !isAdmin) {
      navigate("/", { replace: true });
    }
  }, [officer, isAdmin, navigate]);

  if (!isAdmin) {
    return null;
  }

  const viewHistoryFor = (o) => {
    setAuthorFilter({ officer_id: o.officer_id, name: o.name, login_id: o.login_id });
    draftsPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <main className="container" style={{ marginTop: 48, marginBottom: 80 }}>
      <header className="page-head">
        <div className="eyebrow">Admin</div>
        <h1 className="page-title">Manage officers &amp; drafts</h1>
      </header>

      <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
        <OfficersPanel onViewHistory={viewHistoryFor} />
        <div ref={draftsPanelRef} style={{ scrollMarginTop: 96 }}>
          <DraftsPanel authorFilter={authorFilter} onClearAuthorFilter={() => setAuthorFilter(null)} />
        </div>
      </div>
    </main>
  );
}
