# CMS Todo

## Done
- [x] Three-panel dashboard (sidebar, list, editor)
- [x] Browse collections with entry counts
- [x] Drag-to-reorder within sections
- [x] Edit poems inline (title, type, epigraph, date, tags, content)
- [x] Create new entries
- [x] Move between collections/sections
- [x] Delete (soft to drafts, hard from drafts)
- [x] Search across all collections and drafts
- [x] Autosave (2s debounce, skip if unchanged)
- [x] Preview link (opens localhost:4000, hidden for drafts)
- [x] Line + word count
- [x] Undo last save (8s window, Cmd+Z)
- [x] Duplicate entry
- [x] Drag to sidebar to move between collections
- [x] Keyboard nav (hjkl, arrows, Enter, Escape, Cmd+S/N/Z)
- [x] Tags support
- [x] Free-form entry type (poem, interlude, essay, ...)
- [x] Stats bar (published, drafts, total words)

## Writing
- [ ] Zen mode — fullscreen distraction-free writing, Esc to exit
- [ ] Dark mode — toggle in topbar, persist preference
- [ ] Markdown preview — live rendered preview beside textarea

## Organization
- [ ] Language field — set lang per entry (es/en), show flag/label in list
- [ ] Filter bar — filter list by type, tag, or language with clickable pills
- [ ] Quick publish — "Publicar en..." dropdown on draft items in list
- [ ] Bulk select — checkbox mode, move/tag/delete multiple at once

## Publishing
- [ ] Build status — run `zola build` after save, show pass/fail
- [ ] Git integration — commit button, auto message, show dirty/clean state
- [ ] Deploy — one-click `git push` to publish
- [ ] EPUB/PDF — trigger `make epub` / `make pdf` from dashboard

## Quality of life
- [ ] Sidebar collection reorder (drag to reorder collections)
- [ ] Section management — create/rename/delete sections from CMS
- [ ] Recent edits — show last 5 edited poems at top of sidebar
- [ ] Entry date defaults to today on create
- [ ] Confirm before navigating away with unsaved changes
- [ ] Textarea tab key inserts spaces instead of changing focus

## Future
- [ ] Rich text mode — toggle for longer prose (essays/ensayos)
- [ ] Image upload — drag images into editor, save to collection dir
- [ ] Version history — show git log per file, restore previous versions
- [ ] Export — download collection as .txt, .pdf, or .epub from editor
- [ ] Multiple authors — support collaborators on shared collections
