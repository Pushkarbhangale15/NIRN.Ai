import { useEffect, useState } from "react";
import { api } from "../api.js";
import { useAuth } from "../AuthContext.jsx";

const STATUS_OPTIONS = ["draft", "under_review", "finalised", "archived"];

function CreateOfficerForm({ onCreated, onCancel }) {
  const [name, setName] = useState("");
  const [loginId, setLoginId] = useState("");
  const [password, setPassword] = useState("");
  const [department, setDepartment] = useState("");
  const [designation, setDesignation] = useState("");
  const [role, setRole] = useState("officer");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const created = await api.createOfficerAdmin({
        name,
        login_id: loginId,
        password,
        department: department || null,
        designation: designation || null,
        role,
      });
      onCreated(created);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form className="admin-inline-form" onSubmit={handleSubmit}>
      <div className="field-row">
        <div className="field">
          <label htmlFor="new-officer-name">Full name</label>
          <input id="new-officer-name" value={name} onChange={(e) => setName(e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="new-officer-login">Login ID</label>
          <input
            id="new-officer-login"
            value={loginId}
            onChange={(e) => setLoginId(e.target.value)}
            pattern="^[A-Za-z0-9._-]+$"
            minLength={3}
            required
          />
        </div>
        <div className="field">
          <label htmlFor="new-officer-password">Password</label>
          <input
            id="new-officer-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={10}
            required
          />
        </div>
      </div>
      <div className="field-row">
        <div className="field">
          <label htmlFor="new-officer-dept">Department</label>
          <input id="new-officer-dept" value={department} onChange={(e) => setDepartment(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="new-officer-designation">Designation</label>
          <input id="new-officer-designation" value={designation} onChange={(e) => setDesignation(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="new-officer-role">Role</label>
          <select id="new-officer-role" value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="officer">officer</option>
            <option value="reviewer">reviewer</option>
            <option value="admin">admin</option>
          </select>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="btn-row" style={{ gap: 10, marginTop: 10 }}>
        <button type="submit" className="btn btn-primary btn-sm" disabled={loading}>
          {loading ? "Creating…" : "Create officer"}
        </button>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onCancel} disabled={loading}>
          Cancel
        </button>
      </div>
    </form>
  );
}

function OfficersPanel() {
  const [officers, setOfficers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [showCreate, setShowCreate] = useState(false);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      setOfficers(await api.listOfficers());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const toggleActive = async (officer) => {
    setBusyId(officer.officer_id);
    try {
      const updated = await api.updateOfficer(officer.officer_id, { is_active: !officer.is_active });
      setOfficers((prev) => prev.map((o) => (o.officer_id === updated.officer_id ? updated : o)));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  };

  const changeRole = async (officer, role) => {
    setBusyId(officer.officer_id);
    try {
      const updated = await api.updateOfficer(officer.officer_id, { role });
      setOfficers((prev) => prev.map((o) => (o.officer_id === updated.officer_id ? updated : o)));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  };

  const handleCreated = (created) => {
    setOfficers((prev) => [created, ...prev]);
    setShowCreate(false);
  };

  return (
    <div className="panel">
      <div className="panel-head">
        <span className="panel-title">Officers</span>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span className="mono">{officers.length}</span>
          {!showCreate && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowCreate(true)}>
              + New officer
            </button>
          )}
        </div>
      </div>
      <div className="panel-body">
        {showCreate && (
          <CreateOfficerForm onCreated={handleCreated} onCancel={() => setShowCreate(false)} />
        )}

        {error && <div className="error-box">{error}</div>}
        {loading ? (
          <div className="ri-sub">Loading…</div>
        ) : (
          <div className="admin-table">
            <div className="admin-table-row admin-table-head">
              <span>Name</span>
              <span>Login ID</span>
              <span>Department</span>
              <span>Role</span>
              <span>Status</span>
              <span>Action</span>
            </div>
            {officers.map((o) => (
              <div className="admin-table-row" key={o.officer_id}>
                <span>{o.name}</span>
                <span className="mono">{o.login_id}</span>
                <span>{o.department || "—"}</span>
                <span>
                  <select
                    value={o.role}
                    disabled={busyId === o.officer_id}
                    onChange={(e) => changeRole(o, e.target.value)}
                  >
                    <option value="officer">officer</option>
                    <option value="reviewer">reviewer</option>
                    <option value="admin">admin</option>
                  </select>
                </span>
                <span>
                  <span className={`badge ${o.is_active ? "badge-ok" : "badge-error"}`}>
                    {o.is_active ? "Active" : "Inactive"}
                  </span>
                </span>
                <span>
                  <button
                    type="button"
                    className="btn btn-outline-warn btn-sm"
                    disabled={busyId === o.officer_id}
                    onClick={() => toggleActive(o)}
                  >
                    {o.is_active ? "Deactivate" : "Activate"}
                  </button>
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
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
      <div>
        <strong>Brief:</strong> {detail.brief || "—"}
      </div>
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

function DraftsPanel() {
  const [drafts, setDrafts] = useState([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState("");
  const [department, setDepartment] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [expandedId, setExpandedId] = useState(null);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.listDrafts({
        status: status || undefined,
        department: department || undefined,
        limit: 50,
      });
      setDrafts(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [status, department]);

  const archive = async (draft) => {
    setBusyId(draft.generated_draft_id);
    try {
      await api.archiveDraft(draft.generated_draft_id);
      setDrafts((prev) =>
        prev.map((d) => (d.generated_draft_id === draft.generated_draft_id ? { ...d, status: "archived" } : d))
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="panel">
      <div className="panel-head">
        <span className="panel-title">All Drafts</span>
        <span className="mono">{total}</span>
      </div>
      <div className="panel-body">
        <div className="field-row">
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
              {STATUS_OPTIONS.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
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
              <span>Department</span>
              <span>Status</span>
              <span>Version</span>
              <span>Action</span>
            </div>
            {drafts.map((d) => (
              <div key={d.generated_draft_id}>
                <div className="admin-table-row">
                  <span>{d.title}</span>
                  <span>{d.department}</span>
                  <span>
                    <span className={`badge ${d.status === "archived" ? "badge-unknown" : "badge-info"}`}>
                      {d.status}
                    </span>
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
                    <button
                      type="button"
                      className="btn btn-outline-warn btn-sm"
                      disabled={d.status === "archived" || busyId === d.generated_draft_id}
                      onClick={() => archive(d)}
                    >
                      {d.status === "archived" ? "Archived" : "Archive"}
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

  if (officer?.role !== "admin") {
    return (
      <main className="container" style={{ marginTop: 80, marginBottom: 80 }}>
        <div className="panel">
          <div className="panel-body">
            <p>You need an administrator account to view this page.</p>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="container" style={{ marginTop: 48, marginBottom: 80 }}>
      <header className="page-head">
        <div className="eyebrow">Admin</div>
        <h1 className="page-title">Manage officers &amp; drafts</h1>
      </header>

      <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
        <OfficersPanel />
        <DraftsPanel />
      </div>
    </main>
  );
}
