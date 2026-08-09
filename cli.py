#!/usr/bin/env python3
"""
InstaGPT GraphRAG CLI
URL to Knowledge Graph Pipeline
"""

import asyncio
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from loguru import logger

from src.config import get_settings
from src.pipeline import KnowledgeGraphPipeline as Pipeline
from src.graph import Neo4jGraphStore, create_graph_store

app = typer.Typer(
    name="instagpt-graphrag",
    help="URL to Knowledge Graph Pipeline - Extract, enrich, categorize, and store knowledge from URLs",
    add_completion=False,
)

console = Console()
settings = get_settings()

# Configure logger
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=settings.LOG_LEVEL,
)


@app.command()
def process(
    urls: list[str] = typer.Argument(..., help="URLs to process"),
    concurrent: int = typer.Option(3, "--concurrent", "-c", help="Max concurrent URLs"),
    output_dir: str = typer.Option("./outputs", "--output", "-o", help="Output directory"),
):
    """Process one or more URLs through the full pipeline."""
    
    async def _process():
        pipeline = Pipeline()
        
        try:
            await pipeline.initialize()
            
            console.print(f"Processing {urls[0]}...")
            
            if len(urls) == 1:
                result = await pipeline.process_url(urls[0])
                _display_result(result)
            else:
                results = await pipeline.process_batch(urls, max_concurrent=concurrent)
                _display_batch_results(results)
        
        finally:
            await pipeline.close()
    
    asyncio.run(_process())


@app.command()
def graph(
    stats: bool = typer.Option(True, "--stats/--no-stats", help="Show graph statistics"),
    export: str = typer.Option(None, "--export", "-e", help="Export graph (cypher, json)"),
):
    """View or export the knowledge graph via Neo4j."""
    
    async def _graph():
        graph_store = await create_graph_store()
        try:
            if stats:
                stats_data = await graph_store.get_stats()
                _display_graph_stats(stats_data)
            
            if export:
                format = export.lower()
                if format not in ["cypher", "json"]:
                    console.print(f"[red]Invalid format: {format}. Use cypher or json[/red]")
                    return
                
                filepath = await graph_store.export_graph(format)
                console.print(f"[green]Graph exported to: {filepath}[/green]")
        finally:
            await graph_store.close()
    
    asyncio.run(_graph())


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(10, "--limit", "-l", help="Max results"),
):
    """Search the knowledge graph via Neo4j full-text search."""
    
    async def _search():
        graph_store = await create_graph_store()
        try:
            results = await graph_store.search_entities(query, limit=limit)
            
            if not results:
                console.print("[yellow]No results found[/yellow]")
                return
            
            table = Table(title=f"Search Results for '{query}'")
            table.add_column("Name", style="cyan")
            table.add_column("Type", style="magenta")
            table.add_column("Description", style="white")
            
            for r in results:
                table.add_row(
                    r.get("name", "N/A"),
                    r.get("type", "N/A"),
                    (r.get("description", "") or "")[:200],
                )
            
            console.print(table)
        finally:
            await graph_store.close()
    
    asyncio.run(_search())


@app.command()
def entity(
    name: str = typer.Argument(..., help="Entity name to look up"),
):
    """Get detailed info about an entity from Neo4j."""
    
    async def _entity():
        graph_store = await create_graph_store()
        try:
            entity = await graph_store.get_entity(name)
            
            if not entity:
                console.print(f"[red]Entity '{name}' not found[/red]")
                return
            
            console.print(f"[bold cyan]{entity.get('name', 'N/A')}[/bold cyan] ({entity.get('type', 'N/A')})")
            console.print(f"Topic: [green]{entity.get('topic', 'N/A')}[/green]")
            console.print(f"Sub-topic: [green]{entity.get('sub_topic', 'N/A')}[/green]")
            console.print(f"Content Type: [yellow]{entity.get('content_type', 'N/A')}[/yellow]")
            console.print(f"Version: {entity.get('version', 1)}")
            console.print(f"Confidence: {entity.get('confidence', 0):.0%}")
            console.print()
            console.print("[bold]Description:[/bold]")
            console.print(entity.get("description", "N/A"))
            console.print()
            
            # Related entities
            related = await graph_store.get_related(name, limit=10)
            if related:
                console.print("[bold]Related:[/bold]")
                for rel in related:
                    node = rel.get("node", {})
                    console.print(f"  [{rel.get('relation', 'N/A')}] {node.get('name', 'N/A')} ({node.get('type', 'N/A')})")
        finally:
            await graph_store.close()
    
    asyncio.run(_entity())


def _display_result(result):
    """Display single result."""
    if result.success:
        pr = result.processing_result
        console.print(f"\n[green]Success:[/green] {result.url}")
        if pr:
            console.print(f"  Chunks: {len(pr.chunks)}")
            console.print(f"  Entities: {len(pr.entities)}")
            console.print(f"  Categorized: {len(pr.categorized_items)}")
            console.print(f"  Time: {pr.processing_time_ms}ms")
            stages = [s.value if hasattr(s, 'value') else s for s in pr.stages_completed]
            console.print(f"  Stages: {', '.join(stages)}")
    else:
        console.print(f"\n[red]Failed:[/red] {result.url}")
        console.print(f"  Error: {result.error}")


def _display_batch_results(results):
    """Display batch results."""
    table = Table(title="Batch Processing Results")
    table.add_column("URL", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Entities", justify="right")
    table.add_column("Categorized", justify="right")
    table.add_column("Time (ms)", justify="right")
    
    for r in results:
        status = "[green]OK[/green]" if r.success else "[red]FAIL[/red]"
        table.add_row(
            r.url[:60] + "..." if len(r.url) > 60 else r.url,
            status,
            str(len(r.entities)) if r.processing_result else "0",
            str(len(r.categorized_items)) if r.processing_result else "0",
            str(r.processing_result.processing_time_ms) if r.processing_result else "0"
        )
    
    console.print(table)
    
    success_count = sum(1 for r in results if r.success)
    console.print(f"\n[bold]Summary:[/bold] {success_count}/{len(results)} succeeded")


def _display_graph_stats(stats):
    """Display graph statistics."""
    console.print("\n[bold]Knowledge Graph Statistics[/bold]")
    
    for stat in stats.get("total_nodes", []):
        console.print(f"  Total Nodes: {stat.get('count', 0)}")
    for stat in stats.get("total_edges", []):
        console.print(f"  Total Edges: {stat.get('count', 0)}")
    
    console.print()
    console.print("[bold]Node Types:[/bold]")
    for stat in stats.get("node_types", []):
        console.print(f"  {stat.get('type', 'N/A')}: {stat.get('count', 0)}")
    
    console.print()
    console.print("[bold]Edge Types:[/bold]")
    for stat in stats.get("edge_types", []):
        console.print(f"  {stat.get('type', 'N/A')}: {stat.get('count', 0)}")


@app.command()
def config():
    """Show current configuration."""
    s = get_settings()
    
    table = Table(title="Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="white")
    
    for field_name in dir(s):
        if not field_name.startswith("_"):
            value = getattr(s, field_name)
            if "KEY" in field_name or "SECRET" in field_name or "PASSWORD" in field_name:
                value = "***" if value else "NOT SET"
            table.add_row(field_name, str(value))
    
    console.print(table)


if __name__ == "__main__":
    app()
