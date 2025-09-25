#!/bin/bash

# Code Graph RAG MCP Server Startup Script
# 支持STDIO和HTTP两种传输模式的统一启动脚本

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Code Graph RAG MCP Server${NC}"
echo -e "${BLUE}==========================${NC}"

# Check if repository path is provided
if [ $# -eq 0 ]; then
    echo -e "${YELLOW}Usage: $0 <repository_path> [transport_mode] [port] [api_key]${NC}"
    echo -e "${YELLOW}Transport modes: stdio (default), http${NC}"
    echo -e "${YELLOW}Examples:${NC}"
    echo -e "${YELLOW}  $0 /path/to/your/repo                    # STDIO mode${NC}"
    echo -e "${YELLOW}  $0 /path/to/your/repo http 7444          # HTTP mode on port 7444${NC}"
    echo -e "${YELLOW}  $0 /path/to/your/repo stdio              # STDIO mode (explicit)${NC}"
    echo -e "${BLUE}Note: If no API key provided, will use local models if configured${NC}"
    exit 1
fi

REPO_PATH="$1"
TRANSPORT_MODE="${2:-stdio}"
HTTP_PORT="${3:-7444}"
API_KEY="${4:-}"

# Validate transport mode
if [[ "$TRANSPORT_MODE" != "stdio" && "$TRANSPORT_MODE" != "http" ]]; then
    echo -e "${RED}Error: Invalid transport mode '$TRANSPORT_MODE'. Use 'stdio' or 'http'${NC}"
    exit 1
fi

# Check if repository exists
if [ ! -d "$REPO_PATH" ]; then
    echo -e "${RED}Error: Repository path '$REPO_PATH' does not exist${NC}"
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Warning: .env file not found. Creating a template...${NC}"
    cat > .env << EOF
# Code Graph RAG Configuration
GEMINI_API_KEY=${API_KEY}
MEMGRAPH_HOST=localhost
MEMGRAPH_PORT=7687
MEMGRAPH_HTTP_PORT=${HTTP_PORT}
TARGET_REPO_PATH=${REPO_PATH}

# Optional: OpenAI Configuration
# OPENAI_API_KEY=your_openai_api_key_here

# Optional: Local Model Configuration (uncomment to use local models)
# LOCAL_MODEL_ENDPOINT=http://localhost:11434/v1
# LOCAL_ORCHESTRATOR_MODEL_ID=llama3
# LOCAL_CYPHER_MODEL_ID=llama3
# LOCAL_MODEL_API_KEY=ollama
EOF
    echo -e "${GREEN}Created .env file with template configuration${NC}"
fi

# Check if Memgraph is running
echo -e "${BLUE}Checking Memgraph connection...${NC}"
if ! nc -z localhost 7687 2>/dev/null; then
    echo -e "${RED}Error: Memgraph is not running on localhost:7687${NC}"
    echo -e "${YELLOW}Please start Memgraph first:${NC}"
    echo -e "${YELLOW}  docker-compose up -d${NC}"
    exit 1
fi

echo -e "${GREEN}Memgraph is running${NC}"

# For HTTP mode, check if port is available
if [[ "$TRANSPORT_MODE" == "http" ]]; then
    echo -e "${BLUE}Checking if port ${HTTP_PORT} is available...${NC}"
    if nc -z localhost ${HTTP_PORT} 2>/dev/null; then
        echo -e "${YELLOW}Warning: Port ${HTTP_PORT} is already in use${NC}"
        echo -e "${YELLOW}Please choose a different port or stop the service using this port${NC}"
        exit 1
    fi
    echo -e "${GREEN}Port ${HTTP_PORT} is available${NC}"
fi

# Display server information
echo -e "${BLUE}MCP Server Configuration:${NC}"
echo -e "${YELLOW}Repository: $REPO_PATH${NC}"
echo -e "${YELLOW}Transport Mode: $TRANSPORT_MODE${NC}"

if [[ "$TRANSPORT_MODE" == "http" ]]; then
    echo -e "${YELLOW}HTTP Port: $HTTP_PORT${NC}"
    echo -e "${YELLOW}SSE Endpoint: http://localhost:${HTTP_PORT}/sse${NC}"
    echo -e "${YELLOW}Health Check: http://localhost:${HTTP_PORT}/health${NC}"

    # Display client configuration examples
    echo -e "${BLUE}Client Configuration Examples:${NC}"
    echo -e "${YELLOW}Cherry Studio:${NC}"
    echo -e "${YELLOW}  {\"mcpServers\": {\"code-graph-rag\": {\"url\": \"http://localhost:${HTTP_PORT}/sse\"}}}${NC}"
    echo -e "${YELLOW}Claude Desktop:${NC}"
    echo -e "${YELLOW}  {\"mcpServers\": {\"code-graph-rag\": {\"url\": \"http://localhost:${HTTP_PORT}/sse\"}}}${NC}"
else
    echo -e "${YELLOW}STDIO Mode: Direct process communication${NC}"
    echo -e "${BLUE}Client Configuration:${NC}"
    echo -e "${YELLOW}Cherry Studio: Use STDIO configuration${NC}"
    echo -e "${YELLOW}Claude Desktop: Use STDIO configuration${NC}"
fi

# Start the MCP server
echo -e "${BLUE}Starting MCP server for repository: $REPO_PATH${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
echo ""

# Set environment variables
export TARGET_REPO_PATH="$REPO_PATH"
export MCP_TRANSPORT="$TRANSPORT_MODE"

if [[ "$TRANSPORT_MODE" == "http" ]]; then
    export MCP_PORT="$HTTP_PORT"
fi

# Start the server using python -m
if [[ "$TRANSPORT_MODE" == "http" ]]; then
    python -m codebase_rag.mcp_server http
else
    python -m codebase_rag.mcp_server stdio
fi
