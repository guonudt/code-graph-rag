<div align="center">
  <picture>
    <source srcset="assets/logo-dark-any.png" media="(prefers-color-scheme: dark)">
    <source srcset="assets/logo-light-any.png" media="(prefers-color-scheme: light)">
    <img src="assets/logo-dark.png" alt="Graph-Code Logo" width="480">
  </picture>

  <p>
  <a href="https://github.com/vitali87/code-graph-rag/stargazers">
    <img src="https://img.shields.io/github/stars/vitali87/code-graph-rag?style=social" alt="GitHub stars" />
  </a>
  <a href="https://github.com/vitali87/code-graph-rag/network/members">
    <img src="https://img.shields.io/github/forks/vitali87/code-graph-rag?style=social" alt="GitHub forks" />
  </a>
  <a href="https://github.com/vitali87/code-graph-rag/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/vitali87/code-graph-rag" alt="License" />
  </a>
</p>
</div>

# Graph-Code: A Graph-Based RAG System for Any Codebases

An accurate Retrieval-Augmented Generation (RAG) system that analyzes multi-language codebases using Tree-sitter, builds comprehensive knowledge graphs, and enables natural language querying of codebase structure and relationships as well as editing capabilities.

## 🚀 Code Graph RAG MCP Server

基于Model Context Protocol (MCP)的代码库知识图谱查询服务器，支持STDIO和HTTP两种传输模式，可与Cherry Studio、Claude Desktop等MCP客户端无缝集成。

## ✨ 核心特性

### MCP 服务器特性
- **🌐 双传输模式**：支持STDIO（本地）和HTTP（远程）两种传输方式
- **🧠 智能查询**：使用自然语言查询代码库知识图谱
- **🔍 代码检索**：精确获取函数、类、方法的源代码
- **📊 代码分析**：提供代码库结构摘要和统计信息
- **🛡️ 健康监控**：内置健康检查和状态监控
- **🔧 多模型支持**：支持Gemini、OpenAI、本地模型（Ollama）

### 系统核心特性
- **🌍 Multi-Language Support**:

  | Language | Status | Extensions | Functions | Classes/Structs | Modules | Package Detection | Additional Features |
  |----------|--------|------------|-----------|-----------------|---------|-------------------|---------------------|
  | ✅ Python | **Fully Supported** | `.py` | ✅ | ✅ | ✅ | `__init__.py` | Type inference, decorators, nested functions |
  | ✅ JavaScript | **Fully Supported** | `.js`, `.jsx` | ✅ | ✅ | ✅ | - | ES6 modules, CommonJS, prototype methods, object methods, arrow functions |
  | ✅ TypeScript | **Fully Supported** | `.ts`, `.tsx` | ✅ | ✅ | ✅ | - | Interfaces, type aliases, enums, namespaces, ES6/CommonJS modules |
  | ✅ C++ | **Fully Supported** | `.cpp`, `.h`, `.hpp`, `.cc`, `.cxx`, `.hxx`, `.hh`, `.ixx`, `.cppm`, `.ccm` | ✅ | ✅ (classes/structs/unions/enums) | ✅ | CMakeLists.txt, Makefile | Constructors, destructors, operator overloading, templates, lambdas, C++20 modules, namespaces |
  | ✅ Lua | **Fully Supported** | `.lua` | ✅ | ✅ (tables/modules) | ✅ | - | Local/global functions, metatables, closures, coroutines |
  | ✅ Rust | **Fully Supported** | `.rs` | ✅ | ✅ (structs/enums) | ✅ | - | impl blocks, associated functions |
  | ✅ Java | **Fully Supported** | `.java` | ✅ | ✅ (classes/interfaces/enums) | ✅ | package declarations | Generics, annotations, modern features (records/sealed classes), concurrency, reflection |
  | 🚧 Go | In Development | `.go` | ✅ | ✅ (structs) | ✅ | - | Methods, type declarations |
  | 🚧 Scala | In Development | `.scala`, `.sc` | ✅ | ✅ (classes/objects/traits) | ✅ | package declarations | Case classes, objects |
  | 🚧 C# | In Development | `.cs` | - | - | - | - | Classes, interfaces, generics (planned) |

