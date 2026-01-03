from langgraph.graph import StateGraph, END
from app.state import MedicalAgentState
from app.nodes import (
    route_query, simplifier_agent, critic_agent, 
    retrieval_agent, matcher_agent
)

def build_graph():
    workflow = StateGraph(MedicalAgentState)

    # Add Nodes
    workflow.add_node("router", route_query)
    workflow.add_node("simplifier", simplifier_agent)
    workflow.add_node("critic", critic_agent)
    workflow.add_node("retriever", retrieval_agent)
    workflow.add_node("matcher", matcher_agent)

    # Set Entry
    workflow.set_entry_point("router")

    # Conditional Logic
    workflow.add_conditional_edges(
        "router",
        lambda x: "retriever" if x["next_step"] == "MATCHING" else "simplifier",
        {
            "retriever": "retriever",
            "simplifier": "simplifier"
        }
    )

    # Edges
    workflow.add_edge("simplifier", "critic")
    workflow.add_edge("critic", END)
    
    workflow.add_edge("retriever", "matcher")
    workflow.add_edge("matcher", END)

    return workflow.compile()

graph = build_graph()