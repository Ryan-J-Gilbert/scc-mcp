"""Semantic search over ingested SCC documentation in ChromaDB."""

from __future__ import annotations

import os
from pathlib import Path

import chromadb


def _default_max_chars_per_hit() -> int:
    raw = os.environ.get("SCC_SEARCH_DOCS_MAX_CHARS_PER_HIT", "4000").strip()
    if not raw:
        return 8000
    try:
        n = int(raw)
    except ValueError:
        return 8000
    return max(0, n)


def _truncate_document(text: str, max_chars: int) -> str:
    """Cap body size; each ingested doc is a full article, so limits dominate token use."""
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    omitted = len(text) - max_chars
    return text[:max_chars].rstrip() + f"\n\n...[truncated, {omitted} characters omitted]"


def search_docs(
    query: str,
    *,
    chroma_path: str | None = None,
    collection_name: str | None = None,
    top_k: int = 3,
    max_chars_per_hit: int | None = None,
) -> str:
    """
    Run a similarity search against the TechWeb-derived documentation collection (SGE / SCC operations).

    Environment (optional overrides):

    - ``SCC_CHROMA_PATH``: persistence directory (default: ``<mcp-scc>/data/chroma``).
    - ``SCC_CHROMA_COLLECTION``: collection name (default: ``scc_documentation``, populated by ``scripts/scrape_and_ingest_techweb.py``).
    - ``SCC_SEARCH_DOCS_MAX_CHARS_PER_HIT``: default character cap per hit when ``max_chars_per_hit`` is omitted (``0`` = unlimited).
    """
    base = Path(__file__).resolve().parent.parent
    path = Path(chroma_path or os.environ.get("SCC_CHROMA_PATH", str(base / "data" / "chroma")))
    name = collection_name or os.environ.get("SCC_CHROMA_COLLECTION", "scc_documentation")
    top_k = max(1, min(int(top_k), 12))
    if max_chars_per_hit is None:
        max_chars_per_hit = _default_max_chars_per_hit()
    else:
        max_chars_per_hit = int(max_chars_per_hit)

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

    cap_note = (
        f" | max_chars_per_hit={max_chars_per_hit}"
        if max_chars_per_hit > 0
        else " | max_chars_per_hit=unlimited"
    )
    lines.append(f"Collection: {name!r} | query: {query!r} | top_k={top_k}{cap_note}\n")
    for i, rid in enumerate(row_ids):
        dist = row_dists[i] if i < len(row_dists) else None
        meta = row_metas[i] if i < len(row_metas) else None
        doc = row_docs[i] if i < len(row_docs) else None
        lines.append(f"--- hit {i + 1} | id={rid} | distance={dist}")
        if meta:
            lines.append(f"metadata: {meta}")
        if doc:
            body = doc.strip()
            if max_chars_per_hit > 0:
                body = _truncate_document(body, max_chars_per_hit)
            lines.append(body)
        lines.append("")
    return "\n".join(lines).rstrip()
