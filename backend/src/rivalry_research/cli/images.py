"""CLI commands for image management."""

import json
import logging
import shutil
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ..config import get_settings
from ..sources.image_scanner import (
    scan_entity_images,
    get_image_statistics,
    validate_all_images,
    list_entities_with_images,
    validate_image_directory,
)
from ..sources.image_downloader import download_and_store_image
from ..sources.utils import get_entity_directory

app = typer.Typer(
    name="images",
    help="Manage entity images (download, add, validate)",
)

console = Console()
logger = logging.getLogger(__name__)


@app.command()
def list_cmd(
    entity: str | None = typer.Option(
        None,
        "--entity",
        "-e",
        help="Entity ID to list images for (e.g., Q9021)",
    ),
    show_all: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="List all entities with images",
    ),
):
    """
    List images for an entity or all entities.
    """
    settings = get_settings()
    raw_sources_dir = Path(settings.raw_sources_dir)
    
    if show_all:
        console.print("\n[bold]Entities with Images:[/bold]\n")
        
        entities = list_entities_with_images(raw_sources_dir)
        
        if not entities:
            console.print("[yellow]No entities with images found.[/yellow]")
            return
        
        table = Table(show_header=True)
        table.add_column("Entity", style="cyan")
        table.add_column("Total", style="green", justify="right")
        table.add_column("Manual", style="yellow", justify="right")
        table.add_column("Auto", style="blue", justify="right")
        
        for entity_info in entities:
            table.add_row(
                entity_info["entity_name"],
                str(entity_info["image_count"]),
                str(entity_info["manual_count"]),
                str(entity_info["auto_count"]),
            )
        
        console.print(table)
        console.print()
        return
    
    if not entity:
        console.print("[red]Error: Must specify --entity or --all[/red]")
        raise typer.Exit(1)
    
    # Find entity directory
    entity_dirs = [d for d in raw_sources_dir.iterdir() if d.is_dir() and entity in d.name]
    
    if not entity_dirs:
        console.print(f"[red]No directory found for entity {entity}[/red]")
        raise typer.Exit(1)
    
    entity_dir = entity_dirs[0]
    images = scan_entity_images(entity_dir)
    
    if not images:
        console.print(f"\n[yellow]No images found for {entity_dir.name}[/yellow]\n")
        return
    
    console.print(f"\n[bold]Images for {entity_dir.name}:[/bold]\n")
    
    table = Table(show_header=True)
    table.add_column("Directory", style="cyan")
    table.add_column("Source", style="yellow")
    table.add_column("Title", style="white", max_width=50)
    table.add_column("License", style="green")
    
    for img in images:
        table.add_row(
            img.get("directory_name", "?"),
            img.get("source", "?"),
            img.get("title", "")[:50] if img.get("title") else "",
            img.get("license", "?"),
        )
    
    console.print(table)
    console.print()


