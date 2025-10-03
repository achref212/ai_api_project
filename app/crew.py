from crewai import Agent, Task, Crew
from crewai_tools import Tool
from app.llms import get_groq_llm, get_gemini_llm
from app.models import Message
from typing import List

# Tools (extend as needed; here, a simple one for formatting messages)
from app.llms import MessageFormatterTool

def create_crew(messages: List[Message]) -> Crew:
    # Format input conversation
    conversation = "\n".join([f"{msg.sender}: {msg.content}" for msg in messages])

    # LLMs
    groq_llm = get_groq_llm()
    gemini_llm = get_gemini_llm()

    # Agents
    travel_agent = Agent(
        role="Travel Planner",
        goal="Analyze the conversation for travel discussions (e.g., destinations like Paris) and suggest the best itinerary if relevant.",
        backstory="You are an expert travel planner who creates detailed, personalized plans based on user chats.",
        llm=groq_llm,
        tools=[MessageFormatterTool()],  # Optional tool for formatting
        verbose=True,
    )

    culture_agent = Agent(
        role="Culture Guide",
        goal="Extract places from the conversation and provide cultural and general information if travel or locations are mentioned.",
        backstory="You are a knowledgeable guide sharing insights on history, culture, and tips for destinations.",
        llm=groq_llm,
        verbose=True,
    )

    restaurant_agent = Agent(
        role="Food Recommender",
        goal="Detect talks about eating or dining and suggest the best restaurants for the mentioned place.",
        backstory="You are a gourmet expert recommending top-rated eateries based on user preferences.",
        llm=groq_llm,
        verbose=True,
    )

    summarizer_agent = Agent(
        role="Conversation Summarizer",
        goal="Summarize the entire discussion, focusing on key points as if they are 'unread' messages.",
        backstory="You are a concise summarizer who captures the essence of user chats without adding fluff.",
        llm=gemini_llm,  # Using Gemini for variety/summary
        verbose=True,
    )

    # Tasks (each examines the full conversation)
    travel_task = Task(
        description=f"Examine this conversation: {conversation}. If travel to a place like Paris is discussed, generate a detailed plan (itinerary, tips). Output only if relevant, else 'No travel suggestion'.",
        agent=travel_agent,
        expected_output="A travel plan string or 'No suggestion'.",
    )

    culture_task = Task(
        description=f"Examine this conversation: {conversation}. Extract any places and provide cultural/general info. Output only if relevant, else 'No culture info'.",
        agent=culture_agent,
        expected_output="Cultural info string or 'No suggestion'.",
    )

    restaurant_task = Task(
        description=f"Examine this conversation: {conversation}. If eating/dining is mentioned, suggest top 3 restaurants for the place. Output only if relevant, else 'No restaurant suggestions'.",
        agent=restaurant_agent,
        expected_output="Restaurant list string or 'No suggestion'.",
    )

    summary_task = Task(
        description=f"Summarize this unread discussion: {conversation}. Keep it brief, highlight key topics and decisions.",
        agent=summarizer_agent,
        expected_output="A concise summary string.",
    )

    # Crew: Sequential execution for simplicity (agents run in order)
    crew = Crew(
        agents=[travel_agent, culture_agent, restaurant_agent, summarizer_agent],
        tasks=[travel_task, culture_task, restaurant_task, summary_task],
        verbose=2,  # For logging during dev
    )

    return crew