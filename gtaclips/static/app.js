// HYPECUT dashboard — vanilla JS, no build step.
"use strict";

// ------------------------------------------------------------------ icons
const P = {
  home: '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',
  film: '<rect x="3" y="3" width="18" height="18" rx="2.5"/><path d="M7 3v18M17 3v18M3 8h4M3 16h4M17 8h4M17 16h4"/>',
  radio: '<circle cx="12" cy="12" r="2.5"/><path d="M16.2 7.8a6 6 0 0 1 0 8.4M7.8 16.2a6 6 0 0 1 0-8.4M19 5a10 10 0 0 1 0 14M5 19A10 10 0 0 1 5 5"/>',
  upload: '<path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>',
  calendar: '<rect x="3" y="4.5" width="18" height="16.5" rx="2.5"/><path d="M3 9.5h18M8 2.5v4M16 2.5v4"/>',
  chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  play: '<path d="M7 4.5v15l12.5-7.5z" fill="currentColor"/>',
  check: '<path d="M4.5 12.5l5 5 10-11"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  zap: '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
  refresh: '<path d="M20 11a8 8 0 0 0-14.9-3.9M4 4v4h4M4 13a8 8 0 0 0 14.9 3.9M20 20v-4h-4"/>',
  download: '<path d="M12 4v12M7 11l5 5 5-5M4 20h16"/>',
  trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
  eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  dollar: '<path d="M12 2v20M17 6.5c-.8-1.5-2.6-2.5-5-2.5-3 0-5 1.5-5 3.8 0 5.2 10 2.6 10 8 0 2.3-2.2 4-5 4-2.6 0-4.5-1-5.4-2.7"/>',
  flame: '<path d="M12 22c4.4 0 7-3 7-7 0-5-4-7-5-11-2 2-2.5 4-2 6-1.5-1-2.5-2-3-4C6 9 5 11.5 5 15c0 4 2.6 7 7 7z"/>',
  sparkles: '<path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>',
  lock: '<rect x="4" y="10.5" width="16" height="10.5" rx="2.5"/><path d="M8 10.5V7a4 4 0 0 1 8 0v3.5"/>',
  link: '<path d="M10 14a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1M14 10a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor"/>',
  scan: '<path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3"/><circle cx="12" cy="11" r="3"/><path d="M7 18c1-2 3-3 5-3s4 1 5 3"/>',
  alert: '<path d="M12 3L2 20h20z"/><path d="M12 10v4M12 17v.5"/>',
  chat: '<path d="M4 5h16v11H9l-5 4z"/>',
  activity: '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
  wand: '<path d="M4 20L16 8M14 4v2M20 10h-2M18 6l-1.5 1.5M12 2l.5 1.5M22 12l-1.5.5"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  ext: '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/>',
  shield: '<path d="M12 2l8 3v6c0 5-3.5 9-8 11-4.5-2-8-6-8-11V5z"/><path d="M9 12l2 2 4-4"/>',
  sliders: '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
  palette: '<path d="M12 3a9 9 0 1 0 0 18c1 0 1.5-.8 1.5-1.5 0-1-.8-1.4-.8-2.3 0-.9.7-1.7 1.7-1.7H17a4 4 0 0 0 4-4C21 6.6 17 3 12 3z"/><circle cx="7.5" cy="11" r="1.2" fill="currentColor"/><circle cx="10.5" cy="7.5" r="1.2" fill="currentColor"/><circle cx="15" cy="7.5" r="1.2" fill="currentColor"/>',
  cpu: '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
  logout: '<path d="M15 4h4a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-4M10 17l-5-5 5-5M5 12h11"/>',
  left: '<path d="M15 5l-7 7 7 7"/>',
  right: '<path d="M9 5l7 7-7 7"/>',
  yt: '<path d="M21.6 7.2a2.5 2.5 0 0 0-1.8-1.8C18.2 5 12 5 12 5s-6.2 0-7.8.4A2.5 2.5 0 0 0 2.4 7.2 26 26 0 0 0 2 12a26 26 0 0 0 .4 4.8 2.5 2.5 0 0 0 1.8 1.8C5.8 19 12 19 12 19s6.2 0 7.8-.4a2.5 2.5 0 0 0 1.8-1.8A26 26 0 0 0 22 12a26 26 0 0 0-.4-4.8z" fill="currentColor" stroke="none"/><path d="M10 15l5-3-5-3z" fill="#000" stroke="none"/>',
  ig: '<rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1" fill="currentColor"/>',
  logo: '<path d="M8 5l12 7-12 7z" fill="#fff" stroke="none"/><path d="M3 8.5h3M2 12h4M3 15.5h3" stroke="#29e7ff" stroke-width="2.4"/>',
};
const ic = (n, cls = "") => `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${P[n] || ""}</svg>`;

// ------------------------------------------------------------------ helpers
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtNum = (n) => { n = Number(n || 0); return n >= 1e6 ? (n / 1e6).toFixed(1).replace(/\.0$/, "") + "M" : n >= 1e3 ? (n / 1e3).toFixed(1).replace(/\.0$/, "") + "K" : String(Math.round(n)); };
const fmtMoney = (n, cur = "$") => cur + Number(n || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fmtDur = (s) => { s = Math.round(s || 0); const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60; return h ? `${h}h ${String(m).padStart(2, "0")}m` : `${m}:${String(x).padStart(2, "0")}`; };
const ago = (iso) => { if (!iso) return ""; const d = (Date.now() - new Date(iso)) / 1000; if (d < 45) return "just now"; if (d < 3600) return `${Math.round(d / 60)}m ago`; if (d < 86400) return `${Math.round(d / 3600)}h ago`; return `${Math.round(d / 86400)}d ago`; };
const timeOf = (iso) => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
const dayOf = (iso) => { const d = new Date(iso), t = new Date(); const y = new Date(); y.setDate(t.getDate() + 1); if (d.toDateString() === t.toDateString()) return "Today"; if (d.toDateString() === y.toDateString()) return "Tomorrow"; return d.toLocaleDateString([], { weekday: "long", month: "short", day: "numeric" }); };
const toLocalInput = (iso) => { const d = new Date(iso); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 16); };
const debounce = (fn, ms = 250) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
const PLAT = { twitch: "Twitch", kick: "Kick", youtube: "YouTube", other: "Web", instagram: "Instagram" };
const SIG = { audio: ["Audio", "#ff2e88"], motion: ["Action", "#ff8a3d"], chat: ["Chat", "#29e7ff"], speech: ["Speech", "#b6ff3b"], game: ["Game", "#8b5cf6"] };

async function api(path, opts = {}) {
  const init = { method: opts.method || "GET", credentials: "same-origin", headers: { "X-GTAClips": "1" } };
  if (opts.body instanceof FormData) init.body = opts.body;
  else if (opts.body !== undefined) { init.body = JSON.stringify(opts.body); init.headers["Content-Type"] = "application/json"; }
  const r = await fetch(path, init);
  if (r.status === 401 && !path.startsWith("/api/auth")) { S.authed = false; renderAuth(); throw new Error("Signed out"); }
  const ct = r.headers.get("content-type") || "";
  const data = ct.includes("json") ? await r.json() : await r.text();
  if (!r.ok) throw new Error((data && data.detail) || `Request failed (${r.status})`);
  return data;
}

function toast(msg, kind = "ok", ms = 3800) {
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.innerHTML = `${ic(kind === "err" ? "alert" : kind === "hype" ? "flame" : "check")}<span>${esc(msg)}</span>`;
  $("#toasts").appendChild(el);
  setTimeout(() => { el.style.transition = "0.3s"; el.style.opacity = "0"; el.style.transform = "translateY(10px)"; setTimeout(() => el.remove(), 300); }, ms);
}
const fail = (e) => toast(e.message || String(e), "err", 6000);

function modal(html, { wide = false, onClose } = {}) {
  const back = document.createElement("div");
  back.className = "modal-back";
  back.innerHTML = `<div class="modal ${wide ? "wide" : ""}" role="dialog" aria-modal="true" style="position:relative">${html}</div>`;
  const close = () => { back.remove(); document.removeEventListener("keydown", onKey); onClose && onClose(); };
  const onKey = (e) => { if (e.key === "Escape") close(); };
  back.addEventListener("mousedown", (e) => { if (e.target === back) close(); });
  document.addEventListener("keydown", onKey);
  $("#modal-root").appendChild(back);
  back.close = close;
  return back;
}

function confirmBox(title, text, okLabel = "Confirm", danger = false) {
  return new Promise((res) => {
    const m = modal(`<h2>${esc(title)}</h2><p class="muted">${esc(text)}</p>
      <div class="row" style="justify-content:flex-end;margin-top:20px"><button class="btn ghost" data-no>Cancel</button><button class="btn ${danger ? "danger" : "primary"}" data-yes>${esc(okLabel)}</button></div>`,
      { onClose: () => res(false) });
    $("[data-no]", m).onclick = () => m.close();
    $("[data-yes]", m).onclick = () => { res(true); m.close(); };
  });
}

// ------------------------------------------------------------------ state
const S = {
  authed: false, configured: true, route: "dashboard", params: new URLSearchParams(),
  overview: null, clips: [], streamers: [], runs: [], posts: [], settings: null, status: null,
  scores: {}, events: [], reviewTab: "ready", settingsTab: "accounts", es: null,
};

// ------------------------------------------------------------------ auth screen
function renderAuth() {
  if (S.es) { S.es.close(); S.es = null; }
  const setup = !S.configured;
  $("#app").innerHTML = `
  <div class="auth"><div class="auth-card">
    <div class="auth-logo">${ic("logo")}</div>
    <h1 class="grad-text">HYPECUT</h1>
    <div class="tag">GTA clip engine · owner only</div>
    <form id="auth-form" autocomplete="on">
      ${setup ? `
        <label class="field">Setup code <span class="hint">Printed in the server console on first start</span>
          <input class="input big mono" name="code" placeholder="XXXX-XXXX-XXXX" autocomplete="one-time-code" required></label>
        <label class="field">Create your password <span class="hint">At least 8 characters. Only you will know it.</span>
          <input class="input big" type="password" name="password" minlength="8" autocomplete="new-password" required></label>
      ` : `
        <input type="text" name="username" value="owner" autocomplete="username" hidden>
        <input class="input big" type="password" name="password" placeholder="Password" autocomplete="current-password" required autofocus>
      `}
      <div class="err" id="auth-err"></div>
      <button class="btn primary lg" type="submit">${setup ? "Create & enter" : "Enter"} ${ic("right")}</button>
    </form>
    <div class="lock-note">${ic("lock")} Private dashboard — one owner, locked after 5 wrong tries</div>
  </div></div>`;
  $("#auth-form").onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const btn = $("button[type=submit]", e.target);
    btn.disabled = true;
    try {
      await api(setup ? "/api/auth/setup" : "/api/auth/login", { method: "POST", body: Object.fromEntries(fd) });
      S.authed = true;
      boot();
    } catch (err) { $("#auth-err").textContent = err.message; btn.disabled = false; }
  };
}

// ------------------------------------------------------------------ shell
const NAV = [
  ["dashboard", "Command", "home"],
  ["review", "Review", "film"],
  ["streams", "Streams", "radio"],
  ["vod", "VOD Lab", "upload"],
  ["schedule", "Schedule", "calendar"],
  ["analytics", "Money", "chart"],
  ["settings", "Settings", "gear"],
];

function renderShell() {
  $("#app").innerHTML = `
  <div class="shell">
    <aside class="sidebar">
      <a class="brand" href="#/"><div class="brand-mark">${ic("logo")}</div><div><div class="brand-name">HYPECUT</div><div class="brand-sub">GTA clip engine</div></div></a>
      <nav class="nav">${NAV.map(([id, label, icon]) => `<a href="#/${id === "dashboard" ? "" : id}" data-nav="${id}">${ic(icon)}<span>${label}</span>${id === "review" ? '<span class="count hidden" id="nav-review-count"></span>' : ""}</a>`).join("")}</nav>
      <div class="sidebar-foot">
        <div class="live-pill" id="live-pill"><span class="dot"></span><span>No live streams</span></div>
        <button class="btn ghost sm" id="logout">${ic("logout")} Sign out</button>
      </div>
    </aside>
    <main class="main" id="page"></main>
  </div>`;
  $("#logout").onclick = async () => { await api("/api/auth/logout", { method: "POST" }).catch(() => {}); S.authed = false; renderAuth(); };
}

