# NIRN.Ai

> **NIRN.Ai** is an AI-powered Government Resolution (GR) drafting and alignment assistant built for the **MAHA-GR-ALIGN Hackathon**.

It helps government officers draft new Government Resolutions, retrieve relevant existing GRs, detect policy conflicts, and suggest references using Retrieval-Augmented Generation (RAG) and Large Language Models.

---

## ✨ Features

- 📄 AI-assisted Government Resolution drafting with **Rich Text Editing (Tiptap)**
- 🔍 Semantic search across Government Resolutions
- ⚠ Policy conflict detection and **Auto-save compliance checks**
- 📚 Automatic reference suggestions
- 🌐 Enhanced Bilingual support (Marathi & English) with optimized font rendering
- ⚡ Speed optimizations for local LLM execution (Ollama) and dynamic prompt slicing
- 🎨 Revamped user interface and Language Context management

---

## 🏗 Tech Stack

| Layer | Technology |
|--------|------------|
| Frontend | React, Vite, Tiptap, Framer Motion |
| Backend | FastAPI, Uvicorn |
| AI | LangChain, PyTorch, Transformers |
| Embeddings | SentenceTransformers (multilingual-e5-base) |
| Vector Database | FAISS |
| LLM | Ollama (Gemma 3) / GPT |
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

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd NIRN.Ai
   ```

2. **Create a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate      # macOS/Linux
   # Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize Embeddings & Backend Data**
   Run the automatic setup script to download the prebuilt vector index and document chunks from Google Drive:
   ```bash
   python setup.py
   ```
   *Note: This script automatically downloads the raw embeddings (~300MB) from the shared Google Drive folder and compiles the local FAISS database under `backend/data/`.*

5. **Run the backend**
   ```bash
   cd backend
   uvicorn app:app --reload
   ```

---

## 🗃️ Embeddings & Database Setup

### Automatic Download (Google Drive)
Prebuilt embeddings and corpus chunk metadata are hosted on [Google Drive](https://drive.google.com/drive/folders/1f__XsLWW8hEV19uNNgkhRVyWIim7dwNB?usp=drive_link). The `python setup.py` script:
- Checks if `backend/data/index.faiss`, `backend/data/chunks.pkl`, and `backend/data/metadata.json` are present.
- Downloads the raw source files using `gdown` if any are missing.
- Builds the FAISS index locally.
- Verifies the compiled index is ready.

### Manual Embeddings Regeneration
If you want to modify the documents dataset (located in `mahGRs-main/GRs`) or if the Google Drive download fails, you can regenerate the embeddings locally from scratch:
```bash
python build_embeddings.py
```
This script will:
- Parse and chunk the raw text files in your local dataset.
- Generate embeddings locally using the SentenceTransformer model (`intfloat/multilingual-e5-base`).
- Re-compile the FAISS index database and save the files to `backend/data/`.

### Troubleshooting
- **gdown download failures**: If you get a download quota or access error, ensure you have an active internet connection. If the issue persists, run the local regeneration script (`python build_embeddings.py`) to compile the index from your local `mahGRs-main` text corpus.
- **Memory Limit / CUDA crash**: Local embedding generation requires Python to load the `multilingual-e5-base` model. If your machine runs out of memory, verify that you have closed resource-intensive applications, or use a machine with Apple Silicon (MPS) or a GPU.

---

## 🦙 Local LLM Setup (Ollama + Gemma 3:4b)

NIRN.Ai supports running **100% offline** using local open-source LLMs via Ollama!

### Quick Setup Steps:

1. **Install Ollama**:
   - **macOS**: `brew install ollama` or download from [ollama.com](https://ollama.com)
   - **Windows / Linux**: Download installer from [ollama.com](https://ollama.com)
2. **Pull Gemma 3 (4B) model**:
   ```bash
   ollama pull gemma3:4b
   ```
3. **Configure `.env` in project root**:
   ```env
   LLM_PROVIDER=ollama
   OLLAMA_MODEL=gemma3:4b
   OLLAMA_BASE_URL=http://localhost:11434
   ```
4. **Start backend**:
   ```bash
   uvicorn backend.app:app --reload
   ```

*For detailed instructions and troubleshooting, see the [Ollama Setup Guide](file:///Users/avomine/VSCode/NIRN.Ai/OLLAMA_SETUP.md).*

---

## 📖 Documentation

Detailed documentation is available in the **docs** folder.

| Document | Description |
|----------|-------------|
| `OLLAMA_SETUP.md` | Full Ollama & `gemma3:4b` local model setup guide |
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
