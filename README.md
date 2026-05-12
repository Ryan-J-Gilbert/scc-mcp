# mcp-scc

MCP server for Boston University Shared Computing Cluster (SCC): file-backed **resources**, ChromaDB **search_docs** over ingested TechWeb pages, and **prompts** for SGE / **qsub** batch scripts.

## Setup

```bash
cd mcp-scc
uv sync
```

## Scrape TechWeb and ingest Chroma

One script replaces separate scrape + ingest steps (no spreadsheet / Q&A Excel path):

```bash
uv sync --extra ingest
# Full pipeline (writes markdown under data/scraped_techweb, vectors under data/chroma)
uv run --extra ingest python scripts/scrape_and_ingest_techweb.py

# Scrape only, or ingest only from an existing markdown directory
uv run --extra ingest python scripts/scrape_and_ingest_techweb.py --scrape-only
uv run --extra ingest python scripts/scrape_and_ingest_techweb.py --ingest-only --output-dir ./data/scraped_techweb

# Drop and recreate the collection before upserting (clean rebuild)
uv run --extra ingest python scripts/scrape_and_ingest_techweb.py --recreate-collection
```

Defaults: `--base-url` `https://www.bu.edu/tech/support/research/`, `--output-dir` `./data/scraped_techweb`, `--db-path` `./data/chroma`, `--collection` `scc_documentation`.

If you already have vectors in a differently named collection (for example `scc_docs`), either set `SCC_CHROMA_COLLECTION` to that name for the MCP server or re-ingest with this script’s defaults and `--recreate-collection` so `search_docs` matches without extra env vars.

Place your populated Chroma persistence under `data/chroma/` (or set `SCC_CHROMA_PATH`). The default collection name is `scc_documentation` (written by `scripts/scrape_and_ingest_techweb.py`); override with `SCC_CHROMA_COLLECTION` if you use another name.

## Environment

| Variable | Purpose |
|----------|---------|
| `SCC_RESOURCES_DIR` | Root scanned for `resources/**/*.yaml` and `resources/**/*.md` (default: `./resources`). |
| `SCC_CHROMA_PATH` | Chroma persistence directory (default: `./data/chroma`). |
| `SCC_CHROMA_COLLECTION` | Collection name for documentation chunks (default: `scc_documentation`). |
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
