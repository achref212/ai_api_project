import os
from typing import Literal, Optional
from crewai import LLM
from .config import get_settings


def _ensure_env(var: str, value: Optional[str]):
    """Expose keys to CrewAI/LiteLLM via environment variables."""
    if value and not os.environ.get(var):
        os.environ[var] = value


def _norm_gemini_model(name: str) -> str:
    # Accept "gemini-1.5-pro" and prefix to "gemini/gemini-1.5-pro"
    name = (name or "").strip()
    if not name:
        return "gemini/gemini-1.5-pro"
    if not (name.startswith("gemini/") or name.startswith("google/")):
        name = f"gemini/{name}"
    return name


def _norm_groq_model(name: str) -> str:
    # Accept "llama-3.1-70b-versatile" and prefix to "groq/llama-3.1-70b-versatile"
    name = (name or "").strip()
    if not name:
        return "groq/llama-3.1-70b-versatile"
    if not name.startswith("groq/"):
        name = f"groq/{name}"
    return name


def make_gemini(model: Optional[str] = None) -> LLM:
    s = get_settings()
    _ensure_env("GOOGLE_API_KEY", s.google_api_key)
    model_name = _norm_gemini_model(model or s.gemini_model)
    return LLM(
        model=model_name,
        temperature=0.3,
        api_key=s.google_api_key or os.environ.get("GOOGLE_API_KEY", ""),
    )


def make_groq(model: Optional[str] = None) -> LLM:
    s = get_settings()
    _ensure_env("GROQ_API_KEY", s.groq_api_key)
    model_name = _norm_groq_model(model or s.groq_model)
    return LLM(
        model=model_name,
        temperature=0.3,
        api_key=s.groq_api_key or os.environ.get("GROQ_API_KEY", ""),
    )


def get_llm(provider: Literal["gemini", "groq"] = "gemini", model: Optional[str] = None) -> LLM:
    if provider == "groq":
        return make_groq(model)
    return make_gemini(model)