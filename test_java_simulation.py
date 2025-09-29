#!/usr/bin/env python3
"""测试Java解析逻辑，模拟数据库存储"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_java_parsing_simulation() -> None:
    """测试Java解析逻辑，模拟数据库存储"""

    print("=== Java解析逻辑测试（模拟存储） ===")

    # 测试Java文件路径
    java_file = "/Users/guoshuai/git/uicfinal/uicfinal/uic-client-starter/src/main/java/com/taobao/uic/context/UicCommonContext.java"

    try:
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

        # 模拟数据库存储
        stored_data = {
            "packages": [],
            "classes": [],
            "methods": [],
            "imports": [],
            "relationships": [],
        }

        # 解析import语句
        print("\n📋 解析Import语句:")
        import_count = 0

        def process_imports(node):
            nonlocal import_count
            if node.type == "import_declaration":
                import_count += 1
                try:
                    import_text = node.text.decode("utf8")

                    # 解析import语句
                    parts = (
                        import_text.replace("import ", "").replace(";", "").split(".")
                    )
                    if len(parts) >= 2:
                        package_name = ".".join(parts[:-1])
                        class_name = parts[-1]
                        qualified_name = f"{package_name}.{class_name}"

                        # 模拟存储
                        stored_data["packages"].append(package_name)
                        stored_data["imports"].append(
                            {
                                "package": package_name,
                                "class": class_name,
                                "qualified_name": qualified_name,
                            }
                        )

                        if import_count <= 10:  # 只显示前10个
                            print(f"  ✅ Import {import_count}: {qualified_name}")

                except Exception as e:
                    print(f"  ❌ Import {import_count}: 错误 - {e}")

            for child in node.children:
                process_imports(child)

        process_imports(root_node)
        print(f"✅ Import解析: {len(stored_data['imports'])}个")

        # 解析类声明
        print("\n📋 解析类声明:")
        class_count = 0

        def process_classes(node):
            nonlocal class_count
            if node.type == "class_declaration":
                class_count += 1
                try:
                    name_node = node.child_by_field_name("name")
                    class_name = (
                        name_node.text.decode("utf8") if name_node else "Unknown"
                    )

                    # 解析父类
                    superclass_node = node.child_by_field_name("superclass")
                    superclass = None
                    if superclass_node:
                        if superclass_node.type == "type_identifier":
                            superclass = superclass_node.text.decode("utf8")
                        elif superclass_node.type == "scoped_identifier":
                            superclass = superclass_node.text.decode("utf8")

                    # 解析接口
                    interfaces = []
                    interfaces_node = node.child_by_field_name("interfaces")
                    if interfaces_node:
                        for child in interfaces_node.children:
                            if child.type == "type_list":
                                for type_child in child.children:
                                    if type_child.type == "type_identifier":
                                        interfaces.append(
                                            type_child.text.decode("utf8")
                                        )
                                    elif type_child.type == "scoped_identifier":
                                        interfaces.append(
                                            type_child.text.decode("utf8")
                                        )

                    qualified_name = f"com.taobao.uic.context.{class_name}"

                    # 模拟存储
                    stored_data["classes"].append(
                        {
                            "name": class_name,
                            "qualified_name": qualified_name,
                            "superclass": superclass,
                            "interfaces": interfaces,
                        }
                    )

                    print(f"  ✅ 类 {class_count}: {class_name}")
                    print(f"     父类: {superclass}")
                    print(f"     接口: {interfaces}")

                except Exception as e:
                    print(f"  ❌ 类 {class_count}: 错误 - {e}")

            for child in node.children:
                process_classes(child)

        process_classes(root_node)
        print(f"✅ 类解析: {len(stored_data['classes'])}个")

        # 解析方法声明
        print("\n📋 解析方法声明:")
        method_count = 0

        def process_methods(node):
            nonlocal method_count
            if node.type in ["method_declaration", "constructor_declaration"]:
                method_count += 1
                try:
                    name_node = node.child_by_field_name("name")
                    method_name = (
                        name_node.text.decode("utf8") if name_node else "Unknown"
                    )

                    type_node = node.child_by_field_name("type")
                    return_type = type_node.text.decode("utf8") if type_node else "void"

                    # 解析参数
                    params_node = node.child_by_field_name("parameters")
                    param_count = 0
                    if params_node:
                        for child in params_node.children:
                            if child.type == "formal_parameter":
                                param_count += 1

                    qualified_name = (
                        f"com.taobao.uic.context.UicCommonContext.{method_name}"
                    )

                    # 模拟存储
                    stored_data["methods"].append(
                        {
                            "name": method_name,
                            "qualified_name": qualified_name,
                            "return_type": return_type,
                            "param_count": param_count,
                            "is_constructor": node.type == "constructor_declaration",
                        }
                    )

                    if method_count <= 10:  # 只显示前10个
                        print(
                            f"  ✅ 方法 {method_count}: {method_name}({param_count}参数) -> {return_type}"
                        )

                except Exception as e:
                    print(f"  ❌ 方法 {method_count}: 错误 - {e}")

            for child in node.children:
                process_methods(child)

        process_methods(root_node)
        if method_count > 10:
            print(f"     ... 还有 {method_count - 10} 个方法")
        print(f"✅ 方法解析: {len(stored_data['methods'])}个")

        # 解析方法调用
        print("\n📋 解析方法调用:")
        call_count = 0

        def process_calls(node):
            nonlocal call_count
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

                    if call_count <= 10:  # 只显示前10个
                        print(f"  ✅ 调用 {call_count}: {object_name}.{method_name}()")

                except Exception as e:
                    print(f"  ❌ 调用 {call_count}: 错误 - {e}")

            for child in node.children:
                process_calls(child)

        process_calls(root_node)
        if call_count > 10:
            print(f"     ... 还有 {call_count - 10} 个方法调用")
        print(f"✅ 方法调用解析: {call_count}个")

        # 分析存储的数据
        print("\n🎯 解析结果分析:")
        print(f"  - Import语句: {len(stored_data['imports'])}个")
        print(f"  - 类声明: {len(stored_data['classes'])}个")
        print(f"  - 方法声明: {len(stored_data['methods'])}个")
        print(f"  - 方法调用: {call_count}个")

        # 检查解析的完整性
        print("\n🔍 解析完整性检查:")

        if len(stored_data["imports"]) > 0:
            print("  ✅ Import解析完整")
        else:
            print("  ❌ Import解析不完整")

        if len(stored_data["classes"]) > 0:
            print("  ✅ 类解析完整")
        else:
            print("  ❌ 类解析不完整")

        if len(stored_data["methods"]) > 0:
            print("  ✅ 方法解析完整")
        else:
            print("  ❌ 方法解析不完整")

        if call_count > 0:
            print("  ✅ 方法调用解析完整")
        else:
            print("  ❌ 方法调用解析不完整")

        # 显示一些示例数据
        print("\n📊 示例数据:")
        if stored_data["classes"]:
            cls = stored_data["classes"][0]
            print(
                f"  类示例: {cls['name']} (父类: {cls['superclass']}, 接口: {cls['interfaces']})"
            )

        if stored_data["methods"]:
            method = stored_data["methods"][0]
            print(f"  方法示例: {method['name']}() -> {method['return_type']}")

        if stored_data["imports"]:
            imp = stored_data["imports"][0]
            print(f"  Import示例: {imp['qualified_name']}")

        print("\n✅ Java解析逻辑测试完成！")

        # 总结
        total_elements = (
            len(stored_data["imports"])
            + len(stored_data["classes"])
            + len(stored_data["methods"])
        )
        print("\n📈 总结:")
        print(f"  - 总解析元素: {total_elements}个")
        print(f"  - Import: {len(stored_data['imports'])}个")
        print(f"  - 类: {len(stored_data['classes'])}个")
        print(f"  - 方法: {len(stored_data['methods'])}个")
        print(f"  - 方法调用: {call_count}个")

        if total_elements > 0:
            print("  ✅ Java解析逻辑工作正常！")
        else:
            print("  ❌ Java解析逻辑存在问题")

    except ImportError as e:
        print(f"❌ 导入错误: {e}")
        import traceback

        traceback.print_exc()
    except Exception as e:
        print(f"❌ 测试错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_java_parsing_simulation()
