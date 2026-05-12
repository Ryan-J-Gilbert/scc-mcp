"""
BU SCC MCP server (stdio).

Environment:

- ``SCC_RESOURCES_DIR``: directory to scan for ``*.yaml`` / ``*.md`` resources
  (default: ``<this_dir>/resources``).
- ``SCC_CHROMA_PATH``: Chroma persistence path (default: ``<this_dir>/data/chroma``).
- ``SCC_CHROMA_COLLECTION``: documentation collection name (default: ``scc_documentation``, TechWeb scrape).
- ``SCC_SEARCH_DOCS_MAX_CHARS_PER_HIT``: default body length cap per search hit (default ``8000``; ``0`` = unlimited).
- ``SCC_LOG_LEVEL``: Python logging level for this process (default: ``WARNING``).

Run (from ``mcp-scc/``):

.. code-block:: bash

   uv run python server.py

Cursor MCP config example (stdio):

.. code-block:: json

   {"mcpServers": {"bu-scc": {"command": "uv", "args": ["run", "--directory", "/ABS/PATH/mcp-scc", "python", "server.py"]}}}
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import mcp.server.stdio
import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.lowlevel.helper_types import ReadResourceContents
from pydantic import AnyUrl

from prompts.templates import get_prompt_result, list_prompt_definitions
from resource_loader import ResourceRegistry, default_resources_dir
from tools.search_docs import search_docs


def _resources_path() -> Path:
    return Path(os.environ.get("SCC_RESOURCES_DIR", str(default_resources_dir())))


REGISTRY = ResourceRegistry.load(_resources_path())

server = Server(
    "bu-scc",
    version="0.1.0",
    instructions=(
        "Boston University Shared Computing Cluster (SCC) helper: static resources for "
        "Sun Grid Engine (qsub, #$ directives), modules, scratch/storage, and parallel environments; "
        "search_docs runs semantic search over ingested BU TechWeb SCC documentation in ChromaDB; "
        "prompts draft SGE batch scripts (CPU, GPU, array) consistent with those pages."
    ),
)


@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    return [e.as_mcp_resource() for e in REGISTRY.list_entries()]


@server.read_resource()
async def handle_read_resource(uri: AnyUrl) -> list[ReadResourceContents]:
    key = str(uri)
    try:
        text, mime = REGISTRY.read(key)
    except KeyError as exc:
        raise ValueError(f"Resource not found: {key}") from exc
    return [ReadResourceContents(content=text, mime_type=mime)]


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="search_docs",
            description=(
                "Semantic search over ingested BU TechWeb SCC documentation in ChromaDB "
                "(batch submission, PEs, MPI, GPUs, scratch, modules, etc.). "
                "Each hit is a full article (not a small chunk); keep top_k low (1–3) unless you need breadth. "
                "Long articles are truncated per max_chars_per_hit to limit tokens."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language or keyword query.",
                    },
                    "top_k": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 12,
                        "default": 3,
                        "description": "Number of matching articles to return (each hit can be large).",
                    },
                    "max_chars_per_hit": {
                        "type": "integer",
                        "minimum": 0,
                        "default": 8000,
                        "description": (
                            "Max characters of article body per hit; metadata is always included. "
                            "Use 0 for no truncation (high token use). Omit to use env default."
                        ),
                    },
                },
                "required": ["query"],
            },
        )
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    if name != "search_docs":
        raise ValueError(f"Unknown tool: {name}")
    args = arguments or {}
    query = args.get("query")
    if not query or not isinstance(query, str):
        raise ValueError("Missing or invalid required parameter: query (string)")
    raw_top = args.get("top_k", 3)
    try:
        top_k_int = int(raw_top)
    except (TypeError, ValueError) as exc:
        raise ValueError("top_k must be an integer") from exc
    raw_cap = args.get("max_chars_per_hit")
    max_chars: int | None
    if raw_cap is None:
        max_chars = None
    else:
        try:
            max_chars = int(raw_cap)
        except (TypeError, ValueError) as exc:
            raise ValueError("max_chars_per_hit must be an integer") from exc
    text = search_docs(query, top_k=top_k_int, max_chars_per_hit=max_chars)
    return [types.TextContent(type="text", text=text)]


@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    return list_prompt_definitions()


@server.get_prompt()
async def handle_get_prompt(name: str, arguments: dict[str, str] | None) -> types.GetPromptResult:
    return get_prompt_result(name, arguments)


async def _run() -> None:
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(
                notification_options=NotificationOptions(),
                experimental_capabilities={},
            ),
        )


def main() -> None:
    logging.basicConfig(level=os.environ.get("SCC_LOG_LEVEL", "WARNING"))
    asyncio.run(_run())


if __name__ == "__main__":
    main()
