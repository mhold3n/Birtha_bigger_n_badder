"""Unified MCP Registry Service for Birtha + WrkHrs."""

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

logger = structlog.get_logger()

app = FastAPI(
    title="MCP Registry",
    description="Unified registry for MCP tools and resources",
    version="0.1.0",
)


class MCPServer(BaseModel):
    """MCP Server definition."""
    
    name: str = Field(..., description="Server name")
    type: str = Field(..., description="Server type (tool|resource)")
    description: str = Field(..., description="Server description")
    version: str = Field(..., description="Server version")
    url: str = Field(..., description="Server URL")
    health_url: Optional[str] = Field(None, description="Health check URL")
    tools: List[Dict[str, Any]] = Field(default_factory=list, description="Available tools")
    resources: List[Dict[str, Any]] = Field(default_factory=list, description="Available resources")
    schema: Dict[str, Any] = Field(default_factory=dict, description="JSON Schema")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class MCPRegistry:
    """Registry for MCP servers and their schemas."""

    def __init__(self, config_path: str = "/app/config/mcp_servers.yaml"):
        """Initialize MCP registry.
        
        Args:
            config_path: Path to MCP servers configuration file
        """
        self.config_path = Path(config_path)
        self.servers: Dict[str, MCPServer] = {}
        self._load_servers()

    def _load_servers(self) -> None:
        """Load MCP servers from configuration file."""
        if not self.config_path.exists():
            logger.warning("MCP servers config not found", path=str(self.config_path))
            return

        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            servers_config = config.get('servers', [])
            
            for server_config in servers_config:
                server = MCPServer(**server_config)
                self.servers[server.name] = server
                
            logger.info(
                "Loaded MCP servers",
                count=len(self.servers),
                servers=list(self.servers.keys()),
            )
            
        except Exception as e:
            logger.error("Failed to load MCP servers", error=str(e))

    def get_servers(self, server_type: Optional[str] = None) -> List[MCPServer]:
        """Get list of MCP servers.
        
        Args:
            server_type: Optional filter by server type (tool|resource)
            
        Returns:
            List of MCP servers
        """
        servers = list(self.servers.values())
        
        if server_type:
            servers = [s for s in servers if s.type == server_type]
        
        return servers

    def get_server(self, name: str) -> Optional[MCPServer]:
        """Get MCP server by name.
        
        Args:
            name: Server name
            
        Returns:
            MCP server or None if not found
        """
        return self.servers.get(name)

    def get_tools(self) -> List[Dict[str, Any]]:
        """Get all tools from all servers.
        
        Returns:
            List of tools with server information
        """
        tools = []
        
        for server in self.servers.values():
            for tool in server.tools:
                tool_with_server = tool.copy()
                tool_with_server["server"] = server.name
                tool_with_server["server_type"] = server.type
                tool_with_server["server_url"] = server.url
                tools.append(tool_with_server)
        
        return tools

    def get_resources(self) -> List[Dict[str, Any]]:
        """Get all resources from all servers.
        
        Returns:
            List of resources with server information
        """
        resources = []
        
        for server in self.servers.values():
            for resource in server.resources:
                resource_with_server = resource.copy()
                resource_with_server["server"] = server.name
                resource_with_server["server_type"] = server.type
                resource_with_server["server_url"] = server.url
                resources.append(resource_with_server)
        
        return resources

    def get_server_schema(self, name: str) -> Optional[Dict[str, Any]]:
        """Get JSON schema for a specific server.
        
        Args:
            name: Server name
            
        Returns:
            JSON schema or None if not found
        """
        server = self.servers.get(name)
        return server.schema if server else None

    def search_tools(self, query: str) -> List[Dict[str, Any]]:
        """Search tools by name or description.
        
        Args:
            query: Search query
            
        Returns:
            List of matching tools
        """
        query_lower = query.lower()
        matching_tools = []
        
        for tool in self.get_tools():
            if (query_lower in tool.get("name", "").lower() or
                query_lower in tool.get("description", "").lower()):
                matching_tools.append(tool)
        
        return matching_tools

    def search_resources(self, query: str) -> List[Dict[str, Any]]:
        """Search resources by name or description.
        
        Args:
            query: Search query
            
        Returns:
            List of matching resources
        """
        query_lower = query.lower()
        matching_resources = []
        
        for resource in self.get_resources():
            if (query_lower in resource.get("name", "").lower() or
                query_lower in resource.get("description", "").lower()):
                matching_resources.append(resource)
        
        return matching_resources


