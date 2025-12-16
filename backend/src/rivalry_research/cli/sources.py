"""CLI commands for source management."""

import json
import logging
import shutil
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ..config import get_settings
from ..sources import (
    process_existing_sources,
    scan_raw_sources_directory,
    get_source_statistics,
    validate_manual_source,
)
from ..storage import SourceDatabase

app = typer.Typer(
    name="sources",
    help="Manage sources (scan, process, validate)",
)

console = Console()
logger = logging.getLogger(__name__)


@app.command()
def scan(
    entity: str | None = typer.Option(
        None,
        "--entity",
        "-e",
        help="Filter by entity ID (e.g., Q9021)",
    ),
    unprocessed_only: bool = typer.Option(
        False,
        "--unprocessed-only",
        "-u",
        help="Show only unprocessed sources",
    ),
    show_invalid: bool = typer.Option(
        False,
        "--show-invalid",
        "-i",
        help="Show invalid sources",
    ),
):
    """
    Scan raw_sources directory and report status.
    
    Shows which sources are in the database, which need processing,
    and which are invalid.
    """
    settings = get_settings()
    raw_sources_dir = Path(settings.raw_sources_dir)
    db = SourceDatabase(settings.sources_db)
    
    console.print(f"\n[bold]Scanning sources in:[/bold] {raw_sources_dir}")
    if entity:
        console.print(f"[bold]Entity filter:[/bold] {entity}")
    
    result = scan_raw_sources_directory(raw_sources_dir, db, entity)
    
    # Summary
    console.print("\n[bold cyan]Summary:[/bold cyan]")
    console.print(f"  ✓ Sources in database: {len(result.sources_in_db)}")
    console.print(f"  ⚠ Sources not in database: {len(result.sources_not_in_db)}")
    console.print(f"  ✗ Invalid sources: {len(result.invalid_sources)}")
    
    # Show sources in DB
    if result.sources_in_db and not unprocessed_only:
        console.print("\n[bold green]Sources in Database:[/bold green]")
        table = Table(show_header=True)
        table.add_column("Source ID", style="cyan")
        table.add_column("Type", style="yellow")
        table.add_column("Manual", style="magenta")
        table.add_column("Title", style="white", max_width=60)
        
        for source in result.sources_in_db[:20]:  # Show first 20
            table.add_row(
                source.source_id,
                source.type,
                "✓" if source.is_manual else "✗",
                source.title,
            )
        
        console.print(table)
        
        if len(result.sources_in_db) > 20:
            console.print(f"  ... and {len(result.sources_in_db) - 20} more")
    
    # Show unprocessed sources
    if result.sources_not_in_db:
        console.print("\n[bold yellow]Sources Not in Database (Need Processing):[/bold yellow]")
        table = Table(show_header=True)
        table.add_column("Entity", style="cyan")
        table.add_column("Directory", style="white")
        table.add_column("File Type", style="yellow")
        table.add_column("Has Content", style="green")
        
        for source_meta in result.sources_not_in_db[:20]:
            source_dir = Path(source_meta["source_dir"])
            table.add_row(
                source_meta.get("entity_id", "?"),
                source_dir.name,
                source_meta.get("file_type", "?"),
                "✓" if source_meta.get("has_content_txt") else "✗",
            )
        
        console.print(table)
        
        if len(result.sources_not_in_db) > 20:
            console.print(f"  ... and {len(result.sources_not_in_db) - 20} more")
    
    # Show invalid sources
    if result.invalid_sources and show_invalid:
        console.print("\n[bold red]Invalid Sources:[/bold red]")
        table = Table(show_header=True)
        table.add_column("Path", style="white")
        table.add_column("Reason", style="red")
        
        for invalid in result.invalid_sources:
            table.add_row(
                invalid["path"],
                invalid["reason"],
            )
        
        console.print(table)
    
    console.print()


@app.command()
def process(
    entity: str | None = typer.Option(
        None,
        "--entity",
        "-e",
        help="Process sources only for this entity ID (e.g., Q9021)",
    ),
    all_sources: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Process all unprocessed sources",
    ),
):
    """
    Process unprocessed sources (manual or new).
    
    Extracts content, adds to database, and prepares for File Search.
    """
    if not all_sources and not entity:
        console.print("[red]Error: Must specify --entity or --all[/red]")
        raise typer.Exit(1)
    
    settings = get_settings()
    raw_sources_dir = Path(settings.raw_sources_dir)
    db = SourceDatabase(settings.sources_db)
    
    console.print(f"\n[bold]Processing sources in:[/bold] {raw_sources_dir}")
    if entity:
        console.print(f"[bold]Entity filter:[/bold] {entity}")
    
    with console.status("[bold green]Processing sources..."):
        results = process_existing_sources(db, raw_sources_dir, entity)
    
    if not results:
        console.print("\n[yellow]No unprocessed sources found.[/yellow]")
        return
    
    console.print(f"\n[bold green]✓ Successfully processed {len(results)} sources[/bold green]")
    
    # Show processed sources
    table = Table(show_header=True)
    table.add_column("Source ID", style="cyan")
    table.add_column("Type", style="yellow")
    table.add_column("Manual", style="magenta")
    table.add_column("Title", style="white", max_width=60)
    
    for source, _ in results:
        table.add_row(
            source.source_id,
            source.type,
            "✓" if source.is_manual else "✗",
            source.title,
        )
    
    console.print(table)
    console.print()