- **🌳 Tree-sitter Parsing**: Uses Tree-sitter for robust, language-agnostic AST parsing
- **📊 Knowledge Graph Storage**: Uses Memgraph to store codebase structure as an interconnected graph
- **🗣️ Natural Language Querying**: Ask questions about your codebase in plain English
- **🤖 AI-Powered Cypher Generation**: Supports both cloud models (Google Gemini), local models (Ollama), and OpenAI models for natural language to Cypher translation
- **🤖 OpenAI Integration**: Leverage OpenAI models to enhance AI functionalities.
- **📝 Code Snippet Retrieval**: Retrieves actual source code snippets for found functions/methods
- **✍️ Advanced File Editing**: Surgical code replacement with AST-based function targeting, visual diff previews, and exact code block modifications
- **⚡️ Shell Command Execution**: Can execute terminal commands for tasks like running tests or using CLI tools.
- **🚀 Interactive Code Optimization**: AI-powered codebase optimization with language-specific best practices and interactive approval workflow
- **📚 Reference-Guided Optimization**: Use your own coding standards and architectural documents to guide optimization suggestions
- **🔗 Dependency Analysis**: Parses `pyproject.toml` to understand external dependencies
- **🎯 Nested Function Support**: Handles complex nested functions and class hierarchies
- **🔄 Language-Agnostic Design**: Unified graph schema across all supported languages

## 🏗️ Architecture

The system consists of two main components:

1. **Multi-language Parser**: Tree-sitter based parsing system that analyzes codebases and ingests data into Memgraph
2. **RAG System** (`codebase_rag/`): Interactive CLI for querying the stored knowledge graph
3. **MCP Server**: Model Context Protocol server for integration with MCP clients

## 📋 Prerequisites

- Python 3.12+
- Docker & Docker Compose (for Memgraph)
- **cmake** (required for building pymgclient dependency)
- **For cloud models**: Google Gemini API key
- **For local models**: Ollama installed and running
- `uv` package manager

### Installing cmake

On macOS:
```bash
brew install cmake
```

On Linux (Ubuntu/Debian):
```bash
sudo apt-get update
sudo apt-get install cmake
```

On Linux (CentOS/RHEL):
```bash
sudo yum install cmake
# or on newer versions:
sudo dnf install cmake
```

## 🛠️ Makefile Updates

Use the Makefile for:
- **make install**: Install project dependencies with full language support.
- **make python**: Install dependencies for Python only.
- **make dev**: Setup dev environment (install deps + pre-commit hooks).
- **make test**: Run all tests.
- **make clean**: Clean up build artifacts and cache.
- **make help**: Show available commands.

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone https://github.com/vitali87/code-graph-rag.git
cd code-graph-rag
```

### 2. 安装依赖

For basic Python support:
```bash
uv sync
```

For full multi-language support:
```bash
uv sync --extra treesitter-full
```

For development (including tests and pre-commit hooks):
```bash
make dev
```

### 3. 配置环境变量

```bash
cp .env.example .env
# Edit .env with your configuration (see options below)
```

#### Configuration Options

#### Option 1: Cloud Models (Gemini)

```bash
# .env file
GEMINI_API_KEY=your_gemini_api_key_here
```
Get your free API key from [Google AI Studio](https://aistudio.google.com/app/apikey).

#### Option 2: OpenAI Models
```bash
# .env file
OPENAI_API_KEY=your_openai_api_key_here
```

#### Option 3: Local Models (Ollama)
```bash
# .env file
LOCAL_MODEL_ENDPOINT=http://localhost:11434/v1
LOCAL_ORCHESTRATOR_MODEL_ID=llama3
LOCAL_CYPHER_MODEL_ID=llama3
LOCAL_MODEL_API_KEY=ollama
```

**Install and run Ollama**:
```bash
# Install Ollama (macOS/Linux)
curl -fsSL https://ollama.ai/install.sh | sh

# Pull required models
ollama pull llama3
# Or try other models like:
# ollama pull llama3.1
# ollama pull mistral
# ollama pull codellama

# Ollama will automatically start serving on localhost:11434
```

> **Note**: Local models provide privacy and no API costs, but may have lower accuracy compared to cloud models like Gemini.

### 4. 启动Memgraph数据库

```bash
docker-compose up -d
```

### 5. 解析代码库到知识图谱

```bash
python -m codebase_rag.main start --repo-path . --update-graph --clean
```

### 6. 启动MCP服务器

#### STDIO模式（本地集成）
```bash
# 启动STDIO服务器
./start_mcp_server.sh /path/to/your/repo stdio

