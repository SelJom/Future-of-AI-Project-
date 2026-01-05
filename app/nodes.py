import json
import logging
import re
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from app.llm import get_llm
from app.vector_store import query_trials

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MedicalAgentGraph")

# Initialize separate LLMs
llm_strict = get_llm(temperature=0.1)   # For Logic/Facts/Safety
llm_creative = get_llm(temperature=0.7) # For Tone/Empathy/Chat

# --- HELPER: ROBUST JSON PARSER ---
def extract_and_parse_json(text):
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            json_str = match.group(1)
            json_str = re.sub(r",\s*\}", "}", json_str)
            return json.loads(json_str)
    except:
        pass
    try:
        if "```json" in text:
            pattern = r"```json(.*?)```"
            match = re.search(pattern, text, re.DOTALL)
            if match:
                return json.loads(match.group(1).strip())
    except:
        pass
    return None

# --- 1. SUPERVISOR (Strict) ---
def supervisor_node(state):
    logger.info("--- 🕵️ SUPERVISOR AGENT STARTED ---")
    
    messages = state.get("messages", [])
    query = ""
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            query = m.content
            break
            
    logger.info(f"Analyzing User Query: '{query}'")
    
    system_prompt = """
    You are a JSON Classification Engine.
    TASK: Classify the input text into exactly ONE category.
    
    1. "GENERAL_CHAT":
       - Greetings ("Hello"), Small talk.
       - "I have a question" (without the question itself).
    
    2. "SIMPLE_MEDICAL":
       - Basic Definitions ("What is X?").
       - General advice ("Tips for flu").
    
    3. "COMPLEX_MEDICAL":
       - Interactions ("Can I mix X and Y?").
       - Specific symptoms or conditions.
       - Questions about a specific document context.
    
    RESPONSE FORMAT: {"next_step": "CATEGORY_NAME"}
    """
    
    try:
        resp = llm_strict.invoke([SystemMessage(content=system_prompt), HumanMessage(content=query)])
        decision = extract_and_parse_json(resp.content)
        
        if not decision or "next_step" not in decision:
            q_lower = query.lower()
            if any(x in q_lower for x in ['medicament', 'drug', 'symptom', 'pain', 'mix', 'mélanger']):
                return {"next_step": "COMPLEX_MEDICAL", "iteration_count": 0}
            return {"next_step": "GENERAL_CHAT", "iteration_count": 0}
            
        next_step = decision.get("next_step", "GENERAL_CHAT")
        logger.info(f"Supervisor Decision: {next_step}")
        return {"next_step": next_step, "iteration_count": 0}
        
    except Exception as e:
        logger.error(f"Supervisor Error: {e}")
        return {"next_step": "GENERAL_CHAT", "iteration_count": 0}

# --- NEW: SIMPLE MEDICAL NODE ---
def simple_medical_node(state):
    logger.info("--- ⚡ SIMPLE MEDICAL AGENT STARTED ---")
    messages = state.get("messages", [])
    language = state.get("user_profile", {}).get("language", "English")
    
    prompt = f"""
    You are a helpful Medical Assistant.
    Answer the user's question clearly, concisely, and accurately in {language}.
    
    STRICT RULES:
    1. **NO INTRODUCTIONS**: Do NOT say "Hello", "I am an AI", or "Here is the answer".
    2. **START IMMEDIATELY**: Begin directly with the medical explanation.
    """
    response = llm_creative.invoke([SystemMessage(content=prompt)] + messages[-3:])
    return {"messages": [response]}

