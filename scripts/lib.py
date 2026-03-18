"""Shared utilities for PDF and EPUB build scripts."""

import re
import tomllib
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = tomllib.loads((ROOT / "config.toml").read_text())


def images_dir(slug):
    return ROOT / "content" / "poems" / slug


def parse_frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n?(.*)", text, re.DOTALL)
    if not m:
        return {}, text
    return yaml.safe_load(m.group(1)) or {}, m.group(2)


def _read_poems(dir):
    """Read poem .md files from a directory, skipping drafts."""
    poems = []
    for f in sorted(dir.glob("*.md")):
        if f.name == "_index.md":
            continue
        meta, body = parse_frontmatter(f.read_text())
        if meta.get("draft"):
            continue
        extra = meta.get("extra", {})
        poems.append({
            **extra,
            "title": meta.get("title", ""),
            "slug": f.stem,
            "weight": meta.get("weight", 0),
            "date": str(meta.get("date", "")),
            "content": body,
        })
    return poems


def read_collections():
    poems = ROOT / "content" / "poems"
    cols = []
    for d in sorted(poems.iterdir()):
        if not d.is_dir():
            continue
        idx = d / "_index.md"
        if not idx.exists():
            continue
        meta, _ = parse_frontmatter(idx.read_text())
        if meta.get("draft"):
            continue
        extra = meta.get("extra", {})
        cols.append({"slug": d.name, **meta, **extra})

    cols.sort(key=lambda c: c.get("weight", 0))
    return cols


def read_entries(slug):
    """Read all entries for a collection, including subsections."""
    base = ROOT / "content" / "poems" / slug
    idx, _ = parse_frontmatter((base / "_index.md").read_text())
    entries = _read_poems(base)

    for sub in sorted(base.iterdir()):
        if not sub.is_dir() or sub.name.startswith("."):
            continue
        si = sub / "_index.md"
        if not si.exists():
            continue
        meta, _ = parse_frontmatter(si.read_text())
        extra = meta.get("extra", {})

        entries.append({
            **extra,
            "title": meta.get("title", ""),
            "slug": sub.name,
            "weight": meta.get("weight", 0),
        })

        entries.extend(_read_poems(sub))

    entries.sort(key=lambda e: e.get("weight", 0))
    return idx, entries


def md_to_segments(line):
    """Parse a markdown line into segments with bold/italic flags."""
    line = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", line)
    line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)

    segs = []
    last = 0
    for m in re.finditer(r"\*\*([^*]+)\*\*|\*([^*]+)\*|(?<!\w)_([^_]+)_(?!\w)", line):
        if m.start() > last:
            segs.append({"t": line[last:m.start()]})
        if m.group(1):
            segs.append({"t": m.group(1), "b": True})
        elif m.group(2):
            segs.append({"t": m.group(2), "i": True})
        elif m.group(3):
            segs.append({"t": m.group(3), "i": True})
        last = m.end()

    if last < len(line):
        segs.append({"t": line[last:]})
    return segs


def content_to_stanzas(content):
    """Split poem content into stanzas of line-segments."""
    stanzas = []
    for raw in re.split(r"\n{2,}", content.strip()):
        lines = [md_to_segments(l.strip()) for l in raw.strip().split("\n")]
        lines = [s for s in lines if s]
        if lines:
            stanzas.append(lines)
    return stanzas
