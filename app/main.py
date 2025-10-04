from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Literal, Optional, Dict, Any

from .orchestrator import run_orchestrator, ContextType

app = FastAPI(
    title="CrewAI Orchestrator API",
    version="1.3.0",
    description="Super-Agent orchestrator for Travel / Project / Social packs (Gemini + Groq)."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/v1/orchestrate")
def orchestrate(
    body: Dict[str, Any],
    context: Literal["auto", "travel", "project", "social"] = Query("auto"),
    trip_provider: Optional[Literal["gemini", "groq"]] = Query(None),
    culture_provider: Optional[Literal["gemini", "groq"]] = Query(None),
    food_provider: Optional[Literal["gemini", "groq"]] = Query(None),
    weather_provider: Optional[Literal["gemini", "groq"]] = Query(None),
    packsmart_provider: Optional[Literal["gemini", "groq"]] = Query(None),
):
    msgs = body.get("messages") or []
    if not isinstance(msgs, list) or not msgs:
        raise HTTPException(400, "messages must be a non-empty list")

    locale = body.get("locale") or "en"
    destination_hint = body.get("destination_hint")

    overrides = {
        "TripPlanner": trip_provider,
        "CultureGuide": culture_provider,
        "FoodieFriend": food_provider,
        "WeatherAdvisor": weather_provider,
        "PackSmart": packsmart_provider,
    }

    ctx: Optional[ContextType] = None if context == "auto" else context  # type: ignore
    return run_orchestrator(
        messages=[{"sender": m.get("sender","user"), "text": m.get("text","")} for m in msgs],
        locale=locale,
        destination_hint=destination_hint,
        context=ctx,
        provider_overrides=overrides
    )