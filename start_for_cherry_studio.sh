#!/bin/bash

# Cherry Studio MCP Server启动脚本
# 确保在正确的环境中启动MCP服务器

# 设置项目根目录
PROJECT_ROOT="/Users/guoshuai/git/code-graph-rag"
cd "$PROJECT_ROOT"

# 激活虚拟环境
source venv/bin/activate

# 启动MCP服务器
exec python -m codebase_rag.mcp_server stdio
