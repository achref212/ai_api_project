from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Literal, Optional
import json, re

from .models import (
    AnalyzeRequest,
    AnalyzeResponse,
    TripPlan,
    CultureInfo,
    FoodSuggestions,
    UnreadSummary,
)
from .crew import run_pipeline

app = FastAPI(
    title="CrewAI Travel Concierge API",
    version="1.0.0",
    description=(
        "Analyze user conversations and generate a short trip plan (LLM1), "
        "culture & etiquette (LLM2), food ideas (LLM3), and an unread summary (LLM4)."
    ),
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


def _extract_jsonish(blob) -> dict | None:
    """Return a dict from string/dict/list that may contain code fences or extra text."""
    if not blob:
        return None
    if isinstance(blob, dict):
        return blob
    if isinstance(blob, list):
        for item in blob:
            if isinstance(item, dict):
                return item
            if isinstance(item, str):
                d = _extract_jsonish(item)
                if d:
                    return d
        return None

    if isinstance(blob, str):
        s = blob.strip()
        # strip ```json ... ``` or ``` ... ```
        if s.startswith("```"):
            s = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", s)
            s = re.sub(r"\s*```$", "", s)
        # find first {...}
        m = re.search(r"\{.*\}", s, re.S)
        if not m:
            return None
        json_str = m.group(0)
        try:
            return json.loads(json_str)
        except Exception:
            return None
    return None


@app.post("/api/v1/analyze", response_model=AnalyzeResponse)
def analyze(
    req: AnalyzeRequest,
    provider_sequence: Optional[List[Literal["gemini", "groq"]]] = Query(
        default=None,
        description="Provider list for [planner, culture, food, summary]; defaults to all gemini.",
    ),
):
    if not req.messages:
        raise HTTPException(status_code=400, detail="messages cannot be empty")

    provider_sequence = provider_sequence or ["gemini", "gemini", "gemini", "gemini"]

    raw_outputs = run_pipeline(
        messages=[m.dict() for m in req.messages],
        locale=req.locale or "en",
        destination_hint=req.destination_hint,
        provider_sequence=provider_sequence,
    )

    def _coerce(label: str, model):
        blob = raw_outputs.get(label)
        data = _extract_jsonish(blob)
        if not data:
            return None
        try:
            return model(**data)
        except Exception:
            return None

    resp = AnalyzeResponse(
        trip_plan=_coerce("trip_plan", TripPlan),
        culture=_coerce("culture", CultureInfo),
        food=_coerce("food", FoodSuggestions),
        unread_summary=_coerce("unread_summary", UnreadSummary),
        raw_outputs=raw_outputs,
    )

    # Fallback: if all are None, try to parse the aggregated 'raw'
    if not any([resp.trip_plan, resp.culture, resp.food, resp.unread_summary]):
        raw_blob = raw_outputs.get("raw")
        data = _extract_jsonish(raw_blob)
        if isinstance(data, dict) and {"summary", "action_items"} <= set(data.keys()):
            try:
                resp.unread_summary = UnreadSummary(**data)
            except Exception:
                pass

    return resp