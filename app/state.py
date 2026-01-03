from typing import TypedDict, List, Optional, Dict, Annotated
import operator
from langchain_core.messages import BaseMessage

class MedicalAgentState(TypedDict):
    """
    Shared state for the multi-agent system.
    Annotated list allows agents to append messages history.
    """
    messages: Annotated[List[BaseMessage], operator.add]
    
    # Input
    user_query: str
    
    # Literacy Track
    simplified_text: Optional[str]
    literacy_critique: Optional[str]
    
    # Matching Track
    retrieved_trials: List[str]
    final_recommendation: Optional[str]
    
    # Fairness & Audit (Grade Part B)
    fairness_metrics: Dict[str, float] # e.g. {'toxicity': 0.1, 'complexity': 4.5}
    fairness_flag: bool # True if intervention needed
    
    # Routing
    next_step: str