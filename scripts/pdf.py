# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""Generate PDFs for each poetry collection using Typst."""

import json
import subprocess
from pathlib import Path

from lib import ROOT, CONFIG, read_collections, read_entries, content_to_stanzas, images_dir

OUT = ROOT / "public" / "pdf"
TYPST_TPL = ROOT / "scripts" / "typst" / "book.typ"
TYPST_DATA = ROOT / "scripts" / "typst" / "data"


def build_pdf(col):
    _, entries = read_entries(col["slug"])
    img_dir = images_dir(col["slug"])

    pdf_entries = []
    for e in entries:
        typ = e.get("entry_type", "poem")
        entry = {"type": typ, "title": e.get("title", ""), "slug": e.get("slug", "")}

        if typ == "poem":
            entry["stanzas"] = content_to_stanzas(e.get("content", ""))
        elif typ == "section":
            entry["body"] = e.get("body", e.get("title", ""))
        elif typ == "picture":
            entry["caption"] = e.get("caption", "")
            img = e.get("image")
            p = img_dir / img if img else None
            entry["image"] = f"/{p.relative_to(ROOT)}" if p and p.exists() else None

        pdf_entries.append(entry)

    cover = None
    if col.get("cover"):
        cp = img_dir / col["cover"]
        if cp.exists():
            cover = f"/{cp.relative_to(ROOT)}"

    data_file = TYPST_DATA / f"{col['slug']}.json"
    data_file.write_text(json.dumps({
        "title": col.get("title", ""),
        "subtitle": col.get("subtitle", ""),
        "author": col.get("author", CONFIG.get("title", "")),
        "slug": col["slug"],
        "lang": col.get("lang", "es"),
        "cover": cover,
        "entries": pdf_entries,
    }, indent=2, ensure_ascii=False))

    out_pdf = OUT / f"{col['slug']}.pdf"
    try:
        subprocess.run([
            "typst", "compile", str(TYPST_TPL), str(out_pdf),
            "--root", str(ROOT),
            "--input", f"data=/{data_file.relative_to(ROOT)}",
        ], check=True, capture_output=True, text=True)
        print(f"  {out_pdf.relative_to(ROOT)}")
    except subprocess.CalledProcessError as e:
        print(f"ERROR {col['slug']}: {e.stderr}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    TYPST_DATA.mkdir(parents=True, exist_ok=True)

    for col in read_collections():
        build_pdf(col)
    print("PDF build complete!")


if __name__ == "__main__":
    main()
