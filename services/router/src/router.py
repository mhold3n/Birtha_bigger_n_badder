"""Agent router with MCP client integration."""

import asyncio
import json
from typing import Any, Dict, List, Optional

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from httpx import AsyncClient, HTTPError
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from .config import settings
from .mcp_client import MCPClient, mcp_client

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Global clients
redis_client: Optional[Redis] = None
api_client: Optional[AsyncClient] = None

app = FastAPI(
    title="Agent Router",
    description="Router service with MCP tool integration",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TaskRequest(BaseModel):
    """Task request model."""

    prompt: str = Field(..., description="User prompt")
    system: str = Field(
        default="You are a helpful coding agent.",
        description="System prompt",
    )
    model: str = Field(
        default="mistralai/Mistral-7B-Instruct-v0.3",
        description="Model to use",
    )
    tools: Optional[List[str]] = Field(
        default=None,
        description="List of MCP tools to use",
    )
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)


class TaskResponse(BaseModel):
    """Task response model."""

    task_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    tools_used: List[str] = Field(default_factory=list)
    execution_time: float


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    timestamp: float
    version: str
    services: Dict[str, str]
    mcp_servers: Dict[str, bool]


@app.on_event("startup")
async def startup_event():
    """Initialize clients on startup."""
    global redis_client, api_client
    
    logger.info("Starting Agent Router", version="0.1.0")
    
    # Initialize Redis client
    try:
        redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
        await redis_client.ping()
        logger.info("Connected to Redis", url=settings.redis_url)
    except Exception as e:
        logger.error("Failed to connect to Redis", error=str(e))
        redis_client = None
    
    # Initialize API client
    try:
        api_client = AsyncClient(
            base_url=settings.api_url,
            timeout=settings.request_timeout,
        )
        logger.info("Initialized API client", base_url=settings.api_url)
    except Exception as e:
        logger.error("Failed to initialize API client", error=str(e))
        api_client = None


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global redis_client, api_client
    
    if redis_client:
        await redis_client.close()
        logger.info("Closed Redis connection")
    
    if api_client:
        await api_client.aclose()
        logger.info("Closed API client connection")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    services = {}
    
    # Check Redis
    if redis_client:
        try:
            await redis_client.ping()
            services["redis"] = "healthy"
        except Exception:
            services["redis"] = "unhealthy"
    else:
        services["redis"] = "not_configured"
    
    # Check API client
    if api_client:
        try:
            response = await api_client.get("/health")
            services["api"] = "healthy" if response.status_code == 200 else "unhealthy"
        except Exception:
            services["api"] = "unhealthy"
    else:
        services["api"] = "not_configured"
    
    # Check MCP servers
    mcp_servers = {}
    async with MCPClient() as mcp:
        mcp_servers = await mcp.health_check_all()
    
    return HealthResponse(
        status="healthy" if all(s == "healthy" for s in services.values()) else "degraded",
        timestamp=asyncio.get_event_loop().time(),
        version="0.1.0",
        services=services,
        mcp_servers=mcp_servers,
    )


