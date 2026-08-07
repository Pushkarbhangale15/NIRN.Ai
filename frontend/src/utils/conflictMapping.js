// Maps a ConflictOut row (from GET /api/drafts/{id}/conflicts) into the
// ConflictHit shape ConflictCard.jsx already expects (the shape POST
// /api/analysis/{id}/conflicts returns). Mirrors backend/routes.py's own
// _conflict_row_to_hit — confidence/conflict_type/source_url aren't columns
// on DraftConflict, so those are the same fixed constants the backend uses
// for DB-sourced (non-fresh) hits.
export function conflictOutToHit(c) {
  return {
    conflict_id: c.conflict_id,
    draft_clause: c.draft_excerpt || "",
    existing_gr_id: c.conflicting_gr_id || "",
    existing_gr_title: c.source_gr_title || "",
    existing_department: c.source_of_conflict || "",
    existing_clause: c.conflicting_text || "",
    relation: "overlap",
    confidence: 1.0,
    justification: c.justification,
    source_url: null,
    conflict_type: "Policy Conflict",
    severity: c.severity,
    resolution_status: c.resolution_status,
    resolved_clause_text: c.resolved_clause_text,
    source_ocr_low_confidence: c.source_ocr_low_confidence,
    is_dismissed: c.is_dismissed,
    dismissed_reason: c.dismissed_reason,
  };
}