# 或直接启动
python -m codebase_rag.mcp_server stdio
```

#### HTTP模式（远程集成）
```bash
# 启动HTTP服务器（默认端口7445）
./start_mcp_server.sh /path/to/your/repo http

# 指定自定义端口
./start_mcp_server.sh /path/to/your/repo http 8080

# 或直接启动
python -m codebase_rag.mcp_server http
```

### 7. 生成客户端配置

```bash
# 自动生成所有客户端配置文件
python config/generate_mcp_config.py
```

### 8. 测试服务器

```bash
# 运行HTTP模式测试
python codebase_rag/tests/test_http_mcp_server.py

# 运行STDIO模式测试
python codebase_rag/tests/test_mcp_server.py
```

## 🛠️ 可用工具

MCP服务器提供4个核心工具：

### 1. `query_codebase`
使用自然语言查询代码库知识图谱。

**参数:**
- `query` (string): 关于代码库的自然语言问题

**示例查询:**
- "找到所有处理用户认证的函数"
- "显示 src 目录下的所有类"
- "哪些文件包含数据库操作？"
- "找到最复杂的函数"

### 2. `get_code_snippet`
获取特定函数或类的源代码。

**参数:**
- `qualified_name` (string): 函数或类的完全限定名

**示例:**
- `"User.authenticate"`
- `"database.connection.connect"`
- `"utils.helpers.validate_email"`

### 3. `get_codebase_summary`
获取代码库摘要，包括语言分布、文件统计等。

**参数:** 无

### 4. `health_check`
检查MCP服务器和依赖项的健康状态。

**参数:** 无

## 🔧 配置选项

### 传输模式选择

| 模式 | 适用场景 | 性能 | 部署复杂度 | 扩展性 |
|------|----------|------|------------|--------|
| **STDIO** | 本地开发、单机部署 | 高 | 低 | 低 |
| **HTTP** | 远程集成、分布式部署 | 中等 | 中等 | 高 |

### 模型配置

#### 本地模型（推荐）
```bash
# .env文件配置
LOCAL_MODEL_ENDPOINT=http://localhost:11434/v1
LOCAL_ORCHESTRATOR_MODEL_ID=llama3
LOCAL_CYPHER_MODEL_ID=llama3
LOCAL_MODEL_API_KEY=ollama
```

#### Gemini模型
```bash
# .env文件配置
GEMINI_API_KEY=your_gemini_api_key_here
```

#### OpenAI模型
```bash
# .env文件配置
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_ORCHESTRATOR_MODEL_ID=gpt-4o-mini
OPENAI_CYPHER_MODEL_ID=gpt-4o-mini
```

## 🌐 客户端集成

### Cherry Studio集成

#### STDIO模式配置
```json
{
  "mcpServers": {
    "code-graph-rag": {
      "name": "Code Graph RAG",
      "type": "STDIO",
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/code-graph-rag",
        "run",
        "mcp_server.py",
        "stdio"
      ],
      "env": {
        "TARGET_REPO_PATH": "/path/to/code-graph-rag",
        "MEMGRAPH_HOST": "localhost",
        "MEMGRAPH_PORT": "7687"
      }
    }
  }
}
```

#### HTTP模式配置
```json
{
  "mcpServers": {
    "code-graph-rag-http": {
      "name": "Code Graph RAG (HTTP)",
      "type": "HTTP",
      "url": "http://localhost:7444/sse"
    }
  }
}
```

### Claude Desktop集成

#### STDIO模式配置
```json
{
  "mcpServers": {
    "code-graph-rag": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/code-graph-rag",
        "run",
        "mcp_server.py",
        "stdio"
      ]
    }
  }
}
```

#### HTTP模式配置
```json
{
  "mcpServers": {
    "code-graph-rag-http": {
      "command": "curl",
      "args": [
        "-X", "POST",
        "-H", "Content-Type: application/json",
        "-d", "@-",
        "http://localhost:7445/sse"
      ]
    }
  }
}
```

## 📊 服务器端点

### STDIO模式
- **通信方式**: 标准输入/输出
- **适用场景**: 本地进程间通信

### HTTP模式
- **SSE端点**: `http://localhost:7445/sse` - MCP协议通信
- **健康检查**: `http://localhost:7445/health` - 服务器状态检查

