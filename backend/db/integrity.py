"""
db/integrity.py — SHA-256 tamper-evidence for draft_versions content.

Not a diff mechanism (see diffing.py for that) — this proves, after the
fact, that a stored version's content matches exactly what was written
at that workflow stage, for a government audit trail. Always computed
server-side; a client-supplied hash is never accepted anywhere in this
codebase.
"""

import hashlib


def hash_content(content: str) -> str:
    return hashlib.sha256((content or "").encode("utf-8")).hexdigest()


def verify_content(content: str, expected_hash: str) -> bool:
    return hash_content(content) == expected_hash
