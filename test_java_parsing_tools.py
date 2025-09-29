#!/usr/bin/env python3
"""测试Java解析工具的实际解析流程"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_java_parsing_tools():
    """测试Java解析工具的实际解析流程"""

    print("=== Java解析工具测试 ===")

    # 测试Java文件路径
    java_file = "/Users/guoshuai/git/uicfinal/uicfinal/uic-client-starter/src/main/java/com/taobao/uic/context/UicCommonContext.java"

    try:
        # 导入我们的解析工具
        from codebase_rag.parsers.definition_processor import DefinitionProcessor
        from codebase_rag.parsers.java_type_inference import JavaTypeInference
        from codebase_rag.parsers.java_utils import (
            extract_java_class_info,
            extract_java_import_path,
        )
        from codebase_rag.services.graph_service import MemgraphIngestor

        print("✅ 成功导入Java解析工具")

        # 创建必要的实例
        ingestor = MemgraphIngestor()
        type_inference = JavaTypeInference(ingestor)
        # processor = DefinitionProcessor(ingestor, type_inference)  # 暂时注释掉未使用的变量

        print("✅ 成功创建解析器实例")

        # 读取Java文件
        with open(java_file, encoding="utf-8") as f:
            java_code = f.read()

        print("✅ 读取Java文件成功")

        # 使用tree-sitter解析
        import tree_sitter
        from tree_sitter import Language
        from tree_sitter_java import language

        java_lang = language()
        language_obj = Language(java_lang)
        parser = tree_sitter.Parser(language_obj)
        tree = parser.parse(bytes(java_code, "utf8"))
        root_node = tree.root_node

        print("✅ tree-sitter解析成功")

        # 测试import解析
        print("\n📋 测试Import解析:")
        import_count = 0
        import_errors = 0

        def test_imports(node):
            nonlocal import_count, import_errors
            if node.type == "import_declaration":
                import_count += 1
                try:
                    import_info = extract_java_import_path(node)
                    if import_info:
                        print(f"  ✅ Import {import_count}: {import_info}")
                    else:
                        print(f"  ❌ Import {import_count}: 解析失败")
                        import_errors += 1
                except Exception as e:
                    print(f"  ❌ Import {import_count}: 错误 - {e}")
                    import_errors += 1
            for child in node.children:
                test_imports(child)

        test_imports(root_node)
        print(f"✅ Import解析测试完成: {import_count}个, 错误{import_errors}个")

        # 测试类解析
        print("\n📋 测试类解析:")
        class_count = 0
        class_errors = 0

        def test_classes(node):
            nonlocal class_count, class_errors
            if node.type == "class_declaration":
                class_count += 1
                try:
                    class_info = extract_java_class_info(node)
                    print(f"  ✅ 类 {class_count}: {class_info['name']}")
                    print(f"     父类: {class_info['superclass']}")
                    print(f"     接口: {class_info['interfaces']}")
                except Exception as e:
                    print(f"  ❌ 类 {class_count}: 错误 - {e}")
                    class_errors += 1
            for child in node.children:
                test_classes(child)

        test_classes(root_node)
        print(f"✅ 类解析测试完成: {class_count}个, 错误{class_errors}个")

        # 测试方法解析
        print("\n📋 测试方法解析:")
        method_count = 0
        method_errors = 0

        def test_methods(node):
            nonlocal method_count, method_errors
            if node.type in ["method_declaration", "constructor_declaration"]:
                method_count += 1
                try:
                    name_node = node.child_by_field_name("name")
                    method_name = (
                        name_node.text.decode("utf8") if name_node else "Unknown"
                    )

                    # 测试方法类型推断
                    method_type = type_inference.infer_method_type(
                        node, "com.taobao.uic.context.UicCommonContext"
                    )
                    print(f"  ✅ 方法 {method_count}: {method_name} -> {method_type}")
                except Exception as e:
                    print(f"  ❌ 方法 {method_count}: 错误 - {e}")
                    method_errors += 1
            for child in node.children:
                test_methods(child)

        test_methods(root_node)
        print(f"✅ 方法解析测试完成: {method_count}个, 错误{method_errors}个")

        # 测试方法调用解析
        print("\n📋 测试方法调用解析:")
        call_count = 0
        call_errors = 0

        def test_calls(node):
            nonlocal call_count, call_errors
            if node.type == "method_invocation":
                call_count += 1
                try:
                    name_node = node.child_by_field_name("name")
                    method_name = (
                        name_node.text.decode("utf8") if name_node else "Unknown"
                    )

                    object_node = node.child_by_field_name("object")
                    object_name = (
                        object_node.text.decode("utf8") if object_node else "None"
                    )

                    # 测试方法调用类型推断
                    call_type = type_inference.infer_method_call_type(
                        node, "com.taobao.uic.context.UicCommonContext"
                    )
                    if call_count <= 10:  # 只显示前10个
                        print(
                            f"  ✅ 调用 {call_count}: {object_name}.{method_name}() -> {call_type}"
                        )
                except Exception as e:
                    print(f"  ❌ 调用 {call_count}: 错误 - {e}")
                    call_errors += 1
            for child in node.children:
                test_calls(child)

        test_calls(root_node)
        if call_count > 10:
            print(f"     ... 还有 {call_count - 10} 个方法调用")
        print(f"✅ 方法调用解析测试完成: {call_count}个, 错误{call_errors}个")

        print("\n🎯 解析工具测试总结:")
        print(f"  - Import解析: {import_count}个, 错误{import_errors}个")
        print(f"  - 类解析: {class_count}个, 错误{class_errors}个")
        print(f"  - 方法解析: {method_count}个, 错误{method_errors}个")
        print(f"  - 方法调用解析: {call_count}个, 错误{call_errors}个")

        if (
            import_errors == 0
            and class_errors == 0
            and method_errors == 0
            and call_errors == 0
        ):
            print("\n✅ 所有解析工具工作正常！")
        else:
            print("\n❌ 发现解析问题，需要进一步调试")

    except ImportError as e:
        print(f"❌ 导入错误: {e}")
        import traceback

        traceback.print_exc()
    except Exception as e:
        print(f"❌ 测试错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_java_parsing_tools()
