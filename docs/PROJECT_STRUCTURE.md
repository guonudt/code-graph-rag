# 📁 项目结构说明

本文档详细说明了 Code Graph RAG MCP Server 项目的目录结构和文件组织。

## 🏗️ 整体结构

```
code-graph-rag/
├── codebase_rag/              # 核心代码库
├── config/                    # 配置文件目录
├── scripts/                   # 脚本目录
├── examples/                  # 示例代码
├── docs/                      # 文档目录
├── assets/                    # 静态资源
├── grammars/                  # Tree-sitter语法文件
├── optimize/                  # 优化相关文件
├── venv/                      # Python虚拟环境
├── .github/                   # GitHub配置
├── pyproject.toml             # 项目配置
├── docker-compose.yaml        # Docker配置
├── Makefile                   # 构建脚本
├── README.md                  # 项目说明
├── LICENSE                    # 许可证
└── CONTRIBUTING.md            # 贡献指南
```

## 📂 详细说明

### `codebase_rag/` - 核心代码库

这是项目的主要代码目录，包含所有核心功能：

```
codebase_rag/
├── mcp_server.py              # MCP服务器主文件
├── config.py                  # 配置管理
├── main.py                    # 主程序入口
├── graph_loader.py            # 图数据加载器
├── graph_updater.py           # 图数据更新器
├── parser_loader.py           # 解析器加载器
├── language_config.py         # 语言配置
├── prompts.py                 # 提示词模板
├── schemas.py                 # 数据模式定义
├── tools/                     # MCP工具实现
│   ├── code_retrieval.py      # 代码检索工具
│   ├── codebase_query.py      # 代码库查询工具
│   ├── directory_lister.py    # 目录列表工具
│   ├── document_analyzer.py   # 文档分析工具
│   ├── file_editor.py         # 文件编辑工具
│   ├── file_reader.py         # 文件读取工具
│   ├── file_writer.py         # 文件写入工具
│   ├── language.py            # 语言检测工具
│   └── shell_command.py       # Shell命令工具
├── services/                  # 服务层
│   ├── graph_service.py       # 图数据库服务
│   └── llm.py                 # LLM服务
├── parsers/                   # 代码解析器
│   ├── call_processor.py      # 调用处理器
│   ├── definition_processor.py # 定义处理器
│   ├── import_processor.py   # 导入处理器
│   ├── structure_processor.py # 结构处理器
│   ├── factory.py             # 解析器工厂
│   ├── constants.py           # 常量定义
│   ├── utils.py               # 工具函数
│   ├── type_inference.py      # 类型推断
│   ├── python_utils.py        # Python工具
│   ├── java_utils.py          # Java工具
│   ├── java_type_inference.py # Java类型推断
│   ├── cpp_utils.py           # C++工具
│   ├── rust_utils.py          # Rust工具
│   └── lua_utils.py           # Lua工具
└── tests/                     # 测试文件
    ├── test_mcp_unified.py    # 统一测试套件
    ├── test_mcp_server.py     # STDIO模式测试
    ├── test_http_mcp_server.py # HTTP模式测试
    ├── test_treesitter_operators.py # Tree-sitter测试
    └── [其他测试文件...]      # 其他测试文件
```

### `config/` - 配置文件目录

包含所有MCP客户端配置文件：

```
config/
├── generate_mcp_config.py     # 配置生成器
├── mcp_stdio_config.json      # STDIO模式配置
├── mcp_http_config.json       # HTTP模式配置
├── claude_desktop_http_config.json # Claude Desktop HTTP配置
└── generic_http_config.json   # 通用HTTP配置
```

### 脚本文件

项目根目录下的实用脚本：

```
build_binary.py                # 二进制构建脚本
realtime_updater.py            # 实时更新脚本
start_mcp_server.sh            # MCP服务器启动脚本
```

### `examples/` - 示例代码

包含示例和演示代码：

```
examples/
├── graph_export_example.py     # 图导出示例
└── my_graph.json              # 示例图数据
```

### `docs/` - 文档目录

包含项目文档：

```
docs/
├── PROJECT_STRUCTURE.md       # 项目结构说明（本文档）
└── [其他文档...]              # 其他文档文件
```

### `assets/` - 静态资源

包含项目的静态资源文件：

```
assets/
├── logo-dark-any.png          # 深色主题Logo
└── logo-light-any.png         # 浅色主题Logo
```

### `grammars/` - Tree-sitter语法文件

包含Tree-sitter语法定义：

```
grammars/
├── tree-sitter-c-sharp/       # C#语法
├── tree-sitter-lua/           # Lua语法
└── tree-sitter-php/           # PHP语法
```

### `optimize/` - 优化相关文件

包含优化和性能相关文件：

```
optimize/
├── code_to_text.sh            # 代码转文本脚本
├── EXPERT_PYTHON_PROGRAMMING_FOURTH_EDITION.pdf # 参考文档
├── tree-sitter-cpp.txt        # C++语法说明
└── tree-sitter.txt            # Tree-sitter说明
```

## 🔧 配置文件说明

### `pyproject.toml`
项目的主要配置文件，包含：
- 项目元数据
- 依赖管理
- 构建配置
- 工具配置

### `docker-compose.yaml`
Docker容器编排配置，用于：
- 启动Memgraph数据库
- 配置服务依赖

### `Makefile`
构建和开发工具脚本，提供：
- 安装命令
- 测试命令
- 清理命令
- 构建命令

## 🚀 开发工作流

### 添加新功能
1. 在 `codebase_rag/` 相应目录下添加代码
2. 在 `codebase_rag/tests/` 添加测试
3. 更新相关文档

### 添加新工具
1. 在 `codebase_rag/tools/` 创建工具文件
2. 在 `codebase_rag/mcp_server.py` 注册工具
3. 添加测试用例

### 添加新解析器
1. 在 `codebase_rag/parsers/` 创建解析器文件
2. 在 `codebase_rag/parsers/factory.py` 注册解析器
3. 添加测试用例

## 📝 命名规范

### 文件命名
- Python文件：使用下划线分隔（`snake_case`）
- 配置文件：使用下划线分隔（`snake_case`）
- 脚本文件：使用下划线分隔（`snake_case`）

### 目录命名
- 使用小写字母和下划线
- 复数形式表示集合（如 `tools/`, `parsers/`）

### 类命名
- 使用驼峰命名法（`PascalCase`）

### 函数和变量命名
- 使用下划线分隔（`snake_case`）

## 🔍 查找文件指南

### 查找MCP相关文件
- MCP服务器：`codebase_rag/mcp_server.py`
- MCP工具：`codebase_rag/tools/`
- MCP测试：`codebase_rag/tests/test_mcp_*.py`
- MCP配置：`config/*_config.json`

### 查找解析器相关文件
- 解析器实现：`codebase_rag/parsers/`
- 解析器测试：`codebase_rag/tests/test_*_parser.py`

### 查找服务相关文件
- 服务实现：`codebase_rag/services/`
- 服务测试：`codebase_rag/tests/test_*_service.py`

## 📋 维护清单

定期检查以下内容：
- [ ] 清理临时文件和缓存
- [ ] 更新依赖版本
- [ ] 检查测试覆盖率
- [ ] 更新文档
- [ ] 检查代码质量
- [ ] 验证配置文件
