import json
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from app.llm import get_llm
from app.vector_store import query_trials

llm = get_llm()

# --- 1. SUPERVISOR (Le Chef d'Orchestre) ---
def supervisor_node(state):
    """
    Analyse l'intention. Si c'est médical, on lance la chaîne complexe.
    Sinon, on répond simplement.
    """
    messages = state.get("messages", [])
    query = messages[-1].content if messages else ""
    
    system_prompt = """
    Tu es le Superviseur d'une IA médicale. Analyse la demande de l'utilisateur.
    
    SI la demande concerne :
    - Une maladie, un symptôme, un médicament.
    - Une explication d'ordonnance (OCR context).
    - Une question de santé complexe.
    -> Réponds JSON: {"next_step": "MEDICAL_CHAIN"}
    
    SINON (Salutations, blagues, questions hors sujet) :
    -> Réponds JSON: {"next_step": "GENERAL_CHAT"}
    """
    
    try:
        resp = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=query)])
        decision = json.loads(resp.content.replace("```json", "").replace("```", "").strip())
        return {"next_step": decision.get("next_step", "GENERAL_CHAT"), "iteration_count": 0}
    except:
        return {"next_step": "GENERAL_CHAT", "iteration_count": 0}

# --- 2. MEDICAL EXPERT (L'Analyste Factuel) ---
def medical_expert_node(state):
    """
    Récupère la vérité scientifique (via RAG ou connaissances brutes).
    Ne simplifie PAS. Cherche l'exactitude.
    """
    query = state["messages"][-1].content
    # Simulation RAG (ou votre vraie fonction query_trials)
    retrieved = query_trials(query) 
    facts = f"Documents RAG: {retrieved}\n\nConnaissances LLM brutes sur: {query}"
    
    return {"medical_facts": facts}

# --- 3. PROFILER (L'Anthropologue) ---
def profiler_node(state):
    """
    Transforme les données démographiques en stratégie de communication.
    """
    profile = state.get("user_profile", {})
    age = profile.get("age", 30)
    lang = profile.get("language", "Français")
    level = profile.get("literacy_level", "Moyen")
    
    prompt = f"""
    Tu es un expert en communication interculturelle et santé publique (Health Literacy).
    
    Patient: {age} ans. Langue: {lang}. Niveau lecture: {level}.
    
    Définis une stratégie de rédaction en 3 points :
    1. Ton (Empathique, Direct, Formel ?)
    2. Métaphores culturelles adaptées (ex: mécanique pour un ingénieur, nature pour contexte rural, etc. - INVENTE selon le profil).
    3. Tabous à éviter ou précautions de langage.
    
    Réponds uniquement avec la stratégie.
    """
    
    strategy = llm.invoke([HumanMessage(content=prompt)]).content
    return {"cultural_strategy": strategy}

# --- 4. TRANSLATOR (Le Pédagogue) ---
def translator_node(state):
    """
    Rédige l'explication en combinant Faits + Stratégie + (Optionnel) Critiques précédentes.
    """
    facts = state["medical_facts"]
    strategy = state["cultural_strategy"]
    feedback = state.get("critique_feedback", "Aucune critique pour l'instant.")
    messages = state["messages"]
    
    prompt = f"""
    Tu es le 'Health Literacy Translator'. 
    
    TA MISSION : Rédiger une réponse pour le patient.
    
    SOURCES MÉDICALES (Ne rien inventer) :
    {facts}
    
    STRATÉGIE DE COMMUNICATION :
    {strategy}
    
    FEEDBACK DU GUARDIAN (Corrections à appliquer si nécessaire) :
    {feedback}
    
    Rédige la réponse maintenant (en {state['user_profile'].get('language')}).
    """
    
    # On garde l'historique des messages pour le contexte
    response = llm.invoke([SystemMessage(content=prompt)] + messages[-2:]) # Contexte court
    return {"draft_response": response.content}

# --- 5. GUARDIAN (Le Superviseur de Sécurité - Boucle de Rétroaction) ---
def guardian_node(state):
    """
    Vérifie si la simplification n'a pas déformé la vérité médicale ou omis un danger.
    """
    facts = state["medical_facts"]
    draft = state["draft_response"]
    
    prompt = f"""
    Tu es le Docteur Superviseur (Safety Guardian).
    
    1. FAITS MÉDICAUX ORIGINAUX : {facts}
    2. BROUILLON SIMPLIFIÉ PROPOSÉ : {draft}
    
    TÂCHE : Détecte les erreurs graves.
    - Hallucination (Le brouillon dit un truc non présent dans les faits ?)
    - Omission dangereuse (Un effet secondaire grave a disparu ?)
    - Infantilisation excessive ou ton inapproprié ?
    
    Réponds JSON :
    {{
        "status": "APPROVED" ou "REJECTED",
        "feedback": "Si REJECTED, explique précisément quoi corriger. Si APPROVED, mets 'RAS'."
    }}
    """
    
    try:
        resp = llm.invoke([HumanMessage(content=prompt)])
        analysis = json.loads(resp.content.replace("```json", "").replace("```", "").strip())
        return {
            "safety_status": analysis.get("status", "REJECTED"),
            "critique_feedback": analysis.get("feedback", "Erreur parsing"),
            "iteration_count": state["iteration_count"] + 1
        }
    except:
        # En cas de doute, on rejette
        return {"safety_status": "REJECTED", "critique_feedback": "Format JSON invalide, réessaie.", "iteration_count": state["iteration_count"] + 1}

# --- 6. VISUALIZER (Le Générateur d'Image Mentale) ---
def visualizer_node(state):
    """
    Génère un prompt pour une image qui aide à comprendre.
    """
    draft = state["draft_response"]
    
    prompt = f"""
    Analyse cette explication médicale : "{draft}"
    
    Crée une description pour une image éducative (infographie ou illustration simple) qui aiderait à comprendre le concept clé.
    Pas de texte dans l'image, juste du visuel.
    
    Exemple : "Un dessin schématique de poumons agissant comme des éponges..."
    
    Réponds avec le prompt de l'image uniquement.
    """
    
    vis_prompt = llm.invoke([HumanMessage(content=prompt)]).content
    
    # Ici, nous appendons finalement la réponse au fil de discussion
    final_content = f"{draft}\n\n---\n*🎨 Idée visuelle suggérée par l'IA : {vis_prompt}*"
    
    return {
        "visual_prompt": vis_prompt,
        "messages": [SystemMessage(content=final_content)] # C'est ici qu'on finalise
    }

# --- AGENT SIMPLE (Pour le "Bonjour") ---
def general_chat_node(state):
    return {"messages": [llm.invoke(state["messages"])]}