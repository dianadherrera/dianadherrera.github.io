// -- State --
var current = null;
var data = null;
var editingFile = null;
var debounce = null;
var autosaveTimer = null;
var lastSavedBody = null;
var undoSnapshot = null; // previous save state for undo
var focusedIdx = -1;     // keyboard nav index
var focusPanel = "list"; // "sidebar" or "list"
var sidebarIdx = -1;
var sortMode = false;
var sortables = [];

// -- API helpers --
function api(method, path, body) {
  var opts = { method: method, headers: {} };
  if (body) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  return fetch(path, opts).then(function(r) { return r.json(); });
}

// -- Init --
function init() {
  return api("GET", "/api/collections").then(function(cols) {
    if (!current && cols.length) current = cols[0].slug;
    renderSidebar(cols);
    loadStats();
    if (current) return loadCollection(current);
  });
}

function loadStats() {
  api("GET", "/api/stats").then(function(s) {
    document.getElementById("stats").innerHTML =
      "<span><strong>" + s.published + "</strong> publicados</span>" +
      "<span><strong>" + s.drafts + "</strong> borradores</span>" +
      "<span><strong>" + s.words.toLocaleString() + "</strong> palabras</span>";
  });
}

// -- Sidebar --
function renderSidebar(cols) {
  var html = '<div class="sidebar-section">Colecciones</div>';
  var published = cols.filter(function(c) { return !c.is_draft; });
  var drafts = cols.filter(function(c) { return c.is_draft; });

  published.forEach(function(c) { html += sidebarLink(c); });
  if (drafts.length) {
    html += '<div class="sidebar-section">Borradores</div>';
    drafts.forEach(function(c) { html += sidebarLink(c); });
  }

  var sidebar = document.getElementById("sidebar");
  sidebar.innerHTML = html;
  sidebar.querySelectorAll("a").forEach(function(a) {
    a.onclick = function(e) {
      e.preventDefault();
      current = a.dataset.slug;
      closeEditor();
      init();
    };
  });

  // Drag-to-sidebar: make each sidebar link a drop target
  sidebar.querySelectorAll("a").forEach(function(a) {
    a.addEventListener("dragover", function(e) {
      e.preventDefault();
      a.classList.add("drop-target");
    });
    a.addEventListener("dragleave", function() {
      a.classList.remove("drop-target");
    });
    a.addEventListener("drop", function(e) {
      e.preventDefault();
      a.classList.remove("drop-target");
      var file = e.dataTransfer.getData("text/plain");
      var targetSlug = a.dataset.slug;
      if (!file || targetSlug === current) return;
      api("POST", "/api/move", { from_slug: current, file: file, to_slug: targetSlug, to_section: null }).then(function() {
        if (editingFile === file) closeEditor();
        loadCollection(current);
        loadStats();
        init();
        flash("Movido a " + a.querySelector("span").textContent);
      });
    });
  });
}

function sidebarLink(c) {
  var cls = [];
  if (c.slug === current) cls.push("active");
  if (c.is_draft) cls.push("is-draft");
  return '<a href="#" data-slug="' + c.slug + '" class="' + cls.join(" ") + '">'
    + '<span>' + esc(c.title) + '</span>'
    + '<span class="count">' + c.count + '</span>'
    + '</a>';
}

// -- List --
function loadCollection(slug) {
  return api("GET", "/api/collection/" + slug).then(function(d) {
    data = d;
    focusedIdx = -1;
    renderList();
  });
}

function renderList() {
  var el = document.getElementById("list");
  var html = "";

  if (data.pages.length) {
    html += '<div class="section-items" id="root-pages">';
    data.pages.forEach(function(p) { html += itemHtml(p); });
    html += "</div>";
  }

  data.sections.forEach(function(sec) {
    html += '<div class="section-label">' + esc(sec.title) + '</div>';
    html += '<div class="section-items" id="sec-' + sec.slug + '">';
    sec.pages.forEach(function(p) { html += itemHtml(p); });
    html += "</div>";
  });

  if (!data.pages.length && !data.sections.length) {
    html = '<div class="empty-state">Sin entradas</div>';
  }

  el.innerHTML = html;

  el.querySelectorAll("[data-edit]").forEach(function(span) {
    span.onclick = function() { openEditor(span.dataset.edit); };
  });

  // Make items draggable for sidebar drop (always, independent of sort mode)
  el.querySelectorAll(".item").forEach(function(item) {
    item.setAttribute("draggable", "true");
    item.addEventListener("dragstart", function(e) {
      if (sortMode) return; // let SortableJS handle it in sort mode
      e.dataTransfer.setData("text/plain", item.dataset.file);
      e.dataTransfer.effectAllowed = "move";
    });
  });

  // Init sortables if in sort mode
  if (sortMode) enableSortables();

  // Restore focus highlight
  if (focusedIdx >= 0) {
    var items = getAllItems();
    if (items[focusedIdx]) items[focusedIdx].classList.add("focused");
  }
}

