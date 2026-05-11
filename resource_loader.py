"""Load MCP resources from YAML and Markdown files under ``resources/``."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mcp.types as types
import yaml
from pydantic import AnyUrl

META_REQUIRED = ("uri", "name", "description", "mime_type")
URI_PREFIX = "scc://"


@dataclass(frozen=True)
class ResourceEntry:
    uri: str
    name: str
    description: str
    mime_type: str
    source_path: Path

    def as_mcp_resource(self) -> types.Resource:
        return types.Resource(
            uri=AnyUrl(self.uri),
            name=self.name,
            description=self.description,
            mimeType=self.mime_type,
        )


class ResourceRegistry:
    def __init__(self, entries: dict[str, ResourceEntry]):
        self._by_uri = entries

    @classmethod
    def load(cls, resources_dir: Path) -> ResourceRegistry:
        if not resources_dir.is_dir():
            raise FileNotFoundError(f"Resources directory not found: {resources_dir}")
        entries: dict[str, ResourceEntry] = {}
        for path in sorted(resources_dir.rglob("*.yaml")):
            entry = _load_yaml_resource(path)
            _register(entries, entry)
        for path in sorted(resources_dir.rglob("*.md")):
            entry = _load_markdown_resource(path)
            _register(entries, entry)
        return cls(entries)

    def list_entries(self) -> list[ResourceEntry]:
        return list(self._by_uri.values())

    def read(self, uri: str) -> tuple[str, str]:
        entry = self._by_uri.get(uri)
        if entry is None:
            raise KeyError(f"Unknown resource URI: {uri}")
        text = _read_body(entry)
        return text, entry.mime_type


def _register(entries: dict[str, ResourceEntry], entry: ResourceEntry) -> None:
    if entry.uri in entries:
        raise ValueError(f"Duplicate resource URI {entry.uri!r} ({entry.source_path})")
    entries[entry.uri] = entry


def _validate_meta(meta: dict[str, Any], source: Path) -> None:
    missing = [k for k in META_REQUIRED if k not in meta or meta[k] in (None, "")]
    if missing:
        raise ValueError(f"{source}: meta missing required keys: {missing}")
    uri = str(meta["uri"])
    if not uri.startswith(URI_PREFIX):
        raise ValueError(f"{source}: meta.uri must start with {URI_PREFIX!r}, got {uri!r}")


def _load_yaml_resource(path: Path) -> ResourceEntry:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: root must be a mapping")
    meta = data.get("meta")
    if not isinstance(meta, dict):
        raise ValueError(f"{path}: expected top-level 'meta' mapping")
    _validate_meta(meta, path)
    body = {k: v for k, v in data.items() if k != "meta"}
    # Stash serialized body on entry via closure — store path + kind instead
    return ResourceEntry(
        uri=str(meta["uri"]),
        name=str(meta["name"]),
        description=str(meta["description"]),
        mime_type=str(meta["mime_type"]),
        source_path=path,
    )


def _load_markdown_resource(path: Path) -> ResourceEntry:
    text = path.read_text(encoding="utf-8")
    meta, _body_start_line = _parse_front_matter(text, path)
    _validate_meta(meta, path)
    return ResourceEntry(
        uri=str(meta["uri"]),
        name=str(meta["name"]),
        description=str(meta["description"]),
        mime_type=str(meta["mime_type"]),
        source_path=path,
    )


def _parse_front_matter(text: str, path: Path) -> tuple[dict[str, Any], int]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path}: expected YAML front matter starting with ---")
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        raise ValueError(f"{path}: unclosed front matter (missing closing ---)")
    fm_text = "\n".join(lines[1:end])
    meta_raw = yaml.safe_load(fm_text) or {}
    if not isinstance(meta_raw, dict):
        raise ValueError(f"{path}: front matter must be a mapping")
    if "meta" in meta_raw and isinstance(meta_raw["meta"], dict):
        meta = meta_raw["meta"]
    else:
        meta = meta_raw
    return meta, end + 1


def _read_body(entry: ResourceEntry) -> str:
    suffix = entry.source_path.suffix.lower()
    if suffix == ".yaml":
        data = yaml.safe_load(entry.source_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{entry.source_path}: root must be a mapping")
        body = {k: v for k, v in data.items() if k != "meta"}
        return yaml.dump(body, default_flow_style=False, sort_keys=False, allow_unicode=True)
    if suffix == ".md":
        text = entry.source_path.read_text(encoding="utf-8")
        _meta, body_start = _parse_front_matter(text, entry.source_path)
        body_lines = text.splitlines()[body_start:]
        return "\n".join(body_lines).lstrip("\n")
    raise ValueError(f"{entry.source_path}: unsupported resource type")


def default_resources_dir() -> Path:
    return Path(__file__).resolve().parent / "resources"
