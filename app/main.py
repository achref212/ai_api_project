from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Literal, Optional, Any
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
    version="1.1.0",
    description=(
        "Analyze user conversations and generate a trip plan (LLM1), "
        "culture & etiquette (LLM2), food ideas (LLM3), and an unread summary (LLM4). "
        "Designed to work for ANY locality: cities, villages, rural areas, islands, parks."
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


# ---------- Robust JSON extraction utilities ----------

FENCE_START = re.compile(r"^```[a-zA-Z0-9_-]*\s*")
FENCE_END   = re.compile(r"\s*```$")


def _strip_fences(s: str) -> str:
    s = s.strip()
    s = FENCE_START.sub("", s)
    s = FENCE_END.sub("", s)
    return s.strip()


def _first_json_object(s: str) -> Optional[str]:
    """
    Return the first {...} block (handles extra text around).
    """
    m = re.search(r"\{.*\}", s, re.S)
    return m.group(0) if m else None


def _maybe_load_json(text: str) -> Optional[dict]:
    text = text.strip()
    if not text:
        return None
    # remove markdown fences if present
    text = _strip_fences(text)
    # if it's already just JSON, try parse
    try:
        return json.loads(text)
    except Exception:
        pass
    # else, try to find the first {...}
    first = _first_json_object(text)
    if not first:
        return None
    try:
        return json.loads(first)
    except Exception:
        return None


def _extract_jsonish(blob: Any) -> Optional[dict]:
    """
    Accepts strings, dicts (including CrewAI step dicts), or lists and returns a dict if found.
    Handles common CrewAI shapes: {"raw": "...json..."}, {"output": "...json..."}.
    """
    if blob is None:
        return None

    # If it's already a dict with our expected schema
    if isinstance(blob, dict):
        # Directly shaped dict?
        if any(k in blob for k in ("destination", "overview", "theme", "summary")):
            return blob

        # CrewAI step-like structures
        for key in ("raw", "output", "pydantic", "json_dict"):
            if key in blob and blob[key]:
                inner = _extract_jsonish(blob[key])
                if inner:
                    return inner
        # If dict but no recognized keys, give up
        return None

    # If it's a list, try each item
    if isinstance(blob, list):
        for item in blob:
            out = _extract_jsonish(item)
            if out:
                return out
        return None

    # If it's a string, try to load JSON
    if isinstance(blob, str):
        return _maybe_load_json(blob)

    return None


# ---------- API Endpoint ----------

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
        # leniency: trim strings & coerce basic types
        try:
            # strip whitespace from all string fields
            if isinstance(data, dict):
                for k, v in list(data.items()):
                    if isinstance(v, str):
                        data[k] = v.strip()
                    if isinstance(v, list):
                        data[k] = [x.strip() if isinstance(x, str) else x for x in v]
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