function itemHtml(p) {
  var cls = ["item"];
  if (p.entry_type === "interlude") cls.push("interlude");
  if (p.draft) cls.push("is-draft");
  if (p.file === editingFile) cls.push("active");

  var tags = "";
  if (p.tags && p.tags.length) {
    tags = p.tags.map(function(t) { return '<span class="tag">' + esc(t) + "</span>"; }).join("");
  }

  return '<div class="' + cls.join(" ") + '" data-file="' + p.file + '">'
    + '<span class="title" data-edit="' + p.file + '">' + esc(p.title) + "</span>"
    + '<span class="meta">' + tags + "<span>" + (p.entry_type || "poem") + "</span>" + (p.date ? '<span class="date">' + p.date + '</span>' : '') + "</span>"
    + "</div>";
}

function getAllItems() {
  return Array.from(document.querySelectorAll("#list .item"));
}

// -- Sort mode --
document.getElementById("btn-sort").onclick = toggleSortMode;

function toggleSortMode() {
  if (sortMode) {
    exitSortMode();
  } else {
    enterSortMode();
  }
}

function enterSortMode() {
  sortMode = true;
  document.body.classList.add("sort-mode");
  document.getElementById("btn-sort").textContent = "Listo";
  document.getElementById("btn-sort").classList.remove("btn-ghost");
  document.getElementById("btn-sort").classList.add("btn");
  enableSortables();
}

function exitSortMode() {
  // Save order on exit
  var order = {};
  document.querySelectorAll(".section-items").forEach(function(list) {
    list.querySelectorAll(".item").forEach(function(item, i) {
      order[item.dataset.file] = i + 1;
    });
  });
  api("POST", "/api/save-order", { slug: current, order: order }).then(function() {
    flash("Orden guardado");
  });

  sortMode = false;
  document.body.classList.remove("sort-mode");
  document.getElementById("btn-sort").textContent = "Reordenar";
  document.getElementById("btn-sort").classList.remove("btn");
  document.getElementById("btn-sort").classList.add("btn-ghost");
  destroySortables();
}

function cancelSortMode() {
  sortMode = false;
  document.body.classList.remove("sort-mode");
  document.getElementById("btn-sort").textContent = "Reordenar";
  document.getElementById("btn-sort").classList.remove("btn");
  document.getElementById("btn-sort").classList.add("btn-ghost");
  destroySortables();
  loadCollection(current);
  flash("Orden descartado");
}

function enableSortables() {
  destroySortables();
  document.querySelectorAll(".section-items").forEach(function(el) {
    sortables.push(Sortable.create(el, {
      animation: 150,
      ghostClass: "sortable-ghost",
      chosenClass: "sortable-chosen",
      group: "poems",
    }));
  });
}

function destroySortables() {
  sortables.forEach(function(s) { s.destroy(); });
  sortables = [];
}

