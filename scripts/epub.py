# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""Generate EPUBs for each poetry collection."""

import hashlib
import re
import zipfile
from datetime import datetime, timezone
from html import escape as esc
from pathlib import Path

from lib import ROOT, CONFIG, read_collections, read_entries, images_dir

OUT = ROOT / "public" / "epub"

EPUB_CSS = """\
body { font-family: "Baskerville", "Palatino", "Georgia", serif; margin: 2em 1.5em; line-height: 1.7; color: #1a1a1a; }
h1 { font-size: 1.15em; font-weight: normal; font-style: italic; text-align: center; margin: 2em 0 0.5em; color: #555; }
h1 + .date { margin-top: 0.5em; }
.stanza { margin: 1.2em 0; text-indent: 0; font-size: 0.95em; }
.epigraph { text-align: center; font-style: italic; font-size: 0.85em; color: #888; margin: 0 1em 2em; }
.date { font-size: 0.7em; color: #aaa; text-align: center; margin-bottom: 2em; font-family: sans-serif; }
.section-page { text-align: center; font-style: italic; color: #888; margin: 40% 1em 0; }
.image { text-align: center; margin: 2em 0; page-break-before: always; }
.image img { max-width: 100%; max-height: 80vh; }
.caption { text-align: center; font-style: italic; font-size: 0.85em; color: #888; margin-top: 0.5em; }
.centered { text-align: center; margin-top: 35%; }
.centered h2 { font-size: 1.1em; font-weight: normal; font-style: italic; color: #555; }
.centered p { font-size: 0.85em; color: #888; margin: 0.5em 0; }
.centered .small { font-size: 0.75em; color: #aaa; }
.centered a { color: #555; }"""


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
            # Use sentinel chars to protect tags from HTML escaping
            l = re.sub(r"\*\*([^*]+)\*\*", "\x00S\x01\\1\x00/S\x01", l)
            l = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", "\x00E\x01\\1\x00/E\x01", l)
            l = re.sub(r"\*([^*]+)\*", "\x00E\x01\\1\x00/E\x01", l)
            l = esc(l)
            l = l.replace("\x00S\x01", "<strong>").replace("\x00/S\x01", "</strong>")
            l = l.replace("\x00E\x01", "<em>").replace("\x00/E\x01", "</em>")
            lines.append(l)
        stanzas.append(f'<p class="stanza">{"<br/>".join(lines)}</p>')
    return "\n".join(stanzas)


def xhtml(title, body, css=True):
    css_link = '<link rel="stylesheet" href="style.css"/>' if css else ""
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<!DOCTYPE html>\n'
        f'<html xmlns="http://www.w3.org/1999/xhtml">\n'
        f"<head><title>{esc(title)}</title>{css_link}</head>\n"
        f"<body>\n{body}\n</body></html>"
    )


def mime(f):
    if f.endswith(".png"):
        return "image/png"
    if f.endswith(".gif"):
        return "image/gif"
    return "image/jpeg"


