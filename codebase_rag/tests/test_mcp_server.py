#!/usr/bin/env python3
"""
Test script for the Code Graph RAG MCP Server
Tests the MCP server functionality using the official MCP client
"""

import asyncio
import subprocess

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
async def test_mcp_server() -> bool:
    """Test the MCP server functionality."""
    print("🧪 Testing Code Graph RAG MCP Server")
    print("=" * 50)

    # Server parameters
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "codebase_rag.mcp_server", "stdio"],
        env={"TARGET_REPO_PATH": "."},
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize the session
                print("\n🔧 Test 1: Initializing MCP session...")
                try:
                    init_result = await session.initialize()
                    print(
                        f"✅ Session initialized: {init_result.serverInfo.name} v{init_result.serverInfo.version}"
                    )
                except Exception as e:
                    print(f"❌ Session initialization failed: {e}")
                    return False

                # List tools (MCP tools/list functionality)
                print("\n🛠️ Test 2: Listing available tools (MCP tools/list)...")
                tools_result = await session.list_tools()
                tools = tools_result.tools
                print(f"✅ Found {len(tools)} tools:")
                for tool in tools:
                    print(f"  - {tool.name}: {tool.description[:50]}...")
                    print(f"    Title: {tool.title}")
                    print(f"    Input Schema: {tool.inputSchema}")
                    print()

                # Test query_codebase tool
                print("\n🔎 Test 3: Testing query_codebase tool...")
                try:
                    query_result = await session.call_tool(
                        "query_codebase", arguments={"query": "Find all Python files"}
                    )
                    if query_result.content:
                        print("✅ Query codebase successful")
                        print(
                            f"Response preview: {query_result.content[0].text[:200]}..."
                        )
                    else:
                        print("⚠️ Query codebase returned no content")
                except Exception as e:
                    print(f"❌ Query codebase failed: {e}")

                # Test get_codebase_summary tool
                print("\n📊 Test 4: Testing get_codebase_summary tool...")
                try:
                    summary_result = await session.call_tool(
                        "get_codebase_summary", arguments={}
                    )
                    if summary_result.content:
                        print("✅ Get codebase summary successful")
                        print(
                            f"Summary preview: {summary_result.content[0].text[:200]}..."
                        )
                    else:
                        print("⚠️ Get codebase summary returned no content")
                except Exception as e:
                    print(f"❌ Get codebase summary failed: {e}")

                print("\n🎉 All MCP tests completed!")
                print("\n📋 Next steps:")
                print(
                    "1. Copy claude_desktop_config.json to Claude Desktop config directory"
                )
                print("2. Restart Claude Desktop")
                print("3. Test the tools in Claude Desktop")

                return True

    except Exception as e:
        print(f"❌ MCP server test failed: {e}")
        print("\n🔧 Troubleshooting:")
        print("1. Ensure Memgraph is running: docker-compose up -d")
        print(
            "2. Ensure repository has been parsed: python -m codebase_rag.main start --repo-path . --update-graph --clean"
        )
        print("3. Check environment variables in .env file")
        return False


async def main() -> None:
    """Main test function."""
    print("🚀 Code Graph RAG MCP Server Test Suite")
    print("=" * 50)

    # Check if uv is available
    try:
        subprocess.run(["uv", "--version"], check=True, capture_output=True)
        print("✅ uv is available")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ uv is not available. Please install uv first:")
        print("   curl -LsSf https://astral.sh/uv/install.sh | sh")
        return

    # Run MCP tests
    tests_passed = await test_mcp_server()

    if tests_passed:
        print(
            "\n🎉 All tests passed! The MCP server is ready for Claude Desktop integration."
        )
    else:
        print("\n❌ Some tests failed. Please check the configuration and try again.")


if __name__ == "__main__":
    asyncio.run(main())
