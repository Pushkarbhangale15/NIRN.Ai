// findClauseInDoc.js — locates a flagged conflict clause inside the TipTap
// (ProseMirror) document so it can be selected, highlighted, and scrolled
// into view. There's no built-in "search in document" in TipTap/ProseMirror.
//
// Matches within a single textblock (paragraph/heading/listItem) only:
// draft clauses are extracted upstream (conflict_detection's clause
// splitter) as single paragraphs, and convertGRToHTML renders each as one
// <p>, so this is the common case. A clause split across multiple blocks
// (e.g. a manual line break mid-clause) won't be found — documented
// limitation, not handled in v1.

function normalize(text) {
  return text.trim().replace(/\s+/g, ' ');
}

// Returns { from, to } ProseMirror positions of the first occurrence of
// `needle` inside `doc`, or null if not found (e.g. the clause text has
// drifted since detection, from an unrelated edit elsewhere in the draft).
export function findClauseRange(doc, needle) {
  const target = normalize(needle || '');
  if (!target) return null;

  let result = null;
  doc.descendants((node, pos) => {
    if (result || !node.isTextblock) return true;

    const blockText = normalize(doc.textBetween(pos, pos + node.nodeSize, ' ', ' '));
    const idx = blockText.indexOf(target);
    if (idx !== -1) {
      // +1 to step past the block's own opening token into its text content.
      result = { from: pos + 1 + idx, to: pos + 1 + idx + target.length };
    }
    return !result;
  });

  return result;
}
