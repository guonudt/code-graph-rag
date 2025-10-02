from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

import mgclient
from loguru import logger


class MemgraphIngestor:
    """Handles all communication and query execution with the Memgraph database."""

    def __init__(self, host: str, port: int, batch_size: int = 1000):
        self._host = host
        self._port = port
        self.batch_size = batch_size
        self.conn: mgclient.Connection | None = None
        self.node_buffer: list[tuple[str, dict[str, Any]]] = []
        self.relationship_buffer: list[tuple[tuple, str, tuple, dict | None]] = []
        self.relationship_counters: dict[str, int] = defaultdict(
            int
        )  # Track relationship types
        self.unique_constraints = {
            "Project": "name",
            "Package": "qualified_name",
            "Folder": "path",
            "Module": "qualified_name",
            "Class": "qualified_name",
            "Function": "qualified_name",
            "Method": "qualified_name",
            "File": "path",
            "ExternalPackage": "name",
        }

    def __enter__(self) -> "MemgraphIngestor":
        logger.info(f"Connecting to Memgraph at {self._host}:{self._port}...")
        self.conn = mgclient.connect(host=self._host, port=self._port)
        self.conn.autocommit = True
        logger.info("Successfully connected to Memgraph.")
        return self

    def __exit__(
        self, exc_type: type | None, exc_val: Exception | None, exc_tb: Any
    ) -> None:
        if exc_type:
            logger.error(
                f"An exception occurred: {exc_val}. Flushing remaining items...",
                exc_info=True,
            )
        self.flush_all()
        if self.conn:
            self.conn.close()
            logger.info("\nDisconnected from Memgraph.")

    def _execute_query(self, query: str, params: dict[str, Any] | None = None) -> list:
        if not self.conn:
            raise ConnectionError("Not connected to Memgraph.")
        params = params or {}
        cursor = None
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, params)
            if not cursor.description:
                return []
            column_names = [desc.name for desc in cursor.description]
            return [dict(zip(column_names, row)) for row in cursor.fetchall()]
        except Exception as e:
            if (
                "already exists" not in str(e).lower()
                and "constraint" not in str(e).lower()
            ):
                logger.error(f"!!! Cypher Error: {e}")
                logger.error(f"    Query: {query}")
                logger.error(f"    Params: {params}")
            raise
        finally:
            if cursor:
                cursor.close()

    def _execute_batch(self, query: str, params_list: list[dict[str, Any]]) -> None:
        if not self.conn or not params_list:
            return
        cursor = None
        try:
            cursor = self.conn.cursor()
            batch_query = f"UNWIND $batch AS row\n{query}"

            # Log batch execution details
            logger.debug(f"🔄 Executing batch query with {len(params_list)} items")
            logger.debug(f"   Query: {query}")

            cursor.execute(batch_query, {"batch": params_list})
            logger.debug("✅ Batch query executed successfully")
        except Exception as e:
            if "already exists" not in str(e).lower():
                logger.error(f"!!! Batch Cypher Error: {e}")
                logger.error(f"   Batch size: {len(params_list)}")
                logger.error(f"   Query: {query}")
                # Log sample of problematic parameters
                if params_list:
                    logger.error(f"   Sample parameters: {params_list[:2]}")
        finally:
            if cursor:
                cursor.close()

    def clean_database(self) -> None:
        logger.info("--- Cleaning database... ---")
        self._execute_query("MATCH (n) DETACH DELETE n;")
        logger.info("--- Database cleaned. ---")

    def reset_counters(self) -> None:
        """Reset relationship counters for a new processing session."""
        self.relationship_counters.clear()
        logger.debug("🔄 Reset relationship counters for new session")

    def ensure_constraints(self) -> None:
        logger.info("Ensuring constraints...")
        for label, prop in self.unique_constraints.items():
            try:
                self._execute_query(
                    f"CREATE CONSTRAINT ON (n:{label}) ASSERT n.{prop} IS UNIQUE;"
                )
            except Exception:
                pass
        logger.info("Constraints checked/created.")

    def ensure_node_batch(self, label: str, properties: dict[str, Any]) -> None:
        """Adds a node to the buffer."""
        self.node_buffer.append((label, properties))

    def ensure_relationship_batch(
        self,
        from_spec: tuple[str, str, Any],
        rel_type: str,
        to_spec: tuple[str, str, Any],
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Adds a relationship to the buffer."""
        from_label, from_key, from_val = from_spec
        to_label, to_key, to_val = to_spec

        relationship_entry = (
            (from_label, from_key, from_val),
            rel_type,
            (to_label, to_key, to_val),
            properties,
        )

        self.relationship_buffer.append(relationship_entry)
        # Track relationship type count
        self.relationship_counters[rel_type] += 1

        # Log relationship creation for debugging
        logger.debug(
            f"🔗 Added relationship: {from_label}({from_key}={from_val})--[{rel_type}]-->{to_label}({to_key}={to_val})"
        )

    def flush_nodes(self) -> None:
        """Flushes the buffered nodes to the database."""
        if not self.node_buffer:
            logger.debug("📝 No nodes to flush - buffer is empty")
            return

        logger.info(f"📝 Starting to flush {len(self.node_buffer)} nodes...")

        nodes_by_label = defaultdict(list)
        for label, props in self.node_buffer:
            nodes_by_label[label].append(props)

        # Log node counts by label
        logger.info("📊 Node counts by label:")
        for label, props_list in nodes_by_label.items():
            logger.info(f"  - {label}: {len(props_list)} nodes")

        total_flushed = 0
        for label, props_list in nodes_by_label.items():
            if not props_list:
                continue
            id_key = self.unique_constraints.get(label)
            if not id_key:
                logger.warning(
                    f"⚠️ No unique constraint defined for label '{label}'. Skipping {len(props_list)} nodes."
                )
                continue

            logger.debug(f"🔄 Flushing {len(props_list)} {label} nodes...")
            prop_keys = list(props_list[0].keys())
            set_clause = ", ".join([f"n.{key} = row.{key}" for key in prop_keys])
            query = (
                f"MERGE (n:{label} {{{id_key}: row.{id_key}}}) "
                f"ON CREATE SET {set_clause} ON MATCH SET {set_clause}"
            )

            try:
                self._execute_batch(query, props_list)
                total_flushed += len(props_list)
                logger.debug(f"✅ Successfully flushed {len(props_list)} {label} nodes")
            except Exception as e:
                logger.error(f"❌ Failed to flush {len(props_list)} {label} nodes: {e}")
                raise

        logger.info(f"✅ Successfully flushed {total_flushed} nodes total")
        self.node_buffer.clear()

    def flush_relationships(self) -> None:
        if not self.relationship_buffer:
            logger.debug("🔗 No relationships to flush - buffer is empty")
            return

        logger.info(
            f"🔗 Starting to flush {len(self.relationship_buffer)} relationships..."
        )

        rels_by_pattern = defaultdict(list)
        for from_node, rel_type, to_node, props in self.relationship_buffer:
            pattern = (from_node[0], from_node[1], rel_type, to_node[0], to_node[1])
            rels_by_pattern[pattern].append(
                {"from_val": from_node[2], "to_val": to_node[2], "props": props or {}}
            )

        # Log relationship counts by pattern
        logger.info("📊 Relationship counts by pattern:")
        for pattern, params_list in rels_by_pattern.items():
            from_label, from_key, rel_type, to_label, to_key = pattern
            logger.info(
                f"  - {from_label}--[{rel_type}]-->{to_label}: {len(params_list)} relationships"
            )

        total_flushed = 0
        for pattern, params_list in rels_by_pattern.items():
            from_label, from_key, rel_type, to_label, to_key = pattern
            query = (
                f"MATCH (a:{from_label} {{{from_key}: row.from_val}}), "
                f"(b:{to_label} {{{to_key}: row.to_val}})\n"
                f"MERGE (a)-[r:{rel_type}]->(b)"
            )
            if any(p["props"] for p in params_list):
                query += "\nSET r += row.props"

            logger.debug(
                f"🔄 Flushing {len(params_list)} {rel_type} relationships ({from_label} -> {to_label})..."
            )

            try:
                self._execute_batch(query, params_list)
                total_flushed += len(params_list)
                logger.debug(
                    f"✅ Successfully flushed {len(params_list)} {rel_type} relationships"
                )
            except Exception as e:
                logger.error(
                    f"❌ Failed to write {len(params_list)} relationships of type {rel_type}: {e}"
                )
                logger.error(f"   Query: {query}")
                logger.error(f"   Parameters count: {len(params_list)}")
                # Log first few parameters for debugging
                if params_list:
                    logger.error(f"   First few parameters: {params_list[:3]}")
                raise

        logger.info(f"✅ Successfully flushed {total_flushed} relationships total")
        self.relationship_buffer.clear()

    def flush_all(self) -> None:
        logger.info("--- Flushing all pending writes to database... ---")

        # Log buffer sizes before flushing
        logger.info("📊 Buffer status before flush:")
        logger.info(f"  - Nodes in buffer: {len(self.node_buffer)}")
        logger.info(f"  - Relationships in buffer: {len(self.relationship_buffer)}")

        # Track timing
        import time

        start_time = time.time()

        self.flush_nodes()
        self.flush_relationships()

        flush_time = time.time() - start_time
        logger.info(f"--- Flushing complete in {flush_time:.3f}s ---")

        # Log relationship statistics
        self._log_relationship_statistics()

        # Perform data integrity checks
        self._perform_data_integrity_checks()

        # Verify data was written correctly
        self._verify_data_written()

    def _log_relationship_statistics(self) -> None:
        """Log statistics about relationship types processed."""
        if not self.relationship_counters:
            logger.info("📊 No relationships were processed in this session")
            return

        logger.info("📊 Relationship statistics:")
        total_relationships = sum(self.relationship_counters.values())
        logger.info(f"  Total relationships processed: {total_relationships}")

        # Sort by count (descending) for better readability
        sorted_rels = sorted(
            self.relationship_counters.items(), key=lambda x: x[1], reverse=True
        )
        for rel_type, count in sorted_rels:
            percentage = (
                (count / total_relationships) * 100 if total_relationships > 0 else 0
            )
            logger.info(f"  - {rel_type}: {count} ({percentage:.1f}%)")

    def _perform_data_integrity_checks(self) -> None:
        """Perform basic data integrity checks after flushing."""
        try:
            logger.info("🔍 Performing data integrity checks...")

            # Check for orphaned relationships (relationships pointing to non-existent nodes)
            orphan_check_query = """
            MATCH (a)-[r]->(b)
            WHERE NOT EXISTS((a)-[:DEFINES|:IMPORTS|:CALLS|:INHERITS|:EXPORTS]->())
            AND NOT EXISTS((b)-[:DEFINES|:IMPORTS|:CALLS|:INHERITS|:EXPORTS]->())
            RETURN count(r) as orphaned_count
            """

            orphan_result = self._execute_query(orphan_check_query)
            orphaned_count = orphan_result[0]["orphaned_count"] if orphan_result else 0

            if orphaned_count > 0:
                logger.warning(
                    f"⚠️ Found {orphaned_count} potentially orphaned relationships"
                )

                # Print examples of orphaned CALLS relationships only
                example_query = """
                MATCH (a)-[r:CALLS]->(b)
                WHERE NOT EXISTS((a)-[:DEFINES|:IMPORTS|:CALLS|:INHERITS|:EXPORTS]->())
                AND NOT EXISTS((b)-[:DEFINES|:IMPORTS|:CALLS|:INHERITS|:EXPORTS]->())
                RETURN labels(a) as from_labels, properties(a) as from_props,
                       type(r) as rel_type,
                       labels(b) as to_labels, properties(b) as to_props
                LIMIT 20
                """

                try:
                    examples = self._execute_query(example_query)
                    logger.warning("📋 Examples of orphaned CALLS relationships:")
                    for i, example in enumerate(examples, 1):
                        from_labels = example.get("from_labels", [])
                        from_props = example.get("from_props", {})
                        rel_type = example.get("rel_type", "UNKNOWN")
                        to_labels = example.get("to_labels", [])
                        to_props = example.get("to_props", {})

                        # Extract key identifiers for better readability
                        from_id = (
                            from_props.get("qualified_name")
                            or from_props.get("name")
                            or from_props.get("path")
                            or "unknown"
                        )
                        to_id = (
                            to_props.get("qualified_name")
                            or to_props.get("name")
                            or to_props.get("path")
                            or "unknown"
                        )

                        logger.warning(
                            f"  {i}. {from_labels[0] if from_labels else 'Unknown'}({from_id})--[{rel_type}]-->{to_labels[0] if to_labels else 'Unknown'}({to_id})"
                        )

                except Exception as e:
                    logger.error(f"Failed to get orphaned relationship examples: {e}")
            else:
                logger.info("✅ No orphaned relationships detected")

            # Check for nodes without any relationships
            isolated_nodes_query = """
            MATCH (n)
            OPTIONAL MATCH (n)-[r]-()
            WITH n, count(r) as rel_count
            WHERE rel_count = 0
            RETURN count(n) as isolated_count
            """

            isolated_result = self._execute_query(isolated_nodes_query)
            isolated_count = (
                isolated_result[0]["isolated_count"] if isolated_result else 0
            )

            if isolated_count > 0:
                logger.warning(
                    f"⚠️ Found {isolated_count} isolated nodes (nodes without relationships)"
                )

                # Print examples of isolated nodes
                isolated_example_query = """
                MATCH (n)
                OPTIONAL MATCH (n)-[r]-()
                WITH n, count(r) as rel_count
                WHERE rel_count = 0
                RETURN labels(n) as node_labels, properties(n) as node_props
                LIMIT 5
                """

                try:
                    examples = self._execute_query(isolated_example_query)
                    logger.warning("📋 Examples of isolated nodes:")
                    for i, example in enumerate(examples, 1):
                        node_labels = example.get("node_labels", [])
                        node_props = example.get("node_props", {})

                        # Extract key identifiers for better readability
                        node_id = (
                            node_props.get("qualified_name")
                            or node_props.get("name")
                            or node_props.get("path")
                            or "unknown"
                        )

                        logger.warning(
                            f"  {i}. {node_labels[0] if node_labels else 'Unknown'}({node_id})"
                        )

                except Exception as e:
                    logger.error(f"Failed to get isolated node examples: {e}")
            else:
                logger.info("✅ No isolated nodes detected")

            # Check for duplicate relationships
            duplicate_check_query = """
            MATCH (a)-[r]->(b)
            WITH a, b, type(r) as rel_type, count(r) as rel_count
            WHERE rel_count > 1
            RETURN sum(rel_count) as duplicate_count
            """

            duplicate_result = self._execute_query(duplicate_check_query)
            duplicate_count = (
                duplicate_result[0]["duplicate_count"] if duplicate_result else 0
            )

            if duplicate_count > 0:
                logger.warning(f"⚠️ Found {duplicate_count} duplicate relationships")
            else:
                logger.info("✅ No duplicate relationships detected")

        except Exception as e:
            logger.error(f"❌ Data integrity check failed: {e}")

    def _verify_data_written(self) -> None:
        """Verify that data was written correctly to the database."""
        try:
            logger.info("🔍 Verifying data was written correctly...")

            # Get current database statistics
            node_count_query = "MATCH (n) RETURN count(n) as node_count"
            rel_count_query = "MATCH ()-[r]->() RETURN count(r) as rel_count"

            node_result = self._execute_query(node_count_query)
            rel_result = self._execute_query(rel_count_query)

            current_nodes = node_result[0]["node_count"] if node_result else 0
            current_relationships = rel_result[0]["rel_count"] if rel_result else 0

            logger.info("📊 Current database state:")
            logger.info(f"  - Total nodes: {current_nodes}")
            logger.info(f"  - Total relationships: {current_relationships}")

            # Check if we have expected minimum counts
            if current_nodes == 0:
                logger.warning(
                    "⚠️ No nodes found in database - this might indicate a problem"
                )
            elif current_nodes < 10:  # Arbitrary threshold
                logger.warning(
                    f"⚠️ Very few nodes ({current_nodes}) in database - check if parsing worked correctly"
                )
            else:
                logger.info(f"✅ Database contains {current_nodes} nodes")

            if current_relationships == 0:
                logger.warning(
                    "⚠️ No relationships found in database - this might indicate a problem"
                )
            elif current_relationships < 5:  # Arbitrary threshold
                logger.warning(
                    f"⚠️ Very few relationships ({current_relationships}) in database - check if relationship processing worked correctly"
                )
            else:
                logger.info(
                    f"✅ Database contains {current_relationships} relationships"
                )

            # Check for specific relationship types
            rel_type_query = """
            MATCH ()-[r]->()
            WITH type(r) as rel_type, count(r) as count
            RETURN rel_type, count
            ORDER BY count DESC
            """

            rel_type_result = self._execute_query(rel_type_query)
            if rel_type_result:
                logger.info("📊 Relationship types in database:")
                for row in rel_type_result:
                    logger.info(f"  - {row['rel_type']}: {row['count']}")

            # Check for specific node types
            node_type_query = """
            MATCH (n)
            WITH labels(n) as node_labels, count(n) as count
            UNWIND node_labels as label
            WITH label, count
            RETURN label, count
            ORDER BY count DESC
            """

            node_type_result = self._execute_query(node_type_query)
            if node_type_result:
                logger.info("📊 Node types in database:")
                for row in node_type_result:
                    logger.info(f"  - {row['label']}: {row['count']}")

        except Exception as e:
            logger.error(f"❌ Data verification failed: {e}")

    def fetch_all(self, query: str, params: dict[str, Any] | None = None) -> list:
        """Executes a query and fetches all results with enhanced logging and result formatting."""
        logger.info(f"🔍 Executing query: {query}")
        if params:
            logger.info(f"📋 Query parameters: {params}")

        import time

        start_time = time.time()

        try:
            results = self._execute_query(query, params)
            execution_time = time.time() - start_time

            logger.info(f"✅ Query executed successfully in {execution_time:.3f}s")
            logger.info(f"📊 Retrieved {len(results)} result(s)")

            # Print query results in a formatted way
            if results:
                self._print_query_results(results, query)
            else:
                logger.info("📭 No results found for this query")

            return results

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"❌ Query failed after {execution_time:.3f}s: {e}")
            raise

    def execute_write(self, query: str, params: dict[str, Any] | None = None) -> None:
        """Executes a write query without returning results."""
        logger.debug(f"Executing write query: {query} with params: {params}")
        self._execute_query(query, params)

    def export_graph_to_dict(self) -> dict[str, Any]:
        """Export the entire graph as a dictionary with nodes and relationships."""
        logger.info("Exporting graph data...")

        # Get all nodes with their labels and properties
        nodes_query = """
        MATCH (n)
        RETURN id(n) as node_id, labels(n) as labels, properties(n) as properties
        """
        nodes_data = self.fetch_all(nodes_query)

        # Get all relationships with their types and properties
        relationships_query = """
        MATCH (a)-[r]->(b)
        RETURN id(a) as from_id, id(b) as to_id, type(r) as type, properties(r) as properties
        """
        relationships_data = self.fetch_all(relationships_query)

        graph_data = {
            "nodes": nodes_data,
            "relationships": relationships_data,
            "metadata": {
                "total_nodes": len(nodes_data),
                "total_relationships": len(relationships_data),
                "exported_at": self._get_current_timestamp(),
            },
        }

        logger.info(
            f"Exported {len(nodes_data)} nodes and {len(relationships_data)} relationships"
        )
        return graph_data

    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        return datetime.now(UTC).isoformat()

    def _print_query_results(self, results: list, query: str) -> None:
        """Print query results in a formatted and readable way."""
        if not results:
            return

        # Determine if this is a simple or complex query result
        is_simple_result = len(results[0].keys()) <= 3 and all(
            isinstance(v, str | int | float | bool) or v is None
            for v in results[0].values()
        )

        if is_simple_result and len(results) <= 10:
            # Print simple results in a clean format
            logger.info("📋 Query Results:")
            for i, row in enumerate(results, 1):
                logger.info(f"  Result {i}:")
                for key, value in row.items():
                    if value is None:
                        logger.info(f"    {key}: null")
                    elif isinstance(value, bool):
                        logger.info(f"    {key}: {'✓' if value else '✗'}")
                    elif isinstance(value, int | float):
                        logger.info(f"    {key}: {value}")
                    else:
                        # Truncate long strings
                        str_value = str(value)
                        if len(str_value) > 100:
                            str_value = str_value[:97] + "..."
                        logger.info(f"    {key}: {str_value}")
                logger.info("")  # Empty line between results
        else:
            # For complex results or many results, show a summary
            logger.info("📋 Query Results Summary:")
            logger.info(f"  Total results: {len(results)}")
            logger.info(f"  Columns: {', '.join(results[0].keys())}")

            # Show first few results as examples
            max_examples = min(3, len(results))
            logger.info(f"  First {max_examples} result(s):")
            for i, row in enumerate(results[:max_examples], 1):
                logger.info(f"    Example {i}: {dict(row)}")

            if len(results) > max_examples:
                logger.info(f"    ... and {len(results) - max_examples} more results")

    def get_query_statistics(self, query: str) -> dict[str, Any]:
        """Get statistics about a query execution."""
        import time

        start_time = time.time()

        try:
            results = self._execute_query(query)
            execution_time = time.time() - start_time

            return {
                "execution_time": execution_time,
                "result_count": len(results),
                "success": True,
                "query": query,
            }
        except Exception as e:
            execution_time = time.time() - start_time
            return {
                "execution_time": execution_time,
                "result_count": 0,
                "success": False,
                "error": str(e),
                "query": query,
            }

    def fetch_paginated(
        self,
        query: str,
        page: int = 1,
        page_size: int = 50,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a query with pagination support."""
        import time

        start_time = time.time()

        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 50
        if page_size > 1000:
            page_size = 1000  # Limit max page size

        offset = (page - 1) * page_size

        try:
            # Add pagination to the query
            paginated_query = f"{query.rstrip(';')} SKIP {offset} LIMIT {page_size};"

            # Get total count for pagination info
            count_query = f"MATCH {query.split('MATCH')[1].split('RETURN')[0]} RETURN count(*) as total"
            count_result = self._execute_query(count_query, params)
            total_count = count_result[0]["total"] if count_result else 0

            # Execute paginated query
            results = self._execute_query(paginated_query, params)
            execution_time = time.time() - start_time

            # Calculate pagination info
            total_pages = (total_count + page_size - 1) // page_size
            has_next = page < total_pages
            has_prev = page > 1

            logger.info(
                f"📄 Paginated query: page {page}/{total_pages}, {len(results)}/{total_count} results in {execution_time:.3f}s"
            )

            return {
                "results": results,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": total_pages,
                    "has_next": has_next,
                    "has_prev": has_prev,
                    "offset": offset,
                },
                "execution_time": execution_time,
                "success": True,
            }

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"❌ Paginated query failed after {execution_time:.3f}s: {e}")
            return {
                "results": [],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_count": 0,
                    "total_pages": 0,
                    "has_next": False,
                    "has_prev": False,
                    "offset": offset,
                },
                "execution_time": execution_time,
                "success": False,
                "error": str(e),
            }
