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
from rich.progress import Progress, SpinnerColumn, TextColumn
from loguru import logger

from src.config import get_settings
from src.pipeline import KnowledgeGraphPipeline as Pipeline
from src.graph import GraphStore

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
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                
                if len(urls) == 1:
                    task = progress.add_task(f"Processing {urls[0]}...", total=None)
                    result = await pipeline.process_url(urls[0])
                    progress.update(task, completed=True)
                    
                    _display_result(result)
                else:
                    task = progress.add_task(f"Processing {len(urls)} URLs...", total=len(urls))
                    results = await pipeline.process_batch(urls, max_concurrent=concurrent)
                    progress.update(task, completed=len(urls))
                    
                    _display_batch_results(results)
        
        finally:
            await pipeline.close()
    
    asyncio.run(_process())


@app.command()
def graph(
    stats: bool = typer.Option(True, "--stats/--no-stats", help="Show graph statistics"),
    export: str = typer.Option(None, "--export", "-e", help="Export graph (graphml, gexf, json)"),
):
    """View or export the knowledge graph."""
    
    graph_store = GraphStore()
    
    if stats:
        stats_data = graph_store.get_stats()
        _display_graph_stats(stats_data)
    
    if export:
        format = export.lower()
        if format not in ["graphml", "gexf", "json"]:
            console.print(f"[red]Invalid format: {format}. Use graphml, gexf, or json[/red]")
            return
        
        filepath = graph_store.export_graph(format)
        console.print(f"[green]Graph exported to: {filepath}[/green]")


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(10, "--limit", "-l", help="Max results"),
    topic: str = typer.Option(None, "--topic", "-t", help="Filter by topic"),
):
    """Search the knowledge graph."""
    
    graph_store = GraphStore()
    
    # Simple text search in graph
    results = []
    query_lower = query.lower()
    
    for node_id, data in graph_store.graph.nodes(data=True):
        if data.get("node_type") == "entity":
            name = data.get("name", "").lower()
            description = data.get("description", "").lower()
            tags = " ".join(data.get("tags", [])).lower()
            
            if query_lower in name or query_lower in description or query_lower in tags:
                if topic is None or data.get("topic") == topic:
                    results.append({
                        "id": node_id,
                        "name": data.get("name"),
                        "type": data.get("type"),
                        "topic": data.get("topic"),
                        "description": data.get("description", "")[:200],
                        "tags": data.get("tags", [])[:5]
                    })
    
    results = results[:limit]
    
    if not results:
        console.print("[yellow]No results found[/yellow]")
        return
    
    table = Table(title=f"Search Results for '{query}'")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Topic", style="green")
    table.add_column("Description", style="white")
    table.add_column("Tags", style="dim")
    
    for r in results:
        table.add_row(
            r["name"],
            r["type"],
            r["topic"] or "N/A",
            r["description"],
            ", ".join(r["tags"])
        )
    
    console.print(table)


@app.command()
def entity(
    name: str = typer.Argument(..., help="Entity name to look up"),
):
    """Get detailed info about an entity."""
    
    graph_store = GraphStore()
    entity = graph_store.get_entity(name)
    
    if not entity:
        console.print(f"[red]Entity '{name}' not found[/red]")
        return
    
    console.print(f"[bold cyan]{entity['name']}[/bold cyan] ({entity['type']})")
    console.print(f"Topic: [green]{entity.get('topic', 'N/A')}[/green]")
    console.print(f"Sub-topic: [green]{entity.get('sub_topic', 'N/A')}[/green]")
    console.print(f"Content Type: [yellow]{entity.get('content_type', 'N/A')}[/yellow]")
    console.print(f"Version: {entity.get('version', 1)}")
    console.print(f"Confidence: {entity.get('confidence', 0):.0%}")
    console.print()
    console.print("[bold]Description:[/bold]")
    console.print(entity.get("description", "N/A"))
    console.print()
    
    if entity.get("key_points"):
        console.print("[bold]Key Points:[/bold]")
        for pt in entity["key_points"]:
            console.print(f"  • {pt}")
        console.print()
    
    if entity.get("similar_tools"):
        console.print("[bold]Similar Tools:[/bold]")
        for tool in entity["similar_tools"][:5]:
            console.print(f"  • {tool.get('name')}: {tool.get('description', '')[:100]}")
        console.print()
    
    # Related entities
    related = graph_store.get_related(name, limit=10)
    if related:
        console.print("[bold]Related:[/bold]")
        for rel in related:
            console.print(f"  [{rel['relation']}] {rel.get('name', 'N/A')} ({rel.get('type', 'N/A')})")


def _display_result(result):
    """Display single result."""
    if result.success:
        console.print(f"\n[green]✓ Success:[/green] {result.url}")
        console.print(f"  Chunks: {len(result.chunks)}")
        console.print(f"  Entities: {len(result.entities)}")
        console.print(f"  Categorized: {len(result.categorized_items)}")
        console.print(f"  Time: {result.processing_time_ms}ms")
        console.print(f"  Stages: {', '.join(s.value for s in result.stages_completed)}")
    else:
        console.print(f"\n[red]✗ Failed:[/red] {result.url}")
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
        status = "[green]✓[/green]" if r.success else "[red]✗[/red]"
        table.add_row(
            r.url[:60] + "..." if len(r.url) > 60 else r.url,
            status,
            str(len(r.entities)),
            str(len(r.categorized_items)),
            str(r.processing_time_ms)
        )
    
    console.print(table)
    
    success_count = sum(1 for r in results if r.success)
    console.print(f"\n[bold]Summary:[/bold] {success_count}/{len(results)} succeeded")


def _display_graph_stats(stats):
    """Display graph statistics."""
    console.print("\n[bold]Knowledge Graph Statistics[/bold]")
    console.print(f"  Total Nodes: {stats['total_nodes']}")
    console.print(f"  Total Edges: {stats['total_edges']}")
    console.print(f"  Density: {stats['density']:.4f}")
    console.print()
    
    console.print("[bold]Node Types:[/bold]")
    for ntype, count in stats['node_types'].items():
        console.print(f"  {ntype}: {count}")
    
    console.print()
    console.print("[bold]Edge Types:[/bold]")
    for etype, count in stats['edge_types'].items():
        console.print(f"  {etype}: {count}")


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
            if "KEY" in field_name or "SECRET" in field_name:
                value = "***" if value else "NOT SET"
            table.add_row(field_name, str(value))
    
    console.print(table)


if __name__ == "__main__":
    app()