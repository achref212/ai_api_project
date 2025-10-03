from pydantic import BaseModel
from typing import List, Dict, Any

class Message(BaseModel):
    sender: str
    content: str

class AnalyzeRequest(BaseModel):
    messages: List[Message]

class Suggestion(BaseModel):
    type: str  # e.g., "travel", "culture", "restaurant"
    content: str

class AnalyzeResponse(BaseModel):
    suggestions: List[Suggestion]
    summary: str