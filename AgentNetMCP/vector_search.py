#!/usr/bin/env python3
"""
Vector search module for AgentNet MCP server.
This module provides semantic search capabilities using Chroma vector store.
"""

import os
import sys
import json
import argparse
from pathlib import Path

# Add the parent directory to the path so we can import from main.py
sys.path.append(str(Path(__file__).parent.parent))

try:
    from main import get_vectorstore, build_reason, _metadata_to_list, _format_capabilities
except ImportError:
    print("Error: Could not import from main.py. Make sure you're running from the correct directory.")
    sys.exit(1)

def semantic_search(query, k=3):
    """
    Perform semantic search using Chroma vector store.
    
    Args:
        query (str): The search query
        k (int): Number of results to return
        
    Returns:
        list: List of search results with metadata
    """
    try:
        vectorstore = get_vectorstore()
        results = vectorstore.similarity_search_with_score(query, k=k)
        
        formatted_results = []
        for doc, score in results:
            metadata = doc.metadata or {}
            similarity = max(0.0, min(1.0, 1.0 - float(score)))
            
            # Build reason for match
            caps_list = _metadata_to_list(metadata.get("capabilities", []))
            tags_list = _metadata_to_list(metadata.get("tags", []))
            reason = build_reason(query, {
                "name": metadata.get("name", ""),
                "description": doc.page_content,
                "capabilities": caps_list,
                "tags": tags_list,
            })
            
            result = {
                "id": metadata.get("id", ""),
                "name": metadata.get("name", ""),
                "description": doc.page_content,
                "provider": metadata.get("provider", ""),
                "endpoint": metadata.get("endpoint", ""),
                "capabilities": caps_list,
                "tags": tags_list,
                "similarity_score": similarity,
                "reason": reason
            }
            formatted_results.append(result)
        
        return formatted_results
        
    except Exception as e:
        print(f"Error during semantic search: {e}", file=sys.stderr)
        return []

def main():
    parser = argparse.ArgumentParser(description="Semantic search for AgentNet")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--k", type=int, default=3, help="Number of results to return")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    results = semantic_search(args.query, args.k)
    
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        if not results:
            print("No results found.")
            return
        
        for index, result in enumerate(results, start=1):
            similarity = result["similarity_score"]
            name = result["name"]
            provider = result["provider"]
            agent_id = result["id"]
            endpoint = result["endpoint"]
            caps_list = result["capabilities"]
            reason = result["reason"]
            
            print(f"[{index}] {name} — {provider}  score={similarity:.3f}  (id={agent_id})")
            print(f"    {reason}")
            if endpoint:
                print(f"    endpoint: {endpoint}")
            caps_line = _format_capabilities(caps_list)
            print(f"    {caps_line}")
            print()

if __name__ == "__main__":
    main()

