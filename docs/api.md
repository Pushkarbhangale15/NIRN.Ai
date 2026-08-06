# API Reference

This is a route map, not full request/response schemas — for those, run
the backend and open the auto-generated OpenAPI docs at
**http://localhost:8000/docs**, which is always in sync with the code.

All routes are prefixed `/api`. Most require `Authorization: Bearer
<token>` from `POST /api/auth/login` — see **[backend/README.md](../backend/README.md)**
for the auth model, rate limiting, and which routes are public. Admin
routes require the officer's role to be `admin`.

## Auth (`backend/auth_routes.py`)
| Method | Path | Notes |
|---|---|---|
| POST | `/api/auth/login` | Rate-limited (slowapi), generic error on failure |
| GET | `/api/officers/me` | Current officer profile |
| POST | `/api/officers/me/change-password` | |

## Drafts (`backend/routes.py`)
| Method | Path | Notes |
|---|---|---|
| POST | `/api/drafts` | Create a draft from raw text (Upload GR flow) |
| GET | `/api/drafts` | Paginated history |
| GET | `/api/drafts/{draft_id}` | Full detail incl. conflicts/references |
| PATCH | `/api/drafts/{draft_id}` | Save editor content (snapshots previous version) |
| DELETE | `/api/drafts/{draft_id}` | Archive |
| POST | `/api/copilot/draft` | AI-generate a new GR draft |
| POST | `/api/copilot/chat` | Copilot chat over a draft |
| POST | `/api/copilot/compare` | Side-by-side GR comparison |
| POST | `/api/copilot/explain-clause` | Plain-language clause explanation |
| POST | `/api/upload-gr/parse-file` | Extract text from an uploaded `.pdf`/`.docx`/`.txt` (public, no auth) |

## Analysis (`backend/routes.py`)
| Method | Path | Notes |
|---|---|---|
| POST | `/api/analysis/{draft_id}` | Runs all four checks below in one call — what the main screen uses |
| POST | `/api/analysis/{draft_id}/template` | Manual of Office Procedure rule checks |
| POST | `/api/analysis/{draft_id}/references` | Citation extraction + corpus resolution |
| POST | `/api/analysis/{draft_id}/conflicts` | Cross-departmental conflict detection |
| POST | `/api/analysis/{draft_id}/terminology` | Bilingual terminology mapping |
| POST | `/api/conflicts/detect` | Standalone conflict detection on raw text, no draft/persistence |

## Conflict resolution (`backend/routes.py`)
| Method | Path | Notes |
|---|---|---|
| GET | `/api/drafts/{draft_id}/conflicts` | Persisted conflicts for a draft |
| PATCH | `/api/conflicts/{conflict_id}/dismiss` | Flag as a false positive |
| POST | `/api/conflicts/{conflict_id}/resolve` | Generate + re-verify a revised clause (one LLM call); does not persist |
| POST | `/api/conflicts/{conflict_id}/resolve/accept` | Commit the revision: patches the draft, marks the conflict `resolved` |

`resolution_status` on a conflict is one of `not_attempted`, `resolved`,
`attempted_still_conflicting`, `attempted_error` — durable, read back on
every analysis run rather than recomputed on the fly.

## Corpus / search (`backend/routes.py`)
| Method | Path | Notes |
|---|---|---|
| GET | `/api/corpus/search` | Semantic search over the GR corpus (public) |
| GET | `/api/corpus/{gr_id}/ocr` | Full OCR text for a corpus GR |
| GET | `/api/official-source/{gr_number}` | Official source metadata |
| GET | `/api/official-gr/{gr_number}` | Official GR document |
| GET | `/api/knowledge/search` | Search the government terminology glossary |
| GET | `/api/health/db` | DB connectivity check |

## Export (`backend/export_docx.py`)
| Method | Path | Notes |
|---|---|---|
| POST | `/api/export/docx` | Export a draft as a Word document, matching editor formatting |

## Admin (`backend/admin_routes.py`, admin role required)
| Method | Path | Notes |
|---|---|---|
| GET | `/api/admin/summary` | Counts dashboard |
| GET | `/api/admin/drafts` | All drafts across officers |
| GET | `/api/officers` | List officers |
| POST | `/api/officers` | Create an officer |
| GET | `/api/officers/{officer_id}/drafts` | An officer's drafts |
| PATCH | `/api/officers/{officer_id}` | Update officer |
| PATCH | `/api/officers/{officer_id}/activate` | |
| PATCH | `/api/officers/{officer_id}/deactivate` | |
| POST | `/api/officers/{officer_id}/reset-password` | |
| DELETE | `/api/officers/{officer_id}` | |
