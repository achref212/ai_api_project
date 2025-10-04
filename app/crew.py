from __future__ import annotations
from typing import Dict, Any, List, Optional
from crewai import Agent, Task, Crew, Process
from .llms import get_llm

PROMPT_BASE = "\n\nSTRICT: Output JSON ONLY, no markdown fences, no prose.\n"

TRIP = """You are TripPlanner.
OUTPUT:
{"destination":"<place or 'unknown'>","days":<int>,"suggested_itinerary":["Day 1: ...","Day 2: ...", "..."]}

Rules:
- No packing lists. No food/culture in this output.
""" + PROMPT_BASE

CULTURE = """You are CultureGuide.
OUTPUT:
{"overview":"...","do_and_dont":["Do: ...","Don't: ..."],"key_phrases":["Hello: ...","Thanks: ...","Please: ...","Excuse me: ...","Goodbye: ..."]}

Rules:
- No itinerary. No packing list.
""" + PROMPT_BASE

FOOD = """You are FoodieFriend.
OUTPUT:
{"theme":"...","suggestions":["1) ...","2) ...","3) ...","4) ... (optional)"]}

Rules:
- No venue name fabrication. No itinerary. No packing list.
""" + PROMPT_BASE

SUMMARY = """You are ChatSummarizer.
OUTPUT:
{"summary":"...", "action_items":["...","..."]}

Rules:
- Use only conversation messages.
""" + PROMPT_BASE


def _concat_messages(messages: List[dict]) -> str:
    return "\n".join(f"{m.get('sender','user')}: {m.get('text','')}" for m in messages)


def build_crew(provider_sequence: Optional[List[str]] = None) -> Crew:
    provider_sequence = provider_sequence or ["gemini","gemini","groq","gemini"]
    planner_llm = get_llm(provider_sequence[0])
    culture_llm = get_llm(provider_sequence[1])
    food_llm    = get_llm(provider_sequence[2])
    summary_llm = get_llm(provider_sequence[3])

    planner = Agent(role="TripPlanner", goal="Trip JSON only.", backstory="Planner.", llm=planner_llm, verbose=False, allow_delegation=False)
    culture = Agent(role="CultureGuide", goal="Culture JSON only.", backstory="Etiquette.", llm=culture_llm, verbose=False, allow_delegation=False)
    foodie  = Agent(role="FoodieFriend", goal="Food JSON only.", backstory="Food.", llm=food_llm, verbose=False, allow_delegation=False)
    summarizer = Agent(role="ChatSummarizer", goal="Summary JSON only.", backstory="Recaps.", llm=summary_llm, verbose=False, allow_delegation=False)

    return Crew(
        agents=[planner, culture, foodie, summarizer],
        tasks=[
            Task(description=TRIP,    agent=planner,    expected_output="JSON"),
            Task(description=CULTURE, agent=culture,    expected_output="JSON"),
            Task(description=FOOD,    agent=foodie,     expected_output="JSON"),
            Task(description=SUMMARY, agent=summarizer, expected_output="JSON"),
        ],
        process=Process.sequential,
        verbose=False,
    )


def run_pipeline(messages: List[dict], locale: str = "en", destination_hint: Optional[str] = None, provider_sequence: Optional[List[str]] = None) -> Dict[str, Any]:
    convo = _concat_messages(messages)
    crew = build_crew(provider_sequence)

    ctx_blob = (
        f"\n\n---\nINPUT CONTEXT\n"
        f"Conversation:\n{convo}\n\n"
        f"Locale: {locale}\n"
        f"Destination hint: {destination_hint or 'N/A'}\n"
        f"---\n"
    )
    for t in crew.tasks:
        t.description = t.description.rstrip() + ctx_blob

    result = crew.kickoff()

    try:
        steps = getattr(getattr(crew, "last_crew_run", None), "tasks_outputs", None) or []
    except Exception:
        steps = []
    if not steps:
        steps = result if isinstance(result, list) else [result]

    labels = ["trip_plan", "culture", "food", "unread_summary"]
    out: Dict[str, Any] = {}
    for label, step in zip(labels, steps):
        if isinstance(step, str):
            raw = step
        elif isinstance(step, dict):
            raw = step.get("raw") or step.get("output") or step
        else:
            raw = getattr(step, "raw", None) or getattr(step, "output", None) or str(step)
        out[label] = raw
    return out