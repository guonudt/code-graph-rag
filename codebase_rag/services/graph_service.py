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
            cursor.execute(batch_query, {"batch": params_list})
        except Exception as e:
            if "already exists" not in str(e).lower():
                logger.error(f"!!! Batch Cypher Error: {e}")
        finally:
            if cursor:
                cursor.close()

    def clean_database(self) -> None:
        logger.info("--- Cleaning database... ---")
        self._execute_query("MATCH (n) DETACH DELETE n;")
        logger.info("--- Database cleaned. ---")

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

    def flush_nodes(self) -> None:
        """Flushes the buffered nodes to the database."""
        if not self.node_buffer:
            return

        nodes_by_label = defaultdict(list)
        for label, props in self.node_buffer:
            nodes_by_label[label].append(props)
        for label, props_list in nodes_by_label.items():
            if not props_list:
                continue
            id_key = self.unique_constraints.get(label)
            if not id_key:
                logger.warning(
                    f"No unique constraint defined for label '{label}'. Skipping flush."
                )
                continue

            prop_keys = list(props_list[0].keys())
            set_clause = ", ".join([f"n.{key} = row.{key}" for key in prop_keys])
            query = (
                f"MERGE (n:{label} {{{id_key}: row.{id_key}}}) "
                f"ON CREATE SET {set_clause} ON MATCH SET {set_clause}"
            )
            self._execute_batch(query, props_list)
        logger.info(f"Flushed {len(self.node_buffer)} nodes.")
        self.node_buffer.clear()

    def flush_relationships(self) -> None:
        if not self.relationship_buffer:
            return

        rels_by_pattern = defaultdict(list)
        for from_node, rel_type, to_node, props in self.relationship_buffer:
            pattern = (from_node[0], from_node[1], rel_type, to_node[0], to_node[1])
            rels_by_pattern[pattern].append(
                {"from_val": from_node[2], "to_val": to_node[2], "props": props or {}}
            )

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
                self._execute_batch(query, params_list)
            except Exception as e:
                logger.error(
                    f"❌ Failed to write relationships of type {rel_type}: {e}"
                )
                logger.error(f"   Query: {query}")
                logger.error(f"   Parameters: {params_list}")
                raise

        logger.info(f"Flushed {len(self.relationship_buffer)} relationships.")
        self.relationship_buffer.clear()

    def flush_all(self) -> None:
        logger.info("--- Flushing all pending writes to database... ---")
        self.flush_nodes()
        self.flush_relationships()
        logger.info("--- Flushing complete. ---")

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
