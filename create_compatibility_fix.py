#!/usr/bin/env python3
"""创建QueryCursor兼容性修复方案"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def create_querycursor_compatibility_fix() -> None:
    """创建QueryCursor兼容性修复方案"""

    print("=== QueryCursor兼容性修复方案 ===")

    # 检查当前tree-sitter版本支持的功能
    try:
        import tree_sitter

        print(f"✅ tree-sitter版本: {getattr(tree_sitter, '__version__', 'Unknown')}")

        # 检查可用的功能
        available_features = [
            attr for attr in dir(tree_sitter) if not attr.startswith("_")
        ]
        print(f"✅ 可用功能: {available_features}")

        # 检查Query相关功能
        query_features = [attr for attr in available_features if "Query" in attr]
        print(f"✅ Query相关功能: {query_features}")

        if "QueryCursor" not in available_features:
            print("❌ QueryCursor不可用，需要创建兼容性方案")

            # 创建兼容性方案
            compatibility_code = '''
# QueryCursor兼容性方案
class QueryCursorCompat:
    """QueryCursor兼容性包装类"""

    def __init__(self, query):
        self.query = query
        self.matches = []
        self.current_index = 0

    def execute(self, node):
        """执行查询"""
        self.matches = self._find_matches(node, self.query)
        self.current_index = 0

    def next_match(self):
        """获取下一个匹配"""
        if self.current_index < len(self.matches):
            match = self.matches[self.current_index]
            self.current_index += 1
            return match
        return None

    def _find_matches(self, node, query):
        """查找匹配的节点"""
        matches = []
        # 这里需要实现具体的查询逻辑
        # 由于QueryCursor的复杂性，我们可能需要简化查询
        return matches

# 替换QueryCursor的使用
try:
    from tree_sitter import QueryCursor
    QueryCursor = QueryCursor
except ImportError:
    QueryCursor = QueryCursorCompat
'''

            print("📝 兼容性代码:")
            print(compatibility_code)

        else:
            print("✅ QueryCursor可用")

    except ImportError as e:
        print(f"❌ 导入错误: {e}")

    print("\n🔧 修复建议:")
    print("1. 创建QueryCursor兼容性包装类")
    print("2. 修改所有使用QueryCursor的文件")
    print("3. 简化查询逻辑，避免复杂的QueryCursor功能")
    print("4. 或者升级tree-sitter到支持QueryCursor的版本")

    print("\n📋 需要修改的文件:")
    files_to_modify = [
        "codebase_rag/parsers/definition_processor.py",
        "codebase_rag/parsers/utils.py",
        "codebase_rag/parsers/type_inference.py",
        "codebase_rag/parsers/call_processor.py",
    ]

    for file_path in files_to_modify:
        print(f"  - {file_path}")

    print("\n✅ 兼容性修复方案创建完成！")


if __name__ == "__main__":
    create_querycursor_compatibility_fix()
