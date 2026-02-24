import json

with open("food-agent.ipynb", "r") as f:
    nb = json.load(f)

# Cell 4: Update FoodMemoryHookProvider
cell4_code = "".join(nb["cells"][4]["source"])
cell4_code = cell4_code.replace('query="food preferences cuisines dietary restrictions favorites",\n                top_k=10', 'query="food preferences cuisine",\n                top_k=3 # Optimized: Removed unnecessary context by lowering top_k')
nb["cells"][4]["source"] = [line + "\n" if not line.endswith("\n") else line for line in cell4_code.split("\n")[:-1]]

# Cell 6: Update create_food_agent
cell6_new_code = """def create_food_agent(user_id: str, session_id: str):
    \"\"\"Create a food recommendation agent with memory\"\"\"
    
    # Optimized: Shortened system prompt
    system_prompt = \"\"\"You are a concise food assistant. Help users discover new foods & remember their preferences. Given today's date: {datetime.today().strftime('%Y-%m-%d')}.\"\"\"
    
    memory_hooks = FoodMemoryHookProvider(client, memory_id)
    
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

# Create the agent
food_agent = create_food_agent(USER_ID, SESSION_ID)
logger.info("✅ Food agent created with memory!")

# Optimized: Client-side rate limiting and fallback
import time

def safe_invoke(agent, user_input, max_retries=3):
    \"\"\"Invokes the agent with rate limiting and fallback mechanisms.\"\"\"
    fallbacks = [
        "us.anthropic.claude-3-5-haiku-20241022-v1:0",
        "us.anthropic.claude-3-haiku-20240307-v1:0",
        "us.anthropic.claude-3-5-sonnet-20241022-v2:0" # Fallback to Sonnet if Haiku fails
    ]
    
    # Client-side rate limit: space out requests
    time.sleep(1) 
    
    for attempt in range(max_retries):
        try:
            return agent(user_input)
        except Exception as e:
            error_str = str(e).lower()
            if "throttl" in error_str or "429" in error_str or "rate" in error_str:
                logger.warning(f"⚠️ Throttled (Attempt {attempt+1}/{max_retries}). Error: {str(e)[:50]}")
                
                if attempt < len(fallbacks):
                    fallback_model = fallbacks[attempt]
                    # Simulate switching regions via cross-region inference profiles or just changing model
                    logger.info(f"🔄 Switching to fallback model: {fallback_model}")
                    agent.model = fallback_model
                    
                    sleep_time = 2 ** attempt
                    logger.info(f"⏳ Sleeping for {sleep_time}s...")
                    time.sleep(sleep_time)
                else:
                    raise e
            else:
                raise e
"""
nb["cells"][6]["source"] = [line + "\n" if i < len(cell6_new_code.split('\n')) - 1 else line for i, line in enumerate(cell6_new_code.split('\n'))]

# Cell 7: Update agent call
cell7_code = "".join(nb["cells"][7]["source"])
cell7_code = cell7_code.replace('food_agent("I really', 'safe_invoke(food_agent, "I really')
nb["cells"][7]["source"] = [line + "\n" if not line.endswith("\n") else line for line in cell7_code.split("\n")[:-1]]

# Cell 8: Update agent calls and retrieve memory block
cell8_code = "".join(nb["cells"][8]["source"])
cell8_code = cell8_code.replace('food_agent("I really', 'safe_invoke(food_agent, "I really')
cell8_code = cell8_code.replace('food_agent("Can you give me', 'safe_invoke(food_agent, "Can you give me')
cell8_code = cell8_code.replace('top_k=10', 'top_k=3 # Optimized context retrieval')
nb["cells"][8]["source"] = [line + "\n" if not line.endswith("\n") else line for line in cell8_code.split("\n")[:-1]]

with open("food-agent.ipynb", "w") as f:
    json.dump(nb, f, indent=1)

print("Modifications done and saved to food-agent.ipynb")
