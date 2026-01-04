import os
from dotenv import load_dotenv

load_dotenv()

# class Config:
#     import os

# class Config:
#     # --- OLLAMA SETTINGS ---
#     LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
#     LLM_API_KEY = os.getenv("LLM_API_KEY", "ollama")
#     LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2-vision")
#     VISION_MODEL_NAME = os.getenv("VISION_MODEL_NAME", "llama3.2-vision")

#     # --- VECTOR DATABASE ---
#     CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
    
#     # --- NEW: MEDICAL EMBEDDINGS ---
#     EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "pritamdeka/S-PubMedBert-MS-MARCO")

#     # --- FAIRNESS / SAFETY THRESHOLDS ---
#     TOXICITY_THRESHOLD = 3.0  # Out of 10
#     COMPLEXITY_THRESHOLD = 8.0 # Out of 10




class Config:
    # --- OLLAMA SETTINGS ---
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    LLM_API_KEY = os.getenv("LLM_API_KEY", "ollama")
    
    # MODIFICATION 1 : Modèle de chat ultra-léger (TinyLlama)
    # C'est lui qui servira pour le RAG et la discussion
    LLM_MODEL = os.getenv("LLM_MODEL", "tinyllama")
    
    # MODIFICATION 2 : Modèle de vision ultra-léger (Moondream)
    # C'est lui qui lira les ordonnances
    VISION_MODEL_NAME = os.getenv("VISION_MODEL_NAME", "moondream")

    # --- VECTOR DATABASE ---
    CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
    
    # --- MEDICAL EMBEDDINGS ---
    # MODIFICATION 3 : On passe sur un modèle générique très rapide pour le test
    # Si 'pritamdeka' est trop lent à télécharger/charger, utilisez 'all-MiniLM-L6-v2'
    EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")

    # --- FAIRNESS / SAFETY THRESHOLDS ---
    TOXICITY_THRESHOLD = 3.0  
    COMPLEXITY_THRESHOLD = 8.0