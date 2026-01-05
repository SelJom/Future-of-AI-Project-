from langgraph.graph import StateGraph, END
from app.state import MedicalAgentState
from app.nodes import (
    supervisor_node,
    simple_medical_node,  
    medical_expert_node,
    profiler_node,
    translator_node,
    guardian_node,
    general_chat_node
)

def should_retry(state):
    status = state.get("safety_status", "APPROVED")
    count = state.get("iteration_count", 0)
    
    if status == "REJECTED" and count < 3:
        return "retry"
    return "finalize"

def build_graph():
    workflow = StateGraph(MedicalAgentState)

    # --- ADD NODES ---
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("general_chat", general_chat_node)
    workflow.add_node("simple_medical", simple_medical_node) # NEW
    
    # Complex Chain
    workflow.add_node("medical_expert", medical_expert_node)
    workflow.add_node("profiler", profiler_node)
    workflow.add_node("translator", translator_node)
    workflow.add_node("guardian", guardian_node)

    # --- DEFINE EDGES ---
    workflow.set_entry_point("supervisor")

    # 1. Supervisor Routing (Orchestrator)
    workflow.add_conditional_edges(
        "supervisor",
        lambda x: x["next_step"],
        {
            "GENERAL_CHAT": "general_chat",
            "SIMPLE_MEDICAL": "simple_medical", # Fast Track
            "COMPLEX_MEDICAL": "medical_expert" # Slow/Safe Track
        }
    )

    # 2. Simple Medical -> End
    workflow.add_edge("simple_medical", END)

    # 3. Complex Chain Flow
    workflow.add_edge("medical_expert", "profiler")
    workflow.add_edge("profiler", "translator")
    workflow.add_edge("translator", "guardian")

    # 4. Guardian Loop
    workflow.add_conditional_edges(
        "guardian",
        should_retry,
        {
            "retry": "translator",
            "finalize": END
        }
    )

    # 5. General Chat -> End
    workflow.add_edge("general_chat", END)

    return workflow.compile()

graph = build_graph()