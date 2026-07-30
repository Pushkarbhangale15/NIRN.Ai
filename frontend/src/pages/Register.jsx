import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../AuthContext.jsx";

export default function Register() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [loginId, setLoginId] = useState("");
  const [password, setPassword] = useState("");
  const [department, setDepartment] = useState("");
  const [designation, setDesignation] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.register({
        name,
        login_id: loginId,
        password,
        department: department || null,
        designation: designation || null,
      });
      // Auto sign-in right after registering so the officer doesn't have
      // to fill the login form again with the same credentials.
      await login(loginId, password);
      navigate("/");
    } catch (err) {
      setError(err.message || "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="container" style={{ maxWidth: 460, marginTop: 60, marginBottom: 80 }}>
      <form className="panel" onSubmit={handleSubmit}>
        <div className="panel-head">
          <span className="panel-title">Create an Officer Account</span>
        </div>
        <div className="panel-body">
          <div className="field">
            <label htmlFor="name">Full name</label>
            <input id="name" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="field">
            <label htmlFor="reg_login_id">Login ID</label>
            <input
              id="reg_login_id"
              value={loginId}
              onChange={(e) => setLoginId(e.target.value)}
              autoComplete="username"
              pattern="^[A-Za-z0-9._-]+$"
              title="Letters, numbers, dots, underscores and hyphens only"
              minLength={3}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="reg_password">Password</label>
            <input
              id="reg_password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              minLength={10}
              title="At least 10 characters"
              required
            />
          </div>
          <div className="field-row">
            <div className="field">
              <label htmlFor="department">Department (optional)</label>
              <input id="department" value={department} onChange={(e) => setDepartment(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="designation">Designation (optional)</label>
              <input id="designation" value={designation} onChange={(e) => setDesignation(e.target.value)} />
            </div>
          </div>

          {error && (
            <div style={{ color: "var(--red)", fontSize: 13, marginTop: 4 }}>{error}</div>
          )}

          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading}
            style={{ width: "100%", marginTop: 16 }}
          >
            {loading ? "Creating account…" : "Register"}
          </button>

          <p style={{ marginTop: 16, fontSize: 13.5, textAlign: "center" }}>
            Already have an account? <Link to="/login">Sign in</Link>
          </p>
        </div>
      </form>
    </main>
  );
}