// -- Editor --
function openEditor(file) {
  editingFile = file;
  undoSnapshot = null;

  // Highlight in list
  document.querySelectorAll(".item").forEach(function(el) {
    el.classList.toggle("active", el.dataset.file === file);
  });

  Promise.all([
    api("GET", "/api/entry/" + current + "/" + file),
    api("GET", "/api/collections"),
    api("GET", "/api/collection/" + current),
  ]).then(function(results) {
    var entry = results[0];
    var cols = results[1];
    var col = results[2];

    var moveOpts = '<option value="">Mover a...</option>';
    cols.forEach(function(c) {
      if (c.slug !== current) moveOpts += '<option value="' + c.slug + '">' + esc(c.title) + "</option>";
    });

    var secOpts = "";
    if (col.sections.length) {
      secOpts = '<select class="move-select" id="ed-move-sec"><option value="">Raiz</option>';
      col.sections.forEach(function(s) {
        secOpts += '<option value="' + s.slug + '">' + esc(s.title) + "</option>";
      });
      secOpts += "</select>";
    }

    var tagsVal = (entry.tags || []).join(", ");

    document.getElementById("editor-panel").innerHTML =
      '<div class="editor">'
      + '<div class="row">'
      + '  <div class="field"><label>Titulo</label><input type="text" id="ed-title" value="' + esc(entry.title) + '"></div>'
      + '  <div class="field field-sm"><label>Tipo</label><input type="text" id="ed-type" value="' + esc(entry.entry_type) + '" list="types"></div>'
      + '  <div class="field field-md"><label>Fecha</label><input type="date" id="ed-date" value="' + (entry.date || "") + '"></div>'
      + '</div>'
      + '<datalist id="types"><option value="poem"><option value="interlude"><option value="essay"></datalist>'
      + '<div class="row">'
      + '  <div class="field"><label>Epigrafe</label><input type="text" id="ed-epigraph" value="' + esc(entry.epigraph || "") + '" placeholder="Dedicatoria o nota..."></div>'
      + '  <div class="field"><label>Tags</label><input type="text" id="ed-tags" value="' + esc(tagsVal) + '" placeholder="amor, naturaleza, ..."></div>'
      + '</div>'
      + '<div class="field" style="flex:1;display:flex;flex-direction:column">'
      + '  <label>Contenido <span class="word-count" id="ed-wc"></span></label>'
      + '  <textarea id="ed-body" style="flex:1">' + esc(entry.body) + '</textarea>'
      + '</div>'
      + '<div class="actions">'
      + '  <button class="btn" id="btn-save">Guardar</button>'
      + '  <button class="btn btn-ghost" id="btn-undo" style="display:none">Deshacer</button>'
      + (entry.draft ? '' : '  <a class="btn btn-ghost" id="btn-preview" href="' + previewUrl(file) + '" target="_blank" rel="noopener">Vista previa</a>')
      + '  <button class="btn btn-ghost" id="btn-dup">Duplicar</button>'
      + '  <button class="btn btn-ghost" id="btn-close">Cerrar</button>'
      + '  <span class="spacer"></span>'
      + '  <select class="move-select" id="ed-move-col">' + moveOpts + '</select>'
      + secOpts
      + '  <button class="btn btn-secondary" id="btn-move">Mover</button>'
      + '  <button class="btn btn-danger" id="btn-delete">Eliminar</button>'
      + '</div>'
      + '</div>';

    updateWc();
    lastSavedBody = JSON.stringify(gatherEditorData());

    document.getElementById("btn-save").onclick = saveEntry;
    document.getElementById("btn-close").onclick = closeEditor;
    document.getElementById("btn-move").onclick = moveEntry;
    document.getElementById("btn-delete").onclick = deleteEntry;
    document.getElementById("btn-dup").onclick = duplicateEntry;
    document.getElementById("btn-undo").onclick = undoSave;

    // Autosave on any input change
    ["ed-title", "ed-type", "ed-date", "ed-epigraph", "ed-tags", "ed-body"].forEach(function(id) {
      var el = document.getElementById(id);
      if (el) el.oninput = function() {
        if (id === "ed-body") updateWc();
        scheduleAutosave();
      };
    });
  });
}

function closeEditor() {
  clearTimeout(autosaveTimer);
  editingFile = null;
  lastSavedBody = null;
  undoSnapshot = null;
  document.getElementById("editor-panel").innerHTML = '<div class="editor-empty">Selecciona un poema</div>';
  document.querySelectorAll(".item.active").forEach(function(el) { el.classList.remove("active"); });
}

function previewUrl(file) {
  var slug = file.replace(/\.md$/, "");
  return "http://localhost:4000/poems/" + current + "/" + slug + "/";
}

function updateWc() {
  var el = document.getElementById("ed-body");
  var wc = document.getElementById("ed-wc");
  if (!el || !wc) return;
  var t = el.value.trim();
  var words = t ? t.split(/ +/).length : 0;
  var lines = t ? t.split("\n").filter(function(l) { return l.trim(); }).length : 0;
  wc.textContent = lines + " lineas · " + words + " palabras";
}

function scheduleAutosave() {
  clearTimeout(autosaveTimer);
  if (!editingFile) return;
  autosaveTimer = setTimeout(function() {
    if (!editingFile) return;
    var body = gatherEditorData();
    if (!body) return;
    var snapshot = JSON.stringify(body);
    if (snapshot === lastSavedBody) return;
    undoSnapshot = lastSavedBody;
    lastSavedBody = snapshot;
    api("PUT", "/api/entry/" + current + "/" + editingFile, body).then(function() {
      showUndo();
      flash("Autoguardado");
    });
  }, 2000);
}

