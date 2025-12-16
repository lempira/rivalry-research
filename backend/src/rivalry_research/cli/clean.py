"""Data cleanup commands for Rivalry Research."""

import shutil
from pathlib import Path

import typer

from ..config import get_settings

app = typer.Typer(help="Delete generated data")


def count_files_recursive(path: Path) -> int:
    """Count all files in a directory recursively."""
    if not path.exists():
        return 0
    if path.is_file():
        return 1
    return sum(1 for _ in path.rglob("*") if _.is_file())


def format_size(path: Path) -> str:
    """Get human-readable size of a file or directory."""
    if not path.exists():
        return "0 B"
    
    if path.is_file():
        size = path.stat().st_size
    else:
        size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def show_what_will_be_deleted(
    analyses_dir: Path,
    raw_sources_dir: Path,
    sources_db: Path,
    scope: str = "all",
) -> None:
    """Display what will be deleted."""
    typer.echo("\nData to be deleted:")
    typer.echo("━" * 70)
    
    if scope in ("all", "analyses"):
        count = count_files_recursive(analyses_dir)
        size = format_size(analyses_dir)
        status = "✓ exists" if analyses_dir.exists() else "✗ not found"
        typer.echo(f"Analyses:     {count:>5} files, {size:>10} ({status})")
        typer.echo(f"  Path: {analyses_dir}")
    
    if scope in ("all", "sources"):
        count = count_files_recursive(raw_sources_dir)
        size = format_size(raw_sources_dir)
        status = "✓ exists" if raw_sources_dir.exists() else "✗ not found"
        typer.echo(f"Sources:      {count:>5} files, {size:>10} ({status})")
        typer.echo(f"  Path: {raw_sources_dir}")
        
        db_status = "✓ exists" if sources_db.exists() else "✗ not found"
        db_size = format_size(sources_db)
        typer.echo(f"Database:     {db_size:>17} ({db_status})")
        typer.echo(f"  Path: {sources_db}")
    
    typer.echo("━" * 70)


def delete_path(path: Path, dry_run: bool = False) -> bool:
    """Delete a file or directory."""
    if not path.exists():
        return False
    
    if dry_run:
        return True
    
    try:
        if path.is_file():
            path.unlink()
        else:
            shutil.rmtree(path)
        return True
    except Exception as e:
        typer.echo(f"Error deleting {path}: {e}", err=True)
        return False


@app.command("all")
def clean_all(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would be deleted without deleting"),
) -> None:
    """
    Delete all generated data (analyses, sources, and database).
    
    This will delete:
    - All analysis JSON files in data/analyses/
    - All downloaded sources in data/raw_sources/
    - The SQLite database at data/sources.db
    """
    settings = get_settings()
    
    show_what_will_be_deleted(
        settings.analyses_dir,
        settings.raw_sources_dir,
        settings.sources_db_path,
        scope="all"
    )
    
    if dry_run:
        typer.echo("\n[DRY RUN] No files were deleted.")
        return
    
    if not force:
        typer.confirm("\nDelete all data?", abort=True)
    
    typer.echo("\nDeleting...")
    
    deleted = []
    
    if delete_path(settings.analyses_dir, dry_run):
        deleted.append("analyses")
        typer.echo("✓ Deleted analyses")
    
    if delete_path(settings.raw_sources_dir, dry_run):
        deleted.append("sources")
        typer.echo("✓ Deleted sources")
    
    if delete_path(settings.sources_db_path, dry_run):
        deleted.append("database")
        typer.echo("✓ Deleted database")
    
    if deleted:
        typer.echo(f"\n✓ Successfully deleted: {', '.join(deleted)}")
    else:
        typer.echo("\n✗ No data found to delete")


@app.command("analyses")
def clean_analyses(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would be deleted without deleting"),
) -> None:
    """
    Delete only analysis results.
    
    This will delete all analysis JSON files in data/analyses/
    """
    settings = get_settings()
    
    show_what_will_be_deleted(
        settings.analyses_dir,
        settings.raw_sources_dir,
        settings.sources_db_path,
        scope="analyses"
    )
    
    if dry_run:
        typer.echo("\n[DRY RUN] No files were deleted.")
        return
    
    if not force:
        typer.confirm("\nDelete analyses?", abort=True)
    
    typer.echo("\nDeleting...")
    
    if delete_path(settings.analyses_dir, dry_run):
        typer.echo("✓ Deleted analyses")
        typer.echo(f"\n✓ Successfully deleted analyses from: {settings.analyses_dir}")
    else:
        typer.echo("\n✗ No analyses found to delete")


@app.command("sources")
def clean_sources(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would be deleted without deleting"),
) -> None:
    """
    Delete only source data.
    
    This will delete:
    - All downloaded sources in data/raw_sources/
    - The SQLite database at data/sources.db
    """
    settings = get_settings()
    
    show_what_will_be_deleted(
        settings.analyses_dir,
        settings.raw_sources_dir,
        settings.sources_db_path,
        scope="sources"
    )
    
    if dry_run:
        typer.echo("\n[DRY RUN] No files were deleted.")
        return
    
    if not force:
        typer.confirm("\nDelete sources and database?", abort=True)
    
    typer.echo("\nDeleting...")
    
    deleted = []
    
    if delete_path(settings.raw_sources_dir, dry_run):
        deleted.append("sources")
        typer.echo("✓ Deleted sources")
    
    if delete_path(settings.sources_db_path, dry_run):
        deleted.append("database")
        typer.echo("✓ Deleted database")
    
    if deleted:
        typer.echo(f"\n✓ Successfully deleted: {', '.join(deleted)}")
    else:
        typer.echo("\n✗ No sources found to delete")


@app.command("database")
def clean_database(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would be deleted without deleting"),
) -> None:
    """
    Delete only the SQLite database.
    
    This will delete the SQLite database at data/sources.db.
    Downloaded sources will be preserved and can be re-indexed.
    
    Useful for:
    - Resetting the database without losing downloaded sources
    - Recovering from database corruption
    - Force re-indexing of existing sources
    """
    settings = get_settings()
    
    typer.echo("\nData to be deleted:")
    typer.echo("━" * 70)
    
    db_status = "✓ exists" if settings.sources_db_path.exists() else "✗ not found"
    db_size = format_size(settings.sources_db_path)
    typer.echo(f"Database:     {db_size:>17} ({db_status})")
    typer.echo(f"  Path: {settings.sources_db_path}")
    typer.echo("━" * 70)
    
    if dry_run:
        typer.echo("\n[DRY RUN] No files were deleted.")
        return
    
    if not force:
        typer.confirm("\nDelete database?", abort=True)
    
    typer.echo("\nDeleting...")
    
    if delete_path(settings.sources_db_path, dry_run):
        typer.echo("✓ Deleted database")
        typer.echo(f"\n✓ Successfully deleted database from: {settings.sources_db_path}")
    else:
        typer.echo("\n✗ No database found to delete")

