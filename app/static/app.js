// -- State --
let current = null;
let data = null;
let editingFile = null;
let debounce = null;
let autosaveTimer = null;
let lastSavedBody = null;
let focusedIdx = -1;
let focusPanel = "list";
let sidebarIdx = -1;
let currentSortBy = "weight";
let sortMode = false;
let sortables = [];

// -- Helpers --
const api = (method, path, body) => {
  const opts = { method, headers: {} };
  if (body) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  return fetch(path, opts).then(r => r.json());
};

let flashTimer = null;
const flash = (msg) => {
  clearTimeout(flashTimer);
  const el = document.getElementById("flash");
  el.textContent = msg;
  el.classList.add("show");
  flashTimer = setTimeout(() => el.classList.remove("show"), 2000);
};

const clone = (id) => document.getElementById(id).content.cloneNode(true).firstElementChild;
const $f = (el, name) => el.querySelector(`[data-field="${name}"]`);
const $a = (el, name) => el.querySelector(`[data-action="${name}"]`);

// -- Init --
function init() {
  return api("GET", "/api/collections").then(cols => {
    if (!current && cols.length) current = cols[0].slug;
    const cur = cols.find(c => c.slug === current);
    currentSortBy = cur ? cur.sort_by : "weight";
    renderSidebar(cols);
    renderToolbar();
    loadStats();
    if (current) {
      openCollectionEditor();
      return loadCollection(current);
    }
  });
}

function loadStats() {
  api("GET", "/api/stats").then(s => {
    const el = document.getElementById("stats");
    el.textContent = "";
    for (const [val, label] of [[s.published, "publicados"], [s.drafts, "borradores"], [s.words.toLocaleString(), "palabras"]]) {
      const span = document.createElement("span");
      const strong = document.createElement("strong");
      strong.textContent = val;
      span.append(strong, ` ${label}`);
      el.appendChild(span);
    }
  });
}

// -- Sidebar --
function renderSidebar(cols) {
  const sidebar = document.getElementById("sidebar");
  sidebar.textContent = "";

  const published = cols.filter(c => !c.is_draft);
  const drafts = cols.filter(c => c.is_draft);

  sidebar.append(sidebarSection("Colecciones"), sidebarGroup(published));
  if (drafts.length) {
    sidebar.append(sidebarSection("Borradores"), sidebarGroup(drafts));
  }

  // New collection button
  const btn = document.createElement("button");
  btn.className = "sidebar-new-btn";
  btn.textContent = "+ Coleccion";
  btn.onclick = createCollection;
  sidebar.appendChild(btn);

  // Drag reordering
  for (const group of sidebar.querySelectorAll(".sidebar-group")) {
    Sortable.create(group, {
      animation: 150,
      ghostClass: "sortable-ghost",
      onEnd() {
        const order = {};
        sidebar.querySelectorAll(".sidebar-group a").forEach((a, i) => {
          order[a.dataset.slug] = i + 1;
        });
        api("POST", "/api/save-collection-order", { order }).then(() => flash("Orden guardado"));
      }
    });
  }

  // Click + drop-to-move
  for (const a of sidebar.querySelectorAll("a")) {
    a.onclick = (e) => {
      e.preventDefault();
      current = a.dataset.slug;
      closeEditor();
      init();
    };
    a.addEventListener("dragover", e => { e.preventDefault(); a.classList.add("drop-target"); });
    a.addEventListener("dragleave", () => a.classList.remove("drop-target"));
    a.addEventListener("drop", e => {
      e.preventDefault();
      a.classList.remove("drop-target");
      const file = e.dataTransfer.getData("text/plain");
      if (!file || a.dataset.slug === current) return;
      api("POST", "/api/move", { from_slug: current, file, to_slug: a.dataset.slug, to_section: null }).then(() => {
        if (editingFile === file) closeEditor();
        loadCollection(current);
        loadStats();
        init();
        flash(`Movido a ${$f(a, "title").textContent}`);
      });
    });
  }
}

function sidebarSection(label) {
  const div = document.createElement("div");
  div.className = "sidebar-section";
  div.textContent = label;
  return div;
}

function sidebarGroup(cols) {
  const group = document.createElement("div");
  group.className = "sidebar-group";
  for (const c of cols) {
    const a = clone("tpl-sidebar-link");
    a.dataset.slug = c.slug;
    if (c.slug === current) a.classList.add("active");
    if (c.is_draft) a.classList.add("is-draft");
    $f(a, "title").textContent = c.title;
    $f(a, "count").textContent = c.count;
    group.appendChild(a);
  }
  return group;
}

