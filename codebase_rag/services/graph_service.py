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
        self.node_counters: dict[str, int] = defaultdict(int)  # Track node types
        self._flushed = False  # Track if flush_all has been called
        # Track unique nodes and relationships to prevent duplicates in buffer
        self.seen_nodes: set[str] = set()
        self.seen_relationships: set[str] = set()
        self.skipped_duplicate_nodes: int = 0
        self.skipped_duplicate_relationships: int = 0
        self.unique_constraints = {
            "Project": "name",
            "Package": "qualified_name",
            "Folder": "path",
            "Module": "qualified_name",
            "Interface": "qualified_name",
            "Class": "qualified_name",
            "Enum": "qualified_name",
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

            cursor.execute(batch_query, {"batch": params_list})
        except Exception as e:
            logger.error(f"!!! Batch Cypher Error: {e}")
            logger.error(f"   Batch size: {len(params_list)}")
            logger.error(f"   Query: {query}")
            # Log sample of problematic parameters
            if params_list:
                logger.error(f"   Sample parameters: {params_list[:2]}")
            raise
        finally:
            if cursor:
                cursor.close()

    def _execute_batch_query(
        self, query: str, params_list: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Execute a batch query that returns results (unlike _execute_batch which is for writes)."""
        if not self.conn or not params_list:
            return []
        cursor = None
        try:
            cursor = self.conn.cursor()
            batch_query = f"UNWIND $batch AS row\n{query}"
            cursor.execute(batch_query, {"batch": params_list})

            if not cursor.description:
                return []
            column_names = [desc.name for desc in cursor.description]
            return [dict(zip(column_names, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.debug(f"Batch query error: {e}")
            return []
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
        self.node_counters.clear()
        self.seen_nodes.clear()
        self.seen_relationships.clear()
        self.skipped_duplicate_nodes = 0
        self.skipped_duplicate_relationships = 0
        self._flushed = False
        logger.debug("🔄 Reset counters and deduplication sets for new session")

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
        """Adds a node to the buffer if it's not already present."""
        # Check for duplicates using unique constraint
        unique_key = self.unique_constraints.get(label)
        if unique_key and unique_key in properties:
            key_value = properties[unique_key]
            node_key = f"{label}:{key_value}"

            # Skip if node already in buffer
            if node_key in self.seen_nodes:
                self.skipped_duplicate_nodes += 1
                logger.debug(
                    f"⏭️ Skipping duplicate node: {label}({unique_key}={key_value})"
                )
                return

            # Mark as seen
            self.seen_nodes.add(node_key)

        # Add node to buffer
        self.node_buffer.append((label, properties))
        # Track node type count
        self.node_counters[label] += 1

    def ensure_relationship_batch(
        self,
        from_spec: tuple[str, str, Any],
        rel_type: str,
        to_spec: tuple[str, str, Any],
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Adds a relationship to the buffer if it's not already present."""
        from_label, from_key, from_val = from_spec
        to_label, to_key, to_val = to_spec

        # Check for duplicates
        rel_key = f"{from_label}:{from_val}--[{rel_type}]-->{to_label}:{to_val}"

        # Skip if relationship already in buffer
        if rel_key in self.seen_relationships:
            self.skipped_duplicate_relationships += 1
            logger.debug(f"⏭️ Skipping duplicate relationship: {rel_key}")
            return

        # Mark as seen
        self.seen_relationships.add(rel_key)

        relationship_entry = (
            (from_label, from_key, from_val),
            rel_type,
            (to_label, to_key, to_val),
            properties,
        )

        self.relationship_buffer.append(relationship_entry)
        # Track relationship type count
        self.relationship_counters[rel_type] += 1

    def flush_nodes(self) -> None:
        """Flushes the buffered nodes to the database."""
        if not self.node_buffer:
            return

        logger.info(f"Flushing {len(self.node_buffer)} nodes...")

        nodes_by_label = defaultdict(list)
        for label, props in self.node_buffer:
            nodes_by_label[label].append(props)

        total_flushed = 0
        for label, props_list in nodes_by_label.items():
            if not props_list:
                continue
            id_key = self.unique_constraints.get(label)
            if not id_key:
                logger.warning(
                    f"No unique constraint defined for label '{label}'. Skipping {len(props_list)} nodes."
                )
                continue
            prop_keys = list(props_list[0].keys())
            set_clause = ", ".join([f"n.{key} = row.{key}" for key in prop_keys])
            query = (
                f"MERGE (n:{label} {{{id_key}: row.{id_key}}}) "
                f"ON CREATE SET {set_clause} ON MATCH SET {set_clause}"
            )

            try:
                self._execute_batch(query, props_list)
                total_flushed += len(props_list)
            except Exception as e:
                logger.error(f"Failed to flush {len(props_list)} {label} nodes: {e}")
                raise

        logger.info(f"Successfully flushed {total_flushed} nodes total")

        self.node_buffer.clear()

    def flush_relationships(self) -> None:
        if not self.relationship_buffer:
            return

        logger.info(f"Flushing {len(self.relationship_buffer)} relationships...")

        rels_by_pattern = defaultdict(list)
        for from_node, rel_type, to_node, props in self.relationship_buffer:
            pattern = (from_node[0], from_node[1], rel_type, to_node[0], to_node[1])
            rels_by_pattern[pattern].append(
                {"from_val": from_node[2], "to_val": to_node[2], "props": props or {}}
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

            try:
                # Check if both nodes exist before creating relationships
                node_check_query = (
                    f"OPTIONAL MATCH (a:{from_label} {{{from_key}: row.from_val}})\n"
                    f"OPTIONAL MATCH (b:{to_label} {{{to_key}: row.to_val}})\n"
                    f"RETURN row.from_val as from_val, row.to_val as to_val, "
                    f"a IS NOT NULL as from_exists, b IS NOT NULL as to_exists"
                )

                try:
                    node_check_result = self._execute_batch_query(
                        node_check_query, params_list
                    )

                    if node_check_result:
                        missing_from = sum(
                            1
                            for row in node_check_result
                            if not row.get("from_exists", False)
                        )
                        missing_to = sum(
                            1
                            for row in node_check_result
                            if not row.get("to_exists", False)
                        )

                        if missing_from > 0 or missing_to > 0:
                            logger.warning(
                                f"⚠️ Missing nodes for {rel_type} relationships:"
                            )
                            if missing_from > 0:
                                logger.warning(
                                    f"   - {missing_from} missing {from_label} nodes (from)"
                                )
                            if missing_to > 0:
                                logger.warning(
                                    f"   - {missing_to} missing {to_label} nodes (to)"
                                )

                            # Show a few examples of missing nodes (limit to 5)
                            missing_examples = [
                                row
                                for row in node_check_result
                                if not row.get("from_exists", False)
                                or not row.get("to_exists", False)
                            ][:5]

                            if missing_examples:
                                logger.warning(
                                    "   Examples of missing nodes (showing up to 5):"
                                )
                                for ex in missing_examples:
                                    from_status = "✓" if ex.get("from_exists") else "✗"
                                    to_status = "✓" if ex.get("to_exists") else "✗"
                                    logger.warning(
                                        f"      {from_status} {from_label}({from_key}={ex['from_val']}) -> "
                                        f"{to_status} {to_label}({to_key}={ex['to_val']})"
                                    )
                except Exception as e:
                    logger.debug(
                        f"Could not check node existence for {rel_type} relationships: {e}"
                    )

                self._execute_batch(query, params_list)
                total_flushed += len(params_list)
            except Exception as e:
                logger.error(
                    f"Failed to write {len(params_list)} relationships of type {rel_type}: {e}"
                )
                raise

        logger.info(f"Successfully flushed {total_flushed} relationships total")
        self.relationship_buffer.clear()

    def flush_all(self) -> None:
        if self._flushed:
            logger.info("Flush already completed, skipping duplicate flush")
            return

        logger.info("Flushing all pending writes to database...")

        # Track timing
        import time

        start_time = time.time()

        self.flush_nodes()
        self.flush_relationships()

        flush_time = time.time() - start_time
        logger.info(f"Flushing complete in {flush_time:.3f}s")

        # Log relationship statistics
        self._log_relationship_statistics()

        # Verify data was written correctly
        self._verify_data_written()

        # Mark as flushed to prevent duplicate calls
        self._flushed = True

    def _log_relationship_statistics(self) -> None:
        """Log statistics about relationship types processed."""
        if not self.relationship_counters:
            return

        logger.info("Relationship statistics:")
        total_relationships = sum(self.relationship_counters.values())
        logger.info(f"  Total relationships: {total_relationships}")

        # Sort by count (descending) for better readability
        sorted_rels = sorted(
            self.relationship_counters.items(), key=lambda x: x[1], reverse=True
        )
        for rel_type, count in sorted_rels[:5]:  # Only show top 5
            logger.info(f"  - {rel_type}: {count}")

    def _verify_data_written(self) -> None:
        """Verify that data was written correctly to the database."""
        try:
            # Log what we expected to write from buffer
            expected_relationships = sum(self.relationship_counters.values())
            expected_nodes = sum(self.node_counters.values())
            logger.info(
                f"Expected from buffer - Nodes: {expected_nodes}, Relationships: {expected_relationships}"
            )

            # Get current database statistics
            node_count_query = "MATCH (n) RETURN count(n) as node_count"
            rel_count_query = "MATCH ()-[r]->() RETURN count(r) as rel_count"

            node_result = self._execute_query(node_count_query)
            rel_result = self._execute_query(rel_count_query)

            current_nodes = node_result[0]["node_count"] if node_result else 0
            current_relationships = rel_result[0]["rel_count"] if rel_result else 0

            logger.info(
                f"Actual in database - Nodes: {current_nodes}, Relationships: {current_relationships}"
            )

            # Compare expected vs actual
            if expected_relationships > 0:
                relationship_diff = expected_relationships - current_relationships
                if relationship_diff > 0:
                    logger.warning(
                        f"⚠️ Database has {relationship_diff} fewer relationships than expected from buffer"
                    )
                elif relationship_diff < 0:
                    logger.info(
                        f"Database has {abs(relationship_diff)} more relationships than expected (possibly from previous runs)"
                    )

            if expected_nodes > 0:
                node_diff = expected_nodes - current_nodes
                if node_diff > 0:
                    logger.warning(
                        f"⚠️ Database has {node_diff} fewer nodes than expected from buffer"
                    )
                elif node_diff < 0:
                    logger.info(
                        f"Database has {abs(node_diff)} more nodes than expected (possibly from previous runs)"
                    )

        except Exception as e:
            logger.error(f"Data verification failed: {e}")

    def _print_all_database_contents(self, limit: int = 100) -> None:
        """Print all nodes and relationships currently in the database."""
        try:
            logger.info("📋 Printing all database contents...")

            # Print all nodes - using properties() to get accurate data
            logger.info("🏷️ All nodes in database:")
            nodes_query = f"""
            MATCH (n)
            RETURN labels(n)[0] as label, properties(n) as props
            ORDER BY label
            LIMIT {limit}
            """
            nodes_result = self._execute_query(nodes_query)

            if nodes_result:
                current_label = None
                node_count = 0
                for row in nodes_result:
                    label = row["label"]
                    props = row["props"]

                    # Group by label for better readability
                    if current_label != label:
                        current_label = label
                        logger.info(f"  📂 {label} nodes:")

                    # Get the unique identifier for this node type
                    unique_key = self.unique_constraints.get(label, "name")
                    unique_value = props.get(unique_key, "N/A")

                    # Show all important properties for debugging
                    logger.info(f"    - {label}({unique_key}={unique_value})")
                    logger.info(f"      Properties: {props}")
                    node_count += 1

                if node_count >= limit:
                    logger.info(f"    ... (showing first {limit} nodes)")
            else:
                logger.info("  No nodes found in database")

            # Print all relationships - using properties() to get accurate data
            logger.info("🔗 All relationships in database:")
            rels_query = f"""
            MATCH (a)-[r]->(b)
            RETURN labels(a)[0] as from_label,
                   properties(a) as from_props,
                   type(r) as rel_type,
                   labels(b)[0] as to_label,
                   properties(b) as to_props
            ORDER BY from_label, rel_type, to_label
            LIMIT {limit}
            """
            rels_result = self._execute_query(rels_query)

            if rels_result:
                current_rel = None
                rel_count = 0
                for row in rels_result:
                    from_label = row["from_label"]
                    from_props = row["from_props"]
                    rel_type = row["rel_type"]
                    to_label = row["to_label"]
                    to_props = row["to_props"]

                    # Get unique identifiers
                    from_unique_key = self.unique_constraints.get(from_label, "name")
                    to_unique_key = self.unique_constraints.get(to_label, "name")

                    from_unique_value = from_props.get(from_unique_key, "N/A")
                    to_unique_value = to_props.get(to_unique_key, "N/A")

                    # Group by relationship type for better readability
                    rel_key = f"{from_label}--[{rel_type}]-->{to_label}"
                    if current_rel != rel_key:
                        current_rel = rel_key
                        logger.info(f"  📂 {rel_key}:")

                    logger.info(
                        f"    - {from_label}({from_unique_key}={from_unique_value})--[{rel_type}]-->{to_label}({to_unique_key}={to_unique_value})"
                    )
                    rel_count += 1

                if rel_count >= limit:
                    logger.info(f"    ... (showing first {limit} relationships)")
            else:
                logger.info("  No relationships found in database")

        except Exception as e:
            logger.error(f"❌ Failed to print database contents: {e}")

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
