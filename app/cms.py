# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""Local CMS for poetry collections."""

import json
import re
import shutil
import unicodedata
import webbrowser
from datetime import date as Date
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote, parse_qs, urlparse

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
    body = body.strip("\n")
    path.write_text(f"---\n{fm}---\n{body}\n" if body else f"---\n{fm}---\n")


def update_weight(path, weight):
    text = path.read_text()
    if re.search(r"^weight:", text, re.MULTILINE):
        text = re.sub(r"^(weight:\s*)\d+", rf"\g<1>{weight}", text, count=1, flags=re.MULTILINE)
    else:
        text = re.sub(r"^(---\n)", rf"\g<1>weight: {weight}\n", text, count=1)
    path.write_text(text)


def slugify(title):
    s = unicodedata.normalize("NFD", title.lower().strip())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
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
        is_draft = meta.get("draft", False)
        count = sum(1 for f in d.rglob("*.md") if f.name != "_index.md")
        cols.append({
            "slug": d.name, "title": meta.get("title", d.name),
            "weight": meta.get("weight", 0), "is_draft": is_draft, "count": count,
            "sort_by": meta.get("sort_by", "weight"),
        })
    cols.sort(key=lambda c: (c["is_draft"], c["weight"]))
    return cols


def get_collection(slug):
    base = CONTENT / slug
    idx_meta, _ = parse_fm(base / "_index.md")
    sort_by = idx_meta.get("sort_by", "weight")
    sort_key = (lambda p: p["date"], True) if sort_by == "date" else (lambda p: p["weight"], False)

    pages = []
    for f in sorted(base.glob("*.md")):
        if f.name == "_index.md":
            continue
        meta, _ = parse_fm(f)
        e = entry_from_meta(meta)
        e["file"] = f.name
        pages.append(e)
    pages.sort(key=sort_key[0], reverse=sort_key[1])

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
        sec_pages.sort(key=sort_key[0], reverse=sort_key[1])
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

    # Check collection sort mode
    idx = CONTENT / slug / "_index.md"
    col_meta, _ = parse_fm(idx)
    sort_by = col_meta.get("sort_by", "weight")

    meta = {"title": data["title"]}
    if sort_by == "weight":
        weights = [parse_fm(f)[0].get("weight", 0) for f in base.glob("*.md") if f.name != "_index.md"]
        meta["weight"] = max(weights) + 1 if weights else 1
    if data.get("entry_type") == "interlude":
        meta["template"] = "interlude.html"
    meta["date"] = data.get("date") or str(Date.today())
    if slug == "drafts":
        meta["draft"] = True
    meta["extra"] = extra
    write_entry(base / fname, meta, data.get("body", ""))
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
    shutil.move(src, dst)

    meta, body = parse_fm(dst)
    meta["weight"] = new_w
    if "draft" in meta and to_slug != "drafts":
        del meta["draft"]
    if to_slug == "drafts":
        meta["draft"] = True
    write_entry(dst, meta, body)


def find_cover(slug):
    for ext in ("jpg", "jpeg", "png", "webp"):
        p = CONTENT / slug / f"cover.{ext}"
        if p.exists():
            return p
    return None


def get_collection_meta(slug):
    idx = CONTENT / slug / "_index.md"
    meta, _ = parse_fm(idx)
    extra = meta.get("extra", {})
    cover = find_cover(slug)
    return {
        "title": meta.get("title", ""),
        "weight": meta.get("weight", 0),
        "lang": extra.get("lang", ""),
        "has_cover": cover is not None,
        "draft": meta.get("draft", False),
    }


def save_collection_meta(slug, data):
    idx = CONTENT / slug / "_index.md"
    meta, body = parse_fm(idx)
    meta["title"] = data["title"]
    meta["weight"] = data.get("weight", meta.get("weight", 0))
    if data.get("draft"):
        meta["draft"] = True
    elif "draft" in meta:
        del meta["draft"]
    extra = meta.get("extra", {})
    if data.get("lang"):
        extra["lang"] = data["lang"]
    elif "lang" in extra:
        del extra["lang"]
    meta["extra"] = extra
    write_entry(idx, meta, body)


def create_collection(data):
    slug = slugify(data["title"])
    col_dir = CONTENT / slug
    col_dir.mkdir(exist_ok=True)
    weights = []
    for d in CONTENT.iterdir():
        idx = d / "_index.md"
        if d.is_dir() and idx.exists():
            m, _ = parse_fm(idx)
            weights.append(m.get("weight", 0))
    w = max(weights) + 1 if weights else 1
    extra = {}
    if data.get("lang"):
        extra["lang"] = data["lang"]
    meta = {
        "title": data["title"],
        "sort_by": "weight",
        "weight": w,
        "template": "collection.html",
        "draft": True,
        "extra": extra,
    }
    write_entry(col_dir / "_index.md", meta, "")
    return slug


def save_collection_order(order):
    for slug, weight in order.items():
        idx = CONTENT / slug / "_index.md"
        if idx.exists():
            update_weight(idx, weight)


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
        is_draft = col_meta.get("draft", False)
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

class Abort(Exception):
    def __init__(self, code=404):
        self.code = code