# Global registry instance
registry = MCPRegistry()


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "mcp-registry",
        "servers_count": len(registry.servers),
    }


@app.get("/mcp/registry", response_model=List[MCPServer])
async def get_registry(
    type: Optional[str] = None,
) -> List[MCPServer]:
    """Get all MCP servers in the registry.
    
    Args:
        type: Optional filter by server type (tool|resource)
        
    Returns:
        List of MCP servers
    """
    return registry.get_servers(type)


@app.get("/mcp/registry/tools")
async def get_tools() -> List[Dict[str, Any]]:
    """Get all tools from all MCP servers.
    
    Returns:
        List of tools with server information
    """
    return registry.get_tools()


@app.get("/mcp/registry/resources")
async def get_resources() -> List[Dict[str, Any]]:
    """Get all resources from all MCP servers.
    
    Returns:
        List of resources with server information
    """
    return registry.get_resources()


@app.get("/mcp/registry/{name}", response_model=MCPServer)
async def get_server(name: str) -> MCPServer:
    """Get specific MCP server by name.
    
    Args:
        name: Server name
        
    Returns:
        MCP server information
        
    Raises:
        HTTPException: If server not found
    """
    server = registry.get_server(name)
    if not server:
        raise HTTPException(status_code=404, detail=f"Server '{name}' not found")
    return server


@app.get("/mcp/registry/{name}/schema")
async def get_server_schema(name: str) -> Dict[str, Any]:
    """Get JSON schema for specific MCP server.
    
    Args:
        name: Server name
        
    Returns:
        JSON schema
        
    Raises:
        HTTPException: If server not found
    """
    schema = registry.get_server_schema(name)
    if not schema:
        raise HTTPException(status_code=404, detail=f"Schema for server '{name}' not found")
    return schema


@app.get("/mcp/registry/search/tools")
async def search_tools(q: str) -> List[Dict[str, Any]]:
    """Search tools by name or description.
    
    Args:
        q: Search query
        
    Returns:
        List of matching tools
    """
    return registry.search_tools(q)


@app.get("/mcp/registry/search/resources")
async def search_resources(q: str) -> List[Dict[str, Any]]:
    """Search resources by name or description.
    
    Args:
        q: Search query
        
    Returns:
        List of matching resources
    """
    return registry.search_resources(q)


@app.post("/mcp/registry/register", response_model=MCPServer)
async def register_server(server: MCPServer) -> MCPServer:
    """Register a new MCP server.
    
    Args:
        server: MCP server to register
        
    Returns:
        Registered server information
    """
    try:
        # Add to registry
        registry.servers[server.name] = server
        
        logger.info(
            "MCP server registered",
            name=server.name,
            type=server.type,
            url=server.url,
            tools_count=len(server.tools),
            resources_count=len(server.resources),
        )
        
        return server
        
    except Exception as e:
        logger.error("Failed to register MCP server", name=server.name, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to register server: {str(e)}")


@app.get("/mcp/registry/stats")
async def get_registry_stats() -> Dict[str, Any]:
    """Get registry statistics.
    
    Returns:
        Registry statistics
    """
    tools = registry.get_tools()
    resources = registry.get_resources()
    
    tool_servers = len([s for s in registry.servers.values() if s.type == "tool"])
    resource_servers = len([s for s in registry.servers.values() if s.type == "resource"])
    
    return {
        "total_servers": len(registry.servers),
        "tool_servers": tool_servers,
        "resource_servers": resource_servers,
        "total_tools": len(tools),
        "total_resources": len(resources),
        "servers": {
            name: {
                "type": server.type,
                "tools_count": len(server.tools),
                "resources_count": len(server.resources),
            }
            for name, server in registry.servers.items()
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)











