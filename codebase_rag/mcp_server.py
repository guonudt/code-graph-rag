#!/usr/bin/env python3
"""
Code Graph RAG MCP Server
支持STDIO和HTTP两种传输模式的MCP服务器
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any

# Add the project root to Python path for direct execution
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from mcp.server import fastmcp
from starlette.requests import Request
from starlette.responses import JSONResponse

try:
    # Try relative imports first (when run as module)
    from .config import settings
    from .graph_updater import MemgraphIngestor
    from .services.llm import CypherGenerator, create_rag_orchestrator
    from .tools.code_retrieval import CodeRetriever, create_code_retrieval_tool
    from .tools.codebase_query import create_query_tool
    from .tools.directory_lister import DirectoryLister, create_directory_lister_tool
    from .tools.document_analyzer import DocumentAnalyzer, create_document_analyzer_tool
    from .tools.file_editor import FileEditor, create_file_editor_tool
    from .tools.file_reader import FileReader, create_file_reader_tool
    from .tools.file_writer import FileWriter, create_file_writer_tool
    from .tools.shell_command import ShellCommander, create_shell_command_tool
except ImportError:
    # Fall back to absolute imports (when run directly)
    from codebase_rag.config import settings
    from codebase_rag.graph_updater import MemgraphIngestor
    from codebase_rag.services.llm import CypherGenerator, create_rag_orchestrator
    from codebase_rag.tools.code_retrieval import (
        CodeRetriever,
        create_code_retrieval_tool,
    )
    from codebase_rag.tools.codebase_query import create_query_tool
    from codebase_rag.tools.directory_lister import (
        DirectoryLister,
        create_directory_lister_tool,
    )
    from codebase_rag.tools.document_analyzer import (
        DocumentAnalyzer,
        create_document_analyzer_tool,
    )
    from codebase_rag.tools.file_editor import FileEditor, create_file_editor_tool
    from codebase_rag.tools.file_reader import FileReader, create_file_reader_tool
    from codebase_rag.tools.file_writer import FileWriter, create_file_writer_tool
    from codebase_rag.tools.shell_command import (
        ShellCommander,
        create_shell_command_tool,
    )

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
rag_agent: Any | None = None
repo_path: Path | None = None
message_history: list[Any] = []


async def ensure_services() -> None:
    """Ensure all services and RAG agent are initialized."""
    global ingestor, rag_agent, repo_path

    if ingestor is None:
        ingestor = MemgraphIngestor(
            host=settings.MEMGRAPH_HOST, port=settings.MEMGRAPH_PORT
        )
        # Manually enter the context manager
        ingestor.__enter__()
        logger.info("Initialized MemgraphIngestor")

    if repo_path is None:
        repo_path = Path(settings.TARGET_REPO_PATH).resolve()
        logger.info(f"Set repository path to: {repo_path}")

    if rag_agent is None:
        # Initialize RAG agent with all tools (similar to main.py)
        logger.info("Initializing RAG agent with full tool set...")

        # Validate settings
        settings.validate_for_usage()

        # Initialize all services
        cypher_generator = CypherGenerator()
        code_retriever = CodeRetriever(project_root=str(repo_path), ingestor=ingestor)
        file_reader = FileReader(project_root=str(repo_path))
        file_writer = FileWriter(project_root=str(repo_path))
        file_editor = FileEditor(project_root=str(repo_path))
        shell_commander = ShellCommander(
            project_root=str(repo_path), timeout=settings.SHELL_COMMAND_TIMEOUT
        )
        directory_lister = DirectoryLister(project_root=str(repo_path))
        document_analyzer = DocumentAnalyzer(project_root=str(repo_path))

        # Create all tools
        from rich.console import Console

        console = Console(width=None, force_terminal=True)

        query_tool = create_query_tool(ingestor, cypher_generator, console)
        code_tool = create_code_retrieval_tool(code_retriever)
        file_reader_tool = create_file_reader_tool(file_reader)
        file_writer_tool = create_file_writer_tool(file_writer)
        file_editor_tool = create_file_editor_tool(file_editor)
        shell_command_tool = create_shell_command_tool(shell_commander)
        directory_lister_tool = create_directory_lister_tool(directory_lister)
        document_analyzer_tool = create_document_analyzer_tool(document_analyzer)

        # Create RAG orchestrator with all tools
        rag_agent = create_rag_orchestrator(
            tools=[
                query_tool,
                code_tool,
                file_reader_tool,
                file_writer_tool,
                file_editor_tool,
                shell_command_tool,
                directory_lister_tool,
                document_analyzer_tool,
            ]
        )
        logger.info("RAG agent initialized with full tool set")


@mcp.tool()
async def query_codebase(query: str) -> str:
    """Query the codebase using natural language with full RAG capabilities.

    This tool uses the complete RAG agent with all available tools to provide
    comprehensive answers about your codebase. It can query the knowledge graph,
    read files, analyze code, and provide detailed explanations.

    Examples:
    - "Find all functions that handle authentication"
    - "What classes are in the user module?"
    - "Show me functions with the longest call chains"
    - "Which files contain database operations?"
    - "Explain how the authentication system works"
    - "What are the main components of this application?"

    Args:
        query: Natural language question about the codebase
    """
    await ensure_services()

    try:
        import time

        start_time = time.time()

        logger.info(f"🤖 RAG Query: {query}")

        if rag_agent is None:
            return "❌ Error: RAG agent not initialized"

        # Use RAG agent to process the query (similar to run_chat_loop)
        response = await run_with_cancellation_mcp(
            rag_agent.run(query, message_history=message_history)
        )

        query_time = time.time() - start_time

        if isinstance(response, dict) and response.get("cancelled"):
            logger.warning("Query was cancelled")
            return "⚠️ Query was cancelled by user"

        # Extract the response output
        if hasattr(response, "output"):
            result_text = response.output
        elif isinstance(response, dict) and "output" in response:
            result_text = response["output"]
        else:
            result_text = str(response)

        # Add timing information
        result_text += f"\n\n⏱️ **Query processed in {query_time:.3f}s**"

        # Update message history
        if hasattr(response, "new_messages"):
            message_history.extend(response.new_messages())

        logger.info(f"✅ RAG query completed in {query_time:.3f}s")
        return str(result_text)

    except Exception as e:
        error_time = time.time() - start_time if "start_time" in locals() else 0
        logger.error(f"❌ Error in RAG query after {error_time:.3f}s: {e}")
        return f"❌ Error processing query: {str(e)}\n⏱️ Failed after: {error_time:.3f}s"


async def run_with_cancellation_mcp(coro: Any, timeout: float | None = None) -> Any:
    """Run a coroutine with proper cancellation handling for MCP context."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout) if timeout else await coro
    except TimeoutError:
        logger.warning("Query timed out")
        return {"cancelled": True, "timeout": True}
    except asyncio.CancelledError:
        logger.warning("Query was cancelled")
        return {"cancelled": True}
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise


