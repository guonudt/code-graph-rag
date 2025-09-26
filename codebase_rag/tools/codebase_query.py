from loguru import logger
from pydantic_ai import Tool
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..graph_updater import MemgraphIngestor
from ..schemas import GraphData
from ..services.llm import CypherGenerator, LLMGenerationError


class GraphQueryError(Exception):
    """Custom exception for graph query failures."""

    pass


def create_query_tool(
    ingestor: MemgraphIngestor,
    cypher_gen: CypherGenerator,
    console: Console | None = None,
) -> Tool:
    """
    Factory function that creates the knowledge graph query tool,
    injecting its dependencies.
    """
    # Use provided console or create a default one
    if console is None:
        console = Console(width=None, force_terminal=True)

    async def query_codebase_knowledge_graph(natural_language_query: str) -> GraphData:
        """
        Queries the codebase knowledge graph using natural language.

        Provide your question in plain English about the codebase structure,
        functions, classes, dependencies, or relationships. The tool will
        automatically translate your natural language question into the
        appropriate database query and return the results.

        Examples:
        - "Find all functions that call each other"
        - "What classes are in the user authentication module"
        - "Show me functions with the longest call chains"
        - "Which files contain functions related to database operations"
        """
        import time

        logger.info(
            f"[Tool:QueryGraph] 🔍 Processing query: '{natural_language_query}'"
        )
        start_time = time.time()
        cypher_query = "N/A"

        try:
            # Generate Cypher query
            logger.info("[Tool:QueryGraph] 🤖 Generating Cypher query...")
            cypher_query = await cypher_gen.generate(natural_language_query)
            logger.info(f"[Tool:QueryGraph] ✅ Generated Cypher: {cypher_query}")

            # Execute query
            logger.info("[Tool:QueryGraph] 🔄 Executing query...")
            results = ingestor.fetch_all(cypher_query)

            query_time = time.time() - start_time
            logger.info(f"[Tool:QueryGraph] ⏱️ Total query time: {query_time:.3f}s")

            if results:
                # Create enhanced table display
                table = Table(
                    show_header=True,
                    header_style="bold cyan",
                    border_style="bright_blue",
                    title_style="bold white",
                )

                headers = results[0].keys()
                for header in headers:
                    table.add_column(header, style="green", min_width=15)

                # Add rows with enhanced formatting
                for i, row in enumerate(results):
                    renderable_values = []
                    for value in row.values():
                        if value is None:
                            renderable_values.append("[dim]null[/dim]")
                        elif isinstance(value, bool):
                            renderable_values.append(
                                "[green]✓[/green]" if value else "[red]✗[/red]"
                            )
                        elif isinstance(value, int | float):
                            renderable_values.append(f"[yellow]{value}[/yellow]")
                        elif isinstance(value, str) and len(value) > 50:
                            # Truncate long strings with ellipsis
                            renderable_values.append(f"{value[:47]}...")
                        else:
                            renderable_values.append(str(value))
                    table.add_row(*renderable_values)

                # Display results with enhanced formatting
                console.print()
                console.print(
                    Panel(
                        table,
                        title=f"[bold blue]📊 Query Results ({len(results)} items)[/bold blue]",
                        subtitle=f"[dim]Query time: {query_time:.3f}s[/dim]",
                        expand=False,
                        border_style="bright_blue",
                    )
                )

                # Show query details in a separate panel
                console.print(
                    Panel(
                        f"[bold]Natural Language Query:[/bold] {natural_language_query}\n"
                        f"[bold]Generated Cypher:[/bold] [dim]{cypher_query}[/dim]",
                        title="[bold green]🔍 Query Details[/bold green]",
                        expand=False,
                        border_style="green",
                    )
                )

            summary = f"✅ Successfully retrieved {len(results)} item(s) from the graph in {query_time:.3f}s"
            return GraphData(query_used=cypher_query, results=results, summary=summary)

        except LLMGenerationError as e:
            error_time = time.time() - start_time
            logger.error(
                f"[Tool:QueryGraph] ❌ Cypher generation failed after {error_time:.3f}s: {e}"
            )
            return GraphData(
                query_used="N/A",
                results=[],
                summary=f"❌ Couldn't translate your request into a database query. Error: {e}",
            )
        except Exception as e:
            error_time = time.time() - start_time
            logger.error(
                f"[Tool:QueryGraph] ❌ Query execution failed after {error_time:.3f}s: {e}",
                exc_info=True,
            )
            return GraphData(
                query_used=cypher_query,
                results=[],
                summary=f"❌ Database query error after {error_time:.3f}s: {e}",
            )

    return Tool(
        function=query_codebase_knowledge_graph,
        description="Query the codebase knowledge graph using natural language questions. Ask in plain English about classes, functions, methods, dependencies, or code structure. Examples: 'Find all functions that call each other', 'What classes are in the user module', 'Show me functions with the longest call chains'.",
    )
