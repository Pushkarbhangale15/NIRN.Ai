# NIRN.Ai

> **NIRN.Ai** is an AI-powered Government Resolution (GR) drafting and alignment assistant built for the **MAHA-GR-ALIGN Hackathon**.

It helps government officers draft new Government Resolutions, retrieve relevant existing GRs, detect policy conflicts, and suggest references using Retrieval-Augmented Generation (RAG) and Large Language Models.

---

## ✨ Features

- 📄 AI-assisted Government Resolution drafting
- 🔍 Semantic search across Government Resolutions
- ⚠ Policy conflict detection
- 📚 Automatic reference suggestions
- 🌐 Bilingual support (Marathi & English)

---

## 🏗 Tech Stack

| Layer | Technology |
|--------|------------|
| Frontend | React |
| Backend | FastAPI |
| AI | LangChain |
| Embeddings | BGE-M3 |
| Vector Database | Qdrant |
| LLM | Gemma / GPT |
| Dataset | Maharashtra Government Resolution Dataset |

---

## 📂 Project Structure

```text
NIRN.Ai/

├── backend/
├── frontend/
├── data/
├── embeddings/
├── vector_db/
├── prompts/
├── models/
├── docs/
├── README.md
├── CONTRIBUTING.md
├── requirements.txt
└── LICENSE
```

---

## 🚀 Quick Start

Clone the repository

```bash
git clone <repository-url>
cd NIRN.Ai
```

Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate      # macOS/Linux
```

Windows

```powershell
venv\Scripts\activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

Run the backend

```bash
uvicorn backend.app:app --reload
```

---

## 📖 Documentation

Detailed documentation is available in the **docs** folder.

| Document | Description |
|----------|-------------|
| `docs/setup.md` | Complete project setup |
| `docs/api.md` | Backend API documentation |
| `docs/architecture.md` | System architecture |
| `CONTRIBUTING.md` | Development workflow and contribution guide |

---

## 👥 Team

- **Pushkar** — Team Lead • AI/RAG
- **Prasad** — Data Processing & Embeddings
- **Kumar** — Backend
- **Tanmay** — Frontend

---

## 📄 License

This project is licensed under the MIT License.