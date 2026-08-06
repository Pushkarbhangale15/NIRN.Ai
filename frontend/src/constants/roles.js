/**
 * constants/roles.js — display-label mapping for the officer_role
 * values (officer/reviewer/admin). The three-tier approval workflow
 * (Drafting Officer -> Reviewing Officer -> Approving Authority) reuses
 * these exact values; only the display label changes, defined once
 * here and reused everywhere a role is shown (Admin officer table,
 * Approval queues/banners, workflow history).
 *
 * Mirrors backend/role_labels.py — the backend copy exists for its own
 * server-side logging, but every user-facing label in this app is
 * rendered client-side via LanguageContext, so this is the copy that
 * actually reaches the UI.
 */

export const ROLE_LABEL_KEYS = {
  officer: "role_label_officer",
  reviewer: "role_label_reviewer",
  admin: "role_label_admin",
};

export const ROLES = ["officer", "reviewer", "admin"];

export function roleLabel(role, t) {
  return t(ROLE_LABEL_KEYS[role] || "role_label_officer");
}
