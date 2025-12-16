"""File Search management commands for Rivalry Research."""

import json
from datetime import datetime
from typing import Any

import typer

from ..rag import file_search_client

app = typer.Typer(help="File Search store management")


def format_timestamp(timestamp: Any) -> str:
    """Format timestamp for display."""
    if timestamp is None:
        return "N/A"
    
    if isinstance(timestamp, str):
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, AttributeError):
            return timestamp
    
    return str(timestamp)


def format_size(size_bytes: int | None) -> str:
    """Format file size in human-readable format."""
    if size_bytes is None:
        return "N/A"
    
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


@app.command("list-stores")
def list_stores(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information"),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
) -> None:
    """List all File Search stores."""
    try:
        stores = file_search_client.list_stores()
        
        if json_output:
            output = []
            for store in stores:
                store_data = {
                    "name": store.name,
                    "display_name": getattr(store, "display_name", None),
                    "create_time": getattr(store, "create_time", None),
                }
                output.append(store_data)
            typer.echo(json.dumps(output, indent=2))
            return
        
        if not stores:
            typer.echo("No File Search stores found.")
            return
        
        typer.echo("\nFile Search Stores:")
        typer.echo("━" * 70)
        
        for store in stores:
            display_name = getattr(store, "display_name", "N/A")
            create_time = getattr(store, "create_time", None)
            
            typer.echo(f"✓ {store.name}")
            typer.echo(f"  Name: {display_name}")
            typer.echo(f"  Created: {format_timestamp(create_time)}")
            
            if verbose:
                try:
                    docs = file_search_client.list_documents(store.name)
                    typer.echo(f"  Documents: {docs['total']}")
                except Exception as e:
                    typer.echo(f"  Documents: Error ({e})")
            
            typer.echo()
        
        typer.echo(f"Total: {len(stores)} store{'s' if len(stores) != 1 else ''}")
        
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        typer.echo("\nMake sure GOOGLE_API_KEY environment variable is set.", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error listing stores: {e}", err=True)
        raise typer.Exit(1)


@app.command("list-docs")
def list_docs(
    store_name: str = typer.Argument(None, help="File Search store name (lists all stores if omitted)"),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
) -> None:
    """List document counts in File Search stores."""
    try:
        if store_name:
            stores = [type("Store", (), {"name": store_name})()]
        else:
            stores = file_search_client.list_stores()
            if not stores:
                typer.echo("No File Search stores found.")
                return
        
        all_store_counts = []
        
        for store in stores:
            try:
                doc_counts = file_search_client.list_documents(store.name)
                display_name = getattr(store, "display_name", "Unknown")
                
                all_store_counts.append({
                    "store_name": store.name,
                    "display_name": display_name,
                    "counts": doc_counts,
                })
                    
            except Exception as e:
                if json_output:
                    all_store_counts.append({
                        "store_name": store.name,
                        "error": str(e)
                    })
                else:
                    typer.echo(f"Error getting documents from {store.name}: {e}", err=True)
        
        if json_output:
            typer.echo(json.dumps(all_store_counts, indent=2))
            return
        
        if not all_store_counts:
            typer.echo("No stores found.")
            return
        
        typer.echo("\nNote: The File Search API does not support listing individual documents.")
        typer.echo("Showing document counts per store instead.\n")
        
        total_active = 0
        total_pending = 0
        total_failed = 0
        
        for item in all_store_counts:
            if "error" in item:
                typer.echo(f"✗ {item['store_name']}")
                typer.echo(f"  Error: {item['error']}\n")
                continue
            
            counts = item["counts"]
            display_name = item["display_name"]
            
            typer.echo(f"Store: {item['store_name']} ({display_name})")
            typer.echo("━" * 70)
            
            if counts["active"] > 0:
                typer.echo(f"  ✓ Active (ready):  {counts['active']} document{'s' if counts['active'] != 1 else ''}")
            
            if counts["pending"] > 0:
                typer.echo(f"  ⏳ Pending:        {counts['pending']} document{'s' if counts['pending'] != 1 else ''}")
            
            if counts["failed"] > 0:
                typer.echo(f"  ✗ Failed:         {counts['failed']} document{'s' if counts['failed'] != 1 else ''}")
            
            if counts["total"] == 0:
                typer.echo("  (No documents)")
            
            typer.echo(f"  Total:           {counts['total']} document{'s' if counts['total'] != 1 else ''}")
            typer.echo()
            
            total_active += counts["active"]
            total_pending += counts["pending"]
            total_failed += counts["failed"]
        
        if len(all_store_counts) > 1:
            total = total_active + total_pending + total_failed
            typer.echo(f"Summary: {total} total documents across {len(all_store_counts)} stores")
            typer.echo(f"  ✓ {total_active} active, ⏳ {total_pending} pending, ✗ {total_failed} failed")
        
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        typer.echo("\nMake sure GOOGLE_API_KEY environment variable is set.", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error listing documents: {e}", err=True)
        raise typer.Exit(1)


@app.command("health-check")
def health_check(
    store_name: str = typer.Argument(None, help="File Search store name (checks default store if omitted)"),
    all_stores: bool = typer.Option(False, "--all", "-a", help="Check all stores"),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
) -> None:
    """Check health of File Search stores."""
    try:
        if store_name:
            stores = [type("Store", (), {"name": store_name, "display_name": None})()]
        elif all_stores:
            stores = file_search_client.list_stores()
            if not stores:
                typer.echo("No File Search stores found.")
                return
        else:
            all_stores_list = file_search_client.list_stores()
            stores = []
            for store in all_stores_list:
                display_name = getattr(store, "display_name", "")
                if display_name == file_search_client.GLOBAL_STORE_NAME:
                    stores.append(store)
                    break
            
            if not stores:
                typer.echo(f"Default store '{file_search_client.GLOBAL_STORE_NAME}' not found.")
                typer.echo("Use --all to check all stores, or specify a store name.")
                raise typer.Exit(1)
        
        all_results = []
        
        for store in stores:
            try:
                health = file_search_client.health_check(store.name)
                health["store_name"] = store.name
                health["display_name"] = getattr(store, "display_name", None)
                all_results.append(health)
            except Exception as e:
                all_results.append({
                    "store_name": store.name,
                    "display_name": getattr(store, "display_name", None),
                    "status": "error",
                    "error": str(e)
                })
        
        if json_output:
            typer.echo(json.dumps(all_results, indent=2))
            return
        
        if len(all_results) == 1:
            result = all_results[0]
            display_name = result.get("display_name") or "Unknown"
            
            typer.echo(f"\nHealth Check: {result['store_name']} ({display_name})")
            typer.echo("━" * 70)
            typer.echo()
            
            if "error" in result:
                typer.echo(f"✗ Error: {result['error']}")
                raise typer.Exit(1)
            
            typer.echo(f"{'✓' if result['accessible'] else '✗'} Store accessible")
            
            if result["document_count"] > 0:
                typer.echo(f"✓ Documents loaded ({result['document_count']} documents)")
            else:
                typer.echo("✗ No documents loaded")
            
            typer.echo(f"{'✓' if result['all_processed'] else '✗'} All documents processed")
            
            if result["query_test_passed"]:
                typer.echo("✓ Query test passed")
            else:
                typer.echo("✗ Query test failed")
            
            if result["response_time"]:
                if result["response_time"] < 5.0:
                    typer.echo(f"✓ Response time OK ({result['response_time']:.2f}s)")
                else:
                    typer.echo(f"⚠ Response time slow ({result['response_time']:.2f}s)")
            
            typer.echo()
            
            status = result["status"].upper()
            if status == "HEALTHY":
                typer.echo("Overall Status: HEALTHY ✓")
            elif status == "WARNING":
                typer.echo("Overall Status: WARNING ⚠")
            else:
                typer.echo("Overall Status: ERROR ✗")
            
            if result["issues"]:
                typer.echo("\nIssues:")
                for issue in result["issues"]:
                    typer.echo(f"  • {issue}")
            
            if status != "HEALTHY":
                raise typer.Exit(1)
            
        else:
            typer.echo("\nHealth Check: All Stores")
            typer.echo("━" * 70)
            typer.echo()
            
            healthy_count = 0
            
            for result in all_results:
                display_name = result.get("display_name") or "Unknown"
                status = result["status"].upper()
                
                if "error" in result:
                    typer.echo(f"✗ {result['store_name']} ({display_name})")
                    typer.echo(f"  ERROR - {result['error']}")
                elif status == "HEALTHY":
                    typer.echo(f"✓ {result['store_name']} ({display_name})")
                    typer.echo("  HEALTHY")
                    healthy_count += 1
                elif status == "WARNING":
                    typer.echo(f"⚠ {result['store_name']} ({display_name})")
                    typer.echo("  WARNING")
                    if result["issues"]:
                        for issue in result["issues"]:
                            typer.echo(f"    • {issue}")
                else:
                    typer.echo(f"✗ {result['store_name']} ({display_name})")
                    typer.echo("  ERROR")
                    if result["issues"]:
                        for issue in result["issues"]:
                            typer.echo(f"    • {issue}")
                
                typer.echo()
            
            typer.echo(f"Summary: {healthy_count}/{len(all_results)} stores healthy")
            
            if healthy_count != len(all_results):
                raise typer.Exit(1)
        
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        typer.echo("\nMake sure GOOGLE_API_KEY environment variable is set.", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error during health check: {e}", err=True)
        raise typer.Exit(1)

