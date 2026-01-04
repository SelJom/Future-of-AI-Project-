import os
import json
import uuid
import datetime
import torch
import chromadb
from langchain_huggingface import HuggingFaceEmbeddings
from app.config import Config

# ==========================================
# PART 1: SESSION MANAGEMENT (Chat History)
# ==========================================
SESSION_FILE = "./data/sessions.json"

def ensure_session_file():
    """Ensures the data directory and sessions.json file exist."""
    if not os.path.exists("./data"):
        os.makedirs("./data")
    if not os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)

def get_all_sessions():
    """Returns the dictionary of all sessions."""
    ensure_session_file()
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def create_session(title="Nouvelle Conversation"):
    """Creates a new session entry."""
    sessions = get_all_sessions()
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "title": title,
        "timestamp": str(datetime.datetime.now()),
        "history": []
    }
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(sessions, f, indent=4)
    return session_id

def save_message_to_session(session_id, role, content):
    """Appends a message to the history."""
    sessions = get_all_sessions()
    if session_id in sessions:
        sessions[session_id]["history"].append({"role": role, "content": content})
        
        # Note: We removed the automatic renaming here because 
        # main.py now handles it with the LLM logic.
        
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(sessions, f, indent=4)

def get_session_history(session_id):
    """Returns the message list for a specific session."""
    sessions = get_all_sessions()
    return sessions.get(session_id, {}).get("history", [])

# --- NEW FUNCTIONS ADDED BELOW ---

def delete_session(session_id: str):
    """
    Deletes a specific session from the JSON file.
    """
    sessions = get_all_sessions()
    if session_id in sessions:
        del sessions[session_id]
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(sessions, f, indent=4)
        return True
    return False

def update_session_title(session_id: str, new_title: str):
    """
    Updates the title of a specific session.
    """
    sessions = get_all_sessions()
    if session_id in sessions:
        sessions[session_id]["title"] = new_title
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(sessions, f, indent=4, ensure_ascii=False)
        return True
    return False

# ==========================================
# PART 2: VECTOR STORE (RAG & Medical Brain)
# ==========================================

def get_device():
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"

def get_vector_store():
    # Ensure directory exists
    if not os.path.exists(Config.CHROMA_DB_PATH):
        os.makedirs(Config.CHROMA_DB_PATH)

    client = chromadb.PersistentClient(path=Config.CHROMA_DB_PATH)
    device = get_device()
    
    embedding_func = HuggingFaceEmbeddings(
        model_kwargs={'device': device},
        model_name=Config.EMBEDDING_MODEL_NAME,
        encode_kwargs={'normalize_embeddings': True}
    )

    collection = client.get_or_create_collection(
        name="medical_knowledge_base",
        metadata={"hnsw:space": "cosine"}
    )
    return collection, embedding_func

def query_trials(query_text: str, n_results=3):
    """
    Searches ChromaDB for medical context/trials.
    Used by the Medical Researcher Agent.
    """
    try:
        collection, embedding_func = get_vector_store()
        query_vec = embedding_func.embed_query(query_text)
        
        results = collection.query(
            query_embeddings=[query_vec],
            n_results=n_results,
            # We search broadly for any medical info
            # (Remove 'where' clause if your DB is mixed or you want generic search)
            where={"type": "trial"} 
        )
        
        if not results['documents'] or not results['documents'][0]:
            return ["Info Système : Aucune étude clinique spécifique trouvée en local."]
        
        return results['documents'][0]
    except Exception as e:
        print(f"Vector Store Query Error: {e}")
        return [f"Erreur de recherche base de données: {str(e)}"]

def seed_db():
    """
    Populate the DB with dummy data if empty.
    """
    collection, embedding_func = get_vector_store()
    if collection.count() == 0:
        docs = [
            "NCT001: Phase 3 Trial for Pembrolizumab in Stage IV NSCLC. Inclusion: Age > 18.",
            "NCT002: Study of Metformin for Type 2 Diabetes prevention. Exclusion: Kidney failure.",
            "NCT003: CAR-T Therapy for B-cell Lymphoma. Requirement: Prior chemo failure."
        ]
        ids = ["1", "2", "3"]
        metas = [{"type": "trial"}, {"type": "trial"}, {"type": "trial"}]
        embeddings = embedding_func.embed_documents(docs)
        collection.add(documents=docs, embeddings=embeddings, ids=ids, metadatas=metas)
        print("Database seeded with mock trials.")