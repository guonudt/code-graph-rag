#!/usr/bin/env python3
"""
Code Graph RAG MCP Server
支持STDIO和HTTP两种传输模式的MCP服务器
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any

from mcp.server import fastmcp
from starlette.requests import Request
from starlette.responses import JSONResponse

from .config import settings
from .graph_updater import MemgraphIngestor
from .services.llm import CypherGenerator
from .tools.code_retrieval import CodeRetriever

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server with default settings
# The actual host and port will be set when running the server
mcp = fastmcp.FastMCP("code-graph-rag")

# Global services (will be initialized when needed)
ingestor: MemgraphIngestor | None = None
cypher_generator: CypherGenerator | None = None
code_retriever: CodeRetriever | None = None
repo_path: Path | None = None


async def ensure_services() -> None:
    """Ensure all services are initialized."""
    global ingestor, cypher_generator, code_retriever, repo_path

    if ingestor is None:
        ingestor = MemgraphIngestor(
            host=settings.MEMGRAPH_HOST, port=settings.MEMGRAPH_PORT
        )
        # Manually enter the context manager
        ingestor.__enter__()
        logger.info("Initialized MemgraphIngestor")

    if cypher_generator is None:
        cypher_generator = CypherGenerator()
        logger.info("Initialized CypherGenerator")

    if repo_path is None:
        repo_path = Path(settings.TARGET_REPO_PATH).resolve()
        logger.info(f"Set repository path to: {repo_path}")

    if code_retriever is None:
        code_retriever = CodeRetriever(str(repo_path), ingestor)
        logger.info("Initialized CodeRetriever")


@mcp.tool()
async def query_codebase(query: str) -> str:
    """Query the codebase knowledge graph using natural language.

    Ask questions about classes, functions, methods, dependencies, or code structure.
    Examples:
    - "Find all functions that handle authentication"
    - "What classes are in the user module?"
    - "Show me functions with the longest call chains"
    - "Which files contain database operations?"

    Args:
        query: Natural language question about the codebase
    """
    await ensure_services()

    try:
        logger.info(f"Querying codebase: {query}")

        # Generate Cypher query from natural language
        if cypher_generator is None:
            return "Error: Cypher generator not initialized"
        cypher_query = await cypher_generator.generate(query)
        logger.info(f"Generated Cypher: {cypher_query}")

        # Execute query
        if ingestor is None:
            return "Error: Memgraph ingestor not initialized"
        results = ingestor.fetch_all(cypher_query)

        if not results:
            return f"No results found for query: '{query}'\n\nGenerated Cypher: {cypher_query}"

        # Format results
        result_text = f"Query: {query}\n"
        result_text += f"Generated Cypher: {cypher_query}\n\n"
        result_text += f"Found {len(results)} result(s):\n\n"

        for i, row in enumerate(results, 1):
            result_text += f"Result {i}:\n"
            for key, value in row.items():
                result_text += f"  {key}: {value}\n"
            result_text += "\n"

        logger.info(f"Query completed successfully, found {len(results)} results")
        return result_text

    except Exception as e:
        logger.error(f"Error querying codebase: {e}")
        return f"Error querying codebase: {str(e)}"


@mcp.tool()
async def get_code_snippet(qualified_name: str) -> str:
    """Retrieve the source code for a specific function, class, or method.

    Args:
        qualified_name: Fully qualified name of the function, class, or method
                       Examples: "User.authenticate", "database.connection.connect"
    """
    await ensure_services()

    try:
        logger.info(f"Retrieving code snippet for: {qualified_name}")

        if code_retriever is None:
            return "Error: Code retriever not initialized"
        snippet = await code_retriever.find_code_snippet(qualified_name)

        if not snippet.found:
            return f"Code snippet not found: {qualified_name}\nError: {snippet.error_message}"

        result_text = f"Code snippet for: {qualified_name}\n"
        result_text += f"File: {snippet.file_path}\n"
        result_text += f"Lines: {snippet.line_start}-{snippet.line_end}\n"
        if snippet.docstring:
            result_text += f"Docstring: {snippet.docstring}\n"
        result_text += f"\n```\n{snippet.source_code}\n```"

        logger.info(f"Successfully retrieved code snippet for: {qualified_name}")
        return result_text

    except Exception as e:
        logger.error(f"Error retrieving code snippet: {e}")
        return f"Error retrieving code snippet: {str(e)}"


@mcp.tool()
async def get_codebase_summary() -> str:
    """Get a summary of the codebase structure including languages, file counts, and main components."""
    await ensure_services()

    try:
        logger.info("Getting codebase summary")

        # Query for basic statistics
        stats_query = """
        MATCH (n)
        RETURN labels(n)[0] AS node_type, count(n) AS count
        ORDER BY count DESC
        """

        if ingestor is None:
            return "Error: Memgraph ingestor not initialized"
        results = ingestor.fetch_all(stats_query)

        result_text = f"Codebase Summary for: {repo_path}\n\n"
        result_text += "Node Statistics:\n"

        for row in results:
            result_text += f"  {row['node_type']}: {row['count']}\n"

        # Get language distribution
        lang_query = """
        MATCH (f:File)
        WHERE f.extension IS NOT NULL
        RETURN f.extension AS extension, count(f) AS count
        ORDER BY count DESC
        """

        lang_results = ingestor.fetch_all(lang_query)

        result_text += "\nFile Types:\n"
        for row in lang_results:
            result_text += f"  {row['extension']}: {row['count']}\n"

        logger.info("Successfully generated codebase summary")
        return result_text

    except Exception as e:
        logger.error(f"Error getting codebase summary: {e}")
        return f"Error getting codebase summary: {str(e)}"


@mcp.tool()
async def health_check() -> str:
    """Check the health status of the MCP server and its dependencies."""
    try:
        await ensure_services()

        # Test Memgraph connection
        test_query = "RETURN 1 as test"
        if ingestor is None:
            return "❌ MCP Server is unhealthy\n❌ Memgraph connection: Failed (not initialized)"
        result = ingestor.fetch_all(test_query)

        if result and result[0]["test"] == 1:
            return "✅ MCP Server is healthy\n✅ Memgraph connection: OK\n✅ All services initialized"
        else:
            return "⚠️ MCP Server is running but Memgraph connection may have issues"

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return f"❌ Health check failed: {str(e)}"


@mcp.custom_route("/health", methods=["GET"])
async def http_health_check(request: Request) -> JSONResponse:
    """HTTP health check endpoint for external monitoring."""
    try:
        await ensure_services()

        # Test Memgraph connection
        test_query = "RETURN 1 as test"
        if ingestor is None:
            return JSONResponse(
                {
                    "status": "unhealthy",
                    "server": "code-graph-rag",
                    "error": "Memgraph not initialized",
                },
                status_code=500,
            )
        result = ingestor.fetch_all(test_query)

        if result and result[0]["test"] == 1:
            return JSONResponse(
                {
                    "status": "healthy",
                    "server": "code-graph-rag",
                    "memgraph": "connected",
                    "services": "initialized",
                }
            )
        else:
            return JSONResponse(
                {
                    "status": "degraded",
                    "server": "code-graph-rag",
                    "memgraph": "connection_issues",
                    "services": "initialized",
                },
                status_code=503,
            )

    except Exception as e:
        logger.error(f"HTTP health check failed: {e}")
        return JSONResponse(
            {"status": "unhealthy", "server": "code-graph-rag", "error": str(e)},
            status_code=500,
        )


def get_transport_mode() -> str:
    """Determine transport mode from environment variables or command line arguments."""
    # Check command line arguments first
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ["stdio", "http", "sse"]:
            return arg

    # Check environment variable
    transport = os.getenv("MCP_TRANSPORT", "").lower()
    if transport in ["stdio", "http", "sse"]:
        return transport

    # Default to stdio for backward compatibility
    return "stdio"


def get_server_config() -> dict[str, Any]:
    """Get server configuration based on transport mode."""
    transport = get_transport_mode()

    if transport in ["http", "sse"]:
        # HTTP mode configuration
        host = os.getenv("MCP_HOST", settings.MEMGRAPH_HOST)
        port = int(os.getenv("MCP_PORT", settings.MCP_HTTP_PORT))
        return {"transport": "sse", "host": host, "port": port}
    else:
        # STDIO mode configuration
        return {"transport": "stdio"}


if __name__ == "__main__":
    # Auto-detect and set local models if configured
    if (
        settings.LOCAL_MODEL_ENDPOINT
        and settings.LOCAL_ORCHESTRATOR_MODEL_ID
        and settings.LOCAL_CYPHER_MODEL_ID
    ):
        logger.info("Local model configuration detected, switching to local models")
        settings.set_orchestrator_model(settings.LOCAL_ORCHESTRATOR_MODEL_ID)
        settings.set_cypher_model(settings.LOCAL_CYPHER_MODEL_ID)

    # Validate settings before starting
    try:
        settings.validate_for_usage()
        logger.info("Configuration validated successfully")
        logger.info(f"Using orchestrator model: {settings.active_orchestrator_model}")
        logger.info(f"Using cypher model: {settings.active_cypher_model}")
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Please configure either:")
        logger.error("1. GEMINI_API_KEY for Gemini models")
        logger.error("2. LOCAL_MODEL_* settings for local models")
        logger.error("3. OPENAI_API_KEY for OpenAI models")
        exit(1)

    # Get server configuration
    config = get_server_config()
    transport = config["transport"]

    if transport == "stdio":
        # STDIO mode
        logger.info("Starting Code Graph RAG MCP Server (STDIO mode)")
        mcp.run(transport="stdio")
    else:
        # HTTP mode
        host = config["host"]
        port = config["port"]
        logger.info(f"Starting Code Graph RAG MCP Server (HTTP mode) on {host}:{port}")
        logger.info("Available endpoints:")
        logger.info(f"  - SSE: http://{host}:{port}/sse")
        logger.info(f"  - Health: http://{host}:{port}/health")

        # Create a new FastMCP instance with the configured host and port
        http_mcp = fastmcp.FastMCP(name="code-graph-rag", host=host, port=port)

        # Register all tools with the new instance
        # We know the tools from the original mcp instance, so we can register them directly
        http_mcp.tool()(query_codebase)
        http_mcp.tool()(get_code_snippet)
        http_mcp.tool()(get_codebase_summary)
        http_mcp.tool()(health_check)

        # Add the health endpoint
        @http_mcp.custom_route("/health", methods=["GET"])
        async def http_health_check_new(request: Request) -> JSONResponse:
            return await http_health_check(request)

        # Note: FastMCP handles SSE connection errors internally
        # The ClosedResourceError is expected behavior when clients disconnect
        # and doesn't affect server functionality

        # Configure logging to reduce noise from expected SSE disconnections
        import logging
        import warnings

        # Suppress specific warnings and errors
        warnings.filterwarnings("ignore", category=RuntimeWarning)
        logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

        # Set environment variable to suppress anyio warnings
        os.environ["ANYIO_BACKEND"] = "asyncio"

        # Run the HTTP server
        http_mcp.run(transport="sse")
