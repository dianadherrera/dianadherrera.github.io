# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""Local CMS for poetry collections."""

import json
import re
import shutil
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote, parse_qs, urlparse
import webbrowser
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content" / "poems"
STATIC = Path(__file__).resolve().parent / "static"


# -- Data helpers --

def parse_fm(path):
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n?(.*)", text, re.DOTALL)
    if not m:
        return {}, text
    return yaml.safe_load(m.group(1)) or {}, m.group(2)


def write_entry(path, meta, body):
    fm = yaml.dump(meta, allow_unicode=True, default_flow_style=False, sort_keys=False)
    path.write_text(f"---\n{fm}---\n{body}")


def update_weight(path, weight):
    text = path.read_text()
    if re.search(r"^weight:", text, re.MULTILINE):
        text = re.sub(r"^(weight:\s*)\d+", rf"\g<1>{weight}", text, count=1, flags=re.MULTILINE)
    else:
        text = re.sub(r"^(---\n)", rf"\g<1>weight: {weight}\n", text, count=1)
    path.write_text(text)


def slugify(title):
    s = title.lower().strip()
    for a, b in [("á","a"),("à","a"),("é","e"),("è","e"),("í","i"),("ì","i"),
                  ("ó","o"),("ò","o"),("ú","u"),("ù","u"),("ñ","n")]:
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def entry_from_meta(meta, body=None):
    extra = meta.get("extra", {})
    d = {
        "title": meta.get("title", ""),
        "weight": meta.get("weight", 0),
        "date": str(meta.get("date", "")),
        "entry_type": extra.get("entry_type", "poem"),
        "lang": extra.get("lang", ""),
        "epigraph": extra.get("epigraph", ""),
        "tags": extra.get("tags", []),
        "draft": meta.get("draft", False),
    }
    if body is not None:
        d["body"] = body
    return d


def get_collections():
    cols = []
    for d in sorted(CONTENT.iterdir()):
        idx = d / "_index.md"
        if not d.is_dir() or not idx.exists():
            continue
        meta, _ = parse_fm(idx)
        extra = meta.get("extra", {})
        is_draft = meta.get("draft", False) or extra.get("status") == "draft"
        count = sum(1 for f in d.rglob("*.md") if f.name != "_index.md")
        cols.append({
            "slug": d.name, "title": meta.get("title", d.name),
            "weight": meta.get("weight", 0), "is_draft": is_draft, "count": count,
        })
    cols.sort(key=lambda c: (c["is_draft"], c["weight"]))
    return cols


def get_collection(slug):
    base = CONTENT / slug
    pages = []
    for f in sorted(base.glob("*.md")):
        if f.name == "_index.md":
            continue
        meta, _ = parse_fm(f)
        e = entry_from_meta(meta)
        e["file"] = f.name
        pages.append(e)
    pages.sort(key=lambda p: p["weight"])

    sections = []
    for sub in sorted(base.iterdir()):
        si = sub / "_index.md"
        if not sub.is_dir() or not si.exists():
            continue
        meta, _ = parse_fm(si)
        sec_pages = []
        for f in sorted(sub.glob("*.md")):
            if f.name == "_index.md":
                continue
            pm, _ = parse_fm(f)
            e = entry_from_meta(pm)
            e["file"] = f"{sub.name}/{f.name}"
            sec_pages.append(e)
        sec_pages.sort(key=lambda p: p["weight"])
        sections.append({
            "slug": sub.name, "title": meta.get("title", sub.name),
            "weight": meta.get("weight", 0), "pages": sec_pages,
        })
    sections.sort(key=lambda s: s["weight"])
    return {"pages": pages, "sections": sections}


def get_entry(slug, file):
    path = CONTENT / slug / file
    meta, body = parse_fm(path)
    e = entry_from_meta(meta, body)
    e["file"] = file
    return e


def save_entry(slug, file, data):
    path = CONTENT / slug / file
    old_meta, _ = parse_fm(path)
    extra = old_meta.get("extra", {})

    extra["entry_type"] = data.get("entry_type", "poem")
    for k in ("lang", "epigraph"):
        if data.get(k):
            extra[k] = data[k]
        elif k in extra:
            del extra[k]
    if data.get("tags"):
        extra["tags"] = data["tags"]
    elif "tags" in extra:
        del extra["tags"]
    for k in ("position", "cover", "credit", "image"):
        if k in old_meta.get("extra", {}):
            extra[k] = old_meta["extra"][k]

    meta = {"title": data["title"]}
    if data.get("draft"):
        meta["draft"] = True
    if data.get("date"):
        meta["date"] = data["date"]
    if old_meta.get("weight") is not None:
        meta["weight"] = old_meta["weight"]
    if data.get("template") or old_meta.get("template"):
        meta["template"] = data.get("template") or old_meta["template"]
    meta["extra"] = extra
    write_entry(path, meta, data.get("body", ""))


def create_entry(slug, data, section=None):
    base = CONTENT / slug / section if section else CONTENT / slug
    fname = slugify(data["title"]) + ".md"
    extra = {"entry_type": data.get("entry_type", "poem")}
    if data.get("lang"):
        extra["lang"] = data["lang"]
    if data.get("tags"):
        extra["tags"] = data["tags"]

    weights = [parse_fm(f)[0].get("weight", 0) for f in base.glob("*.md") if f.name != "_index.md"]
    w = max(weights) + 1 if weights else 1

    meta = {"title": data["title"], "weight": w}
    if data.get("entry_type") == "interlude":
        meta["template"] = "interlude.html"
    if data.get("date"):
        meta["date"] = data["date"]
    if slug == "drafts":
        meta["draft"] = True
    meta["extra"] = extra
    write_entry(base / fname, meta, data.get("body", "\n"))
    return fname


