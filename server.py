import asyncio
import uuid
import logging
import os
import contextvars
import jwt
import sqlite3
import json
from typing import Dict, Any, Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
import uvicorn
from pydantic import BaseModel, Field

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent, ImageContent, CreateMessageRequestParams
import mcp.types as types

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-server")

JWT_SECRET = "production-mcp-secret"
# Context variable to hold the user role for the current async request execution
user_role_var = contextvars.ContextVar("user_role", default="guest")

# --- Application State for Async Tasks ---
# In production, use Redis/Celery. For this demo, we use an in-memory dictionary.
background_tasks: Dict[str, Dict[str, Any]] = {}

# --- Server Initialization ---
app = FastAPI(title="Production MCP Demo")
mcp_server = Server("production-mcp-demo")
sse = SseServerTransport("/messages")

# --- Agent-Native Tool Contracts ---
# Using Pydantic creates strict, typed contract boundaries for predictable LLM behavior.

class StartTaskSchema(BaseModel):
    task_name: str = Field(description="The name or type of the background task to start.")
    complexity: int = Field(description="A number between 1 and 10 indicating how complex the task is.", ge=1, le=10)

class CheckTaskSchema(BaseModel):
    job_id: str = Field(description="The unique ID of the running background job.")

class SampleLlmSchema(BaseModel):
    data_to_analyze: str = Field(description="The raw text data that needs intelligent analysis by the client.")
    question: str = Field(description="What specific question to ask the client LLM about the data.")

class QueryCustomerSchema(BaseModel):
    customer_id: str = Field(description="The unique user ID to query the corporate database for.")

class LoginRequest(BaseModel):
    username: str
    role: str

# --- Tool Registrations ---

@mcp_server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """Exposes all available tools and their strict schemas."""
    return [
        Tool(
            name="start_long_running_task",
            description="Start an asynchronous background job. Returns a job_id immediately without waiting for completion.",
            inputSchema=StartTaskSchema.model_json_schema()
        ),
        Tool(
            name="check_task_status",
            description="Check the current status and progress of a background job.",
            inputSchema=CheckTaskSchema.model_json_schema()
        ),
        Tool(
            name="query_customer_context",
            description="Securely query the internal corporate database for a customer's details and active tickets.",
            inputSchema=QueryCustomerSchema.model_json_schema()
        ),
        Tool(
            name="sample_llm_intelligence",
            description="Requests the connecting client's LLM to analyze data securely on the client side without server credentials.",
            inputSchema=SampleLlmSchema.model_json_schema()
        )
    ]

async def _async_worker(job_id: str, complexity: int):
    """The actual long-running job executing in the background."""
    for i in range(1, complexity + 1):
        await asyncio.sleep(2)  # Simulate 2 seconds of work per complexity point
        progress = int((i / complexity) * 100)
        background_tasks[job_id]["progress"] = progress
        logger.info(f"Job {job_id} at {progress}%")
    
    background_tasks[job_id]["status"] = "completed"
    background_tasks[job_id]["result"] = f"Task successfully generated a highly optimized workflow in {complexity * 2} seconds."

