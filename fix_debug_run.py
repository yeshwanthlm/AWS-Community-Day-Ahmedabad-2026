import re

with open("debug_run.py", "r") as f:
    content = f.read()

# 1. Update top_k
content = content.replace('top_k=10', 'top_k=3 # Optimized context retrieval')

# 2. Add safe_invoke
safe_invoke_code = """
import time

def safe_invoke(agent, user_input, max_retries=3):
    \"\"\"Invokes the agent with client-side rate limiting and fallback mechanisms.\"\"\"
    fallbacks = [
        "us.anthropic.claude-3-5-haiku-20241022-v1:0",
        "us.anthropic.claude-3-haiku-20240307-v1:0",
        "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
    ]
    
    time.sleep(1) # Client-side rate limit
    
    for attempt in range(max_retries):
        try:
            return agent(user_input)
        except Exception as e:
            error_str = str(e).lower()
            if "throttl" in error_str or "429" in error_str or "rate" in error_str:
                logger.warning(f"⚠️ Throttled (Attempt {attempt+1}/{max_retries}). Error: {str(e)[:50]}")
                if attempt < len(fallbacks):
                    fallback_model = fallbacks[attempt]
                    logger.info(f"🔄 Switching to fallback model: {fallback_model}")
                    agent.model = fallback_model
                    time.sleep(2 ** attempt)
                else:
                    raise e
            else:
                raise e
"""

old_create = """def create_food_agent(user_id: str, session_id: str):
    \"\"\"Create a food recommendation agent with memory\"\"\"
    
    system_prompt = f\"\"\"You are a friendly and knowledgeable food recommendation assistant.

Your role:
- Help users discover new foods, cuisines, recipes, and dining experiences they'll love
- Remember their food preferences (cuisines, dietary restrictions, favorite restaurants, liked/disliked ingredients)
- Give personalized food recommendations based on their taste
- Discuss recipes, cooking tips, and share interesting culinary facts

Behavior:
- Have natural conversations about food and dining
- Don't give unsolicited recommendations - wait for the user to ask or show interest
- Focus on understanding their tastes, dietary needs, and restrictions first
- When they DO ask for recommendations, use everything you know about them to provide tailored suggestions

Today's date: {datetime.today().strftime('%Y-%m-%d')}
\"\"\"
    
    # Create memory hooks
    memory_hooks = FoodMemoryHookProvider(client, memory_id)
    
    # Create agent
    agent = Agent(
        name="FoodieBuddy",
        model="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        system_prompt=system_prompt,
        hooks=[memory_hooks],
        tools=[search_food],
        state={"actor_id": user_id, "session_id": session_id}
    )
    
    return agent"""

new_create = """def create_food_agent(user_id: str, session_id: str):
    \"\"\"Create a food recommendation agent with memory\"\"\"
    
    # Optimized: Shortened system prompt
    system_prompt = f\"\"\"You are a concise food assistant. Help users discover new foods & remember their preferences. Given today's date: {datetime.today().strftime('%Y-%m-%d')}.\"\"\"
    
    memory_hooks = FoodMemoryHookProvider(client, memory_id)
    
    # Create agent
    agent = Agent(
        name="FoodieBuddy",
        # Optimized: Used a smaller model (Haiku) instead of Sonnet
        model="us.anthropic.claude-3-5-haiku-20241022-v1:0",
        system_prompt=system_prompt,
        hooks=[memory_hooks],
        tools=[search_food],
        # Optimized: Limited max_tokens
        max_tokens=600,
        state={"actor_id": user_id, "session_id": session_id}
    )
    return agent
""" + safe_invoke_code

content = content.replace(old_create, new_create)

# 3. Replace calls
content = re.sub(r'food_agent\("([^"]+)"\)', r'safe_invoke(food_agent, "\1")', content)

with open("debug_run.py", "w") as f:
    f.write(content)

print("Applied fixes to debug_run.py")
