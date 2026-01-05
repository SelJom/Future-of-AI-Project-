from langgraph.graph import StateGraph, END
from app.state import MedicalAgentState
from app.nodes import (
    supervisor_node,
    simple_medical_node,
    medical_expert_node,
    profiler_node,
    translator_node,
    guardian_node,
    general_chat_node,
    publisher_node 
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
    workflow.add_node("simple_medical", simple_medical_node)
    
    # Complex Chain
    workflow.add_node("medical_expert", medical_expert_node)
    workflow.add_node("profiler", profiler_node)
    workflow.add_node("translator", translator_node)
    workflow.add_node("guardian", guardian_node)
    workflow.add_node("publisher", publisher_node)

    workflow.set_entry_point("supervisor")

    # 1. Supervisor Routing
    workflow.add_conditional_edges(
        "supervisor",
        lambda x: x["next_step"],
        {
            "GENERAL_CHAT": "general_chat",
            "SIMPLE_MEDICAL": "simple_medical",
            "COMPLEX_MEDICAL": "medical_expert"
        }
    )

    # 2. Simple & General -> End
    workflow.add_edge("simple_medical", END)
    workflow.add_edge("general_chat", END)

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
            "finalize": "publisher" 
        }
    )
    
    # 5. Publisher -> End
    workflow.add_edge("publisher", END)

    return workflow.compile()

graph = build_graph()