## This is for you Kumar...
# Backend API

## GET /

Returns

```json
{
    "status":"running"
}
```

---

## POST /search

Input

```json
{
    "query":"Scholarship"
}
```

Output

```json
{
    "answer":"...",
    "references":[]
}
```

---

## POST /draft

Input

```json
{
    "prompt":"Create AI Lab GR"
}
```

Output

Generated draft.

---

## POST /conflict

Input

Draft text.

Output

Detected conflicts.

---

## POST /reference

Returns similar GR references.