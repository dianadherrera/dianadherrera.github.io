# Website

Poetry website for [dherrera.xyz](https://dherrera.xyz).

## Dependencies

- [Zola](https://www.getzola.org/), static site generator
- [Typst](https://typst.app), PDF typesetting
- [uv](https://docs.astral.sh/uv/), runs Python scripts for PDF and EPUB generation
- [GitHub Actions](.github/workflows/deploy.yml), deploy to GitHub Pages

```bash
brew bundle
```

## Usage

```bash
make dev         # Dev server at localhost:4000
make build       # Site + PDF + EPUB
make clean       # Remove build artifacts
```

## Content

Poems live in `content/poems/`.

Images go in the same folder and are referenced with relative paths.

Line breaks are preserved with [`macros/poem.html`](templates/macros/poem.html).
