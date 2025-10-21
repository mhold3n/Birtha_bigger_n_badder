from __future__ import annotations

from typing import Any, Dict, List, Optional

import json
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import settings


router = APIRouter(prefix="/api/ai", tags=["AI"])


class QueryRequest(BaseModel):
    prompt: Optional[str] = Field(default=None)
    messages: Optional[List[Dict[str, str]]] = Field(default=None)
    model: str = Field(default="mistralai/Mistral-7B-Instruct-v0.3")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)
    tools: Optional[List[str]] = Field(default=None, description="MCP tools to use via router (server:tool)")
    tool_args: Optional[Dict[str, Dict[str, Any]]] = Field(default=None, description="Per-tool argument overrides (key: server:tool)")
    context: Optional[Dict[str, Any]] = Field(default=None)
    use_router: bool = Field(default=True, description="Route via agent router with MCP integration")
    system: str = Field(default="You are a helpful AI assistant.")


@router.post("/query")
async def ai_query(req: QueryRequest) -> Dict[str, Any]:
    if not req.prompt and not req.messages:
        raise HTTPException(status_code=400, detail="Provide 'prompt' or 'messages'")

    if req.use_router:
        payload = {
            "prompt": req.prompt or (req.messages[-1]["content"] if req.messages else ""),
            "system": req.system,
            "model": req.model,
            "tools": req.tools,
            "tool_args": req.tool_args,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{settings.router_url}/route", json=payload)
            try:
                resp.raise_for_status()
            except httpx.HTTPError:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp.json()
    else:
        # Simple LLM call via AI stack
        payload = {"prompt": req.prompt or (req.messages[-1]["content"] if req.messages else ""), "model": req.model}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{settings.ai_stack_url}/llm/prompt", json=payload)
            try:
                resp.raise_for_status()
            except httpx.HTTPError:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp.json()


class WorkflowRunRequest(BaseModel):
    name: str = Field(description="Workflow name (e.g., code-rag, media-fixups, sysadmin-ops)")
    input: Dict[str, Any] = Field(default_factory=dict)
    model: str = Field(default="mistralai/Mistral-7B-Instruct-v0.3")
    temperature: float = Field(default=0.2)
    max_tokens: Optional[int] = Field(default=None)


@router.post("/workflows/run")
async def run_workflow(req: WorkflowRunRequest) -> Dict[str, Any]:
    name = req.name.lower()
    if name == "code-rag":
        # Route via agent router with MCP tools and repo context
        repos = [r.strip() for r in settings.ai_repos.split(",") if r.strip()]
        tools = [
            "github-mcp:search",  # placeholder; depends on actual MCP tool names
            "filesystem-mcp:code_analysis",
            "vector-db-mcp:embedding_search",
        ]
        tool_args = {
            "github-mcp:search": {"repos": repos, "query": req.input.get("query", "")},
            "filesystem-mcp:code_analysis": {"path": req.input.get("path", "/workspace")},
            "vector-db-mcp:embedding_search": {"text": req.input.get("query", ""), "top_k": 5},
        }
        payload = {
            "prompt": req.input.get("query", "Summarize repository context and answer."),
            "system": "You are a code assistant using tools to retrieve context.",
            "model": req.model,
            "tools": tools,
            "tool_args": tool_args,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{settings.router_url}/route", json=payload)
            try:
                resp.raise_for_status()
            except httpx.HTTPError:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp.json()

    if name == "media-fixups":
        # Use marker directories (processed docs) as context via filesystem MCP
        tools = [
            "filesystem-mcp:directory_traversal",
            "filesystem-mcp:file_read",
        ]
        tool_args = {
            "filesystem-mcp:directory_traversal": {"path": settings.marker_processed_dir},
            "filesystem-mcp:file_read": {"path": req.input.get("file")},
        }
        prompt = req.input.get("instruction", "Analyze document and propose fixes.")
        payload = {
            "prompt": prompt,
            "system": "You assist with media/document fix-ups using filesystem context.",
            "model": req.model,
            "tools": tools,
            "tool_args": tool_args,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{settings.router_url}/route", json=payload)
            try:
                resp.raise_for_status()
            except httpx.HTTPError:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp.json()

    if name == "sysadmin-ops":
        # Basic prompt routed through router (tools optional)
        payload = {
            "prompt": req.input.get("task", ""),
            "system": "You are a sysadmin assistant.",
            "model": req.model,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{settings.router_url}/route", json=payload)
            try:
                resp.raise_for_status()
            except httpx.HTTPError:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp.json()

    raise HTTPException(status_code=400, detail=f"Unknown workflow: {req.name}")


class SimulationAnalyzeRequest(BaseModel):
    payload: Dict[str, Any] = Field(default_factory=dict)
    instructions: str = Field(default="Analyze and summarize insights.")
    model: str = Field(default="mistralai/Mistral-7B-Instruct-v0.3")


@router.post("/simulations/analyze")
async def simulations_analyze(req: SimulationAnalyzeRequest) -> Dict[str, Any]:
    # Simple analysis via AI stack LLM
    prompt = f"Instructions: {req.instructions}\n\nPayload JSON:\n{json.dumps(req.payload, indent=2)}\n\nProvide concise analysis."
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.ai_stack_url}/llm/prompt",
            json={"prompt": prompt, "model": req.model},
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPError:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()


@router.get("/status")
async def ai_status() -> Dict[str, Any]:
    """Aggregate health/status for AI components: API (worker), Router, AI Stack, MCPs."""
    status: Dict[str, Any] = {"api": {}, "router": {}, "ai_stack": {}, "worker": {}}

    # API/Worker (OpenAI client in API)
    try:
        from ..app import openai_client  # lazy import to reuse initialized client
        if openai_client:
            try:
                models = await openai_client.models.list()
                status["worker"] = {"status": "healthy", "model_count": len(models.data)}
                status["api"]["openai"] = "healthy"
            except Exception as e:  # pragma: no cover - I/O
                status["worker"] = {"status": "unhealthy", "error": str(e)}
                status["api"]["openai"] = "unhealthy"
        else:
            status["worker"] = {"status": "not_configured"}
            status["api"]["openai"] = "not_configured"
    except Exception:
        status["worker"] = {"status": "unknown"}

    # Router health (+ MCP servers)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{settings.router_url}/health")
            if r.status_code == 200:
                data = r.json()
                status["router"] = {
                    "status": data.get("status", "unknown"),
                    "services": data.get("services", {}),
                    "mcp_servers": data.get("mcp_servers", {}),
                }
            else:
                status["router"] = {"status": "unhealthy", "code": r.status_code}
    except Exception as e:  # pragma: no cover - I/O
        status["router"] = {"status": "unreachable", "error": str(e)}

    # AI Stack health
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{settings.ai_stack_url}/health")
            if r.status_code == 200:
                data = r.json()
                status["ai_stack"] = {"status": "healthy", **data}
            else:
                status["ai_stack"] = {"status": "unhealthy", "code": r.status_code}
    except Exception as e:  # pragma: no cover - I/O
        status["ai_stack"] = {"status": "unreachable", "error": str(e)}

    # Overall status
    components = [status.get("worker", {}), status.get("router", {}), status.get("ai_stack", {})]
    overall = "healthy" if all(c.get("status") == "healthy" for c in components) else "degraded"
    status["status"] = overall
    return status


# =========================
# MCP discovery + control
# =========================


class ToggleRequest(BaseModel):
    enabled: bool = Field(...)


class MCPCallRequest(BaseModel):
    server: str
    tool: str
    arguments: Optional[Dict[str, Any]] = None


async def _get_disabled_servers() -> List[str]:
    try:
        from ..app import redis_client  # type: ignore
        if redis_client:
            disabled = await redis_client.smembers("mcp:disabled")
            return list(disabled or [])
    except Exception:
        pass
    return []


async def _set_server_enabled(name: str, enabled: bool) -> None:
    try:
        from ..app import redis_client  # type: ignore
        if not redis_client:
            return
        if enabled:
            await redis_client.srem("mcp:disabled", name)
        else:
            await redis_client.sadd("mcp:disabled", name)
    except Exception:
        pass


@router.get("/mcp/servers")
async def mcp_servers() -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"{settings.router_url}/mcp/servers")
        try:
            r.raise_for_status()
        except httpx.HTTPError:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        data = r.json() or {}
        servers = data.get("servers", [])
        disabled = set(await _get_disabled_servers())
        for s in servers:
            s["enabled"] = s.get("name") not in disabled
        return {"servers": servers}


@router.post("/mcp/servers/{name}/enable")
async def mcp_toggle_server(name: str, body: ToggleRequest) -> Dict[str, Any]:
    await _set_server_enabled(name, body.enabled)
    return {"server": name, "enabled": body.enabled}


@router.get("/mcp/servers/{name}/tools")
async def mcp_server_tools(name: str) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(f"{settings.router_url}/mcp/servers/{name}/tools")
        try:
            r.raise_for_status()
        except httpx.HTTPError:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()


@router.post("/mcp/call")
async def mcp_call(req: MCPCallRequest) -> Dict[str, Any]:
    disabled = await _get_disabled_servers()
    if req.server in disabled:
        raise HTTPException(status_code=403, detail=f"Server '{req.server}' is disabled")
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Router expects tool_name and arguments; send as JSON body
        r = await client.post(
            f"{settings.router_url}/mcp/servers/{req.server}/call",
            json={"tool_name": req.tool, "arguments": req.arguments or {}},
        )
        try:
            r.raise_for_status()
        except httpx.HTTPError:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()