@app.command()
def add(
    entity: str = typer.Argument(..., help="Entity ID (e.g., Q9021)"),
    file: Path = typer.Argument(..., help="Path to image file"),
    title: str | None = typer.Option(None, "--title", "-t", help="Image title"),
    license: str = typer.Option("public_domain", "--license", "-l", help="License type"),
    attribution: str | None = typer.Option(None, "--attribution", "-a", help="Attribution text"),
    source: str = typer.Option("manual", "--source", "-s", help="Source description"),
):
    """
    Add a manual image for an entity.
    
    Copies the image file to the appropriate location and creates metadata.
    """
    settings = get_settings()
    raw_sources_dir = Path(settings.raw_sources_dir)
    
    if not file.exists():
        console.print(f"[red]Error: File not found: {file}[/red]")
        raise typer.Exit(1)
    
    # Validate file type
    valid_extensions = [".jpg", ".jpeg", ".png", ".gif", ".webp"]
    if file.suffix.lower() not in valid_extensions:
        console.print(f"[red]Error: File must be an image ({', '.join(valid_extensions)})[/red]")
        raise typer.Exit(1)
    
    console.print(f"\n[bold]Adding manual image for entity {entity}[/bold]")
    
    # Find or create entity directory
    entity_dirs = [d for d in raw_sources_dir.iterdir() if d.is_dir() and entity in d.name]
    
    if not entity_dirs:
        console.print(f"[yellow]No existing directory for {entity}. Creating new directory...[/yellow]")
        entity_dir = raw_sources_dir / f"Entity_{entity}"
        entity_dir.mkdir(parents=True, exist_ok=True)
    else:
        entity_dir = entity_dirs[0]
    
    # Create images directory if it doesn't exist
    images_dir = entity_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    
    # Find next manual_NNN number
    manual_dirs = [d for d in images_dir.iterdir() if d.is_dir() and d.name.startswith("manual_")]
    next_num = len(manual_dirs) + 1
    
    manual_dir = images_dir / f"manual_{next_num:03d}"
    manual_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy image file
    dest_file = manual_dir / f"image{file.suffix.lower()}"
    shutil.copy2(file, dest_file)
    console.print(f"[green]✓ Copied image to: {dest_file}[/green]")
    
    # Generate thumbnail
    try:
        from ..sources.image_downloader import _generate_thumbnail
        thumbnail_path = _generate_thumbnail(dest_file, manual_dir)
        console.print(f"[green]✓ Generated thumbnail[/green]")
    except Exception as e:
        console.print(f"[yellow]⚠ Failed to generate thumbnail: {e}[/yellow]")
    
    # Create metadata
    metadata = {
        "source": source,
        "original_url": None,
        "title": title or file.name,
        "license": license,
        "attribution": attribution,
        "file_size_bytes": dest_file.stat().st_size,
        "image_format": file.suffix.lower().lstrip("."),
        "local_filename": dest_file.name,
    }
    
    metadata_file = manual_dir / "metadata.json"
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    
    console.print(f"[green]✓ Created metadata.json[/green]")
    console.print(f"\n[bold green]✓ Image added to: {manual_dir}[/bold green]")
    console.print("\n[dim]The image will be automatically loaded in future analyses.[/dim]")
    console.print()


@app.command()
def validate(
    entity: str | None = typer.Option(
        None,
        "--entity",
        "-e",
        help="Validate images only for this entity ID",
    ),
):
    """
    Validate images for correctness.
    
    Checks if image files are valid, metadata exists, and structure is correct.
    """
    settings = get_settings()
    raw_sources_dir = Path(settings.raw_sources_dir)
    
    console.print(f"\n[bold]Validating images in:[/bold] {raw_sources_dir}\n")
    
    entity_dirs = [d for d in raw_sources_dir.iterdir() if d.is_dir()]
    
    if entity:
        entity_dirs = [d for d in entity_dirs if entity in d.name]
    
    total_valid = 0
    total_invalid = 0
    
    for entity_dir in entity_dirs:
        images_dir = entity_dir / "images"
        
        if not images_dir.exists():
            continue
        
        validation_result = validate_all_images(entity_dir)
        
        if validation_result["total"] == 0:
            continue
        
        console.print(f"[bold]{entity_dir.name}:[/bold]")
        console.print(f"  Total: {validation_result['total']}")
        console.print(f"  [green]Valid: {validation_result['valid']}[/green]")
        
        if validation_result["invalid"] > 0:
            console.print(f"  [red]Invalid: {validation_result['invalid']}[/red]")
            
            for error in validation_result["errors"]:
                console.print(f"    [red]✗ {error['directory']}: {error['error']}[/red]")
        
        console.print()
        
        total_valid += validation_result["valid"]
        total_invalid += validation_result["invalid"]
    
    console.print(f"[bold]Summary:[/bold]")
    console.print(f"  Total valid: {total_valid}")
    console.print(f"  Total invalid: {total_invalid}")
    console.print()


