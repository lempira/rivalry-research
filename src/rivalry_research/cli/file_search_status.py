"""CLI commands for File Search status monitoring."""

import argparse
import json
import sys
from datetime import datetime
from typing import Any

from ..rag import file_search_client


def format_timestamp(timestamp: Any) -> str:
    """Format timestamp for display."""
    if timestamp is None:
        return "N/A"
    
    # Handle various timestamp formats
    if isinstance(timestamp, str):
        try:
            # Try parsing ISO format
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, AttributeError):
            return timestamp
    
    return str(timestamp)


def format_size(size_bytes: int | None) -> str:
    """Format file size in human-readable format."""
    if size_bytes is None:
        return "N/A"
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def cmd_list_stores(args: argparse.Namespace) -> int:
    """List all File Search stores."""
    try:
        stores = file_search_client.list_stores()
        
        if args.json:
            # JSON output
            output = []
            for store in stores:
                store_data = {
                    "name": store.name,
                    "display_name": getattr(store, 'display_name', None),
                    "create_time": getattr(store, 'create_time', None),
                }
                output.append(store_data)
            print(json.dumps(output, indent=2))
            return 0
        
        # Human-readable output
        if not stores:
            print("No File Search stores found.")
            return 0
        
        print("\nFile Search Stores:")
        print("━" * 70)
        
        for store in stores:
            display_name = getattr(store, 'display_name', 'N/A')
            create_time = getattr(store, 'create_time', None)
            
            print(f"✓ {store.name}")
            print(f"  Name: {display_name}")
            print(f"  Created: {format_timestamp(create_time)}")
            
            # Try to get document count
            if args.verbose:
                try:
                    docs = file_search_client.list_documents(store.name)
                    print(f"  Documents: {len(docs)}")
                except Exception as e:
                    print(f"  Documents: Error ({e})")
            
            print()
        
        print(f"Total: {len(stores)} store{'s' if len(stores) != 1 else ''}")
        return 0
        
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("\nMake sure GOOGLE_API_KEY environment variable is set.", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error listing stores: {e}", file=sys.stderr)
        return 1


def cmd_list_docs(args: argparse.Namespace) -> int:
    """List documents in File Search stores."""
    try:
        # If no store specified, list docs from all stores
        if args.store_name:
            stores = [type('Store', (), {'name': args.store_name})()]
        else:
            stores = file_search_client.list_stores()
            if not stores:
                print("No File Search stores found.")
                return 0
        
        all_docs = []
        
        for store in stores:
            try:
                docs = file_search_client.list_documents(store.name)
                
                # Apply limit if specified
                if args.limit:
                    docs = docs[:args.limit]
                
                for doc in docs:
                    doc_data = {
                        'store_name': store.name,
                        'doc': doc
                    }
                    all_docs.append(doc_data)
                    
            except Exception as e:
                if args.json:
                    all_docs.append({
                        'store_name': store.name,
                        'error': str(e)
                    })
                else:
                    print(f"Error listing documents from {store.name}: {e}", file=sys.stderr)
        
        if args.json:
            # JSON output
            output = []
            for item in all_docs:
                if 'error' in item:
                    output.append(item)
                else:
                    doc = item['doc']
                    doc_data = {
                        "store_name": item['store_name'],
                        "name": doc.name,
                        "display_name": getattr(doc, 'display_name', None),
                        "create_time": getattr(doc, 'create_time', None),
                        "state": getattr(doc, 'state', None),
                    }
                    output.append(doc_data)
            print(json.dumps(output, indent=2))
            return 0
        
        # Human-readable output
        if not all_docs:
            print("No documents found.")
            return 0
        
        # Group by store
        current_store = None
        total_count = 0
        ready_count = 0
        
        for item in all_docs:
            if 'error' in item:
                continue
                
            doc = item['doc']
            
            # Print store header if changed
            if current_store != item['store_name']:
                if current_store is not None:
                    print()
                current_store = item['store_name']
                
                # Get store display name if possible
                display_name = "Unknown"
                try:
                    all_stores = file_search_client.list_stores()
                    for s in all_stores:
                        if s.name == current_store:
                            display_name = getattr(s, 'display_name', 'Unknown')
                            break
                except:
                    pass
                
                print(f"\nDocuments in {current_store} ({display_name}):")
                print("━" * 70)
            
            # Document details
            display_name = getattr(doc, 'display_name', 'N/A')
            create_time = getattr(doc, 'create_time', None)
            state = getattr(doc, 'state', 'ACTIVE')
            
            # Status icon
            if state == 'ACTIVE':
                icon = "✓"
                ready_count += 1
            elif state == 'PROCESSING':
                icon = "⏳"
            else:
                icon = "✗"
            
            print(f"{icon} {display_name}")
            print(f"  ID: {doc.name}")
            print(f"  Uploaded: {format_timestamp(create_time)}")
            print(f"  Status: {state.lower()}")
            
            total_count += 1
            print()
        
        print(f"Total: {total_count} document{'s' if total_count != 1 else ''}", end='')
        if total_count > ready_count:
            print(f" ({ready_count} ready, {total_count - ready_count} processing)")
        else:
            print()
        
        return 0
        
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("\nMake sure GOOGLE_API_KEY environment variable is set.", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error listing documents: {e}", file=sys.stderr)
        return 1


def cmd_health_check(args: argparse.Namespace) -> int:
    """Check health of File Search stores."""
    try:
        # Determine which stores to check
        if args.store_name:
            # Specific store
            stores = [type('Store', (), {'name': args.store_name, 'display_name': None})()]
        elif args.all:
            # All stores
            stores = file_search_client.list_stores()
            if not stores:
                print("No File Search stores found.")
                return 0
        else:
            # Default: look for the global store
            all_stores = file_search_client.list_stores()
            stores = []
            for store in all_stores:
                display_name = getattr(store, 'display_name', '')
                if display_name == file_search_client.GLOBAL_STORE_NAME:
                    stores.append(store)
                    break
            
            if not stores:
                print(f"Default store '{file_search_client.GLOBAL_STORE_NAME}' not found.")
                print("Use --all to check all stores, or specify a store name.")
                return 1
        
        all_results = []
        
        for store in stores:
            try:
                health = file_search_client.health_check(store.name)
                health['store_name'] = store.name
                health['display_name'] = getattr(store, 'display_name', None)
                all_results.append(health)
            except Exception as e:
                all_results.append({
                    'store_name': store.name,
                    'display_name': getattr(store, 'display_name', None),
                    'status': 'error',
                    'error': str(e)
                })
        
        if args.json:
            # JSON output
            print(json.dumps(all_results, indent=2))
            return 0
        
        # Human-readable output
        if len(all_results) == 1:
            # Single store - detailed output
            result = all_results[0]
            display_name = result.get('display_name') or 'Unknown'
            
            print(f"\nHealth Check: {result['store_name']} ({display_name})")
            print("━" * 70)
            print()
            
            if 'error' in result:
                print(f"✗ Error: {result['error']}")
                return 1
            
            # Status checks
            print(f"{'✓' if result['accessible'] else '✗'} Store accessible")
            
            if result['document_count'] > 0:
                print(f"✓ Documents loaded ({result['document_count']} documents)")
            else:
                print(f"✗ No documents loaded")
            
            print(f"{'✓' if result['all_processed'] else '✗'} All documents processed")
            
            if result['query_test_passed']:
                print(f"✓ Query test passed")
            else:
                print(f"✗ Query test failed")
            
            if result['response_time']:
                if result['response_time'] < 5.0:
                    print(f"✓ Response time OK ({result['response_time']:.2f}s)")
                else:
                    print(f"⚠ Response time slow ({result['response_time']:.2f}s)")
            
            print()
            
            # Overall status
            status = result['status'].upper()
            if status == 'HEALTHY':
                print(f"Overall Status: HEALTHY ✓")
                return 0
            elif status == 'WARNING':
                print(f"Overall Status: WARNING ⚠")
            else:
                print(f"Overall Status: ERROR ✗")
            
            # Issues
            if result['issues']:
                print("\nIssues:")
                for issue in result['issues']:
                    print(f"  • {issue}")
            
            return 0 if status == 'HEALTHY' else 1
            
        else:
            # Multiple stores - summary output
            print("\nHealth Check: All Stores")
            print("━" * 70)
            print()
            
            healthy_count = 0
            
            for result in all_results:
                display_name = result.get('display_name') or 'Unknown'
                status = result['status'].upper()
                
                if 'error' in result:
                    print(f"✗ {result['store_name']} ({display_name})")
                    print(f"  ERROR - {result['error']}")
                elif status == 'HEALTHY':
                    print(f"✓ {result['store_name']} ({display_name})")
                    print(f"  HEALTHY")
                    healthy_count += 1
                elif status == 'WARNING':
                    print(f"⚠ {result['store_name']} ({display_name})")
                    print(f"  WARNING")
                    if result['issues']:
                        for issue in result['issues']:
                            print(f"    • {issue}")
                else:
                    print(f"✗ {result['store_name']} ({display_name})")
                    print(f"  ERROR")
                    if result['issues']:
                        for issue in result['issues']:
                            print(f"    • {issue}")
                
                print()
            
            print(f"Summary: {healthy_count}/{len(all_results)} stores healthy")
            
            return 0 if healthy_count == len(all_results) else 1
        
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("\nMake sure GOOGLE_API_KEY environment variable is set.", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error during health check: {e}", file=sys.stderr)
        return 1


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog='rivalry-fs',
        description='File Search status monitoring for rivalry research',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    subparsers.required = True
    
    # list-stores command
    parser_list_stores = subparsers.add_parser(
        'list-stores',
        help='List all File Search stores'
    )
    parser_list_stores.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed information including document counts'
    )
    parser_list_stores.add_argument(
        '--json',
        action='store_true',
        help='Output in JSON format'
    )
    parser_list_stores.set_defaults(func=cmd_list_stores)
    
    # list-docs command
    parser_list_docs = subparsers.add_parser(
        'list-docs',
        help='List documents in File Search stores'
    )
    parser_list_docs.add_argument(
        'store_name',
        nargs='?',
        help='File Search store name (lists all stores if omitted)'
    )
    parser_list_docs.add_argument(
        '--limit', '-l',
        type=int,
        help='Limit number of documents shown'
    )
    parser_list_docs.add_argument(
        '--json',
        action='store_true',
        help='Output in JSON format'
    )
    parser_list_docs.set_defaults(func=cmd_list_docs)
    
    # health-check command
    parser_health = subparsers.add_parser(
        'health-check',
        help='Check health of File Search stores'
    )
    parser_health.add_argument(
        'store_name',
        nargs='?',
        help='File Search store name (checks default store if omitted)'
    )
    parser_health.add_argument(
        '--all', '-a',
        action='store_true',
        help='Check all stores'
    )
    parser_health.add_argument(
        '--json',
        action='store_true',
        help='Output in JSON format'
    )
    parser_health.set_defaults(func=cmd_health_check)
    
    # Parse and execute
    args = parser.parse_args()
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())

