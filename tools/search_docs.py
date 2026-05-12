"""Semantic search over ingested SCC documentation in ChromaDB."""

from __future__ import annotations

import os
from pathlib import Path

import chromadb


def search_docs(
    query: str,
    *,
    chroma_path: str | None = None,
    collection_name: str | None = None,
    top_k: int = 5,
) -> str:
    """
    Run a similarity search against the TechWeb-derived documentation collection (SGE / SCC operations).

    Environment (optional overrides):

    - ``SCC_CHROMA_PATH``: persistence directory (default: ``<mcp-scc>/data/chroma``).
    - ``SCC_CHROMA_COLLECTION``: collection name (default: ``scc_documentation``, populated by ``scripts/scrape_and_ingest_techweb.py``).
    """
    base = Path(__file__).resolve().parent.parent
    path = Path(chroma_path or os.environ.get("SCC_CHROMA_PATH", str(base / "data" / "chroma")))
    name = collection_name or os.environ.get("SCC_CHROMA_COLLECTION", "scc_documentation")
    top_k = max(1, min(int(top_k), 50))

    if not path.is_dir():
        return (
            f"Chroma persistence directory not found: {path}\n"
            "Populate ``data/chroma`` from your ingest pipeline or set ``SCC_CHROMA_PATH``."
        )

    try:
        client = chromadb.PersistentClient(path=str(path))
        collection = client.get_collection(name)
    except Exception as exc:  # noqa: BLE001 - surface to model as text
        return f"Chroma error ({name} @ {path}): {exc}"

    try:
        results = collection.query(
            query_texts=[query],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as exc:  # noqa: BLE001
        return f"Query failed: {exc}"

    lines: list[str] = []
    ids = results.get("ids") or [[]]
    docs = results.get("documents") or [[]]
    metas = results.get("metadatas") or [[]]
    dists = results.get("distances") or [[]]

    row_ids = ids[0] if ids else []
    row_docs = docs[0] if docs else []
    row_metas = metas[0] if metas else []
    row_dists = dists[0] if dists else []

    if not row_ids:
        lines.append("No hits returned.")
        return "\n".join(lines)

    lines.append(f"Collection: {name!r} | query: {query!r} | top_k={top_k}\n")
    for i, rid in enumerate(row_ids):
        dist = row_dists[i] if i < len(row_dists) else None
        meta = row_metas[i] if i < len(row_metas) else None
        doc = row_docs[i] if i < len(row_docs) else None
        lines.append(f"--- hit {i + 1} | id={rid} | distance={dist}")
        if meta:
            lines.append(f"metadata: {meta}")
        if doc:
            lines.append(doc.strip())
        lines.append("")
    return "\n".join(lines).rstrip()