function updateChrome() {
  $$(".nav a").forEach((a) => a.classList.toggle("active", a.dataset.nav === S.route));
  const ready = S.overview?.clips?.ready || 0;
  const badge = $("#nav-review-count");
  if (badge) { badge.textContent = ready; badge.classList.toggle("hidden", !ready); }
  const live = Object.keys(S.overview?.live || {}).length;
  const pill = $("#live-pill");
  if (pill) {
    pill.classList.toggle("on", live > 0);
    pill.innerHTML = `<span class="dot ${live ? "live" : ""}"></span><span>${live ? `${live} stream${live > 1 ? "s" : ""} live` : "No live streams"}</span>`;
  }
}

function header(title, sub, actions = "") {
  return `<div class="topbar"><div><h1 class="page-title">${title}</h1>${sub ? `<div class="page-sub">${sub}</div>` : ""}</div><div class="spacer"></div><div class="row">${actions}</div></div>`;
}

// ------------------------------------------------------------------ router
function parseRoute() {
  const h = location.hash.replace(/^#\/?/, "");
  const [path, query] = h.split("?");
  S.route = path || "dashboard";
  S.params = new URLSearchParams(query || "");
}

async function render() {
  parseRoute();
  updateChrome();
  const page = $("#page");
  if (!page) return;
  const fn = PAGES[S.route] || PAGES.dashboard;
  try { await fn(page); } catch (e) { if (S.authed) fail(e); }
  updateChrome();
}

// ------------------------------------------------------------------ live events
function connectStream() {
  if (S.es) S.es.close();
  const es = new EventSource("/api/stream");
  S.es = es;
  es.onmessage = (ev) => {
    let m; try { m = JSON.parse(ev.data); } catch { return; }
    handleEvent(m);
  };
  es.onerror = () => { /* browser retries automatically */ };
}

const refreshOverview = debounce(async () => { try { S.overview = await api("/api/overview"); updateChrome(); if (S.route === "dashboard") paintDashboardDynamic(); } catch {} }, 600);

function handleEvent(m) {
  switch (m.type) {
    case "scores": {
      const buf = (S.scores[m.run_id] ||= { series: {}, signals: {}, status: {} });
      m.combined.forEach((v, i) => { buf.series[m.t0 + i] = v; });
      const keys = Object.keys(buf.series).map(Number).sort((a, b) => a - b);
      keys.slice(0, Math.max(0, keys.length - 180)).forEach((k) => delete buf.series[k]);
      for (const [k, arr] of Object.entries(m.signals || {})) buf.signals[k] = arr.length ? arr[arr.length - 1] : 0;
      buf.status = m.status || {};
      if (S.route === "dashboard") paintRadarItem(m.run_id);
      break;
    }
    case "activity":
      S.events.unshift(m.event); S.events = S.events.slice(0, 60);
      if (S.route === "dashboard") paintFeed();
      if (m.event.kind === "moment") toast(m.event.message, "hype");
      if (m.event.kind === "posted" && m.event.level !== "error") toast(m.event.message, "ok");
      refreshOverview();
      break;
    case "clip": {
      const i = S.clips.findIndex((c) => c.id === m.clip.id);
      if (i >= 0) S.clips[i] = { ...S.clips[i], ...m.clip }; else S.clips.unshift({ ...m.clip, posts: [] });
      if (S.route === "review") paintReviewGrid();
      if (S.route === "dashboard") paintFresh();
      document.dispatchEvent(new CustomEvent("clip-updated", { detail: m.clip }));
      refreshOverview();
      break;
    }
    case "clip_stage": {
      const c = S.clips.find((x) => x.id === m.id);
      if (c) { c.stage = m.stage; if (S.route === "review") paintReviewGrid(); }
      break;
    }
    case "clip_deleted":
      S.clips = S.clips.filter((c) => c.id !== m.id);
      if (S.route === "review") paintReviewGrid();
      break;
    case "run": {
      const i = S.runs.findIndex((r) => r.id === m.run.id);
      if (i >= 0) S.runs[i] = m.run; else S.runs.unshift(m.run);
      if (S.route === "vod") paintVodRuns();
      if (S.route === "streams") paintRuns();
      refreshOverview();
      break;
    }
    case "streamer": {
      const i = S.streamers.findIndex((s) => s.id === m.streamer.id);
      if (i >= 0) { S.streamers[i] = { ...S.streamers[i], ...m.streamer }; if (S.route === "streams") paintStreamers(); }
      break;
    }
    case "post":
      if (S.route === "schedule") loadSchedule();
      refreshOverview();
      break;
    case "stats":
      if (S.route === "analytics") PAGES.analytics($("#page"));
      break;
  }
}

// ================================================================== DASHBOARD
async function pageDashboard(page) {
  page.innerHTML = header("Command Center", "Live radar, fresh clips and everything happening right now",
    `<a class="btn" href="#/vod">${ic("upload")} Upload VOD</a><a class="btn primary" href="#/streams">${ic("radio")} Watch a stream</a>`) +
    `<div class="stats" id="stats"></div>
     <div class="grid g-main">
       <div class="col" style="gap:18px">
         <div class="card"><div class="card-h"><h3>Live radar</h3><span class="badge live hidden" id="radar-live">${ic("radio")} LIVE</span><div class="spacer"></div><span class="small dim">hype score · last 3 min</span></div><div class="radar" id="radar"></div></div>
         <div class="card"><div class="card-h"><h3>Fresh clips</h3><div class="spacer"></div><a class="btn sm ghost" href="#/review">Open review ${ic("right")}</a></div><div class="strip" id="fresh"></div></div>
         <div class="card"><div class="card-h"><h3>Views · 30 days</h3><div class="spacer"></div><a class="btn sm ghost" href="#/analytics">Money ${ic("right")}</a></div><canvas class="chart" id="views-chart" style="height:170px"></canvas></div>
       </div>
       <div class="card"><div class="card-h"><h3>Activity</h3><div class="spacer"></div><span class="dot ok"></span><span class="small dim">live</span></div><div class="feed" id="feed"></div></div>
     </div>`;
  const [ov, clips] = await Promise.all([api("/api/overview"), api("/api/clips?limit=60")]);
  S.overview = ov; S.events = ov.events || []; S.clips = clips;
  paintDashboardDynamic();
  paintFeed();
  paintFresh();
}

function paintDashboardDynamic() {
  const ov = S.overview; if (!ov || !$("#stats")) return;
  const c = ov.clips || {}, p = ov.posts || {};
  $("#stats").innerHTML = `
    <a class="stat pink" href="#/review"><div class="label">${ic("film")} To review</div><div class="value">${c.ready || 0}</div><div class="foot">${(c.rendering || 0) + (c.detected || 0)} rendering · ${ov.clips_today} today</div></a>
    <a class="stat orange" href="#/schedule"><div class="label">${ic("calendar")} Scheduled</div><div class="value">${p.scheduled || 0}</div><div class="foot">${p.failed ? `<span style="color:#ff95a0">${p.failed} failed</span>` : "queue healthy"}</div></a>
    <a class="stat cyan" href="#/schedule"><div class="label">${ic("zap")} Posted</div><div class="value">${p.posted || 0}</div><div class="foot">Shorts + Reels</div></a>
    <a class="stat violet" href="#/analytics"><div class="label">${ic("eye")} Views</div><div class="value">${fmtNum(ov.views)}</div><div class="foot">all posted clips</div></a>
    <a class="stat lime" href="#/analytics"><div class="label">${ic("dollar")} Est. earnings</div><div class="value grad-text">${fmtMoney(ov.earnings, ov.currency)}</div><div class="foot">campaign CPM + ad share</div></a>`;
  paintRadar();
  drawBars($("#views-chart"), (ov.days || []).map((d) => ({ label: d.day.slice(5), value: d.views })));
}

function paintRadar() {
  const el = $("#radar"); if (!el) return;
  const runs = (S.overview?.active_runs || []).filter((r) => r.kind === "live");
  $("#radar-live")?.classList.toggle("hidden", !runs.length);
  if (!runs.length) {
    el.innerHTML = `<div class="empty"><div class="big-icon">${ic("radio")}</div><h4>Nobody's being watched</h4><p>Add a streamer and hit <b>Watch</b>, or turn on <b>Auto-watch</b> so HYPECUT jumps in the second they go live.</p><a class="btn primary" href="#/streams">${ic("plus")} Add a streamer</a></div>`;
    return;
  }
  const existing = new Set($$(".radar-item", el).map((x) => Number(x.dataset.run)));
  const want = new Set(runs.map((r) => r.id));
  $$(".radar-item", el).forEach((x) => { if (!want.has(Number(x.dataset.run))) x.remove(); });
  if (!existing.size) el.innerHTML = "";
  for (const r of runs) {
    if (existing.has(r.id)) continue;
    const st = S.streamers.find((s) => s.id === r.streamer_id);
    const plat = st?.platform || "other";
    const div = document.createElement("div");
    div.className = "radar-item"; div.dataset.run = r.id;
    div.innerHTML = `
      <div class="radar-head"><span class="dot live"></span><span class="name">${esc(r.title || "Stream")}</span><span class="badge ${plat}">${PLAT[plat] || "Live"}</span>
        <span class="small dim" data-meta></span><span class="hype-score grad-text" data-score>0</span>
        <button class="btn sm danger" data-stop="${r.id}" title="Stop watching">${ic("stop")}</button></div>
      <canvas height="110"></canvas>
      <div class="sig-bars">${Object.entries(SIG).map(([k, [n, col]]) => `<div class="sig">${n}<div class="bar"><i data-sig="${k}" style="width:0;background:${col}"></i></div></div>`).join("")}</div>`;
    el.appendChild(div);
    $("[data-stop]", div).onclick = async () => { await api(`/api/runs/${r.id}/stop`, { method: "POST" }).catch(fail); toast("Stopping…"); };
    paintRadarItem(r.id);
  }
}

function paintRadarItem(runId) {
  const item = $(`.radar-item[data-run="${runId}"]`);
  if (!item) { if (S.route === "dashboard" && !$(`.radar-item[data-run="${runId}"]`)) refreshOverview(); return; }
  const buf = S.scores[runId]; if (!buf) return;
  const keys = Object.keys(buf.series).map(Number).sort((a, b) => a - b);
  const vals = keys.map((k) => buf.series[k]);
  const thr = S.settings?.settings?.detection?.threshold ?? 0.55;
  drawHype($("canvas", item), vals, thr);
  const last = vals.length ? vals[vals.length - 1] : 0;
  $("[data-score]", item).textContent = Math.round(last * 100);
  for (const [k] of Object.entries(SIG)) { const bar = $(`[data-sig="${k}"]`, item); if (bar) bar.style.width = `${Math.round((buf.signals[k] || 0) * 100)}%`; }
  const s = buf.status || {};
  $("[data-meta]", item).innerHTML = `${fmtDur(s.timeline)} · ${s.moments || 0} moments · ${s.chat_connected ? `💬 ${fmtNum(s.chat_messages)}` : `<span title="${esc(s.chat_error || "")}">chat off</span>`}`;
}

function setupCanvas(cv) {
  const dpr = window.devicePixelRatio || 1;
  const w = cv.clientWidth || 600, h = cv.clientHeight || 110;
  if (cv.width !== Math.round(w * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); }
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  return [ctx, w, h];
}

function drawHype(cv, vals, thr) {
  if (!cv) return;
  const [ctx, w, h] = setupCanvas(cv);
  const n = Math.max(vals.length, 60), pad = 4;
  const x = (i) => (i / (n - 1)) * w, y = (v) => h - pad - v * (h - pad * 2);
  ctx.strokeStyle = "rgba(255,255,255,0.06)"; ctx.lineWidth = 1;
  for (let g = 0.25; g < 1; g += 0.25) { ctx.beginPath(); ctx.moveTo(0, y(g)); ctx.lineTo(w, y(g)); ctx.stroke(); }
  ctx.setLineDash([5, 5]); ctx.strokeStyle = "rgba(255,230,0,0.55)";
  ctx.beginPath(); ctx.moveTo(0, y(thr)); ctx.lineTo(w, y(thr)); ctx.stroke(); ctx.setLineDash([]);
  if (!vals.length) return;
  const off = n - vals.length;
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, "rgba(255,46,136,0.55)"); grad.addColorStop(1, "rgba(255,46,136,0)");
  ctx.beginPath(); ctx.moveTo(x(off), h);
  vals.forEach((v, i) => ctx.lineTo(x(off + i), y(v)));
  ctx.lineTo(x(off + vals.length - 1), h); ctx.closePath(); ctx.fillStyle = grad; ctx.fill();
  const lg = ctx.createLinearGradient(0, 0, w, 0); lg.addColorStop(0, "#8b5cf6"); lg.addColorStop(0.6, "#ff2e88"); lg.addColorStop(1, "#ff8a3d");
  ctx.beginPath(); vals.forEach((v, i) => (i ? ctx.lineTo : ctx.moveTo).call(ctx, x(off + i), y(v)));
  ctx.strokeStyle = lg; ctx.lineWidth = 2.5; ctx.lineJoin = "round"; ctx.stroke();
  vals.forEach((v, i) => { if (v >= thr) { ctx.beginPath(); ctx.arc(x(off + i), y(v), 2.6, 0, 7); ctx.fillStyle = "#ffe600"; ctx.fill(); } });
}

