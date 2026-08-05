"""
db/repositories/__init__.py — package marker.

SQL RULE: every file in this package builds queries exclusively with the
SQLAlchemy ORM / select() / insert() / update() constructs. Never an
f-string, never string concatenation. Column/sort-field names that come
from a client MUST be mapped through a hardcoded allowlist before use —
they can never be interpolated or bound directly. See
backend/README.md, "SQL injection prevention".
"""
