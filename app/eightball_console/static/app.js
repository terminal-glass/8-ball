/* 8-Ball console UI. No framework, no inline script, no innerHTML with data. */
"use strict";
(() => {
  const $ = (s) => document.querySelector(s);
  const el = (tag, attrs, ...kids) => {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") n.className = v; else if (k === "text") n.textContent = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v); else n.setAttribute(k, v === true ? "" : v);
    }
    for (const k of kids.flat()) if (k !== null && k !== undefined && k !== false) n.append(k.nodeType ? k : String(k));
    return n;
  };
  const S = { me: null, instance: localStorage.getItem("eb.instance") || "local", cat: "all", job: null, es: null, lastSeq: 0, nerds: null };
  const theme = localStorage.getItem("eb.theme") || "auto";
  document.documentElement.dataset.theme = theme;

  async function api(path, opts = {}) {
    const o = { credentials: "same-origin", headers: { Accept: "application/json" }, ...opts };
    if (o.body !== undefined) {
      o.method = o.method || "POST";
      o.headers = { ...o.headers, "Content-Type": "application/json", "X-8Ball": "1" };
      o.body = JSON.stringify(o.body);
    }
    const r = await fetch(path, o);
    let data = null;
    try { data = await r.json(); } catch (_) { data = null; }
    if (!r.ok) throw new Error((data && (data.detail || data.error)) || `HTTP ${r.status}`);
    return data;
  }
  const gb = (b) => (typeof b === "number" && b > 0 ? (b / 1e9 >= 1 ? (b / 1e9).toFixed(2) + " GB" : (b / 1e6).toFixed(0) + " MB") : "unknown");
  const unk = (v, suffix = "") => (v === null || v === undefined || v === "" ? el("span", { class: "eb-unknown", text: "unknown" }) : `${v}${suffix}`);
  const fitTag = (f) => el("span", { class: `eb-fit ${f.color}`, title: (f.reasons || []).join("; ") + " (estimated)", text: f.label });
  const banner = (msg, info) => { const b = $("#eb-banner"); b.textContent = msg || ""; b.hidden = !msg; b.classList.toggle("info", !!info); };

  // ------------------------------------------------------------ routing
  const pages = ["profile", "ollama", "nerds", "console", "settings"];
  function route() {
    let p = (location.hash || "#profile").slice(1).split("/")[0];
    if (!pages.includes(p)) p = "profile";
    for (const x of pages) $(`#page-${x}`).hidden = x !== p;
    document.querySelectorAll(".eb-tabs a").forEach((a) => { if (a.dataset.tab === p) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
    ({ profile: loadProfile, ollama: loadModels, nerds: loadNerds, console: loadConsole, settings: loadSettings })[p]();
  }
  window.addEventListener("hashchange", route);

  // ------------------------------------------------------------ profile
  async function loadProfile() {
    const body = $("#profile-body");
    let d;
    try { d = await api("api/profile"); } catch (e) { body.replaceChildren(el("p", { text: e.message })); return; }
    const p = d.profile;
    const nodes = [];
    const ok = d.status === "valid" || d.status === "stale";
    nodes.push(el("div", { class: "eb-card" }, el("h2", { text: "Profile snapshot" }), el("dl", { class: "eb-kv" },
      el("dt", { text: "Status" }), el("dd", {}, el("strong", { class: ok ? "st-succeeded" : "st-failed", text: d.status }), d.problems.length ? " - " + d.problems.join("; ") : ""),
      el("dt", { text: "Captured" }), el("dd", {}, unk(p && p.captured_at), d.age_days != null ? ` (${d.age_days} days ago)` : ""),
      el("dt", { text: "Platform" }), el("dd", {}, unk(p && p.platform && p.platform.id), p && p.platform && p.platform.authorized ? " (supported)" : ""),
      el("dt", { text: "Catalog" }), el("dd", {}, unk(p && p.catalog && String(p.catalog.commit).slice(0, 12))),
      el("dt", { text: "Fit policy" }), el("dd", { text: d.fit_policy + " (all fit results are estimates)" }))));
    if (p) {
      const c = p.capacity, h = p.host || {}, cl = p.classification || {};
      nodes.push(el("div", { class: "eb-card" }, el("h2", { text: "Hardware" }), el("dl", { class: "eb-kv" },
        el("dt", { text: "OS" }), el("dd", {}, unk(h.os)),
        el("dt", { text: "CPU" }), el("dd", {}, unk(h.cpu_model), c.cpu_threads ? `, ${c.cpu_threads} threads` : ""),
        el("dt", { text: "System RAM" }), el("dd", {}, unk(c.system_ram_gb, " GB")),
        el("dt", { text: "GPU" }), el("dd", {}, (h.gpu_devices || []).length ? h.gpu_devices.map((g) => `${g.vendor}${g.name ? " " + g.name : ""}`).join(", ") : "none detected"),
        el("dt", { text: "GPU VRAM" }), el("dd", {}, unk(c.gpu_vram_gb, " GB")),
        el("dt", { text: "Free disk (models)" }), el("dd", {}, unk(d.live.model_disk_free_gb, " GB now"), c.model_disk_free_gb != null ? ` (${c.model_disk_free_gb} GB at scan)` : ""),
        el("dt", { text: "Cloud provider" }), el("dd", {}, h.cloud_provider || "none detected"))));
      nodes.push(el("div", { class: "eb-card" }, el("h2", { text: "Classification" }), el("dl", { class: "eb-kv" },
        el("dt", { text: "Catalog lane" }), el("dd", {}, unk(p.lane && p.lane.lane_path)),
        el("dt", { text: "Deployment type" }), el("dd", {}, cl.catalog_deployment_type_id ? `type ${cl.catalog_deployment_type_id} (catalog deployment type, not a P# or M tier)` : unk(null)),
        el("dt", { text: "P# identity" }), el("dd", {}, el("span", { class: "eb-unknown", text: "unknown" }), " - " + ((cl.p_identity || {}).reason || "")),
        el("dt", { text: "M tier" }), el("dd", {}, el("span", { class: "eb-unknown", text: "unclassified" }), " - " + ((cl.m_tier || {}).reason || ""))),
        ...(cl.notes || []).map((n) => el("p", { class: "eb-small", text: n }))));
      const un = p.unknowns || [];
      nodes.push(el("div", { class: "eb-card" }, el("h2", { text: `Unknowns (${un.length})` }),
        un.length ? el("ul", {}, un.map((u) => el("li", {}, el("code", { text: u.field }), " - " + u.reason))) : el("p", { class: "eb-small", text: "Every value used for fit was measured." })));
      if (p.suitability) {
        const cnt = p.suitability.counts;
        nodes.push(el("div", { class: "eb-card" }, el("h2", { text: "Happy Nerds tags on this machine" }),
          el("div", { class: "eb-legend" }, Object.entries(d.legend).map(([k, [color, label]]) => el("span", {}, el("span", { class: `eb-fit ${color}`, text: label }), ` ${cnt[k] || 0}`))),
          el("p", { class: "eb-small", text: "Counted at profile build time over every exact tag of the 50 featured families." })));
      }
    } else {
      nodes.push(el("div", { class: "eb-card" }, el("h2", { text: "No usable profile" }),
        el("p", { text: "Run the hardware scan and profile build on this machine, then reload. Until then every fit shows as Unknown." })));
    }
    body.replaceChildren(...nodes);
  }

  // ------------------------------------------------------------ ollama
  async function fillInstances() {
    const sel = $("#inst");
    if (sel.options.length) return;
    const list = await api("api/instances");
    for (const i of list) sel.append(el("option", { value: i.id, text: `${i.label}${i.reachable ? " (Ollama " + i.version + ")" : " (unreachable)"}` }));
    if (!list.find((i) => i.id === S.instance)) S.instance = list[0].id;
    sel.value = S.instance;
    sel.addEventListener("change", () => { S.instance = sel.value; localStorage.setItem("eb.instance", S.instance); loadModels(); });
  }
  async function loadModels() {
    try { await fillInstances(); } catch (e) { banner(e.message); }
    const body = $("#models-body");
    let d;
    try { d = await api(`api/models?instance=${encodeURIComponent(S.instance)}`); } catch (e) { body.replaceChildren(el("p", { text: e.message })); return; }
    offline(d.online);
    const admin = S.me && S.me.role === "admin";
    const rows = d.installed.map((m) => el("tr", {},
      el("td", { "data-l": "Model" }, el("code", { text: m.ref }), " ", el("span", { class: "eb-badge inst", text: "Installed" }), m.running ? el("span", { class: "eb-badge run", text: " Running" }) : null, m.cloud ? el("span", { class: "eb-badge", text: "Cloud" }) : null),
      el("td", { "data-l": "Size", class: "num", text: m.cloud ? "-" : gb(m.size_bytes) }),
      el("td", { "data-l": "Fit" }, fitTag(m.fit), m.in_catalog ? null : el("span", { class: "eb-small", text: " not in catalog" })),
      el("td", { "data-l": "Updated", class: "num", text: (m.modified_at || "").slice(0, 10) }),
      el("td", {}, admin && !m.cloud ? el("button", { class: "eb-btn eb-btn-2 eb-btn-sm", type: "button", onclick: () => askRemove(m.ref), disabled: m.running || null, title: m.running ? "loaded right now" : null, text: "Remove" }) : null)));
    body.replaceChildren(d.installed.length ? el("table", { class: "eb-table" },
      el("thead", {}, el("tr", {}, ["Model", "Size", "Fit (estimated)", "Updated", ""].map((h) => el("th", { text: h })))), el("tbody", {}, rows)) : el("p", { text: "No models installed." }),
      el("p", { class: "eb-small", text: `Free disk for models: ${d.model_disk_free_gb ?? "unknown"} GB. "Installed" means Ollama lists the model; "Fits" is only an estimate.` }));
    renderActiveJobs();
  }
  $("#refresh-models").addEventListener("click", loadModels);
  $("#pull-form").addEventListener("submit", (ev) => { ev.preventDefault(); startPull($("#pull-ref").value.trim()); });

  async function startPull(ref) {
    if (!ref) return;
    try {
      const r = await api("api/jobs/pull", { body: { instance: S.instance, model: ref, idempotency_key: `pull:${S.instance}:${ref}:${Date.now()}` } });
      banner(`Pull of ${r.job.params.model} ${r.created ? "started" : "is already running"}. You can leave this page; the job keeps going.`, true);
      watchJob(r.job.id);
      if (location.hash !== "#ollama") location.hash = "#ollama"; else renderActiveJobs();
    } catch (e) { banner(e.message); }
  }
  const watchers = new Map();
  function watchJob(id) {
    if (watchers.has(id)) return;
    const es = new EventSource(`api/jobs/${id}/events`);
    watchers.set(id, { es, job: null });
    es.addEventListener("progress", (m) => { const ev = JSON.parse(m.data); const w = watchers.get(id); if (w) { w.progress = ev.data; renderActiveJobs(); } });
    es.addEventListener("state", (m) => { const ev = JSON.parse(m.data); const w = watchers.get(id); if (w) { w.state = ev.data.state; w.detail = ev.data.detail; renderActiveJobs(); } });
    es.addEventListener("end", () => { es.close(); setTimeout(() => { watchers.delete(id); renderActiveJobs(); loadModelsIfVisible(); }, 4000); loadModelsIfVisible(); });
  }
  function loadModelsIfVisible() { if (!$("#page-ollama").hidden) loadModels(); if (!$("#page-nerds").hidden) loadNerds(); }
  async function renderActiveJobs() {
    const box = $("#active-jobs");
    const items = [];
    for (const [id, w] of watchers) {
      if (!w.job) { try { w.job = await api(`api/jobs/${id}`); } catch (_) { continue; } }
      const p = w.progress || {};
      const pct = typeof p.percent === "number" ? p.percent : null;
      items.push(el("div", { class: "eb-job" },
        el("div", {}, el("strong", { text: `${w.job.kind} ${w.job.params.model || w.job.params.workflow}` }), " ",
          el("span", { class: `st-${w.state || w.job.state}`, text: w.state || w.job.state }), w.detail ? ` - ${w.detail}` : ""),
        el("div", { class: "eb-progress", role: "progressbar", "aria-valuemin": "0", "aria-valuemax": "100", "aria-valuenow": pct != null ? pct.toFixed(0) : null },
          (() => { const bar = el("div"); bar.style.width = `${pct != null ? pct.toFixed(1) : 0}%`; return bar; })()),
        el("div", { class: "eb-small" }, `${p.status || "waiting"}${pct != null ? ` ${pct.toFixed(1)}% (${gb(p.completed)} of ${gb(p.total)})` : ""} `,
          el("a", { href: `#console/${id}`, text: "Open console" }))));
    }
    box.replaceChildren(...items);
  }
  async function resumeWatchers() {
    try { for (const j of await api("api/jobs")) if (j.state === "running" || j.state === "queued") watchJob(j.id); } catch (_) { /* ignore */ }
  }

  function askRemove(ref) {
    const dlg = $("#confirm-dlg"), inp = $("#dlg-input"), ok = $("#dlg-ok");
    $("#dlg-text").textContent = `This deletes ${ref} from ${S.instance}. Type the exact tag to confirm.`;
    inp.value = ""; ok.disabled = true;
    inp.oninput = () => { ok.disabled = inp.value.trim() !== ref; };
    dlg.onclose = async () => {
      if (dlg.returnValue !== "ok") return;
      try { const r = await api("api/jobs/remove", { body: { instance: S.instance, model: ref, confirm: inp.value.trim() } }); watchJob(r.job.id); banner(`Removing ${ref}.`, true); renderActiveJobs(); }
      catch (e) { banner(e.message); }
    };
    dlg.showModal();
  }

  // ------------------------------------------------------------ nerds
  async function loadNerds() {
    try { await fillInstances(); } catch (_) { /* shown elsewhere */ }
    let d;
    try { d = await api(`api/nerds?instance=${encodeURIComponent(S.instance)}`); } catch (e) { $("#nerds-body").replaceChildren(el("p", { text: e.message })); return; }
    S.nerds = d; offline(d.online);
    $("#legend").replaceChildren(...Object.values(d.legend).map(([c, l]) => el("span", { class: `eb-fit ${c}`, text: l })),
      el("span", { class: "eb-small", text: "Installed is shown separately from fit. All fit values are estimates." }));
    if (d.profile_status !== "valid") banner(`Host profile is ${d.profile_status}; fit is shown as Unknown until a valid profile exists.`);
    const cats = $("#nerd-cats");
    cats.replaceChildren(...[{ id: "all", label: "All" }, ...d.categories].map((c) => el("button", { type: "button", class: "eb-btn eb-btn-2 eb-btn-sm eb-cat", role: "tab", "aria-selected": String(S.cat === c.id), onclick: () => { S.cat = c.id; loadNerdsRender(); cats.querySelectorAll("button").forEach((b) => b.setAttribute("aria-selected", String(b.textContent === c.label))); }, text: c.label })));
    loadNerdsRender();
  }
  function loadNerdsRender() {
    const d = S.nerds; if (!d) return;
    const all = $("#show-all").checked, admin = S.me && S.me.role === "admin";
    const cards = d.families.filter((f) => S.cat === "all" || f.category === S.cat).map((f) => {
      const rank = { fits: 0, constrained: 1, unknown: 2, cloud: 3, rejected: 4 };
      const vs = f.variants.filter((v) => all || v.installed || v.fit.state !== "rejected")
        .sort((a, b) => (b.installed - a.installed) || ((b.ref === f.suggested_ref) - (a.ref === f.suggested_ref))
          || (rank[a.fit.state] - rank[b.fit.state]) || ((b.download_size_bytes || 0) - (a.download_size_bytes || 0)));
      const limit = all ? vs.length : 8;
      const sug = f.suggested_ref;
      return el("div", { class: "eb-card" },
        el("h3", {}, f.display_name, " ", el("span", { class: "eb-badge", text: (d.categories.find((c) => c.id === f.category) || {}).label || f.category }),
          f.installed_refs.length ? el("span", { class: "eb-badge inst", text: ` Installed: ${f.installed_refs.length}` }) : null),
        el("p", { class: "eb-small", text: f.bot_line }),
        f.kind === "embedding" ? el("p", { class: "eb-small", text: "Embedding model: used by apps for search, not for chat." }) : null,
        sug ? el("p", { class: "eb-small" }, "Suggested here: ", el("code", { text: sug })) : el("p", { class: "eb-small", text: "No local variant fits this machine by the estimates." }),
        el("ul", { class: "eb-variants" }, vs.slice(0, limit).map((v) => el("li", {},
          el("code", { text: v.ref }), fitTag(v.fit), v.installed ? el("span", { class: "eb-badge inst", text: "Installed" }) : null,
          el("span", { class: "grow", text: v.cloud ? "cloud" : `${gb(v.download_size_bytes)} download` }),
          admin && !v.cloud && !v.installed && v.fit.state !== "rejected" ? el("button", { type: "button", class: "eb-btn eb-btn-sm", disabled: !d.online || null, title: d.online ? null : "offline", onclick: () => startPull(v.ref), text: "Pull" }) : null)),
          vs.length > limit ? el("li", { class: "eb-small", text: `${vs.length - limit} more; tick 'Show every variant' to list them` }) : null,
          vs.length === 0 ? el("li", { class: "eb-small", text: "No variant fits; tick 'Show every variant' to see rejected ones." }) : null));
    });
    $("#nerds-body").replaceChildren(...cards);
  }
  $("#show-all").addEventListener("change", loadNerdsRender);

  // ------------------------------------------------------------ console
  async function loadConsole() {
    const want = (location.hash.split("/")[1]) || S.job;
    let jobs = [];
    try { jobs = await api("api/jobs"); } catch (e) { banner(e.message); }
    const list = $("#job-list");
    list.replaceChildren(...jobs.map((j) => el("li", {}, el("button", { type: "button", "aria-current": String(j.id === want), onclick: () => { location.hash = `#console/${j.id}`; } },
      el("strong", { text: `${j.kind} ${j.params.model || j.params.workflow}` }), el("br"), el("span", { class: `st-${j.state}`, text: j.state }), ` ${(j.created_at || "").replace("T", " ").slice(0, 19)}Z`))));
    if (!jobs.length) list.replaceChildren(el("li", { class: "eb-small", text: "No jobs yet." }));
    try {
      const wfs = await api("api/workflows"), admin = S.me && S.me.role === "admin";
      $("#wf-list").replaceChildren(...Object.entries(wfs).filter(([id]) => id !== "model-refresh").map(([id, w]) => el("div", { class: "eb-card" },
        el("h3", { text: w.label }), el("p", { class: "eb-small", text: w.description }),
        admin ? el("button", { type: "button", class: "eb-btn eb-btn-sm", onclick: async () => {
          try { const r = await api("api/jobs/upgrade", { body: { instance: S.instance, workflow: id } }); location.hash = `#console/${r.job.id}`; } catch (e) { banner(e.message); } }, text: "Run" }) : null)));
    } catch (_) { /* ignore */ }
    if (want && want !== S.job) attach(want);
    else if (!want && jobs[0]) attach(jobs[0].id);
  }
  async function attach(id) {
    S.job = id; S.lastSeq = 0;
    if (S.es) S.es.close();
    const log = $("#log"); log.textContent = "";
    let job;
    try { job = await api(`api/jobs/${id}`); } catch (e) { log.textContent = e.message; return; }
    $("#job-head").replaceChildren(el("strong", { text: `${job.kind} ${job.params.model || job.params.workflow}` }), el("span", { id: "job-state", class: `st-${job.state}`, text: job.state }), el("code", { class: "eb-small", text: id }));
    $("#cancel-job").disabled = !(S.me && S.me.role === "admin") || ["succeeded", "failed", "cancelled", "interrupted"].includes(job.state);
    streamLog(id);
    tty(id);
  }
  function streamLog(id) {
    if (S.es) S.es.close();
    const log = $("#log");
    const es = new EventSource(`api/jobs/${id}/events?after=${S.lastSeq}`);
    S.es = es;
    const line = (ev) => {
      S.lastSeq = Math.max(S.lastSeq, ev.seq);
      let t = null;
      if (ev.type === "log") t = ev.msg;
      else if (ev.type === "state") { t = `== ${ev.data.state}${ev.data.detail ? ": " + ev.data.detail : ""}`; const s = $("#job-state"); if (s) { s.textContent = ev.data.state; s.className = `st-${ev.data.state}`; }
        if (["succeeded", "failed", "cancelled", "interrupted"].includes(ev.data.state)) $("#cancel-job").disabled = true; }
      else if (ev.type === "progress" && ev.data && !ev.data._quiet) t = `${ev.data.status}${typeof ev.data.percent === "number" ? " " + ev.data.percent.toFixed(1) + "%" : ""}`;
      if (t === null) return;
      const stick = log.scrollTop + log.clientHeight >= log.scrollHeight - 8;
      log.append(`[${ev.ts.slice(11, 19)}Z] ${t}\n`);
      if (stick) log.scrollTop = log.scrollHeight;
    };
    for (const t of ["log", "state", "progress"]) es.addEventListener(t, (m) => line(JSON.parse(m.data)));
    es.addEventListener("end", () => es.close());
  }
  async function tty(id) {
    const wrap = $("#tty-wrap"), frame = $("#tty");
    if (!$("#use-tty").checked || !(S.me && S.me.console_enabled)) { wrap.hidden = true; frame.removeAttribute("src"); return; }
    try { const t = await api(`api/console/${id}/token`); frame.src = t.url; wrap.hidden = false; }
    catch (_) { wrap.hidden = true; }
  }
  $("#reconnect").addEventListener("click", () => { if (S.job) { streamLog(S.job); tty(S.job); } });
  $("#use-tty").addEventListener("change", () => S.job && tty(S.job));
  $("#copy-log").addEventListener("click", () => navigator.clipboard && navigator.clipboard.writeText($("#log").textContent));
  $("#cancel-job").addEventListener("click", async () => {
    if (!S.job || !confirm("Cancel this job?")) return;
    try { await api(`api/jobs/${S.job}/cancel`, { body: {} }); } catch (e) { banner(e.message); }
  });
  window.addEventListener("hashchange", () => { const id = location.hash.split("/")[1]; if (location.hash.startsWith("#console") && id && id !== S.job) attach(id); });

  // ------------------------------------------------------------ settings
  async function loadSettings() {
    const m = S.me || {};
    let inst = [];
    try { inst = await api("api/instances"); } catch (_) { /* ignore */ }
    $("#settings-body").replaceChildren(
      el("div", { class: "eb-card" }, el("h2", { text: "Console" }), el("dl", { class: "eb-kv" },
        el("dt", { text: "Version" }), el("dd", { text: m.version }), el("dt", { text: "Signed in as" }), el("dd", { text: `${m.name} (${m.role})` }),
        el("dt", { text: "Auth mode" }), el("dd", { text: m.auth_mode }), el("dt", { text: "Catalog commit" }), el("dd", { text: m.catalog_commit }),
        el("dt", { text: "Network" }), el("dd", { text: `${m.online ? "online" : "offline (pulls disabled)"}; offline setting: ${m.offline_mode}` }),
        el("dt", { text: "Terminal view" }), el("dd", { text: m.console_enabled ? "enabled (read-only job logs)" : "disabled" }))),
      el("div", { class: "eb-card" }, el("h2", { text: "Ollama instances" }), el("p", { class: "eb-small", text: "Instances are fixed in the server config; the browser can only choose one by id." }),
        el("ul", {}, inst.map((i) => el("li", {}, `${i.label} (${i.id}): `, i.reachable ? `Ollama ${i.version}` : el("span", { class: "st-failed", text: "unreachable" }))))),
      el("div", { class: "eb-card" }, el("h2", { text: "About" }), el("p", { class: "eb-small", text: "8-Ball console: open source, see app/LICENSES.md in the 8-Ball repository. It talks only to the native Ollama REST API and never exposes a shell." })));
    $("#theme").value = localStorage.getItem("eb.theme") || "auto";
  }
  $("#theme").addEventListener("change", (e) => { localStorage.setItem("eb.theme", e.target.value); document.documentElement.dataset.theme = e.target.value; });

  function offline(online) {
    $("#pull-btn").disabled = !online || !(S.me && S.me.role === "admin");
    if (!online) banner("Offline: pulls and cloud actions are disabled. Installed models still work.");
  }

  async function boot() {
    try { S.me = await api("api/whoami"); } catch (e) { banner(e.message); }
    if (S.me) $("#eb-status").textContent = `${S.me.name} · ${S.me.online ? "online" : "offline"}`;
    resumeWatchers();
    route();
  }
  boot();
})();
