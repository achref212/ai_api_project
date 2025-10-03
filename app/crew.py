from crewai import Agent, Task, Crew
from app.llms import get_llm
from app.models import Message
from typing import List, Dict

def create_crew(messages: List[Message], active_configs: Dict[str, Dict[str, str]]) -> Crew:
    # Format input conversation
    conversation = "\n".join([f"{msg.sender}: {msg.content}" for msg in messages])

    # Agents (only instantiate if active, with dynamic LLM)
    agents = {}
    tasks = []

    # Travel Agent (Gemini for creative planning)
    if active_configs.get("travel", {}).get("active", False):
        agents["travel"] = Agent(
            role="Travel Planner",
            goal="Analyze the conversation for travel discussions and suggest the best itinerary if relevant.",
            backstory="You are an expert travel planner who creates detailed, personalized plans based on user chats.",
            llm=get_llm(active_configs["travel"]["llm"]),
            verbose=True,
        )
        tasks.append(Task(
            description=f"Examine this conversation: {conversation}. If travel to a place like Paris is discussed, generate a detailed plan (itinerary, tips). Output only if relevant, else 'No travel suggestion'.",
            agent=agents["travel"],
            expected_output="A travel plan string or 'No suggestion'.",
        ))

    # Culture Agent (Groq for factual info)
    if active_configs.get("culture", {}).get("active", False):
        agents["culture"] = Agent(
            role="Culture Guide",
            goal="Extract places from the conversation and provide cultural and general information if relevant.",
            backstory="You are a knowledgeable guide sharing insights on history, culture, and tips for destinations.",
            llm=get_llm(active_configs["culture"]["llm"]),
            verbose=True,
        )
        tasks.append(Task(
            description=f"Examine this conversation: {conversation}. Extract any places and provide cultural/general info. Output only if relevant, else 'No culture info'.",
            agent=agents["culture"],
            expected_output="Cultural info string or 'No suggestion'.",
        ))

    # Restaurant Agent (Gemini for recommendations)
    if active_configs.get("restaurant", {}).get("active", False):
        agents["restaurant"] = Agent(
            role="Food Recommender",
            goal="Detect talks about eating or dining and suggest the best restaurants if relevant.",
            backstory="You are a gourmet expert recommending top-rated eateries based on user preferences.",
            llm=get_llm(active_configs["restaurant"]["llm"]),
            verbose=True,
        )
        tasks.append(Task(
            description=f"Examine this conversation: {conversation}. If eating/dining is mentioned, suggest top 3 restaurants for the place. Output only if relevant, else 'No restaurant suggestions'.",
            agent=agents["restaurant"],
            expected_output="Restaurant list string or 'No suggestion'.",
        ))

    # Summary Agent (Groq for quick summary, always active)
    active_configs["summary"] = {"active": True, "llm": "groq"}
    agents["summary"] = Agent(
        role="Conversation Summarizer",
        goal="Summarize the entire discussion, focusing on key points as if they are 'unread' messages.",
        backstory="You are a concise summarizer who captures the essence of user chats without adding fluff.",
        llm=get_llm(active_configs["summary"]["llm"]),
        verbose=True,
    )
    tasks.append(Task(
        description=f"Summarize this unread discussion: {conversation}. Keep it brief, highlight key topics and decisions.",
        agent=agents["summary"],
        expected_output="A concise summary string.",
    ))

    # Crew
    crew = Crew(
        agents=list(agents.values()),
        tasks=tasks,
        verbose=True,
    )

    return crew