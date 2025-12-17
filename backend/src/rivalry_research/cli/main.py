"""Main CLI entry point for Rivalry Research."""

import typer

from . import clean, fs, sources, images

app = typer.Typer(
    name="rivalry",
    help="Rivalry Research CLI - Tools for analyzing rivalrous relationships",
    no_args_is_help=True,
)

# Register subcommand groups
app.add_typer(clean.app, name="clean", help="Data cleanup commands")
app.add_typer(fs.app, name="fs", help="File Search management commands")
app.add_typer(sources.app, name="sources", help="Source management commands")
app.add_typer(images.app, name="images", help="Image management commands")


if __name__ == "__main__":
    app()

