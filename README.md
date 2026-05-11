# mcp-scc

MCP server for Boston University Shared Computing Cluster (SCC): file-backed **resources**, ChromaDB **search_docs**, and Slurm **prompts**.

## Setup

```bash
cd mcp-scc
uv sync
```

Place your populated Chroma persistence under `data/chroma/` (or set `SCC_CHROMA_PATH`). The default collection name is `scc_docs`; override with `SCC_CHROMA_COLLECTION` if your ingest used a different name.

## Environment

| Variable | Purpose |
|----------|---------|
| `SCC_RESOURCES_DIR` | Root scanned for `resources/**/*.yaml` and `resources/**/*.md` (default: `./resources`). |
| `SCC_CHROMA_PATH` | Chroma persistence directory (default: `./data/chroma`). |
| `SCC_CHROMA_COLLECTION` | Collection name for documentation chunks (default: `scc_docs`). |
| `SCC_LOG_LEVEL` | Python log level (default: `WARNING`). |

## Run (stdio)

```bash
uv run python server.py
```

### Cursor MCP example

```json
{
  "mcpServers": {
    "bu-scc": {
      "command": "uv",
      "args": ["run", "--directory", "/ABSOLUTE/PATH/TO/mcp-scc", "python", "server.py"]
    }
  }
}
```

Replace `/ABSOLUTE/PATH/TO/mcp-scc` with the real path to this directory.