function drawBars(cv, data, color) {
  if (!cv) return;
  const [ctx, w, h] = setupCanvas(cv);
  const max = Math.max(1, ...data.map((d) => d.value));
  const bw = w / Math.max(1, data.length), padB = 18;
  ctx.font = "10px Inter, sans-serif"; ctx.fillStyle = "#6c6787"; ctx.textAlign = "center";
  data.forEach((d, i) => {
    const bh = (d.value / max) * (h - padB - 10);
    const g = ctx.createLinearGradient(0, h - padB - bh, 0, h - padB);
    g.addColorStop(0, color || "#ff2e88"); g.addColorStop(1, color ? color + "33" : "rgba(255,138,61,0.25)");
    ctx.fillStyle = g;
    const bx = i * bw + bw * 0.18, bwid = bw * 0.64;
    ctx.beginPath(); (ctx.roundRect ? ctx.roundRect(bx, h - padB - bh, bwid, Math.max(bh, 1.5), 4) : ctx.rect(bx, h - padB - bh, bwid, Math.max(bh, 1.5))); ctx.fill();
    if (data.length <= 12 || i % Math.ceil(data.length / 8) === 0) { ctx.fillStyle = "#6c6787"; ctx.fillText(d.label, i * bw + bw / 2, h - 4); }
  });
  if (max <= 1 && data.every((d) => !d.value)) { ctx.fillStyle = "#6c6787"; ctx.font = "13px Inter"; ctx.fillText("No views yet — post your first clip", w / 2, h / 2); }
}

const FEED_IC = { moment: "flame", clip: "film", posted: "zap", live: "radio", vod: "upload", schedule: "calendar", security: "shield", autopilot: "wand", streamer: "user", tuning: "sliders", accounts: "link" };
function paintFeed() {
  const el = $("#feed"); if (!el) return;
  if (!S.events.length) { el.innerHTML = `<div class="empty small">Quiet for now. Activity shows up here in real time.</div>`; return; }
  el.innerHTML = S.events.map((e) => `<div class="feed-item ${esc(e.level)}"><div class="ic">${ic(FEED_IC[e.kind] || "activity")}</div><div><div class="msg">${esc(e.message)}</div><div class="ts">${ago(e.ts)}</div></div></div>`).join("");
}

function paintFresh() {
  const el = $("#fresh"); if (!el) return;
  const list = S.clips.filter((c) => ["ready", "rendering", "detected", "scheduled"].includes(c.status)).slice(0, 14);
  if (!list.length) { el.style.display = "block"; el.innerHTML = `<div class="empty small">No clips yet. Watch a stream or drop a VOD in the lab.</div>`; return; }
  el.style.display = "";
  el.innerHTML = list.map(clipCard).join("");
  bindCards(el, list);
}

// ================================================================== REVIEW
const TABS = [["ready", "To review"], ["scheduled", "Scheduled"], ["posted", "Posted"], ["rendering,detected", "Processing"], ["rejected", "Skipped"], ["failed", "Failed"]];

async function pageReview(page) {
  if (S.params.get("tab")) S.reviewTab = S.params.get("tab");
  page.innerHTML = header("Review", "Approve with <span class='kbd'>A</span>, skip with <span class='kbd'>S</span>, move with <span class='kbd'>←</span> <span class='kbd'>→</span>",
    `<button class="btn" id="retry-failed">${ic("refresh")} Retry failed</button><button class="btn" id="approve-all">${ic("check")} Approve all 70+</button>`) +
    `<div class="tabs" id="tabs"></div><div id="grid"></div>`;
  S.clips = await api("/api/clips?limit=400");
  paintReviewGrid();
  $("#retry-failed").onclick = async () => {
    const failed = S.clips.filter((c) => c.status === "failed");
    if (!failed.length) return toast("No failed clips");
    let n = 0;
    for (const c of failed) { try { await api(`/api/clips/${c.id}/rerender`, { method: "POST", body: {} }); n++; } catch { /* already busy — skip */ } }
    toast(`Re-rendering ${n} clip${n === 1 ? "" : "s"}…`);
    S.reviewTab = "rendering,detected"; paintReviewGrid();
  };
  $("#approve-all").onclick = async () => {
    const hot = S.clips.filter((c) => c.status === "ready" && c.virality >= 70);
    if (!hot.length) return toast("No ready clips with virality 70+");
    if (!(await confirmBox("Approve all hot clips?", `${hot.length} clips with virality ≥ 70 will be scheduled into your next free slots.`, "Approve all"))) return;
    let ok = 0;
    for (const c of hot) { try { await api(`/api/clips/${c.id}/approve`, { method: "POST", body: {} }); ok++; } catch (e) { fail(e); break; } }
    toast(`${ok} clips scheduled`);
  };
  const id = Number(S.params.get("clip"));
  if (id) openReview(id);
}

function tabClips(tab) { const st = tab.split(","); return S.clips.filter((c) => st.includes(c.status)); }

function paintReviewGrid() {
  const tabs = $("#tabs"), grid = $("#grid"); if (!tabs || !grid) return;
  tabs.innerHTML = TABS.map(([k, label]) => `<button class="tab ${S.reviewTab === k ? "on" : ""}" data-tab="${k}">${label}<span class="n">${tabClips(k).length}</span></button>`).join("");
  $$("[data-tab]", tabs).forEach((b) => (b.onclick = () => { S.reviewTab = b.dataset.tab; paintReviewGrid(); }));
  const list = tabClips(S.reviewTab);
  if (!list.length) {
    const msg = { ready: ["All caught up 🎉", "New key moments land here automatically while streams are being watched."], scheduled: ["Nothing scheduled", "Approve clips in “To review” and they'll slot into your posting schedule."], posted: ["Nothing posted yet", "Connect YouTube and Instagram in Settings, then approve a clip."] }[S.reviewTab] || ["Empty", ""];
    grid.innerHTML = `<div class="card empty"><div class="big-icon">${ic("film")}</div><h4>${msg[0]}</h4><p>${msg[1]}</p></div>`;
    return;
  }
  grid.innerHTML = `<div class="clip-grid">${list.map(clipCard).join("")}</div>`;
  bindCards(grid, list);
}

function viralClass(v) { return v >= 70 ? "hot" : v >= 45 ? "warm" : "cold"; }

function clipCard(c) {
  const busy = c.status === "rendering" || c.status === "detected";
  const v = Math.round(c.virality || 0);
  const posted = (c.posts || []).filter((p) => p.status === "posted").map((p) => p.platform);
  return `<div class="clip-card" data-clip="${c.id}" tabindex="0">
    ${c.has_thumb ? `<img loading="lazy" src="/api/clips/${c.id}/thumb?v=${encodeURIComponent(c.updated_at || "")}" alt="">` : ""}
    ${busy ? `<div class="processing"><div class="col" style="align-items:center"><div class="spinner"></div><div class="small muted">${c.stage ? esc(c.stage) + "…" : c.status === "detected" ? "Queued" : "Waiting in line"}</div></div></div>` : ""}
    <div class="shade"></div>
    <div class="top">${c.status === "failed" ? `<span class="badge err">failed</span>` : ""}${posted.map((p) => `<span class="badge ${p}">${ic(p === "youtube" ? "yt" : "ig")}</span>`).join("")}${!busy && v ? `<span class="viral ${viralClass(v)}">${v}</span>` : ""}</div>
    <div class="bottom">${c.status === "failed" && c.error ? `<div class="small" style="color:#ff95a0;margin-bottom:6px;display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden">${esc(c.error)}</div>` : ""}<div class="title">${esc(c.title || c.hook || "Key moment")}</div>
      <div class="meta">${c.streamer ? `<span>${esc(c.streamer)}</span>·` : ""}<span>${fmtDur(c.duration)}</span>·<span>${ago(c.created_at)}</span></div></div>
  </div>`;
}

function bindCards(root, list) {
  $$(".clip-card", root).forEach((card) => {
    const id = Number(card.dataset.clip);
    const c = list.find((x) => x.id === id);
    card.onclick = () => openReview(id, list.map((x) => x.id));
    card.onkeydown = (e) => { if (e.key === "Enter") card.click(); };
    if (!c?.has_video) return;
    let vid;
    card.onmouseenter = () => {
      vid = document.createElement("video");
      Object.assign(vid, { muted: true, autoplay: true, loop: true, playsInline: true, src: `/api/clips/${id}/video?v=${encodeURIComponent(c.updated_at || "")}` });
      card.insertBefore(vid, card.querySelector(".shade"));
    };
    card.onmouseleave = () => { vid?.remove(); vid = null; };
  });
}

