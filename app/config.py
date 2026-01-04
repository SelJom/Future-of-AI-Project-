import os
from dotenv import load_dotenv

load_dotenv()


class Config:
     # --- OLLAMA SETTINGS ---
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    LLM_API_KEY = os.getenv("LLM_API_KEY", "ollama")
    LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2-vision")
    # LLM_MODEL = os.getenv("LLM_MODEL", "tinyllama")

    VISION_MODEL_NAME = os.getenv("VISION_MODEL_NAME", "llama3.2-vision")
    # VISION_MODEL_NAME = os.getenv("VISION_MODEL_NAME", "moondream")


     # --- VECTOR DATABASE ---
    CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
    
    # --- NEW: MEDICAL EMBEDDINGS ---
    EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "pritamdeka/S-PubMedBert-MS-MARCO")
    # EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")

     # --- FAIRNESS / SAFETY THRESHOLDS ---
    TOXICITY_THRESHOLD = 3.0  # Out of 10
    COMPLEXITY_LEVELS = {
        "Niveau 1 (ELI5)": "Explain like I'm 5 years old. Use very simple words, analogies, and short sentences.",
        "Niveau 2 (Grand Public)": "General public. Clear, standard language, avoid jargon without explanation.",
        "Niveau 3 (Initié)": "Informed patient. Use correct terminology but explain complex mechanisms.",
        "Niveau 4 (Avancé)": "Advanced understanding. Detailed biological mechanisms and statistics.",
        "Niveau 5 (Expert)": "Medical professional level. precise clinical terminology, dense information."
    }