def build_epub(col):
    _, entries = read_entries(col["slug"])
    img_dir = images_dir(col["slug"])
    lang = col.get("lang", CONFIG.get("default_language", "es"))
    is_es = lang == "es"
    author = col.get("author", CONFIG.get("title", ""))
    donate = CONFIG.get("extra", {}).get("donate", "")

    image_files = []
    spine = []
    manifest = []
    files = {}  # path-in-zip -> content (bytes or str)

    def add_image(filename):
        src = img_dir / filename
        if src.exists() and filename not in image_files:
            files[f"OEBPS/images/{filename}"] = src.read_bytes()
            image_files.append(filename)

    def add_page(pid, content):
        files[f"OEBPS/{pid}.xhtml"] = content
        spine.append(pid)
        manifest.append({"id": pid, "href": f"{pid}.xhtml"})

    # Title page
    if col.get("cover"):
        add_image(col["cover"])
    cover_img = f'<img src="images/{col["cover"]}" alt="" style="max-width:100%; display:block;" />' if col.get("cover") else ""
    add_page("title", xhtml(col.get("title", ""), f"""
<div style="text-align:center; padding:8% 12%;">
  <p style="font-size:1.3em; font-style:italic; color:#333; margin:0 0 1em;">{esc(col.get("title", ""))}</p>
  <div style="background:#f5f2ec; padding:8% 6%; display:inline-block;">
    {cover_img}
  </div>
  <p style="font-size:0.85em; color:#888; margin:1.5em 0 0;">{esc(author)}</p>
</div>""", css=False))

    # Content pages
    for i, entry in enumerate(entries):
        pid = f"p{i}"
        typ = entry.get("entry_type", "poem")

        if typ == "section":
            body = esc(entry.get("body", entry.get("title", "")))
            add_page(pid, xhtml(entry.get("title", ""), f'<div class="section-page">{body}</div>'))

        elif typ == "picture":
            img = entry.get("image", "")
            if img:
                add_image(img)
            title = entry.get("title", "")
            img_tag = f'<img src="images/{img}" alt="{esc(title)}" />' if img else ""
            title_tag = f'<p class="caption">{esc(title)}</p>' if title else ""
            cap_tag = f'<p class="caption">{esc(entry.get("caption", ""))}</p>' if entry.get("caption") else ""
            add_page(pid, xhtml(title, f'<div class="image">{img_tag}</div>\n{title_tag}\n{cap_tag}'))

        elif typ == "poem":
            content = entry.get("content", "")
            for img_md in re.findall(r"!\[[^\]]*\]\(/poems/[^/]+/([^)]+)\)", content):
                add_image(img_md)
                content = content.replace(f"/poems/{col['slug']}/{img_md}", f"images/{img_md}")

            title = entry.get("title", "")
            date_html = f'<p class="date">{entry.get("date", "")}</p>' if entry.get("date") else ""
            epi_html = f'<p class="epigraph">{esc(entry.get("epigraph", ""))}</p>' if entry.get("epigraph") else ""
            add_page(pid, xhtml(title, f"<h1>{esc(title)}</h1>\n{date_html}\n{epi_html}\n{md_to_xhtml(content)}"))

    # Support page
    if is_es:
        support_title, thanks, msg, small = "Apoyo", "Gracias por leer", "Si estas palabras tocaron algo en ti, considera apoyar mi trabajo.", "Cada contribución me permite dedicar más tiempo a la poesía."
    else:
        support_title, thanks, msg, small = "Support", "Thank you for reading", "If these words touched something in you, consider supporting my work.", "Every contribution allows me to dedicate more time to poetry."
    donate_link = f'<p><a href="{donate}">{donate.replace("https://", "")}</a></p>' if donate else ""
    add_page("support", xhtml(support_title, f"""
<div class="centered">
  <h2>{thanks}</h2>
  <p>{msg}</p>
  {donate_link}
  <p class="small">{small}</p>
</div>"""))

    # Copyright
    base_url = CONFIG.get("base_url", "")
    add_page("copyright", xhtml("Copyright", f"""
<div class="centered">
  <p class="small">&copy; {esc(author)}</p>
  <p class="small"><a href="https://creativecommons.org/licenses/by-nc-nd/4.0/">CC BY-NC-ND 4.0</a></p>
  <p class="small"><a href="{base_url}">{base_url.replace("https://", "")}</a></p>
</div>"""))

    # Navigation
    nav_items = [f'<li><a href="title.xhtml">{esc(col.get("title", ""))}</a></li>']
    for i, entry in enumerate(entries):
        typ = entry.get("entry_type", "poem")
        if typ in ("poem", "section"):
            label = entry.get("title", "") if typ == "poem" else entry.get("body", entry.get("title", ""))
            nav_items.append(f'<li><a href="p{i}.xhtml">{esc(label)}</a></li>')
    nav_body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">\n'
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
        manifest_xml.append(f'    <item id="img{i}" href="images/{f}" media-type="{mime(f)}"/>')

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
        # mimetype must be first, uncompressed
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        for zpath, data in files.items():
            zf.writestr(zpath, data, compress_type=zipfile.ZIP_DEFLATED)

    kb = out.stat().st_size // 1024
    print(f"  {out.relative_to(ROOT)} ({kb}KB)")


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    for col in read_collections():
        build_epub(col)
    print("EPUB build complete!")


if __name__ == "__main__":
    main()