function createCollection() {
  const title = prompt("Nombre de la coleccion:");
  if (!title) return;
  api("POST", "/api/create-collection", { title }).then(r => {
    current = r.slug;
    init();
    flash("Coleccion creada");
  });
}

// -- List --
function loadCollection(slug) {
  return api("GET", `/api/collection/${slug}`).then(d => {
    data = d;
    focusedIdx = -1;
    renderList();
  });
}

function renderList() {
  const el = document.getElementById("list");
  el.textContent = "";

  if (data.pages.length) {
    el.appendChild(itemGroup("root-pages", data.pages));
  }

  for (const sec of data.sections) {
    const label = document.createElement("div");
    label.className = "section-label";
    label.textContent = sec.title;
    el.append(label, itemGroup(`sec-${sec.slug}`, sec.pages));
  }

  if (!data.pages.length && !data.sections.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "Sin entradas";
    el.appendChild(empty);
  }

  if (sortMode) enableSortables();

  if (focusedIdx >= 0) {
    const items = getAllItems();
    if (items[focusedIdx]) items[focusedIdx].classList.add("focused");
  }
}

function itemGroup(id, pages) {
  const wrap = document.createElement("div");
  wrap.className = "section-items";
  wrap.id = id;
  for (const p of pages) wrap.appendChild(buildItem(p));
  return wrap;
}

function buildItem(p) {
  const el = clone("tpl-item");
  el.dataset.file = p.file;
  if (p.entry_type === "interlude") el.classList.add("interlude");
  if (p.draft) el.classList.add("is-draft");
  if (p.file === editingFile) el.classList.add("active");

  const title = $f(el, "title");
  title.textContent = p.title;
  title.onclick = () => openEditor(p.file);

  const tagsEl = $f(el, "tags");
  for (const t of (p.tags || [])) {
    const span = document.createElement("span");
    span.className = "tag";
    span.textContent = t;
    tagsEl.appendChild(span);
  }

  $f(el, "type").textContent = p.entry_type || "poem";

  const dateEl = $f(el, "date");
  if (p.date) {
    dateEl.textContent = p.date;
  } else {
    dateEl.remove();
  }

  el.draggable = true;
  el.addEventListener("dragstart", e => {
    if (sortMode) return;
    e.dataTransfer.setData("text/plain", p.file);
    e.dataTransfer.effectAllowed = "move";
  });

  return el;
}

const getAllItems = () => [...document.querySelectorAll("#list .item")];

// -- Toolbar --
function renderToolbar() {
  const sortBtn = document.getElementById("btn-sort");
  sortBtn.style.display = currentSortBy === "weight" ? "" : "none";

  const links = document.getElementById("toolbar-links");
  if (!links || !current) return;
  links.textContent = "";
  for (const [label, href] of [["PDF", `/pdf/${current}.pdf`], ["EPUB", `/epub/${current}.epub`]]) {
    const a = document.createElement("a");
    Object.assign(a, { className: "btn btn-ghost", href, target: "_blank", rel: "noopener", textContent: label });
    links.appendChild(a);
  }
}

// -- Collection editor --
function openCollectionEditor() {
  if (!current || editingFile) return;
  api("GET", `/api/collection/${current}/meta`).then(m => {
    if (editingFile) return;

    const el = clone("tpl-collection");
    $f(el, "title").value = m.title;
    $f(el, "lang").value = m.lang;
    $f(el, "draft").checked = m.draft;

    const img = $f(el, "cover-img");
    const empty = $f(el, "cover-empty");
    if (m.has_cover) {
      img.src = `/covers/${current}`;
      img.alt = m.title;
      empty.remove();
    } else {
      img.remove();
    }

    $a(el, "save").onclick = () => {
      api("PUT", `/api/collection/${current}/meta`, {
        title: $f(el, "title").value,
        lang: $f(el, "lang").value,
        draft: $f(el, "draft").checked,
      }).then(() => { flash("Guardado"); init(); });
    };

    const panel = document.getElementById("editor-panel");
    panel.textContent = "";
    panel.appendChild(el);
  });
}

// -- Sort mode --
document.getElementById("btn-sort").onclick = () => {
  sortMode ? exitSortMode() : enterSortMode();
};

function enterSortMode() {
  sortMode = true;
  document.body.classList.add("sort-mode");
  const btn = document.getElementById("btn-sort");
  btn.textContent = "Listo";
  btn.classList.remove("btn-ghost");
  enableSortables();
}

