# 🦙 Ollama & Gemma 3 (4B) Setup Guide

This guide explains how team members can install **Ollama**, download the **`gemma3:4b`** model, and configure **NIRN.Ai** to run completely offline on local machines.

---

## 🛈 Overview

NIRN.Ai supports running local open-source LLMs via **Ollama**. This allows full offline functionality without relying on internet access or paid API keys.

---

## 📥 Step 1: Install Ollama

Choose the installer for your operating system:

### 🍎 macOS
- **Download**: [ollama.com/download/mac](https://ollama.com/download/mac) (Unzip and drag to Applications)
- **Or via Homebrew**:
  ```bash
  brew install ollama
  ```

### 🪟 Windows
- **Download**: [ollama.com/download/windows](https://ollama.com/download/windows)
- Run `OllamaSetup.exe` and follow the setup wizard.

### 🐧 Linux
- Run the terminal installation command:
  ```bash
  curl -fsSL https://ollama.com/install.sh | sh
  ```

---

## ⏬ Step 2: Download the `gemma3:4b` Model

Once Ollama is installed, open your Terminal (macOS/Linux) or Command Prompt / PowerShell (Windows) and run:

```bash
ollama pull gemma3:4b
```

> **Note**: `gemma3:4b` requires ~2.5 GB – 3 GB of disk space. Ensure Ollama service is active in the system tray / background.

---

## 🧪 Step 3: Test the Model (Optional)

Verify that Ollama and Gemma 3 are functioning correctly by running:

```bash
ollama run gemma3:4b "Explain Maharashtra Government Resolutions in short."
```

Type `/exit` or press `Ctrl+D` to exit the CLI chat session.

---

## ⚙️ Step 4: Configure NIRN.Ai

In your project root directory (`NIRN.Ai/`), open or create the `.env` file and set the following environment variables:

```env
# Switch LLM Provider to Ollama
LLM_PROVIDER=ollama

# Ollama local configuration
OLLAMA_MODEL=gemma3:4b
OLLAMA_BASE_URL=http://localhost:11434
```

*(If you ever want to switch back to Gemini API, set `LLM_PROVIDER=gemini` and provide `LLM_API_KEY`)*.

---

## 🚀 Step 5: Run the Project

1. **Activate your Python virtual environment**:
   ```bash
   # macOS / Linux
   source venv/bin/activate

   # Windows PowerShell
   venv\Scripts\activate
   ```

2. **Start the FastAPI Backend**:
   ```bash
   uvicorn backend.app:app --reload
   ```

3. **Start the Frontend (in a separate terminal)**:
   ```bash
   cd frontend
   npm run dev
   ```

The application will now use your local `gemma3:4b` LLM for drafting GRs, conflict analysis, and reference suggestions!

---

## ❓ Troubleshooting

- **Error: `ConnectionRefusedError` / Cannot connect to http://localhost:11434**
  Make sure Ollama is running in the background. You can start it manually by launching the Ollama desktop app or executing `ollama serve`.
- **Model Not Found (`model 'gemma3:4b' not found`)**
  Run `ollama list` to verify downloaded models. If missing, re-run `ollama pull gemma3:4b`.
- **Slow Generation Speed**
  Ensure your machine has sufficient RAM (8GB+ recommended) and close resource-heavy background apps.
