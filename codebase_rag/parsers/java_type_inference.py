"""Java-specific type inference engine using tree-sitter for precise semantic analysis."""

from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger
from tree_sitter import Node

from .import_processor import ImportProcessor
from .java_utils import (
    extract_java_class_info,
    extract_java_field_info,
    extract_java_method_call_info,
    safe_decode_text,
)

if TYPE_CHECKING:
    from .factory import ASTCacheProtocol


class JavaTypeInferenceEngine:
    """Handles precise type inference for Java using tree-sitter AST analysis."""

    def __init__(
        self,
        import_processor: ImportProcessor,
        function_registry: Any,
        repo_path: Path,
        project_name: str,
        ast_cache: "ASTCacheProtocol",
        queries: dict[str, Any],
        module_qn_to_file_path: dict[str, Path],
        class_inheritance: dict[str, list[str]],
    ):
        self.import_processor = import_processor
        self.function_registry = function_registry
        self.repo_path = repo_path
        self.project_name = project_name
        self.ast_cache = ast_cache
        self.queries = queries
        self.module_qn_to_file_path = module_qn_to_file_path
        self.class_inheritance = class_inheritance

        # Cache for variable type lookups to prevent infinite recursion
        self._lookup_cache: dict[str, str | None] = {}
        self._lookup_in_progress: set[str] = set()

    def build_java_variable_type_map(
        self, scope_node: Node, module_qn: str
    ) -> dict[str, str]:
        """
        Build a comprehensive map of variable names to their types within a Java scope.

        This analyzes:
        - Method parameters (formal_parameter nodes)
        - Local variable declarations (local_variable_declaration nodes)
        - Field declarations in the containing class
        - Constructor assignments

        Args:
            scope_node: The AST node representing the scope (method, constructor, etc.)
            module_qn: Qualified name of the current module

        Returns:
            Dictionary mapping variable names to their fully qualified type names
        """
        local_var_types: dict[str, str] = {}

        try:
            # 1. Analyze method/constructor parameters
            self._analyze_java_parameters(scope_node, local_var_types, module_qn)

            # 2. Analyze local variable declarations in the scope
            self._analyze_java_local_variables(scope_node, local_var_types, module_qn)

            # 3. Analyze field declarations from the containing class
            self._analyze_java_class_fields(scope_node, local_var_types, module_qn)

            # 4. Analyze constructor assignments and field initializations
            self._analyze_java_constructor_assignments(
                scope_node, local_var_types, module_qn
            )

            # 5. Analyze enhanced for loop variables using tree-sitter
            self._analyze_java_enhanced_for_loops(
                scope_node, local_var_types, module_qn
            )

            logger.debug(
                f"Built Java variable type map with {len(local_var_types)} entries"
            )

        except Exception as e:
            logger.error(f"Failed to build Java variable type map: {e}")

        return local_var_types

    def _analyze_java_parameters(
        self, scope_node: Node, local_var_types: dict[str, str], module_qn: str
    ) -> None:
        """Analyze formal parameters using tree-sitter field access."""
        # Get the formal parameter list
        params_node = scope_node.child_by_field_name("parameters")
        if not params_node:
            return

        for child in params_node.children:
            if child.type == "formal_parameter":
                # Extract parameter name and type using tree-sitter fields
                param_name_node = child.child_by_field_name("name")
                param_type_node = child.child_by_field_name("type")

                if param_name_node and param_type_node:
                    param_name = safe_decode_text(param_name_node)
                    param_type = safe_decode_text(param_type_node)

                    if param_name and param_type:
                        # Resolve the type to its fully qualified name
                        resolved_type = self._resolve_java_type_name(
                            param_type, module_qn
                        )
                        local_var_types[param_name] = resolved_type
                        logger.debug(f"Parameter: {param_name} -> {resolved_type}")

            elif child.type == "spread_parameter":
                # Handle varargs (String... args) using tree-sitter traversal
                param_name = None
                param_type = None

                for subchild in child.children:
                    if subchild.type == "type_identifier":
                        decoded_text = safe_decode_text(subchild)
                        if decoded_text:
                            param_type = decoded_text + "[]"  # Treat varargs as array
                    elif subchild.type == "variable_declarator":
                        name_node = subchild.child_by_field_name("name")
                        if name_node:
                            param_name = safe_decode_text(name_node)

                if param_name and param_type:
                    resolved_type = self._resolve_java_type_name(param_type, module_qn)
                    local_var_types[param_name] = resolved_type
                    logger.debug(f"Varargs parameter: {param_name} -> {resolved_type}")

    def _analyze_java_local_variables(
        self, scope_node: Node, local_var_types: dict[str, str], module_qn: str
    ) -> None:
        """Analyze local variable declarations using tree-sitter traversal."""
        self._traverse_for_local_variables(scope_node, local_var_types, module_qn)

    def _traverse_for_local_variables(
        self, node: Node, local_var_types: dict[str, str], module_qn: str
    ) -> None:
        """Recursively traverse AST to find local variable declarations."""
        if node.type == "local_variable_declaration":
            self._process_java_variable_declaration(node, local_var_types, module_qn)

        # Recursively traverse children
        for child in node.children:
            self._traverse_for_local_variables(child, local_var_types, module_qn)

    def _process_java_variable_declaration(
        self, decl_node: Node, local_var_types: dict[str, str], module_qn: str
    ) -> None:
        """Process a local_variable_declaration node to extract type information."""
        # Get the type field
        type_node = decl_node.child_by_field_name("type")
        if not type_node:
            return

        declared_type = safe_decode_text(type_node)
        if not declared_type:
            return

        # Get the variable declarator field
        declarator_node = decl_node.child_by_field_name("declarator")
        if not declarator_node:
            return

        # Handle single or multiple declarators
        if declarator_node.type == "variable_declarator":
            self._process_variable_declarator(
                declarator_node, declared_type, local_var_types, module_qn
            )
        else:
            # Multiple declarators - traverse to find them
            for child in declarator_node.children:
                if child.type == "variable_declarator":
                    self._process_variable_declarator(
                        child, declared_type, local_var_types, module_qn
                    )

    def _process_variable_declarator(
        self,
        declarator_node: Node,
        declared_type: str,
        local_var_types: dict[str, str],
        module_qn: str,
    ) -> None:
        """Process a variable_declarator node to extract variable name and infer actual type."""
        # Get variable name
        name_node = declarator_node.child_by_field_name("name")
        if not name_node:
            return

        var_name = safe_decode_text(name_node)
        if not var_name:
            return

        # Check if there's an initialization value
        value_node = declarator_node.child_by_field_name("value")
        if value_node:
            # Try to infer more specific type from the initializer
            inferred_type = self._infer_java_type_from_expression(value_node, module_qn)
            if inferred_type:
                # Use the inferred type if it's more specific
                resolved_type = self._resolve_java_type_name(inferred_type, module_qn)
                local_var_types[var_name] = resolved_type
                logger.debug(
                    f"Local variable (inferred): {var_name} -> {resolved_type}"
                )
                return

        # Fall back to declared type
        resolved_type = self._resolve_java_type_name(declared_type, module_qn)
        local_var_types[var_name] = resolved_type
        logger.debug(f"Local variable (declared): {var_name} -> {resolved_type}")

    def _analyze_java_class_fields(
        self, scope_node: Node, local_var_types: dict[str, str], module_qn: str
    ) -> None:
        """Analyze field declarations from the containing class for 'this' references."""
        # Find the containing class
        containing_class = self._find_containing_java_class(scope_node)
        if not containing_class:
            return

        # Get class body
        body_node = containing_class.child_by_field_name("body")
        if not body_node:
            return

        # Traverse class body for field declarations
        for child in body_node.children:
            if child.type == "field_declaration":
                field_info = extract_java_field_info(child)
                if field_info.get("name") and field_info.get("type"):
                    field_name = field_info["name"]
                    field_type = field_info["type"]

                    # Store as this.fieldName for accurate resolution
                    this_field_ref = f"this.{field_name}"
                    resolved_type = self._resolve_java_type_name(
                        str(field_type), module_qn
                    )
                    local_var_types[this_field_ref] = resolved_type

                    # Also store without 'this.' for direct field access
                    # Only add if not already present (respect variable shadowing)
                    if str(field_name) not in local_var_types:
                        local_var_types[str(field_name)] = resolved_type
                    logger.debug(f"Class field: {field_name} -> {resolved_type}")

    def _analyze_java_constructor_assignments(
        self, scope_node: Node, local_var_types: dict[str, str], module_qn: str
    ) -> None:
        """Analyze constructor assignments for field initialization patterns."""
        # This is for patterns like: this.field = new SomeClass();
        self._traverse_for_assignments(scope_node, local_var_types, module_qn)

    def _traverse_for_assignments(
        self, node: Node, local_var_types: dict[str, str], module_qn: str
    ) -> None:
        """Recursively traverse to find assignment expressions."""
        if node.type == "assignment_expression":
            self._process_java_assignment(node, local_var_types, module_qn)

        # Recursively traverse children
        for child in node.children:
            self._traverse_for_assignments(child, local_var_types, module_qn)

    def _process_java_assignment(
        self, assignment_node: Node, local_var_types: dict[str, str], module_qn: str
    ) -> None:
        """Process Java assignment expressions to infer types."""
        # Get left and right sides of assignment
        left_node = assignment_node.child_by_field_name("left")
        right_node = assignment_node.child_by_field_name("right")

        if not left_node or not right_node:
            return

        # Extract variable name from left side
        var_name = self._extract_java_variable_reference(left_node)
        if not var_name:
            return

        # Infer type from right side
        inferred_type = self._infer_java_type_from_expression(right_node, module_qn)
        if inferred_type:
            resolved_type = self._resolve_java_type_name(inferred_type, module_qn)
            local_var_types[var_name] = resolved_type
            logger.debug(f"Assignment: {var_name} -> {resolved_type}")

    def _extract_java_variable_reference(self, node: Node) -> str | None:
        """Extract variable reference from left side of assignment."""
        if node.type == "identifier":
            return safe_decode_text(node)
        elif node.type == "field_access":
            # Handle this.field pattern
            object_node = node.child_by_field_name("object")
            field_node = node.child_by_field_name("field")

            if object_node and field_node:
                object_name = safe_decode_text(object_node)
                field_name = safe_decode_text(field_node)

                if object_name and field_name:
                    return f"{object_name}.{field_name}"

        return None

    def _infer_java_type_from_expression(
        self, expr_node: Node, module_qn: str
    ) -> str | None:
        """Infer Java type from various expression types."""
        if expr_node.type == "object_creation_expression":
            # Handle 'new SomeClass()' expressions
            type_node = expr_node.child_by_field_name("type")
            if type_node:
                return safe_decode_text(type_node)

        elif expr_node.type == "method_invocation":
            # Handle method call return types
            return self._infer_java_method_return_type(expr_node, module_qn)

        elif expr_node.type == "identifier":
            # Handle variable references - look up their types
            var_name = safe_decode_text(expr_node)
            if var_name:
                return self._lookup_variable_type(var_name, module_qn)

        elif expr_node.type == "field_access":
            # Handle field access expressions
            return self._infer_java_field_access_type(expr_node, module_qn)

        elif expr_node.type == "string_literal":
            return "String"

        elif expr_node.type == "integer_literal":
            return "int"

        elif expr_node.type == "decimal_floating_point_literal":
            return "double"

        elif expr_node.type == "true" or expr_node.type == "false":
            return "boolean"

        elif expr_node.type == "array_creation_expression":
            # Handle array creation
            type_node = expr_node.child_by_field_name("type")
            if type_node:
                base_type = safe_decode_text(type_node)
                return f"{base_type}[]" if base_type else None

        return None

    def _infer_java_method_return_type(
        self, method_call_node: Node, module_qn: str
    ) -> str | None:
        """Infer return type of a Java method invocation."""
        call_info = extract_java_method_call_info(method_call_node)

        method_name = call_info.get("name")
        object_ref = call_info.get("object")

        if not method_name:
            return None

        # Build the method call string for resolution
        if object_ref:
            call_string = f"{object_ref}.{method_name}"
        else:
            call_string = str(method_name)

        # Try to resolve the method and get its return type
        return self._resolve_java_method_return_type(call_string, module_qn)

    def _infer_java_field_access_type(
        self, field_access_node: Node, module_qn: str
    ) -> str | None:
        """Infer type of field access expressions."""
        object_node = field_access_node.child_by_field_name("object")
        field_node = field_access_node.child_by_field_name("field")

        if not object_node or not field_node:
            return None

        object_name = safe_decode_text(object_node)
        field_name = safe_decode_text(field_node)

        if not object_name or not field_name:
            return None

        # Get the type of the object
        object_type = self._lookup_variable_type(object_name, module_qn)
        if not object_type:
            return None

        # Look up the field type in the object's class
        return self._lookup_java_field_type(object_type, field_name, module_qn)

    def _resolve_java_method_return_type(
        self, method_call: str, module_qn: str
    ) -> str | None:
        """Resolve the return type of a Java method call using AST analysis."""
        if not method_call:
            return None

        # Parse the method call to extract object and method parts
        parts = method_call.split(".")
        if len(parts) < 2:
            # Simple method call without object - look in current class
            method_name = method_call
            current_class_qn = self._get_current_class_name(module_qn)
            if current_class_qn:
                return self._find_method_return_type(current_class_qn, method_name)
        else:
            # Method call on an object - resolve the object type first
            object_part = ".".join(parts[:-1])
            method_name = parts[-1]

            # Check if it's a static method call on a fully qualified class
            if object_part in self.function_registry:
                return self._find_method_return_type(object_part, method_name)

            # Try to resolve object type as a local variable
            object_type = self._lookup_variable_type(object_part, module_qn)
            if object_type:
                return self._find_method_return_type(object_type, method_name)

            # Check if it's a static method call on a class in the same package
            potential_class_qn = f"{module_qn}.{object_part}"
            if potential_class_qn in self.function_registry:
                return self._find_method_return_type(potential_class_qn, method_name)

        # Fallback to heuristics for common patterns
        return self._heuristic_method_return_type(method_call)

    def _find_method_return_type(self, class_qn: str, method_name: str) -> str | None:
        """Find the return type of a method in a specific class using AST analysis."""
        if not class_qn or not method_name:
            return None

        # Extract module and class information
        parts = class_qn.split(".")
        if len(parts) < 2:
            return None

        module_qn = ".".join(parts[:-1])
        target_class_name = parts[-1]

        # Get the AST for the module
        file_path = self.module_qn_to_file_path.get(module_qn)
        if file_path is None or file_path not in self.ast_cache:
            return None

        root_node, _ = self.ast_cache[file_path]

        # Find the method in the class and extract its return type
        return self._find_method_return_type_in_ast(
            root_node, target_class_name, method_name, module_qn
        )

    def _find_method_return_type_in_ast(
        self, node: Node, class_name: str, method_name: str, module_qn: str
    ) -> str | None:
        """Find method return type by traversing the AST."""
        if node.type == "class_declaration":
            # Check if this is the target class
            name_node = node.child_by_field_name("name")
            if name_node and safe_decode_text(name_node) == class_name:
                # Found the target class, look for the method
                body_node = node.child_by_field_name("body")
                if body_node:
                    return self._search_methods_in_class_body(
                        body_node, method_name, module_qn
                    )

        # Recursively traverse children
        for child in node.children:
            result = self._find_method_return_type_in_ast(
                child, class_name, method_name, module_qn
            )
            if result:
                return result

        return None

    def _search_methods_in_class_body(
        self, body_node: Node, method_name: str, module_qn: str
    ) -> str | None:
        """Search for a specific method in a class body and return its return type."""
        for child in body_node.children:
            if child.type == "method_declaration":
                # Check method name
                name_node = child.child_by_field_name("name")
                if name_node and safe_decode_text(name_node) == method_name:
                    # Found the method, extract return type
                    type_node = child.child_by_field_name("type")
                    if type_node:
                        return_type = safe_decode_text(type_node)
                        if return_type:
                            # Resolve to fully qualified name
                            return self._resolve_java_type_name(return_type, module_qn)
        return None

    def _heuristic_method_return_type(self, method_call: str) -> str | None:
        """Fallback heuristics for common Java patterns when AST analysis fails."""
        if "get" in method_call.lower():
            # Getter methods often return the field type
            if "string" in method_call.lower() or "name" in method_call.lower():
                return "java.lang.String"
            elif "id" in method_call.lower():
                return "java.lang.Long"
            elif "size" in method_call.lower() or "length" in method_call.lower():
                return "int"
        elif "create" in method_call.lower() or "new" in method_call.lower():
            # Factory methods often return instances of the class they're creating
            parts = method_call.split(".")
            if len(parts) >= 2:
                method_name = parts[-1]
                if "user" in method_name.lower():
                    return "User"
                elif "order" in method_name.lower():
                    return "Order"
        elif "is" in method_call.lower() or "has" in method_call.lower():
            return "boolean"

        return None

    def _lookup_java_field_type(
        self, class_type: str, field_name: str, module_qn: str
    ) -> str | None:
        """Look up the type of a field in a Java class."""
        if not class_type or not field_name:
            return None

        # Resolve class_type to fully qualified name if needed
        resolved_class_type = self._resolve_java_type_name(class_type, module_qn)

        # If resolved_class_type is already a FQN, use it directly.
        # Otherwise, assume it's a class in the same package.
        if "." in resolved_class_type:
            class_qn = resolved_class_type
        else:
            class_qn = f"{module_qn}.{resolved_class_type}"

        # Extract module and class information
        parts = class_qn.split(".")
        if len(parts) < 2:
            return None

        # Get the module qualified name and target class
        target_module_qn = ".".join(parts[:-1])
        target_class_name = parts[-1]

        # Use the direct mapping from module QN to file path - much more robust!
        file_path = self.module_qn_to_file_path.get(target_module_qn)
        if file_path is None or file_path not in self.ast_cache:
            return None

        root_node, _ = self.ast_cache[file_path]

        # Find the class and its field using tree-sitter
        field_type = self._find_field_type_in_class(
            root_node, target_class_name, field_name, target_module_qn
        )

        return field_type

    def _lookup_variable_type(self, var_name: str, module_qn: str) -> str | None:
        """Look up the type of a variable by analyzing the module scope."""
        if not var_name or not module_qn:
            return None

        # Create a cache key to prevent infinite recursion
        cache_key = f"{module_qn}:{var_name}"
        if cache_key in self._lookup_cache:
            return self._lookup_cache[cache_key]

        # Mark as being processed to detect cycles
        if cache_key in self._lookup_in_progress:
            return None  # Cycle detected, return None to break recursion

        self._lookup_in_progress.add(cache_key)

        try:
            # Get the AST for the module
            module_parts = module_qn.split(".")
            if len(module_parts) < 2:
                result = None
            else:
                # Use the direct mapping from module QN to file path - much more robust!
                file_path = self.module_qn_to_file_path.get(module_qn)
                if file_path is None or file_path not in self.ast_cache:
                    result = None
                else:
                    root_node, _ = self.ast_cache[file_path]

                    # Build variable type map for this module and look up the variable
                    variable_types = self.build_java_variable_type_map(
                        root_node, module_qn
                    )

                    # Check different forms of the variable name
                    if var_name in variable_types:
                        result = variable_types[var_name]
                    elif f"this.{var_name}" in variable_types:
                        result = variable_types[f"this.{var_name}"]
                    else:
                        result = None

            # Cache the result
            self._lookup_cache[cache_key] = result
            return result

        finally:
            # Always remove from in-progress set
            self._lookup_in_progress.discard(cache_key)

    def _resolve_java_type_name(self, type_name: str, module_qn: str) -> str:
        """Resolve a Java type name to its fully qualified name."""
        if not type_name:
            return "Object"  # Default fallback

        # Handle primitive types
        if type_name in [
            "int",
            "long",
            "double",
            "float",
            "boolean",
            "char",
            "byte",
            "short",
        ]:
            return type_name

        # Handle common Java types
        if type_name in ["String", "Object", "Integer", "Long", "Double", "Boolean"]:
            return f"java.lang.{type_name}"

        # Handle arrays
        if type_name.endswith("[]"):
            base_type = type_name[:-2]
            resolved_base = self._resolve_java_type_name(base_type, module_qn)
            return f"{resolved_base}[]"

        # Handle generic types (basic support)
        if "<" in type_name and ">" in type_name:
            # Extract base type before the generic parameters
            base_type = type_name.split("<")[0]
            return self._resolve_java_type_name(base_type, module_qn)

        # Check imports for the type
        if module_qn in self.import_processor.import_mapping:
            import_map = self.import_processor.import_mapping[module_qn]
            if type_name in import_map:
                return import_map[type_name]

        # Check if it's a class or interface in the same package
        same_package_qn = f"{module_qn}.{type_name}"
        if same_package_qn in self.function_registry and self.function_registry[
            same_package_qn
        ] in ["Class", "Interface"]:
            return same_package_qn

        # Fallback: return as-is (might be a simple class name)
        return type_name

    def _find_containing_java_class(self, node: Node) -> Node | None:
        """Find the Java class that contains the given node."""
        current = node.parent
        while current:
            if current.type in [
                "class_declaration",
                "interface_declaration",
                "enum_declaration",
                "record_declaration",
            ]:
                return current
            current = current.parent
        return None

    def resolve_java_method_call(
        self, call_node: Node, local_var_types: dict[str, str], module_qn: str
    ) -> tuple[str, str] | None:
        """
        Resolve a Java method invocation to its qualified name and type.

        This is the main entry point for precise method call resolution.

        Args:
            call_node: The method_invocation AST node
            local_var_types: Map of variable names to types in current scope
            module_qn: Qualified name of current module

        Returns:
            Tuple of (method_type, method_qualified_name) or None if not resolvable
        """
        call_text = call_node.text.decode("utf8") if call_node.text else "unknown"
        logger.info(
            f"☕ Resolving Java method call: '{call_text}' in module: '{module_qn}'"
        )

        if call_node.type != "method_invocation":
            logger.warning(f"❌ Expected method_invocation node, got: {call_node.type}")
            return None

        call_info = extract_java_method_call_info(call_node)
        method_name = call_info.get("name")
        object_ref = call_info.get("object")

        logger.debug(
            f"📋 Extracted call info - method: '{method_name}', object: '{object_ref}'"
        )

        if not method_name:
            logger.warning("❌ No method name found in call node")
            return None

        # Case 1: Static method call or call without object (e.g., "method()" or "Class.method()")
        if not object_ref:
            logger.info(f"🔍 Resolving static/local method: '{method_name}'")
            logger.debug(
                f"📊 Available local variables: {list(local_var_types.keys())}"
            )
            result = self._resolve_static_or_local_method(str(method_name), module_qn)
            if result:
                logger.info(f"✅ Found static/local method: {result}")
            else:
                logger.warning(f"❌ Static/local method not found: '{method_name}'")
            return result

        # Case 2: Instance method call (e.g., "obj.method()")
        # First, determine the type of the object
        logger.info(f"🔍 Resolving object type for: '{object_ref}'")
        logger.debug(f"📊 Available local variables: {list(local_var_types.keys())}")

        object_type = self._resolve_java_object_type(
            str(object_ref), local_var_types, module_qn
        )
        if not object_type:
            logger.warning(f"❌ Could not determine type of object: '{object_ref}'")
            logger.debug(f"📊 Local variables available: {local_var_types}")
            logger.debug(f"📊 Module: '{module_qn}'")
            return None

        logger.info(f"✅ Object type resolved to: '{object_type}'")
        # Now find the method in the object's class
        result = self._resolve_instance_method(object_type, str(method_name), module_qn)
        if result:
            logger.info(f"✅ Found instance method: {result}")
        else:
            logger.warning(
                f"❌ Instance method not found: '{object_type}.{method_name}'"
            )
        return result

    def _resolve_java_object_type(
        self, object_ref: str, local_var_types: dict[str, str], module_qn: str
    ) -> str | None:
        """Resolve the type of a Java object reference using tree-sitter analysis."""
        logger.debug(
            f"🔍 Resolving Java object type for: '{object_ref}' in module: '{module_qn}'"
        )
        logger.debug(f"📊 Available local variables: {list(local_var_types.keys())}")

        # Check if it's a local variable
        if object_ref in local_var_types:
            result = local_var_types[object_ref]
            logger.debug(f"✅ Found as local variable: '{object_ref}' -> '{result}'")
            return result

        # Check for 'this' reference - find the containing class
        if object_ref == "this":
            logger.debug(f"🔍 Processing 'this' reference in module: '{module_qn}'")
            logger.debug(
                f"📊 Function registry contains {len(self.function_registry)} entries"
            )

            # Look for any class in the current module (simplified)
            matching_classes = []
            for qn, entity_type in self.function_registry.items():
                if entity_type == "Class" and qn.startswith(module_qn + "."):
                    matching_classes.append(qn)
                    logger.debug(
                        f"📋 Found matching class: '{qn}' (type: {entity_type})"
                    )

            if matching_classes:
                # If multiple classes, prefer the one that matches the module name exactly
                for qn in matching_classes:
                    if qn == module_qn or qn.startswith(module_qn + "."):
                        logger.debug(f"✅ Selected 'this' class: '{qn}'")
                        return str(qn)
                # Fallback to first match
                result = str(matching_classes[0])
                logger.debug(f"✅ Fallback 'this' class: '{result}'")
                return result
            else:
                logger.warning(
                    f"❌ No classes found in module '{module_qn}' for 'this' reference"
                )
                return None

        # Check for 'super' reference
        if object_ref == "super":
            logger.debug(f"🔍 Processing 'super' reference in module: '{module_qn}'")

            # For super calls, we need to look at parent classes
            # This is a simplified implementation
            matching_classes = []
            for qn, entity_type in self.function_registry.items():
                if entity_type == "Class" and qn.startswith(module_qn + "."):
                    matching_classes.append(qn)
                    logger.debug(f"📋 Found class for super lookup: '{qn}'")

            for qn in matching_classes:
                # Look for parent classes - simplified approach
                parent_qn = self._find_parent_class(qn)
                if parent_qn:
                    logger.debug(f"✅ Found super class: '{qn}' -> '{parent_qn}'")
                    return parent_qn
                else:
                    logger.debug(f"⚠️ No parent class found for: '{qn}'")

            logger.warning(
                f"❌ No super class found for any class in module '{module_qn}'"
            )
            return None

        # Check if it's a static class reference
        if module_qn in self.import_processor.import_mapping:
            import_map = self.import_processor.import_mapping[module_qn]
            logger.debug(
                f"📦 Import map for module '{module_qn}': {list(import_map.keys())}"
            )

            if object_ref in import_map:
                result = import_map[object_ref]
                logger.debug(
                    f"✅ Found as imported class: '{object_ref}' -> '{result}'"
                )
                return result
        else:
            logger.debug(f"⚠️ No import mapping found for module: '{module_qn}'")

        # Check if it's a simple class name in the same package
        # First, try to find the actual package name from the module_qn
        package_name = self._extract_java_package_name(module_qn)
        if package_name:
            same_package_class_qn = f"{package_name}.{object_ref}"
            logger.debug(f"🔍 Checking same package class: '{same_package_class_qn}'")

            if (
                same_package_class_qn in self.function_registry
                and self.function_registry[same_package_class_qn] == "Class"
            ):
                logger.debug(
                    f"✅ Found as same package class: '{same_package_class_qn}'"
                )
                return same_package_class_qn
            else:
                logger.debug(
                    f"📊 Function registry entries starting with '{same_package_class_qn}':"
                )
                for qn, entity_type in self.function_registry.items():
                    if qn.startswith(same_package_class_qn):
                        logger.debug(f"  - {qn} ({entity_type})")

        # Fallback: try to extract package from module_qn by removing the filename
        # module_qn format: "project.src.main.java.com.alibaba.havana.demo.diamond.DiamondController"
        # We need: "project.src.main.java.com.alibaba.havana.demo.diamond" (remove filename)
        fallback_package = self._extract_package_from_module_qn(module_qn)
        if fallback_package:
            fallback_class_qn = f"{fallback_package}.{object_ref}"
            logger.debug(f"🔍 Checking fallback package class: '{fallback_class_qn}'")

            if (
                fallback_class_qn in self.function_registry
                and self.function_registry[fallback_class_qn] == "Class"
            ):
                logger.debug(
                    f"✅ Found as fallback package class: '{fallback_class_qn}'"
                )
                return fallback_class_qn
            else:
                logger.debug(
                    f"❌ Fallback package class '{fallback_class_qn}' not found in function registry"
                )
                logger.debug(
                    f"📊 Function registry entries starting with '{fallback_class_qn}':"
                )
                for qn, entity_type in self.function_registry.items():
                    if qn.startswith(fallback_class_qn):
                        logger.debug(f"  - {qn} ({entity_type})")

        # Last resort: try with module_qn directly (for cases where module_qn is the package)
        simple_class_qn = f"{module_qn}.{object_ref}"
        logger.debug(f"🔍 Checking simple class name: '{simple_class_qn}'")

        if (
            simple_class_qn in self.function_registry
            and self.function_registry[simple_class_qn] == "Class"
        ):
            logger.debug(f"✅ Found as simple class: '{simple_class_qn}'")
            return simple_class_qn
        else:
            logger.debug(
                f"❌ Simple class '{simple_class_qn}' not found in function registry"
            )

        # Additional debugging: show what's available in function registry
        logger.debug(f"📊 Function registry entries starting with '{module_qn}':")
        for qn, entity_type in self.function_registry.items():
            if qn.startswith(module_qn):
                logger.debug(f"  - {qn} ({entity_type})")

        logger.warning(
            f"❌ Could not resolve object type for: '{object_ref}' in module: '{module_qn}'"
        )
        return None

    def _extract_java_package_name(self, module_qn: str) -> str | None:
        """Extract the actual Java package name from module_qn.

        With the new design, module_qn format is: project_name.module_name.src.main.java.package_name.class_name
        We need to extract the package part (everything except the last part which is class_name).

        Args:
            module_qn: The module qualified name (format: project_name.module_name.src.main.java.package_name.class_name)

        Returns:
            The Java package name (project_name.module_name.src.main.java.package_name)
        """
        if not module_qn:
            return None

        # Split the module_qn and remove the last part (class name) to get package
        parts = module_qn.split(".")
        if len(parts) < 2:
            return None

        # Remove the last part (class name) to get package
        package_parts = parts[:-1]
        return ".".join(package_parts)

    def _find_package_declaration(self, root_node: Node) -> str | None:
        """Find package declaration in Java AST."""
        for child in root_node.children:
            if child.type == "package_declaration":
                # Extract package name from package declaration
                package_name = self._extract_package_name_from_declaration(child)
                if package_name:
                    return package_name
        return None

    def _extract_package_name_from_declaration(self, package_node: Node) -> str | None:
        """Extract package name from package declaration node."""
        # Look for scoped_identifier or identifier nodes in package declaration
        for child in package_node.children:
            if child.type in ["scoped_identifier", "identifier"]:
                return safe_decode_text(child)
        return None

    def _extract_package_from_module_qn(self, module_qn: str) -> str | None:
        """Extract package name from module_qn.

        With the new design, module_qn format is: project_name.module_name.src.main.java.package_name.class_name
        We need to extract the package part (everything except the last part which is class_name).

        Args:
            module_qn: The module qualified name (format: project_name.module_name.src.main.java.package_name.class_name)

        Returns:
            The package name (project_name.module_name.src.main.java.package_name)
        """
        if not module_qn:
            return None

        # Split the module_qn and remove the last part (class name) to get package
        parts = module_qn.split(".")
        if len(parts) < 2:
            return None

        # Remove the last part (class name) to get package
        package_parts = parts[:-1]
        return ".".join(package_parts)

    def _find_parent_class(self, class_qn: str) -> str | None:
        """Find the parent class of a given class using actual inheritance data."""
        logger.debug(f"🔍 Looking for parent class of: '{class_qn}'")
        logger.debug(
            f"📊 Class inheritance data contains {len(self.class_inheritance)} classes"
        )

        # Look up the parent class from the parsed inheritance information
        parent_classes = self.class_inheritance.get(class_qn, [])
        logger.debug(f"📋 Parent classes for '{class_qn}': {parent_classes}")

        # Return the first parent class if any exists
        # In Java, there's only one direct superclass due to single inheritance
        if parent_classes:
            result = parent_classes[0]
            logger.debug(f"✅ Found parent class: '{class_qn}' -> '{result}'")
            return result
        else:
            logger.debug(f"❌ No parent classes found for: '{class_qn}'")
            return None

    def _resolve_static_or_local_method(
        self, method_name: str, module_qn: str
    ) -> tuple[str, str] | None:
        """Resolve a static method call or local method call using tree-sitter."""
        logger.debug(
            f"🔍 Resolving static/local method: '{method_name}' in module: '{module_qn}'"
        )
        logger.debug(
            f"📊 Function registry contains {len(self.function_registry)} entries"
        )

        # Search for methods in the current module that match the method name
        matching_methods = []
        for qn, entity_type in self.function_registry.items():
            if (
                qn.startswith(f"{module_qn}.")
                and entity_type in ["Method", "Constructor"]
                and qn.split("(")[0].endswith(f".{method_name}")
            ):
                matching_methods.append((entity_type, qn))
                logger.debug(
                    f"📋 Found matching static/local method: {qn} ({entity_type})"
                )

        if matching_methods:
            result = matching_methods[0]
            logger.debug(f"✅ Selected static/local method: {result}")
            return result
        else:
            logger.debug(
                f"❌ No static/local methods found for '{method_name}' in module '{module_qn}'"
            )
            logger.debug(f"📊 Available methods in module '{module_qn}':")
            for qn, entity_type in self.function_registry.items():
                if qn.startswith(f"{module_qn}.") and entity_type in [
                    "Method",
                    "Constructor",
                ]:
                    logger.debug(f"  - {qn} ({entity_type})")
            return None

    def _resolve_instance_method(
        self, object_type: str, method_name: str, module_qn: str
    ) -> tuple[str, str] | None:
        """Resolve an instance method call on a specific object type using tree-sitter."""
        logger.info(
            f"🔍 Resolving instance method: '{object_type}.{method_name}' in module: '{module_qn}'"
        )

        # Resolve object_type to fully qualified name
        logger.debug(
            f"📝 Step 1: Resolving object type '{object_type}' to fully qualified name"
        )
        resolved_type = self._resolve_java_type_name(object_type, module_qn)
        logger.debug(f"✅ Resolved object type: '{object_type}' -> '{resolved_type}'")

        if not resolved_type:
            logger.warning(f"❌ Failed to resolve object type: '{object_type}'")
            return None

        # Look for the method in the class using flexible signature matching
        logger.debug(
            f"📝 Step 2: Looking for method '{method_name}' in class '{resolved_type}'"
        )
        method_result = self._find_method_with_any_signature(resolved_type, method_name)
        if method_result:
            logger.info(
                f"✅ Found method in class: '{resolved_type}.{method_name}' -> {method_result}"
            )
            return method_result
        else:
            logger.debug(
                f"❌ Method '{method_name}' not found in class '{resolved_type}'"
            )

        # Check inheritance hierarchy and interface implementations using tree-sitter navigation
        logger.debug(
            f"📝 Step 3: Checking inheritance hierarchy for method '{method_name}'"
        )
        inherited_result = self._find_inherited_method(
            resolved_type, method_name, module_qn
        )
        if inherited_result:
            logger.info(
                f"✅ Found inherited method: '{resolved_type}.{method_name}' -> {inherited_result}"
            )
            return inherited_result
        else:
            logger.debug(
                f"❌ Method '{method_name}' not found in inheritance hierarchy"
            )

        # Also check interface implementations
        logger.debug(
            f"📝 Step 4: Checking interface implementations for method '{method_name}'"
        )
        interface_result = self._find_interface_method(
            resolved_type, method_name, module_qn
        )
        if interface_result:
            logger.info(
                f"✅ Found interface method: '{resolved_type}.{method_name}' -> {interface_result}"
            )
            return interface_result
        else:
            logger.debug(
                f"❌ Method '{method_name}' not found in interface implementations"
            )

        logger.warning(
            f"❌ Could not resolve instance method: '{resolved_type}.{method_name}'"
        )
        logger.debug(f"📊 Function registry entries for '{resolved_type}':")
        for qn, entity_type in self.function_registry.items():
            if qn.startswith(resolved_type):
                logger.debug(f"  - {qn} ({entity_type})")

        return None

    def _find_method_with_any_signature(
        self, class_qn: str, method_name: str
    ) -> tuple[str, str] | None:
        """Find a method with any parameter signature using function registry."""
        logger.debug(f"🔍 Searching for method '{method_name}' in class '{class_qn}'")
        logger.debug(
            f"📊 Function registry contains {len(self.function_registry)} entries"
        )

        # Search through all registered methods for this class and method name
        target_pattern = f"{class_qn}.{method_name}"
        logger.debug(f"📝 Looking for pattern: '{target_pattern}'")

        matching_methods = []
        for qn, method_type in self.function_registry.items():
            # Use contains to find methods that include the method name
            if (
                class_qn in qn
                and method_name in qn
                and method_type in ["Method", "Constructor"]
            ):
                logger.debug(f"📋 Found potential match: '{qn}' (type: {method_type})")

                # Handle format: package.Class.Class.method(params)
                # Extract the simple class name from the full qualified name
                simple_class_name = class_qn.split(".")[-1]
                logger.debug(f"    Simple class name: '{simple_class_name}'")

                # Look for pattern: class_qn.simple_class_name.method_name
                expected_pattern = f"{class_qn}.{simple_class_name}.{method_name}"
                logger.debug(f"    Expected pattern: '{expected_pattern}'")

                if qn.startswith(expected_pattern):
                    # Extract the part after method name
                    after_method = qn[len(expected_pattern) :]
                    logger.debug(f"    After method name: '{after_method}'")

                    # Valid if it's empty or starts with ( or <
                    if (
                        after_method == ""
                        or after_method.startswith("(")
                        or after_method.startswith("<")
                    ):
                        matching_methods.append((method_type, qn))
                        logger.debug(
                            f"✅ Valid method match: '{qn}' (type: {method_type})"
                        )
                    else:
                        logger.debug(
                            f"❌ Invalid pattern - after method '{after_method}' doesn't start with '(' or '<'"
                        )
                else:
                    # Fallback: try to find method name after any occurrence of simple class name
                    simple_class_pattern = f".{simple_class_name}.{method_name}"
                    logger.debug(f"    Fallback pattern: '{simple_class_pattern}'")

                    if simple_class_pattern in qn:
                        # Find the position of this pattern
                        pattern_index = qn.find(simple_class_pattern)
                        after_method = qn[pattern_index + len(simple_class_pattern) :]
                        logger.debug(
                            f"    Fallback - after method name: '{after_method}'"
                        )

                        if (
                            after_method == ""
                            or after_method.startswith("(")
                            or after_method.startswith("<")
                        ):
                            matching_methods.append((method_type, qn))
                            logger.debug(
                                f"✅ Valid fallback match: '{qn}' (type: {method_type})"
                            )
                        else:
                            logger.debug(
                                f"❌ Invalid fallback pattern - after method '{after_method}' doesn't start with '(' or '<'"
                            )
                    else:
                        logger.debug(
                            f"❌ Neither primary nor fallback pattern found in '{qn}'"
                        )

        if matching_methods:
            result = matching_methods[0]
            logger.debug(f"✅ Selected method: {result}")
            logger.debug(f"📊 Total matches found: {len(matching_methods)}")
            return result
        else:
            logger.debug(f"❌ No methods found for '{class_qn}.{method_name}'")

            # Show all methods for this class
            logger.debug(f"📊 Available methods for class '{class_qn}':")
            class_methods = []
            for qn, entity_type in self.function_registry.items():
                if qn.startswith(class_qn) and entity_type in ["Method", "Constructor"]:
                    class_methods.append(f"{qn} ({entity_type})")

            if class_methods:
                for method in class_methods:
                    logger.debug(f"  - {method}")
            else:
                logger.debug(f"  No methods found for class '{class_qn}'")

            # Show all methods containing the method name
            logger.debug(f"📊 All methods containing '{method_name}':")
            name_matches = []
            for qn, entity_type in self.function_registry.items():
                if method_name in qn and entity_type in ["Method", "Constructor"]:
                    name_matches.append(f"{qn} ({entity_type})")

            if name_matches:
                for match in name_matches:
                    logger.debug(f"  - {match}")
            else:
                logger.debug(f"  No methods found containing '{method_name}'")

            return None

    def _find_inherited_method(
        self, class_qn: str, method_name: str, module_qn: str
    ) -> tuple[str, str] | None:
        """Find an inherited method using precise tree-sitter inheritance traversal."""
        # Get the superclass using tree-sitter AST analysis
        superclass_qn = self._get_superclass_name(class_qn)
        if not superclass_qn:
            return None

        # Look for the method in the superclass using flexible signature matching
        method_result = self._find_method_with_any_signature(superclass_qn, method_name)
        if method_result:
            return method_result

        # Recursively check the superclass's superclass
        return self._find_inherited_method(superclass_qn, method_name, module_qn)

    def _find_interface_method(
        self, class_qn: str, method_name: str, module_qn: str
    ) -> tuple[str, str] | None:
        """Find a method in implemented interfaces using precise tree-sitter analysis."""
        # Get all interfaces implemented by this class
        implemented_interfaces = self._get_implemented_interfaces(class_qn)

        for interface_qn in implemented_interfaces:
            # Look for the method in the interface using flexible signature matching
            method_result = self._find_method_with_any_signature(
                interface_qn, method_name
            )
            if method_result:
                return method_result

        return None

    def _get_implemented_interfaces(self, class_qn: str) -> list[str]:
        """Get all interfaces implemented by a class using tree-sitter AST analysis."""
        # Extract module and class information
        parts = class_qn.split(".")
        if len(parts) < 2:  # Need at least project.class
            return []

        module_qn = ".".join(parts[:-1])
        target_class_name = parts[-1]

        # Use the direct mapping from module QN to file path - much more robust!
        file_path = self.module_qn_to_file_path.get(module_qn)
        if file_path is None or file_path not in self.ast_cache:
            return []

        root_node, _ = self.ast_cache[file_path]

        # Use tree-sitter to find the specific class and its implements clause
        interfaces = self._find_interfaces_using_ast(
            root_node, target_class_name, module_qn
        )
        return interfaces

    def _find_interfaces_using_ast(
        self, node: Node, target_class_name: str, module_qn: str
    ) -> list[str]:
        """Find implemented interfaces using precise tree-sitter AST traversal."""
        if node.type == "class_declaration":
            # Check if this is the target class
            name_node = node.child_by_field_name("name")
            if name_node and safe_decode_text(name_node) == target_class_name:
                # Found the target class, now look for interfaces list
                interfaces_node = node.child_by_field_name("interfaces")
                if interfaces_node:
                    # Extract interface names using tree-sitter traversal
                    interface_list: list[str] = []
                    self._extract_interface_names(
                        interfaces_node, interface_list, module_qn
                    )
                    return interface_list

        # Recursively traverse children using tree-sitter
        for child in node.children:
            result = self._find_interfaces_using_ast(
                child, target_class_name, module_qn
            )
            if result:
                return result

        return []

    def _extract_interface_names(
        self, interfaces_node: Node, interface_list: list[str], module_qn: str
    ) -> None:
        """Extract interface names from the interfaces list using tree-sitter."""
        for child in interfaces_node.children:
            if child.type == "type_identifier":
                interface_name = safe_decode_text(child)
                if interface_name:
                    # Resolve to fully qualified name
                    resolved_interface = self._resolve_java_type_name(
                        interface_name, module_qn
                    )
                    interface_list.append(resolved_interface)
            # Recursively traverse for nested type structures
            elif child.children:
                self._extract_interface_names(child, interface_list, module_qn)

    def _get_current_class_name(self, module_qn: str) -> str | None:
        """Extract current class name from AST context using precise tree-sitter traversal."""
        # Get the AST for the current module
        module_parts = module_qn.split(".")
        if len(module_parts) < 2:  # Need at least project.filename
            return None

        # Use the direct mapping from module QN to file path - much more robust!
        file_path = self.module_qn_to_file_path.get(module_qn)
        if file_path is None or file_path not in self.ast_cache:
            return None

        root_node, _ = self.ast_cache[file_path]

        # Use tree-sitter to find class declarations in the current context
        class_names: list[str] = []
        self._traverse_for_class_declarations(root_node, class_names)

        # Return the fully qualified name of the first class found
        if class_names:
            return f"{module_qn}.{class_names[0]}"

        return None

    def _traverse_for_class_declarations(
        self, node: Node, class_names: list[str]
    ) -> None:
        """Recursively traverse AST using tree-sitter to find class declarations."""
        if node.type in [
            "class_declaration",
            "interface_declaration",
            "enum_declaration",
        ]:
            name_node = node.child_by_field_name("name")
            if name_node:
                class_name = safe_decode_text(name_node)
                if class_name:
                    class_names.append(class_name)

        # Recursively traverse children using tree-sitter
        for child in node.children:
            self._traverse_for_class_declarations(child, class_names)

    def _get_superclass_name(self, class_qn: str) -> str | None:
        """Get the superclass name using precise tree-sitter AST analysis."""
        # Extract module and class information
        parts = class_qn.split(".")
        if len(parts) < 2:  # Need at least project.class
            return None

        module_qn = ".".join(parts[:-1])
        target_class_name = parts[-1]

        # Use the direct mapping from module QN to file path - much more robust!
        file_path = self.module_qn_to_file_path.get(module_qn)
        if file_path is None or file_path not in self.ast_cache:
            return None

        root_node, _ = self.ast_cache[file_path]

        # Use tree-sitter to find the specific class and its extends clause
        superclass = self._find_superclass_using_ast(
            root_node, target_class_name, module_qn
        )
        return superclass

    def _find_superclass_using_ast(
        self, node: Node, target_class_name: str, module_qn: str
    ) -> str | None:
        """Find superclass using precise tree-sitter AST traversal."""
        if node.type == "class_declaration":
            # Check if this is the target class
            name_node = node.child_by_field_name("name")
            if name_node and safe_decode_text(name_node) == target_class_name:
                # Found the target class, now look for extends clause
                superclass_node = node.child_by_field_name("superclass")
                if superclass_node:
                    # Extract the superclass type using tree-sitter field access
                    type_node = superclass_node.child_by_field_name("type")
                    if type_node:
                        superclass_name = safe_decode_text(type_node)
                        if superclass_name:
                            # Resolve to fully qualified name
                            return self._resolve_java_type_name(
                                superclass_name, module_qn
                            )

        # Recursively traverse children using tree-sitter
        for child in node.children:
            result = self._find_superclass_using_ast(
                child, target_class_name, module_qn
            )
            if result:
                return result

        return None

    def _analyze_java_enhanced_for_loops(
        self, scope_node: Node, local_var_types: dict[str, str], module_qn: str
    ) -> None:
        """Analyze enhanced for loops using tree-sitter to extract loop variable types."""
        self._traverse_for_enhanced_for_loops(scope_node, local_var_types, module_qn)

    def _traverse_for_enhanced_for_loops(
        self, node: Node, local_var_types: dict[str, str], module_qn: str
    ) -> None:
        """Recursively traverse AST using tree-sitter to find enhanced for statements."""
        if node.type == "enhanced_for_statement":
            self._process_enhanced_for_statement(node, local_var_types, module_qn)

        # Recursively traverse children using tree-sitter
        for child in node.children:
            self._traverse_for_enhanced_for_loops(child, local_var_types, module_qn)

    def _process_enhanced_for_statement(
        self, for_node: Node, local_var_types: dict[str, str], module_qn: str
    ) -> None:
        """Process enhanced for statement using tree-sitter field access."""
        # Enhanced for loop: for (Type variable : collection)
        # Use tree-sitter field access to get the type and name
        type_node = for_node.child_by_field_name("type")
        name_node = for_node.child_by_field_name("name")

        if type_node and name_node:
            var_type = safe_decode_text(type_node)
            var_name = safe_decode_text(name_node)

            if var_type and var_name:
                resolved_type = self._resolve_java_type_name(var_type, module_qn)
                local_var_types[var_name] = resolved_type
                logger.debug(
                    f"Enhanced for loop variable: {var_name} -> {resolved_type}"
                )
        else:
            # Alternative parsing: look for variable_declarator in for loop children
            for child in for_node.children:
                if child.type == "variable_declarator":
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        var_name = safe_decode_text(name_node)
                        if var_name:
                            # Find the type by looking at siblings
                            parent = child.parent
                            if parent:
                                for sibling in parent.children:
                                    if sibling.type == "type_identifier":
                                        var_type = safe_decode_text(sibling)
                                        if var_type:
                                            resolved_type = (
                                                self._resolve_java_type_name(
                                                    var_type, module_qn
                                                )
                                            )
                                            local_var_types[var_name] = resolved_type
                                            logger.debug(
                                                f"Enhanced for loop variable (alt): {var_name} -> {resolved_type}"
                                            )
                                            break

    def _find_field_type_in_class(
        self, root_node: Node, class_name: str, field_name: str, module_qn: str
    ) -> str | None:
        """Find the type of a specific field in a class using tree-sitter AST analysis."""

        # Find the target class in the AST
        for child in root_node.children:
            if child.type == "class_declaration":
                class_info = extract_java_class_info(child)
                if class_info.get("name") == class_name:
                    # Found the target class, look for the field
                    class_body = child.child_by_field_name("body")
                    if class_body:
                        for field_child in class_body.children:
                            if field_child.type == "field_declaration":
                                field_info = extract_java_field_info(field_child)
                                if field_info.get("name") == field_name:
                                    field_type = field_info.get("type")
                                    if field_type:
                                        # Resolve the field type to fully qualified name
                                        return self._resolve_java_type_name(
                                            str(field_type), module_qn
                                        )
        return None