function exitSortMode() {
  const order = {};
  for (const list of document.querySelectorAll(".section-items")) {
    list.querySelectorAll(".item").forEach((item, i) => {
      order[item.dataset.file] = i + 1;
    });
  }
  api("POST", "/api/save-order", { slug: current, order }).then(() => flash("Orden guardado"));

  sortMode = false;
  document.body.classList.remove("sort-mode");
  const btn = document.getElementById("btn-sort");
  btn.textContent = "Reordenar";
  btn.classList.add("btn-ghost");
  destroySortables();
}

function cancelSortMode() {
  sortMode = false;
  document.body.classList.remove("sort-mode");
  const btn = document.getElementById("btn-sort");
  btn.textContent = "Reordenar";
  btn.classList.add("btn-ghost");
  destroySortables();
  loadCollection(current);
  flash("Orden descartado");
}

function enableSortables() {
  destroySortables();
  for (const el of document.querySelectorAll(".section-items")) {
    sortables.push(Sortable.create(el, {
      animation: 150,
      ghostClass: "sortable-ghost",
      chosenClass: "sortable-chosen",
      group: "poems",
    }));
  }
}

function destroySortables() {
  sortables.forEach(s => s.destroy());
  sortables = [];
}

// -- Editor --
let statusTimer = null;
function showStatus(msg) {
  clearTimeout(statusTimer);
  for (const el of document.querySelectorAll('[data-field="status"]')) el.textContent = msg;
  if (msg === "Guardado") statusTimer = setTimeout(() => {
    for (const el of document.querySelectorAll('[data-field="status"]')) el.textContent = "";
  }, 2000);
}

function openEditor(file) {
  editingFile = file;

  for (const item of document.querySelectorAll(".item")) {
    item.classList.toggle("active", item.dataset.file === file);
  }

  api("GET", `/api/entry/${current}/${file}`).then(entry => {
    const el = clone("tpl-editor");

    $f(el, "title").value = entry.title;
    $f(el, "entry_type").value = entry.entry_type;
    $f(el, "epigraph").value = entry.epigraph || "";
    $f(el, "tags").value = (entry.tags || []).join(", ");
    $f(el, "date").value = entry.date || "";
    $f(el, "draft").checked = entry.draft;
    $f(el, "body").value = entry.body;

    const preview = $a(el, "preview");
    if (entry.draft) {
      preview.remove();
    } else {
      preview.href = previewUrl(file);
    }

    $a(el, "save").onclick = saveEntry;
    $a(el, "zen").onclick = toggleZen;
    $a(el, "delete").onclick = deleteEntry;

    for (const inp of el.querySelectorAll("input, textarea, select")) {
      const evt = inp.tagName === "SELECT" ? "onchange" : "oninput";
      inp[evt] = () => {
        if (inp.dataset.field === "body") updateWc();
        scheduleAutosave();
      };
    }
    $f(el, "draft").onchange = scheduleAutosave;

    const panel = document.getElementById("editor-panel");
    panel.textContent = "";
    panel.appendChild(el);

    updateWc();
    lastSavedBody = JSON.stringify(gatherEditorData());
  });
}

function closeEditor() {
  clearTimeout(autosaveTimer);
  editingFile = null;
  lastSavedBody = null;
  if (document.body.classList.contains("zen-mode")) toggleZen();
  for (const el of document.querySelectorAll(".item.active")) el.classList.remove("active");
  openCollectionEditor();
}

const previewUrl = (file) => `http://localhost:4000/poems/${current}/${file.replace(/\.md$/, "")}/`;

function updateWc() {
  const body = document.querySelector('[data-field="body"]');
  const wc = document.querySelector('[data-field="wc"]');
  if (!body || !wc) return;
  const t = body.value.trim();
  const words = t ? t.split(/ +/).length : 0;
  const lines = t ? t.split("\n").filter(l => l.trim()).length : 0;
  wc.textContent = `${lines} lineas · ${words} palabras`;
}

function scheduleAutosave() {
  clearTimeout(autosaveTimer);
  if (!editingFile) return;
  autosaveTimer = setTimeout(() => {
    if (!editingFile) return;
    const body = gatherEditorData();
    if (!body) return;
    const snapshot = JSON.stringify(body);
    if (snapshot === lastSavedBody) return;
    lastSavedBody = snapshot;
    showStatus("Guardando...");
    api("PUT", `/api/entry/${current}/${editingFile}`, body).then(() => {
      showStatus("Guardado");
    });
  }, 2000);
}

