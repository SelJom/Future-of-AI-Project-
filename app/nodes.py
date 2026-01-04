# app/nodes.py
from langchain_core.messages import SystemMessage, HumanMessage
from app.llm import get_llm
from app.vector_store import query_trials
from app.fairness import FairnessAuditor

llm = get_llm()
auditor = FairnessAuditor()

# --- 1. Router Agent ---
def route_query(state):
    # (Code inchangé)
    query = state["user_query"]
    prompt = f"""
    Classify this intent: "{query}"
    Reply EXACTLY one word:
    - MATCHING (if looking for clinical trials, studies, or treatments)
    - LITERACY (if asking for definition, simplification, or explanation)
    """
    response = llm.invoke([HumanMessage(content=prompt)])
    decision = response.content.strip().upper()
    if "MATCHING" in decision:
        return {"next_step": "MATCHING"}
    return {"next_step": "LITERACY"}

# --- 2. Literacy Agents (MODIFIÉ POUR PERSONNALISATION) ---
def simplifier_agent(state):
    original = state["user_query"]
    profile = state.get("user_profile", {})
    
    # Extraction des infos profil avec valeurs par défaut
    age = profile.get("age", "adulte")
    lang = profile.get("langue", "français")
    etudes = profile.get("etudes", "niveau standard")
    
    # Prompt dynamique
    system_prompt = f"""
    You are a Health Literacy Expert. 
    Your goal is to explain the medical text to a user with these characteristics:
    - Age: {age} years old
    - Native Language: {lang}
    - Education Level: {etudes}
    
    If the user speaks a language other than English, TRANSLATE your explanation to {lang}.
    Be empathetic, clear, and use analogies suited to their education level.
    """
    
    msg = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=original)
    ]
    res = llm.invoke(msg)
    return {"simplified_text": res.content}

def critic_agent(state):
    # (Code inchangé pour la logique, mais on auditera le texte adapté)
    simplified = state["simplified_text"]
    metrics = auditor.audit_text(simplified)
    
    critique_prompt = f"Check if this simplification lost medical meaning. Text: {simplified}. Reply 'OK' or explain the error."
    critique = llm.invoke([HumanMessage(content=critique_prompt)]).content
    
    return {
        "fairness_metrics": metrics,
        "literacy_critique": critique,
        "fairness_flag": metrics['toxicity_score'] > 5
    }

# --- 3. Matching Agents (MODIFIÉ) ---
def retrieval_agent(state):
    # (Code inchangé)
    docs = query_trials(state["user_query"])
    return {"retrieved_trials": docs}

def matcher_agent(state):
    trials = "\n".join(state["retrieved_trials"])
    query = state["user_query"]
    profile = state.get("user_profile", {})
    lang = profile.get("langue", "français")

    msg = [
        SystemMessage(content=f"You are a Clinical Research Coordinator. Analyze the patient profile against the trials. Answer in {lang}."),
        HumanMessage(content=f"Patient: {query}\n\nAvailable Trials:\n{trials}")
    ]
    res = llm.invoke(msg)
    return {"final_recommendation": res.content}