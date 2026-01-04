# app/state.py
from typing import TypedDict, List, Optional, Dict, Annotated
import operator
from langchain_core.messages import BaseMessage

class MedicalAgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    user_query: str
    
    # NOUVEAU : Profil utilisateur pour la personnalisation
    user_profile: Dict[str, str] 

    simplified_text: Optional[str]
    literacy_critique: Optional[str]
    retrieved_trials: List[str]
    final_recommendation: Optional[str]
    fairness_metrics: Dict[str, float]
    fairness_flag: bool
    next_step: str