@mcp.tool()
async def get_code_snippet(qualified_name: str) -> str:
    """Retrieve the source code for a specific function, class, or method using RAG agent.

    Args:
        qualified_name: Fully qualified name of the function, class, or method
                       Examples: "User.authenticate", "database.connection.connect"
    """
    # Use RAG agent to get code snippet with context
    query = f"Show me the source code for {qualified_name}. Include the file path, line numbers, and any docstring."
    result = await query_codebase(query)
    return str(result)


@mcp.tool()
async def get_codebase_summary() -> str:
    """Get a comprehensive summary of the codebase structure using RAG agent."""
    query = "Provide a comprehensive summary of this codebase. Include the main components, file types, programming languages used, project structure, and key functionality. Also show statistics about the codebase like file counts and node types in the knowledge graph."
    result = await query_codebase(query)
    return str(result)


@mcp.tool()
async def query_codebase_paginated(
    query: str, page: int = 1, page_size: int = 50
) -> str:
    """Query the codebase with pagination support using RAG agent.

    This tool is useful for large result sets that need to be browsed page by page.
    It uses the RAG agent to provide intelligent pagination and context.

    Args:
        query: Natural language question about the codebase
        page: Page number to retrieve (default: 1)
        page_size: Number of results per page (default: 50, max: 1000)
    """
    # Use RAG agent for paginated queries with context
    paginated_query = f"{query}. Please provide results in a paginated format for page {page} with {page_size} items per page. Include pagination information and navigation details."
    result = await query_codebase(paginated_query)
    return str(result)


