from langgraph.graph import StateGraph, END
from app.state import MedicalAgentState
from app.nodes import (
    supervisor_node,
    medical_expert_node,
    profiler_node,
    translator_node,
    guardian_node,
    general_chat_node
    # visualizer_node # REMOVED
)

def should_retry(state):
    status = state.get("safety_status", "APPROVED")
    count = state.get("iteration_count", 0)
    
    if status == "REJECTED" and count < 3:
        return "retry"
    return "finalize"

def build_graph():
    workflow = StateGraph(MedicalAgentState)

    # --- Add Nodes ---
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("general_chat", general_chat_node)
    
    # Medical Chain
    workflow.add_node("medical_expert", medical_expert_node)
    workflow.add_node("profiler", profiler_node)
    workflow.add_node("translator", translator_node)
    workflow.add_node("guardian", guardian_node)
    # workflow.add_node("visualizer", visualizer_node) # REMOVED

    # --- Define Edges ---
    workflow.set_entry_point("supervisor")

    # 1. Supervisor Decision
    workflow.add_conditional_edges(
        "supervisor",
        lambda x: x["next_step"],
        {
            "GENERAL_CHAT": "general_chat",
            "MEDICAL_CHAIN": "medical_expert"
        }
    )

    # 2. Linear Chain
    workflow.add_edge("medical_expert", "profiler")
    workflow.add_edge("profiler", "translator")
    workflow.add_edge("translator", "guardian")

    # 3. Conditional Loop (Guardian -> Translator OR END)
    workflow.add_conditional_edges(
        "guardian",
        should_retry,
        {
            "retry": "translator",   # Return to drafting with feedback
            "finalize": END          # MODIFIED: Goes straight to END (no image generation)
        }
    )

    # 4. End
    workflow.add_edge("general_chat", END)

    return workflow.compile()

graph = build_graph()