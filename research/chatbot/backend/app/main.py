import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from app.graph.router import app_graph

app = FastAPI(title="OpenGIN Bot Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    question: str
    session_id: str

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        # thread_id for state persistence
        config = {"configurable": {"thread_id": request.session_id}}
        
        # Initial state
        initial_state = {
            "messages": [HumanMessage(content=request.question)],
            "entity_cache": {}
        }
        
        # Invoke the graph with a recursion limit to prevent infinite loops
        final_state = await app_graph.ainvoke(initial_state, config=config, recursion_limit=15)
        
        # The last message from the agent is the answer
        assistant_message = final_state["messages"][-1]
        
        return {
            "success": True,
            "answer": assistant_message.content,
            "session_id": request.session_id
        }
    except Exception as e:
        import traceback
        print(f"❌ ERROR in /chat: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=9000, reload=True)
