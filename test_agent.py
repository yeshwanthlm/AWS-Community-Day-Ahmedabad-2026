import asyncio
import os
from strands import Agent
from strands.agent.models import AgentInput

async def test():
    # Load module
    from debug_run import food_agent
    
    print("\n--- Testing Agent Async ---")
    print("You: I really love spicy food, especially Thai cuisines! But I have a peanut allergy.")
    
    # Try calling purely async
    result = await food_agent.invoke_async("I really love spicy food, especially Thai cuisines! But I have a peanut allergy.")
    print("Agent:", result.content[0]["text"])

if __name__ == "__main__":
    asyncio.run(test())
