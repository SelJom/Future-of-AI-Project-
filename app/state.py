from typing import TypedDict, List, Annotated, Dict
import operator
from langchain_core.messages import BaseMessage

class MedicalAgentState(TypedDict):
    """
    État partagé avancé pour le système multi-agents.
    Permet la réflexion et la correction.
    """
    # Historique de la conversation
    messages: Annotated[List[BaseMessage], operator.add]
    
    # --- Contextes persistants ---
    user_profile: Dict[str, str]  # {age, culture, language, literacy_level}
    
    # --- Espace de travail des Agents ---
    medical_facts: str        # Les faits bruts extraits par l'Expert ou l'OCR
    cultural_strategy: str    # Les consignes de ton données par le Profiler
    draft_response: str       # Le brouillon rédigé par le Traducteur
    critique_feedback: str    # Les remarques du Guardian
    
    # --- Visuel ---
    visual_prompt: str        # Le prompt généré pour créer une image explicative
    
    # --- Contrôle du flux ---
    iteration_count: int      # Pour éviter les boucles infinies de correction
    next_step: str            # Direction donnée par le Superviseur
    safety_status: str        # "APPROVED" ou "REJECTED"