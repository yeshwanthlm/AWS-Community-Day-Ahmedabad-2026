import os
import logging
from datetime import datetime
from botocore.exceptions import ClientError

from strands import Agent, tool
from strands.hooks import (
    AgentInitializedEvent, 
    AfterInvocationEvent,
    HookProvider, 
    HookRegistry
)
from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore.memory.constants import StrategyType
from bedrock_agentcore.identity.auth import requires_iam_access_token

from ddgs import DDGS
from ddgs.exceptions import RatelimitException

# ==========================================
# Configuration & Setup
# ==========================================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("food_agent_runtime")

REGION = os.getenv('AWS_REGION', 'us-east-1')
client = MemoryClient(region_name=REGION)
MEMORY_NAME = "FoodAgentMemory"

def get_or_create_memory_id() -> str:
    """Initialize or retrieve the Bedrock AgentCore Memory ID."""
    strategies = [
        {
            StrategyType.USER_PREFERENCE.value: {
                "name": "FoodPreferences",
                "description": "Captures food preferences including cuisines, dietary restrictions, favorite dishes",
                "namespaces": ["user/{actorId}/food_preferences"]
            }
        }
    ]

    try:
        memory = client.create_memory_and_wait(
            name=MEMORY_NAME,
            strategies=strategies,
            description="Memory for food recommendation agent",
            event_expiry_days=7,
            max_wait=300,
            poll_interval=10
        )
        logger.info(f"Created memory: {memory['id']}")
        return memory['id']
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ValidationException' and "already exists" in str(e):
            memories = client.list_memories()
            memory_id = next((m['id'] for m in memories if m['id'].startswith(MEMORY_NAME)), None)
            if memory_id:
                logger.info(f"Memory already exists. Using: {memory_id}")
                return memory_id
            raise ValueError(f"Memory {MEMORY_NAME} exists but ID not found in list_memories()")
        else:
            raise e

# Initialize global memory ID for the runtime
MEMORY_ID = get_or_create_memory_id()


# ==========================================
# Memory Hook Provider
# ==========================================
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
                logger.warning("Missing actor_id in agent state. Cannot load preferences.")
                return
            
            namespace = f"user/{actor_id}/food_preferences"
            preferences = self.memory_client.retrieve_memories(
                memory_id=self.memory_id,
                namespace=namespace,
                query="food preferences cuisines dietary restrictions favorites",
                top_k=5
            )
            
            if preferences:
                pref_texts = []
                for pref in preferences:
                    if isinstance(pref, dict):
                        content = pref.get('content', {})
                        if isinstance(content, dict):
                            text = content.get('text', '').strip()
                            if text:
                                pref_texts.append(f"- {text}")
                
                if pref_texts:
                    context = "\\n".join(pref_texts)
                    event.agent.system_prompt += f"\\n\\n## User's Food Preferences:\\n{context}"
                    logger.info(f"Loaded {len(pref_texts)} food preferences for user: {actor_id}")
                    
        except Exception as e:
            logger.error(f"Error loading preferences: {e}")
    
    def on_after_invocation(self, event: AfterInvocationEvent):
        """Save conversation after each interaction"""
        try:
            messages = event.agent.messages
            if len(messages) < 2:
                return
                
            actor_id = event.agent.state.get("actor_id")
            session_id = event.agent.state.get("session_id")
            
            if not actor_id or not session_id:
                logger.warning("Missing actor_id or session_id. Cannot save conversation.")
                return
            
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
                self.memory_client.create_event(
                    memory_id=self.memory_id,
                    actor_id=actor_id,
                    session_id=session_id,
                    messages=[(user_msg, "USER"), (assistant_msg, "ASSISTANT")]
                )
                logger.debug(f"Saved conversation event for session: {session_id}")
                
        except Exception as e:
            logger.error(f"Error saving conversation: {e}")
    
    def register_hooks(self, registry: HookRegistry):
        registry.add_callback(AgentInitializedEvent, self.on_agent_initialized)
        registry.add_callback(AfterInvocationEvent, self.on_after_invocation)
        logger.info("Food memory hooks registered")


# ==========================================
# Agent Tools (Search & M2M Identity Mock)
# ==========================================
@tool
def search_food(query: str, max_results: int = 5) -> str:
    """Search for food information, recipes, cuisines, or restaurant recommendations.
    
    Args:
        query: Search query about food 
        max_results: Maximum number of results to return
    """
    try:
        results = DDGS().text(f"{query} food recipe restaurant", region="us-en", max_results=max_results)
        if not results:
            return "No results found."
        
        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(f"{i}. {r.get('title', 'No title')}\\n   {r.get('body', '')}")
        
        return "\\n\\n".join(formatted)
    except RatelimitException:
        return "Rate limit reached. Please try again later."
    except Exception as e:
        return f"Search error: {str(e)}"

@tool
@requires_iam_access_token(
    audience=["https://api.example-restaurant.com/v1/*"], 
    signing_algorithm="ES384",
    duration_seconds=300
)
async def book_restaurant(restaurant_id: str, date: str, time: str, guests: int, *, access_token: str) -> str:
    """Book a table at a restaurant. Requires an IAM Access Token injected by AgentCore Identity.
    
    Args:
        restaurant_id: The ID of the restaurant.
        date: The date for the booking (YYYY-MM-DD).
        time: The time for the booking (HH:MM).
        guests: The number of guests.
        access_token: The signed JWT access token injected by the decorator. (DO NOT PASS THIS)
    """
    logger.info(f"[Identity] Injected AWS STS JWT Access Token (length: {len(access_token)}).")
    logger.info(f"[Policy Gateway] Verifying token & identity for booking at {restaurant_id}...")
    return f"Successfully booked {guests} guests at {restaurant_id} for {date} at {time} using IAM JWT authentication."


# ==========================================
# Core Agent Creator
# ==========================================
def create_food_agent(user_id: str, session_id: str) -> Agent:
    """
    Create a food recommendation agent integrated with AgentCore Memory and Tools.
    This factory function is typically invoked per-request context in runtime environments.
    """
    
    system_prompt = f"""You are a concise food assistant. Help users discover new foods & remember their preferences. 
You can search the web for recipes using `search_food` and book restaurants securely using `book_restaurant`. 
Date: {datetime.today().strftime("%Y-%m-%d")}"""
    
    memory_hooks = FoodMemoryHookProvider(client, MEMORY_ID)
    
    agent = Agent(
        name="FoodieBuddy",
        model="us.anthropic.claude-3-5-haiku-20241022-v1:0",
        system_prompt=system_prompt,
        hooks=[memory_hooks],
        tools=[search_food, book_restaurant],
        state={
            "actor_id": user_id, 
            "session_id": session_id
        }
    )
    
    logger.info(f"Agent instantiated for User: {user_id} | Session: {session_id}")
    return agent


if __name__ == "__main__":
    import asyncio
    
    # Simple Local Test Execution
    async def main():
        user_id = "food-lover-001"
        session_id = f"food_chat_runtime_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        agent = create_food_agent(user_id, session_id)
        
        prompt = "Hi! I'm hungry. Can you recommend some Thai food and try booking a table for me at 'thai-palace-123' for tonight at 8 PM for 2 guests? Keep in mind I have a peanut allergy!"
        print(f"\\nUser: {prompt}")
        print("Agent Computing...")
        
        # Invoke Agent
        response = await agent.invoke_async(prompt)
        print(f"\\nAgent: {response.output}")
        
    asyncio.run(main())