async function openReview(id, order) {
  order = order || tabClips(S.reviewTab).map((c) => c.id);
  let c;
  try { c = await api(`/api/clips/${id}`); } catch (e) { return fail(e); }
  const defaults = S.settings?.settings?.schedule?.platforms || ["youtube", "instagram"];
  const v = Math.round(c.virality || 0);
  const ai = c.ai || {};
  const posted = c.posts.filter((p) => ["scheduled", "posting", "posted"].includes(p.status));
  const sigs = Object.entries(c.signals || {}).filter(([k, val]) => SIG[k] && typeof val === "number");
  const m = modal(`
    <button class="btn icon ghost modal-x" data-close title="Close (Esc)">${ic("x")}</button>
    <div class="review">
      <div>
        <div class="player">${c.has_video ? `<video controls autoplay playsinline src="/api/clips/${c.id}/video?v=${encodeURIComponent(c.updated_at)}"></video>`
          : c.status === "rejected" ? `${c.has_thumb ? `<img src="/api/clips/${c.id}/thumb?v=${encodeURIComponent(c.updated_at)}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:.35">` : ""}<div class="processing"><div class="col" style="align-items:center;padding:20px"><div style="font-weight:800;color:var(--text)">Skipped by the AI editor</div><div class="small">Not rendered, to save time.</div><button class="btn primary" data-render-anyway>${ic("film")} Render it anyway</button></div></div>`
          : `<div class="processing"><div class="col" style="align-items:center"><div class="spinner"></div><div>${c.status === "failed" ? esc(c.error) : "Rendering… this updates by itself"}</div></div></div>`}</div>
        <div class="row" style="justify-content:center;margin-top:12px">
          <button class="btn sm ghost" data-prev>${ic("left")} Prev</button>
          <span class="small dim">${order.indexOf(c.id) + 1} / ${order.length}</span>
          <button class="btn sm ghost" data-next>Next ${ic("right")}</button>
        </div>
      </div>
      <div class="review-side">
        <div class="row"><span class="badge ${c.status === "ready" ? "info" : c.status === "posted" ? "ok" : c.status === "failed" ? "err" : ""}">${esc(c.status)}</span>
          ${c.streamer ? `<span class="badge">${ic("user")} ${esc(c.streamer)}</span>` : ""}<span class="badge">${ic("clock")} ${fmtDur(c.duration)}</span>
          ${!c.streamer_permission ? `<span class="badge warn" title="Mark permission on the Streams page">${ic("lock")} no permission yet</span>` : ""}</div>
        <div class="verdict">
          <div class="row"><b>${ic("sparkles").replace("<svg", '<svg style="width:16px;height:16px;vertical-align:-3px;color:#a78bfa"')} ${ai.source === "claude" ? "AI editor" : "Auto-detected"}</b><div class="spacer"></div><span class="hype-score grad-text" style="font-size:30px">${v}</span><span class="small dim">/100</span></div>
          <div class="meter"><i style="width:${v}%"></i></div>
          <div class="small" style="margin-top:8px">${esc(ai.reason || "")}</div>
          <div class="chips" style="margin-top:10px">${sigs.map(([k, val]) => `<span class="chip ${k === c.signals.top ? "" : "cyan"}">${SIG[k][0]} ${Math.round(val * 100)}</span>`).join("")}</div>
        </div>
        <label class="field">Hook text <span class="hint">Burned into the first seconds — changing it re-renders the video</span><input class="input" data-f="hook" maxlength="80" value="${esc(c.hook)}"></label>
        <label class="field">Title (YouTube) <input class="input" data-f="title" maxlength="100" value="${esc(c.title)}"><div class="counter" data-count="title"></div></label>
        <label class="field">Caption (Instagram + YouTube description) <textarea class="input" data-f="caption" rows="3">${esc(c.caption)}</textarea></label>
        <label class="field">Hashtags <input class="input" data-f="hashtags" value="${esc((c.hashtags || []).join(" "))}"></label>
        <div class="row"><span class="small muted" style="font-weight:700">Layout</span><div class="seg" data-layouts>${[["crop", "Full screen"], ["blur", "Blurred bg"], ["split", "Cam on top"]].map(([l, n]) => `<button data-layout="${l}" class="${c.layout === l ? "on" : ""}">${n}</button>`).join("")}</div>
          <button class="btn sm ghost" data-reai title="Ask the AI editor again">${ic("wand")} Re-run AI</button></div>
        ${posted.length ? `<div class="col">${posted.map((p) => `<div class="row small"><span class="badge ${p.platform}">${PLAT[p.platform]}</span><span>${p.status === "posted" ? `posted ${ago(p.posted_at)} · ${fmtNum(p.views)} views` : `${p.status} · ${dayOf(p.scheduled_at)} ${timeOf(p.scheduled_at)}`}</span>${p.url ? `<a class="btn sm ghost" href="${esc(p.url)}" target="_blank" rel="noopener">${ic("ext")}</a>` : ""}</div>`).join("")}</div>` : ""}
        <hr class="sep" style="margin:4px 0">
        <div class="row">
          <label class="platform-toggle"><input type="checkbox" data-plat="youtube" ${defaults.includes("youtube") ? "checked" : ""}>${ic("yt").replace("<svg", '<svg style="width:18px;height:18px;color:#ff0033"')} Shorts</label>
          <label class="platform-toggle"><input type="checkbox" data-plat="instagram" ${defaults.includes("instagram") ? "checked" : ""}>${ic("ig").replace("<svg", '<svg style="width:18px;height:18px;color:#ff5fa8"')} Reels</label>
          <input class="input" type="datetime-local" data-when style="width:auto;flex:1;min-width:190px" title="Leave empty for the next free slot">
        </div>
        <div class="action-bar">
          <button class="btn primary lg" data-approve ${c.has_video ? "" : "disabled"}>${ic("check")} Approve <span class="kbd" style="color:#fff;border-color:rgba(255,255,255,.4)">A</span></button>
          <button class="btn cyan" data-now ${c.has_video ? "" : "disabled"} title="Upload immediately">${ic("zap")} Post now</button>
          <button class="btn" data-skip>${ic("x")} Skip <span class="kbd">S</span></button>
          <div class="spacer"></div>
          ${c.has_video ? `<a class="btn icon ghost" href="/api/clips/${c.id}/download" title="Download MP4">${ic("download")}</a>` : ""}
          <button class="btn icon ghost" data-del title="Delete">${ic("trash")}</button>
        </div>
      </div>
    </div>`, { wide: true, onClose: () => { document.removeEventListener("keydown", keys); document.removeEventListener("clip-updated", onUpd); } });

  const go = (delta) => { const i = order.indexOf(c.id); const nxt = order[i + delta]; if (nxt) { m.close(); openReview(nxt, order); } else { m.close(); } };
  const fields = () => {
    const out = {};
    $$("[data-f]", m).forEach((el) => (out[el.dataset.f] = el.value));
    return out;
  };
  const saveFields = async () => {
    const f = fields();
    const changed = Object.keys(f).some((k) => (k === "hashtags" ? (c.hashtags || []).join(" ") : c[k] || "") !== f[k]);
    if (changed) { await api(`/api/clips/${c.id}`, { method: "PATCH", body: f }); }
  };
  const counter = () => { const t = $('[data-f="title"]', m).value.length; const el = $('[data-count="title"]', m); el.textContent = `${t}/100`; el.classList.toggle("over", t > 100); };
  counter(); $('[data-f="title"]', m).oninput = counter;
  $("[data-close]", m).onclick = () => m.close();
  $("[data-prev]", m).onclick = () => go(-1);
  $("[data-next]", m).onclick = () => go(1);
  let busy = false; // one action at a time: a held or double-tapped key must not stack windows
  const approve = async (now = false) => {
    if (busy) return;
    const platforms = $$("[data-plat]", m).filter((x) => x.checked).map((x) => x.dataset.plat);
    if (!platforms.length) return toast("Pick at least one platform", "err");
    const when = $("[data-when]", m).value;
    busy = true;
    try {
      await saveFields();
      const r = await api(`/api/clips/${c.id}/approve`, { method: "POST", body: { platforms, now, when: when ? new Date(when).toISOString() : null } });
      toast(now ? "Uploading now 🚀" : r.posts.length ? `Scheduled: ${r.posts.map((p) => `${PLAT[p.platform]} ${dayOf(p.scheduled_at)} ${timeOf(p.scheduled_at)}`).join(" · ")}` : "Already scheduled");
      go(1);
    } catch (e) { fail(e); busy = false; }
  };
  $("[data-approve]", m).onclick = () => approve(false);
  $("[data-now]", m).onclick = () => approve(true);
  $("[data-skip]", m).onclick = async () => { if (busy) return; busy = true; try { await api(`/api/clips/${c.id}/reject`, { method: "POST" }); toast("Skipped"); go(1); } catch (e) { fail(e); busy = false; } };
  $("[data-del]", m).onclick = async () => { if (await confirmBox("Delete clip?", "The video files are removed from disk.", "Delete", true)) { try { await api(`/api/clips/${c.id}`, { method: "DELETE" }); toast("Deleted"); go(1); } catch (e) { fail(e); } } };
  $$("[data-layout]", m).forEach((b) => (b.onclick = async () => { try { await saveFields(); await api(`/api/clips/${c.id}/rerender`, { method: "POST", body: { layout: b.dataset.layout } }); toast("Re-rendering…"); m.close(); } catch (e) { fail(e); } }));
  const ra = $("[data-render-anyway]", m);
  if (ra) ra.onclick = async () => { try { await api(`/api/clips/${c.id}/restore`, { method: "POST" }); toast("Rendering it now…"); m.close(); } catch (e) { fail(e); } };
  $("[data-reai]", m).onclick = async () => { try { await api(`/api/clips/${c.id}/rerender`, { method: "POST", body: { rerun_ai: true } }); toast("AI editor is taking another look…"); m.close(); } catch (e) { fail(e); } };
  $$("[data-f]", m).forEach((el) => el.addEventListener("change", () => saveFields().catch(fail)));

  function keys(e) {
    if (e.repeat || !document.body.contains(m)) return;
    if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) return;
    if (e.key === "a" || e.key === "A") { e.preventDefault(); approve(false); }
    else if (e.key === "s" || e.key === "S") { e.preventDefault(); $("[data-skip]", m).click(); }
    else if (e.key === "ArrowRight") go(1);
    else if (e.key === "ArrowLeft") go(-1);
  }
  function onUpd(ev) { if (ev.detail.id === c.id && ev.detail.has_video && !c.has_video) { m.close(); openReview(c.id, order); } }
  document.addEventListener("keydown", keys);
  document.addEventListener("clip-updated", onUpd);
}

// ================================================================== STREAMS
async function pageStreams(page) {
  page.innerHTML = header("Streams", "Paste any Twitch, Kick or YouTube channel. Auto-watch starts clipping the moment they go live.") +
    `<form class="add-bar" id="add-form"><input class="input big" name="url" placeholder="Paste a channel link — twitch.tv/name · kick.com/name · youtube.com/@name" required>
       <button class="btn primary lg" type="submit">${ic("plus")} Add streamer</button></form>
     <div class="streamer-grid" id="streamers"></div>
     <div class="card" style="margin-top:22px"><div class="card-h"><h3>Recent sessions</h3></div><div id="runs" style="overflow-x:auto"></div></div>`;
  $("#add-form").onsubmit = async (e) => {
    e.preventDefault();
    const url = new FormData(e.target).get("url");
    try {
      const st = await api("/api/streamers", { method: "POST", body: { url } });
      toast(`${st.name} added — mark permission to enable posting`);
      e.target.reset();
      S.streamers = await api("/api/streamers"); paintStreamers();
    } catch (err) { fail(err); }
  };
  [S.streamers, S.runs] = await Promise.all([api("/api/streamers"), api("/api/runs")]);
  paintStreamers(); paintRuns();
}

