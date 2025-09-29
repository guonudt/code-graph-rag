#!/usr/bin/env python3
"""测试不依赖QueryCursor的Java解析流程"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_java_parsing_without_querycursor():
    """测试不依赖QueryCursor的Java解析流程"""
    
    print("=== Java解析流程测试（无QueryCursor） ===")
    
    # 测试Java文件路径
    java_file = "/Users/guoshuai/git/uicfinal/uicfinal/uic-client-starter/src/main/java/com/taobao/uic/context/UicCommonContext.java"
    
    try:
        # 导入必要的模块（避免QueryCursor依赖）
        from codebase_rag.services.graph_service import MemgraphIngestor
        
        print("✅ 成功导入图数据库服务")
        
        # 创建图数据库连接
        ingestor = MemgraphIngestor()
        
        # 测试数据库连接
        try:
            result = ingestor.fetch_all("MATCH (n) RETURN count(n) as total")
            print(f"✅ 数据库连接成功，当前节点数: {result[0]['total'] if result else 0}")
        except Exception as e:
            print(f"❌ 数据库连接失败: {e}")
            return
        
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
        
        # 手动解析import语句并存储到数据库
        print("\n📋 解析并存储Import语句:")
        import_count = 0
        import_stored = 0
        
        def process_imports(node):
            nonlocal import_count, import_stored
            if node.type == "import_declaration":
                import_count += 1
                try:
                    import_text = node.text.decode("utf8")
                    
                    # 解析import语句
                    parts = import_text.replace("import ", "").replace(";", "").split(".")
                    if len(parts) >= 2:
                        package_name = ".".join(parts[:-1])
                        class_name = parts[-1]
                        
                        # 存储到数据库
                        query = """
                        MERGE (p:Package {name: $package_name})
                        MERGE (c:Class {name: $class_name, qualified_name: $qualified_name})
                        MERGE (c)-[:BELONGS_TO]->(p)
                        """
                        params = {
                            "package_name": package_name,
                            "class_name": class_name,
                            "qualified_name": f"{package_name}.{class_name}"
                        }
                        
                        ingestor.fetch_all(query, params)
                        import_stored += 1
                        
                        if import_stored <= 5:  # 只显示前5个
                            print(f"  ✅ Import {import_stored}: {package_name}.{class_name}")
                
                except Exception as e:
                    print(f"  ❌ Import {import_count}: 错误 - {e}")
            
            for child in node.children:
                process_imports(child)
        
        process_imports(root_node)
        print(f"✅ Import解析和存储: {import_stored}/{import_count} 成功")
        
        # 手动解析类声明并存储到数据库
        print("\n📋 解析并存储类声明:")
        class_count = 0
        class_stored = 0
        
        def process_classes(node):
            nonlocal class_count, class_stored
            if node.type == "class_declaration":
                class_count += 1
                try:
                    name_node = node.child_by_field_name("name")
                    class_name = name_node.text.decode("utf8") if name_node else "Unknown"
                    
                    # 存储类到数据库
                    query = """
                    MERGE (c:Class {name: $class_name, qualified_name: $qualified_name})
                    SET c.type = 'Class'
                    """
                    params = {
                        "class_name": class_name,
                        "qualified_name": f"com.taobao.uic.context.{class_name}"
                    }
                    
                    ingestor.fetch_all(query, params)
                    class_stored += 1
                    
                    print(f"  ✅ 类 {class_stored}: {class_name}")
                
                except Exception as e:
                    print(f"  ❌ 类 {class_count}: 错误 - {e}")
            
            for child in node.children:
                process_classes(child)
        
        process_classes(root_node)
        print(f"✅ 类解析和存储: {class_stored}/{class_count} 成功")
        
        # 手动解析方法声明并存储到数据库
        print("\n📋 解析并存储方法声明:")
        method_count = 0
        method_stored = 0
        
        def process_methods(node):
            nonlocal method_count, method_stored
            if node.type in ["method_declaration", "constructor_declaration"]:
                method_count += 1
                try:
                    name_node = node.child_by_field_name("name")
                    method_name = name_node.text.decode("utf8") if name_node else "Unknown"
                    
                    type_node = node.child_by_field_name("type")
                    return_type = type_node.text.decode("utf8") if type_node else "void"
                    
                    # 存储方法到数据库
                    query = """
                    MERGE (m:Method {name: $method_name, qualified_name: $qualified_name})
                    SET m.return_type = $return_type, m.type = 'Method'
                    """
                    params = {
                        "method_name": method_name,
                        "qualified_name": f"com.taobao.uic.context.UicCommonContext.{method_name}",
                        "return_type": return_type
                    }
                    
                    ingestor.fetch_all(query, params)
                    method_stored += 1
                    
                    if method_stored <= 10:  # 只显示前10个
                        print(f"  ✅ 方法 {method_stored}: {method_name}() -> {return_type}")
                
                except Exception as e:
                    print(f"  ❌ 方法 {method_count}: 错误 - {e}")
            
            for child in node.children:
                process_methods(child)
        
        process_methods(root_node)
        if method_stored > 10:
            print(f"     ... 还有 {method_stored - 10} 个方法")
        print(f"✅ 方法解析和存储: {method_stored}/{method_count} 成功")
        
        # 检查数据库中的结果
        print("\n📋 检查数据库存储结果:")
        
        # 检查Package节点
        packages = ingestor.fetch_all("MATCH (p:Package) RETURN p.name as name ORDER BY p.name")
        print(f"  📦 Package节点: {len(packages)}个")
        
        # 检查Class节点
        classes = ingestor.fetch_all("MATCH (c:Class) RETURN c.name as name, c.qualified_name as qualified_name ORDER BY c.name")
        print(f"  🏗️ Class节点: {len(classes)}个")
        if len(classes) <= 10:
            for cls in classes:
                print(f"    - {cls['name']} ({cls['qualified_name']})")
        
        # 检查Method节点
        methods = ingestor.fetch_all("MATCH (m:Method) RETURN m.name as name, m.return_type as return_type ORDER BY m.name")
        print(f"  🔧 Method节点: {len(methods)}个")
        if len(methods) <= 10:
            for method in methods:
                print(f"    - {method['name']}() -> {method['return_type']}")
        
        print(f"\n🎯 解析和存储总结:")
        print(f"  - Import解析: {import_stored}/{import_count} 成功")
        print(f"  - 类解析: {class_stored}/{class_count} 成功")
        print(f"  - 方法解析: {method_stored}/{method_count} 成功")
        print(f"  - 数据库Package节点: {len(packages)}个")
        print(f"  - 数据库Class节点: {len(classes)}个")
        print(f"  - 数据库Method节点: {len(methods)}个")
        
        if len(packages) > 0 and len(classes) > 0 and len(methods) > 0:
            print(f"\n✅ Java解析和存储功能正常！")
        else:
            print(f"\n❌ Java解析和存储存在问题")
        
    except ImportError as e:
        print(f"❌ 导入错误: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"❌ 测试错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_java_parsing_without_querycursor()