class Response:
    def __init__(self, body, ctype="application/octet-stream"):
        self.body = body
        self.ctype = ctype


CTYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
STATIC_FILES = {"html": ("index.html", "text/html"), "js": ("app.js", "application/javascript"), "css": ("style.css", "text/css")}


# -- Route handlers --

def r_static(ext):
    name, ctype = STATIC_FILES[ext]
    path = STATIC / name
    if not path.exists():
        raise Abort(404)
    return Response(path.read_bytes(), f"{ctype}; charset=utf-8")

def r_cover(slug):
    fpath = find_cover(slug)
    if not fpath:
        raise Abort(404)
    return Response(fpath.read_bytes(), CTYPES.get(fpath.suffix.lower(), "image/jpeg"))

def r_public_file(path):
    base = ROOT / "public"
    fpath = (base / path).resolve()
    if not fpath.is_relative_to(base) or not fpath.exists():
        raise Abort(404)
    ctype = "application/pdf" if path.endswith(".pdf") else "application/epub+zip"
    return Response(fpath.read_bytes(), ctype)

def r_collections():
    return get_collections()

def r_stats():
    return get_stats()

def r_search(*, q=None):
    return search_poems(q or "")

def r_collection(slug):
    return get_collection(slug)

def r_collection_meta_get(slug):
    return get_collection_meta(slug)

def r_entry_get(slug, file):
    return get_entry(slug, unquote(file))

def r_create_collection(body):
    return {"ok": True, "slug": create_collection(body)}

def r_save_collection_order(body):
    save_collection_order(body["order"])
    return {"ok": True}

def r_save_order(body):
    save_order(body["slug"], body["order"])
    return {"ok": True}

def r_create_entry(body, slug):
    return {"ok": True, "file": create_entry(slug, body)}

def r_move(body):
    move_entry(body["from_slug"], body["file"], body["to_slug"], body.get("to_section"))
    return {"ok": True}

def r_delete(body):
    delete_entry(body["slug"], body["file"])
    return {"ok": True}

def r_entry_put(body, slug, file):
    save_entry(slug, unquote(file), body)
    return {"ok": True}

def r_collection_meta_put(body, slug):
    save_collection_meta(slug, body)
    return {"ok": True}


# -- Routing --

ROUTES = [
    ("GET",  r"/(?P<ext>html|js|css)$",                      r_static),
    ("GET",  r"/api/collections$",                            r_collections),
    ("GET",  r"/api/stats$",                                  r_stats),
    ("GET",  r"/api/search$",                                 r_search),
    ("GET",  r"/api/collection/(?P<slug>[^/]+)/meta$",        r_collection_meta_get),
    ("GET",  r"/api/collection/(?P<slug>[^/]+)$",             r_collection),
    ("GET",  r"/api/entry/(?P<slug>[^/]+)/(?P<file>.+)$",     r_entry_get),
    ("GET",  r"/covers/(?P<slug>[^/]+)$",                     r_cover),
    ("GET",  r"/(?P<path>(?:pdf|epub)/.+)$",                  r_public_file),
    ("POST", r"/api/create-collection$",                      r_create_collection),
    ("POST", r"/api/save-collection-order$",                  r_save_collection_order),
    ("POST", r"/api/save-order$",                             r_save_order),
    ("POST", r"/api/create/(?P<slug>[^/]+)$",                 r_create_entry),
    ("POST", r"/api/move$",                                   r_move),
    ("POST", r"/api/delete$",                                 r_delete),
    ("PUT",  r"/api/entry/(?P<slug>[^/]+)/(?P<file>.+)$",     r_entry_put),
    ("PUT",  r"/api/collection/(?P<slug>[^/]+)/meta$",        r_collection_meta_put),
]

# Pre-compile patterns
ROUTES = [(method, re.compile(pattern), handler) for method, pattern, handler in ROUTES]

STATIC_PATHS = {"/": "/html", "/app.js": "/js", "/style.css": "/css"}


def match_route(method, path):
    for rt_method, rt_pat, rt_handler in ROUTES:
        if rt_method != method:
            continue
        m = rt_pat.match(path)
        if m:
            return rt_handler, m.groupdict()
    return None, {}


class Handler(BaseHTTPRequestHandler):
    def handle_request(self, method):
        parsed = urlparse(self.path)
        path = STATIC_PATHS.get(parsed.path, parsed.path)

        handler, params = match_route(method, path)
        if not handler:
            return self.send_error(404)

        try:
            if method == "GET":
                qs = {k: v[0] for k, v in parse_qs(parsed.query).items()}
                result = handler(**params, **qs)
            else:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                result = handler(**{"body": body, **params})
        except Abort as e:
            return self.send_error(e.code)

        if isinstance(result, Response):
            self.send_response(200)
            self.send_header("Content-Type", result.ctype)
            self.end_headers()
            self.wfile.write(result.body)
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())

    def do_GET(self):
        self.handle_request("GET")

    def do_POST(self):
        self.handle_request("POST")

    def do_PUT(self):
        self.handle_request("PUT")

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
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nCMS: stopped")
        srv.server_close()
