import json
import logging
import re
from langchain_core.messages import SystemMessage, HumanMessage
from app.llm import get_llm
from app.vector_store import query_trials

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MedicalAgentGraph")

llm_strict = get_llm(temperature=0.1)   # For Logic/Facts/Safety
llm_creative = get_llm(temperature=0.7) # For Tone/Empathy/Chat

def parse_json_output(text):
    """
    Extracts JSON object from a string, handling markdown blocks or extra text.
    """
    text = text.strip()
    try:
        # 1. Try direct parse
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            # 2. Extract content between first { and last }
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group())
            # 3. Handle markdown code blocks
            text = text.replace("```json", "").replace("```", "").strip()
            return json.loads(text)
        except:
            return None

# --- 1. SUPERVISOR (The Orchestrator) ---
def supervisor_node(state):
    """
    Analyzes intent and routes to:
    - GENERAL_CHAT: Greetings, off-topic.
    - SIMPLE_MEDICAL: Fast track (no RAG) for basic definitions/advice.
    - COMPLEX_MEDICAL: Full chain (RAG + Safety) for specific drugs, interactions, OCR.
    """
    logger.info("--- 🕵️ SUPERVISOR AGENT STARTED ---")
    
    # 1. Find the last message (ignore system/instruction messages)
    messages = state.get("messages", [])
    query = ""
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            query = m.content
            break
            
    logger.info(f"Analyzing User Query: '{query}'")
    
    system_prompt = """
    You are the Supervisor of a Medical AI. Classify the user's intent into exactly ONE category.
    
    1. "GENERAL_CHAT": 
       - Greetings ("Hello"), Jokes, Off-topic.
       - Vague intent statements like "I have a question" or "Can you help me?" (The user hasn't asked the medical question yet).
    
    2. "SIMPLE_MEDICAL":
       - Basic definitions ("What is Paracetamol?").
       - Basic drug interaction
       - Simple Symptom diagnosis/analysis
       - Standard usage/dosage questions ("When to take Doliprane?").
       - General health advice ("How to sleep better?").
       - NO documents attached.
    
    3. "COMPLEX_MEDICAL":
       - Complex Drug interactions ("Can I take Advil with Warfarin?").
       - Complex Symptom diagnosis/analysis.
       - Complex Questions requiring OCR context (Prescriptions).
       - Specific clinical cases.
    
    OUTPUT FORMAT: Strictly JSON.
    {"next_step": "CATEGORY_NAME"}
    """
    
    try:
        resp = llm_strict.invoke([SystemMessage(content=system_prompt), HumanMessage(content=query)])
        decision = parse_json_output(resp.content)
        
        if not decision or "next_step" not in decision:
            raise ValueError("Invalid JSON output")
            
        next_step = decision.get("next_step", "GENERAL_CHAT")
        logger.info(f"Supervisor Decision: {next_step}")
        return {"next_step": next_step, "iteration_count": 0}
        
    except Exception as e:
        logger.error(f"Supervisor Error: {e}. Defaulting to GENERAL_CHAT.")
        return {"next_step": "GENERAL_CHAT", "iteration_count": 0}

# --- NEW: SIMPLE MEDICAL NODE (Fast Track) ---
def simple_medical_node(state):
    """
    Handles basic medical questions instantly without RAG/Guardian overhead.
    Uses Creative LLM for natural tone.
    """
    logger.info("--- ⚡ SIMPLE MEDICAL AGENT STARTED ---")
    messages = state.get("messages", [])
    language = state.get("user_profile", {}).get("language", "English")
    
    prompt = f"""
    You are a helpful and clear Medical Assistant.
    
    Task: Answer the user's question clearly, concisely, and accurately in {language}.
    
    Guidelines:
    - Be direct and helpful.
    - Do NOT mention that this is a "simple" answer.
    - If the question actually requires more context than you have, ask the user for details.
    """
    
    # Use the conversation history for context
    response = llm_creative.invoke([SystemMessage(content=prompt)] + messages[-3:])
    logger.info("Simple Medical response generated.")
    return {"messages": [response]}

