from typing import TypedDict, Annotated, List, Optional
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    # Conversations messages
    messages: Annotated[List[BaseMessage], add_messages]
    # entity cache for efficiency
    entity_cache: dict
    # knowledge pool for long-term memory (No operator.add to allow resetting)
    facts: List[str]