@mcp.tool()
async def debug_query(cypher_query: str) -> str:
    """Execute a raw Cypher query and return detailed debugging information.

    This tool is useful for testing and debugging Cypher queries directly.
    It provides detailed execution statistics and formatted results.

    Args:
        cypher_query: Raw Cypher query to execute
    """
    await ensure_services()

    try:
        import time

        start_time = time.time()

        logger.info(f"🔧 Debug query: {cypher_query}")

        if ingestor is None:
            return "❌ Error: Memgraph ingestor not initialized"

        # Execute query with detailed timing
        logger.info("🔄 Executing debug query...")
        results = ingestor.fetch_all(cypher_query)

        query_time = time.time() - start_time

        # Format debug information
        debug_text = "🔧 **Debug Query Results**\n"
        debug_text += f"**Cypher Query:** `{cypher_query}`\n"
        debug_text += f"**Execution Time:** {query_time:.3f}s\n"
        debug_text += f"**Result Count:** {len(results)}\n\n"

        if results:
            # Show column information
            columns = list(results[0].keys())
            debug_text += f"**Columns:** {', '.join(columns)}\n\n"

            # Show first few results
            max_debug_results = min(5, len(results))
            debug_text += f"**First {max_debug_results} result(s):**\n"

            for i, row in enumerate(results[:max_debug_results], 1):
                debug_text += f"\n**Result {i}:**\n"
                for key, value in row.items():
                    if value is None:
                        debug_text += f"  • {key}: `null`\n"
                    elif isinstance(value, bool):
                        debug_text += f"  • {key}: {'✅' if value else '❌'}\n"
                    elif isinstance(value, int | float):
                        debug_text += f"  • {key}: `{value}`\n"
                    else:
                        str_value = str(value)
                        if len(str_value) > 100:
                            str_value = str_value[:97] + "..."
                        debug_text += f"  • {key}: `{str_value}`\n"

            if len(results) > max_debug_results:
                debug_text += (
                    f"\n... and {len(results) - max_debug_results} more results"
                )
        else:
            debug_text += "📭 No results returned"

        logger.info(f"✅ Debug query completed in {query_time:.3f}s")
        return debug_text

    except Exception as e:
        error_time = time.time() - start_time if "start_time" in locals() else 0
        logger.error(f"❌ Debug query failed after {error_time:.3f}s: {e}")
        return f"❌ Debug query error: {str(e)}\n⏱️ Failed after: {error_time:.3f}s"


@mcp.tool()
async def analyze_code_structure() -> str:
    """Analyze the overall code structure and architecture using RAG agent."""
    query = "Analyze the codebase structure and architecture. Identify the main components, design patterns used, dependencies between modules, and overall architecture style. Provide insights about how the code is organized."
    result = await query_codebase(query)
    return str(result)


@mcp.tool()
async def find_code_patterns(pattern_description: str) -> str:
    """Find specific code patterns or implementations using RAG agent.

    Args:
        pattern_description: Description of the pattern to find (e.g., "authentication", "database connections", "error handling")
    """
    query = f"Find and analyze code patterns related to: {pattern_description}. Show me examples of how this pattern is implemented throughout the codebase, including file locations and code snippets."
    result = await query_codebase(query)
    return str(result)


@mcp.tool()
async def explain_code_flow(starting_point: str) -> str:
    """Explain how code flows from a specific starting point using RAG agent.

    Args:
        starting_point: The starting point for code flow analysis (e.g., "main function", "API endpoint", "user login")
    """
    query = f"Explain the code flow starting from: {starting_point}. Trace through the execution path, show me the key functions and methods called, and explain how data flows through the system."
    result = await query_codebase(query)
    return str(result)


@mcp.tool()
async def get_dependencies(component: str) -> str:
    """Get dependencies and relationships for a specific component using RAG agent.

    Args:
        component: The component to analyze (e.g., "User class", "database module", "authentication service")
    """
    query = f"Show me the dependencies and relationships for: {component}. Include what this component depends on, what depends on it, and how it integrates with the rest of the system."
    result = await query_codebase(query)
    return str(result)


@mcp.tool()
async def suggest_improvements() -> str:
    """Get suggestions for code improvements using RAG agent."""
    query = "Analyze this codebase and suggest potential improvements. Look for code quality issues, performance optimizations, security concerns, maintainability improvements, and best practices that could be applied."
    result = await query_codebase(query)
    return str(result)


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
        http_mcp.tool()(query_codebase_paginated)
        http_mcp.tool()(get_code_snippet)
        http_mcp.tool()(get_codebase_summary)
        http_mcp.tool()(debug_query)
        http_mcp.tool()(analyze_code_structure)
        http_mcp.tool()(find_code_patterns)
        http_mcp.tool()(explain_code_flow)
        http_mcp.tool()(get_dependencies)
        http_mcp.tool()(suggest_improvements)
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
