---
name: epub
description: EPUB format reference for building and debugging EPUB files. Use when working on EPUB generation, fixing rendering issues, or adding EPUB features like covers, images, TOC, or section breaks.
---

# EPUB 3 Format Reference

EPUB is a ZIP archive with a specific structure and XHTML content. See [spec.md](spec.md) for the full reference, grounded in:

- **EPUB 3.3** (W3C Recommendation) — container, package, content documents
- **EPUB 3.3 Reading Systems** (W3C Recommendation) — CSS, font, nav requirements
- **EPUB Accessibility 1.1** (W3C Recommendation) — a11y metadata, WCAG
- **Apple Books Asset Guide** — cover dimensions, CSS specifics, a11y rules
- **KDP Cover Image Guidelines** — Kindle cover specs

## Quick Structure

```
book.epub (ZIP)
  mimetype                    # MUST be first, uncompressed
  META-INF/container.xml      # points to OPF
  OEBPS/content.opf           # manifest + spine + metadata
  OEBPS/nav.xhtml             # TOC (required in EPUB 3)
  OEBPS/style.css
  OEBPS/*.xhtml               # content pages
  OEBPS/images/*              # images
```

## Key Rules

1. **mimetype first, uncompressed** — spec section 4.3.2
2. **XHTML not HTML** — self-closing tags, xmlns, xml:lang (section 6.1)
3. **Cover** — `properties="cover-image"` in manifest (section D.6.1). Legacy `<meta name="cover">` not in EPUB 3.3 spec but needed for Apple Books thumbnails
4. **Spine = reading order** — TOC nav is separate (section 5.7)
5. **All files in manifest** — every image, CSS, XHTML must be listed (section 5.6)
6. **CSS per CSS Snapshot** — RS must support modules at CR+ status (RS section 6.3). Apple Books: use `em`/`%` not `px` for flowing text
7. **Apple Books covers** — at least 1400px on shortest side, JPEG or PNG, RGB
8. **Kindle covers** — 2560x1600px recommended, JPEG preferred, max 5MB, 300 DPI

## Our EPUB Script

`scripts/epub.py` — generates EPUBs for poetry collections. Key decisions:
- Typst-generated cover PNG for Apple Books thumbnail
- Inline styles for one-off layouts, CSS classes for repeated patterns
- `hyphens: none` on stanzas (poetry line breaks are intentional)
- Closing page with site link and CC license
