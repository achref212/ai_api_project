from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class Message(BaseModel):
    sender: str = Field(..., description="User id or display name")
    text: str = Field(..., description="Message content")
    timestamp: Optional[datetime] = Field(None, description="ISO timestamp if available")
    read: Optional[bool] = Field(default=None, description="Whether the message was read")


class AnalyzeRequest(BaseModel):
    messages: List[Message] = Field(..., description="Chronological list of messages")
    locale: Optional[str] = Field(default="en", description="Language hint for outputs")
    destination_hint: Optional[str] = Field(default=None, description="If users talk about a place, you may pass it here")


class TripPlan(BaseModel):
    destination: str
    days: int
    suggested_itinerary: List[str]


class CultureInfo(BaseModel):
    overview: str
    do_and_dont: List[str]
    key_phrases: List[str]


class FoodSuggestions(BaseModel):
    theme: str
    suggestions: List[str]


class UnreadSummary(BaseModel):
    summary: str
    action_items: List[str]


class AnalyzeResponse(BaseModel):
    trip_plan: TripPlan | None = None
    culture: CultureInfo | None = None
    food: FoodSuggestions | None = None
    unread_summary: UnreadSummary | None = None
    raw_outputs: dict = Field(default_factory=dict, description="Raw agent outputs for debugging")