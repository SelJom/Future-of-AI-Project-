from langgraph.graph import StateGraph, END
from app.state import MedicalAgentState
from app.nodes import (
    supervisor_node, 
    general_chat_agent, 
    medical_researcher_agent, 
    fairness_critic_node
)

def build_graph():
    workflow = StateGraph(MedicalAgentState)

    # Add Nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("general_chat", general_chat_agent)
    workflow.add_node("medical_researcher", medical_researcher_agent)
    workflow.add_node("critic", fairness_critic_node)

    # Entry Point
    workflow.set_entry_point("supervisor")

    # Conditional Logic (The Orchestration)
    workflow.add_conditional_edges(
        "supervisor",
        lambda x: x["next_step"].lower(),
        {
            "general_chat": "general_chat",
            "medical_researcher": "medical_researcher"
        }
    )

    # All agents go to critic for final review
    workflow.add_edge("general_chat", "critic")
    workflow.add_edge("medical_researcher", "critic")
    workflow.add_edge("critic", END)

    return workflow.compile()

graph = build_graph()