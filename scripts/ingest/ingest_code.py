#!/usr/bin/env python3
"""Script to ingest code repositories into the code resources MCP server."""

import argparse
import asyncio
import os
import sys
from typing import List, Optional

import structlog
import httpx

logger = structlog.get_logger()


class CodeIngestionClient:
    """Client for ingesting code repositories."""

    def __init__(
        self,
        mcp_server_url: str = "http://localhost:7002",
    ):
        """Initialize ingestion client.
        
        Args:
            mcp_server_url: Code resources MCP server URL
        """
        self.mcp_server_url = mcp_server_url
        self.client = httpx.AsyncClient(timeout=300.0)

    async def ingest_repository(
        self,
        repository_path: str,
        branch: str = "main",
    ) -> dict:
        """Ingest a code repository.
        
        Args:
            repository_path: Path to repository
            branch: Branch to index
            
        Returns:
            Ingestion results
        """
        try:
            response = await self.client.post(
                f"{self.mcp_server_url}/v1/index",
                json={
                    "repository_path": repository_path,
                    "branch": branch,
                },
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error("Repository ingestion failed", repository_path=repository_path, error=str(e))
            raise

    async def ingest_repositories_batch(
        self,
        repositories: List[dict],
    ) -> List[dict]:
        """Ingest multiple repositories.
        
        Args:
            repositories: List of repository configurations
            
        Returns:
            List of ingestion results
        """
        results = []
        
        for repo_config in repositories:
            try:
                result = await self.ingest_repository(
                    repository_path=repo_config["path"],
                    branch=repo_config.get("branch", "main"),
                )
                results.append(result)
                
            except Exception as e:
                logger.error("Repository ingestion failed", repository=repo_config, error=str(e))
                results.append({
                    "repository_path": repo_config["path"],
                    "error": str(e),
                    "success": False,
                })
        
        return results

    async def check_health(self) -> bool:
        """Check MCP server health.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            response = await self.client.get(f"{self.mcp_server_url}/health")
            response.raise_for_status()
            health_data = response.json()
            return health_data.get("status") == "healthy"
            
        except Exception as e:
            logger.error("Health check failed", error=str(e))
            return False

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


def load_repository_config(config_file: str) -> List[dict]:
    """Load repository configuration from file.
    
    Args:
        config_file: Path to configuration file
        
    Returns:
        List of repository configurations
    """
    import json
    
    if not os.path.exists(config_file):
        logger.warning(f"Configuration file not found: {config_file}")
        return []
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        repositories = config.get("repositories", [])
        logger.info(f"Loaded {len(repositories)} repositories from configuration")
        return repositories
        
    except Exception as e:
        logger.error("Failed to load configuration", config_file=config_file, error=str(e))
        return []


def create_default_config(config_file: str) -> None:
    """Create default configuration file.
    
    Args:
        config_file: Path to configuration file
    """
    import json
    
    default_config = {
        "repositories": [
            {
                "name": "example-repo",
                "path": "/path/to/repository",
                "branch": "main",
                "description": "Example repository for code ingestion",
            },
        ],
        "settings": {
            "default_branch": "main",
            "exclude_patterns": [
                "*.pyc",
                "__pycache__",
                ".git",
                "node_modules",
                "*.log",
            ],
        },
    }
    
    try:
        with open(config_file, 'w') as f:
            json.dump(default_config, f, indent=2)
        
        logger.info(f"Created default configuration: {config_file}")
        
    except Exception as e:
        logger.error("Failed to create configuration", config_file=config_file, error=str(e))


async def main():
    """Main ingestion function."""
    parser = argparse.ArgumentParser(description="Ingest code repositories")
    parser.add_argument("--config", default="repositories.json", help="Configuration file")
    parser.add_argument("--repository", help="Single repository path to ingest")
    parser.add_argument("--branch", default="main", help="Branch to index")
    parser.add_argument("--mcp-url", default="http://localhost:7002", help="MCP server URL")
    parser.add_argument("--create-config", action="store_true", help="Create default configuration")
    parser.add_argument("--health-check", action="store_true", help="Check MCP server health")
    
    args = parser.parse_args()
    
    # Create default configuration if requested
    if args.create_config:
        create_default_config(args.config)
        return
    
    # Initialize client
    client = CodeIngestionClient(mcp_server_url=args.mcp_url)
    
    try:
        # Health check
        if args.health_check:
            is_healthy = await client.check_health()
            if is_healthy:
                print("✅ MCP server is healthy")
                return
            else:
                print("❌ MCP server is unhealthy")
                sys.exit(1)
        
        # Check server health before ingestion
        is_healthy = await client.check_health()
        if not is_healthy:
            print("❌ MCP server is unhealthy, aborting ingestion")
            sys.exit(1)
        
        print("✅ MCP server is healthy, starting ingestion...")
        
        # Ingest single repository
        if args.repository:
            if not os.path.exists(args.repository):
                print(f"❌ Repository path does not exist: {args.repository}")
                sys.exit(1)
            
            print(f"📁 Ingesting repository: {args.repository}")
            result = await client.ingest_repository(
                repository_path=args.repository,
                branch=args.branch,
            )
            
            print(f"✅ Repository ingested successfully:")
            print(f"   Files indexed: {result['files_indexed']}")
            print(f"   Functions indexed: {result['functions_indexed']}")
            print(f"   Classes indexed: {result['classes_indexed']}")
            
        else:
            # Ingest from configuration
            repositories = load_repository_config(args.config)
            
            if not repositories:
                print(f"❌ No repositories found in configuration: {args.config}")
                print("Use --create-config to create a default configuration file")
                sys.exit(1)
            
            print(f"📁 Ingesting {len(repositories)} repositories...")
            
            results = await client.ingest_repositories_batch(repositories)
            
            # Print summary
            successful = sum(1 for r in results if r.get("success", True))
            failed = len(results) - successful
            
            print(f"✅ Ingestion completed:")
            print(f"   Successful: {successful}")
            print(f"   Failed: {failed}")
            
            # Print detailed results
            for result in results:
                if result.get("success", True):
                    print(f"   ✅ {result['repository_path']}: {result['files_indexed']} files, {result['functions_indexed']} functions")
                else:
                    print(f"   ❌ {result['repository_path']}: {result.get('error', 'Unknown error')}")
        
    except KeyboardInterrupt:
        print("\n⏹️  Ingestion interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ingestion failed: {e}")
        sys.exit(1)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())