@mcp_server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent | types.ImageContent]:
    """Execute tools strictly matching standard MCP types."""
    if not arguments:
        raise ValueError("Arguments are required inside the contract")

    if name == "start_long_running_task":
        # AUTHZ CHECK: Only admins can start background jobs
        current_role = user_role_var.get()
        if current_role != "admin":
            return [TextContent(type="text", text="AUTHZ ERROR: Permission Denied. You must have the 'admin' role to start background jobs. You are currently logged in as a 'guest'.")]

        job_id = f"job-{uuid.uuid4().hex[:8]}"
        
        background_tasks[job_id] = {
            "status": "running",
            "progress": 0,
            "task_name": args.task_name,
            "result": None
        }
        
        # Spawn the background task explicitly
        asyncio.create_task(_async_worker(job_id, args.complexity))
        
        return [TextContent(type="text", text=f"SUCCESS: Task '{args.task_name}' is now running. Keep this token to track progress: {job_id}")]

    elif name == "check_task_status":
        args = CheckTaskSchema(**arguments)
        job = background_tasks.get(args.job_id)
        if not job:
            return [TextContent(type="text", text=f"ERROR: Job ID {args.job_id} not found in queue.")]
            
        if job["status"] == "running":
            return [TextContent(type="text", text=f"Job {args.job_id} is running ({job['progress']}% complete). Check again shortly.")]
        else:
            return [TextContent(type="text", text=f"Job {args.job_id} completed. FINAL RESULT: {job['result']}")]
            
    elif name == "query_customer_context":
        args = QueryCustomerSchema(**arguments)
        
        # Connect to DB
        conn = sqlite3.connect("enterprise.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Fetch base customer DB
        cursor.execute("SELECT * FROM customers WHERE customer_id = ?", (args.customer_id,))
        customer = cursor.fetchone()
        
        if not customer:
            return [TextContent(type="text", text=f"ERROR: Customer {args.customer_id} not found in database.")]
            
        result_data = dict(customer)
        
        # Fetch open tickets
        cursor.execute("SELECT issue, status FROM support_tickets WHERE customer_id = ?", (args.customer_id,))
        result_data['tickets'] = [dict(row) for row in cursor.fetchall()]
        
        # AUTHZ ROLE-BASED ACCESS CONTROL
        # Only admins can see financial data (Lifetime value, CC)
        current_role = user_role_var.get()
        if current_role == "admin":
            cursor.execute("SELECT lifetime_value, credit_card_last_4, last_payment_date FROM financials WHERE customer_id = ?", (args.customer_id,))
            financials = cursor.fetchone()
            if financials:
                result_data['financials'] = dict(financials)
            logger.info(f"Admin request: Included highly sensitive financial data in MCP response for {args.customer_id}")
        else:
            result_data['financials'] = "[REDACTED - AUTHZ_ERROR: You do not have 'admin' privileges. Financial data masked.]"
            logger.info(f"Guest request: Masked sensitive financial data for {args.customer_id}")
            
        conn.close()
        
        return [TextContent(type="text", text=json.dumps(result_data, indent=2))]

    elif name == "sample_llm_intelligence":
        args = SampleLlmSchema(**arguments)
        
        # Fetch the active session from context
        session = mcp_server.request_context.session
        request_params = CreateMessageRequestParams(
            messages=[
                types.SamplingMessage(
                    role="user",
                    content=types.TextContent(
                        type="text", 
                        text=f"Please analyze this data: {args.data_to_analyze}\n\nQuestion: {args.question}"
                    )
                )
            ],
            maxTokens=1000
        )
        
        try:
            logger.info("Requesting client LLM sample...")
            sample_result = await session.create_message(request_params)
            
            # Extract TextContent from the client's response
            client_response_text = ""
            for content_block in sample_result.content:
                if content_block.type == "text":
                    client_response_text += content_block.text
                    
            return [TextContent(type="text", text=f"DELEGATED TO CLIENT LLM SUCCESS.\nClient's Intelligence Result:\n{client_response_text}")]
            
        except Exception as e:
            logger.error(f"Sampling failed: {e}")
            return [TextContent(type="text", text=f"ERROR: Failed to sample client LLM. Does this client support the createMessage capability? Details: {e}")]
        
    else:
        raise ValueError(f"Unknown tool requested: {name}")

# --- Transport and Auth Hooks ---

@app.middleware("http")
async def extract_jwt_middleware(request: Request, call_next):
    """
    Middleware that runs on every HTTP request.
    Extracts the Bearer JWT and injects the role into the async context.
    This ensures that when POST /messages triggers the MCP server, we know the user's role.
    """
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    elif "token" in request.query_params:
        token = request.query_params["token"]
        
    if token:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            user_role_var.set(payload.get("role", "guest"))
        except jwt.PyJWTError:
            pass # Invalid token, role defaults to guest

    return await call_next(request)

@app.post("/login")
async def login(credentials: LoginRequest):
    """
    Generates a cryptographically signed JWT.
    In real life this would check a password or communicate with an IdP.
    """
    payload = {
        "sub": credentials.username,
        "role": credentials.role,
    }
    encoded_jwt = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    return {"access_token": encoded_jwt}

@app.get("/sse")
async def handle_sse(request: Request):
    """
    Handle SSE connection with structured Authentication.
    Clients must pass a bearer JWT.
    """
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    elif "token" in request.query_params:
        token = request.query_params["token"]
        
    if not token:
        raise HTTPException(status_code=401, detail="Missing Authentication.")
    
    try:
        # Validate the JWT signature
        jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=403, detail="Invalid or expired JWT credentials.")
        
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await mcp_server.run(streams[0], streams[1], mcp_server.create_initialization_options())

@app.post("/messages")
async def handle_messages(request: Request):
    """Routing for subsequent messages in the SSE lifecycle."""
    await sse.handle_post_message(request.scope, request.receive, request._send)

# Ensure static folder exists and mount it
os.makedirs("static", exist_ok=True)
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
