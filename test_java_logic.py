#!/usr/bin/env python3
"""简化测试Java解析逻辑，不依赖QueryCursor"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_java_parsing_logic():
    """测试Java解析逻辑的核心功能"""
    
    print("=== Java解析逻辑核心测试 ===")
    
    # 测试Java文件路径
    java_file = "/Users/guoshuai/git/uicfinal/uicfinal/uic-client-starter/src/main/java/com/taobao/uic/context/UicCommonContext.java"
    
    try:
        # 导入我们的Java工具函数
        from codebase_rag.parsers.java_utils import extract_java_import_path, extract_java_class_info, safe_decode_text
        
        print("✅ 成功导入Java工具函数")
        
        # 读取Java文件
        with open(java_file, 'r', encoding='utf-8') as f:
            java_code = f.read()
        
        print(f"✅ 读取Java文件成功")
        
        # 使用tree-sitter解析
        import tree_sitter
        from tree_sitter import Language
        from tree_sitter_java import language
        
        java_lang = language()
        language_obj = Language(java_lang)
        parser = tree_sitter.Parser(language_obj)
        tree = parser.parse(bytes(java_code, "utf8"))
        root_node = tree.root_node
        
        print(f"✅ tree-sitter解析成功")
        
        # 测试import解析
        print("\n📋 测试Import解析:")
        import_count = 0
        import_success = 0
        
        def test_imports(node):
            nonlocal import_count, import_success
            if node.type == "import_declaration":
                import_count += 1
                try:
                    import_info = extract_java_import_path(node)
                    if import_info:
                        print(f"  ✅ Import {import_count}: {import_info}")
                        import_success += 1
                    else:
                        print(f"  ❌ Import {import_count}: 解析失败")
                except Exception as e:
                    print(f"  ❌ Import {import_count}: 错误 - {e}")
            for child in node.children:
                test_imports(child)
        
        test_imports(root_node)
        print(f"✅ Import解析测试: {import_success}/{import_count} 成功")
        
        # 测试类解析
        print("\n📋 测试类解析:")
        class_count = 0
        class_success = 0
        
        def test_classes(node):
            nonlocal class_count, class_success
            if node.type == "class_declaration":
                class_count += 1
                try:
                    class_info = extract_java_class_info(node)
                    print(f"  ✅ 类 {class_count}: {class_info['name']}")
                    print(f"     父类: {class_info['superclass']}")
                    print(f"     接口: {class_info['interfaces']}")
                    class_success += 1
                except Exception as e:
                    print(f"  ❌ 类 {class_count}: 错误 - {e}")
            for child in node.children:
                test_classes(child)
        
        test_classes(root_node)
        print(f"✅ 类解析测试: {class_success}/{class_count} 成功")
        
        # 测试方法解析（简化版）
        print("\n📋 测试方法解析:")
        method_count = 0
        
        def test_methods(node):
            nonlocal method_count
            if node.type in ["method_declaration", "constructor_declaration"]:
                method_count += 1
                name_node = node.child_by_field_name("name")
                method_name = name_node.text.decode("utf8") if name_node else "Unknown"
                
                type_node = node.child_by_field_name("type")
                return_type = type_node.text.decode("utf8") if type_node else "void"
                
                if method_count <= 10:  # 只显示前10个
                    print(f"  ✅ 方法 {method_count}: {method_name}() -> {return_type}")
            for child in node.children:
                test_methods(child)
        
        test_methods(root_node)
        if method_count > 10:
            print(f"     ... 还有 {method_count - 10} 个方法")
        print(f"✅ 方法解析测试: 找到 {method_count} 个方法")
        
        # 测试方法调用解析（简化版）
        print("\n📋 测试方法调用解析:")
        call_count = 0
        
        def test_calls(node):
            nonlocal call_count
            if node.type == "method_invocation":
                call_count += 1
                name_node = node.child_by_field_name("name")
                method_name = name_node.text.decode("utf8") if name_node else "Unknown"
                
                object_node = node.child_by_field_name("object")
                object_name = object_node.text.decode("utf8") if object_node else "None"
                
                if call_count <= 10:  # 只显示前10个
                    print(f"  ✅ 调用 {call_count}: {object_name}.{method_name}()")
            for child in node.children:
                test_calls(child)
        
        test_calls(root_node)
        if call_count > 10:
            print(f"     ... 还有 {call_count - 10} 个方法调用")
        print(f"✅ 方法调用解析测试: 找到 {call_count} 个方法调用")
        
        print(f"\n🎯 解析逻辑测试总结:")
        print(f"  - Import解析: {import_success}/{import_count} 成功")
        print(f"  - 类解析: {class_success}/{class_count} 成功")
        print(f"  - 方法解析: {method_count} 个方法")
        print(f"  - 方法调用解析: {call_count} 个调用")
        
        # 分析可能的问题
        print(f"\n🔍 问题分析:")
        
        if import_success < import_count:
            print(f"  ❌ Import解析有问题: {import_count - import_success} 个失败")
        else:
            print(f"  ✅ Import解析正常")
        
        if class_success < class_count:
            print(f"  ❌ 类解析有问题: {class_count - class_success} 个失败")
        else:
            print(f"  ✅ 类解析正常")
        
        if method_count == 0:
            print(f"  ❌ 没有找到方法 - 可能存在方法解析问题")
        else:
            print(f"  ✅ 方法解析正常")
        
        if call_count == 0:
            print(f"  ❌ 没有找到方法调用 - 可能存在方法调用解析问题")
        else:
            print(f"  ✅ 方法调用解析正常")
        
        print(f"\n✅ Java解析逻辑测试完成！")
        
    except ImportError as e:
        print(f"❌ 导入错误: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"❌ 测试错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_java_parsing_logic()