function gatherEditorData() {
  const panel = document.getElementById("editor-panel");
  const title = $f(panel, "title");
  if (!title) return null;
  return {
    title: title.value,
    entry_type: $f(panel, "entry_type").value,
    epigraph: $f(panel, "epigraph").value,
    tags: parseTags($f(panel, "tags").value),
    date: $f(panel, "date").value,
    draft: $f(panel, "draft").checked,
    body: $f(panel, "body").value,
  };
}

const parseTags = (s) => s ? s.split(",").map(t => t.trim()).filter(Boolean) : [];

function saveEntry() {
  clearTimeout(autosaveTimer);
  const body = gatherEditorData();
  if (!body) return;
  lastSavedBody = JSON.stringify(body);
  showStatus("Guardando...");
  api("PUT", `/api/entry/${current}/${editingFile}`, body).then(() => {
    loadCollection(current);
    showStatus("Guardado");
  });
}

function deleteEntry() {
  const action = current === "drafts" ? "eliminar permanentemente" : "mover a borradores";
  if (!confirm(`¿${action}?`)) return;
  api("POST", "/api/delete", { slug: current, file: editingFile }).then(() => {
    closeEditor();
    loadCollection(current);
    loadStats();
    flash(current === "drafts" ? "Eliminado" : "Movido a borradores");
  });
}

// -- Create --
document.getElementById("btn-new").onclick = () => {
  editingFile = null;
  const el = clone("tpl-create");

  $a(el, "create").onclick = createEntry;
  $a(el, "cancel").onclick = closeEditor;

  const panel = document.getElementById("editor-panel");
  panel.textContent = "";
  panel.appendChild(el);
  $f(el, "title").focus();
};

function createEntry() {
  const panel = document.getElementById("editor-panel");
  const title = $f(panel, "title").value;
  if (!title) return flash("Titulo requerido");
  const body = {
    title,
    entry_type: $f(panel, "entry_type").value,
    tags: parseTags($f(panel, "tags").value),
    date: $f(panel, "date").value,
    body: $f(panel, "body").value || "",
  };
  api("POST", `/api/create/${current}`, body).then(r => {
    loadCollection(current);
    loadStats();
    flash("Creado");
    if (r.file) openEditor(r.file);
  });
}

// -- Search --
const searchInput = document.getElementById("search");
const searchResults = document.getElementById("search-results");

searchInput.oninput = () => {
  clearTimeout(debounce);
  const q = searchInput.value.trim();
  if (!q) { searchResults.classList.remove("open"); searchResults.textContent = ""; return; }
  debounce = setTimeout(() => {
    api("GET", `/api/search?q=${encodeURIComponent(q)}`).then(results => {
      searchResults.textContent = "";
      if (!results.length) {
        const empty = document.createElement("div");
        Object.assign(empty, { className: "empty-state" });
        empty.style.padding = "1rem";
        empty.textContent = "Sin resultados";
        searchResults.appendChild(empty);
      } else {
        for (const r of results) {
          const el = clone("tpl-search-result");
          const titleEl = $f(el, "title");
          titleEl.textContent = r.title;
          if (r.draft) {
            const em = document.createElement("em");
            em.textContent = " (borrador)";
            titleEl.appendChild(em);
          }
          $f(el, "meta").textContent = `${r.collection_title} · ${r.entry_type}`;
          $f(el, "snippet").textContent = r.snippet;
          el.onclick = () => {
            searchResults.classList.remove("open");
            searchInput.value = "";
            editingFile = r.file;
            current = r.collection;
            init().then(() => openEditor(r.file));
          };
          searchResults.appendChild(el);
        }
      }
      searchResults.classList.add("open");
    });
  }, 250);
};

document.addEventListener("click", e => {
  if (!e.target.closest(".search-box")) searchResults.classList.remove("open");
});