def delete_entry(slug, file):
    if slug == "drafts":
        (CONTENT / slug / file).unlink()
    else:
        move_entry(slug, file, "drafts")


def move_entry(from_slug, file, to_slug, to_section=None):
    src = CONTENT / from_slug / file
    dst_dir = CONTENT / to_slug / to_section if to_section else CONTENT / to_slug
    dst = dst_dir / Path(file).name

    weights = [parse_fm(f)[0].get("weight", 0) for f in dst_dir.glob("*.md") if f.name != "_index.md"]
    new_w = max(weights) + 1 if weights else 1
    shutil.move(str(src), str(dst))

    meta, body = parse_fm(dst)
    meta["weight"] = new_w
    if "draft" in meta and to_slug != "drafts":
        del meta["draft"]
    if to_slug == "drafts":
        meta["draft"] = True
    write_entry(dst, meta, body)


def save_order(slug, order):
    base = CONTENT / slug
    for rel, weight in order.items():
        path = base / rel
        if path.exists():
            update_weight(path, weight)


def search_poems(query):
    q = query.lower()
    results = []
    for col_dir in sorted(CONTENT.iterdir()):
        if not col_dir.is_dir():
            continue
        idx = col_dir / "_index.md"
        if not idx.exists():
            continue
        col_meta, _ = parse_fm(idx)
        col_title = col_meta.get("title", col_dir.name)
        for md in col_dir.rglob("*.md"):
            if md.name == "_index.md":
                continue
            meta, body = parse_fm(md)
            title = meta.get("title", "")
            extra = meta.get("extra", {})
            tags = " ".join(extra.get("tags", []))
            if q in title.lower() or q in body.lower() or q in tags.lower():
                rel = md.relative_to(col_dir)
                results.append({
                    "collection": col_dir.name, "collection_title": col_title,
                    "file": str(rel), "title": title,
                    "entry_type": extra.get("entry_type", "poem"),
                    "draft": meta.get("draft", False),
                    "snippet": body.strip()[:120],
                })
    return results


def get_stats():
    total = drafts = published = words = 0
    for col_dir in sorted(CONTENT.iterdir()):
        if not col_dir.is_dir():
            continue
        idx = col_dir / "_index.md"
        if not idx.exists():
            continue
        col_meta, _ = parse_fm(idx)
        is_draft = col_meta.get("draft", False) or col_meta.get("extra", {}).get("status") == "draft"
        for md in col_dir.rglob("*.md"):
            if md.name == "_index.md":
                continue
            meta, body = parse_fm(md)
            total += 1
            if meta.get("draft", False) or is_draft:
                drafts += 1
            else:
                published += 1
            words += len(body.split())
    return {"total": total, "published": published, "drafts": drafts, "words": words}


# -- HTTP --

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/":
            self.serve_file("index.html", "text/html")
        elif path == "/app.js":
            self.serve_file("app.js", "application/javascript")
        elif path == "/style.css":
            self.serve_file("style.css", "text/css")
        elif path == "/api/collections":
            self.json_ok(get_collections())
        elif path == "/api/stats":
            self.json_ok(get_stats())
        elif path.startswith("/api/collection/"):
            self.json_ok(get_collection(path.split("/")[-1]))
        elif path.startswith("/api/entry/"):
            parts = path[len("/api/entry/"):].split("/", 1)
            self.json_ok(get_entry(parts[0], unquote(parts[1])))
        elif path == "/api/search":
            self.json_ok(search_poems(qs.get("q", [""])[0]))
        else:
            self.err(404)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        path = urlparse(self.path).path
        if path == "/api/save-order":
            save_order(body["slug"], body["order"])
            self.json_ok({"ok": True})
        elif path.startswith("/api/create/"):
            fname = create_entry(path.split("/")[-1], body)
            self.json_ok({"ok": True, "file": fname})
        elif path == "/api/move":
            move_entry(body["from_slug"], body["file"], body["to_slug"], body.get("to_section"))
            self.json_ok({"ok": True})
        elif path == "/api/delete":
            delete_entry(body["slug"], body["file"])
            self.json_ok({"ok": True})
        else:
            self.err(404)

    def do_PUT(self):
        path = urlparse(self.path).path
        if path.startswith("/api/entry/"):
            parts = path[len("/api/entry/"):].split("/", 1)
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            save_entry(parts[0], unquote(parts[1]), body)
            self.json_ok({"ok": True})
        else:
            self.err(404)

    def serve_file(self, name, ctype):
        path = STATIC / name
        if not path.exists():
            return self.err(404)
        self.send_response(200)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.end_headers()
        self.wfile.write(path.read_bytes())

    def json_ok(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def err(self, code):
        self.send_response(code)
        self.end_headers()

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    port = 8888
    try:
        srv = HTTPServer(("127.0.0.1", port), Handler)
    except OSError:
        print(f"CMS: port {port} already in use, skipping")
        raise SystemExit(0)
    print(f"http://127.0.0.1:{port}")
    webbrowser.open(f"http://127.0.0.1:{port}")
    srv.serve_forever()
