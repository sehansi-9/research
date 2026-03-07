# OpenGIN Bot Python Backend

A stateful, agentic backend for querying temporal graph databases using LangGraph and FastAPI.

## Setup Instructions

1. **Prerequisites**:
   - Python 3.10+
   - pip

2. **Installation**:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Environment**:
   The `.env` file has been pre-configured with your development credentials.

4. **Run the Server**:
   ```bash
   python -m app.main
   ```
   The server will start at `http://0.0.0.0:8000`.

## Key Features
- **Planning Agent**: Automatically breaks down complex temporal queries into logical steps.
- **Stateful Memory**: Uses `MemorySaver` to track conversation history per `session_id`.
- **Temporal Reasoning**: Optimized prompts and tools for interval arithmetic on graph edges.
- **Structured Outputs**: Uses Pydantic for reliable tool calling and planning.
