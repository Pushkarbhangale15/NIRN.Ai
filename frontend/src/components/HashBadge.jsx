import { useState } from "react";
import { useLanguage } from "../LanguageContext.jsx";
import { api } from "../api.js";

/**
 * HashBadge — Task 1: shows a truncated content_sha256 (server-computed,
 * never client-supplied) with a "copy full hash" affordance and a
 * "Verify" button that calls GET
 * /api/drafts/{id}/versions/{version_number}/verify, which recomputes
 * the hash of the stored content server-side and confirms it matches.
 *
 * This proves tamper-evidence — it does NOT diff content; see
 * DraftDiffView for that separate mechanism.
 *
 * `hash` is optional: the Approval tab already knows it (from
 * approval-view) and passes it in directly. The History version list
 * only knows a version NUMBER (from workflow-history, which doesn't
 * carry the hash) — there, this renders "—" until Verify is clicked,
 * which reveals the server-recomputed hash alongside the match result.
 */
export default function HashBadge({ draftId, versionNumber, hash, label }) {
  const { t } = useLanguage();
  const [copied, setCopied] = useState(false);
  const [verifyState, setVerifyState] = useState(null); // null | 'checking' | 'ok' | 'fail' | 'error'
  const [resolvedHash, setResolvedHash] = useState(hash || null);

  const handleCopy = () => {
    if (!resolvedHash) return;
    navigator.clipboard.writeText(resolvedHash).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const handleVerify = async () => {
    if (!draftId || versionNumber == null || verifyState === "checking") return;
    setVerifyState("checking");
    try {
      const res = await api.verifyVersion(draftId, versionNumber);
      setResolvedHash(res.hash);
      setVerifyState(res.verified ? "ok" : "fail");
    } catch {
      setVerifyState("error");
    }
  };

  return (
    <div className="hash-badge">
      <span className="hash-badge-label">
        {label || t("integrity_hash_label")}
        {versionNumber != null ? ` (v${versionNumber})` : ""}:
      </span>
      {resolvedHash ? (
        <>
          <code className="hash-badge-value" title={resolvedHash}>
            {resolvedHash.slice(0, 12)}…
          </code>
          <button type="button" className="hash-badge-btn" onClick={handleCopy}>
            {copied ? t("integrity_hash_copied") : t("integrity_copy_hash")}
          </button>
        </>
      ) : (
        <span className="hash-badge-value" style={{ color: "var(--ink-soft)" }}>
          —
        </span>
      )}
      {draftId && versionNumber != null && (
        <button
          type="button"
          className="hash-badge-btn"
          onClick={handleVerify}
          disabled={verifyState === "checking"}
        >
          {verifyState === "checking" ? t("integrity_verifying") : t("integrity_verify_btn")}
        </button>
      )}
      {verifyState === "ok" && <span className="hash-badge-result ok">✓ {t("integrity_verified_ok")}</span>}
      {verifyState === "fail" && <span className="hash-badge-result fail">✕ {t("integrity_verified_fail")}</span>}
      {verifyState === "error" && <span className="hash-badge-result fail">⚠ Error</span>}
    </div>
  );
}
