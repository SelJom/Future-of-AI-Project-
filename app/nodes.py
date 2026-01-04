import json
from langchain_core.messages import SystemMessage, HumanMessage
from app.llm import get_llm
from app.vector_store import query_trials
from app.fairness import FairnessAuditor

llm = get_llm()
auditor = FairnessAuditor()

# --- 1. SUPERVISOR (ORCHESTRATOR) ---
def supervisor_node(state):
    """
    Decides which agent should handle the query.
    """
    # Get the last user message
    messages = state.get("messages", [])
    if messages:
        query = messages[-1].content
    else:
        query = "Hello"

    prompt = f"""
    You are the Medical AI Supervisor. Analyze the user query.
    
    Query: "{query}"
    
    Decide the next step. Return JSON ONLY:
    {{
        "reasoning": "brief explanation",
        "next_step": "AGENT_NAME"
    }}
    
    Choices for AGENT_NAME:
    - "MEDICAL_RESEARCHER": For specific medical facts, drug interactions, clinical trials, or serious medical advice.
    - "GENERAL_CHAT": For greetings, simple explanations, or non-medical follow-ups.
    """
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        # Clean potential markdown wrapping
        content = response.content.replace("```json", "").replace("```", "").strip()
        decision = json.loads(content)
        return {"next_step": decision.get("next_step", "GENERAL_CHAT")}
    except Exception as e:
        print(f"Supervisor Error: {e}")
        return {"next_step": "GENERAL_CHAT"}

# --- 2. AGENTS ---

def general_chat_agent(state):
    lang = state.get("language", "Français")
    complexity = state.get("complexity_prompt", "Standard")
    messages = state["messages"]
    
    sys_msg = f"""You are a helpful assistant.
    IMPORTANT: You MUST answer in {lang}.
    Complexity Level: {complexity}
    """
    
    # We pass the full history to keep context
    response = llm.invoke([SystemMessage(content=sys_msg)] + messages)
    return {"messages": [response]} # Appends to history

def medical_researcher_agent(state):
    messages = state["messages"]
    query = messages[-1].content
    lang = state.get("language", "Français")
    complexity = state.get("complexity_prompt", "Standard")
    
    # Real RAG Call
    retrieved_docs = query_trials(query)
    docs_str = "\n".join(retrieved_docs) if isinstance(retrieved_docs, list) else str(retrieved_docs)
    
    sys_msg = f"""You are a Medical Expert. 
    Base your answer on the context provided below.
    
    CONTEXT:
    {docs_str}
    
    INSTRUCTIONS:
    1. Answer in {lang}.
    2. Complexity Level: {complexity}.
    3. Be precise and cite the context if relevant.
    """
    
    response = llm.invoke([SystemMessage(content=sys_msg)] + messages)
    return {"messages": [response]}

# --- 3. CRITIC ---
def fairness_critic_node(state):
    messages = state["messages"]
    last_msg = messages[-1]
    
    # Calculate metrics
    metrics = auditor.audit_text(last_msg.content)
    
    return {
        "fairness_metrics": metrics
    }