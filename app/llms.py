from typing import List, Dict
import os
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from crewai.tools import BaseTool  # Kept for completeness, but no tools used

# Load environment variables from .env file
load_dotenv()

# API Keys from .env
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Validate keys
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is required. Please set it in .env file.")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is required. Please set it in .env file.")

def get_groq_llm(model_name="groq/llama-3.3-70b-versatile"):
    """Groq LLM for fast, factual tasks."""
    return ChatGroq(
        groq_api_key=GROQ_API_KEY,
        model_name=model_name,
        temperature=0.7,
    )

def get_gemini_llm(model_name="gemini-2.5-flash"):
    """Gemini 2.5 Flash for creative, detailed tasks."""
    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=GEMINI_API_KEY,
        temperature=0.7,
    )

def get_llm(provider: str):
    """Dynamic LLM selector: 'groq' or 'gemini'."""
    if provider.lower() == "groq":
        return get_groq_llm()
    elif provider.lower() == "gemini":
        return get_gemini_llm()
    else:
        raise ValueError(f"Invalid LLM provider: {provider}. Use 'groq' or 'gemini'.")

# No tools used to avoid errors