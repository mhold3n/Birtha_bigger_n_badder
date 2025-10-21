#!/usr/bin/env python3
"""Script to ingest documents into the document resources MCP server."""

import argparse
import asyncio
import os
import sys
from typing import List, Optional

import structlog
import httpx

logger = structlog.get_logger()


class DocumentIngestionClient:
    """Client for ingesting documents."""

    def __init__(
        self,
        mcp_server_url: str = "http://localhost:7003",
    ):
        """Initialize ingestion client.
        
        Args:
            mcp_server_url: Document resources MCP server URL
        """
        self.mcp_server_url = mcp_server_url
        self.client = httpx.AsyncClient(timeout=300.0)

    async def ingest_document(
        self,
        file_path: str,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Ingest a single document.
        
        Args:
            file_path: Path to document file
            metadata: Optional document metadata
            
        Returns:
            Ingestion results
        """
        try:
            with open(file_path, 'rb') as f:
                files = {"file": (os.path.basename(file_path), f, "application/octet-stream")}
                
                data = {}
                if metadata:
                    data["metadata"] = str(metadata)
                
                response = await self.client.post(
                    f"{self.mcp_server_url}/v1/ingest",
                    files=files,
                    data=data,
                )
                response.raise_for_status()
                return response.json()
                
        except Exception as e:
            logger.error("Document ingestion failed", file_path=file_path, error=str(e))
            raise

    async def ingest_documents_batch(
        self,
        file_paths: List[str],
        metadata: Optional[dict] = None,
    ) -> List[dict]:
        """Ingest multiple documents.
        
        Args:
            file_paths: List of file paths
            metadata: Optional metadata for all documents
            
        Returns:
            List of ingestion results
        """
        results = []
        
        for file_path in file_paths:
            try:
                result = await self.ingest_document(file_path, metadata)
                results.append(result)
                
            except Exception as e:
                logger.error("Document ingestion failed", file_path=file_path, error=str(e))
                results.append({
                    "filename": os.path.basename(file_path),
                    "error": str(e),
                    "success": False,
                })
        
        return results

    async def ingest_directory(
        self,
        directory_path: str,
        metadata: Optional[dict] = None,
        file_extensions: Optional[List[str]] = None,
    ) -> List[dict]:
        """Ingest all documents in a directory.
        
        Args:
            directory_path: Path to directory
            metadata: Optional metadata for all documents
            file_extensions: Allowed file extensions
            
        Returns:
            List of ingestion results
        """
        if file_extensions is None:
            file_extensions = ['.pdf', '.docx', '.txt', '.html', '.htm']
        
        # Find all files with allowed extensions
        file_paths = []
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                _, ext = os.path.splitext(file.lower())
                if ext in file_extensions:
                    file_paths.append(os.path.join(root, file))
        
        logger.info(f"Found {len(file_paths)} documents to ingest")
        
        return await self.ingest_documents_batch(file_paths, metadata)

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


def load_document_config(config_file: str) -> dict:
    """Load document configuration from file.
    
    Args:
        config_file: Path to configuration file
        
    Returns:
        Document configuration
    """
    import json
    
    if not os.path.exists(config_file):
        logger.warning(f"Configuration file not found: {config_file}")
        return {}
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        logger.info(f"Loaded document configuration from {config_file}")
        return config
        
    except Exception as e:
        logger.error("Failed to load configuration", config_file=config_file, error=str(e))
        return {}


def create_default_config(config_file: str) -> None:
    """Create default configuration file.
    
    Args:
        config_file: Path to configuration file
    """
    import json
    
    default_config = {
        "directories": [
            {
                "path": "/path/to/documents",
                "description": "Example document directory",
                "metadata": {
                    "source": "example",
                    "category": "textbooks",
                },
            },
        ],
        "files": [
            {
                "path": "/path/to/document.pdf",
                "description": "Example document",
                "metadata": {
                    "title": "Example Document",
                    "author": "Example Author",
                    "subject": "Example Subject",
                },
            },
        ],
        "settings": {
            "file_extensions": [".pdf", ".docx", ".txt", ".html", ".htm"],
            "exclude_patterns": [
                "*.tmp",
                "*.temp",
                "*.log",
                "*.bak",
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
    parser = argparse.ArgumentParser(description="Ingest documents")
    parser.add_argument("--config", default="documents.json", help="Configuration file")
    parser.add_argument("--file", help="Single file to ingest")
    parser.add_argument("--directory", help="Directory to ingest")
    parser.add_argument("--mcp-url", default="http://localhost:7003", help="MCP server URL")
    parser.add_argument("--create-config", action="store_true", help="Create default configuration")
    parser.add_argument("--health-check", action="store_true", help="Check MCP server health")
    parser.add_argument("--extensions", nargs="+", default=[".pdf", ".docx", ".txt", ".html"], help="File extensions to include")
    
    args = parser.parse_args()
    
    # Create default configuration if requested
    if args.create_config:
        create_default_config(args.config)
        return
    
    # Initialize client
    client = DocumentIngestionClient(mcp_server_url=args.mcp_url)
    
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
        
        # Ingest single file
        if args.file:
            if not os.path.exists(args.file):
                print(f"❌ File does not exist: {args.file}")
                sys.exit(1)
            
            print(f"📄 Ingesting file: {args.file}")
            result = await client.ingest_document(args.file)
            
            print(f"✅ File ingested successfully:")
            print(f"   Chunks created: {result['chunks_created']}")
            print(f"   File size: {result['file_size']} bytes")
            
        # Ingest directory
        elif args.directory:
            if not os.path.exists(args.directory):
                print(f"❌ Directory does not exist: {args.directory}")
                sys.exit(1)
            
            print(f"📁 Ingesting directory: {args.directory}")
            results = await client.ingest_directory(
                directory_path=args.directory,
                file_extensions=args.extensions,
            )
            
            # Print summary
            successful = sum(1 for r in results if r.get("success", True))
            failed = len(results) - successful
            total_chunks = sum(r.get("chunks_created", 0) for r in results if r.get("success", True))
            
            print(f"✅ Directory ingestion completed:")
            print(f"   Files processed: {len(results)}")
            print(f"   Successful: {successful}")
            print(f"   Failed: {failed}")
            print(f"   Total chunks created: {total_chunks}")
            
        else:
            # Ingest from configuration
            config = load_document_config(args.config)
            
            if not config:
                print(f"❌ No configuration found: {args.config}")
                print("Use --create-config to create a default configuration file")
                sys.exit(1)
            
            results = []
            
            # Ingest directories
            directories = config.get("directories", [])
            for dir_config in directories:
                dir_path = dir_config["path"]
                if os.path.exists(dir_path):
                    print(f"📁 Ingesting directory: {dir_path}")
                    dir_results = await client.ingest_directory(
                        directory_path=dir_path,
                        metadata=dir_config.get("metadata"),
                        file_extensions=args.extensions,
                    )
                    results.extend(dir_results)
                else:
                    print(f"⚠️  Directory not found: {dir_path}")
            
            # Ingest individual files
            files = config.get("files", [])
            for file_config in files:
                file_path = file_config["path"]
                if os.path.exists(file_path):
                    print(f"📄 Ingesting file: {file_path}")
                    file_result = await client.ingest_document(
                        file_path=file_path,
                        metadata=file_config.get("metadata"),
                    )
                    results.append(file_result)
                else:
                    print(f"⚠️  File not found: {file_path}")
            
            # Print summary
            if results:
                successful = sum(1 for r in results if r.get("success", True))
                failed = len(results) - successful
                total_chunks = sum(r.get("chunks_created", 0) for r in results if r.get("success", True))
                
                print(f"✅ Configuration-based ingestion completed:")
                print(f"   Files processed: {len(results)}")
                print(f"   Successful: {successful}")
                print(f"   Failed: {failed}")
                print(f"   Total chunks created: {total_chunks}")
            else:
                print("⚠️  No files found to ingest")
        
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











