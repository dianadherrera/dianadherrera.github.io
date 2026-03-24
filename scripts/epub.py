# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""Generate EPUBs for each poetry collection."""

import hashlib
import json
import re
import subprocess
import zipfile
from datetime import datetime, timezone
from html import escape as esc
from pathlib import Path

from lib import ROOT, CONFIG, read_collections, read_entries, images_dir

COVER_TPL = ROOT / "scripts" / "typst" / "cover.typ"
COVER_DATA = ROOT / "tmp"

OUT = ROOT / "public" / "epub"

# CSS matching the site design — no flexbox (unreliable across EPUB readers)
EPUB_CSS = """\
body {
  font-family: "Iowan Old Style", "Palatino", "Georgia", serif;
  margin: 2em 1.5em;
  line-height: 1.75;
  color: #121212;
  background: #fffcf4;
}
h1 {
  font-size: 1.15em;
  font-weight: normal;
  font-style: italic;
  text-align: center;
  margin: 2em 0 0.3em;
  color: #a0522d;
}
h1::after {
  content: "";
  display: block;
  width: 0.8em;
  height: 1px;
  background: #e8e2d6;
  margin: 0.6em auto 0;
}
.stanza {
  margin: 1.2em 0;
  text-indent: 0;
  font-size: 0.95em;
  -webkit-hyphens: none;
  hyphens: none;
}
.epigraph {
  text-align: center;
  font-style: italic;
  font-size: 0.85em;
  color: #6e6358;
  margin: 0 1em 2em;
}
img {
  max-width: 100%;
  display: block;
  margin-left: auto;
  margin-right: auto;
}
.section-page {
  text-align: center;
  font-style: italic;
  color: #6e6358;
  padding-top: 40%;
}
.image {
  text-align: center;
  margin: 2em 0;
}
.caption {
  text-align: center;
  font-style: italic;
  font-size: 0.85em;
  color: #6e6358;
  margin-top: 0.5em;
}
a { color: #a0522d; text-decoration: none; }
"""


def md_to_xhtml(md):
    stanzas = []
    for raw in re.split(r"\n{2,}", md.strip()):
        s = raw.strip()
        if not s:
            continue
        if s.startswith("!["):
            m = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", s)
            if m:
                stanzas.append(f'<div class="image"><img src="{m.group(2)}" alt="{esc(m.group(1))}" /></div>')
            continue

        lines = []
        for l in s.split("\n"):
            l = l.strip()
            if not l:
                continue
            l = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", l)
            l = re.sub(r"\*\*([^*]+)\*\*", "\x00S\x01\\1\x00/S\x01", l)
            l = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", "\x00E\x01\\1\x00/E\x01", l)
            l = re.sub(r"\*([^*]+)\*", "\x00E\x01\\1\x00/E\x01", l)
            l = esc(l)
            l = l.replace("\x00S\x01", "<strong>").replace("\x00/S\x01", "</strong>")
            l = l.replace("\x00E\x01", "<em>").replace("\x00/E\x01", "</em>")
            lines.append(l)
        stanzas.append(f'<p class="stanza">{"<br/>".join(lines)}</p>')
    return "\n".join(stanzas)


def xhtml(title, body, lang="es", css=True, epub_type=None):
    ns = ' xmlns:epub="http://www.idpf.org/2007/ops"' if epub_type else ""
    body_attr = f' epub:type="{epub_type}"' if epub_type else ""
    css_link = '<link rel="stylesheet" href="style.css"/>' if css else ""
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<!DOCTYPE html>\n'
        f'<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{lang}" lang="{lang}"{ns}>\n'
        f"<head><title>{esc(title)}</title>{css_link}</head>\n"
        f'<body{body_attr}>\n{body}\n</body></html>'
    )


def mime(f):
    if f.endswith(".png"):
        return "image/png"
    if f.endswith(".gif"):
        return "image/gif"
    return "image/jpeg"


def generate_cover(col, author):
    """Generate cover image matching the PDF cover layout."""
    img_dir = images_dir(col["slug"])
    cover_path = img_dir / col.get("cover", "cover.jpg")
    if not cover_path.exists():
        return None

    data_file = COVER_DATA / f"{col['slug']}-cover.json"
    data_file.write_text(json.dumps({
        "title": col.get("title", ""),
        "author": author,
        "cover": f"/{cover_path.relative_to(ROOT)}",
    }))

    out = COVER_DATA / f"{col['slug']}-cover.png"
    try:
        subprocess.run([
            "typst", "compile", str(COVER_TPL), str(out),
            "--root", str(ROOT),
            "--input", f"data=/{data_file.relative_to(ROOT)}",
            "--format", "png", "--ppi", "150",
        ], check=True, capture_output=True, text=True)
        return out.read_bytes()
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"  cover generation failed: {e}")
        return None