function gatherEditorData() {
  var title = document.getElementById("ed-title");
  if (!title) return null;
  return {
    title: title.value,
    entry_type: document.getElementById("ed-type").value,
    epigraph: document.getElementById("ed-epigraph").value,
    tags: parseTags(document.getElementById("ed-tags").value),
    date: document.getElementById("ed-date").value,
    body: document.getElementById("ed-body").value,
  };
}

function parseTags(s) {
  if (!s) return [];
  return s.split(",").map(function(t) { return t.trim(); }).filter(function(t) { return t; });
}

function saveEntry() {
  clearTimeout(autosaveTimer);
  var body = gatherEditorData();
  if (!body) return;
  undoSnapshot = lastSavedBody;
  lastSavedBody = JSON.stringify(body);
  api("PUT", "/api/entry/" + current + "/" + editingFile, body).then(function() {
    loadCollection(current);
    showUndo();
    flash("Guardado");
  });
}

function showUndo() {
  var btn = document.getElementById("btn-undo");
  if (!btn || !undoSnapshot) return;
  btn.style.display = "";
  // Hide after 8s
  setTimeout(function() {
    if (btn) btn.style.display = "none";
  }, 8000);
}

function undoSave() {
  if (!undoSnapshot || !editingFile) return;
  var prev = JSON.parse(undoSnapshot);
  undoSnapshot = null;
  api("PUT", "/api/entry/" + current + "/" + editingFile, prev).then(function() {
    // Reload editor with reverted content
    openEditor(editingFile);
    loadCollection(current);
    flash("Deshecho");
  });
}

function duplicateEntry() {
  if (!editingFile) return;
  var body = gatherEditorData();
  if (!body) return;
  body.title = body.title + " (copia)";
  api("POST", "/api/create/" + current, body).then(function(r) {
    loadCollection(current);
    loadStats();
    flash("Duplicado");
    if (r.file) openEditor(r.file);
  });
}

function moveEntry() {
  var col = document.getElementById("ed-move-col").value;
  if (!col) return flash("Selecciona una coleccion");
  var secEl = document.getElementById("ed-move-sec");
  var sec = secEl ? secEl.value : "";
  api("POST", "/api/move", { from_slug: current, file: editingFile, to_slug: col, to_section: sec || null }).then(function() {
    closeEditor();
    loadCollection(current);
    loadStats();
    init();
    flash("Movido");
  });
}

function deleteEntry() {
  var action = current === "drafts" ? "eliminar permanentemente" : "mover a borradores";
  if (!confirm("¿" + action + "?")) return;
  api("POST", "/api/delete", { slug: current, file: editingFile }).then(function() {
    closeEditor();
    loadCollection(current);
    loadStats();
    flash(current === "drafts" ? "Eliminado" : "Movido a borradores");
  });
}

// -- Create --
document.getElementById("btn-new").onclick = function() {
  editingFile = null;
  document.getElementById("editor-panel").innerHTML =
    '<div class="editor">'
    + '<div class="row">'
    + '  <div class="field"><label>Titulo</label><input type="text" id="ed-title" placeholder="Titulo..."></div>'
    + '  <div class="field field-sm"><label>Tipo</label><input type="text" id="ed-type" value="poem" list="types"></div>'
    + '  <div class="field field-md"><label>Fecha</label><input type="date" id="ed-date"></div>'
    + '</div>'
    + '<datalist id="types"><option value="poem"><option value="interlude"><option value="essay"></datalist>'
    + '<div class="row">'
    + '  <div class="field"><label>Tags</label><input type="text" id="ed-tags" placeholder="amor, naturaleza, ..."></div>'
    + '</div>'
    + '<div class="field" style="flex:1;display:flex;flex-direction:column">'
    + '  <label>Contenido</label>'
    + '  <textarea id="ed-body" placeholder="Escribe aqui..." style="flex:1"></textarea>'
    + '</div>'
    + '<div class="actions">'
    + '  <button class="btn" id="btn-create">Crear</button>'
    + '  <button class="btn btn-ghost" id="btn-cancel-create">Cancelar</button>'
    + '</div>'
    + '</div>';

  document.getElementById("btn-create").onclick = createEntry;
  document.getElementById("btn-cancel-create").onclick = closeEditor;
  document.getElementById("ed-title").focus();
};

function createEntry() {
  var title = document.getElementById("ed-title").value;
  if (!title) return flash("Titulo requerido");
  var body = {
    title: title,
    entry_type: document.getElementById("ed-type").value,
    tags: parseTags(document.getElementById("ed-tags").value),
    date: document.getElementById("ed-date").value,
    body: document.getElementById("ed-body").value || "",
  };
  api("POST", "/api/create/" + current, body).then(function(r) {
    loadCollection(current);
    loadStats();
    flash("Creado");
    if (r.file) openEditor(r.file);
  });
}

