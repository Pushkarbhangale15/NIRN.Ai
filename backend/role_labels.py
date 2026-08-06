"""
role_labels.py — display-label mapping for the existing officer_role
enum (officer/reviewer/admin).

The three-tier approval workflow (Drafting Officer -> Reviewing Officer
-> Approving Authority) reuses these exact role values — no new role is
added to the enum, and existing rows are never migrated. This module is
the single place the officer/reviewer/admin -> display-label mapping is
defined on the backend side (used for readable server logs); the
frontend has its own mirror in src/constants/roles.js, since all
user-facing i18n in this app is rendered client-side via
LanguageContext, never composed server-side.
"""

from db.models import OfficerRole

ROLE_DISPLAY_LABELS = {
    OfficerRole.OFFICER: {"en": "Drafting Officer", "mr": "मसुदा अधिकारी"},
    OfficerRole.REVIEWER: {"en": "Reviewing Officer", "mr": "पुनरावलोकन अधिकारी"},
    OfficerRole.ADMIN: {"en": "Approving Authority", "mr": "मंजूरी प्राधिकरण"},
}


def role_display_label(role, language: str = "en") -> str:
    key = role if isinstance(role, OfficerRole) else OfficerRole(role)
    labels = ROLE_DISPLAY_LABELS[key]
    return labels.get(language, labels["en"])