@app.command()
def stats(
    entity: str | None = typer.Option(
        None,
        "--entity",
        "-e",
        help="Show stats for specific entity ID",
    ),
):
    """
    Show image statistics.
    
    Displays counts by source, manual vs auto, etc.
    """
    settings = get_settings()
    raw_sources_dir = Path(settings.raw_sources_dir)
    
    if entity:
        # Stats for specific entity
        entity_dirs = [d for d in raw_sources_dir.iterdir() if d.is_dir() and entity in d.name]
        
        if not entity_dirs:
            console.print(f"[red]No directory found for entity {entity}[/red]")
            raise typer.Exit(1)
        
        entity_dir = entity_dirs[0]
        stats = get_image_statistics(entity_dir)
        
        console.print(f"\n[bold cyan]Image Statistics for {entity_dir.name}[/bold cyan]\n")
        console.print(f"[bold]Total images:[/bold] {stats['total']}")
        console.print(f"[bold]Manual images:[/bold] {stats['manual']}")
        console.print(f"[bold]Auto-fetched:[/bold] {stats['auto']}")
        console.print(f"[bold]With thumbnails:[/bold] {stats['with_thumbnails']}")
        
        if stats['by_source']:
            console.print(f"\n[bold]By Source:[/bold]")
            for source, count in sorted(stats['by_source'].items()):
                console.print(f"  {source}: {count}")
        
        console.print()
    else:
        # Stats for all entities
        entities = list_entities_with_images(raw_sources_dir)
        
        if not entities:
            console.print("\n[yellow]No entities with images found.[/yellow]\n")
            return
        
        total_images = sum(e["image_count"] for e in entities)
        total_manual = sum(e["manual_count"] for e in entities)
        total_auto = sum(e["auto_count"] for e in entities)
        
        console.print(f"\n[bold cyan]Global Image Statistics[/bold cyan]\n")
        console.print(f"[bold]Entities with images:[/bold] {len(entities)}")
        console.print(f"[bold]Total images:[/bold] {total_images}")
        console.print(f"[bold]Manual images:[/bold] {total_manual}")
        console.print(f"[bold]Auto-fetched:[/bold] {total_auto}")
        console.print()


@app.command()
def info(
    entity: str = typer.Argument(..., help="Entity ID (e.g., Q9021)"),
    image_dir: str = typer.Argument(..., help="Image directory name (e.g., manual_001)"),
):
    """
    Show detailed information about a specific image.
    """
    settings = get_settings()
    raw_sources_dir = Path(settings.raw_sources_dir)
    
    # Find entity directory
    entity_dirs = [d for d in raw_sources_dir.iterdir() if d.is_dir() and entity in d.name]
    
    if not entity_dirs:
        console.print(f"[red]No directory found for entity {entity}[/red]")
        raise typer.Exit(1)
    
    entity_dir = entity_dirs[0]
    image_path = entity_dir / "images" / image_dir
    
    if not image_path.exists():
        console.print(f"[red]Image directory not found: {image_path}[/red]")
        raise typer.Exit(1)
    
    # Load metadata
    from ..sources.image_downloader import load_image_metadata
    metadata = load_image_metadata(image_path)
    
    if not metadata:
        console.print(f"[red]No metadata found in {image_path}[/red]")
        raise typer.Exit(1)
    
    # Validate
    is_valid, msg = validate_image_directory(image_path)
    
    console.print(f"\n[bold]Image Information: {image_dir}[/bold]\n")
    console.print(f"[bold]Entity:[/bold] {entity_dir.name}")
    console.print(f"[bold]Location:[/bold] {image_path}")
    console.print(f"[bold]Valid:[/bold] {'✓' if is_valid else '✗'} {msg}")
    console.print()
    
    console.print("[bold]Metadata:[/bold]")
    for key, value in sorted(metadata.items()):
        if value is not None:
            console.print(f"  {key}: {value}")
    
    console.print()

