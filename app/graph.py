from langgraph.graph import StateGraph, END
from app.state import MedicalAgentState
from app.nodes import (
    supervisor_node,
    medical_expert_node,
    profiler_node,
    translator_node,
    guardian_node,
    visualizer_node,
    general_chat_node
)

def should_retry(state):
    """
    Logique de boucle :
    - Si rejeté ET pas trop d'essais -> Retourne au Translator
    - Sinon -> Passe à la suite (Visualizer)
    """
    status = state.get("safety_status", "APPROVED")
    count = state.get("iteration_count", 0)
    
    if status == "REJECTED" and count < 3:
        return "retry"
    return "finalize"

def build_graph():
    workflow = StateGraph(MedicalAgentState)

    # --- Ajout des Noeuds ---
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("general_chat", general_chat_node)
    
    # La Chaîne Médicale
    workflow.add_node("medical_expert", medical_expert_node)
    workflow.add_node("profiler", profiler_node)
    workflow.add_node("translator", translator_node)
    workflow.add_node("guardian", guardian_node)
    workflow.add_node("visualizer", visualizer_node)

    # --- Définition des Entrées/Sorties ---
    workflow.set_entry_point("supervisor")

    # 1. Décision Superviseur
    workflow.add_conditional_edges(
        "supervisor",
        lambda x: x["next_step"],
        {
            "GENERAL_CHAT": "general_chat",
            "MEDICAL_CHAIN": "medical_expert" # On commence par les faits
        }
    )

    # 2. Chaîne Linéaire (Facts -> Profile -> Translate -> Critique)
    workflow.add_edge("medical_expert", "profiler")
    workflow.add_edge("profiler", "translator")
    workflow.add_edge("translator", "guardian")

    # 3. Boucle Conditionnelle (Guardian -> Translator OU Visualizer)
    workflow.add_conditional_edges(
        "guardian",
        should_retry,
        {
            "retry": "translator",   # Retour à la rédaction avec feedback
            "finalize": "visualizer" # Validé, on génère l'image
        }
    )

    # 4. Fin
    workflow.add_edge("visualizer", END)
    workflow.add_edge("general_chat", END)

    return workflow.compile()

graph = build_graph()