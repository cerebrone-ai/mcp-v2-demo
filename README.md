# Production-Ready MCP Server Demo

This repository contains a demonstration of a **Production-grade Model Context Protocol (MCP)** server built in Python using FastAPI, along with a custom Vanilla JavaScript browser client to visualize its features.

Built following the **v2025-11 MCP standard update**, this project moves beyond simple "dummy" JSON responses and implements the advanced architectural patterns required for real-world Agent systems.

## Key Features Demonstrated

1. **Long-Running Async Workflows**
   - True asynchronous background `asyncio` task execution.
   - The server immediately returns a `Job ID` instead of blocking the LLM for minutes.
   - Separate state-polling tool (`check_task_status`) to track background progress dynamically.

2. **Server-Side Tool Sampling**
   - Uses the MCP `session.create_message()` capability.
   - The server delegates intelligence tasks *back* to the connected client rather than relying on its own hardcoded LLM API keys.

3. **Structured Authentication (AuthZ Gateway)**
   - Uses HTTP Server-Sent Events (SSE) instead of basic `stdio`.
   - Enforces a Bearer Token connection requirement, blocking unauthorized LLMs/Agents from executing tools.

4. **Agent-Native contracts**
   - Strict `Pydantic` schemas for robust tool input validation.
   - Responses utilize the standard `mcp.types.TextContent` envelope to ensure perfect interoperability across any MCP-compliant framework (LangChain, LlamaIndex, Claude Desktop).

## Project Structure

- `server.py`: The core FastAPI Server and MCP tool definitions.
- `static/index.html`: The HTML structure for the web client.
- `static/style.css`: Modern UI styling.
- `static/app.js`: The application logic binding the UI to the MCP client.
- `static/simple_mcp_client.js`: A lightweight, vanilla Javascript implementation of the MCP SSE transport and JSON-RPC protocol.

## Installation & Running Locally

### Prerequisites
- Python 3.10+
- A modern web browser

### 1. Setup the Environment

Clone the repository and navigate into it:
```bash
git clone https://github.com/cerebrone-ai/mcp-v2-demo.git
cd mcp-v2-demo
```

Create a virtual environment and activate it:
```bash
# macOS/Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 2. Install Dependencies

Install the required Python packages:
```bash
pip install mcp fastapi uvicorn pydantic sse-starlette anyio
```

*Optionally, you can save these to a `requirements.txt`:*
```bash
pip freeze > requirements.txt
```

### 3. Run the Server

Start the FastAPI application using Uvicorn:
```bash
python server.py
# Or: uvicorn server:app --host 0.0.0.0 --port 8000
```
*The server will start on `http://localhost:8000`.*

### 4. Experience the Demo

1. Open your web browser and navigate to [http://localhost:8000](http://localhost:8000).
2. The UI will present a **Secure Gateway**. The default Bearer token (`super-secret-admin-token`) is pre-filled.
3. Click **Connect over SSE**.
4. The client will establish a session, complete the protocol handshake, and retrieve the **Agent-Native Contracts** (Tools).
5. Click on a tool in the sidebar (like `start_long_running_task`) and click **Invoke via MCP** to test the specific feature!

---
*Created as an exploration of the v2025-11 Model Context Protocol update.*
