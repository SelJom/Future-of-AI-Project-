import chromadb
from langchain_huggingface import HuggingFaceEmbeddings 
from app.config import Config

def get_vector_store():
    # 1. Use the path from Config
    client = chromadb.PersistentClient(path=Config.CHROMA_DB_PATH)
    
    # 2. Use the model name from Config
    embedding_func = HuggingFaceEmbeddings(
        model_name=Config.EMBEDDING_MODEL_NAME,
        model_kwargs={'device': 'cuda'}, 
        encode_kwargs={'normalize_embeddings': True}
    )
    
    collection = client.get_or_create_collection(
        name="clinical_trials",
        metadata={"hnsw:space": "cosine"}
    )
    return collection, embedding_func

def query_trials(query_text: str, n_results=3):
    collection, embedding_func = get_vector_store()
    
    # Generate vector for the question
    query_vec = embedding_func.embed_query(query_text)
    
    results = collection.query(
        query_embeddings=[query_vec],
        n_results=n_results
    )
    
    if not results['documents'] or not results['documents'][0]:
        return ["System Info: No specific trials found in local DB. Using general knowledge."]
        
    return results['documents'][0]

def seed_db():
    """Seeds the DB with mock data for demonstration."""
    collection, embedding_func = get_vector_store()
    
    if collection.count() == 0:
        print("Seeding Database...")
        docs = [
            "NCT001: Phase 3 Trial for Pembrolizumab in Stage IV NSCLC. Inclusion: Age > 18.",
            "NCT002: Study of Metformin for Type 2 Diabetes prevention. Exclusion: Kidney failure.",
            "NCT003: CAR-T Therapy for B-cell Lymphoma. Requirement: Prior chemo failure."
        ]
        ids = ["1", "2", "3"]
        
        # Create embeddings using the medical model
        embeddings = embedding_func.embed_documents(docs)
        
        collection.add(documents=docs, embeddings=embeddings, ids=ids)
        print("Database seeded successfully.")