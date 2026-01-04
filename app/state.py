# app/state.py
from typing import TypedDict, List, Optional, Dict, Annotated
import operator
from langchain_core.messages import BaseMessage

class MedicalAgentState(TypedDict):
    """
    Shared state for the multi-agent system.
    """
    # Chat History
    messages: Annotated[List[BaseMessage], operator.add]
    
    # Orchestration
    next_step: str  # 'general_chat', 'medical_rag', 'fairness_review', etc.
    
    # User Context (Persistent)
    session_id: str
    language: str
    complexity_prompt: str
    
    # Content
    user_query: str
    retrieved_docs: Optional[str]
    draft_response: Optional[str]
    
    # Metrics
    fairness_metrics: Dict[str, float]