@app.get("/")
async def root():
    """Root endpoint with router information."""
    return {
        "name": "Agent Router",
        "version": "0.1.0",
        "description": "Router service with MCP tool integration",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/mcp/servers")
async def list_mcp_servers():
    """List all configured MCP servers."""
    async with MCPClient() as mcp:
        servers = await mcp.list_servers()
        return {
            "servers": [
                {
                    "name": server.name,
                    "type": server.server_type,
                    "url": server.url,
                    "config": server.config,
                }
                for server in servers
            ]
        }


@app.get("/mcp/servers/{server_name}/tools")
async def get_server_tools(server_name: str):
    """Get available tools from an MCP server."""
    try:
        async with MCPClient() as mcp:
            tools = await mcp.get_server_tools(server_name)
            return {"server": server_name, "tools": tools}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(
            "Failed to get tools from MCP server",
            server=server_name,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"Failed to get tools: {str(e)}")


@app.post("/mcp/servers/{server_name}/call")
async def call_mcp_tool(
    server_name: str,
    tool_name: str,
    arguments: Optional[Dict[str, Any]] = None,
):
    """Call a tool on an MCP server."""
    try:
        async with MCPClient() as mcp:
            result = await mcp.call_tool(server_name, tool_name, arguments)
            return {
                "server": server_name,
                "tool": tool_name,
                "arguments": arguments,
                "result": result,
            }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(
            "Failed to call MCP tool",
            server=server_name,
            tool=tool_name,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"Failed to call tool: {str(e)}")


@app.post("/route", response_model=TaskResponse)
async def route_task(request: TaskRequest):
    """Route a task through the agent system with MCP tool integration."""
    if not api_client:
        raise HTTPException(
            status_code=503,
            detail="API client not available",
        )
    
    start_time = asyncio.get_event_loop().time()
    task_id = f"task_{int(start_time)}"
    tools_used = []
    
    try:
        logger.info(
            "Processing task",
            task_id=task_id,
            prompt_length=len(request.prompt),
            tools=request.tools,
        )
        
        # Prepare messages
        messages = [
            {"role": "system", "content": request.system},
            {"role": "user", "content": request.prompt},
        ]
        
        # If tools are specified, try to use them
        if request.tools:
            async with MCPClient() as mcp:
                for tool_spec in request.tools:
                    try:
                        # Parse tool specification (format: "server:tool" or just "tool")
                        if ":" in tool_spec:
                            server_name, tool_name = tool_spec.split(":", 1)
                        else:
                            # Default to first available server
                            servers = await mcp.list_servers()
                            if not servers:
                                continue
                            server_name = servers[0].name
                            tool_name = tool_spec
                        
                        # Call the MCP tool
                        tool_result = await mcp.call_tool(
                            server_name,
                            tool_name,
                            {"query": request.prompt},
                        )
                        
                        # Add tool result to messages
                        messages.append({
                            "role": "assistant",
                            "content": f"Tool result from {server_name}:{tool_name}: {json.dumps(tool_result)}",
                        })
                        
                        tools_used.append(f"{server_name}:{tool_name}")
                        
                    except Exception as e:
                        logger.warning(
                            "Failed to use MCP tool",
                            tool=tool_spec,
                            error=str(e),
                        )
                        continue
        
        # Call the API service
        payload = {
            "model": request.model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        
        response = await api_client.post("/v1/chat/completions", json=payload)
        response.raise_for_status()
        
        result = response.json()
        execution_time = asyncio.get_event_loop().time() - start_time
        
        logger.info(
            "Task completed successfully",
            task_id=task_id,
            execution_time=execution_time,
            tools_used=tools_used,
        )
        
        return TaskResponse(
            task_id=task_id,
            status="completed",
            result=result,
            tools_used=tools_used,
            execution_time=execution_time,
        )
        
    except HTTPError as e:
        execution_time = asyncio.get_event_loop().time() - start_time
        error_msg = f"API request failed: {e.response.text if e.response else str(e)}"
        
        logger.error(
            "Task failed with API error",
            task_id=task_id,
            error=error_msg,
            execution_time=execution_time,
        )
        
        return TaskResponse(
            task_id=task_id,
            status="failed",
            error=error_msg,
            tools_used=tools_used,
            execution_time=execution_time,
        )
        
    except Exception as e:
        execution_time = asyncio.get_event_loop().time() - start_time
        error_msg = f"Unexpected error: {str(e)}"
        
        logger.error(
            "Task failed with unexpected error",
            task_id=task_id,
            error=error_msg,
            execution_time=execution_time,
        )
        
        return TaskResponse(
            task_id=task_id,
            status="failed",
            error=error_msg,
            tools_used=tools_used,
            execution_time=execution_time,
        )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "router:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
