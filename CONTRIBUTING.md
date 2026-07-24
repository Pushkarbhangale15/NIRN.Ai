# Contributing Guide

Welcome to NIRN.AI!

Please follow these rules while contributing.

---

# Branch Rules

Never commit directly to `main`.

Create your own branch.

Example

```bash
git checkout -b your-name
```

Examples

```
pushkar
prasad
kumar
tanmay
```

---

# Daily Workflow

Before starting work

```bash
git checkout main
git pull origin main
```

Switch to your branch

```bash
git checkout your-name
```

Work normally.

Commit often.

```bash
git add .
git commit -m "Describe your changes"
git push
```

---

# Commit Message Examples

Good

```
Added chunking module

Implemented FastAPI search endpoint

Connected frontend search page

Fixed embedding generation
```

Bad

```
Update

Done

Changes
```

---

# Coding Guidelines

- Use meaningful variable names.
- Keep functions small.
- Add comments where needed.
- Don't duplicate code.
- Test before pushing.

---

# Pull Requests

Before creating a Pull Request:

- Code runs successfully.
- No syntax errors.
- No unnecessary files committed.
- Explain what changed.

---

# Team Responsibilities

## Pushkar

- AI
- RAG
- Integration

---

## Prasad

- Dataset
- Metadata
- Chunking

---

## Kumar

- Backend
- APIs

---

## Tanmay

- Frontend
- React

---

Happy Coding 🚀