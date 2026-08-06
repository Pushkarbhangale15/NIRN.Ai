/**
 * constants/workflowStatus.js — the six generated_drafts.status values
 * and their display label / badge color, defined once and reused by
 * every status badge in the app (History, Draft page, Approval
 * queues, Admin's All Drafts tab) instead of re-declaring the list or
 * the CSS class name per component.
 *
 * 'returned' exists in the DB enum for completeness but the backend
 * never actually persists it as a status — a returned draft goes
 * straight back to 'draft' with returned_reason set (see
 * db.models.DraftStatus on the backend). It's kept here anyway so a
 * badge still renders sensibly if it's ever seen.
 */

export const DRAFT_STATUSES = ["draft", "submitted", "reviewed", "approved", "returned", "archived"];

export const STATUS_LABEL_KEYS = {
  draft: "status_draft",
  submitted: "status_submitted",
  reviewed: "status_reviewed",
  approved: "status_approved",
  returned: "status_returned",
  archived: "status_archived",
};

export function statusLabel(status, t) {
  return t(STATUS_LABEL_KEYS[status] || "status_draft");
}

export function statusBadgeClass(status) {
  return `badge badge-status-${DRAFT_STATUSES.includes(status) ? status : "draft"}`;
}