@app.command()
def add(
    entity: str = typer.Argument(..., help="Entity ID (e.g., Q9021)"),
    file: Path = typer.Argument(..., help="Path to source file (PDF or HTML)"),
    title: str | None = typer.Option(None, "--title", "-t", help="Source title"),
    authors: str | None = typer.Option(
        None, "--authors", "-a", help="Comma-separated author names"
    ),
):
    """
    Add a manual source for an entity.
    
    Copies the file to the appropriate location in raw_sources.
    """
    settings = get_settings()
    raw_sources_dir = Path(settings.raw_sources_dir)
    
    if not file.exists():
        console.print(f"[red]Error: File not found: {file}[/red]")
        raise typer.Exit(1)
    
    # Validate file type
    if file.suffix.lower() not in [".pdf", ".html", ".htm"]:
        console.print("[red]Error: File must be PDF or HTML[/red]")
        raise typer.Exit(1)
    
    console.print(f"\n[bold]Adding manual source for entity {entity}[/bold]")
    
    # Find or create entity directory
    entity_dirs = [d for d in raw_sources_dir.iterdir() if d.is_dir() and entity in d.name]
    
    if not entity_dirs:
        console.print(
            f"[yellow]No existing directory for {entity}. Creating new directory...[/yellow]"
        )
        entity_dir = raw_sources_dir / f"Entity_{entity}"
        entity_dir.mkdir(parents=True, exist_ok=True)
    else:
        entity_dir = entity_dirs[0]
    
    # Find next manual_NNN number
    manual_dirs = [d for d in entity_dir.iterdir() if d.is_dir() and d.name.startswith("manual_")]
    next_num = len(manual_dirs) + 1
    
    manual_dir = entity_dir / f"manual_{next_num:03d}"
    manual_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy file
    if file.suffix.lower() == ".pdf":
        dest_file = manual_dir / "original.pdf"
    else:
        dest_file = manual_dir / "original.html"
    
    shutil.copy2(file, dest_file)
    console.print(f"[green]✓ Copied file to: {dest_file}[/green]")
    
    # Create metadata.json if additional info provided
    if title or authors:
        metadata = {}
        if title:
            metadata["title"] = title
        if authors:
            metadata["authors"] = [a.strip() for a in authors.split(",")]
        
        metadata_file = manual_dir / "metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        
        console.print(f"[green]✓ Created metadata.json[/green]")
    
    console.print(f"\n[bold green]✓ Source added to: {manual_dir}[/bold green]")
    console.print("\nNext steps:")
    console.print(f"  1. Run: rivalry sources process --entity {entity}")
    console.print("  2. Recreate File Search store if analyzing this entity")
    console.print()


@app.command()
def validate(
    entity: str | None = typer.Option(
        None,
        "--entity",
        "-e",
        help="Validate sources only for this entity ID",
    ),
):
    """
    Validate manual sources for correctness.
    
    Checks if files are readable, parseable, and have sufficient content.
    """
    settings = get_settings()
    raw_sources_dir = Path(settings.raw_sources_dir)
    
    console.print(f"\n[bold]Validating sources in:[/bold] {raw_sources_dir}")
    
    entity_dirs = [d for d in raw_sources_dir.iterdir() if d.is_dir()]
    
    if entity:
        entity_dirs = [d for d in entity_dirs if entity in d.name]
    
    total_validated = 0
    total_valid = 0
    total_invalid = 0
    
    for entity_dir in entity_dirs:
        manual_dirs = [
            d for d in entity_dir.iterdir() 
            if d.is_dir() and d.name.startswith("manual_")
        ]
        
        for manual_dir in manual_dirs:
            total_validated += 1
            is_valid, message = validate_manual_source(manual_dir)
            
            if is_valid:
                total_valid += 1
                console.print(f"[green]✓ {entity_dir.name}/{manual_dir.name}: {message}[/green]")
            else:
                total_invalid += 1
                console.print(f"[red]✗ {entity_dir.name}/{manual_dir.name}: {message}[/red]")
    
    console.print(f"\n[bold]Validation Summary:[/bold]")
    console.print(f"  Total validated: {total_validated}")
    console.print(f"  Valid: {total_valid}")
    console.print(f"  Invalid: {total_invalid}")
    console.print()


@app.command()
def stats():
    """
    Show statistics about sources.
    
    Displays counts by type, manual vs auto, etc.
    """
    settings = get_settings()
    raw_sources_dir = Path(settings.raw_sources_dir)
    db = SourceDatabase(settings.sources_db)
    
    console.print("\n[bold cyan]Source Statistics[/bold cyan]\n")
    
    stats = get_source_statistics(raw_sources_dir, db)
    
    console.print(f"[bold]Total sources:[/bold] {stats['total_sources']}")
    console.print(f"[bold]Unprocessed sources:[/bold] {stats['unprocessed_sources']}")
    console.print(f"[bold]Invalid sources:[/bold] {stats['invalid_sources']}")
    
    console.print(f"\n[bold]By Origin:[/bold]")
    console.print(f"  Manual: {stats.get('manual_sources', 0)}")
    console.print(f"  Auto: {stats.get('auto_sources', 0)}")
    
    # Get DB stats for type breakdown
    db_stats = db.get_stats()
    
    if db_stats.get('by_type'):
        console.print("\n[bold]By Type:[/bold]")
        for source_type, count in sorted(db_stats['by_type'].items()):
            console.print(f"  {source_type}: {count}")
    
    console.print()

