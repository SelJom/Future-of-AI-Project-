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
    - MATCHING (clinical trials, studies)
    - LITERACY (definitions, side effects, explanations, chat)
    """
    response = llm.invoke([HumanMessage(content=prompt)])
    decision = response.content.strip().upper()
    if "MATCHING" in decision:
        return {"next_step": "MATCHING"}
    return {"next_step": "LITERACY"}

# --- 2. Literacy Agents ---
def simplifier_agent(state):
    original = state["user_query"]
    
    # Get Profile Data
    age = state.get("user_age", 30)
    level = state.get("literacy_level", "Adulte")
    
    # Get Document Context (if any)
    doc_context = state.get("active_document_context", "")
    
    # Dynamic System Prompt
    system_prompt = f"""
    You are a compassionate Health Literacy Expert.
    
    Target Audience:
    - Age: {age} years old
    - Comprehension Level: {level}
    
    Context (Scanned Document):
    {doc_context}
    
    Task: Answer the user's question clearly. 
    - If explaining medical terms, use analogies suitable for a {age} year old.
    - Be empathetic and reassuring.
    - If the context contains a prescription, refer to it specifically.
    """
    
    msg = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=original)
    ]
    res = llm.invoke(msg)
    return {"simplified_text": res.content}

def critic_agent(state):
    simplified = state["simplified_text"]
    metrics = auditor.audit_text(simplified)
    
    # Simple check
    critique_prompt = f"Check if this text is medically accurate but simple: '{simplified}'. Reply 'OK' or briefly explain errors."
    critique = llm.invoke([HumanMessage(content=critique_prompt)]).content
    
    return {
        "fairness_metrics": metrics,
        "literacy_critique": critique,
        "fairness_flag": metrics['toxicity_score'] > 5
    }

# --- 3. Matching Agents ---
def retrieval_agent(state):
    docs = query_trials(state["user_query"])
    return {"retrieved_trials": docs}

def matcher_agent(state):
    trials = "\n".join(state["retrieved_trials"])
    query = state["user_query"]
    msg = [
        SystemMessage(content="Clinical Research Coordinator. Match patient to trials."),
        HumanMessage(content=f"Patient: {query}\n\nTrials:\n{trials}")
    ]
    res = llm.invoke(msg)
    return {"final_recommendation": res.content}