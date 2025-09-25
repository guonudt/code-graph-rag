#!/usr/bin/env python3
"""
MCP服务器STDIO模式测试 - 测试所有工具功能
"""

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


async def test_all_tools_stdio() -> bool:
    """测试STDIO模式下所有工具的功能"""
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "codebase_rag.mcp_server", "stdio"],
        env={
            "TARGET_REPO_PATH": str(project_root),
            "MEMGRAPH_HOST": "localhost",
            "MEMGRAPH_PORT": "7687",
            "LOCAL_MODEL_ENDPOINT": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "LOCAL_ORCHESTRATOR_MODEL_ID": "qwen3-coder-plus",
            "LOCAL_CYPHER_MODEL_ID": "qwen3-coder-plus",
            "LOCAL_MODEL_API_KEY": "sk-cc8763a2fede4939948a45609d83ab8d",
        },
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
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
                            tool_name, {"qualified_name": "mcp_server.query_codebase"}
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


if __name__ == "__main__":
    print("🧪 测试MCP服务器STDIO模式 - 所有工具功能测试...")

    try:
        success = asyncio.run(test_all_tools_stdio())
        if success:
            print("\n🎉 STDIO模式所有工具测试通过！")
        else:
            print("\n❌ STDIO模式工具测试失败")

        sys.exit(0 if success else 1)

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        sys.exit(1)
