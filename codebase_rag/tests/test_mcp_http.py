#!/usr/bin/env python3
"""
MCP服务器HTTP模式功能测试 - 测试MCP工具的实际功能
"""

import asyncio
import socket
import subprocess
import sys
import time
from pathlib import Path

from mcp import ClientSession
from mcp.client.sse import sse_client

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def is_port_available(host: str, port: int) -> bool:
    """检查端口是否可用"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((host, port))
        return False  # 端口被占用
    except OSError:
        return True  # 端口可用
    finally:
        sock.close()


def start_server(port: int) -> subprocess.Popen:
    """启动HTTP服务器"""
    env = {
        "TARGET_REPO_PATH": str(project_root),
        "MEMGRAPH_HOST": "localhost",
        "MEMGRAPH_PORT": "7687",
        "LOCAL_MODEL_ENDPOINT": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "LOCAL_ORCHESTRATOR_MODEL_ID": "qwen3-coder-plus",
        "LOCAL_CYPHER_MODEL_ID": "qwen3-coder-plus",
        "LOCAL_MODEL_API_KEY": "sk-cc8763a2fede4939948a45609d83ab8d",
        "MCP_TRANSPORT": "http",
        "MCP_PORT": str(port),
    }

    cmd = [sys.executable, "-m", "codebase_rag.mcp_server", "http"]

    process = subprocess.Popen(
        cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=project_root
    )

    # 等待服务器启动
    time.sleep(5)
    return process


def stop_server(process: subprocess.Popen) -> None:
    """停止服务器"""
    if process:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


async def test_all_tools_http(port: int) -> bool:
    """通过HTTP模式测试所有MCP工具功能"""
    try:
        # 使用SSE客户端连接HTTP服务器
        async with sse_client(f"http://localhost:{port}/sse") as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                # 初始化
                init_result = await session.initialize()
                print(f"✅ 服务器初始化成功: {init_result.serverInfo.name}")

                # 列出工具
                tools_result = await session.list_tools()
                print(f"✅ 找到 {len(tools_result.tools)} 个工具:")
                for tool in tools_result.tools:
                    print(f"  - {tool.name}: {tool.description}")

                # 逐个测试每个工具
                success_count = 0
                total_tools = len(tools_result.tools)

                for tool in tools_result.tools:
                    tool_name = tool.name
                    print(f"\n🧪 测试工具: {tool_name}")

                    try:
                        if tool_name == "query_codebase":
                            result = await session.call_tool(
                                tool_name, {"query": "Find all Python files"}
                            )
                            result_text = result.content[0].text
                            assert "Query:" in result_text
                            assert "Generated Cypher:" in result_text
                            print(f"✅ {tool_name} 测试通过")

                        elif tool_name == "get_code_snippet":
                            result = await session.call_tool(
                                tool_name,
                                {"qualified_name": "mcp_server.query_codebase"},
                            )
                            result_text = result.content[0].text
                            print(f"get_code_snippet 结果: {result_text[:200]}...")
                            # 检查是否找到代码片段或返回了错误信息
                            if (
                                "Code snippet for:" in result_text
                                or "not found" in result_text.lower()
                            ):
                                print(f"✅ {tool_name} 测试通过")
                            else:
                                print(f"❌ {tool_name} 返回意外结果")
                                continue

                        elif tool_name == "get_codebase_summary":
                            result = await session.call_tool(tool_name, {})
                            result_text = result.content[0].text
                            assert "Codebase Summary" in result_text
                            assert "Node Statistics" in result_text
                            print(f"✅ {tool_name} 测试通过")

                        elif tool_name == "health_check":
                            result = await session.call_tool(tool_name, {})
                            result_text = result.content[0].text
                            assert "healthy" in result_text.lower()
                            assert "Memgraph connection: OK" in result_text
                            print(f"✅ {tool_name} 测试通过")

                        else:
                            print(f"⚠️ 未知工具: {tool_name}")
                            continue

                        success_count += 1

                    except Exception as e:
                        print(f"❌ {tool_name} 测试失败: {e}")

                print(f"\n📊 测试结果: {success_count}/{total_tools} 个工具测试通过")
                return success_count == total_tools

    except Exception as e:
        print(f"❌ MCP工具测试失败: {e}")
        return False


async def run_http_tests() -> bool:
    """运行HTTP模式测试"""
    # 找一个可用的端口
    port = 7447
    while not is_port_available("localhost", port):
        port += 1

    print(f"使用端口: {port}")

    process = None
    try:
        process = start_server(port)

        # 检查进程是否还在运行
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            print("服务器启动失败:")
            print(f"STDOUT: {stdout.decode()}")
            print(f"STDERR: {stderr.decode()}")
            return False

        # 测试所有MCP工具功能
        success = await test_all_tools_http(port)
        return success

    except Exception as e:
        print(f"测试异常: {e}")
        return False
    finally:
        if process:
            stop_server(process)


if __name__ == "__main__":
    print("🧪 测试MCP服务器HTTP模式 - 所有工具功能测试...")

    try:
        success = asyncio.run(run_http_tests())
        if success:
            print("\n🎉 HTTP模式所有工具测试通过！")
        else:
            print("\n❌ HTTP模式工具测试失败")

        sys.exit(0 if success else 1)

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        sys.exit(1)
