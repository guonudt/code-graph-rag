#!/usr/bin/env python3
"""
Unified MCP Configuration Generator
为STDIO和HTTP两种传输模式生成客户端配置
"""

import json
import os
import socket
from pathlib import Path
from typing import Any


def get_local_ip() -> str:
    """获取本机IP地址"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            return str(ip)
    except Exception:
        return "localhost"


def detect_model_config() -> tuple[dict[str, str], str]:
    """检测当前模型配置"""
    env_vars = {}

    # 检查本地模型配置
    if os.getenv("LOCAL_MODEL_ENDPOINT"):
        env_vars.update(
            {
                "LOCAL_MODEL_ENDPOINT": os.getenv(
                    "LOCAL_MODEL_ENDPOINT", "http://localhost:11434/v1"
                ),
                "LOCAL_ORCHESTRATOR_MODEL_ID": os.getenv(
                    "LOCAL_ORCHESTRATOR_MODEL_ID", "llama3"
                ),
                "LOCAL_CYPHER_MODEL_ID": os.getenv("LOCAL_CYPHER_MODEL_ID", "llama3"),
                "LOCAL_MODEL_API_KEY": os.getenv("LOCAL_MODEL_API_KEY", "ollama"),
            }
        )
        return env_vars, "local"

    # 检查 Gemini 配置
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        env_vars["GEMINI_API_KEY"] = gemini_key
        return env_vars, "gemini"

    # 检查 OpenAI 配置
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        env_vars.update(
            {
                "OPENAI_API_KEY": openai_key,
                "OPENAI_ORCHESTRATOR_MODEL_ID": os.getenv(
                    "OPENAI_ORCHESTRATOR_MODEL_ID", "gpt-4o-mini"
                ),
                "OPENAI_CYPHER_MODEL_ID": os.getenv(
                    "OPENAI_CYPHER_MODEL_ID", "gpt-4o-mini"
                ),
            }
        )
        return env_vars, "openai"

    # 默认使用本地模型
    env_vars.update(
        {
            "LOCAL_MODEL_ENDPOINT": "http://localhost:11434/v1",
            "LOCAL_ORCHESTRATOR_MODEL_ID": "llama3",
            "LOCAL_CYPHER_MODEL_ID": "llama3",
            "LOCAL_MODEL_API_KEY": "ollama",
        }
    )
    return env_vars, "local"


def generate_stdio_config(
    project_path: str, model_type: str = "auto"
) -> dict[str, Any]:
    """生成STDIO模式的MCP客户端配置"""

    # 基础环境变量
    base_env = {
        "TARGET_REPO_PATH": project_path,
        "MEMGRAPH_HOST": "localhost",
        "MEMGRAPH_PORT": "7687",
    }

    # 检测或使用指定的模型配置
    if model_type == "auto":
        detected_env, detected_type = detect_model_config()
        env_vars = {**base_env, **detected_env}
        model_suffix = f" ({detected_type.title()})"
    else:
        env_vars = base_env.copy()
        model_suffix = f" ({model_type.title()})"

        if model_type == "local":
            env_vars.update(
                {
                    "LOCAL_MODEL_ENDPOINT": "http://localhost:11434/v1",
                    "LOCAL_ORCHESTRATOR_MODEL_ID": "llama3",
                    "LOCAL_CYPHER_MODEL_ID": "llama3",
                    "LOCAL_MODEL_API_KEY": "ollama",
                }
            )
        elif model_type == "gemini":
            env_vars["GEMINI_API_KEY"] = "your_gemini_api_key_here"
        elif model_type == "openai":
            env_vars.update(
                {
                    "OPENAI_API_KEY": "your_openai_api_key_here",
                    "OPENAI_ORCHESTRATOR_MODEL_ID": "gpt-4o-mini",
                    "OPENAI_CYPHER_MODEL_ID": "gpt-4o-mini",
                }
            )

    config = {
        "mcpServers": {
            "code-graph-rag": {
                "name": f"Code Graph RAG{model_suffix}",
                "type": "STDIO",
                "command": "uv",
                "args": [
                    "--directory",
                    project_path,
                    "run",
                    "codebase_rag/mcp_server.py",
                    "stdio",
                ],
                "env": env_vars,
                "description": "Code Graph RAG MCP Server via STDIO transport",
            }
        }
    }

    return config


def generate_http_config(
    project_path: str,
    host: str = "localhost",
    port: int = 7444,
    project_name: str = "code-graph-rag",
) -> dict[str, Any]:
    """生成HTTP模式的MCP客户端配置"""

    base_url = f"http://{host}:{port}"
    sse_url = f"{base_url}/sse"

    configs = {
        "cherry_studio": {
            "mcpServers": {
                f"{project_name}-http": {
                    "name": "Code Graph RAG (HTTP)",
                    "type": "HTTP",
                    "url": sse_url,
                    "description": "Code Graph RAG MCP Server via HTTP transport",
                }
            }
        },
        "claude_desktop": {
            "mcpServers": {
                f"{project_name}-http": {
                    "command": "curl",
                    "args": [
                        "-X",
                        "POST",
                        "-H",
                        "Content-Type: application/json",
                        "-d",
                        "@-",
                        sse_url,
                    ],
                    "env": {},
                    "description": "Code Graph RAG MCP Server via HTTP transport",
                }
            }
        },
        "generic_client": {
            "server_url": sse_url,
            "health_url": f"{base_url}/health",
            "transport": "HTTP/SSE",
            "description": "Generic HTTP MCP client configuration",
        },
    }

    return configs


def main() -> None:
    """主函数"""
    print("🚀 Unified MCP Configuration Generator")
    print("=" * 50)

    # 获取项目路径
    project_path = str(Path(__file__).parent.resolve())
    print(f"📁 Project path: {project_path}")

    # 检测模型配置
    detected_env, detected_type = detect_model_config()
    print(f"🤖 Detected model type: {detected_type}")

    if detected_type == "local":
        print("   - Local model (Ollama)")
        print(f"   - Endpoint: {detected_env.get('LOCAL_MODEL_ENDPOINT')}")
        print(f"   - Model: {detected_env.get('LOCAL_ORCHESTRATOR_MODEL_ID')}")
    elif detected_type == "gemini":
        print("   - Gemini model")
        print("   - API key: configured")
    elif detected_type == "openai":
        print("   - OpenAI model")
        print("   - API key: configured")

    # 生成STDIO配置
    print("\n📡 Generating STDIO configuration...")
    stdio_config = generate_stdio_config(project_path, "auto")

    # 生成HTTP配置
    print("🌐 Generating HTTP configuration...")
    host = get_local_ip()
    port = 7444
    http_configs = generate_http_config(project_path, host, port)

    # 保存配置文件
    stdio_config_file = "mcp_stdio_config.json"
    cherry_http_config_file = "mcp_http_config.json"
    claude_http_config_file = "claude_desktop_http_config.json"
    generic_config_file = "generic_http_config.json"

    with open(stdio_config_file, "w", encoding="utf-8") as f:
        json.dump(stdio_config, f, indent=2, ensure_ascii=False)

    with open(cherry_http_config_file, "w", encoding="utf-8") as f:
        json.dump(http_configs["cherry_studio"], f, indent=2, ensure_ascii=False)

    with open(claude_http_config_file, "w", encoding="utf-8") as f:
        json.dump(http_configs["claude_desktop"], f, indent=2, ensure_ascii=False)

    with open(generic_config_file, "w", encoding="utf-8") as f:
        json.dump(http_configs["generic_client"], f, indent=2, ensure_ascii=False)

    print("\n✅ Configuration files generated:")
    print(f"  - STDIO: {stdio_config_file}")
    print(f"  - Cherry Studio HTTP: {cherry_http_config_file}")
    print(f"  - Claude Desktop HTTP: {claude_http_config_file}")
    print(f"  - Generic HTTP: {generic_config_file}")

    # 显示配置内容
    print("\n📋 STDIO Configuration:")
    print(json.dumps(stdio_config, indent=2, ensure_ascii=False))

    print("\n📋 Cherry Studio HTTP Configuration:")
    print(json.dumps(http_configs["cherry_studio"], indent=2, ensure_ascii=False))

    print("\n📋 Claude Desktop HTTP Configuration:")
    print(json.dumps(http_configs["claude_desktop"], indent=2, ensure_ascii=False))

    # 显示使用说明
    print("\n🚀 Usage Instructions:")
    print("1. Start MCP server:")
    print(f"   STDIO: ./start_mcp_server.sh {project_path} stdio")
    print(f"   HTTP:  ./start_mcp_server.sh {project_path} http {port}")
    print("\n2. Test server:")
    print("   uv run pytest test/test_mcp_unified.py -v")
    print("\n3. Configure clients:")
    print(f"   Cherry Studio STDIO: Copy {stdio_config_file}")
    print(f"   Cherry Studio HTTP:  Copy {cherry_http_config_file}")
    print(f"   Claude Desktop HTTP: Copy {claude_http_config_file}")

    print("\n🌐 Server endpoints (HTTP mode):")
    print(f"  - SSE: http://{host}:{port}/sse")
    print(f"  - Health: http://{host}:{port}/health")

    print("\n📚 More information:")
    print("  - Server: codebase_rag/mcp_server.py")
    print("  - Start script: scripts/start_mcp_server.sh")
    print("  - Test suite: codebase_rag/tests/test_mcp_unified.py")


if __name__ == "__main__":
    main()
