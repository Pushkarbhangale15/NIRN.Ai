# Project Setup

Clone repository

```bash
git clone <repo-url>
```

Go inside

```bash
cd NIRN.Ai
```

Create virtual environment

```bash
python3 -m venv venv
```

Activate

macOS/Linux

```bash
source venv/bin/activate
```

Windows

```powershell
venv\Scripts\activate
```

Install packages

```bash
pip install -r requirements.txt
```

Run backend

```bash
uvicorn backend.app:app --reload
```