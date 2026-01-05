# 🏥 Medical AI Assistant & Prescription Scanner

A privacy-focused, local medical assistant powered by **FastAPI**, **LangChain**, **LangGraph**, and **Ollama**. This application allows users to chat with an AI regarding health queries and upload prescription images or PDFs for instant OCR analysis and explanation.

## ✨ Features

* **Medical Chatbot:** Context-aware health assistant (considers age, language, and literacy level).
* **Prescription Scanner:** Upload images/PDFs to extract medication details via Vision models.
* **Local Privacy:** Runs entirely on your machine using Ollama (no data sent to the cloud).
* **Safety Audits:** All responses are checked for toxicity and hallucinations before display.

---

## 🛠️ Setup & Installation

### 1. Install Ollama & Models
This project requires **Ollama** to run the AI models locally.

1.  **Download Ollama:** Visit [ollama.com](https://ollama.com/) and install the version for your OS.
2.  **Pull the Models:** Open your terminal and run the following commands to download the required brain and vision models:

```bash
# Chat & Logic Model
ollama pull llama3.2

# Vision Model (for scanning prescriptions)
ollama pull llama3.2-vision
```

Note: Keep the Ollama app running in the background.

2. Set Up Virtual Environment
Open your terminal in the project folder and run the command for your operating system:

🍎 macOS / 🐧 Linux

Bash

# Create venv
python3 -m venv venv

# Activate venv
source venv/bin/activate
🪟 Windows

Bash

# Create venv
python -m venv venv

# Activate venv
venv\Scripts\activate
3. Install Python Dependencies
With your virtual environment activated, install the necessary libraries:

Bash

pip install fastapi uvicorn langchain langchain-community langchain-core langchain-huggingface langgraph chromadb sentence-transformers python-multipart python-dotenv httpx
🚀 How to Launch
Start the Server: Ensure your virtual environment is active, then run:

Bash

python server.py
Open the App: Open your web browser and navigate to:

http://localhost:8000