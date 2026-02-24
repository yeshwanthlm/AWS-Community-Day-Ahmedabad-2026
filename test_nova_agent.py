import asyncio
import sys
import logging
from debug_run import create_food_agent, USER_ID, SESSION_ID

logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

# Explicitly create an agent with the Nova model
agent = create_food_agent(USER_ID, SESSION_ID)

# Ensure the model is correct (in case old code is loaded)
agent.model = "amazon.nova-pro-v1:0"

print("\n--- Testing Agent with Nova ---")
result = agent("I really love spicy food, especially Thai cuisines! But I have a peanut allergy.")
print("Agent Response:", result)
