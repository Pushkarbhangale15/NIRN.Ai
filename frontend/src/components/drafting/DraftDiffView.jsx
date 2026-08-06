import { useCallback, useRef } from "react";
import { useLanguage } from "../../LanguageContext.jsx";

/**
 * DraftDiffView (Task 3b) — VS Code-style side-by-side merge view over
 * the word-level diff segments computed server-side by diffing.py.
 * LEFT = before (deletions highlighted), RIGHT = after (insertions
 * highlighted), scroll-synchronised. Stacks vertically on mobile.
 *
 * Separate from HashBadge/integrity hashing (Task 1): this shows WHAT
 * changed; the hash proves the stored content wasn't tampered with.
 */
export default function DraftDiffView({ segments, additions, deletions, unchanged, beforeLabel, afterLabel }) {
  const { t } = useLanguage();
  const leftRef = useRef(null);
  const rightRef = useRef(null);
  const syncingSide = useRef(null);

  const handleScroll = useCallback((side) => (e) => {
    if (syncingSide.current && syncingSide.current !== side) return;
    const other = side === "left" ? rightRef.current : leftRef.current;
    if (!other) return;
    syncingSide.current = side;
    other.scrollTop = e.target.scrollTop;
    requestAnimationFrame(() => {
      syncingSide.current = null;
    });
  }, []);

  if (unchanged || !segments || segments.length === 0) {
    return <div className="diff-empty-state">{t("diff_no_changes")}</div>;
  }

  return (
    <div>
      <div className="diff-summary">
        <span className="diff-summary-add">
          +{additions} {t("diff_additions")}
        </span>
        <span className="diff-summary-del">
          -{deletions} {t("diff_deletions")}
        </span>
      </div>
      <div className="diff-view">
        <div className="diff-pane">
          <div className="diff-pane-header diff-pane-header-before">{beforeLabel || t("diff_before_label")}</div>
          <div className="diff-pane-body" ref={leftRef} onScroll={handleScroll("left")}>
            {segments.map((seg, i) => {
              if (seg.type === "insert") return null;
              if (seg.type === "delete") {
                return (
                  <mark key={i} className="diff-mark-delete">
                    {seg.text}
                  </mark>
                );
              }
              return <span key={i}>{seg.text}</span>;
            })}
          </div>
        </div>
        <div className="diff-pane">
          <div className="diff-pane-header diff-pane-header-after">{afterLabel || t("diff_after_label")}</div>
          <div className="diff-pane-body" ref={rightRef} onScroll={handleScroll("right")}>
            {segments.map((seg, i) => {
              if (seg.type === "delete") return null;
              if (seg.type === "insert") {
                return (
                  <mark key={i} className="diff-mark-insert">
                    {seg.text}
                  </mark>
                );
              }
              return <span key={i}>{seg.text}</span>;
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
