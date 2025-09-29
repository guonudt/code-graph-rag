#!/usr/bin/env python3
"""分析Java解析问题的测试脚本"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def analyze_java_file():
    """分析Java文件的解析问题"""

    print("=== Java文件解析问题分析 ===")

    # 测试Java文件路径
    java_file = "/Users/guoshuai/git/uicfinal/uicfinal/uic-client-starter/src/main/java/com/taobao/uic/context/UicCommonContext.java"

    try:
        import tree_sitter
        from tree_sitter import Language
        from tree_sitter_java import language

        # 创建解析器
        java_lang = language()
        language_obj = Language(java_lang)
        parser = tree_sitter.Parser(language_obj)

        print("✅ tree-sitter解析器创建成功")

        # 读取Java文件
        with open(java_file, encoding="utf-8") as f:
            java_code = f.read()

        print(f"✅ 读取Java文件成功: {java_file}")
        print(f"   文件大小: {len(java_code)} 字符")

        # 解析代码
        tree = parser.parse(bytes(java_code, "utf8"))
        root_node = tree.root_node

        print("✅ Java代码解析成功")
        print(f"   根节点类型: {root_node.type}")
        print(f"   子节点数量: {len(root_node.children)}")

        # 分析import语句
        print("\n📋 分析Import语句:")
        import_count = 0
        import_details = []

        def analyze_imports(node):
            nonlocal import_count, import_details
            if node.type == "import_declaration":
                import_count += 1
                import_text = node.text.decode("utf8")
                import_details.append(import_text)
                print(f"  {import_count:2d}. {import_text}")
            for child in node.children:
                analyze_imports(child)

        analyze_imports(root_node)
        print(f"✅ 找到 {import_count} 个import声明")

        # 分析类声明
        print("\n📋 分析类声明:")
        class_count = 0

        def analyze_classes(node):
            nonlocal class_count
            if node.type == "class_declaration":
                class_count += 1
                name_node = node.child_by_field_name("name")
                class_name = name_node.text.decode("utf8") if name_node else "Unknown"

                superclass_node = node.child_by_field_name("superclass")
                superclass = (
                    superclass_node.text.decode("utf8") if superclass_node else "None"
                )

                interfaces_node = node.child_by_field_name("interfaces")
                interfaces = []
                if interfaces_node:
                    for child in interfaces_node.children:
                        if child.type == "type_list":
                            for type_child in child.children:
                                if type_child.type == "type_identifier":
                                    interfaces.append(type_child.text.decode("utf8"))
                                elif type_child.type == "scoped_identifier":
                                    interfaces.append(type_child.text.decode("utf8"))

                print(f"  {class_count}. 类名: {class_name}")
                print(f"     父类: {superclass}")
                print(f"     接口: {interfaces}")
            for child in node.children:
                analyze_classes(child)

        analyze_classes(root_node)
        print(f"✅ 找到 {class_count} 个类声明")

        # 分析方法声明
        print("\n📋 分析方法声明:")
        method_count = 0

        def analyze_methods(node):
            nonlocal method_count
            if node.type in ["method_declaration", "constructor_declaration"]:
                method_count += 1
                name_node = node.child_by_field_name("name")
                method_name = name_node.text.decode("utf8") if name_node else "Unknown"

                # 查找返回类型
                type_node = node.child_by_field_name("type")
                return_type = type_node.text.decode("utf8") if type_node else "void"

                # 查找参数
                params_node = node.child_by_field_name("parameters")
                param_count = 0
                if params_node:
                    for child in params_node.children:
                        if child.type == "formal_parameter":
                            param_count += 1

                print(
                    f"  {method_count:2d}. {method_name}({param_count}参数) -> {return_type}"
                )
            for child in node.children:
                analyze_methods(child)

        analyze_methods(root_node)
        print(f"✅ 找到 {method_count} 个方法声明")

        # 分析方法调用
        print("\n📋 分析方法调用:")
        call_count = 0

        def analyze_calls(node):
            nonlocal call_count
            if node.type == "method_invocation":
                call_count += 1
                name_node = node.child_by_field_name("name")
                method_name = name_node.text.decode("utf8") if name_node else "Unknown"

                object_node = node.child_by_field_name("object")
                object_name = object_node.text.decode("utf8") if object_node else "None"

                if call_count <= 10:  # 只显示前10个
                    print(f"  {call_count:2d}. {object_name}.{method_name}()")
            for child in node.children:
                analyze_calls(child)

        analyze_calls(root_node)
        if call_count > 10:
            print(f"     ... 还有 {call_count - 10} 个方法调用")
        print(f"✅ 找到 {call_count} 个方法调用")

        # 分析构造函数调用
        print("\n📋 分析构造函数调用:")
        constructor_count = 0

        def analyze_constructors(node):
            nonlocal constructor_count
            if node.type == "object_creation_expression":
                constructor_count += 1
                type_node = node.child_by_field_name("type")
                type_name = type_node.text.decode("utf8") if type_node else "Unknown"

                if constructor_count <= 5:  # 只显示前5个
                    print(f"  {constructor_count}. new {type_name}()")
            for child in node.children:
                analyze_constructors(child)

        analyze_constructors(root_node)
        if constructor_count > 5:
            print(f"     ... 还有 {constructor_count - 5} 个构造函数调用")
        print(f"✅ 找到 {constructor_count} 个构造函数调用")

        print("\n🎯 解析结果总结:")
        print(f"  - Import声明: {import_count}个")
        print(f"  - 类声明: {class_count}个")
        print(f"  - 方法声明: {method_count}个")
        print(f"  - 方法调用: {call_count}个")
        print(f"  - 构造函数调用: {constructor_count}个")

        # 检查可能的问题
        print("\n🔍 潜在问题分析:")

        if import_count == 0:
            print("  ❌ 没有找到import声明 - 可能存在import解析问题")
        else:
            print(f"  ✅ Import解析正常 ({import_count}个)")

        if class_count == 0:
            print("  ❌ 没有找到类声明 - 可能存在类解析问题")
        else:
            print(f"  ✅ 类解析正常 ({class_count}个)")

        if method_count == 0:
            print("  ❌ 没有找到方法声明 - 可能存在方法解析问题")
        else:
            print(f"  ✅ 方法解析正常 ({method_count}个)")

        if call_count == 0:
            print("  ❌ 没有找到方法调用 - 可能存在方法调用解析问题")
        else:
            print(f"  ✅ 方法调用解析正常 ({call_count}个)")

        print("\n✅ Java文件解析分析完成！")

    except ImportError as e:
        print(f"❌ 导入错误: {e}")
    except Exception as e:
        print(f"❌ 解析错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    analyze_java_file()
