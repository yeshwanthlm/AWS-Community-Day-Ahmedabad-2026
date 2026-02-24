

# ---

import os
import logging
import time
from datetime import datetime
from botocore.exceptions import ClientError

from strands import Agent, tool
from strands.hooks import (
    AgentInitializedEvent, 
    MessageAddedEvent, 
    AfterInvocationEvent,
    HookProvider, 
    HookRegistry
)
from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore.memory.constants import StrategyType

# ---

# Setup logging to see what the agent is doing
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("food-agent")

# Configuration
REGION = os.getenv('AWS_REGION', 'us-east-1')
USER_ID = "food-lover-001"  # User ID for short and long term memory using AWS Agent Core
SESSION_ID = f"food_chat_{datetime.now().strftime('%Y%m%d%H%M%S')}"

print(f"Region: {REGION}")
print(f"User ID: {USER_ID}")
print(f"Session ID: {SESSION_ID}")

# ---

# Initialize Memory Client
client = MemoryClient(region_name=REGION)
memory_name = "FoodAgentMemory"
memory_id = None

# Define memory strategy for food preferences
# Everything goes to short term memory first, then Agent Core moves preferences to long term memory (one time task)
strategies = [
    {
        StrategyType.USER_PREFERENCE.value: {
            "name": "FoodPreferences",
            "description": "Captures food preferences including cuisines, dietary restrictions, favorite dishes, and specific foods the user likes or dislikes",
            "namespaces": ["user/{actorId}/food_preferences"]
        }
    }
]

try:
    # Create memory resource
    memory = client.create_memory_and_wait(
        name=memory_name,
        strategies=strategies,
        description="Memory for food recommendation agent - stores user food preferences",
        event_expiry_days=7,  # Keep preferences for a week
        max_wait=300,
        poll_interval=10
    )
    memory_id = memory['id']
    logger.info(f"✅ Created memory: {memory_id}")
    
except ClientError as e:
    if e.response['Error']['Code'] == 'ValidationException' and "already exists" in str(e):
        # Memory already exists - retrieve its ID
        memories = client.list_memories()
        memory_id = next((m['id'] for m in memories if m['id'].startswith(memory_name)), None)
        logger.info(f"✅ Memory already exists. Using: {memory_id}")
    else:
        raise e

print(f"\n📝 Save this memory_id for future sessions: {memory_id}")

# ---

class FoodMemoryHookProvider(HookProvider):
    """Automatic memory management for food agent"""
    
    def __init__(self, memory_client: MemoryClient, memory_id: str):
        self.memory_client = memory_client
        self.memory_id = memory_id
    
    def on_agent_initialized(self, event: AgentInitializedEvent):
        """Load food preferences when agent starts"""
        try:
            actor_id = event.agent.state.get("actor_id")
            if not actor_id:
                logger.warning("Missing actor_id in agent state")
                return
            
            namespace = f"user/{actor_id}/food_preferences"
            
            # Retrieve stored food preferences (querying food preferences genres directory)
            preferences = self.memory_client.retrieve_memories(
                memory_id=self.memory_id,
                namespace=namespace,
                query="food preferences cuisines dietary restrictions favorites",
                top_k=3 # Optimized context retrieval
            )
            
            if preferences:
                # Format preferences for context
                pref_texts = []
                for pref in preferences:
                    if isinstance(pref, dict):
                        content = pref.get('content', {})
                        if isinstance(content, dict):
                            text = content.get('text', '').strip()
                            if text:
                                pref_texts.append(f"- {text}")
                
                if pref_texts:
                    context = "\n".join(pref_texts)
                    event.agent.system_prompt += f"\n\n## User's Food Preferences (from previous conversations):\n{context}"
                    logger.info(f"✅ Loaded {len(pref_texts)} food preferences")
            else:
                logger.info("No previous food preferences found - starting fresh!")
                    
        except Exception as e:
            logger.error(f"Error loading preferences: {e}")
    
    def on_after_invocation(self, event: AfterInvocationEvent):
        """Save conversation after each interaction"""
        try:
            messages = event.agent.messages
            # Save to memory after two interactions
            if len(messages) < 2:
                return
                
            actor_id = event.agent.state.get("actor_id")
            session_id = event.agent.state.get("session_id")
            
            if not actor_id or not session_id:
                logger.warning("Missing actor_id or session_id")
                return
            
            # Get the last user message and assistant response
            user_msg = None
            assistant_msg = None
            
            for msg in reversed(messages):
                if msg["role"] == "assistant" and not assistant_msg:
                    content = msg.get("content", [])
                    if content and isinstance(content[0], dict) and "text" in content[0]:
                        assistant_msg = content[0]["text"]
                elif msg["role"] == "user" and not user_msg:
                    content = msg.get("content", [])
                    if content and isinstance(content[0], dict) and "text" in content[0]:
                        if "toolResult" not in content[0]:
                            user_msg = content[0]["text"]
                            break
            
            if user_msg and assistant_msg:
                # Save the conversation turn to short term memory
                self.memory_client.create_event(
                    memory_id=self.memory_id,
                    actor_id=actor_id,
                    session_id=session_id,
                    messages=[(user_msg, "USER"), (assistant_msg, "ASSISTANT")]
                )
                logger.info("💾 Saved conversation to memory")
                
        except Exception as e:
            logger.error(f"Error saving conversation: {e}")
    
    def register_hooks(self, registry: HookRegistry):
        registry.add_callback(AgentInitializedEvent, self.on_agent_initialized)
        registry.add_callback(AfterInvocationEvent, self.on_after_invocation)
        logger.info("✅ Food memory hooks registered")

