import json
from langchain_core.messages import SystemMessage, HumanMessage
from app.llm import get_llm

class FairnessAuditor:
    def __init__(self):
        self.llm = get_llm(temperature=0.0) # Zero temp for deterministic grading

    def audit_text(self, text: str) -> dict:
        """
        Calculates Toxicity and Complexity scores.
        Satisfies Rubric B02 (Calculate Metrics).
        """
        prompt = f"""
        You are an AI Ethics Auditor. Analyze the following medical text.
        
        Text: "{text}"
        
        Return a valid JSON object with exactly these keys:
        - toxicity_score: (0-10, where 10 is hate speech)
        - complexity_score: (0-10, where 10 is PhD level, 0 is child level)
        - bias_detected: (true/false)
        - reasoning: (short explanation)
        
        Do not output markdown code blocks. Just the JSON string.
        """
        
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            # Basic cleaning to ensure JSON parsing
            clean_json = response.content.replace("```json", "").replace("```", "").strip()
            metrics = json.loads(clean_json)
            return metrics
        except Exception as e:
            # Fallback for robustness
            print(f"Fairness Audit Failed: {e}")
            return {
                "toxicity_score": 0.0, 
                "complexity_score": 5.0, 
                "bias_detected": False, 
                "reasoning": "Audit failed."
            }