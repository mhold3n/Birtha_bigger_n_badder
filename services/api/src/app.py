"""FastAPI control plane for agent orchestration."""

import asyncio
from datetime import datetime
import logging
from typing import Any, Dict, List, Optional

import structlog
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from openai import AsyncOpenAI
from prometheus_client import Counter, Histogram, generate_latest
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from pathlib import Path

from .config import settings

# Routers (scaffolded control plane API)
try:
    from .routes import vms as vms_router
    from .routes import torrents as torrents_router
    from .routes import search as search_router
    from .routes import apps as apps_router
    from .routes import ai as ai_router
except Exception:
    vms_router = None  # type: ignore
    torrents_router = None  # type: ignore
    search_router = None  # type: ignore
    apps_router = None  # type: ignore
    ai_router = None  # type: ignore

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

# Prometheus metrics
REQUEST_COUNT = Counter(
    "api_requests_total",
    "Total number of API requests",
    ["method", "endpoint", "status_code"],
)

REQUEST_DURATION = Histogram(
    "api_request_duration_seconds",
    "Request duration in seconds",
    ["method", "endpoint"],
)

CHAT_REQUESTS = Counter(
    "chat_requests_total",
    "Total number of chat requests",
    ["model", "status"],
)

CHAT_DURATION = Histogram(
    "chat_request_duration_seconds",
    "Chat request duration in seconds",
    ["model"],
)

# Global clients
redis_client: Optional[Redis] = None
openai_client: Optional[AsyncOpenAI] = None

app = FastAPI(
    title="Agent Orchestrator API",
    description="Control plane for agent orchestration with OpenAI-compatible endpoints",
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

# Mount routers if import succeeded
if vms_router:
    app.include_router(vms_router.router)  # type: ignore[attr-defined]
if torrents_router:
    app.include_router(torrents_router.router)  # type: ignore[attr-defined]
if search_router:
    app.include_router(search_router.router)  # type: ignore[attr-defined]
if apps_router:
    app.include_router(apps_router.router)  # type: ignore[attr-defined]
if ai_router:
    app.include_router(ai_router.router)  # type: ignore[attr-defined]

# Static UI (small SPA panels)
_static_dir = (Path(__file__).resolve().parent / "static")
if _static_dir.exists():
    app.mount("/ui", StaticFiles(directory=str(_static_dir), html=True), name="ui")


class ChatMessage(BaseModel):
    """Chat message model."""

    role: str = Field(..., description="Message role (system, user, assistant)")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Chat completion request model."""

    model: str = Field(
        default="mistralai/Mistral-7B-Instruct-v0.3",
        description="Model to use for completion",
    )
    messages: List[ChatMessage] = Field(..., description="List of messages")
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)
    stream: bool = Field(default=False, description="Enable streaming response")


class ChatResponse(BaseModel):
    """Chat completion response model."""

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    timestamp: str
    version: str
    services: Dict[str, str]


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Middleware to collect Prometheus metrics."""
    start_time = asyncio.get_event_loop().time()
    
    response = await call_next(request)
    
    duration = asyncio.get_event_loop().time() - start_time
    
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status_code=response.status_code,
    ).inc()
    
    REQUEST_DURATION.labels(
        method=request.method,
        endpoint=request.url.path,
    ).observe(duration)
    
    return response


@app.on_event("startup")
async def startup_event():
    """Initialize clients on startup."""
    global redis_client, openai_client
    
    logger.info("Starting Agent Orchestrator API", version="0.1.0")
    
    # Initialize Redis client
    try:
        redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
        await redis_client.ping()
        logger.info("Connected to Redis", url=settings.redis_url)
    except Exception as e:
        logger.error("Failed to connect to Redis", error=str(e))
        redis_client = None
    
    # Initialize OpenAI client
    try:
        openai_client = AsyncOpenAI(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
        )
        logger.info("Initialized OpenAI client", base_url=settings.openai_base_url)
    except Exception as e:
        logger.error("Failed to initialize OpenAI client", error=str(e))
        openai_client = None


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global redis_client
    
    if redis_client:
        await redis_client.close()
        logger.info("Closed Redis connection")


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
    
    # Check OpenAI client
    if openai_client:
        try:
            # Simple test request
            await openai_client.models.list()
            services["openai"] = "healthy"
        except Exception:
            services["openai"] = "unhealthy"
    else:
        services["openai"] = "not_configured"
    
    return HealthResponse(
        status="healthy" if all(s == "healthy" for s in services.values()) else "degraded",
        timestamp=datetime.utcnow().isoformat(),
        version="0.1.0",
        services=services,
    )


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    if not settings.enable_metrics:
        raise HTTPException(status_code=404, detail="Metrics disabled")
    
    return Response(
        content=generate_latest(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.post("/v1/chat/completions", response_model=ChatResponse)
async def chat_completions(request: ChatRequest):
    """OpenAI-compatible chat completions endpoint."""
    if not openai_client:
        raise HTTPException(
            status_code=503,
            detail="OpenAI client not available",
        )
    # Basic validation: require at least one message
    if not request.messages:
        raise HTTPException(status_code=422, detail="'messages' must contain at least one item")
    
    start_time = asyncio.get_event_loop().time()
    
    try:
        logger.info(
            "Processing chat request",
            model=request.model,
            message_count=len(request.messages),
            stream=request.stream,
        )
        
        # Convert to OpenAI format
        openai_messages = [
            {"role": msg.role, "content": msg.content} for msg in request.messages
        ]
        
        # Make request to worker
        response = await openai_client.chat.completions.create(
            model=request.model,
            messages=openai_messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=request.stream,
        )
        
        duration = asyncio.get_event_loop().time() - start_time
        
        # Update metrics
        CHAT_REQUESTS.labels(model=request.model, status="success").inc()
        CHAT_DURATION.labels(model=request.model).observe(duration)
        
        logger.info(
            "Chat request completed",
            model=request.model,
            duration=duration,
            usage=response.usage.dict() if response.usage else None,
        )
        
        return response
        
    except Exception as e:
        duration = asyncio.get_event_loop().time() - start_time
        
        # Update metrics
        CHAT_REQUESTS.labels(model=request.model, status="error").inc()
        CHAT_DURATION.labels(model=request.model).observe(duration)
        
        logger.error(
            "Chat request failed",
            model=request.model,
            error=str(e),
            duration=duration,
        )
        
        raise HTTPException(status_code=500, detail=f"Chat request failed: {str(e)}")


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Agent Orchestrator API",
        "version": "0.1.0",
        "description": "Control plane for agent orchestration",
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics" if settings.enable_metrics else None,
        "endpoints": {
            "vms": "/api/vms",
            "apps": "/api/apps",
            "torrents": "/api/torrents",
            "search": "/api/search",
            "ai": "/api/ai",
        },
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
