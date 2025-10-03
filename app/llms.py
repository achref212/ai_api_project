from groq import Groq
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from crewai_tools import BaseTool
import os

# Hardcoded keys (use .env in prod: from dotenv import load_dotenv; load_dotenv())
GROQ_API_KEY = "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"
GEMINI_API_KEY = "AIzaSyCGu2_r5CogQ1AIMAaUTT-yCzjso1aJnBA"

def get_groq_llm(model_name="llama3.1-70b-versatile"):
    """Groq LLM for fast inference."""
    client = Groq(api_key=GROQ_API_KEY)
    return ChatGroq(
        groq_api_key=GROQ_API_KEY,
        model_name=model_name,
        temperature=0.7,
    )

def get_gemini_llm(model_name="gemini-1.5-pro"):
    """Gemini LLM for summarization."""
    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=GEMINI_API_KEY,
        temperature=0.5,
    )

# Optional: Custom tool for message formatting (not used here for simplicity)
class MessageFormatterTool(BaseTool):
    name: str = "Message Formatter"
    description: str = "Formats conversation messages into a readable string."

    def _run(self, messages: List[Dict[str, str]]) -> str:
        formatted = "\n".join([f"{msg['sender']}: {msg['content']}" for msg in messages])
        return formatted