"""
Scrape BU TechWeb SCC documentation and ingest markdown into ChromaDB.

Combines the workflows from ``scrape_techweb.py`` and ``ingest_docs_chromadb.py``
(without spreadsheet / Q&A Excel ingestion).

Run from the ``mcp-scc`` directory with ingest extras installed::

    uv sync --extra ingest
    uv run --extra ingest python scripts/scrape_and_ingest_techweb.py

Or scrape / ingest separately::

    uv run --extra ingest python scripts/scrape_and_ingest_techweb.py --scrape-only
    uv run --extra ingest python scripts/scrape_and_ingest_techweb.py --ingest-only
"""

from __future__ import annotations

import argparse
import io
import logging
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urldefrag, urljoin

import chromadb
import requests
from bs4 import BeautifulSoup
from chromadb.config import Settings
from markitdown import MarkItDown, StreamInfo
from tqdm import tqdm

logger = logging.getLogger(__name__)

SKIP_ARTICLES = frozenset(
    {"https://www.bu.edu/tech/support/research/whats-happening/updates/"}
)

DEFAULT_BASE_URL = "https://www.bu.edu/tech/support/research/"
DEFAULT_COLLECTION = "scc_documentation"


def crawl_key(url: str) -> str:
    base, _frag = urldefrag(url)
    return base


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _sanitize_metadata(meta: dict[str, Any]) -> dict[str, str | int | float | bool]:
    out: dict[str, str | int | float | bool] = {}
    for key, val in meta.items():
        if val is None:
            continue
        if isinstance(val, (str, int, float, bool)):
            out[key] = val
        else:
            out[key] = str(val)
    return out


class BUResearchScraper:
    """Scrape BU Tech research support pages to markdown (from ``scrape_techweb.py``)."""

    def __init__(self, base_url: str, output_dir: str | Path, request_delay: float = 0.1):
        self.base_url = base_url
        self.output_dir = Path(output_dir)
        self.request_delay = request_delay
        self.visited_urls: set[str] = {crawl_key(u) for u in SKIP_ARTICLES}
        self._markitdown = MarkItDown()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def clean_filename(filename: str) -> str:
        filename = re.sub(r'[\\/*?:"<>|]', "_", filename)
        return filename[:100] if len(filename) > 100 else filename

    def get_soup(self, url: str) -> BeautifulSoup | None:
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except requests.exceptions.RequestException as e:
            logger.warning("Error fetching %s: %s", url, e)
            return None

    def extract_article_content(self, article_url: str) -> dict[str, str] | None:
        logger.info("Extracting: %s", article_url)
        soup = self.get_soup(article_url)
        if not soup:
            return None

        title_elem = soup.find("div", class_="page-title")
        if title_elem and title_elem.find("h1", class_="title"):
            title = title_elem.find("h1", class_="title").text.strip()
        else:
            h1 = soup.find("h1")
            title = h1.text.strip() if h1 else "Untitled Article"

        content_div = soup.find("div", class_="entry")
        if not content_div:
            content_div = soup.find("section", {"role": "main"})
        if not content_div:
            content_div = soup.find("div", class_="content")
        if not content_div:
            logger.warning("Could not find content in %s", article_url)
            return None

        html_fragment = str(content_div)
        html_bytes = io.BytesIO(html_fragment.encode("utf-8"))
        stream_info = StreamInfo(extension=".html", mimetype="text/html", charset="utf-8")
        try:
            result = self._markitdown.convert_stream(html_bytes, stream_info=stream_info)
        except Exception as e:
            logger.warning("MarkItDown conversion failed for %s: %s", article_url, e)
            return None

        body = (
            (getattr(result, "markdown", None) or getattr(result, "text_content", None) or "")
        ).strip()
        if not body:
            logger.warning("MarkItDown produced empty markdown for %s", article_url)
            return None

        markdown_content = f"# {title}\n\n{body}"
        return {"title": title, "content": markdown_content, "url": article_url}

    def save_article(self, article_data: dict[str, str] | None) -> None:
        if not article_data:
            return
        filename = self.clean_filename(article_data["title"])
        filepath = self.output_dir / f"{filename}.md"
        filepath.write_text(
            article_data["content"] + f"\n\nSource: {article_data['url']}",
            encoding="utf-8",
        )
        logger.info("Saved: %s", filepath)

    def extract_links_from_support_rows(self, soup: BeautifulSoup) -> list[str]:
        links: list[str] = []
        for link in soup.find_all("a"):
            href = link.get("href")
            if href and href.startswith("https://www.bu.edu/tech/support/research/"):
                full_url = urljoin(self.base_url, href)
                links.append(crawl_key(full_url))
        return list(dict.fromkeys(links))

    def scrape_recursively(self, url: str, depth: int = 1, max_depth: int = 10) -> None:
        canonical = crawl_key(url)
        if depth > max_depth or canonical in self.visited_urls:
            return

        self.visited_urls.add(canonical)
        logger.info("Visiting: %s (depth %s)", canonical, depth)

        soup = self.get_soup(canonical)
        if not soup:
            return

        if soup.find("div", class_="page-title") or soup.find("div", class_="entry"):
            article_data = self.extract_article_content(canonical)
            if article_data:
                self.save_article(article_data)

        for link in self.extract_links_from_support_rows(soup):
            next_key = crawl_key(link)
            if next_key not in self.visited_urls:
                time.sleep(self.request_delay)
                self.scrape_recursively(next_key, depth + 1, max_depth)

    def start_scraping(self) -> None:
        logger.info("Starting scrape from %s", self.base_url)
        self.scrape_recursively(self.base_url)
        logger.info("Scraping complete. Content saved to %s/", self.output_dir)