## 🧪 测试

### 运行所有测试
```bash
# 统一测试套件（推荐）
uv run pytest codebase_rag/tests/test_mcp_unified.py -v

# 分别测试STDIO和HTTP模式
uv run pytest codebase_rag/tests/test_mcp_server.py -v
uv run pytest codebase_rag/tests/test_http_mcp_server.py -v
```

### 手动测试

#### STDIO模式测试
```bash
# 启动服务器
uv run codebase_rag/mcp_server.py stdio

# 在另一个终端测试
echo '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0.0"}}}' | uv run codebase_rag/mcp_server.py stdio
```

#### HTTP模式测试
```bash
# 启动服务器
uv run codebase_rag/mcp_server.py http

# 测试健康检查
curl http://localhost:7445/health

# 测试MCP通信
curl -X POST http://localhost:7445/sse \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0.0"}}}'
```

## 🐛 故障排除

### 常见问题

1. **服务器无法启动**
   - 检查 `uv` 是否已安装并添加到 PATH
   - 检查项目路径是否正确
   - 检查环境变量配置

2. **工具调用失败**
   - 确保 Memgraph 正在运行 (`docker-compose up -d`)
   - 确保代码库已解析 (`python -m codebase_rag.main start --repo-path . --update-graph --clean`)
   - 检查 API 密钥配置（如果使用云模型）

3. **HTTP模式连接超时**
   - 检查防火墙设置
   - 检查端口是否被占用
   - 检查网络连通性

4. **STDIO模式客户端无法连接**
   - 检查客户端配置路径
   - 确保服务器正在运行
   - 检查环境变量设置

### 调试模式

```bash
# 启用详细日志
export LOG_LEVEL=DEBUG
./start_mcp_server.sh /path/to/repo stdio
```

### 健康检查

```bash
# STDIO模式：使用health_check工具
# HTTP模式：访问健康检查端点
curl http://localhost:7445/health
```

## 📁 项目结构

```
code-graph-rag/
├── codebase_rag/              # 核心代码库
│   ├── mcp_server.py          # MCP服务器（支持STDIO和HTTP）
│   ├── tests/                 # 测试目录
│   │   ├── test_mcp_unified.py    # 统一测试套件
│   │   ├── test_mcp_server.py     # STDIO模式测试
│   │   ├── test_http_mcp_server.py # HTTP模式测试
│   │   └── test_treesitter_operators.py # Tree-sitter测试
│   ├── tools/                 # MCP工具实现
│   ├── services/              # 服务层
│   ├── parsers/               # 代码解析器
│   └── config.py              # 配置管理
├── config/                    # 配置文件目录
│   ├── generate_mcp_config.py # 配置生成器
│   ├── mcp_stdio_config.json  # STDIO模式配置
│   ├── mcp_http_config.json  # HTTP模式配置
│   ├── claude_desktop_http_config.json # Claude Desktop HTTP配置
│   └── generic_http_config.json # 通用HTTP配置
├── build_binary.py            # 构建脚本
├── realtime_updater.py        # 实时更新脚本
├── start_mcp_server.sh        # MCP服务器启动脚本
├── examples/                  # 示例代码
├── docs/                      # 文档目录
└── README.md                  # 本文档
```

## 🔄 模式切换

### 从STDIO切换到HTTP
1. 停止STDIO服务器
2. 启动HTTP服务器：`./scripts/start_mcp_server.sh /path/to/repo http`
3. 更新客户端配置
4. 重启客户端

### 从HTTP切换到STDIO
1. 停止HTTP服务器
2. 启动STDIO服务器：`./scripts/start_mcp_server.sh /path/to/repo stdio`
3. 更新客户端配置
4. 重启客户端

## 🚀 部署选项

### 本地部署
```bash
# STDIO模式
./scripts/start_mcp_server.sh /path/to/repo stdio

# HTTP模式
./scripts/start_mcp_server.sh /path/to/repo http 7445
```

### Docker部署
```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY . .

RUN pip install uv
RUN uv sync

EXPOSE 7444

CMD ["uv", "run", "mcp_server.py", "http"]
```

### 云服务部署

