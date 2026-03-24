# EPUB 3.3 Specification Reference

Sources:
- [EPUB 3.3](https://www.w3.org/TR/epub-33/) — W3C Recommendation
- [EPUB 3.3 Reading Systems](https://www.w3.org/TR/epub-rs-33/) — W3C Recommendation
- [EPUB Accessibility 1.1](https://www.w3.org/TR/epub-a11y-11/) — W3C Recommendation
- [Apple Books Asset Guide](https://help.apple.com/itc/booksassetguide/)
- [KDP Cover Image Guidelines](https://kdp.amazon.com/en_US/help/topic/G6GTK3T3NUHKLEFX)


## 1. ZIP Container (EPUB 3.3 section 4.3)

An EPUB is a ZIP archive with `.epub` extension, media type `application/epub+zip`.

### mimetype (REQUIRED, section 4.3.2)

Must be the **first entry** in the ZIP, **uncompressed** (ZIP_STORED). Content is exactly `application/epub+zip` — no newline, no BOM.

```python
zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
```

All other files SHOULD be compressed (section 4.3.2).

### META-INF/container.xml (REQUIRED, section 4.2.6.3.1)

Points reading systems to the package document:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf"
              media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
```

`OEBPS/` is conventional but not required by spec.


## 2. Package Document (section 5)

The OPF file has three required sections: metadata, manifest, spine.

### Metadata (section 5.5)

Required fields:
- `dc:identifier` — unique publication ID (section 5.5.3.1.1)
- `dc:title` — publication title (section 5.5.3.1.2)
- `dc:language` — primary language (section 5.5.3.1.3)

```xml
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:title>Book Title</dc:title>
  <dc:creator>Author Name</dc:creator>
  <dc:language>es</dc:language>
  <dc:identifier id="uid">urn:uuid:550e8400-e29b-41d4-a716-446655440000</dc:identifier>
  <meta property="dcterms:modified">2026-03-23T12:00:00Z</meta>
</metadata>
```

### Manifest (section 5.6)

Lists **all** publication resources. Each `<item>` requires: `id`, `href`, `media-type`. Optional: `properties`, `fallback`.

```xml
<manifest>
  <item id="css" href="style.css" media-type="text/css"/>
  <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
  <item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
  <item id="cover-img" href="images/cover.png" media-type="image/png" properties="cover-image"/>
</manifest>
```

### Spine (section 5.7)

Ordered list of `<itemref>` elements defining reading order. Each references a manifest item by `idref`. Items must be EPUB content documents (XHTML/SVG) or have fallback chains.

```xml
<spine>
  <itemref idref="cover"/>
  <itemref idref="ch1"/>
</spine>
```

Items in the manifest but not the spine (images, CSS) are still available — they're not in the linear reading flow. Optional `linear="no"` for non-reading-order content.


## 3. Navigation Document (section 7)

One EPUB navigation document is **required** per publication. Must be XHTML containing `<nav epub:type="toc">` with nested `<ol>`.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:epub="http://www.idpf.org/2007/ops" lang="es">
<head><title>Contents</title></head>
<body>
  <nav epub:type="toc" id="toc">
    <ol>
      <li><a href="cover.xhtml">Cover</a></li>
      <li><a href="ch1.xhtml">Chapter 1</a>
        <ol>
          <li><a href="ch1.xhtml#s1">Section 1.1</a></li>
        </ol>
      </li>
    </ol>
  </nav>
</body>
</html>
```

Required: `epub:type="toc"` nav. Optional: `epub:type="page-list"`, `epub:type="landmarks"`.

The nav document must be in the manifest with `properties="nav"`. May be in the spine but not required (section 7.5).

**Reading systems** (RS spec section 7): MUST provide access to links/headings in toc nav. SHOULD provide page-list navigation when present. MUST NOT show list numbering when presenting nav outside the spine.


## 4. Content Documents (section 6.1)

Content pages must be well-formed XHTML (XML serialization of HTML):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="es" lang="es">
<head>
  <title>Page Title</title>
  <link rel="stylesheet" href="style.css"/>
</head>
<body>
  <h1>Chapter Title</h1>
  <p>Content here.</p>
</body>
</html>
```

XHTML means: self-closing tags (`<br/>`, `<img/>`), all attributes quoted, `xmlns` on `<html>`. Embedded SVG and MathML supported (section 6.1.4.1-6.1.4.2). No scripting unless reading system explicitly supports it.


## 5. Cover Image

### EPUB 3.3 (section D.6.1)

The spec defines one mechanism: `properties="cover-image"` on a manifest item.

```xml
<item id="cover-img" href="images/cover.png"
      media-type="image/png" properties="cover-image"/>
```

The legacy `<meta name="cover" content="..."/>` is from EPUB 2, not in the 3.3 spec.

### Apple Books (Asset Guide)

- Cover "should be at least 1400 pixels along the shorter axis"
- JPEG or PNG
- RGB color mode required
- "Do not increase the size of a smaller image to meet the minimum"
- Interior images: max 5.6 million pixels (height x width) — does NOT apply to cover
- Alt text required on all images; "do not use the word 'image' in the alt text"

### Kindle/KDP (Cover Image Guidelines)

- Recommended: 2560px (height) x 1600px (width)
- Minimum: 500px on shortest side
- JPEG preferred (SVG not supported on iPad Kindle app)
- Max 5MB
- 300 DPI minimum
- RGB only (no CMYK)

### Cover XHTML page

A dedicated page showing the cover as the first spine item. Not required by spec but common:

```xml
<body>
  <div style="text-align:center;">
    <img src="images/cover.png" alt="Cover" style="max-width:100%;"/>
  </div>
</body>
```


## 6. Core Media Types (section 3.2)

These MUST be supported by reading systems without fallbacks:

| Category | Formats |
|----------|---------|
| Images | JPEG, PNG, GIF, WebP, SVG |
| Audio | MP3, AAC (MP4), Opus (OGG) |
| Styles | CSS |
| Fonts | TrueType, OpenType, WOFF, WOFF2 |
| Markup | XHTML, SVG |
| Scripts | JavaScript |

**Foreign resources** (anything not core) require fallback chains (section 3.3).


## 7. CSS

### What the spec says (RS spec section 6.3)

Reading systems with viewports MUST support CSS as defined in the CSS Snapshot — all modules at CR status or above. The spec references the evolving snapshot rather than listing individual properties.

The [CSS Snapshot](https://www.w3.org/TR/CSS/) includes these stable modules (REC status):
- CSS Level 2 (CSS2.1), Selectors 3, Color 3, Namespaces
- Cascading and Inheritance 3, Fonts 3, Writing Modes 3
- Basic User Interface 3, Box Model 3, Containment 1
- Media Queries 3, Style Attributes

And these at CR/CRD status (included in snapshot, less mature):
- Backgrounds and Borders 3, Flexbox 1, Grid 1
- Multi-column 1, Values and Units 3, Text 3
- Text Decoration 3, Transforms 1, Fragmentation 3
- Images 3, Custom Properties 1, Display 3
- Scroll Snap 1, Color 4, Easing Functions 1
- Writing Modes 4, Grid 2, Cascading 4-5

Reading systems MAY override creator stylesheets but SHOULD apply them as written when feasible.

### Apple Books CSS specifics (Asset Guide)

- Flowing books: use `em` or `%` for font sizing, not `px` or named sizes
- Main text should be `1em` or undefined for ideal scaling
- Line-height: use unitless values to prevent cascading issues
- Custom text colors in dark theme: requires `class="ibooks-dark-theme-use-custom-text-color"`
- Adobe Page Template (XPGT) not supported; use CSS3
- Fixed-layout: use `px`, requires viewport meta and `rendition:layout` metadata
- Embedded fonts: requires `<meta property="ibooks:specified-fonts">true</meta>`

### Font embedding (RS spec section 6.3, 4.3)

Reading systems MUST support TrueType, OpenType, WOFF, and WOFF2 via `@font-face`. SHOULD support font deobfuscation (RS spec section 4.3).


## 8. Section Breaks and Page Breaks

CSS Fragmentation Level 3 is at CR status — reading systems should support `break-before`, `break-after`, `break-inside`. The older `page-break-*` properties are aliases per CSS Fragmentation spec.

```css
.chapter { break-before: page; }
.stanza { break-inside: avoid; }
```

Visual dividers within a page:

```xml
<hr style="width:2em; border:none; border-top:1px solid #ccc; margin:2em auto;"/>
<p style="text-align:center; margin:2em 0;">* * *</p>
```


## 9. Semantic Vocabulary (Appendix C)

`epub:type` is **optional** for general content, **required** only for nav elements (section 7).

```xml
<section epub:type="chapter">
<section epub:type="dedication">
<aside epub:type="footnote">
```

Requires namespace: `xmlns:epub="http://www.idpf.org/2007/ops"` on `<html>`.

Apple Books (Asset Guide): fixed-layout books should include `epub:type="bodymatter"` for optimal sample generation. Landmarks navigation required for fixed-layout books.


## 10. Accessibility

### EPUB Accessibility 1.1

Required metadata for conformance:
- `accessMode` — sensory modes needed (textual, visual, auditory, tactile)
- `accessibilityFeature` — features present (alt text, captions, etc.)
- `accessibilityHazard` — hazards (flashing, motion, sound, or "none")

WCAG baseline: must meet WCAG 2.0 Level A minimum, should target WCAG 2.2 Level AA.

### Apple Books (Asset Guide)

- Alt text required on all images
- Semantic heading tags (`<h1>`, `<h2>`, etc.) required
- Minimum contrast ratio: 4.5:1 (3:1 for large/heading text)


## 11. Validation

```bash
brew install epubcheck
epubcheck book.epub
```

Common errors: mimetype compressed or not first, missing manifest entries, malformed XHTML, missing required metadata, hrefs pointing to unlisted files.

```bash
unzip -p book.epub mimetype          # verify mimetype content
unzip -l book.epub                   # list all files
unzip -o book.epub -d /tmp/epub-test # extract and inspect
```


## 12. Minimal Valid EPUB 3

Five files minimum:

```
mimetype                  # "application/epub+zip", uncompressed, first entry
META-INF/container.xml    # points to content.opf
OEBPS/content.opf         # metadata + manifest + spine
OEBPS/nav.xhtml           # navigation document (properties="nav")
OEBPS/content.xhtml       # at least one content document in spine
```
