from functools import lru_cache
from typing import Any

# Prefer pydantic-settings if available (Pydantic v2 best practice)
try:
    from pydantic_settings import BaseSettings
    from pydantic import Field, field_validator
except Exception:
    # Fallback for environments where pydantic-settings isn't installed
    from pydantic import BaseSettings, Field  # type: ignore
    try:
        from pydantic import field_validator  # v2
    except Exception:
        # v1 compatibility shim
        def field_validator(*args, **kwargs):  # type: ignore
            def deco(f):
                return f
            return deco


class Settings(BaseSettings):
    # Keys
    google_api_key: str = Field(default="", env="GOOGLE_API_KEY")
    groq_api_key: str = Field(default="", env="GROQ_API_KEY")

    # Models
    gemini_model: str = Field(default="gemini-2.5-flash", env="GEMINI_MODEL")
    groq_model: str = Field(default="llama-3.1-70b-versatile", env="GROQ_MODEL")

    # App
    debug: bool = Field(default=True, env="DEBUG")

    # ---- tolerant boolean parsing ----
    @field_validator("debug", mode="before")
    @classmethod
    def _parse_bool(cls, v: Any) -> Any:
        if isinstance(v, bool):
            return v
        if v is None:
            return False
        if isinstance(v, (int, float)):
            return bool(v)
        s = str(v).strip().lower()
        if s in {"1", "true", "t", "yes", "y", "on"}:
            return True
        if s in {"0", "false", "f", "no", "n", "off"}:
            return False
        # last resort: let pydantic try or default to False
        return False

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()