#### 阿里云函数计算
```yaml
# serverless.yml
service: code-graph-rag-mcp
provider:
  name: aliyun
  runtime: python3.9
  region: cn-hangzhou
functions:
  mcp-server:
    handler: mcp_server.main
    events:
      - http:
          path: /sse
          method: post
      - http:
          path: /health
          method: get
```

## 🌍 多语言支持管理

### 添加新语言支持

使用内置工具轻松添加新语言：

```bash
# 添加C#支持
python -m codebase_rag.tools.language add-grammar c-sharp
```

#### Example: Adding C# Support

```bash
$ python -m codebase_rag.tools.language add-grammar c-sharp
🔍 Using default tree-sitter URL: https://github.com/tree-sitter/tree-sitter-c-sharp
🔄 Adding submodule from https://github.com/tree-sitter/tree-sitter-c-sharp...
✅ Successfully added submodule at grammars/tree-sitter-c-sharp
Auto-detected language: c-sharp
Auto-detected file extensions: ['cs']
Auto-detected node types:
Functions: ['destructor_declaration', 'method_declaration', 'constructor_declaration']
Classes: ['struct_declaration', 'enum_declaration', 'interface_declaration', 'class_declaration']
Modules: ['compilation_unit', 'file_scoped_namespace_declaration', 'namespace_declaration']
Calls: ['invocation_expression']

✅ Language 'c-sharp' has been added to the configuration!
📝 Updated codebase_rag/language_config.py
```

#### Managing Languages

```bash
# List all configured languages
python -m codebase_rag.tools.language list-languages

# Remove a language (this also removes the git submodule unless --keep-submodule is specified)
python -m codebase_rag.tools.language remove-language <language-name>
```

#### Language Configuration

The system uses a configuration-driven approach for language support. Each language is defined in `codebase_rag/language_config.py` with the following structure:

```python
"language-name": LanguageConfig(
    name="language-name",
    file_extensions=[".ext1", ".ext2"],
    function_node_types=["function_declaration", "method_declaration"],
    class_node_types=["class_declaration", "struct_declaration"],
    module_node_types=["compilation_unit", "source_file"],
    call_node_types=["call_expression", "method_invocation"],
),
```

#### Troubleshooting

**Grammar not found**: If the automatic URL doesn't work, use a custom URL:
```bash
python -m codebase_rag.tools.language add-grammar --grammar-url https://github.com/custom/tree-sitter-mylang
```

**Version incompatibility**: If you get "Incompatible Language version" errors, update your tree-sitter package:
```bash
uv add tree-sitter@latest
```

**Missing node types**: The tool automatically detects common node patterns, but you can manually adjust the configuration in `language_config.py` if needed.

## 📦 Building a binary

You can build a binary of the application using the `build_binary.py` script. This script uses PyInstaller to package the application and its dependencies into a single executable.

```bash
python build_binary.py
```
The resulting binary will be located in the `dist` directory.

## 🐛 Debugging

1. **Check Memgraph connection**:
   - Ensure Docker containers are running: `docker-compose ps`
   - Verify Memgraph is accessible on port 7687

2. **View database in Memgraph Lab**:
   - Open http://localhost:3000
   - Connect to memgraph:7687

3. **For local models**:
   - Verify Ollama is running: `ollama list`
   - Check if models are downloaded: `ollama pull llama3`
   - Test Ollama API: `curl http://localhost:11434/v1/models`
   - Check Ollama logs: `ollama logs`

## 📚 相关资源

- [Model Context Protocol 官方文档](https://modelcontextprotocol.io/)
- [FastMCP 框架文档](https://github.com/modelcontextprotocol/python-sdk)
- [Cherry Studio 集成指南](https://docs.cherry-ai.com/)
- [Claude Desktop 配置指南](https://claude.ai/desktop)

## 🤝 贡献

Please see [CONTRIBUTING.md](CONTRIBUTING.md) for detailed contribution guidelines.

Good first PRs are from TODO issues.

## 🙋‍♂️ Support

For issues or questions:
1. Check the logs for error details
2. Verify Memgraph connection
3. Ensure all environment variables are set
4. Review the graph schema matches your expectations

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=vitali87/code-graph-rag&type=Date)](https://www.star-history.com/#vitali87/code-graph-rag&Date)

## 📄 许可证

本项目采用MIT许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

---

**注意**：请根据您的实际环境调整配置文件中的路径和参数。建议开发环境使用STDIO模式，生产环境使用HTTP模式。
