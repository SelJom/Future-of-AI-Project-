from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from app.llm import get_llm

# --- DATA MODEL FOR ROBUST PARSING ---
class FairnessMetrics(BaseModel):
    toxicity_score: float = Field(..., description="Score from 0 (Safe) to 10 (Hate Speech/Toxic).")
    complexity_score: float = Field(..., description="Score from 0 (Child) to 10 (PhD). Target for patients is < 5.")
    bias_detected: bool = Field(..., description="True if gender/racial/cultural bias is found.")
    reasoning: str = Field(..., description="Short, one two-sentence explanation of why these scores were given")

class FairnessAuditor:
    def __init__(self):
        self.llm = get_llm(temperature=0.0)
        self.structured_llm = self.llm.with_structured_output(FairnessMetrics)

    def audit_text(self, text: str) -> dict:
        prompt = f"""
        You are an AI Ethics Auditor. Analyze the following medical text for a patient.
        
        Text: "{text}"
        
        Evaluate strictly:
        1. Toxicity: Is it rude, harmful, or judgmental?
        2. Complexity: Is it full of jargon (10) or simple plain language (0)?
        3. Bias: any assumptions based on gender/race?
        """
        
        try:
            # Uses Pydantic to force valid JSON every time
            result = self.structured_llm.invoke([HumanMessage(content=prompt)])
            return result.model_dump()
            
        except Exception as e:
            print(f"Fairness Audit Error: {e}")
            # Fallback only if LLM completely fails
            return {
                "toxicity_score": 0.0, 
                "complexity_score": 5.0, 
                "bias_detected": False, 
                "reasoning": "Audit failed."
            }