function paintStreamers() {
  const el = $("#streamers"); if (!el) return;
  if (!S.streamers.length) { el.innerHTML = `<div class="card empty" style="grid-column:1/-1"><div class="big-icon">${ic("radio")}</div><h4>No streamers yet</h4><p>Add the GTA streamers you clip for. Get their OK first — clipping with permission is what keeps your channel safe and lets you get paid.</p></div>`; return; }
  el.innerHTML = S.streamers.map((s) => {
    const watching = s.watching;
    return `<div class="card streamer" data-st="${s.id}">
      <div class="head"><div class="avatar ${s.platform}">${esc((s.name || "?").slice(0, 1).toUpperCase())}${s.is_live ? '<span class="live-ring"></span>' : ""}</div>
        <div style="min-width:0"><div class="name ellipsis">${esc(s.name)}</div><div class="row small" style="gap:6px"><span class="badge ${s.platform}">${PLAT[s.platform] || s.platform}</span>${s.is_live ? '<span class="badge live"><span class="dot live" style="width:6px;height:6px"></span>LIVE</span>' : `<span class="dim">${s.last_checked ? "offline · checked " + ago(s.last_checked) : "not checked"}</span>`}</div></div>
        <div class="spacer"></div><span class="small dim nowrap">${s.clips} clips</span>
        <a class="btn icon ghost" href="${esc(s.url)}" target="_blank" rel="noopener" title="Open channel">${ic("ext")}</a>
        <button class="btn icon ghost" data-del title="Remove">${ic("trash")}</button></div>
      ${s.permission ? "" : `<div class="perm-warn">${ic("lock").replace("<svg", '<svg style="width:13px;height:13px;vertical-align:-2px"')} Clips are held until you confirm you have permission to post this streamer's content.</div>`}
      <div class="opts">
        <label class="switch"><input type="checkbox" data-k="permission" ${s.permission ? "checked" : ""}><span class="track"></span>Permission</label>
        <label class="switch"><input type="checkbox" data-k="auto_watch" ${s.auto_watch ? "checked" : ""}><span class="track"></span>Auto-watch</label>
        <label class="field">Layout<select class="input" data-k="layout">${[["auto", "Full screen, no cam"], ["blur", "Blurred background"], ["split", "Cam on top"]].map(([l, n]) => `<option value="${l}" ${(s.layout === "crop" ? "auto" : s.layout) === l ? "selected" : ""}>${n}</option>`).join("")}</select></label>
        <label class="field">Pays per 1K views<input class="input" type="number" min="0" step="0.05" data-k="cpm" value="${s.cpm || 0}"></label>
      </div>
      <div class="row">
        ${watching ? `<button class="btn danger" data-stop="${watching}">${ic("stop")} Stop</button>` : `<button class="btn primary" data-watch>${ic("play")} Watch now</button>`}
        <button class="btn" data-check title="Check if live">${ic("refresh")}</button>
        <button class="btn" data-face title="Set facecam box for split layout">${ic("scan")} Facecam${s.facecam ? " ✓" : ""}</button>
      </div></div>`;
  }).join("");
  $$("[data-st]", el).forEach((card) => {
    const id = Number(card.dataset.st);
    const s = S.streamers.find((x) => x.id === id);
    $$("[data-k]", card).forEach((inp) => (inp.onchange = async () => {
      const val = inp.type === "checkbox" ? inp.checked : inp.type === "number" ? Number(inp.value) : inp.value;
      try { const d = await api(`/api/streamers/${id}`, { method: "PATCH", body: { [inp.dataset.k]: val } }); Object.assign(s, d); if (inp.dataset.k === "permission") paintStreamers(); toast("Saved"); } catch (e) { fail(e); }
    }));
    const w = $("[data-watch]", card);
    if (w) w.onclick = async () => { w.disabled = true; try { await api(`/api/streamers/${id}/watch`, { method: "POST" }); toast(`Watching ${s.name} — connecting…`); S.streamers = await api("/api/streamers"); paintStreamers(); } catch (e) { fail(e); w.disabled = false; } };
    const st = $("[data-stop]", card);
    if (st) st.onclick = async () => { await api(`/api/runs/${st.dataset.stop}/stop`, { method: "POST" }).catch(fail); toast("Stopping…"); setTimeout(async () => { S.streamers = await api("/api/streamers"); paintStreamers(); }, 2500); };
    $("[data-check]", card).onclick = async (e) => { const b = e.currentTarget; b.innerHTML = '<span class="spinner sm"></span>'; try { const r = await api(`/api/streamers/${id}/check`, { method: "POST" }); toast(r.live ? `${s.name} is LIVE: ${r.info}` : `${s.name} is offline`); } catch (er) { fail(er); } b.innerHTML = ic("refresh"); };
    $("[data-face]", card).onclick = () => facecamPicker(s);
    $("[data-del]", card).onclick = async () => { if (await confirmBox(`Remove ${s.name}?`, "Their existing clips stay in your library.", "Remove", true)) { await api(`/api/streamers/${id}`, { method: "DELETE" }).catch(fail); S.streamers = S.streamers.filter((x) => x.id !== id); paintStreamers(); } };
  });
}

function runBadge(r) {
  const cls = { live: "live", done: "ok", ended: "ok", error: "err", stopped: "", processing: "info", downloading: "info", starting: "warn" }[r.status] || "";
  return `<span class="badge ${cls}">${r.status === "live" ? '<span class="dot live" style="width:6px;height:6px"></span>' : ""}${esc(r.status)}</span>`;
}

function paintRuns() {
  const el = $("#runs"); if (!el) return;
  const rows = S.runs.filter((r) => r.kind === "live").slice(0, 15);
  if (!rows.length) { el.innerHTML = `<div class="empty small">No live sessions yet.</div>`; return; }
  el.innerHTML = `<table class="table"><tr><th>Stream</th><th>Status</th><th>Length</th><th>Moments</th><th>Chat</th><th>Started</th><th></th></tr>${rows.map((r) => `
    <tr><td class="ellipsis" style="max-width:240px">${esc(r.title)}</td><td>${runBadge(r)}${r.error ? `<div class="small" style="color:#ff95a0;max-width:280px">${esc(r.error)}</div>` : ""}</td>
    <td class="mono">${fmtDur(r.live?.timeline ?? r.stats?.duration)}</td><td>${r.live?.moments ?? r.stats?.moments ?? 0}</td>
    <td>${r.live ? (r.live.chat_connected ? `<span class="badge ok">💬 ${fmtNum(r.live.chat_messages)}</span>` : `<span class="badge warn" title="${esc(r.live.chat_error || "connecting…")}">chat off</span>${r.live.chat_error ? `<div class="small" style="color:#ffb98a;max-width:260px">${esc(r.live.chat_error.slice(0, 140))}</div>` : ""}`) : fmtNum(r.stats?.chat_messages || 0)}</td>
    <td class="dim">${ago(r.started_at)}</td>
    <td>${["live", "starting"].includes(r.status) ? `<button class="btn sm danger" data-stoprun="${r.id}">${ic("stop")}</button>` : ""}</td></tr>`).join("")}</table>`;
  $$("[data-stoprun]", el).forEach((b) => (b.onclick = () => api(`/api/runs/${b.dataset.stoprun}/stop`, { method: "POST" }).then(() => toast("Stopping…")).catch(fail)));
}

function facecamPicker(s) {
  const m = modal(`<h2>Facecam box · ${esc(s.name)}</h2><p class="muted small">Drag a box around the streamer's camera. The split layout puts it on top of the Short with gameplay underneath.</p>
    <div class="picker" id="picker"><img alt="stream frame"><div class="box hidden"></div></div>
    <div class="row" style="margin-top:16px"><button class="btn ghost" data-clear>Clear box</button><div class="spacer"></div><button class="btn ghost" data-cancel>Cancel</button><button class="btn primary" data-save>${ic("check")} Save</button></div>`, { wide: true });
  const pick = $("#picker", m), img = $("img", pick), box = $(".box", pick);
  let rect = s.facecam ? { ...s.facecam } : null;
  img.onerror = () => { pick.innerHTML = `<div class="empty"><div class="big-icon">${ic("scan")}</div><h4>No footage yet</h4><p>Watch this streamer (or process one of their VODs) first, then come back to draw the box.</p></div>`; };
  img.src = `/api/streamers/${s.id}/frame?t=${Date.now()}`;
  const draw = () => { if (!rect) return box.classList.add("hidden"); box.classList.remove("hidden"); Object.assign(box.style, { left: rect.x * 100 + "%", top: rect.y * 100 + "%", width: rect.w * 100 + "%", height: rect.h * 100 + "%" }); };
  draw();
  let start = null;
  const pt = (e) => { const b = pick.getBoundingClientRect(); return { x: Math.min(1, Math.max(0, (e.clientX - b.left) / b.width)), y: Math.min(1, Math.max(0, (e.clientY - b.top) / b.height)) }; };
  pick.onpointerdown = (e) => { start = pt(e); pick.setPointerCapture(e.pointerId); };
  pick.onpointermove = (e) => { if (!start) return; const p = pt(e); rect = { x: Math.min(start.x, p.x), y: Math.min(start.y, p.y), w: Math.abs(p.x - start.x), h: Math.abs(p.y - start.y) }; draw(); };
  pick.onpointerup = () => { start = null; if (rect && (rect.w < 0.03 || rect.h < 0.03)) { rect = null; draw(); } };
  $("[data-clear]", m).onclick = () => { rect = null; draw(); };
  $("[data-cancel]", m).onclick = () => m.close();
  $("[data-save]", m).onclick = async () => {
    try {
      const r = rect ? Object.fromEntries(Object.entries(rect).map(([k, v]) => [k, Math.round(v * 1000) / 1000])) : null;
      const d = await api(`/api/streamers/${s.id}`, { method: "PATCH", body: { facecam: r } });
      Object.assign(s, d); toast(r ? "Facecam saved — split layout unlocked" : "Facecam cleared"); m.close(); paintStreamers();
    } catch (e) { fail(e); }
  };
}

// ================================================================== VOD LAB
async function pageVod(page) {
  page.innerHTML = header("VOD Lab", "Drop a past broadcast or paste a link — HYPECUT scans the whole thing and pulls the best moments.") +
    `<div class="grid g2" style="margin-bottom:22px">
      <label class="drop" id="drop"><input type="file" id="file" accept="video/*,.mkv,.ts,.flv" hidden>${ic("upload")}<h3>Drop a stream recording</h3><div class="muted">MP4 · MKV · MOV · TS · FLV · WEBM</div><div class="progress hidden" id="up-prog" style="margin:16px auto 0;max-width:320px"><i style="width:0"></i></div></label>
      <div class="card col" style="justify-content:center">
        <h3 style="margin:0;font-family:var(--display);font-size:28px;font-weight:400;letter-spacing:1px">Or paste a VOD link</h3>
        <div class="muted small">Twitch past broadcasts, YouTube streams, Kick VODs — anything yt-dlp can download.</div>
        <form class="col" id="url-form"><input class="input big" name="url" placeholder="https://www.twitch.tv/videos/…" required>
          <div class="row"><select class="input" name="streamer_id" id="vod-streamer" style="flex:1"></select><button class="btn primary" type="submit">${ic("zap")} Scan it</button></div></form>
        <div class="small dim">Pick the streamer so clips get the right credit and permission.</div>
      </div></div>
     <div class="card"><div class="card-h"><h3>Jobs</h3></div><div id="vod-runs" style="overflow-x:auto"></div></div>`;
  [S.streamers, S.runs] = await Promise.all([api("/api/streamers"), api("/api/runs?limit=60")]);
  const opts = `<option value="">No streamer (own footage)</option>` + S.streamers.map((s) => `<option value="${s.id}">${esc(s.name)} · ${PLAT[s.platform]}</option>`).join("");
  $("#vod-streamer").innerHTML = opts;
  paintVodRuns();
  const drop = $("#drop"), file = $("#file");
  const upload = (f) => {
    if (!f) return;
    const fd = new FormData(); fd.append("file", f); fd.append("streamer_id", $("#vod-streamer").value);
    const xhr = new XMLHttpRequest();
    const bar = $("#up-prog"); bar.classList.remove("hidden");
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) $("i", bar).style.width = `${(e.loaded / e.total) * 100}%`; };
    xhr.onload = () => { bar.classList.add("hidden"); if (xhr.status < 300) toast(`Uploaded ${f.name} — scanning…`); else { try { fail(new Error(JSON.parse(xhr.responseText).detail)); } catch { fail(new Error("Upload failed")); } } };
    xhr.onerror = () => fail(new Error("Upload failed"));
    xhr.open("POST", "/api/vod/upload"); xhr.setRequestHeader("X-GTAClips", "1"); xhr.send(fd);
  };
  file.onchange = () => upload(file.files[0]);
  ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
  drop.addEventListener("drop", (e) => upload(e.dataTransfer.files[0]));
  $("#url-form").onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try { await api("/api/vod/url", { method: "POST", body: { url: fd.get("url"), streamer_id: fd.get("streamer_id") || null } }); toast("Downloading & scanning…"); e.target.reset(); }
    catch (err) { fail(err); }
  };
}

function paintVodRuns() {
  const el = $("#vod-runs"); if (!el) return;
  const rows = S.runs.filter((r) => r.kind === "vod");
  if (!rows.length) { el.innerHTML = `<div class="empty small">No VODs processed yet.</div>`; return; }
  el.innerHTML = `<table class="table"><tr><th>Source</th><th>Status</th><th>Progress</th><th>Length</th><th>Clips</th><th>When</th><th></th></tr>${rows.map((r) => `
    <tr><td class="ellipsis" style="max-width:300px" title="${esc(r.source)}">${esc(r.title)}</td><td>${runBadge(r)}${r.error ? `<div class="small" style="color:#ff95a0;max-width:300px">${esc(r.error)}</div>` : ""}</td>
    <td><div class="progress"><i style="width:${Math.round((r.progress || 0) * 100)}%"></i></div><span class="small dim">${Math.round((r.progress || 0) * 100)}%</span></td>
    <td class="mono">${fmtDur(r.stats?.duration)}</td><td>${r.stats?.clips ?? r.stats?.moments ?? "—"}</td><td class="dim">${ago(r.started_at)}</td>
    <td class="nowrap">${["processing", "downloading"].includes(r.status) ? `<button class="btn sm danger" data-stoprun="${r.id}">${ic("stop")}</button>` : ""}
      ${r.status === "done" ? `<a class="btn sm" href="#/review">Review ${ic("right")}</a>` : ""}
      ${r.status === "done" && r.source && !r.source.startsWith("http") ? `<button class="btn sm ghost" data-sim="${esc(r.source)}" title="Replay this file as if it were live — tests the live pipeline">${ic("radio")} Replay live</button>` : ""}</td></tr>`).join("")}</table>`;
  $$("[data-stoprun]", el).forEach((b) => (b.onclick = () => api(`/api/runs/${b.dataset.stoprun}/stop`, { method: "POST" }).then(() => toast("Cancelling…")).catch(fail)));
  $$("[data-sim]", el).forEach((b) => (b.onclick = () => api("/api/live", { method: "POST", body: { simulate: b.dataset.sim } }).then(() => { toast("Replaying as live — watch the radar"); location.hash = "#/"; }).catch(fail)));
}

// ================================================================== SCHEDULE
async function pageSchedule(page) {
  page.innerHTML = header("Schedule", "Approved clips drop into your posting slots automatically", `<a class="btn" href="#/settings?tab=schedule">${ic("clock")} Edit slots</a>`) + `<div id="sched"></div>`;
  await loadSchedule();
}

async function loadSchedule() {
  const el = $("#sched"); if (!el) return;
  const posts = await api("/api/posts?limit=400");
  const upcoming = posts.filter((p) => ["scheduled", "posting"].includes(p.status)).sort((a, b) => new Date(a.scheduled_at) - new Date(b.scheduled_at));
  const failed = posts.filter((p) => p.status === "failed");
  const done = posts.filter((p) => p.status === "posted").sort((a, b) => new Date(b.posted_at) - new Date(a.posted_at)).slice(0, 30);
  const byDay = {};
  upcoming.forEach((p) => { (byDay[dayOf(p.scheduled_at)] ||= []).push(p); });
  const row = (p, kind) => `<div class="post-row" data-post="${p.id}">
      <div class="time">${timeOf(kind === "done" ? p.posted_at : p.scheduled_at)}</div>
      ${p.has_thumb ? `<img src="/api/clips/${p.clip_id}/thumb" alt="">` : "<div></div>"}
      <div style="min-width:0"><div class="ellipsis" style="font-weight:700">${esc(p.title || "Clip #" + p.clip_id)}</div>
        <div class="row small" style="gap:6px;margin-top:3px"><span class="badge ${p.platform}">${ic(p.platform === "youtube" ? "yt" : "ig")} ${PLAT[p.platform]}</span>${p.streamer ? `<span class="dim">${esc(p.streamer)}</span>` : ""}
        ${kind === "done" ? `<span class="dim">· ${fmtNum(p.views)} views · ${fmtNum(p.likes)} likes</span>` : ""}
        ${p.status === "posting" ? `<span class="badge info"><span class="spinner sm"></span> uploading</span>` : ""}
        ${p.error ? `<span class="small" style="color:#ff95a0">${esc(p.error.slice(0, 160))}</span>` : ""}</div></div>
      <div class="row">${kind === "up" && p.status === "scheduled" ? `<input type="datetime-local" class="input" style="width:auto;padding:7px 10px" value="${toLocalInput(p.scheduled_at)}" data-move><button class="btn sm cyan" data-now>${ic("zap")} Now</button><button class="btn sm ghost" data-cancel>${ic("x")}</button>` : ""}
        ${kind === "fail" ? `<button class="btn sm" data-retry>${ic("refresh")} Retry</button><button class="btn sm ghost" data-cancel>${ic("x")}</button>` : ""}
        ${kind === "done" && p.url ? `<a class="btn sm ghost" href="${esc(p.url)}" target="_blank" rel="noopener">${ic("ext")} Open</a>` : ""}</div></div>`;
  el.innerHTML = `
    ${failed.length ? `<div class="card" style="margin-bottom:22px;border-color:rgba(255,77,94,.4)"><div class="card-h"><h3 style="color:#ff95a0">Needs attention</h3></div>${failed.map((p) => row(p, "fail")).join("")}</div>` : ""}
    <div class="grid g2" style="align-items:start">
      <div class="card"><div class="card-h"><h3>Upcoming</h3><div class="spacer"></div><span class="badge">${upcoming.length}</span></div>
        ${upcoming.length ? Object.entries(byDay).map(([d, ps]) => `<div class="day"><div class="day-h"><b>${d}</b> · ${ps.length} post${ps.length > 1 ? "s" : ""}</div>${ps.map((p) => row(p, "up")).join("")}</div>`).join("") : `<div class="empty"><div class="big-icon">${ic("calendar")}</div><h4>Queue is empty</h4><p>Approve clips in Review and they land here.</p><a class="btn primary" href="#/review">Go review</a></div>`}</div>
      <div class="card"><div class="card-h"><h3>Recently posted</h3></div>${done.length ? done.map((p) => row(p, "done")).join("") : `<div class="empty small">Nothing posted yet.</div>`}</div>
    </div>`;
  $$("[data-post]", el).forEach((r) => {
    const id = r.dataset.post;
    const b = (sel, fn) => { const x = $(sel, r); if (x) x.onclick = fn; };
    b("[data-now]", () => api(`/api/posts/${id}/now`, { method: "POST" }).then(() => toast("Uploading now 🚀")).catch(fail));
    b("[data-cancel]", () => api(`/api/posts/${id}/cancel`, { method: "POST" }).then(() => { toast("Cancelled"); loadSchedule(); }).catch(fail));
    b("[data-retry]", () => api(`/api/posts/${id}/retry`, { method: "POST" }).then(() => { toast("Retrying"); loadSchedule(); }).catch(fail));
    const mv = $("[data-move]", r);
    if (mv) mv.onchange = () => api(`/api/posts/${id}`, { method: "PATCH", body: { scheduled_at: new Date(mv.value).toISOString() } }).then(() => { toast("Moved"); loadSchedule(); }).catch(fail);
  });
}

// ================================================================== ANALYTICS / MONEY
async function pageAnalytics(page) {
  const [ov, tune] = await Promise.all([api("/api/analytics"), api("/api/analytics/autotune")]);
  const cur = ov.currency || "$";
  const posts = (ov.posts || {}).posted || 0;
  const maxS = Math.max(1, ...ov.by_streamer.map((s) => s.views));
  const sigs = Object.entries(ov.by_signal || {}).sort((a, b) => b[1].avg_views - a[1].avg_views);
  const maxSig = Math.max(1, ...sigs.map(([, v]) => v.avg_views));
  page.innerHTML = header("Money", "Views, earnings, and what kind of moment actually performs",
    `<button class="btn" id="refresh">${ic("refresh")} Refresh stats</button>`) + `
    <div class="stats" style="grid-template-columns:repeat(4,minmax(0,1fr))">
      <div class="stat lime"><div class="label">${ic("dollar")} Est. earnings</div><div class="value grad-text">${fmtMoney(ov.earnings, cur)}</div><div class="foot">campaign CPM + platform ad share</div></div>
      <div class="stat violet"><div class="label">${ic("eye")} Total views</div><div class="value">${fmtNum(ov.views)}</div><div class="foot">${posts} posts</div></div>
      <div class="stat cyan"><div class="label">${ic("activity")} Avg / post</div><div class="value">${fmtNum(posts ? ov.views / posts : 0)}</div><div class="foot">views per Short/Reel</div></div>
      <div class="stat pink"><div class="label">${ic("dollar")} Per post</div><div class="value">${fmtMoney(posts ? ov.earnings / posts : 0, cur)}</div><div class="foot">earnings per upload</div></div>
    </div>
    <div class="grid g-main" style="margin-bottom:18px">
      <div class="card"><div class="card-h"><h3>Views by post day · 30 days</h3></div><canvas class="chart" id="an-chart"></canvas></div>
      <div class="card"><div class="card-h"><h3>Platforms</h3></div>
        ${["youtube", "instagram"].map((p) => { const d = ov.by_platform[p] || { views: 0, posts: 0, earnings: 0 }; return `<div class="row" style="margin-bottom:14px"><span class="badge ${p}" style="font-size:12px;padding:6px 10px">${ic(p === "youtube" ? "yt" : "ig")} ${PLAT[p]}</span><div class="spacer"></div><div style="text-align:right"><div style="font-family:var(--display);font-size:28px;line-height:1">${fmtNum(d.views)}</div><div class="small dim">${d.posts} posts · ${fmtMoney(d.earnings, cur)}</div></div></div>`; }).join("")}
        <hr class="sep"><div class="help">Earnings = views × (streamer's <b>pay per 1K</b> + platform <b>RPM</b> from Settings → Money). It's an estimate — check your campaign dashboards for the real payout.</div>
      </div>
    </div>
    <div class="grid g2" style="margin-bottom:18px;align-items:start">
      <div class="card"><div class="card-h"><h3>By streamer</h3></div>
        ${ov.by_streamer.length ? ov.by_streamer.map((s) => `<div class="hbar"><span class="ellipsis" style="font-weight:700">${esc(s.name)}</span><div class="track"><i style="width:${(s.views / maxS) * 100}%"></i></div><span class="mono small" style="text-align:right">${fmtMoney(s.earnings, cur)}</span></div>`).join("") : `<div class="empty small">No posted clips yet.</div>`}</div>
      <div class="card"><div class="card-h"><h3>What works · avg views by trigger</h3></div>
        ${sigs.length ? sigs.map(([k, v]) => `<div class="hbar"><span style="font-weight:700">${SIG[k]?.[0] || k}</span><div class="track"><i style="width:${(v.avg_views / maxSig) * 100}%;background:${SIG[k]?.[1] || "#ff2e88"}"></i></div><span class="mono small" style="text-align:right">${fmtNum(v.avg_views)}</span></div>`).join("") : `<div class="empty small">Post a few clips to learn which moments pop.</div>`}</div>
    </div>
    <div class="grid g2" style="align-items:start">
      <div class="card"><div class="card-h"><h3>Top clips</h3></div>
        ${ov.top.length ? `<table class="table">${ov.top.map((t, i) => `<tr><td class="mono dim">${i + 1}</td><td class="ellipsis" style="max-width:260px;font-weight:700">${esc(t.title)}</td><td><span class="badge ${t.platform}">${PLAT[t.platform]}</span></td><td class="mono">${fmtNum(t.views)}</td><td>${t.url ? `<a class="btn sm ghost" href="${esc(t.url)}" target="_blank" rel="noopener">${ic("ext")}</a>` : ""}</td></tr>`).join("")}</table>` : `<div class="empty small">Nothing yet.</div>`}</div>
      <div class="card"><div class="card-h"><h3>Auto-tune detection</h3><div class="spacer"></div>${ic("wand").replace("<svg", '<svg style="width:18px;height:18px;color:#a78bfa"')}</div>
        <div class="help" style="margin-bottom:14px">Learns from your own view counts: triggers that lead to big views get more weight, the rest get less.</div>
        ${tune.ready ? `<table class="table"><tr><th>Signal</th><th>Now</th><th>Proposed</th><th>Corr.</th></tr>${Object.keys(tune.current).map((k) => `<tr><td>${SIG[k]?.[0] || k}</td><td class="mono">${tune.current[k]}</td><td class="mono" style="color:${tune.proposed[k] > tune.current[k] ? "#7dffc0" : tune.proposed[k] < tune.current[k] ? "#ff95a0" : "inherit"}">${tune.proposed[k]}</td><td class="mono dim">${tune.correlations[k] ?? "—"}</td></tr>`).join("")}</table><button class="btn primary" id="apply-tune" style="margin-top:14px">${ic("check")} Apply new weights</button>`
          : `<div class="row"><div class="progress" style="flex:1"><i style="width:${(tune.have / tune.needed) * 100}%"></i></div><span class="small dim">${tune.have}/${tune.needed} posted clips</span></div>`}
      </div>
    </div>`;
  drawBars($("#an-chart"), ov.days.map((d) => ({ label: d.day.slice(5), value: d.views })));
  $("#refresh").onclick = async (e) => { e.currentTarget.disabled = true; try { const r = await api("/api/analytics/refresh", { method: "POST" }); toast(`Updated ${r.updated} posts${r.errors.length ? " · " + r.errors[0] : ""}`, r.errors.length ? "err" : "ok"); PAGES.analytics(page); } catch (er) { fail(er); } };
  const ap = $("#apply-tune");
  if (ap) ap.onclick = () => api("/api/analytics/autotune/apply", { method: "POST" }).then(() => { toast("Weights updated"); PAGES.analytics(page); }).catch(fail);
}

// ================================================================== SETTINGS
const STABS = [["accounts", "Accounts", "link"], ["ai", "AI editor", "sparkles"], ["detection", "Detection", "sliders"], ["style", "Video style", "palette"], ["schedule", "Schedule", "calendar"], ["money", "Money", "dollar"], ["general", "General", "gear"], ["security", "Security", "shield"]];

async function pageSettings(page) {
  if (S.params.get("tab")) S.settingsTab = S.params.get("tab");
  const yt = S.params.get("yt");
  if (yt === "ok") toast("YouTube connected ✓"); else if (yt === "error") toast("YouTube connection failed — check client ID/secret and redirect URI", "err", 7000); else if (yt === "signin") toast("Sign in first, then connect YouTube", "err");
  if (yt) history.replaceState(null, "", "#/settings?tab=accounts");
  S.settings = await api("/api/settings");
  page.innerHTML = header("Settings", "Everything is saved on your machine — keys never leave it except to the service they belong to") +
    `<div class="settings"><div class="subnav">${STABS.map(([k, l, i]) => `<button data-stab="${k}" class="${S.settingsTab === k ? "on" : ""}">${ic(i)} ${l}</button>`).join("")}</div><div id="spane"></div></div>`;
  $$("[data-stab]").forEach((b) => (b.onclick = () => { S.settingsTab = b.dataset.stab; $$("[data-stab]").forEach((x) => x.classList.toggle("on", x === b)); paintSettings(); }));
  paintSettings();
}

// field builders — inputs carry data-path="section.key[.sub]" and data-type
const F = {
  text: (path, label, hint = "", ph = "", type = "text") => `<label class="field">${label}${hint ? ` <span class="hint">${hint}</span>` : ""}<input class="input" data-path="${path}" data-type="text" type="${type}" placeholder="${esc(ph)}" value="${esc(getP(path))}" autocomplete="off"></label>`,
  secret: (path, label, hint = "") => `<label class="field">${label}${hint ? ` <span class="hint">${hint}</span>` : ""}<input class="input mono" data-path="${path}" data-type="text" type="password" placeholder="${getP(path) ? "•••••••• (saved — type to replace)" : "not set"}" value="" autocomplete="new-password"></label>`,
  num: (path, label, hint = "", step = "any", min = "") => `<label class="field">${label}${hint ? ` <span class="hint">${hint}</span>` : ""}<input class="input" data-path="${path}" data-type="number" type="number" step="${step}" min="${min}" value="${esc(getP(path))}"></label>`,
  toggle: (path, label, hint = "") => `<div><label class="switch"><input type="checkbox" data-path="${path}" data-type="bool" ${getP(path) ? "checked" : ""}><span class="track"></span>${label}</label>${hint ? `<div class="help" style="margin:4px 0 0 52px">${hint}</div>` : ""}</div>`,
  select: (path, label, options, hint = "") => `<label class="field">${label}${hint ? ` <span class="hint">${hint}</span>` : ""}<select class="input" data-path="${path}" data-type="text">${options.map((o) => { const [v, l] = Array.isArray(o) ? o : [o, o]; return `<option value="${esc(v)}" ${String(getP(path)) === String(v) ? "selected" : ""}>${esc(l)}</option>`; }).join("")}</select></label>`,
  range: (path, label, min, max, step) => `<div class="range-row"><span class="small" style="font-weight:700">${label}</span><input type="range" data-path="${path}" data-type="number" min="${min}" max="${max}" step="${step}" value="${esc(getP(path))}"><span class="val" data-val="${path}">${esc(getP(path))}</span></div>`,
  list: (path, label, hint = "", rows = 3) => `<label class="field">${label}${hint ? ` <span class="hint">${hint}</span>` : ""}<textarea class="input" rows="${rows}" data-path="${path}" data-type="list">${esc((getP(path) || []).join(", "))}</textarea></label>`,
  textarea: (path, label, hint = "") => `<label class="field">${label}${hint ? ` <span class="hint">${hint}</span>` : ""}<textarea class="input" rows="3" data-path="${path}" data-type="text">${esc(getP(path))}</textarea></label>`,
  color: (path, label) => `<label class="field">${label}<input class="input" type="color" data-path="${path}" data-type="text" value="${esc(getP(path))}"></label>`,
};
function getP(path) { return path.split(".").reduce((o, k) => (o == null ? undefined : o[k]), S.settings.settings) ?? ""; }

function collect(root) {
  const out = {};
  $$("[data-path]", root).forEach((el) => {
    const [section, ...rest] = el.dataset.path.split(".");
    let v;
    if (el.dataset.type === "bool") v = el.checked;
    else if (el.dataset.type === "number") v = el.value === "" ? 0 : Number(el.value);
    else if (el.dataset.type === "list") v = el.value.split(/[,\n]/).map((x) => x.trim()).filter(Boolean);
    else v = el.value;
    if (el.type === "password" && !v) return; // unchanged secret
    out[section] ||= {};
    let o = out[section];
    rest.slice(0, -1).forEach((k) => (o = o[k] ||= {}));
    o[rest[rest.length - 1]] = v;
  });
  return out;
}

async function saveSection(root, btn) {
  const data = collect(root);
  btn && (btn.disabled = true);
  try {
    for (const [section, vals] of Object.entries(data)) await api(`/api/settings/${section}`, { method: "PUT", body: vals });
    S.settings = await api("/api/settings");
    toast("Saved");
  } catch (e) { fail(e); }
  btn && (btn.disabled = false);
}

const saveBtn = `<div class="row"><div class="spacer"></div><button class="btn primary" data-save>${ic("check")} Save changes</button></div>`;

function paintSettings() {
  const pane = $("#spane"); if (!pane) return;
  const st = S.settings.status;
  const t = S.settingsTab;
  let html = "";
  if (t === "accounts") {
    html = `
    <div class="card section">
      <div class="acct"><div class="logo yt">${ic("yt").replace('fill="#000"', 'fill="#ff0033"').replace("currentColor", "#fff")}</div><div><h4>YouTube Shorts</h4><div class="small">${st.youtube_connected ? `<span class="badge ok">${ic("check")} connected${st.youtube_channel ? " · " + esc(st.youtube_channel) : ""}</span>` : `<span class="badge warn">not connected</span>`}</div></div><div class="spacer"></div>
        ${st.youtube_connected ? `<button class="btn danger sm" id="yt-disc">Disconnect</button>` : ""}<button class="btn primary" id="yt-conn">${ic("link")} ${st.youtube_connected ? "Reconnect" : "Connect YouTube"}</button></div>
      <div class="field-row">${F.text("youtube.client_id", "OAuth client ID")}${F.secret("youtube.client_secret", "OAuth client secret")}</div>
      <div class="field-row">${F.select("youtube.privacy", "Upload as", [["public", "Public"], ["unlisted", "Unlisted"], ["private", "Private (test)"]])}${F.secret("youtube.api_key", "API key (for live chat)", "Needed only to read YouTube live chat")}</div>
      ${F.toggle("youtube.add_shorts_tag", "Add #Shorts to the description")}
      <details class="help"><summary>How to get these (5 min, one time)</summary><ol>
        <li>Open <b>console.cloud.google.com</b> → create a project → enable <b>YouTube Data API v3</b>.</li>
        <li>OAuth consent screen → External → add yourself as a test user (or publish the app).</li>
        <li>Credentials → Create <b>OAuth client ID</b> → type <b>Web application</b> → authorized redirect URI:<br><code>${esc(st.youtube_redirect_uri)}</code></li>
        <li>Paste the client ID + secret here, Save, then press <b>Connect YouTube</b>.</li>
        <li>Optional: Credentials → Create <b>API key</b> for reading YouTube live chat.</li></ol>
        Uploads use your YouTube API quota (about 6 uploads/day on the default quota — request more in Google Cloud if you need it).</details>
      ${saveBtn}
    </div>
    <div class="card section" style="margin-top:18px">
      <div class="acct"><div class="logo ig">${ic("ig").replace("currentColor", "#fff")}</div><div><h4>Instagram Reels</h4><div class="small">${st.instagram_connected ? `<span class="badge ok">${ic("check")} set${st.instagram_username ? " · @" + esc(st.instagram_username) : ""}</span>` : `<span class="badge warn">not connected</span>`}</div></div><div class="spacer"></div><button class="btn" id="ig-test">${ic("refresh")} Test connection</button></div>
      <div class="field-row">${F.text("instagram.user_id", "Instagram account ID", "Numeric IG business/creator ID")}${F.secret("instagram.access_token", "Long-lived access token")}</div>
      <div class="field-row">${F.select("instagram.upload_mode", "Upload method", [["resumable", "Direct upload (recommended)"], ["url", "Public URL (needs Public base URL)"]])}${F.text("instagram.graph_version", "Graph API version")}</div>
      ${F.toggle("instagram.share_to_feed", "Also show Reels on the profile grid")}
      <details class="help"><summary>How to get these</summary><ol>
        <li>Switch your Instagram to a <b>Creator</b> or <b>Business</b> account and link it to a Facebook Page.</li>
        <li>At <b>developers.facebook.com</b> create an app → add <b>Instagram</b> (Graph API) with permissions <code>instagram_content_publish</code>, <code>instagram_basic</code>, <code>pages_show_list</code>, <code>instagram_manage_insights</code>.</li>
        <li>Generate a user token in Graph API Explorer, exchange it for a <b>long-lived token</b> (60 days), and read your IG user ID from <code>/me/accounts?fields=instagram_business_account</code>.</li>
        <li>Paste both here and hit <b>Test connection</b>. Refresh the token before it expires.</li></ol></details>
      ${saveBtn}
    </div>`;
  } else if (t === "ai") {
    html = `<div class="card section">
      <div class="row"><h4>AI editor</h4><div class="spacer"></div>${st.ai_key_set ? `<span class="badge ok">key saved</span>` : `<span class="badge warn">no key — using templates</span>`}<button class="btn sm" id="ai-test">${ic("zap")} Test</button></div>
      <div class="help">Claude looks at frames from each moment plus the transcript, skips duds, and writes the hook, title, caption and hashtags.</div>
      ${F.toggle("ai.enabled", "Use the AI editor")}
      <div class="field-row">${F.secret("ai.api_key", "Anthropic API key", "console.anthropic.com → API keys")}${F.select("ai.model", "Model", [["claude-opus-5-5", "Claude Opus 5.5 (best)"], ["claude-sonnet-5-5", "Claude Sonnet 5.5 (cheaper)"], ["claude-haiku-5-5", "Claude Haiku 5.5 (cheapest)"]])}${F.select("ai.effort", "Effort", [["low", "Low (fast)"], ["medium", "Medium"], ["high", "High (pickier)"]])}</div>
      ${F.toggle("ai.auto_reject", "Auto-skip clips the AI says aren't worth posting")}
      ${F.range("ai.min_virality", "Min virality", 0, 100, 1)}
      ${F.textarea("ai.style", "Voice & style", "How your hooks and captions should sound")}
      ${F.list("ai.default_hashtags", "Hashtag pool", "Comma separated", 2)}
      ${saveBtn}</div>`;
  } else if (t === "detection") {
    const w = ["audio", "chat", "motion", "speech", "game"];
    html = `<div class="card section">
      <h4>Trigger sensitivity</h4><div class="help">Each signal is compared with that stream's own normal level. The hype score is a soft-OR: one strong signal or several medium ones trigger a clip. Lower threshold = more clips.</div>
      ${F.range("detection.threshold", "Threshold", 0.2, 0.95, 0.01)}
      <h4 style="margin-top:6px">Signal weights</h4>
      ${w.map((k) => F.range(`detection.weights.${k}`, SIG[k][0], 0, 2.5, 0.05)).join("")}
      <div class="field-row">${F.num("detection.pre_roll", "Seconds before peak", "", "0.5", "0")}${F.num("detection.post_roll", "Seconds after peak", "", "0.5", "0")}${F.num("detection.min_len", "Min clip length (s)", "", "1", "5")}${F.num("detection.max_len", "Max clip length (s)", "Shorts ≤ 60s", "1", "10")}</div>
      <div class="field-row">${F.num("detection.cooldown", "Cooldown between clips (s)", "", "1", "0")}${F.num("detection.buffer_minutes", "Live buffer (min)", "", "1", "2")}${F.num("detection.max_clips_per_vod", "Max clips per VOD", "", "1", "1")}${F.num("detection.chat_delay", "Chat delay (s)", "", "0.5", "0")}</div>
      ${F.list("detection.hype_words", "Chat hype words & emotes", "These count extra in chat velocity")}
      ${F.list("detection.speech_words", "Speech hype phrases", "Needs Whisper")}
      ${F.list("detection.game_words", "In-game banner words (OCR)", "Needs tesseract", 2)}
      ${F.toggle("detection.use_whisper_live", "Transcribe streams live for the speech signal", st.whisper ? "Uses extra CPU — fine on a decent machine or GPU." : "Install faster-whisper (requirements-ml.txt) to enable.")}
      ${F.toggle("detection.use_ocr", "Read in-game banners with OCR", st.tesseract ? "Looks for WASTED / BUSTED etc. every 2 seconds." : "Install tesseract + pytesseract to enable.")}
      ${saveBtn}</div>`;
  } else if (t === "style") {
    html = `<div class="card section"><div class="row" style="align-items:flex-start;gap:26px">
      <div class="col" style="flex:1;min-width:260px;gap:16px">
        ${F.select("render.default_layout", "Default layout", [["auto", "Full screen 9:16, no facecam (recommended)"], ["blur", "Blurred background"], ["split", "Facecam on top + gameplay"]])}
        ${F.select("render.audio_mode", "Audio", [["game_only", "Game audio only — remove the streamer's voice"], ["original", "Original (streamer + game)"], ["mute", "Muted"]], st.voice ? "Voice removal also removes in-game dialogue; engines, guns, music stay." : "Game-only needs the voice-removal model: pip install -r requirements-ml.txt")}
        ${F.toggle("render.captions", "Burn in word-by-word captions", "Only used with Original audio (captions transcribe the streamer's voice).")}
        <div class="field-row">${F.color("render.caption_color", "Caption")}${F.color("render.highlight_color", "Active word")}${F.color("render.progress_color", "Accent / bar")}</div>
        ${F.range("render.caption_size", "Caption size", 50, 130, 1)}
        ${F.range("render.caption_position", "Caption height", 0.35, 0.85, 0.01)}
        ${F.range("render.hook_seconds", "Hook seconds", 0, 8, 0.5)}
        ${F.text("render.credit_template", "Credit line", "{platform_url} and {name} are filled in", "🎥 {platform_url}")}
        ${F.toggle("render.progress_bar", "Progress bar")}
        <div class="field-row">${F.select("render.whisper_model", "Speech model", [["tiny", "tiny (fastest)"], ["base", "base"], ["small", "small (better)"], ["medium", "medium (GPU)"], ["large-v3", "large-v3 (GPU)"]])}${F.select("render.preset", "Encode speed", ["ultrafast", "veryfast", "fast", "medium", "slow"])}${F.num("render.crf", "Quality (CRF)", "lower = better", "1", "14")}</div>
      </div>
      <div class="col" style="align-items:center;position:sticky;top:20px"><div class="preview-916" id="pv"><div class="pv-hook">HE STOLE A COP CAR</div><div class="pv-cap"><span data-hl>NO</span> WAY BRO</div><div class="pv-credit">twitch.tv/streamer</div><div class="pv-bar"></div></div><div class="small dim">live preview</div></div>
    </div>${saveBtn}</div>`;
  } else if (t === "schedule") {
    const zones = (Intl.supportedValuesOf ? Intl.supportedValuesOf("timeZone") : []).map((z) => `<option value="${z}">`).join("");
    html = `<div class="card section">
      <h4>Posting slots</h4><div class="help">One post per platform per slot. Approved clips fill the next free slot. Times are in the timezone below.</div>
      <div class="chips" id="slots"></div>
      <div class="row"><input class="input" type="time" id="slot-in" style="width:auto"><button class="btn sm" id="slot-add">${ic("plus")} Add slot</button></div>
      <label class="field">Timezone<input class="input" list="tzs" data-path="general.timezone" data-type="text" value="${esc(getP("general.timezone"))}"><datalist id="tzs">${zones}</datalist></label>
      <div class="row">${["youtube", "instagram"].map((p) => `<label class="platform-toggle"><input type="checkbox" data-plat-default="${p}" ${(getP("schedule.platforms") || []).includes(p) ? "checked" : ""}> Post to ${PLAT[p]} by default</label>`).join("")}</div>
      <hr class="sep"><h4>${ic("wand").replace("<svg", '<svg style="width:16px;height:16px;vertical-align:-3px;color:#a78bfa"')} Autopilot</h4>
      ${F.toggle("schedule.autopilot", "Auto-approve hot clips from streamers you have permission for", "Clips at or above the virality bar go straight into the schedule — no review needed.")}
      ${F.range("schedule.autopilot_min_virality", "Virality bar", 40, 100, 1)}
      ${F.num("schedule.max_retries", "Upload retries", "", "1", "1")}
      ${saveBtn}</div>`;
  } else if (t === "money") {
    html = `<div class="card section">
      <h4>Earnings model</h4><div class="help">Used for the estimates on the Money page. Set a streamer's own rate on the Streams page (“Pays per 1K views”).</div>
      <div class="field-row">${F.num("money.youtube_rpm", "YouTube Shorts RPM", "your ad share per 1K views", "0.01", "0")}${F.num("money.instagram_rpm", "Instagram RPM", "bonus programs, if any", "0.01", "0")}${F.num("money.default_cpm", "Default campaign CPM", "per 1K views when a streamer has none", "0.05", "0")}${F.text("money.currency", "Currency symbol")}</div>
      <hr class="sep"><h4>The playbook</h4><div class="help"><ol>
        <li><b>Clipping campaigns</b> — streamers and brands pay per 1K views on clipping marketplaces. Join GTA campaigns, add those streamers with their rate, and let HYPECUT pump out clips. Fastest money.</li>
        <li><b>Clip for streamers directly</b> — offer mid-size GTA streamers a monthly fee or revenue share. Your pitch: “Every stream → 10 Shorts by morning.”</li>
        <li><b>Your own GTA VI channel</b> — permitted clips + strong hooks → YouTube Partner Program (Shorts ad share) and Instagram reach.</li>
        <li><b>Sell the tool</b> — once it's proven, streamers pay monthly to auto-clip themselves.</li></ol>
        Always get permission, credit the streamer, and add real edits (hooks, captions) — reposting raw footage gets copyright strikes and fails YouTube's reused-content review.</div>
      ${saveBtn}</div>`;
  } else if (t === "general") {
    html = `<div class="card section">
      <div class="field-row">${F.text("general.game", "Game", "Used in AI prompts and fallback titles")}${F.text("general.public_base_url", "Public base URL", "Only if you reach this dashboard via a domain/tunnel", "https://clips.example.com")}</div>
      ${saveBtn}
      <hr class="sep"><h4>System check</h4>
      <div class="row">${[["ffmpeg", st.ffmpeg, "video engine"], ["ffmpeg text (libass)", st.ffmpeg_libass, "captions + hook text"], ["voice removal (demucs)", st.voice, "game-only audio"], ["faster-whisper", st.whisper, "captions + speech signal"], ["tesseract", st.tesseract, "in-game OCR"]].map(([n, ok, d]) => `<span class="badge ${ok ? "ok" : "warn"}">${ok ? ic("check") : ic("alert")} ${n} <span class="dim" style="font-weight:600">· ${d}</span></span>`).join("")}</div>
    </div>`;
  } else if (t === "security") {
    html = `<div class="card section">
      <h4>Change password</h4>
      <form class="col" id="pw-form" style="max-width:420px">
        <input type="text" value="owner" autocomplete="username" hidden>
        <input class="input" type="password" name="current" placeholder="Current password" autocomplete="current-password" required>
        <input class="input" type="password" name="new" placeholder="New password (8+ chars)" minlength="8" autocomplete="new-password" required>
        <button class="btn primary" type="submit" style="align-self:flex-start">${ic("lock")} Update password</button></form>
      <div class="help">Changing the password signs out every other device.</div>
      <hr class="sep"><h4>Sessions</h4>
      <div class="row"><button class="btn danger" id="logout-all">${ic("logout")} Sign out everywhere</button></div>
      <hr class="sep"><div class="help"><b>Keep it private:</b> the server listens on 127.0.0.1 by default. To use it from your phone, put it behind Tailscale or a Cloudflare Tunnel with HTTPS rather than opening a port. Forgot the password? Run <code>python -m gtaclips set-password</code> on the machine.</div>
    </div>`;
  }
  pane.innerHTML = html;
  $$("[data-save]", pane).forEach((b) => (b.onclick = () => {
    if (t === "schedule") {
      const plats = $$("[data-plat-default]", pane).filter((x) => x.checked).map((x) => x.dataset.platDefault);
      return saveSection(pane, b).then(() => api("/api/settings/schedule", { method: "PUT", body: { platforms: plats, slots: slotState } })).then(async () => { S.settings = await api("/api/settings"); }).catch(fail);
    }
    return saveSection(b.closest(".card"), b);
  }));
  $$('input[type="range"]', pane).forEach((r) => (r.oninput = () => { const v = $(`[data-val="${r.dataset.path}"]`, pane); if (v) v.textContent = r.value; stylePreview(); }));
  $$('input[type="color"]', pane).forEach((r) => (r.oninput = stylePreview));
  stylePreview();
  // account actions
  const on = (id, fn) => { const x = $(id, pane); if (x) x.onclick = fn; };
  on("#yt-conn", async () => { try { await saveSection(pane.querySelector(".card")); const r = await api("/api/settings/youtube/connect", { method: "POST" }); location.href = r.url; } catch (e) { fail(e); } });
  on("#yt-disc", async () => { await api("/api/settings/youtube/disconnect", { method: "POST" }).catch(fail); S.settings = await api("/api/settings"); paintSettings(); });
  on("#ig-test", async (e) => { const b = e.currentTarget; b.disabled = true; try { await saveSection(b.closest(".card")); const r = await api("/api/settings/instagram/test", { method: "POST" }); toast(`Instagram OK — @${r.username}`); S.settings = await api("/api/settings"); paintSettings(); } catch (er) { fail(er); } b.disabled = false; });
  on("#ai-test", async (e) => { const b = e.currentTarget; b.disabled = true; try { await saveSection(b.closest(".card")); const r = await api("/api/settings/ai/test", { method: "POST" }); toast(`AI says: ${r.reply}`); S.settings = await api("/api/settings"); } catch (er) { fail(er); } b.disabled = false; });
  on("#logout-all", async () => { if (await confirmBox("Sign out everywhere?", "Every device, including this one, will need the password again.", "Sign out all", true)) { await api("/api/auth/logout-all", { method: "POST" }).catch(() => {}); S.authed = false; renderAuth(); } });
  const pw = $("#pw-form", pane);
  if (pw) pw.onsubmit = async (e) => { e.preventDefault(); try { await api("/api/auth/password", { method: "POST", body: Object.fromEntries(new FormData(pw)) }); toast("Password updated"); pw.reset(); } catch (er) { fail(er); } };
  // slots editor
  let slotState = [...(getP("schedule.slots") || [])];
  const paintSlots = () => { const el = $("#slots", pane); if (!el) return; el.innerHTML = slotState.sort().map((s) => `<span class="chip cyan">${ic("clock").replace("<svg", '<svg style="width:12px;height:12px"')} ${esc(s)}<button data-rm="${esc(s)}" title="Remove">×</button></span>`).join("") || `<span class="small dim">No slots — add at least one.</span>`; $$("[data-rm]", el).forEach((b) => (b.onclick = () => { slotState = slotState.filter((x) => x !== b.dataset.rm); paintSlots(); })); };
  paintSlots();
  on("#slot-add", () => { const v = $("#slot-in", pane).value; if (v && !slotState.includes(v)) { slotState.push(v); paintSlots(); } });
}

function stylePreview() {
  const pv = $("#pv"); if (!pv) return;
  const val = (p) => { const el = $(`[data-path="${p}"]`); return el ? el.value : getP(p); };
  const accent = val("render.progress_color");
  $(".pv-hook", pv).style.background = accent;
  const cap = $(".pv-cap", pv);
  cap.style.color = val("render.caption_color");
  cap.style.top = `${Number(val("render.caption_position")) * 100}%`;
  cap.style.fontSize = `${Number(val("render.caption_size")) / 6.5}px`;
  $("[data-hl]", pv).style.color = val("render.highlight_color");
  $(".pv-bar", pv).style.background = accent;
}

// ------------------------------------------------------------------ pages registry
const PAGES = { dashboard: pageDashboard, review: pageReview, streams: pageStreams, vod: pageVod, schedule: pageSchedule, analytics: pageAnalytics, settings: pageSettings };

// ------------------------------------------------------------------ boot
async function boot() {
  try {
    const st = await api("/api/auth/status");
    S.configured = st.configured; S.authed = st.authed;
  } catch { S.authed = false; }
  if (!S.authed) return renderAuth();
  renderShell();
  connectStream();
  try { [S.settings, S.streamers] = await Promise.all([api("/api/settings"), api("/api/streamers")]); } catch {}
  await render();
}

window.addEventListener("hashchange", () => { if (S.authed) { $$(".modal-back").forEach((m) => m.close && m.close()); render(); } });
window.addEventListener("resize", debounce(() => { if (S.route === "dashboard") paintDashboardDynamic(); }, 200));
boot();
