from __future__ import annotations

from typing import Dict, Any, List, Literal, Optional
from pathlib import Path

from crewai import Agent, Task, Crew, Process
from .llms import get_llm
from .config import get_settings

VALID_PROVIDERS = ("gemini", "groq")
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

MessageDict = Dict[str, Any]


def _concat_messages(messages: List[MessageDict]) -> str:
    parts: List[str] = []
    for m in messages:
        who = str(m.get("sender", "user"))
        txt = str(m.get("text", ""))
        parts.append(f"{who}: {txt}")
    return "\n".join(parts)


def _norm_providers(seq: Optional[List[str]]) -> List[str]:
    if not seq:
        return ["gemini", "gemini", "gemini", "gemini"]
    norm: List[str] = []
    for i in range(4):
        prov = (seq[i] if i < len(seq) else "gemini") or "gemini"
        prov = prov.lower().strip()
        if prov not in VALID_PROVIDERS:
            prov = "gemini"
        norm.append(prov)
    return norm


def _read_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def build_crew(provider_sequence: Optional[List[Literal["gemini", "groq"]]] = None) -> Crew:
    _ = get_settings()
    provider_sequence = _norm_providers(provider_sequence)

    planner_llm = get_llm(provider_sequence[0])
    culture_llm = get_llm(provider_sequence[1])
    food_llm    = get_llm(provider_sequence[2])
    summary_llm = get_llm(provider_sequence[3])

    planner = Agent(
        role="TripPlanner",
        goal="Create a short, practical plan for the trip mentioned by users.",
        backstory="Expert travel planner focusing on concise, structured itineraries.",
        llm=planner_llm,
        verbose=False,
        allow_delegation=False,
    )
    culture = Agent(
        role="CultureGuide",
        goal="Explain culture and etiquette for the destination in a compact way.",
        backstory="Cultural advisor with focus on helpful etiquette.",
        llm=culture_llm,
        verbose=False,
        allow_delegation=False,
    )
    foodie = Agent(
        role="FoodieFriend",
        goal="Suggest dining ideas aligned with users' tastes.",
        backstory="Food enthusiast who suggests cuisines/types without fabricating specifics.",
        llm=food_llm,
        verbose=False,
        allow_delegation=False,
    )
    summarizer = Agent(
        role="ChatSummarizer",
        goal="Summarize unread discussion and action items.",
        backstory="Keeps the team on the same page with succinct recaps.",
        llm=summary_llm,
        verbose=False,
        allow_delegation=False,
    )

    trip_task = Task(
        description=_read_prompt("trip_planner.md"),
        agent=planner,
        expected_output="Valid JSON per the schema in the prompt."
    )
    culture_task = Task(
        description=_read_prompt("culture.md"),
        agent=culture,
        expected_output="Valid JSON per the schema in the prompt."
    )
    food_task = Task(
        description=_read_prompt("food.md"),
        agent=foodie,
        expected_output="Valid JSON per the schema in the prompt."
    )
    summary_task = Task(
        description=_read_prompt("summary.md"),
        agent=summarizer,
        expected_output="Valid JSON per the schema in the prompt."
    )

    crew = Crew(
        agents=[planner, culture, foodie, summarizer],
        tasks=[trip_task, culture_task, food_task, summary_task],
        process=Process.sequential,
        verbose=False,
    )
    return crew


def run_pipeline(
    messages: List[MessageDict],
    locale: str = "en",
    destination_hint: Optional[str] = None,
    provider_sequence: Optional[List[Literal["gemini", "groq"]]] = None,
) -> Dict[str, Any]:
    convo = _concat_messages(messages)
    crew = build_crew(provider_sequence)

    # Inject inputs into each task's description (do NOT write to task.context)
    input_block = (
        "\n\n---\n"
        "INPUT\n"
        "Conversation:\n"
        f"{convo}\n\n"
        f"Locale: {locale}\n"
        f"Destination hint: {destination_hint or 'N/A'}\n"
        "---\n"
    )
    for task in crew.tasks:
        task.description = task.description + input_block

    results = crew.kickoff()

    out_map: Dict[str, Any] = {}
    labels = ["trip_plan", "culture", "food", "unread_summary"]

    # Newer CrewAI
    try:
        steps = getattr(crew.last_crew_run, "tasks_outputs", None)
        if steps:
            for label, step in zip(labels, steps):
                value = getattr(step, "raw", None) or getattr(step, "pydantic", None) or getattr(step, "output", None)
                out_map[label] = value
            return out_map
    except Exception:
        pass

    # Older CrewAI
    try:
        steps = getattr(crew.last_crew_run, "tasks_results", None)
        if steps:
            for label, step in zip(labels, steps):
                value = getattr(step, "raw", None) or getattr(step, "pydantic", None) or getattr(step, "output", None)
                out_map[label] = value
            return out_map
    except Exception:
        pass

    # Fallback: read each Task object's .output directly
    try:
        task_outputs = [getattr(t, "output", None) for t in crew.tasks]
        if any(task_outputs):
            for label, val in zip(labels, task_outputs):
                out_map[label] = val
            return out_map
    except Exception:
        pass

    out_map["raw"] = str(results)
    return out_map