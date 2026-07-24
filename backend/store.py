"""
store.py — a dictionary pretending to be a database.

Day 1 does not need Postgres. Drafts live in memory so the API works
end to end immediately. Everything resets when the server restarts,
which is fine for a five-day hackathon and one less thing to break
during the demo.

To add persistence later, replace these four functions with database
calls. Nothing else in the codebase changes, because nothing else
touches the dictionary directly.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from schemas import Draft, DraftCreate

_drafts: Dict[str, Draft] = {}


def create_draft(payload: DraftCreate) -> Draft:
    """Store a new draft and return it with an id and timestamp."""
    draft = Draft(
        id=uuid.uuid4().hex[:12],
        created_at=datetime.now(timezone.utc),
        **payload.model_dump(),
    )
    _drafts[draft.id] = draft
    return draft


def get_draft(draft_id: str) -> Optional[Draft]:
    """Return the draft, or None if it does not exist."""
    return _drafts.get(draft_id)


def list_drafts() -> List[Draft]:
    """All drafts, newest first."""
    return sorted(_drafts.values(), key=lambda d: d.created_at, reverse=True)


def delete_draft(draft_id: str) -> bool:
    """Returns True if something was deleted, False if the id was unknown."""
    return _drafts.pop(draft_id, None) is not None