def build_epub(col):
    _, entries = read_entries(col["slug"])
    img_dir = images_dir(col["slug"])
    lang = col.get("lang", CONFIG.get("default_language", "es"))
    is_es = lang == "es"
    author = col.get("author", CONFIG.get("title", ""))

    image_files = []
    spine = []
    manifest = []
    files = {}

    def add_image(filename):
        src = img_dir / filename
        if src.exists() and filename not in image_files:
            files[f"OEBPS/images/{filename}"] = src.read_bytes()
            image_files.append(filename)

    def add_page(pid, content):
        files[f"OEBPS/{pid}.xhtml"] = content
        spine.append(pid)
        manifest.append({"id": pid, "href": f"{pid}.xhtml"})

    # Cover image for Apple Books thumbnail (Typst-generated PNG)
    if col.get("cover"):
        add_image(col["cover"])
        cover_data = generate_cover(col, author)
        if cover_data:
            files["OEBPS/images/book-cover.png"] = cover_data
            image_files.insert(0, "book-cover.png")

    # Title page — text only
    add_page("title", xhtml(col.get("title", ""), f"""
<div style="text-align:center; padding-top:30%;">
  <p style="font-size:1.3em; font-style:italic; color:#a0522d; margin:0 0 0.5em;">{esc(col.get("title", ""))}</p>
  <div style="width:0.8em; height:1px; background:#e8e2d6; margin:0.6em auto;"></div>
  <p style="font-size:0.85em; color:#6e6358; margin:0.5em 0 0;">{esc(author)}</p>
</div>""", lang=lang))

    # Cover image page — avoid page break splitting the image
    if col.get("cover"):
        add_page("cover", xhtml(col.get("title", ""), f"""
<div style="text-align:center; page-break-inside:avoid;">
  <img src="images/{col["cover"]}" alt="{esc(col.get("title", ""))}" style="max-width:70%;" />
</div>""", lang=lang))

    # Content pages
    for i, entry in enumerate(entries):
        pid = f"p{i}"
        typ = entry.get("entry_type", "poem")
        if "cover" in entry and "content" not in entry:
            typ = "picture"

        if typ == "interlude":
            lines = entry.get("content", "").strip()
            lines = lines.replace("\\\n", "<br/>").replace("\n", "<br/>")
            lines = esc(lines).replace("&lt;br/&gt;", "<br/>")
            add_page(pid, xhtml(entry.get("title", ""), f'<div class="section-page">{lines}</div>', lang=lang))

        elif typ == "section":
            body = esc(entry.get("body", entry.get("title", "")))
            add_page(pid, xhtml(entry.get("title", ""), f'<div class="section-page">{body}</div>', lang=lang))

        elif typ == "picture":
            img = entry.get("cover", entry.get("image", ""))
            if img:
                img_path = f"{entry.get('slug', '')}/{img}"
                add_image(img_path)
            title = entry.get("title", "")
            caption = entry.get("subtitle", entry.get("caption", ""))
            title_html = f'<p style="font-size:1.3em; font-style:italic; color:#6e6358; margin:0;">{esc(title)}</p>' if title else ""
            cap_html = f'<p style="font-size:0.85em; font-style:italic; color:#6e6358; margin:0.2em 0 0; letter-spacing:0.08em;">{esc(caption)}</p>' if caption else ""
            sep_html = '<div style="width:0.8em; height:1px; background:#e8e2d6; margin:0.5em auto;"></div>'
            img_html = f'<img src="images/{img_path}" alt="{esc(title)}" style="max-width:100%;" />' if img else ""
            add_page(pid, xhtml(title, f"""
<div style="text-align:center; padding-top:15%;">
  {title_html}
  {cap_html}
  {sep_html}
  <div style="margin-top:2em;">
    {img_html}
  </div>
</div>""", lang=lang))

        elif typ == "poem":
            content = entry.get("content", "")
            for img_md in re.findall(r"!\[[^\]]*\]\(([^/)][^)]*)\)", content):
                add_image(img_md)
                content = content.replace(f"]({img_md})", f"](images/{img_md})")

            title = entry.get("title", "")
            epi_html = f'<p class="epigraph">{esc(entry.get("epigraph", ""))}</p>' if entry.get("epigraph") else ""
            add_page(pid, xhtml(title, f"<h1>{esc(title)}</h1>\n{epi_html}\n{md_to_xhtml(content)}", lang=lang))

    # Closing page — no flexbox
    illus_path = ROOT / "static" / "flower-tiny.jpg"
    illus_html = ""
    if illus_path.exists():
        files["OEBPS/images/illustration.jpg"] = illus_path.read_bytes()
        image_files.append("illustration.jpg")
        illus_html = '<img src="images/illustration.jpg" alt="Botanical illustration" style="max-width:80px;" />'

    if is_es:
        thanks, msg, small = "Gracias por leer", "Si estas palabras tocaron algo en ti,", "tu apoyo me permite continuar en este camino."
    else:
        thanks, msg, small = "Thank you for reading", "If these words touched something in you,", "your support allows me to continue on this path."
    base_url = CONFIG.get("base_url", "")

    add_page("closing", xhtml(thanks, f"""
<div style="text-align:center; padding-top:25%;">
  {illus_html}
  <p style="font-size:1.1em; font-style:italic; color:#6e6358; margin:1em 0 0.3em;">{thanks}</p>
  <p style="font-size:0.8em; color:#6e6358; margin:0;">{msg}</p>
  <p style="font-size:0.8em; color:#6e6358; margin:0.1em 0 0;">{small}</p>
  <p style="font-size:0.8em; margin:0.4em 0 0;"><a href="{base_url}">{base_url.replace("https://", "")}</a></p>
  <div style="width:0.8em; height:1px; background:#e8e2d6; margin:1.5em auto;"></div>
  <p style="font-size:0.7em; color:#6e6358;">&#169; {esc(author)} &#183; <a href="https://creativecommons.org/licenses/by-nc-nd/4.0/" style="color:#6e6358;">CC BY-NC-ND 4.0</a></p>
</div>""", lang=lang))

    # Navigation
    nav_items = [f'<li><a href="title.xhtml">{esc(col.get("title", ""))}</a></li>']
    for i, entry in enumerate(entries):
        typ = entry.get("entry_type", "poem")
        if "cover" in entry and "content" not in entry:
            typ = "picture"
        if typ in ("poem", "picture"):
            nav_items.append(f'<li><a href="p{i}.xhtml">{esc(entry.get("title", ""))}</a></li>')
        elif typ == "interlude":
            label = entry.get("content", "").strip().replace("\\\n", " ").replace("\n", " ")
            nav_items.append(f'<li><a href="p{i}.xhtml"><em>{esc(label)}</em></a></li>')
        elif typ == "section":
            label = entry.get("body", entry.get("title", ""))
            nav_items.append(f'<li><a href="p{i}.xhtml">{esc(label)}</a></li>')
    nav_body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE html>\n'
        f'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{lang}" lang="{lang}">\n'
        '<head><title>Contents</title><link rel="stylesheet" href="style.css"/></head>\n'
        f'<body><nav epub:type="toc" id="toc"><ol>{"".join(nav_items)}</ol></nav></body></html>'
    )
    files["OEBPS/nav.xhtml"] = nav_body
    spine.append("nav")
    manifest.append({"id": "nav", "href": "nav.xhtml"})

    # OPF
    h = hashlib.md5(col["slug"].encode()).hexdigest()
    uuid = f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"

    cover_meta = f'    <meta name="cover" content="img0"/>' if col.get("cover") else ""
    manifest_xml = ['    <item id="css" href="style.css" media-type="text/css"/>']
    manifest_xml.append('    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>')
    for m in manifest:
        if m["id"] != "nav":
            manifest_xml.append(f'    <item id="{m["id"]}" href="{m["href"]}" media-type="application/xhtml+xml"/>')
    for i, f in enumerate(image_files):
        props = ' properties="cover-image"' if i == 0 and col.get("cover") else ""
        manifest_xml.append(f'    <item id="img{i}" href="images/{f}" media-type="{mime(f)}"{props}/>')

    spine_xml = [f'    <itemref idref="{s}"/>' for s in spine if s != "nav"]

    opf = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{esc(col.get("title", ""))}</dc:title>
    <dc:creator>{esc(author)}</dc:creator>
    <dc:language>{lang}</dc:language>
    <dc:identifier id="uid">urn:uuid:{uuid}</dc:identifier>
    <meta property="dcterms:modified">{datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}</meta>
    <meta property="schema:accessMode">textual</meta>
    <meta property="schema:accessMode">visual</meta>
    <meta property="schema:accessibilityFeature">alternativeText</meta>
    <meta property="schema:accessibilityHazard">none</meta>
    <meta property="schema:accessModeSufficient">textual</meta>
{cover_meta}
  </metadata>
  <manifest>
{chr(10).join(manifest_xml)}
  </manifest>
  <spine>
{chr(10).join(spine_xml)}
  </spine>
</package>"""
    files["OEBPS/content.opf"] = opf
    files["OEBPS/style.css"] = EPUB_CSS
    files["META-INF/container.xml"] = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
        '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
        '</rootfiles></container>'
    )

    # Write ZIP
    out = OUT / f"{col['slug']}.epub"
    with zipfile.ZipFile(out, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        for zpath, data in files.items():
            zf.writestr(zpath, data, compress_type=zipfile.ZIP_DEFLATED)

    kb = out.stat().st_size // 1024
    print(f"  {out.relative_to(ROOT)} ({kb}KB)")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    COVER_DATA.mkdir(parents=True, exist_ok=True)

    for col in read_collections():
        build_epub(col)
    print("EPUB build complete!")


if __name__ == "__main__":
    main()