# ---

from ddgs import DDGS
from ddgs.exceptions import DDGSException, RatelimitException

@tool
def search_food(query: str, max_results: int = 5) -> str:
    """Search for food information, recipes, cuisines, or restaurant recommendations.
    
    Args:
        query: Search query about food (e.g., \"best authentic italian pasta recipes\")
        max_results: Maximum number of results to return
    
    Returns:
        Search results with food information
    """
    try:
        results = DDGS().text(f"{query} food recipe restaurant", region="us-en", max_results=max_results)
        if not results:
            return "No results found."
        
        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(f"{i}. {r.get('title', 'No title')}\n   {r.get('body', '')}")
        
        return "\n\n".join(formatted)
    except RatelimitException:
        return "Rate limit reached. Please try again later."
    except Exception as e:
        return f"Search error: {str(e)}"

logger.info("✅ Food search tool ready")

# ---

def create_food_agent(user_id: str, session_id: str):
    """Create a food recommendation agent with memory"""
    
    # Optimized: Shortened system prompt
    system_prompt = f"""You are a concise food assistant. Help users discover new foods & remember their preferences. Given today's date: {datetime.today().strftime('%Y-%m-%d')}."""
    
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

import time

def safe_invoke(agent, user_input, max_retries=3):
    """Invokes the agent with client-side rate limiting and fallback mechanisms."""
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


# Create the agent
food_agent = create_food_agent(USER_ID, SESSION_ID)
logger.info("✅ Food agent created with memory!")

# ---

# Test the agent - logging is already enabled in the configuration cell
print("You: I really love spicy food, especially Thai cuisines! But I have a peanut allergy.")
print("\nAgent: ", end="")
safe_invoke(food_agent, "I really love spicy food, especially Thai cuisines! But I have a peanut allergy.")

# ---

# Test the agent - logging is already enabled in the configuration cell
print("You: I really love spicy food, especially Thai cuisines! But I have a peanut allergy.")
print("\nAgent: ", end="")
safe_invoke(food_agent, "I really love spicy food, especially Thai cuisines! But I have a peanut allergy.")

print("\nYou: Can you give me a recommendation for tonight?")
print("\nAgent: ", end="")
safe_invoke(food_agent, "Can you give me a recommendation for tonight?")

print(f"\nSession ID: {SESSION_ID}")

# Check SHORT-TERM MEMORY (Raw Conversations)
print("\nSHORT-TERM MEMORY (Raw Conversations)")
print("=" * 60)
events = client.list_events(memory_id=memory_id, actor_id=USER_ID, session_id=SESSION_ID)
if events:
    for i, event in enumerate(events, 1):
        print(f"\n--- Event {i} ---")
        print(event)
else:
    print("No events found. Memory ID:", memory_id)

# Check LONG-TERM MEMORY (Background Processed Preferences)
print("\nLONG-TERM MEMORY PREFERENCES:")
print("=" * 50)
try:
    preferences = client.retrieve_memories(
        memory_id=memory_id,
        namespace=f"user/{USER_ID}/food_preferences",
        query="food preferences cuisines dietary restrictions favorites",
        top_k=3 # Optimized context retrieval
    )

    if preferences:
        for i, pref in enumerate(preferences, 1):
            if isinstance(pref, dict):
                content = pref.get('content', {})
                if isinstance(content, dict):
                    text = content.get('text', '')
                    if text:
                        print(f"{i}. {text}")
    else:
        print("No preferences extracted yet. It could take 30-60 seconds to process in the background.")
except Exception as e:
    print(f"Could not retrieve from long-term memory: {e}")

# ---