// -- Keyboard navigation --
document.addEventListener("keydown", e => {
  const tag = e.target.tagName;
  const inEditor = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";

  if ((e.metaKey || e.ctrlKey) && e.key === "s") {
    e.preventDefault();
    if (editingFile) saveEntry();
    return;
  }
  if ((e.metaKey || e.ctrlKey) && e.key === "n") {
    e.preventDefault();
    document.getElementById("btn-new").click();
    return;
  }
  if ((e.metaKey || e.ctrlKey) && e.key === "l") {
    if (document.body.classList.contains("zen-mode")) { e.preventDefault(); toggleZenTheme(); }
    return;
  }
  if ((e.metaKey || e.ctrlKey) && e.key === "e" && editingFile) {
    e.preventDefault();
    toggleZen();
    return;
  }
  if (e.key === "Escape") {
    if (document.body.classList.contains("zen-mode")) { toggleZen(); return; }
    if (sortMode) cancelSortMode();
    else if (inEditor) e.target.blur();
    else if (editingFile) closeEditor();
    return;
  }

  if (!inEditor) {
    if (e.key === "/") {
      e.preventDefault();
      document.getElementById("search").focus();
      return;
    }
    if (e.key === "h" || e.key === "ArrowLeft") {
      e.preventDefault();
      focusPanel = "sidebar";
      if (sidebarIdx < 0) sidebarIdx = 0;
      highlightSidebar();
      clearListFocus();
      return;
    }
    if (e.key === "l" || e.key === "ArrowRight") {
      e.preventDefault();
      focusPanel = "list";
      if (focusedIdx < 0) focusedIdx = 0;
      highlightFocused(getAllItems());
      clearSidebarFocus();
      return;
    }
  }

  if (inEditor) return;

  if (focusPanel === "sidebar") {
    const links = [...document.querySelectorAll(".sidebar a")];
    if (!links.length) return;
    if (e.key === "ArrowDown" || e.key === "j") {
      e.preventDefault();
      sidebarIdx = Math.min(sidebarIdx + 1, links.length - 1);
      highlightSidebar();
    } else if (e.key === "ArrowUp" || e.key === "k") {
      e.preventDefault();
      sidebarIdx = Math.max(sidebarIdx - 1, 0);
      highlightSidebar();
    } else if (e.key === "Enter" && sidebarIdx >= 0) {
      e.preventDefault();
      links[sidebarIdx].click();
      focusPanel = "list";
      focusedIdx = 0;
    }
  } else {
    const items = getAllItems();
    if (!items.length) return;
    if (e.key === "ArrowDown" || e.key === "j") {
      e.preventDefault();
      focusedIdx = Math.min(focusedIdx + 1, items.length - 1);
      highlightFocused(items);
    } else if (e.key === "ArrowUp" || e.key === "k") {
      e.preventDefault();
      focusedIdx = Math.max(focusedIdx - 1, 0);
      highlightFocused(items);
    } else if (e.key === "Enter" && focusedIdx >= 0 && focusedIdx < items.length) {
      e.preventDefault();
      openEditor(items[focusedIdx].dataset.file);
    }
  }
});

function highlightFocused(items) {
  items.forEach(el => el.classList.remove("focused"));
  if (focusedIdx >= 0 && focusedIdx < items.length) {
    items[focusedIdx].classList.add("focused");
    items[focusedIdx].scrollIntoView({ block: "nearest" });
  }
}

const clearListFocus = () => getAllItems().forEach(el => el.classList.remove("focused"));

function highlightSidebar() {
  const links = [...document.querySelectorAll(".sidebar a")];
  links.forEach(el => el.classList.remove("focused"));
  if (sidebarIdx >= 0 && sidebarIdx < links.length) {
    links[sidebarIdx].classList.add("focused");
    links[sidebarIdx].scrollIntoView({ block: "nearest" });
  }
}

const clearSidebarFocus = () => document.querySelectorAll(".sidebar a").forEach(el => el.classList.remove("focused"));

// -- Zen mode --
function toggleZen() {
  const entering = !document.body.classList.contains("zen-mode");
  document.body.classList.toggle("zen-mode");
  if (!entering) { document.body.classList.remove("zen-light"); }

  const old = document.querySelector(".zen-stats");
  if (old) old.remove();

  if (!entering) return;

  document.body.classList.add("zen-light");

  const panel = document.getElementById("editor-panel");
  const stats = clone("tpl-zen-stats");
  $f(stats, "title").textContent = $f(panel, "title")?.value || "";
  $f(stats, "date").textContent = $f(panel, "date")?.value || "";
  document.querySelector(".editor").appendChild(stats);
  updateZenStats();

  const ta = document.querySelector('[data-field="body"]');
  if (ta) { ta.focus(); ta.addEventListener("input", updateZenStats); }
}

function toggleZenTheme() {
  document.body.classList.toggle("zen-light");
}

function updateZenStats() {
  const ta = document.querySelector('[data-field="body"]');
  const el = document.querySelector('.zen-stats [data-field="wc"]');
  if (!ta || !el) return;
  const t = ta.value.trim();
  const lines = t ? t.split("\n").filter(l => l.trim()).length : 0;
  const words = t ? t.split(/\s+/).length : 0;
  const chars = t.length;
  el.textContent = `${lines}L  ${words}P  ${chars}C`;
}

// -- Start --
init();
