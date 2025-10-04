from __future__ import annotations
from typing import Dict, Any, List, Literal, Optional
import json, re
from crewai import Agent, Task, Crew, Process
from .llms import get_llm

# ---------------- helpers ----------------

def _concat_messages(messages: List[dict]) -> str:
    return "\n".join(f"{m.get('sender','user')}: {m.get('text','')}" for m in messages)

def _read_prompt(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

_MD_OPEN = re.compile(r"^\s*```[a-zA-Z0-9_-]*", re.M)
_MD_CLOSE = re.compile(r"```\s*$", re.M)

def _strip_md_fences(s: str) -> str:
    s = s.strip()
    s = _MD_OPEN.sub("", s)
    s = _MD_CLOSE.sub("", s)
    return s.strip()

def _first_json_obj(text: str) -> Optional[str]:
    m = re.search(r"\{.*\}", text, re.S)
    return m.group(0) if m else None

def parse_jsonish(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, dict):
        if "raw" in raw and isinstance(raw["raw"], str):
            raw = raw["raw"]
        else:
            return raw
    if not isinstance(raw, str):
        return raw
    cleaned = _strip_md_fences(raw)
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    first = _first_json_obj(cleaned)
    if first:
        try:
            return json.loads(first)
        except Exception:
            return cleaned
    return cleaned

# ---------------- context detection ----------------

ContextType = Literal["travel", "project", "social"]

TRAVEL_HINTS  = re.compile(r"\b(trip|travel|itinerary|hotel|flight|train|visa|beach|resort|tour|hike|mountain|village|island|weekend|louvre|montmartre|paris|rome|chamonix|itinerar)\b", re.I)
PROJECT_HINTS = re.compile(r"\b(task|todo|deadline|deliverable|budget|cost|split|share|pay|invoice|assign|status|milestone|sprint|ticket|story)\b", re.I)
SOCIAL_HINTS  = re.compile(r"\b(feel|angry|tension|vibe|tone|argue|confused|happy|sad|frustrated|toxic|mood|engagement|distant|reset)\b", re.I)

def classify_context(messages: List[dict]) -> ContextType:
    text = " ".join(m.get("text", "") for m in messages)
    scores = {
        "travel": len(TRAVEL_HINTS.findall(text)),
        "project": len(PROJECT_HINTS.findall(text)),
        "social": len(SOCIAL_HINTS.findall(text)),
    }
    return max(scores, key=scores.get) if any(scores.values()) else "travel"

# ---------------- providers ----------------

def llm_for(role: str, forced: Optional[str]) -> Any:
    if forced in {"gemini", "groq"}:
        return get_llm(forced)
    default_map = {
        "TripPlanner": "gemini",
        "CultureGuide": "gemini",
        "FoodieFriend": "groq",
        "WeatherAdvisor": "groq",
        "PackSmart": "gemini",
        "TaskOrganizer": "groq",
        "ExpenseTracker": "groq",
        "UnreadSummarizer": "gemini",
        "MoodDetector": "gemini",
        "ConversationAnalyzer": "groq",
    }
    return get_llm(default_map.get(role, "gemini"))

# ---------------- validators (keep models in line) ----------------

def _ensure_list_str(x: Any, max_len: int | None = None) -> List[str]:
    out: List[str] = []
    if isinstance(x, list):
        for i in x:
            if isinstance(i, str):
                s = i.strip()
                if s:
                    out.append(s)
    if max_len is not None:
        out = out[:max_len]
    return out

def guard_trip(d: Any) -> Dict[str, Any] | None:
    if not isinstance(d, dict): return None
    out: Dict[str, Any] = {
        "destination": str(d.get("destination") or "unknown"),
        "days": int(d.get("days") or 3),
        "day_by_day": [],
        "weather_assumptions": {
            "season": "unknown",
            "typical_conditions": [],
            "packing_highlights": []
        }
    }
    # accept either new schema or fallback suggested_itinerary
    if "day_by_day" in d and isinstance(d["day_by_day"], list):
        for i, day in enumerate(d["day_by_day"], start=1):
            if not isinstance(day, dict): continue
            out["day_by_day"].append({
                "day": int(day.get("day") or i),
                "theme": str(day.get("theme") or "").strip() or "Day plan",
                "morning": str(day.get("morning") or "").strip() or "Free exploration",
                "afternoon": str(day.get("afternoon") or "").strip() or "Local walk",
                "evening": str(day.get("evening") or "").strip() or "Relaxed dinner",
                "indoor_rain_plan": _ensure_list_str(day.get("indoor_rain_plan"), 3) or ["Local museum", "Covered market"],
                "dining_ideas": _ensure_list_str(day.get("dining_ideas"), 3) or ["neighborhood café", "casual bistro"],
                "local_tips": _ensure_list_str(day.get("local_tips"), 3) or ["Book popular sites in advance"]
            })
    elif "suggested_itinerary" in d and isinstance(d["suggested_itinerary"], list):
        # fallback transform: 1 line per itinerary item
        for i, line in enumerate(d["suggested_itinerary"], start=1):
            if isinstance(line, str):
                out["day_by_day"].append({
                    "day": i,
                    "theme": "Highlights",
                    "morning": line,
                    "afternoon": "Flexible time",
                    "evening": "Local dinner",
                    "indoor_rain_plan": ["Local museum", "Gallery"],
                    "dining_ideas": ["classic bistro", "market hall"],
                    "local_tips": ["Greet with 'Hello' or local equivalent"]
                })
    # weather assumptions
    if isinstance(d.get("weather_assumptions"), dict):
        wa = d["weather_assumptions"]
        out["weather_assumptions"]["season"] = str(wa.get("season") or "unknown")
        out["weather_assumptions"]["typical_conditions"] = _ensure_list_str(wa.get("typical_conditions"), 4)
        out["weather_assumptions"]["packing_highlights"] = _ensure_list_str(wa.get("packing_highlights"), 4)

    # clamp sizes
    if not out["day_by_day"]:
        # minimal sensible default for 3 days
        for i in range(1, min(out["days"], 3) + 1):
            out["day_by_day"].append({
                "day": i,
                "theme": "Explore & local culture",
                "morning": "Orientation walk",
                "afternoon": "Key sights or nature trail",
                "evening": "Neighborhood stroll",
                "indoor_rain_plan": ["Local museum", "Covered market"],
                "dining_ideas": ["casual eatery", "street food market"],
                "local_tips": ["Carry reusable bottle"]
            })
    out["days"] = min(max(out["days"], 1), 5)
    out["day_by_day"] = out["day_by_day"][:out["days"]]
    return out

def guard_culture(d: Any) -> Dict[str, Any] | None:
    if not isinstance(d, dict): return None
    return {
        "overview": str(d.get("overview") or "").strip() or "Be polite and greet locals; respect queues and quiet spaces.",
        "do_and_dont": _ensure_list_str(d.get("do_and_dont"), 8) or [
            "Do: greet with 'Hello' before asking for help",
            "Don't: speak loudly in small venues"
        ],
        "key_phrases": _ensure_list_str(d.get("key_phrases"), 8) or [
            "Hello: Hello",
            "Thanks: Thank you",
            "Please: Please",
            "Excuse me: Excuse me",
            "Goodbye: Goodbye"
        ],
        "safety_basics": _ensure_list_str(d.get("safety_basics"), 6) or [
            "Watch your belongings in crowded areas",
            "Use licensed taxis or known ride-hailing"
        ],
    }

def guard_food(d: Any) -> Dict[str, Any] | None:
    if not isinstance(d, dict): return None
    return {
        "theme": str(d.get("theme") or "").strip() or "Local, budget-friendly picks near central areas",
        "suggestions": _ensure_list_str(d.get("suggestions"), 5) or [
            "1) Cozy neighborhood bistro fare",
            "2) Market hall tastings",
            "3) Bakery lunch: quiche/sandwich"
        ],
        "dish_ideas": _ensure_list_str(d.get("dish_ideas"), 6) or [
            "Hearty regional stew", "Fresh pastry", "Grilled fish or chicken"
        ]
    }

def guard_weather(d: Any) -> Dict[str, Any] | None:
    if not isinstance(d, dict): return None
    return {
        "season": str(d.get("season") or "unknown"),
        "typical_conditions": _ensure_list_str(d.get("typical_conditions"), 5) or ["variable conditions"],
        "day_adjustments": _ensure_list_str(d.get("day_adjustments"), 8) or [
            "Carry compact umbrella for showers",
            "Prefer indoor sights if heavy rain"
        ]
    }

def guard_packsmart(d: Any) -> Dict[str, Any] | None:
    if not isinstance(d, dict): return None
    items = _ensure_list_str(d.get("packing_list"))
    # dedupe + min size + cap
    seen, cleaned = set(), []
    for x in items:
        if x not in seen:
            cleaned.append(x); seen.add(x)
    essentials = ["ID & wallet", "Phone & charger", "Reusable water bottle"]
    for e in essentials:
        if e not in seen:
            cleaned.insert(0, e); seen.add(e)
    cleaned = cleaned[:15]
    return {"packing_list": cleaned}

# ---------------- crews ----------------

def build_travel_crew(overrides: Optional[Dict[str, str]] = None) -> Crew:
    overrides = overrides or {}
    planner = Agent(
        role="TripPlanner",
        goal="Produce strict JSON trip plan only; avoid packing/food/culture keys.",
        backstory="You are disciplined; you never add extra keys.",
        llm=llm_for("TripPlanner", overrides.get("TripPlanner")),
        verbose=False, allow_delegation=False,
    )
    culture = Agent(
        role="CultureGuide",
        goal="Compact etiquette + phrases JSON.",
        backstory="Accurate, brief, village-and-city friendly.",
        llm=llm_for("CultureGuide", overrides.get("CultureGuide")),
        verbose=False, allow_delegation=False,
    )
    foodie = Agent(
        role="FoodieFriend",
        goal="Styles/areas only; no fake names; JSON.",
        backstory="Budget-aware foodie.",
        llm=llm_for("FoodieFriend", overrides.get("FoodieFriend")),
        verbose=False, allow_delegation=False,
    )
    weather = Agent(
        role="WeatherAdvisor",
        goal="Seasonal assumptions + day adjustments; JSON.",
        backstory="No web calls; generic but practical.",
        llm=llm_for("WeatherAdvisor", overrides.get("WeatherAdvisor")),
        verbose=False, allow_delegation=False,
    )
    packsmart = Agent(
        role="PackSmart",
        goal="Compact packing list JSON only.",
        backstory="Practical & minimal.",
        llm=llm_for("PackSmart", overrides.get("PackSmart")),
        verbose=False, allow_delegation=False,
    )

    tasks = [
        Task(description=_read_prompt("app/prompts/trip_planner.md"), agent=planner, expected_output="JSON"),
        Task(description=_read_prompt("app/prompts/culture.md"), agent=culture, expected_output="JSON"),
        Task(description=_read_prompt("app/prompts/food.md"), agent=foodie, expected_output="JSON"),
        Task(description=_read_prompt("app/prompts/weather.md"), agent=weather, expected_output="JSON"),
        Task(description=_read_prompt("app/prompts/packsmart.md"), agent=packsmart, expected_output="JSON"),
    ]
    return Crew(agents=[planner, culture, foodie, weather, packsmart], tasks=tasks, process=Process.sequential, verbose=False)

def build_project_crew(overrides: Optional[Dict[str, str]] = None) -> Crew:
    overrides = overrides or {}
    tasker = Agent(role="TaskOrganizer", goal="Extract tasks/assignees/dates JSON.", backstory="Project minded.",
                   llm=llm_for("TaskOrganizer", overrides.get("TaskOrganizer")), verbose=False, allow_delegation=False)
    expenses = Agent(role="ExpenseTracker", goal="Expenses/budget split JSON.", backstory="Clear categories.",
                     llm=llm_for("ExpenseTracker", overrides.get("ExpenseTracker")), verbose=False, allow_delegation=False)
    unread = Agent(role="UnreadSummarizer", goal="Unread summary + actions JSON.", backstory="Keeps teams aligned.",
                   llm=llm_for("UnreadSummarizer", overrides.get("UnreadSummarizer")), verbose=False, allow_delegation=False)
    tasks = [
        Task(description=_read_prompt("app/prompts/tasks.md"), agent=tasker, expected_output="JSON"),
        Task(description=_read_prompt("app/prompts/expenses.md"), agent=expenses, expected_output="JSON"),
        Task(description=_read_prompt("app/prompts/summary.md"), agent=unread, expected_output="JSON"),
    ]
    return Crew(agents=[tasker, expenses, unread], tasks=tasks, process=Process.sequential, verbose=False)

def build_social_crew(overrides: Optional[Dict[str, str]] = None) -> Crew:
    overrides = overrides or {}
    mood = Agent(role="MoodDetector", goal="Tone + signals JSON.", backstory="Kind and neutral.",
                 llm=llm_for("MoodDetector", overrides.get("MoodDetector")), verbose=False, allow_delegation=False)
    analytics = Agent(role="ConversationAnalyzer", goal="Participation stats JSON.", backstory="Fair and helpful.",
                      llm=llm_for("ConversationAnalyzer", overrides.get("ConversationAnalyzer")), verbose=False, allow_delegation=False)
    unread = Agent(role="UnreadSummarizer", goal="Unread summary + actions JSON.", backstory="Keeps teams aligned.",
                   llm=llm_for("UnreadSummarizer", overrides.get("UnreadSummarizer")), verbose=False, allow_delegation=False)
    tasks = [
        Task(description=_read_prompt("app/prompts/mood.md"), agent=mood, expected_output="JSON"),
        Task(description=_read_prompt("app/prompts/convo_analytics.md"), agent=analytics, expected_output="JSON"),
        Task(description=_read_prompt("app/prompts/summary.md"), agent=unread, expected_output="JSON"),
    ]
    return Crew(agents=[mood, analytics, unread], tasks=tasks, process=Process.sequential, verbose=False)

# ---------------- orchestrate ----------------

def build_crew_for_context(ctx: ContextType, overrides: Optional[Dict[str,str]] = None) -> Crew:
    if ctx == "project": return build_project_crew(overrides)
    if ctx == "social":  return build_social_crew(overrides)
    return build_travel_crew(overrides)

def run_orchestrator(
    messages: List[dict],
    locale: str = "en",
    destination_hint: Optional[str] = None,
    context: Optional[ContextType] = None,
    provider_overrides: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    convo = _concat_messages(messages)
    ctx = context or classify_context(messages)
    crew = build_crew_for_context(ctx, provider_overrides)

    context_blob = (
        "\n\n---\nINPUT CONTEXT\n"
        f"Conversation:\n{convo}\n\n"
        f"Locale: {locale}\n"
        f"Destination hint: {destination_hint or 'N/A'}\n"
        "---\n"
    )
    # Append shared context to each task prompt (no CrewAI .context usage)
    for t in crew.tasks:
        if isinstance(t.description, str):
            t.description = t.description.rstrip() + context_blob

    result = crew.kickoff()

    # Resolve outputs across CrewAI versions
    steps = []
    try:
        steps = getattr(getattr(crew, "last_crew_run", None), "tasks_outputs", None) or []
    except Exception:
        steps = []
    if not steps:
        steps = result if isinstance(result, list) else [result]

    if ctx == "travel":
        labels = ["trip_plan", "culture", "food", "weather", "packsmart"]
    elif ctx == "project":
        labels = ["tasks", "expenses", "unread_summary"]
    else:
        labels = ["mood", "convo_analytics", "unread_summary"]

    final: Dict[str, Any] = {"context": ctx}
    for label, step in zip(labels, steps):
        raw = None
        if isinstance(step, str):
            raw = step
        elif isinstance(step, dict):
            raw = step.get("raw") or step.get("output") or json.dumps(step)
        else:
            raw = getattr(step, "raw", None) or getattr(step, "output", None) or str(step)
        parsed = parse_jsonish(raw)

        # Apply guards for travel pack to avoid wrong content (e.g., packing_list in TripPlanner)
        if ctx == "travel":
            if label == "trip_plan":
                parsed = guard_trip(parsed) or parsed
            elif label == "culture":
                parsed = guard_culture(parsed) or parsed
            elif label == "food":
                parsed = guard_food(parsed) or parsed
            elif label == "weather":
                parsed = guard_weather(parsed) or parsed
            elif label == "packsmart":
                parsed = guard_packsmart(parsed) or parsed

        final[label] = {"raw": raw, "json": parsed}

    return final