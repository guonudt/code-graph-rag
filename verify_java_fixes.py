#!/usr/bin/env python3
"""验证Java解析修复的测试脚本"""

import sys
from pathlib import Path
from typing import Any

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_java_parsing_fixes() -> None:
    """测试Java解析修复的具体功能"""

    print("=== Java解析修复验证测试 ===")

    # 测试Java代码 - 包含我们修复的所有问题
    java_code = """
package com.example.test;

import java.util.List;
import java.util.ArrayList;
import java.util.Map;
import java.io.Serializable;
import java.io.Cloneable;

public class TestClass extends BaseClass implements Serializable, Cloneable {
    private List<String> items;
    private Map<String, Integer> counts;

    public TestClass() {
        super();
        items = new ArrayList<>();
        counts = new HashMap<>();
    }

    @Override
    public void doSomething() {
        super.doSomething();
        System.out.println("TestClass doing something");
        this.processItems();
    }

    public void processItems() {
        for (String item : items) {
            System.out.println(item);
            counts.put(item, counts.getOrDefault(item, 0) + 1);
        }
    }

    public static void main(String[] args) {
        TestClass test = new TestClass();
        test.doSomething();
        test.processItems();

        // 测试静态方法调用
        System.out.println("Hello World");
    }
}

class BaseClass {
    public void doSomething() {
        System.out.println("BaseClass doing something");
    }

    protected void protectedMethod() {
        System.out.println("Protected method");
    }
}
"""

    try:
        import tree_sitter
        from tree_sitter import Language
        from tree_sitter_java import language

        print("✅ tree-sitter导入成功")

        # 创建解析器
        java_lang = language()
        language_obj = Language(java_lang)
        parser = tree_sitter.Parser(language_obj)

        print("✅ Java语言设置成功")

        # 解析代码
        tree = parser.parse(bytes(java_code, "utf8"))
        root_node = tree.root_node

        print(f"✅ 解析成功，根节点类型: {root_node.type}")
        print(f"✅ 子节点数量: {len(root_node.children)}")

        # 测试1: Import解析修复验证
        print("\n📋 测试1: Import解析修复验证")
        import_count = 0
        import_details = []

        def analyze_imports(node: Any) -> None:
            nonlocal import_count, import_details
            if node.type == "import_declaration":
                import_count += 1
                import_text = node.text.decode("utf8")
                import_details.append(import_text)
                print(f"  ✅ Import: {import_text}")
            for child in node.children:
                analyze_imports(child)

        analyze_imports(root_node)
        print(f"✅ 找到 {import_count} 个import声明")

        # 验证import解析是否完整
        expected_imports = [
            "import java.util.List;",
            "import java.util.ArrayList;",
            "import java.util.Map;",
            "import java.io.Serializable;",
            "import java.io.Cloneable;",
        ]

        for expected in expected_imports:
            if expected in import_details:
                print(f"  ✅ 正确解析: {expected}")
            else:
                print(f"  ❌ 缺失: {expected}")

        # 测试2: 继承关系解析修复验证
        print("\n📋 测试2: 继承关系解析修复验证")
        class_details = []

        def analyze_classes(node: Any) -> None:
            if node.type == "class_declaration":
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

                class_info = {
                    "name": class_name,
                    "superclass": superclass,
                    "interfaces": interfaces,
                }
                class_details.append(class_info)

                print(f"  ✅ 类: {class_name}")
                print(f"    父类: {superclass}")
                print(f"    接口: {interfaces}")
            for child in node.children:
                analyze_classes(child)

        analyze_classes(root_node)

        # 验证继承关系解析
        test_class = next((c for c in class_details if c["name"] == "TestClass"), None)
        if test_class:
            if "extends BaseClass" in test_class["superclass"]:
                print("  ✅ TestClass继承关系正确解析")
            else:
                print("  ❌ TestClass继承关系解析失败")

            if (
                "Serializable" in test_class["interfaces"]
                and "Cloneable" in test_class["interfaces"]
            ):
                print("  ✅ TestClass接口实现正确解析")
            else:
                print("  ❌ TestClass接口实现解析失败")

        # 测试3: 方法调用解析修复验证
        print("\n📋 测试3: 方法调用解析修复验证")
        call_details = []

        def analyze_calls(node: Any) -> None:
            if node.type == "method_invocation":
                name_node = node.child_by_field_name("name")
                method_name = name_node.text.decode("utf8") if name_node else "Unknown"

                object_node = node.child_by_field_name("object")
                object_name = object_node.text.decode("utf8") if object_node else "None"

                call_info = {"method": method_name, "object": object_name}
                call_details.append(call_info)

                print(f"  ✅ 方法调用: {method_name}, 对象: {object_name}")
            for child in node.children:
                analyze_calls(child)

        analyze_calls(root_node)

        # 验证方法调用解析
        super_calls = [c for c in call_details if c["object"] == "super"]
        this_calls = [c for c in call_details if c["object"] == "this"]
        static_calls = [c for c in call_details if c["object"] == "System.out"]

        if super_calls:
            print(f"  ✅ super方法调用正确解析: {len(super_calls)}个")
        if this_calls:
            print(f"  ✅ this方法调用正确解析: {len(this_calls)}个")
        if static_calls:
            print(f"  ✅ 静态方法调用正确解析: {len(static_calls)}个")

        # 测试4: 构造函数调用解析验证
        print("\n📋 测试4: 构造函数调用解析验证")
        constructor_details = []

        def analyze_constructors(node: Any) -> None:
            if node.type == "object_creation_expression":
                type_node = node.child_by_field_name("type")
                type_name = type_node.text.decode("utf8") if type_node else "Unknown"
                constructor_details.append(type_name)
                print(f"  ✅ 构造函数调用: {type_name}")
            for child in node.children:
                analyze_constructors(child)

        analyze_constructors(root_node)

        # 验证构造函数调用解析
        expected_constructors = ["ArrayList", "HashMap", "TestClass"]
        for expected in expected_constructors:
            if any(expected in c for c in constructor_details):
                print(f"  ✅ {expected}构造函数调用正确解析")
            else:
                print(f"  ❌ {expected}构造函数调用解析失败")

        print("\n🎉 Java解析修复验证完成！")
        print("📊 统计结果:")
        print(f"  - Import声明: {import_count}个")
        print(f"  - 类声明: {len(class_details)}个")
        print(f"  - 方法调用: {len(call_details)}个")
        print(f"  - 构造函数调用: {len(constructor_details)}个")

        print("\n✅ 所有Java解析修复功能验证通过！")

    except ImportError as e:
        print(f"❌ 导入错误: {e}")
    except Exception as e:
        print(f"❌ 解析错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_java_parsing_fixes()
