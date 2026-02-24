import re

with open("movie-agent.ipynb", "r") as f:
    content = f.read()

# 1. Update top_k = 10 -> 3
content = content.replace('top_k=10', 'top_k=3 # Optimized context retrieval')

# 2. Add safe_invoke
safe_invoke_code = """
import time

def safe_invoke(agent, user_input, max_retries=3):
    \"\"\"Invokes the agent with rate limiting and fallback mechanisms.\"\"\"
    fallbacks = [
        "us.anthropic.claude-3-5-haiku-20241022-v1:0",
        "us.anthropic.claude-3-haiku-20240307-v1:0",
        "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
    ]
    
    time.sleep(1) # Client-side rate limit spacing
    
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

# 3. Update create_movie_agent
old_create = """def create_movie_agent(user_id: str, session_id: str):
    \"\"\"Create a movie recommendation agent with memory\"\"\"
    
    system_prompt = f\"\"\"You are a friendly movie recommendation assistant with excellent taste in films.

Your role:
- Help users discover movies they'll love
- Remember their preferences (genres, directors, actors, specific movies)
- Give personalized recommendations based on their taste
- Discuss movies, share interesting facts, and engage in movie conversations

Behavior:
- Have natural conversations about movies
- Don't give unsolicited recommendations - wait for the user to ask
- Focus on understanding their tastes first
- When they DO ask for recommendations, use everything you know about them

Today's date: {datetime.today().strftime('%Y-%m-%d')}
\"\"\"
    
    # Create memory hooks
    memory_hooks = MovieMemoryHookProvider(client, memory_id)
    
    # Create agent
    agent = Agent(
        name="MovieBuddy",
        model="us.anthropic.claude-sonnet-4-20250514-v1:0",
        system_prompt=system_prompt,
        hooks=[memory_hooks],
        tools=[search_movies],
        state={"actor_id": user_id, "session_id": session_id}
    )
    
    return agent"""

new_create = """def create_movie_agent(user_id: str, session_id: str):
    \"\"\"Create a movie recommendation agent with memory\"\"\"
    
    # Optimized: Shortened system prompt
    system_prompt = f\"\"\"You are a concise movie assistant. Remember user preferences and give tailored recommendations when asked. Date: {datetime.today().strftime('%Y-%m-%d')}\"\"\"
    
    # Create memory hooks
    memory_hooks = MovieMemoryHookProvider(client, memory_id)
    
    # Create agent
    # Optimized: Use Haiku for lower latency/cost and limit max tokens
    agent = Agent(
        name="MovieBuddy",
        model="us.anthropic.claude-3-5-haiku-20241022-v1:0",
        system_prompt=system_prompt,
        hooks=[memory_hooks],
        tools=[search_movies],
        max_tokens=600,
        state={"actor_id": user_id, "session_id": session_id}
    )
    
    return agent
""" + safe_invoke_code

if old_create in content:
    content = content.replace(old_create, new_create)
else:
    print("WARNING: Could not find old create_movie_agent method exact match")

# 4. Wrap movie_agent and new_movie_agent invocations
content = re.sub(r'(new_movie_agent|movie_agent)\("([^"]+)"\)', r'safe_invoke(\1, "\2")', content)

with open("movie-agent.ipynb", "w") as f:
    f.write(content)

print("Applied fixes to movie-agent.ipynb")
