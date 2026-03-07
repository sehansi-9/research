from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from app.graph.state import AgentState
from app.graph.nodes.agent import call_model
from app.graph.nodes.tools import tools

# Logic to determine if we continue or end
def should_continue(state: AgentState):
    messages = state['messages']
    last_message = messages[-1]
    
    # If the LLM called a tool, we continue to the tools node
    if last_message.tool_calls:
        return "continue"
    
    # Otherwise, we finish
    return "end"

# Initialize Graph
workflow = StateGraph(AgentState)

# Define Nodes
workflow.add_node("agent", call_model)
workflow.add_node("tools", ToolNode(tools))

# Build graph
workflow.set_entry_point("agent")

workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "continue": "tools",
        "end": END
    }
)

# After tools are called, we go back to the agent to process the results
workflow.add_edge("tools", "agent")

# Compile with memory for conversation persistence
app_graph = workflow.compile(checkpointer=MemorySaver())
