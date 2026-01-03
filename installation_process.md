# 🏥 Local Multi-Agent Health System (LangGraph + Llama 3)

**Architecture & Implementation Report Project**
*A 100% Local-First, Privacy-Preserving Medical Agent for Health Literacy & Clinical Trial Matching.*

---

## 📋 1. Prerequisites

Before running the project, ensure you have the following installed:

1.  **Python 3.10+**
2.  **Ollama** (Required for local LLM inference)
    * Download here: [https://ollama.com/download](https://ollama.com/download)

---

## 🚀 2. Quick Start Guide

### Step 1: Initialize the AI Model
Open a terminal and run the following command to download and serve the Llama 3 model locally. Keep this terminal window **open** in the background.

```bash
ollama run llama3
# Wait for the download to finish. 
# Once you see the '>>>' prompt, the model is ready.
# You can minimize this window, but do not close it.