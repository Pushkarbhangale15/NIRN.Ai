import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import shasan from "../assets/shasan.svg";
import { useAuth } from "../AuthContext.jsx";
import { useLanguage } from "../LanguageContext.jsx";
import { api } from "../api.js";

const IconEye = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 5c-7 0-10 7-10 7s3 7 10 7 10-7 10-7-3-7-10-7Zm0 12a5 5 0 1 1 0-10 5 5 0 0 1 0 10Zm0-8a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z" />
  </svg>
);

function LoginCard({ onSuccess }) {
  const { t, siteLanguage, toggleLanguage } = useLanguage();
  const { login } = useAuth();
  const location = useLocation();
  const [loginId, setLoginId] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const returnTo = location.state?.returnTo || "/";

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (submitting) return;
    setError("");
    setSubmitting(true);
    try {
      const officer = await login(loginId.trim(), password);
      onSuccess(officer, returnTo);
    } catch (err) {
      setError(err.message || t("login_error_generic"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="login-card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1>{t("login_heading")}</h1>
          <p className="login-sub">
            {location.state?.returnTo ? t("login_returnto_note") : t("login_tagline")}
          </p>
        </div>
        <button
          type="button"
          onClick={toggleLanguage}
          className="nav-lang-toggle"
          style={{ flexShrink: 0 }}
        >
          {siteLanguage === "en" ? "मराठी" : "English"}
        </button>
      </div>

      <form onSubmit={handleSubmit} noValidate>
        <div className="login-field">
          <label htmlFor="login_id">{t("login_id_label")}</label>
          <input
            id="login_id"
            name="login_id"
            type="text"
            autoFocus
            autoComplete="username"
            value={loginId}
            onChange={(e) => setLoginId(e.target.value)}
            placeholder={t("login_id_placeholder")}
            required
          />
        </div>

        <div className="login-field">
          <label htmlFor="password">{t("login_password_label")}</label>
          <div className="login-password-row">
            <input
              id="password"
              name="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              style={{ paddingRight: 64 }}
            />
            <button
              type="button"
              className="login-password-toggle"
              onClick={() => setShowPassword((s) => !s)}
              tabIndex={-1}
            >
              {showPassword ? t("login_hide_password") : t("login_show_password")}
            </button>
          </div>
        </div>

        <div className="login-error-slot">
          {error && <div className="login-error-message">{error}</div>}
        </div>

        <button
          type="submit"
          className="btn btn-red login-submit-btn"
          disabled={submitting || !loginId.trim() || !password}
        >
          {submitting ? (
            <>
              <span className="spinner-small" /> {t("login_submitting")}
            </>
          ) : (
            t("login_submit")
          )}
        </button>
      </form>

      <p className="login-footnote">{t("login_provisioned_note")}</p>
    </div>
  );
}

function ChangePasswordCard({ officer, onDone }) {
  const { t } = useLanguage();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (submitting) return;
    setError("");

    if (newPassword.length < 10) {
      setError(t("change_password_too_short"));
      return;
    }
    if (newPassword !== confirmPassword) {
      setError(t("change_password_mismatch"));
      return;
    }

    setSubmitting(true);
    try {
      await api.changeMyPassword(currentPassword, newPassword);
      setSuccess(true);
      setTimeout(() => onDone(), 900);
    } catch (err) {
      setError(err.message || t("change_password_mismatch"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="login-card">
      <h1>{t("change_password_heading")}</h1>
      <p className="login-sub">{t("change_password_sub")}</p>

      <form onSubmit={handleSubmit} noValidate>
        <div className="login-field">
          <label htmlFor="current_password">{t("change_password_current")}</label>
          <input
            id="current_password"
            type="password"
            autoFocus
            autoComplete="current-password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            required
          />
        </div>
        <div className="login-field">
          <label htmlFor="new_password">{t("change_password_new")}</label>
          <input
            id="new_password"
            type="password"
            autoComplete="new-password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            minLength={10}
            required
          />
        </div>
        <div className="login-field">
          <label htmlFor="confirm_password">{t("change_password_confirm")}</label>
          <input
            id="confirm_password"
            type="password"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            minLength={10}
            required
          />
        </div>

        <div className="login-error-slot">
          {error && <div className="login-error-message">{error}</div>}
          {success && (
            <div className="login-error-message" style={{ background: "#e3f5e8", borderColor: "var(--ok)", color: "var(--ok)" }}>
              {t("change_password_success")}
            </div>
          )}
        </div>

        <button
          type="submit"
          className="btn btn-red login-submit-btn"
          disabled={submitting || success || !currentPassword || !newPassword || !confirmPassword}
        >
          {submitting ? (
            <>
              <span className="spinner-small" /> {t("change_password_submitting")}
            </>
          ) : (
            t("change_password_submit")
          )}
        </button>
      </form>
    </div>
  );
}

export default function Login() {
  const { t } = useLanguage();
  const { officer, refreshMe } = useAuth();
  const navigate = useNavigate();
  const [pendingOfficer, setPendingOfficer] = useState(null);

  const handleLoginSuccess = (loggedInOfficer, returnTo) => {
    if (loggedInOfficer.must_change_password) {
      setPendingOfficer(loggedInOfficer);
    } else {
      navigate(returnTo, { replace: true });
    }
  };

  const handlePasswordChangeDone = async () => {
    await refreshMe();
    navigate("/", { replace: true });
  };

  const active = pendingOfficer || (officer?.must_change_password ? officer : null);

  return (
    <div className="login-screen">
      <div className="login-panel">
        <div className="geo-shape geo-shape-1" />
        <div className="geo-shape geo-shape-2" />
        <div className="geo-shape geo-shape-3" />
        <div className="login-panel-logo">
          <img src={shasan} alt="Government of Maharashtra" />
          <span className="login-panel-wordmark">NIRN.Ai</span>
        </div>
        <p className="login-panel-tagline">{t("login_tagline")}</p>
      </div>
      <div className="login-form-side">
        {active ? (
          <ChangePasswordCard officer={active} onDone={handlePasswordChangeDone} />
        ) : (
          <LoginCard onSuccess={handleLoginSuccess} />
        )}
      </div>
    </div>
  );
}
