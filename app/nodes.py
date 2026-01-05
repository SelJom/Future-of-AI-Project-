import json
from langchain_core.messages import SystemMessage, HumanMessage
from app.llm import get_llm
from app.vector_store import query_trials

llm = get_llm()

# --- 1. SUPERVISOR ---
def supervisor_node(state):
    """
    Analyzes intent. Routes to Medical Chain or General Chat.
    """
    messages = state.get("messages", [])
    query = messages[-1].content if messages else ""
    
    system_prompt = """
    You are the Supervisor of a Medical AI. Analyze the user's request.
    
    IF the request concerns:
    - A disease, symptom, or medication.
    - A prescription explanation (OCR context).
    - A complex health question.
    -> Respond JSON: {"next_step": "MEDICAL_CHAIN"}
    
    OTHERWISE (Greetings, jokes, off-topic):
    -> Respond JSON: {"next_step": "GENERAL_CHAT"}
    """
    
    try:
        resp = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=query)])
        decision = json.loads(resp.content.replace("```json", "").replace("```", "").strip())
        return {"next_step": decision.get("next_step", "GENERAL_CHAT"), "iteration_count": 0}
    except:
        return {"next_step": "GENERAL_CHAT", "iteration_count": 0}

# --- 2. MEDICAL EXPERT (IMPROVED: General Knowledge Fallback) ---
def medical_expert_node(state):
    """
    Retrieves scientific truth. If RAG is empty, uses internal high-level knowledge.
    """
    query = state["messages"][-1].content
    
    # 1. Try RAG
    retrieved = query_trials(query)
    
    # 2. Call LLM to synthesize facts (RAG + General Knowledge)
    prompt = f"""
    You are an expert medical knowledge base.
    
    User Query: "{query}"
    Found Documents (RAG): {retrieved}
    
    YOUR MISSION:
    List the relevant medical facts to answer (Symptoms, Standard Treatments, Precautions).
    - IF the RAG contains the info, prioritize it.
    - IF the RAG is empty or insufficient, USE YOUR GENERAL HIGH-LEVEL MEDICAL KNOWLEDGE (Gold Standard).
    
    Do not draft the final response yet, just provide the raw, accurate facts.
    """
    
    facts_response = llm.invoke([HumanMessage(content=prompt)])
    return {"medical_facts": facts_response.content}

# --- 3. PROFILER ---
def profiler_node(state):
    """
    Defines communication strategy based on demographics.
    """
    profile = state.get("user_profile", {})
    age = profile.get("age", 30)
    lang = profile.get("language", "English")
    level = profile.get("literacy_level", "Medium")
    
    prompt = f"""
    You are an expert in Health Literacy and Intercultural Communication.
    
    Patient: {age} years old. Language: {lang}. Literacy Level: {level}.
    
    Define a drafting strategy in 3 points:
    1. Tone (Empathetic, Direct, Formal?)
    2. Cultural Metaphors (e.g., mechanics for an engineer, nature for rural context - INVENT based on profile).
    3. Taboos to avoid or language precautions.
    
    Respond ONLY with the strategy text.
    """
    
    strategy = llm.invoke([HumanMessage(content=prompt)]).content
    return {"cultural_strategy": strategy}

# --- 4. TRANSLATOR (IMPROVED: Natural Tone) ---
def translator_node(state):
    """
    Drafts the final explanation.
    """
    facts = state["medical_facts"]
    strategy = state["cultural_strategy"]
    feedback = state.get("critique_feedback", "No critique so far.")
    
    # We force a direct conversational tone
    prompt = f"""
    You are an empathetic and clear General Practitioner (GP). You are in a direct consultation.
    
    MEDICAL FACTS TO CONVEY:
    {facts}
    
    COMMUNICATION STRATEGY (Tone/Adaptation):
    {strategy}
    
    PREVIOUS CORRECTIONS (If applicable):
    {feedback}
    
    DRAFTING INSTRUCTIONS:
    1. NEVER start with "I understand", "Here is the answer", or "Based on the facts".
    2. Answer directly like a human (e.g., "For a sore throat, the most effective thing is...").
    3. Use the strategy defined above.
    4. Be concise but complete.
    
    Draft the response now in {state['user_profile'].get('language')}.
    """
    
    # We only send the system prompt to prevent history from polluting the style
    response = llm.invoke([SystemMessage(content=prompt)])
    return {"draft_response": response.content}

# --- 5. GUARDIAN ---
def guardian_node(state):
    """
    Safety check for hallucinations or dangerous advice.
    """
    facts = state["medical_facts"]
    draft = state["draft_response"]
    
    prompt = f"""
    You are the Safety Guardian Doctor.
    
    1. ORIGINAL MEDICAL FACTS: {facts}
    2. PROPOSED SIMPLIFIED DRAFT: {draft}
    
    TASK: Detect serious errors.
    - Hallucination (Does the draft say something not present in general medical facts?)
    - Dangerous Omission (Did a serious side effect disappear?)
    - Excessive Infantilization or inappropriate tone?
    
    Respond JSON:
    {{
        "status": "APPROVED" or "REJECTED",
        "feedback": "If REJECTED, explain precisely what to fix. If APPROVED, put 'N/A'."
    }}
    """
    
    try:
        resp = llm.invoke([HumanMessage(content=prompt)])
        analysis = json.loads(resp.content.replace("```json", "").replace("```", "").strip())
        return {
            "safety_status": analysis.get("status", "REJECTED"),
            "critique_feedback": analysis.get("feedback", "Parsing error"),
            "iteration_count": state["iteration_count"] + 1
        }
    except:
        return {"safety_status": "REJECTED", "critique_feedback": "Invalid JSON format.", "iteration_count": state["iteration_count"] + 1}

# --- 6. VISUALIZER (EMPTY / UNUSED) ---
def visualizer_node(state):
    return {}

# --- GENERAL CHAT ---
def general_chat_node(state):
    return {"messages": [llm.invoke(state["messages"])]}