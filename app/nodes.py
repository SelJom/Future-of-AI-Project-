from langchain_core.messages import SystemMessage, HumanMessage
from app.llm import get_llm
from app.vector_store import query_trials
from app.fairness import FairnessAuditor

llm = get_llm()
auditor = FairnessAuditor()

# --- 1. Router Agent ---
def route_query(state):
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

# --- 2. Literacy Agents ---
def simplifier_agent(state):
    original = state["user_query"]
    msg = [
        SystemMessage(content="You are a Health Literacy Expert. Rewrite the text for a 6th-grade reading level. Be empathetic."),
        HumanMessage(content=original)
    ]
    res = llm.invoke(msg)
    return {"simplified_text": res.content}

def critic_agent(state):
    """
    Implements Grading B02 (Metrics) and B03 (Mitigation).
    Calculates fairness scores and critiques medical accuracy.
    """
    simplified = state["simplified_text"]
    
    # A. Calculate Fairness Metrics
    metrics = auditor.audit_text(simplified)
    
    # B. Medical Critique
    critique_prompt = f"Check if this simplification lost medical meaning. Text: {simplified}. Reply 'OK' or explain the error."
    critique = llm.invoke([HumanMessage(content=critique_prompt)]).content
    
    return {
        "fairness_metrics": metrics,
        "literacy_critique": critique,
        "fairness_flag": metrics['toxicity_score'] > 5 # Flag if toxic
    }

# --- 3. Matching Agents ---
def retrieval_agent(state):
    docs = query_trials(state["user_query"])
    return {"retrieved_trials": docs}

def matcher_agent(state):
    trials = "\n".join(state["retrieved_trials"])
    query = state["user_query"]
    msg = [
        SystemMessage(content="You are a Clinical Research Coordinator. Analyze the patient profile against the trials."),
        HumanMessage(content=f"Patient: {query}\n\nAvailable Trials:\n{trials}")
    ]
    res = llm.invoke(msg)
    return {"final_recommendation": res.content}