# --- 2. MEDICAL EXPERT (Strict + List Handling Fix) ---
def medical_expert_node(state):
    logger.info("--- 🔬 MEDICAL EXPERT AGENT STARTED ---")
    
    messages = state.get("messages", [])
    query = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")
    
    # 1. Try RAG
    logger.info("Querying Vector Store (RAG)...")
    try:
        retrieved_data = query_trials(query)
        
        # --- FIX FOR "LIST HAS NO ATTRIBUTE STRIP" ---
        if isinstance(retrieved_data, list):
            # If it's a list of strings, join them.
            retrieved = "\n\n".join([str(item) for item in retrieved_data])
        elif isinstance(retrieved_data, str):
            retrieved = retrieved_data
        else:
            # Fallback for other types
            retrieved = str(retrieved_data)
            
    except Exception as e:
        logger.error(f"RAG Retrieval Failed: {e}")
        retrieved = ""
    
    # 2. Check for Valid Context
    if not retrieved or len(retrieved.strip()) < 10 or "Aucune étude" in retrieved:
        rag_status = "NO_CONTEXT_FOUND"
        rag_content = "No specific documents available."
        logger.info("RAG is empty. Forcing General Knowledge.")
    else:
        rag_status = "CONTEXT_AVAILABLE"
        rag_content = retrieved
        logger.info(f"RAG Retrieved Context.")
    
    # 3. Call LLM
    prompt = f"""
    You are a Senior Medical Researcher. 
    TASK: Provide a factual medical summary for the query.
    
    [USER QUERY]: "{query}"
    [RAG STATUS]: {rag_status}
    [RAG CONTENT]: {rag_content}
    
    CRITICAL INSTRUCTIONS:
    1. If RAG content is available, use it.
    2. **IF RAG IS EMPTY, YOU MUST USE YOUR OWN GENERAL MEDICAL KNOWLEDGE.**
    3. Do NOT say "I cannot answer" or "I need documents". Answer the question directly.
    4. Provide standard medical facts (Interactions, Contraindications, Usage).
    
    Output the raw facts now.
    """
    
    facts_response = llm_strict.invoke([HumanMessage(content=prompt)])
    facts = facts_response.content
    
    # 4. Emergency Fallback
    if "cannot" in facts.lower() and ("context" in facts.lower() or "document" in facts.lower()):
        logger.warning("Expert refused to answer. Retrying with Creative Fallback.")
        retry_prompt = f"Answer this medical question using general knowledge: {query}"
        facts_response = llm_creative.invoke([HumanMessage(content=retry_prompt)])
        facts = facts_response.content

    logger.info(f"Medical Facts Extracted: {facts[:50]}...")
    return {"medical_facts": facts}

# --- 3. PROFILER (Creative) ---
def profiler_node(state):
    logger.info("--- 👤 PROFILER AGENT STARTED ---")
    profile = state.get("user_profile", {})
    prompt = f"Define a communication strategy for: Age {profile.get('age')}, Lang {profile.get('language')}."
    strategy = llm_creative.invoke([HumanMessage(content=prompt)]).content
    return {"cultural_strategy": strategy}

# --- 4. TRANSLATOR (Creative + Diagrams + Clean Output) ---
def translator_node(state):
    logger.info("--- ✍️ TRANSLATOR AGENT STARTED ---")
    facts = state["medical_facts"]
    strategy = state["cultural_strategy"]
    feedback = state.get("critique_feedback", "N/A")
    language = state['user_profile'].get('language', 'English')
    
    prompt = f"""
    You are a compassionate Family Doctor.
    FACTS: {facts}
    STRATEGY: {strategy}
    SAFETY FEEDBACK: {feedback}
    
    MISSION: Explain to the patient in {language}.
    
    **STRICT FORMATTING RULES:**
    1. **NO INTRODUCTIONS**: Do NOT say "Hello", "I am Doctor X", "Here is a response", or "As an AI".
    2. **START IMMEDIATELY**: Start the first sentence directly with the medical explanation.
    3. Tone: Warm, clear, direct. Use metaphors if helpful.
    
    Draft response:
    """
    response = llm_creative.invoke([SystemMessage(content=prompt)])
    return {"draft_response": response.content}

# --- 5. GUARDIAN (Strict) ---
def guardian_node(state):
    logger.info("--- 🛡️ GUARDIAN AGENT STARTED ---")
    facts = state["medical_facts"]
    draft = state["draft_response"]
    
    prompt = f"""
    Audit this response.
    SOURCE: {facts}
    DRAFT: {draft}
    
    OUTPUT JSON: {{ "status": "APPROVED" | "REJECTED", "feedback": "..." }}
    """
    
    try:
        resp = llm_strict.invoke([HumanMessage(content=prompt)])
        analysis = extract_and_parse_json(resp.content)
        if not analysis: return {"safety_status": "APPROVED", "iteration_count": 99}
        
        status = analysis.get("status", "REJECTED")
        logger.info(f"Guardian Status: {status}")
        return {"safety_status": status, "critique_feedback": analysis.get("feedback", "N/A"), "iteration_count": state["iteration_count"] + 1}
    except:
        return {"safety_status": "APPROVED", "iteration_count": 99}

# --- 6. PUBLISHER (Required for Complex Chain) ---
def publisher_node(state):
    """
    Takes the final draft and appends it to the conversation history.
    """
    logger.info("--- 📤 PUBLISHING FINAL RESPONSE ---")
    final_text = state["draft_response"]
    return {"messages": [AIMessage(content=final_text)]}

# --- 7. VISUALIZER (Unused) ---
def visualizer_node(state):
    return {}

# --- 8. GENERAL CHAT (Creative) ---
def general_chat_node(state):
    logger.info("--- 💬 GENERAL CHAT AGENT STARTED ---")
    response = llm_creative.invoke(state["messages"])
    return {"messages": [response]}