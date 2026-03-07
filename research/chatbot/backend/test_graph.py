import asyncio
from app.graph.router import app_graph
from langchain_core.messages import HumanMessage
import os

async def test():
    print("Testing LangGraph...")
    config = {"configurable": {"thread_id": "test_session"}}
    initial_state = {
        "messages": [HumanMessage(content="Who are the persons appointed to the tourism related ministries")],
        "entity_cache": {}
    }
    try:
        final_state = await app_graph.ainvoke(initial_state, config=config)
        print("Success!")
        print(f"Answer: {final_state['messages'][-1].content}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
