import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext.jsx";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [loginId, setLoginId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(loginId, password);
      navigate("/");
    } catch (err) {
      setError(err.message || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="container" style={{ maxWidth: 420, marginTop: 80, marginBottom: 80 }}>
      <form className="panel" onSubmit={handleSubmit}>
        <div className="panel-head">
          <span className="panel-title">Officer Sign In</span>
        </div>
        <div className="panel-body">
          <div className="field">
            <label htmlFor="login_id">Login ID</label>
            <input
              id="login_id"
              value={loginId}
              onChange={(e) => setLoginId(e.target.value)}
              autoComplete="username"
              required
            />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
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
            {loading ? "Signing in…" : "Sign in"}
          </button>

          <p style={{ marginTop: 16, fontSize: 13.5, textAlign: "center", color: "var(--ink-soft)" }}>
            New accounts are created by an administrator.
          </p>
        </div>
      </form>
    </main>
  );
}
