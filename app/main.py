from fastapi import FastAPI, HTTPException
from app.models import AnalyzeRequest, AnalyzeResponse, Suggestion
from app.crew import create_crew
from app.llms import get_groq_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from typing import List, Dict

app = FastAPI(title="AI Suggestions API", description="CrewAI-powered analysis with dynamic LLM orchestration",
              version="1.0.1")


# Orchestrator: Classify topics and select active agents + LLM per agent
def orchestrate_llms(messages: List[Dict]) -> Dict[str, Dict[str, str]]:
    conversation = "\n".join([f"{msg['sender']}: {msg['content']}" for msg in messages])
    llm = get_groq_llm()  # Use quick Groq for classification

    prompt = ChatPromptTemplate.from_template(
        """Analyze this conversation and output JSON with keys for each topic: {"travel": {"active": true/false, "llm": "groq|gemini"}, "culture": {...}, "restaurant": {...}}.
        - travel: active if destinations/trips mentioned; llm="gemini" for creative planning.
        - culture: active if places/history mentioned; llm="groq" for factual info.
        - restaurant: active if food/dining discussed; llm="gemini" for recommendations.
        Do not include summary (always groq). Conversation: {conversation}"""
    )
    chain = prompt | llm | JsonOutputParser()

    try:
        result = chain.invoke({"conversation": conversation})
        # Ensure all keys present
        for key in ["travel", "culture", "restaurant"]:
            if key not in result:
                result[key] = {"active": False, "llm": "groq"}
        return result
    except Exception:
        # Fallback: Minimal activation
        return {
            "travel": {"active": False, "llm": "gemini"},
            "culture": {"active": False, "llm": "groq"},
            "restaurant": {"active": False, "llm": "gemini"}
        }


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_conversation(request: AnalyzeRequest):
    try:
        # Orchestrate: Get active configs with LLM choices
        active_configs = orchestrate_llms([msg.dict() for msg in request.messages])

        # Create and run dynamic crew
        crew = create_crew(request.messages, active_configs)
        result = crew.kickoff()  # Fixed: Changed from process() to kickoff()

        # Parse outputs with explicit mapping (only non-'No' content)
        outputs = {}
        for task in crew.tasks:
            if hasattr(task, 'output') and task.output.raw:
                raw = task.output.raw.strip()
                if "No" not in raw:
                    agent_type = task.agent.role.lower().split()[
                        0]  # e.g., "travel", "culture", "food" -> "restaurant", "conversation" -> "summary"
                    if agent_type == "food":
                        agent_type = "restaurant"
                    elif agent_type == "conversation":
                        agent_type = "summary"
                    outputs[agent_type] = raw

        # Build suggestions
        suggestions: List[Suggestion] = []
        if "travel" in outputs:
            suggestions.append(Suggestion(type="travel", content=outputs["travel"]))
        if "culture" in outputs:
            suggestions.append(Suggestion(type="culture", content=outputs["culture"]))
        if "restaurant" in outputs:
            suggestions.append(Suggestion(type="restaurant", content=outputs["restaurant"]))

        summary = outputs.get("summary", "No summary available due to processing error.")

        return AnalyzeResponse(
            suggestions=suggestions,
            summary=summary
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI processing failed: {str(e)}")


@app.get("/")
async def root():
    return {"message": "AI Suggestions API with Dynamic LLM Orchestration is running. Use /docs for Swagger."}