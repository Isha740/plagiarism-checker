(() => {
  const MODES = ["compare", "reference"];
  const LABELS = { cosine: "Word cosine", phrase_overlap: "Phrase overlap", sentence_match: "Sentences matched",
                   sequence: "Word order", semantic: "Meaning" };
  const S = {};
  MODES.forEach(m => S[m] = { docs: [], ref: null, limits: { max_docs: 0, min_docs_to_compare: 2 }, useRef: false, busy: false });

  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const sev = (p) => p >= 60 ? "high" : p >= 30 ? "mid" : "low";
  const stroke = (p) => `<div class="stroke ${sev(p)}"><div class="track"><div class="fill" style="--w:${Math.min(p, 100)}%"></div></div><b>${p.toFixed(1)}%</b></div>`;
  const chips = (f) => `<div class="chips">${Object.entries(f).map(([k, v]) => `<span class="chip">${LABELS[k] || k} <b>${v.toFixed(0)}%</b></span>`).join("")}</div>`;

  function highlight(text, other) {
    const common = new Set((other.toLowerCase().match(/[a-z0-9']+/g) || []).filter(w => w.length > 3));
    return text.split(/([A-Za-z0-9']+)/).map((part, i) =>
      i % 2 && part.length > 3 && common.has(part.toLowerCase()) ? `<mark>${esc(part)}</mark>` : esc(part)).join("");
  }

  function toast(msg, ok) {
    const t = $("toast");
    if (!msg) { t.hidden = true; return; }
    t.textContent = msg; t.className = "toast" + (ok ? " ok" : ""); t.hidden = false;
  }

  async function api(path, opts) {
    const r = await fetch(path, opts);
    let data = {};
    try { data = await r.json(); } catch (e) { /* non-JSON error */ }
    if (!r.ok) throw new Error(data.error || "Something went wrong (" + r.status + ")");
    return data;
  }

  // ----layout
  const dropHTML = (mode, kind, multiple, title) => `
    <label class="drop" data-mode="${mode}" data-kind="${kind}">
      <input type="file" ${multiple ? "multiple" : ""} accept=".txt,.pdf,.docx" data-mode="${mode}" data-kind="${kind}">
      <strong>${title}</strong> or drop ${multiple ? "them" : "it"} here<br>
      <small>.txt, .pdf, .docx · up to 5 MB each</small>
    </label>`;

  function build() {
    $("panels").innerHTML = `
    <section class="panel" id="panel-compare" role="tabpanel" aria-labelledby="tab-compare">
      <div class="grid">
        <div>
          <h2>Documents</h2>
          <p class="sub">Upload one or many. Every document is compared with all the others.</p>
          ${dropHTML("compare", "doc", true, "Choose documents")}
          <div class="count"><span>Uploaded documents</span><span id="count-compare"></span></div>
          <ul class="list" id="list-compare"></ul>
        </div>
        <div>
          <h2>Reference document</h2>
          <p class="sub">Optional. Turn on to also see how close each document is to one source text.</p>
          <label class="toggle"><input type="checkbox" id="useref-compare">
            <span>Also compare with a reference document<small>Adds a second table with each document's similarity to the reference.</small></span></label>
          <div class="refbox" id="refbox-compare" hidden>
            ${dropHTML("compare", "ref", false, "Choose the reference")}
            <ul class="list" id="reflist-compare" style="margin-top:10px"></ul>
          </div>
        </div>
      </div>
      <div class="runbar"><button class="btn" id="run-compare">Compare documents</button><span class="hint" id="hint-compare"></span></div>
      <div class="results" id="results-compare" aria-live="polite"></div>
    </section>

    <section class="panel" id="panel-reference" role="tabpanel" aria-labelledby="tab-reference" hidden>
      <div class="grid">
        <div>
          <h2>Reference document</h2>
          <p class="sub">The source text every assignment is checked against.</p>
          ${dropHTML("reference", "ref", false, "Choose the reference")}
          <ul class="list" id="reflist-reference" style="margin-top:10px"></ul>
        </div>
        <div>
          <h2>Assignments</h2>
          <p class="sub">Upload one or many. They are compared only with the reference.</p>
          ${dropHTML("reference", "doc", true, "Choose assignments")}
          <div class="count"><span>Uploaded assignments</span><span id="count-reference"></span></div>
          <ul class="list" id="list-reference"></ul>
        </div>
      </div>
      <div class="runbar"><button class="btn" id="run-reference">Check against reference</button><span class="hint" id="hint-reference"></span></div>
      <div class="results" id="results-reference" aria-live="polite"></div>
    </section>`;
  }

  // ----- state -> DOM
  const liDoc = (d, mode) => `<li><span class="nm">${esc(d.name)}</span><span class="meta">${d.words.toLocaleString()} words</span>
      <button class="del" data-id="${d.id}" data-mode="${mode}" aria-label="Delete ${esc(d.name)}">Delete</button></li>`;

  function renderLists(mode) {
    const s = S[mode];
    const list = $("list-" + mode);
    list.innerHTML = s.docs.length ? s.docs.map(d => liDoc(d, mode)).join("")
      : `<li class="empty">Nothing uploaded yet</li>`;
    $("count-" + mode).textContent = `${s.docs.length} / ${s.limits.max_docs}`;
    const rl = $("reflist-" + mode);
    if (rl) rl.innerHTML = s.ref ? liDoc(s.ref, mode) : `<li class="empty">No reference uploaded</li>`;
    if (mode === "compare") $("refbox-compare").hidden = !s.useRef;
    updateRun(mode);
  }

  function updateRun(mode) {
    const s = S[mode], btn = $("run-" + mode), hint = $("hint-" + mode);
    let msg = "";
    if (mode === "compare") {
      const need = s.limits.min_docs_to_compare - s.docs.length;
      if (need > 0) msg = `Upload at least ${s.limits.min_docs_to_compare} documents to compare (${s.docs.length} uploaded).`;
      else if (s.useRef && !s.ref) msg = "Upload a reference document, or switch the reference option off.";
    } else {
      if (!s.ref) msg = "Upload a reference document.";
      else if (!s.docs.length) msg = "Upload at least 1 assignment.";
    }
    btn.disabled = !!msg || s.busy;
    hint.textContent = msg || (mode === "compare" ? `${s.docs.length} documents ready.` : `${s.docs.length} assignments ready.`);
  }

  async function refresh(mode, keepResults) {
    const d = await api("/api/state?mode=" + mode);
    Object.assign(S[mode], { docs: d.docs, ref: d.ref, limits: d.limits });
    if (!keepResults) $("results-" + mode).innerHTML = "";
    renderLists(mode);
  }

  // ----- actions
  async function upload(mode, kind, files) {
    if (!files.length) return;
    const fd = new FormData();
    fd.append("mode", mode); fd.append("kind", kind);
    [...files].forEach(f => fd.append("files", f));
    try {
      const r = await api("/api/upload", { method: "POST", body: fd });
      const msgs = [];
      if (r.added.length) msgs.push(`Added ${r.added.length} file${r.added.length > 1 ? "s" : ""}.`);
      msgs.push(...r.errors);
      toast(msgs.join("\n"), !r.errors.length);
      await refresh(mode);
    } catch (e) { toast(e.message); }
  }

  async function remove(mode, id) {
    try { await api("/api/docs/" + id, { method: "DELETE" }); toast(""); await refresh(mode); }
    catch (e) { toast(e.message); }
  }

  async function run(mode) {
    const s = S[mode];
    s.busy = true; updateRun(mode);
    const out = $("results-" + mode);
    out.innerHTML = `<p class="hint">Comparing…</p>`;
    try {
      const data = await api("/api/compare", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode, use_ref: s.useRef }) });
      toast("");
      renderResults(mode, data);
    } catch (e) { out.innerHTML = ""; toast(e.message); }
    s.busy = false; updateRun(mode);
  }

  // ------ results
  function renderResults(mode, data) {
    const out = $("results-" + mode);
    let html = "";
    if (mode === "compare") {
      html = `<div class="tablewrap"><table><thead><tr><th>Document</th><th>Max similarity</th><th>Most similar to</th>${data.use_ref ? "<th>Similarity with reference</th>" : ""}</tr></thead><tbody>
        ${data.table.map(e => `<tr class="pick" data-doc="${e.doc_id}"><td class="fname">${esc(e.name)}</td>
          <td>${stroke(e.best ? e.best.score : 0)}</td><td>${e.best ? esc(e.best.other_name) : "–"}</td>
          ${data.use_ref ? `<td>${stroke(e.ref_score || 0)}</td>` : ""}</tr>`).join("")}
        </tbody></table></div>
        <div class="inspect"><label>Select a document
          <select id="inspect-compare">${data.table.map(e => `<option value="${e.doc_id}">${esc(e.name)}</option>`).join("")}</select></label>
          <div id="detail-compare"></div></div>`;
    } else {
      html = `<div class="tablewrap"><table><thead><tr><th>Document</th><th>Similarity with reference</th></tr></thead><tbody>
        ${data.ref_table.map(e => `<tr><td class="fname">${esc(e.name)}</td><td>${stroke(e.score)}</td></tr>`).join("")}
        </tbody></table></div>`;
    }
    out.innerHTML = html;
    out._data = data;
    if (mode === "compare") showDetail(data.table[0].doc_id);
  }

  function showDetail(docId) {
    const data = $("results-compare")._data;
    const e = data.table.find(x => x.doc_id == docId);
    $("inspect-compare").value = String(docId);
    $("detail-compare").innerHTML = e && e.best ? `<div class="detail">
        <div>${stroke(e.best.score)}</div>
        <div class="with">Max similarity with <strong>${esc(e.best.other_name)}</strong></div>
        ${chips(e.best.factors)}</div>` : `<p class="hint">No similar document found.</p>`;
  }

  // ------ events
  function setTab(mode) {
    MODES.forEach(m => {
      $("tab-" + m).setAttribute("aria-selected", String(m === mode));
      $("panel-" + m).hidden = m !== mode;
    });
    toast("");
  }

  function init() {
    build();
    $("tab-compare").onclick = () => setTab("compare");
    $("tab-reference").onclick = () => setTab("reference");

    document.addEventListener("change", (e) => {
      const t = e.target;
      if (t.matches('input[type="file"]')) { upload(t.dataset.mode, t.dataset.kind, t.files).then(() => { t.value = ""; }); }
      else if (t.id === "useref-compare") {
        S.compare.useRef = t.checked; $("refbox-compare").hidden = !t.checked;
        $("results-compare").innerHTML = ""; updateRun("compare");
      } else if (t.id === "inspect-compare") {
        showDetail(t.value);
      }
    });
    document.addEventListener("click", (e) => {
      const del = e.target.closest(".del");
      if (del) { remove(del.dataset.mode, del.dataset.id); return; }
      const row = e.target.closest("tr.pick");
      if (row) {
        showDetail(row.dataset.doc);
        $("inspect-compare").scrollIntoView({ behavior: "smooth", block: "center" });
      }
    });
    document.querySelectorAll(".drop").forEach(z => {
      z.addEventListener("dragover", (e) => { e.preventDefault(); z.classList.add("over"); });
      z.addEventListener("dragleave", () => z.classList.remove("over"));
      z.addEventListener("drop", (e) => {
        e.preventDefault(); z.classList.remove("over");
        let files = e.dataTransfer.files;
        if (z.dataset.kind === "ref") files = [...files].slice(0, 1);
        upload(z.dataset.mode, z.dataset.kind, files);
      });
    });
    $("run-compare").onclick = () => run("compare");
    $("run-reference").onclick = () => run("reference");
    MODES.forEach(m => refresh(m).catch(e => toast(e.message)));
  }
  init();
})();