// -- Search --
var searchInput = document.getElementById("search");
var searchResults = document.getElementById("search-results");

searchInput.oninput = function() {
  clearTimeout(debounce);
  var q = searchInput.value.trim();
  if (!q) { searchResults.classList.remove("open"); searchResults.innerHTML = ""; return; }
  debounce = setTimeout(function() {
    api("GET", "/api/search?q=" + encodeURIComponent(q)).then(function(results) {
      if (!results.length) {
        searchResults.innerHTML = '<div class="empty-state" style="padding:1rem">Sin resultados</div>';
      } else {
        searchResults.innerHTML = results.map(function(r) {
          return '<div class="search-result" data-go-col="' + r.collection + '" data-go-file="' + r.file + '">'
            + '<div class="sr-title">' + esc(r.title) + (r.draft ? " <em>(borrador)</em>" : "") + '</div>'
            + '<div class="sr-meta">' + esc(r.collection_title) + " · " + r.entry_type + '</div>'
            + '<div class="sr-snippet">' + esc(r.snippet) + '</div>'
            + '</div>';
        }).join("");

        searchResults.querySelectorAll("[data-go-col]").forEach(function(el) {
          el.onclick = function() {
            var targetCol = el.dataset.goCol;
            var targetFile = el.dataset.goFile;
            searchResults.classList.remove("open");
            searchInput.value = "";
            editingFile = targetFile; // set before render so list highlights it
            current = targetCol;
            init().then(function() {
              openEditor(targetFile);
            });
          };
        });
      }
      searchResults.classList.add("open");
    });
  }, 250);
};

document.addEventListener("click", function(e) {
  if (!e.target.closest(".search-box")) {
    searchResults.classList.remove("open");
  }
});

// -- Keyboard navigation --
document.addEventListener("keydown", function(e) {
  // Don't capture when typing in inputs
  var tag = e.target.tagName;
  var inEditor = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";

  // Cmd/Ctrl+S — save from anywhere
  if ((e.metaKey || e.ctrlKey) && e.key === "s") {
    e.preventDefault();
    if (editingFile) saveEntry();
    return;
  }

  // Cmd/Ctrl+N — new entry
  if ((e.metaKey || e.ctrlKey) && e.key === "n") {
    e.preventDefault();
    document.getElementById("btn-new").click();
    return;
  }

  // Cmd/Ctrl+Z — undo (only when not in a text field)
  if ((e.metaKey || e.ctrlKey) && e.key === "z" && !inEditor && undoSnapshot) {
    e.preventDefault();
    undoSave();
    return;
  }

  // Escape — cancel sort mode, close editor, or blur input
  if (e.key === "Escape") {
    if (sortMode) {
      cancelSortMode();
    } else if (inEditor) {
      e.target.blur();
    } else if (editingFile) {
      closeEditor();
    }
    return;
  }

  // Panel switching: h = sidebar, l = list
  if (!inEditor) {
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

  // Arrow keys — navigate within active panel
  if (inEditor) return;

  if (focusPanel === "sidebar") {
    var links = Array.from(document.querySelectorAll(".sidebar a"));
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
    var items = getAllItems();
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
  items.forEach(function(el) { el.classList.remove("focused"); });
  if (focusedIdx >= 0 && focusedIdx < items.length) {
    items[focusedIdx].classList.add("focused");
    items[focusedIdx].scrollIntoView({ block: "nearest" });
  }
}

function clearListFocus() {
  getAllItems().forEach(function(el) { el.classList.remove("focused"); });
}

function highlightSidebar() {
  var links = Array.from(document.querySelectorAll(".sidebar a"));
  links.forEach(function(el) { el.classList.remove("focused"); });
  if (sidebarIdx >= 0 && sidebarIdx < links.length) {
    links[sidebarIdx].classList.add("focused");
    links[sidebarIdx].scrollIntoView({ block: "nearest" });
  }
}

function clearSidebarFocus() {
  document.querySelectorAll(".sidebar a").forEach(function(el) { el.classList.remove("focused"); });
}

// -- Util --
function esc(s) {
  if (!s) return "";
  var d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function flash(msg) {
  var el = document.getElementById("flash");
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(function() { el.classList.remove("show"); }, 2000);
}

// -- Start --
init();
