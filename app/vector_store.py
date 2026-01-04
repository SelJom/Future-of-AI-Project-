# app/vector_store.py
import chromadb
import uuid
import datetime
from langchain_huggingface import HuggingFaceEmbeddings 
from app.config import Config

def get_vector_store():
    # 1. Init du client Chroma
    client = chromadb.PersistentClient(path=Config.CHROMA_DB_PATH)
    
    embedding_func = HuggingFaceEmbeddings(
        model_kwargs={'device': 'cuda'},
        model_name=Config.EMBEDDING_MODEL_NAME

    )
    
    collection = client.get_or_create_collection(
        name="medical_knowledge_base",
        metadata={"hnsw:space": "cosine"}
    )
    return collection, embedding_func

def query_trials(query_text: str, n_results=3):
    collection, embedding_func = get_vector_store()
    query_vec = embedding_func.embed_query(query_text)
    
    results = collection.query(
        query_embeddings=[query_vec],
        n_results=n_results,
        where={"type": "trial"}
    )
    
    if not results['documents'] or not results['documents'][0]:
        return ["System Info: No specific trials found."]
    return results['documents'][0]

def log_interaction(user_input, ai_response, source_type, fairness_score=None):
    collection, embedding_func = get_vector_store()
    
    doc_text = f"User: {user_input} | AI: {ai_response}"
    
    # Gestion sécurisée des scores si None
    tox = str(fairness_score.get('toxicity_score', 0)) if fairness_score else "N/A"
    comp = str(fairness_score.get('complexity_score', 0)) if fairness_score else "N/A"

    meta = {
        "type": "history",
        "source": source_type,
        "timestamp": str(datetime.datetime.now()),
        "fairness_toxicity": tox,
        "fairness_complexity": comp
    }
    
    ids = [str(uuid.uuid4())]
    embeddings = embedding_func.embed_documents([doc_text])
    
    collection.add(documents=[doc_text], embeddings=embeddings, metadatas=[meta], ids=ids)
    print("Interaction logged successfully.")

def get_history():
    """Récupère tout l'historique"""
    collection, _ = get_vector_store()
    try:
        results = collection.get(where={"type": "history"})
        history_items = []
        if results['documents']:
            for i in range(len(results['documents'])):
                item = {
                    "content": results['documents'][i],
                    "meta": results['metadatas'][i]
                }
                history_items.append(item)
        return history_items
    except Exception as e:
        print(f"Erreur historique: {e}")
        return []

def seed_db():
    # (Mettre à jour seed_db pour inclure le champ metadata {"type": "trial"})
    collection, embedding_func = get_vector_store()
    if collection.count() == 0:
        docs = ["NCT001: Phase 3 Trial...", "NCT002: Metformin...", "NCT003: CAR-T..."]
        ids = ["1", "2", "3"]
        metas = [{"type": "trial"}] * 3 # Ajout du type
        embeddings = embedding_func.embed_documents(docs)
        collection.add(documents=docs, embeddings=embeddings, ids=ids, metadatas=metas)