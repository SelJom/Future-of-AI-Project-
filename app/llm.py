from langchain_openai import ChatOpenAI
from app.config import Config
import sys

def get_llm(temperature=0.1):
    """
    Returns a configured LLM client.
    Fails gracefully if the server is unreachable.
    """
    try:
        llm = ChatOpenAI(
            base_url=Config.LLM_BASE_URL,
            api_key=Config.LLM_API_KEY,
            model=Config.LLM_MODEL,
            temperature=temperature,
            max_retries=2,
            streaming=True
        )
        return llm
    except Exception as e:
        print(f"ERROR: Could not connect to LLM at {Config.LLM_BASE_URL}")
        print(f"Details: {e}")
        sys.exit(1)