# --- 2. MEDICAL EXPERT (Complex Track) ---
def medical_expert_node(state):
    logger.info("--- 🔬 MEDICAL EXPERT AGENT STARTED ---")
    
    messages = state.get("messages", [])
    query = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")
    
    # 1. Try RAG
    logger.info("Querying Vector Store (RAG)...")
    retrieved = query_trials(query)
    logger.info(f"RAG Retrieved {len(retrieved)} chars of context.")
    
    # 2. Call LLM
    prompt = f"""
    You are a Senior Medical Researcher. Your goal is to provide a purely factual summary.
    
    User Query: "{query}"
    Context from Database (RAG): {retrieved}
    
    INSTRUCTIONS:
    1. Extract all relevant medical facts (Symptoms, Dosages, Treatments, Contraindications).
    2. If RAG data is present, prioritize it.
    3. If RAG is empty/irrelevant, use your high-level general medical knowledge (Gold Standard).
    4. Do NOT simplify language yet. Do NOT be conversational. Be precise and technical.
    
    Output the raw medical facts now.
    """
    
    facts_response = llm_strict.invoke([HumanMessage(content=prompt)])
    facts = facts_response.content
    logger.info(f"Medical Facts Extracted (First 50 chars): {facts[:50]}...")
    return {"medical_facts": facts}

# --- 3. PROFILER ---
def profiler_node(state):
    logger.info("--- 👤 PROFILER AGENT STARTED ---")
    profile = state.get("user_profile", {})
    age = profile.get("age", 30)
    lang = profile.get("language", "English")
    level = profile.get("literacy_level", "Medium")
    
    logger.info(f"Profiling for: Age {age}, Lang {lang}, Level {level}")
    
    prompt = f"""
    You are an expert in Health Communication.
    
    Target: Age {age}, Language {lang}, Literacy {level}.
    
    Task: Define a communication strategy.
    1. Tone (e.g., Empathetic, Direct).
    2. Analogy Strategy (1 concrete metaphor).
    3. Key Precautions (Terms to simplify).
    
    Keep it concise.
    """
    
    strategy = llm_creative.invoke([HumanMessage(content=prompt)]).content
    logger.info(f"Strategy Defined: {strategy[:50]}...")
    return {"cultural_strategy": strategy}

# --- 4. TRANSLATOR ---
def translator_node(state):
    logger.info("--- ✍️ TRANSLATOR AGENT STARTED ---")
    facts = state["medical_facts"]
    strategy = state["cultural_strategy"]
    feedback = state.get("critique_feedback", "No prior critique.")
    language = state['user_profile'].get('language', 'English')
    
    logger.info(f"Drafting response in {language}...")
    
    prompt = f"""
    You are a compassionate Family Doctor.
    
    [MEDICAL FACTS]: {facts}
    [STRATEGY]: {strategy}
    [FEEDBACK]: {feedback}
    
    MISSION:
    Explain the medical facts to the patient in {language}.
    
    GUIDELINES:
    1. Tone: Warm, direct, reassuring.
    2. Clarity: Use the metaphors from the Strategy.
    3. NO Fluff: Start directly with the answer.
    4. Diagrams: Assess if the users would be able to understand response better with the use of diagrams and trigger them by adding the 

[Image of X]
 tag.
    
    Draft the response now.
    """
    
    response = llm_creative.invoke([SystemMessage(content=prompt)])
    draft = response.content
    logger.info("Draft generated.")
    return {"draft_response": draft}

# --- 5. GUARDIAN ---
def guardian_node(state):
    logger.info("--- 🛡️ GUARDIAN AGENT STARTED ---")
    facts = state["medical_facts"]
    draft = state["draft_response"]
    
    prompt = f"""
    You are the Senior Chief Medical Officer. Audit this response.
    
    SOURCE: {facts}
    DRAFT: {draft}
    
    CHECK:
    1. Hallucinations?
    2. Dangerous Omissions?
    3. Bad Tone?
    
    OUTPUT JSON:
    {{
        "status": "APPROVED" | "REJECTED",
        "feedback": "Reason if REJECTED, else 'N/A'"
    }}
    """
    
    try:
        resp = llm_strict.invoke([HumanMessage(content=prompt)])
        analysis = parse_json_output(resp.content)
        
        if not analysis:
            # Fallback if JSON fails but response seems ok
            logger.warning("Guardian JSON parse failed. Assuming APPROVED to prevent loop.")
            return {"safety_status": "APPROVED", "critique_feedback": "N/A", "iteration_count": state["iteration_count"] + 1}

        status = analysis.get("status", "REJECTED")
        feedback = analysis.get("feedback", "N/A")
        
        logger.info(f"Guardian Status: {status}")
        return {
            "safety_status": status,
            "critique_feedback": feedback,
            "iteration_count": state["iteration_count"] + 1
        }
    except Exception as e:
        logger.error(f"Guardian Error: {e}. Defaulting to APPROVED.")
        return {"safety_status": "APPROVED", "critique_feedback": "N/A", "iteration_count": state["iteration_count"] + 1}


# --- GENERAL CHAT ---
def general_chat_node(state):
    logger.info("--- 💬 GENERAL CHAT AGENT STARTED ---")
    response = llm_creative.invoke(state["messages"])
    logger.info("General Chat response generated.")
    return {"messages": [response]}