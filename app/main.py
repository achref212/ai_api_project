from fastapi import FastAPI, HTTPException
from app.models import AnalyzeRequest, AnalyzeResponse, Suggestion
from app.crew import create_crew
from typing import List

app = FastAPI(title="AI Suggestions API", description="CrewAI-powered analysis of user messages", version="1.0.0")

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_conversation(request: AnalyzeRequest):
    try:
        # Create and kick off the crew
        crew = create_crew(request.messages)
        result = crew.kickoff()

        # Parse results (CrewAI outputs a combined result; here, extract per task)
        # For simplicity, assume sequential outputs; in prod, use crew outputs dict
        outputs = {
            "travel": crew.tasks[0].output.raw if "No" not in crew.tasks[0].output.raw else None,
            "culture": crew.tasks[1].output.raw if "No" not in crew.tasks[1].output.raw else None,
            "restaurant": crew.tasks[2].output.raw if "No" not in crew.tasks[2].output.raw else None,
            "summary": crew.tasks[3].output.raw,
        }

        # Build suggestions list
        suggestions: List[Suggestion] = []
        if outputs["travel"]:
            suggestions.append(Suggestion(type="travel", content=outputs["travel"]))
        if outputs["culture"]:
            suggestions.append(Suggestion(type="culture", content=outputs["culture"]))
        if outputs["restaurant"]:
            suggestions.append(Suggestion(type="restaurant", content=outputs["restaurant"]))

        return AnalyzeResponse(
            suggestions=suggestions,
            summary=outputs["summary"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI processing failed: {str(e)}")

@app.get("/")
async def root():
    return {"message": "AI Suggestions API is running. Use /docs for Swagger."}