def load_markdown_articles(scraped_content_dir: Path) -> tuple[list[str], list[dict[str, str]], list[str]]:
    """Load ``*.md`` articles (adapted from ``ingest_docs_chromadb.py``)."""
    if not scraped_content_dir.is_dir():
        logger.error("Scraped content directory not found: %s", scraped_content_dir)
        return [], [], []

    documents: list[str] = []
    metadatas: list[dict[str, str]] = []
    ids: list[str] = []

    markdown_files = sorted(scraped_content_dir.glob("*.md"))
    logger.info("Found %s markdown files", len(markdown_files))

    for filepath in tqdm(markdown_files, desc="Loading markdown"):
        try:
            content = filepath.read_text(encoding="utf-8")
            title = filepath.stem
            lines = content.split("\n")
            if lines and lines[0].startswith("# "):
                title = lines[0].replace("# ", "").strip()

            source_url: str | None = None
            for line in reversed(lines):
                if line.startswith("Source:"):
                    source_url = line.replace("Source:", "").strip()
                    break

            documents.append(content)
            metadatas.append(
                {
                    "source": source_url or str(filepath),
                    "doc_type": "article",
                    "title": title,
                    "filename": filepath.name,
                }
            )
            ids.append(f"article_{filepath.stem}")
        except Exception as e:
            logger.error("Error loading %s: %s", filepath, e)

    logger.info("Loaded %s articles", len(documents))
    return documents, metadatas, ids


def ingest_markdown_batches(
    db_path: Path,
    collection_name: str,
    scraped_content_dir: Path,
    *,
    batch_size: int = 100,
    recreate_collection: bool = False,
) -> int:
    """Upsert markdown articles into Chroma. Returns final document count."""
    db_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(db_path),
        settings=Settings(anonymized_telemetry=False),
    )

    if recreate_collection:
        try:
            client.delete_collection(name=collection_name)
            logger.info("Deleted collection %r", collection_name)
        except Exception:
            logger.info("No existing collection %r to delete", collection_name)

    try:
        collection = client.get_collection(name=collection_name)
        logger.info("Using existing collection %r", collection_name)
    except Exception:
        collection = client.create_collection(name=collection_name)
        logger.info("Created collection %r", collection_name)

    documents, metadatas, ids = load_markdown_articles(scraped_content_dir)
    if not documents:
        logger.error("No documents to ingest.")
        return collection.count()

    metas_sanitized = [_sanitize_metadata(m) for m in metadatas]

    total_batches = (len(documents) + batch_size - 1) // batch_size
    logger.info("Ingesting %s documents in %s batches", len(documents), total_batches)

    for i in tqdm(range(0, len(documents), batch_size), desc="Ingesting batches"):
        batch_docs = documents[i : i + batch_size]
        batch_metas = metas_sanitized[i : i + batch_size]
        batch_ids = ids[i : i + batch_size]
        try:
            collection.upsert(documents=batch_docs, metadatas=batch_metas, ids=batch_ids)
        except Exception as e:
            logger.error("Error ingesting batch %s: %s", i // batch_size + 1, e)

    final = collection.count()
    logger.info("Ingestion complete. Collection %r has %s documents.", collection_name, final)
    return final


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    root = _project_root()
    parser = argparse.ArgumentParser(
        description="Scrape BU TechWeb SCC docs and ingest markdown into ChromaDB.",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="TechWeb crawl entry URL")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "data" / "scraped_techweb",
        help="Directory for scraped .md files",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=root / "data" / "chroma",
        help="ChromaDB persistence directory",
    )
    parser.add_argument(
        "--collection",
        default=DEFAULT_COLLECTION,
        help="ChromaDB collection name (match SCC_CHROMA_COLLECTION for the MCP server)",
    )
    parser.add_argument("--batch-size", type=int, default=100, help="Chroma upsert batch size")
    parser.add_argument("--max-depth", type=int, default=10, help="Maximum crawl depth")
    parser.add_argument("--request-delay", type=float, default=0.1, help="Delay between requests (seconds)")
    parser.add_argument("--scrape-only", action="store_true", help="Only scrape; skip Chroma ingest")
    parser.add_argument("--ingest-only", action="store_true", help="Only ingest existing markdown")
    parser.add_argument(
        "--recreate-collection",
        action="store_true",
        help="Delete the collection before ingest (full rebuild of vectors for this collection)",
    )
    args = parser.parse_args()

    if args.scrape_only and args.ingest_only:
        parser.error("Choose at most one of --scrape-only / --ingest-only")

    if not args.ingest_only:
        scraper = BUResearchScraper(
            args.base_url,
            args.output_dir,
            request_delay=args.request_delay,
        )
        scraper.scrape_recursively(args.base_url, depth=1, max_depth=args.max_depth)
        logger.info("Scrape finished.")

    if not args.scrape_only:
        ingest_markdown_batches(
            args.db_path,
            args.collection,
            args.output_dir,
            batch_size=args.batch_size,
            recreate_collection=args.recreate_collection,
        )


if __name__ == "__main__":
    main()
