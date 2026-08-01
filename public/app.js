const statusEl = document.getElementById("status");
const pagesEl = document.getElementById("pages");
const scoreListEl = document.getElementById("scoreList");
const playerBar = document.getElementById("playerBar");
const playBtn = document.getElementById("playBtn");
const stopBtn = document.getElementById("stopBtn");
const selectModeBtn = document.getElementById("selectModeBtn");
const clearSelBtn = document.getElementById("clearSelBtn");
const selectionLabelEl = document.getElementById("selectionLabel");
const audioEl = document.getElementById("audioEl");
const audioStatus = document.getElementById("audioStatus");
const themeToggle = document.getElementById("themeToggle");
const commandForm = document.getElementById("commandForm");
const commandInput = document.getElementById("commandInput");
const commandSend = document.getElementById("commandSend");
const commandReply = document.getElementById("commandReply");
const commandSelection = document.getElementById("commandSelection");
const commandTranscript = document.getElementById("commandTranscript");
const editToolbar = document.getElementById("editToolbar");
const durationSelect = document.getElementById("durationSelect");
const renderStatus = document.getElementById("renderStatus");
const agentExpandBtn = document.getElementById("agentExpandBtn");
const agentBackBtn = document.getElementById("agentBackBtn");
const emptyState = document.getElementById("emptyState");
const scoreWorkspace = document.getElementById("scoreWorkspace");
const libraryOpenBtn = document.getElementById("libraryOpenBtn");
const libraryCloseBtn = document.getElementById("libraryCloseBtn");
const libraryBackdrop = document.getElementById("libraryBackdrop");
const emptyLibraryBtn = document.getElementById("emptyLibraryBtn");

let activeSlug = null;
let activeTitle = null;
/** @type {null | { unit: number, elements: Record<string, any>, events: {elid:number, positionMs:number}[] }} */
let timeline = null;
/** @type {Array<{measure:number, page:number, x:number, y:number, w:number, h:number, elids:number[], startMs:number, endMs:number}>} */
let measures = [];
let pageViews = [];
let rafId = 0;
let selectMode = false;
/** @type {null | { measureStart: number, measureEnd: number, voices: string[], staves: string[], elids: number[], pageIndices: number[], label: string }} */
let selection = null;
/** @type {{role:string, content:string}[]} */
let chatHistory = [];
let anchorMeasure = null;
let seedMeta = null;
let scoreRevision = 0;

function setStatus(text, isError = false) {
  const t = (text || "").trim();
  statusEl.textContent = t;
  statusEl.classList.toggle("error", isError);
  statusEl.hidden = !t || (!isError && /^(Loaded|Loading)/i.test(t));
}

function setAudioStatus(text) {
  audioStatus.textContent = text || "";
}

function setRenderStatus(text) {
  renderStatus.textContent = text || "";
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function formatDuration(ms) {
  if (!ms && ms !== 0) return "";
  const s = Math.round(ms / 1000);
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${String(r).padStart(2, "0")}`;
}

/* ---------- Theme ---------- */

function currentTheme() {
  return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
}

function applyTheme(theme) {
  const next = theme === "dark" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", next);
  try {
    localStorage.setItem("copland-theme", next);
  } catch {
    /* ignore */
  }
  const toDark = next === "light";
  themeToggle.textContent = toDark ? "Dark" : "Light";
  themeToggle.setAttribute(
    "aria-label",
    toDark ? "Switch to dark theme" : "Switch to light theme",
  );
}

function initTheme() {
  applyTheme(currentTheme());
  themeToggle.addEventListener("click", () => {
    applyTheme(currentTheme() === "dark" ? "light" : "dark");
  });
}


/* ---------- Library drawer (mobile) ---------- */

function isMobileShell() {
  return window.matchMedia("(max-width: 960px)").matches;
}

function setLibraryOpen(open) {
  const on = Boolean(open) && isMobileShell();
  document.body.classList.toggle("library-open", on);
  libraryBackdrop.hidden = !on;
  libraryCloseBtn.hidden = !isMobileShell();
  libraryOpenBtn.hidden = !isMobileShell();
}

function initLibraryShell() {
  const mq = window.matchMedia("(max-width: 960px)");
  const sync = () => {
    libraryOpenBtn.hidden = !mq.matches;
    libraryCloseBtn.hidden = !mq.matches;
    if (!mq.matches) {
      document.body.classList.remove("library-open");
      libraryBackdrop.hidden = true;
    }
  };
  sync();
  mq.addEventListener("change", sync);
  libraryOpenBtn.addEventListener("click", () => setLibraryOpen(true));
  libraryCloseBtn.addEventListener("click", () => setLibraryOpen(false));
  libraryBackdrop.addEventListener("click", () => setLibraryOpen(false));
  emptyLibraryBtn.addEventListener("click", () => {
    if (isMobileShell()) setLibraryOpen(true);
    else scoreListEl.querySelector("button")?.focus();
  });
}

function showScoreWorkspace(show) {
  emptyState.hidden = show;
  scoreWorkspace.hidden = !show;
  document.body.classList.toggle("has-score", show);
}

/* ---------- Agent rail (desktop) / bottom dock + fullscreen (mobile) ---------- */

function setAgentExpanded(expanded) {
  const on = Boolean(expanded) && isMobileShell();
  document.body.classList.toggle("agent-expanded", on);
  agentExpandBtn.hidden = !isMobileShell() || on;
  agentBackBtn.hidden = !on;
  agentExpandBtn.setAttribute("aria-expanded", on ? "true" : "false");
  if (on) {
    commandInput.focus();
  }
}

function initAgentRail() {
  const mq = window.matchMedia("(max-width: 960px)");
  const sync = () => {
    if (!mq.matches) {
      document.body.classList.remove("agent-expanded");
      agentExpandBtn.hidden = true;
      agentBackBtn.hidden = true;
      return;
    }
    const expanded = document.body.classList.contains("agent-expanded");
    agentExpandBtn.hidden = expanded;
    agentBackBtn.hidden = !expanded;
  };
  sync();
  mq.addEventListener("change", sync);
  agentExpandBtn.addEventListener("click", () => setAgentExpanded(true));
  agentBackBtn.addEventListener("click", () => setAgentExpanded(false));
}

/* ---------- Playhead ---------- */

function hidePlayheads() {
  for (const pv of pageViews) pv.playhead.hidden = true;
}

function stopPlayheadLoop() {
  cancelAnimationFrame(rafId);
}

function startPlayheadLoop() {
  stopPlayheadLoop();
  const tick = () => {
    updatePlayhead(audioEl.currentTime * 1000);
    if (!audioEl.paused && !audioEl.ended) rafId = requestAnimationFrame(tick);
  };
  rafId = requestAnimationFrame(tick);
}

function svgPointFromClient(svg, clientX, clientY) {
  const pt = svg.createSVGPoint();
  pt.x = clientX;
  pt.y = clientY;
  const ctm = svg.getScreenCTM();
  if (!ctm) return null;
  return pt.matrixTransform(ctm.inverse());
}

function cursorAtMs(ms) {
  if (!timeline?.events?.length) return null;
  const { events, elements, unit } = timeline;
  let i = 0;
  while (i + 1 < events.length && events[i + 1].positionMs <= ms) i++;
  const cur = events[i];
  const next = events[i + 1] || null;
  const el = elements[String(cur.elid)] || elements[cur.elid];
  if (!el) return null;

  let x = el.x;
  if (next) {
    const nel = elements[String(next.elid)] || elements[next.elid];
    if (nel && nel.page === el.page && Math.abs(nel.y - el.y) < el.sy * 0.5) {
      const span = Math.max(1, next.positionMs - cur.positionMs);
      const t = Math.min(1, Math.max(0, (ms - cur.positionMs) / span));
      x = el.x + (nel.x - el.x) * t;
    } else {
      const span = Math.max(1, (next?.positionMs || cur.positionMs + 500) - cur.positionMs);
      const t = Math.min(1, Math.max(0, (ms - cur.positionMs) / span));
      x = el.x + el.sx * t * 0.85;
    }
  }

  return {
    page: el.page,
    x: x / unit,
    y: el.y / unit,
    h: el.sy / unit,
  };
}

function updatePlayhead(ms) {
  const cur = cursorAtMs(ms);
  if (!cur) {
    hidePlayheads();
    return;
  }
  for (const pv of pageViews) {
    if (pv.page !== cur.page) {
      pv.playhead.hidden = true;
      continue;
    }
    const vb = pv.svg.viewBox.baseVal;
    const svgW = vb.width || pv.svg.width.baseVal.value;
    const svgH = vb.height || pv.svg.height.baseVal.value;
    const rect = pv.svg.getBoundingClientRect();
    const stageRect = pv.stage.getBoundingClientRect();
    const scaleX = rect.width / svgW;
    const scaleY = rect.height / svgH;
    const left = rect.left - stageRect.left + cur.x * scaleX;
    const top = rect.top - stageRect.top + cur.y * scaleY;
    const height = cur.h * scaleY;
    pv.playhead.hidden = false;
    pv.playhead.style.transform = `translate(${left}px, ${top}px)`;
    pv.playhead.style.height = `${Math.max(24, height)}px`;
  }
}

/* ---------- Measure model / selection ---------- */

function buildMeasures(tl) {
  const unit = tl.unit || 12;
  const byKey = new Map();
  for (const ev of tl.events) {
    const el = tl.elements[String(ev.elid)] || tl.elements[ev.elid];
    if (!el) continue;
    const key = `${el.page}:${Math.round(el.y / 40)}`;
    if (!byKey.has(key)) byKey.set(key, []);
    byKey.get(key).push({ el, ev });
  }

  /** @type {typeof measures} */
  const out = [];
  for (const items of byKey.values()) {
    items.sort((a, b) => a.el.x - b.el.x || a.ev.positionMs - b.ev.positionMs);
    const gaps = [];
    for (let i = 1; i < items.length; i++) {
      gaps.push(items[i].el.x - (items[i - 1].el.x + items[i - 1].el.sx));
    }
    const positive = gaps.filter((g) => g > 0).sort((a, b) => a - b);
    const median = positive.length ? positive[Math.floor(positive.length / 2)] : 0;
    const threshold = Math.max(median * 2.2, (items[0]?.el.sx || 400) * 0.85);

    let cluster = [items[0]];
    const flush = () => {
      if (!cluster.length) return;
      const xs = cluster.map((c) => c.el.x);
      const rights = cluster.map((c) => c.el.x + c.el.sx);
      const ys = cluster.map((c) => c.el.y);
      const bottoms = cluster.map((c) => c.el.y + c.el.sy);
      const times = cluster.map((c) => c.ev.positionMs);
      out.push({
        measure: 0,
        page: cluster[0].el.page,
        x: Math.min(...xs) / unit,
        y: Math.min(...ys) / unit,
        w: (Math.max(...rights) - Math.min(...xs)) / unit,
        h: (Math.max(...bottoms) - Math.min(...ys)) / unit,
        elids: cluster.map((c) => c.ev.elid),
        startMs: Math.min(...times),
        endMs: Math.max(...times),
      });
      cluster = [];
    };

    for (let i = 1; i < items.length; i++) {
      const gap = items[i].el.x - (items[i - 1].el.x + items[i - 1].el.sx);
      if (gap > threshold) flush();
      cluster.push(items[i]);
    }
    flush();
  }

  out.sort((a, b) => a.startMs - b.startMs || a.page - b.page || a.x - b.x);
  out.forEach((m, i) => {
    m.measure = i + 1;
  });
  return out;
}

function selectionContext() {
  if (!selection) return null;
  return {
    measure_start: selection.measureStart,
    measure_end: selection.measureEnd,
    voices: selection.voices,
    staves: selection.staves,
    elids: selection.elids,
    page_indices: selection.pageIndices,
    label: selection.label,
  };
}

function updateSelectionUi() {
  if (!selection) {
    selectionLabelEl.hidden = true;
    clearSelBtn.hidden = true;
    commandSelection.textContent = "No selection";
  } else {
    selectionLabelEl.hidden = false;
    clearSelBtn.hidden = false;
    selectionLabelEl.textContent = selection.label;
    commandSelection.textContent = selection.label;
  }
  paintSelectionOverlays();
}

function setSelectionRange(start, end) {
  const a = Math.min(start, end);
  const b = Math.max(start, end);
  const picked = measures.filter((m) => m.measure >= a && m.measure <= b);
  if (!picked.length) {
    selection = null;
    updateSelectionUi();
    return;
  }
  selection = {
    measureStart: a,
    measureEnd: b,
    voices: [],
    staves: [],
    elids: picked.flatMap((m) => m.elids),
    pageIndices: [...new Set(picked.map((m) => m.page))],
    label: a === b ? `Measure ${a}` : `Measures ${a}–${b}`,
  };
  updateSelectionUi();
}

function clearSelection() {
  selection = null;
  anchorMeasure = null;
  updateSelectionUi();
}

function paintSelectionOverlays() {
  for (const pv of pageViews) {
    pv.overlay.innerHTML = "";
    if (!selection) continue;
    const vb = pv.svg.viewBox.baseVal;
    const svgW = vb.width || pv.svg.width.baseVal.value;
    const svgH = vb.height || pv.svg.height.baseVal.value;
    const rect = pv.svg.getBoundingClientRect();
    const stageRect = pv.stage.getBoundingClientRect();
    const scaleX = rect.width / svgW;
    const scaleY = rect.height / svgH;
    const ox = rect.left - stageRect.left;
    const oy = rect.top - stageRect.top;

    for (const m of measures) {
      if (m.page !== pv.page) continue;
      if (m.measure < selection.measureStart || m.measure > selection.measureEnd) continue;
      const hilite = document.createElement("div");
      hilite.className = "measure-hilite";
      hilite.style.left = `${ox + m.x * scaleX}px`;
      hilite.style.top = `${oy + m.y * scaleY}px`;
      hilite.style.width = `${Math.max(6, m.w * scaleX)}px`;
      hilite.style.height = `${Math.max(12, m.h * scaleY)}px`;
      pv.overlay.appendChild(hilite);
    }
  }
}

function measureAtPoint(pageIndex, svgX, svgY) {
  let best = null;
  let bestDist = Infinity;
  for (const m of measures) {
    if (m.page !== pageIndex) continue;
    const inside =
      svgX >= m.x && svgX <= m.x + m.w && svgY >= m.y && svgY <= m.y + m.h;
    if (inside) return m;
    const cx = m.x + m.w / 2;
    const cy = m.y + m.h / 2;
    const d = (svgX - cx) ** 2 + (svgY - cy) ** 2;
    if (d < bestDist) {
      bestDist = d;
      best = m;
    }
  }
  return best;
}

function onScoreClick(ev, pageIndex, svg) {
  if (!timeline?.events?.length) return;
  const pt = svgPointFromClient(svg, ev.clientX, ev.clientY);
  if (!pt) return;

  if (selectMode || ev.shiftKey) {
    const m = measureAtPoint(pageIndex, pt.x, pt.y);
    if (!m) return;
    if (ev.shiftKey && anchorMeasure != null) {
      setSelectionRange(anchorMeasure, m.measure);
    } else {
      anchorMeasure = m.measure;
      setSelectionRange(m.measure, m.measure);
    }
    return;
  }

  const unit = timeline.unit || 12;
  const mx = pt.x * unit;
  const my = pt.y * unit;

  let best = null;
  let bestDist = Infinity;
  for (const evnt of timeline.events) {
    const el = timeline.elements[String(evnt.elid)] || timeline.elements[evnt.elid];
    if (!el || el.page !== pageIndex) continue;
    const inY = my >= el.y - el.sy * 0.15 && my <= el.y + el.sy * 1.05;
    if (!inY) continue;
    const dx = mx < el.x ? el.x - mx : mx > el.x + el.sx ? mx - (el.x + el.sx) : 0;
    const inside = mx >= el.x && mx <= el.x + el.sx;
    const score = inside ? dx - 1e9 : dx;
    if (score < bestDist) {
      bestDist = score;
      let ms = evnt.positionMs;
      if (inside && el.sx > 0) {
        const t = Math.min(1, Math.max(0, (mx - el.x) / el.sx));
        const idx = timeline.events.indexOf(evnt);
        const next = timeline.events[idx + 1];
        if (next) ms = evnt.positionMs + (next.positionMs - evnt.positionMs) * t;
      }
      best = ms;
    }
  }
  if (best == null) return;

  const seekSec = best / 1000;
  audioEl.currentTime = seekSec;
  updatePlayhead(best);
  if (audioEl.paused) {
    audioEl
      .play()
      .then(() => {
        setAudioStatus("Playing");
        startPlayheadLoop();
      })
      .catch(() => setAudioStatus(`Seeked to ${seekSec.toFixed(1)}s`));
  } else {
    setAudioStatus(`Seeked to ${seekSec.toFixed(1)}s`);
  }
}

function setSelectMode(on) {
  selectMode = on;
  selectModeBtn.setAttribute("aria-pressed", on ? "true" : "false");
  selectModeBtn.textContent = on ? "Selecting…" : "Select";
  for (const pv of pageViews) {
    pv.stage.classList.toggle("select-mode", on);
  }
}

/* ---------- Score load / refresh ---------- */

function bindScorePointer(stage, pageIndex, svgEl) {
  let longPressTimer = 0;
  let longPressFired = false;
  const clearLong = () => {
    if (longPressTimer) {
      clearTimeout(longPressTimer);
      longPressTimer = 0;
    }
  };

  stage.addEventListener(
    "pointerdown",
    (ev) => {
      if (ev.pointerType === "mouse" && ev.button !== 0) return;
      longPressFired = false;
      clearLong();
      longPressTimer = window.setTimeout(() => {
        longPressFired = true;
        if (!selectMode) setSelectMode(true);
        const pt = svgPointFromClient(svgEl, ev.clientX, ev.clientY);
        if (!pt) return;
        const m = measureAtPoint(pageIndex, pt.x, pt.y);
        if (!m) return;
        if (anchorMeasure != null && selection) {
          setSelectionRange(anchorMeasure, m.measure);
        } else {
          anchorMeasure = m.measure;
          setSelectionRange(m.measure, m.measure);
        }
        setAudioStatus("Select mode · tap another measure to extend");
      }, 420);
    },
    { passive: true },
  );

  stage.addEventListener(
    "pointerup",
    (ev) => {
      clearLong();
      if (longPressFired) {
        ev.preventDefault();
        return;
      }
    },
    { passive: false },
  );
  stage.addEventListener("pointercancel", clearLong);
  stage.addEventListener("pointerleave", clearLong);
  stage.addEventListener("click", (ev) => {
    if (longPressFired) {
      longPressFired = false;
      ev.preventDefault();
      ev.stopPropagation();
      return;
    }
    onScoreClick(ev, pageIndex, svgEl);
  });
}

function mountPages(svgTexts) {
  pagesEl.innerHTML = "";
  pageViews = [];
  svgTexts.forEach((svg, pageIndex) => {
    const wrap = document.createElement("div");
    wrap.className = "page";
    wrap.innerHTML = `
      <div class="page-stage">
        ${svg}
        <div class="measure-overlay"></div>
        <div class="playhead" hidden></div>
      </div>
    `;
    const stage = wrap.querySelector(".page-stage");
    const svgEl = stage.querySelector("svg");
    const playhead = stage.querySelector(".playhead");
    const overlay = stage.querySelector(".measure-overlay");
    bindScorePointer(stage, pageIndex, svgEl);
    pagesEl.appendChild(wrap);
    pageViews.push({ page: pageIndex, wrap, svg: svgEl, playhead, stage, overlay });
  });
  setSelectMode(selectMode);
  paintSelectionOverlays();
}

async function loadSeedVisuals(slug, meta) {
  const [timelineRes, ...pageRes] = await Promise.all([
    fetch(`/seed/${slug}/${meta.timeline}`),
    ...meta.pages.map((p) => fetch(`/seed/${slug}/${p}`)),
  ]);
  if (!timelineRes.ok) throw new Error("timeline missing");
  timeline = await timelineRes.json();
  measures = buildMeasures(timeline);
  const pages = [];
  for (const res of pageRes) {
    if (!res.ok) throw new Error("page missing");
    pages.push(await res.text());
  }
  mountPages(pages);
  audioEl.src = `/seed/${slug}/${meta.audio}`;
  return pages.length;
}

async function applyScoreAssets(assets) {
  if (!assets || !activeSlug) return;
  scoreRevision = assets.revision || scoreRevision;
  const render = assets.render || {};
  if (render.ok && Array.isArray(render.pages) && render.pages.length) {
    const pageTexts = [];
    for (const url of render.pages) {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`render page HTTP ${res.status}`);
      pageTexts.push(await res.text());
    }
    if (render.timeline_url) {
      const tr = await fetch(render.timeline_url);
      if (tr.ok) {
        timeline = await tr.json();
        measures = buildMeasures(timeline);
      }
    }
    if (render.audio_url) {
      const t = audioEl.currentTime;
      const wasPlaying = !audioEl.paused;
      audioEl.src = render.audio_url;
      audioEl.currentTime = t;
      if (wasPlaying) {
        try {
          await audioEl.play();
        } catch {
          /* ignore */
        }
      }
    }
    mountPages(pageTexts);
    setRenderStatus(`Rendered v${scoreRevision} via MuseScore · ${assets.summary?.note_count ?? "?"} notes`);
    setStatus("Score updated.");
  } else {
    setRenderStatus(
      render.detail ||
        "Edits applied in memory. SVG re-render needs MuseScore CLI locally (seed pages unchanged).",
    );
    if (assets.summary) {
      setStatus(
        `Applied (model: ${assets.summary.measure_count} measures, ${assets.summary.note_count} notes).`,
      );
    }
  }

  if (assets.selection?.measure_start != null) {
    setSelectionRange(assets.selection.measure_start, assets.selection.measure_end);
  }
}

async function openSession(slug, title) {
  try {
    const res = await fetch("/api/session/open", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ score_slug: slug, score_title: title }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || `session HTTP ${res.status}`);
    setRenderStatus(
      data.render?.mscore_available
        ? "Edit session ready · MuseScore CLI available for re-render"
        : "Edit session ready · MuseScore CLI unavailable (mutations apply; seed SVG until CLI present)",
    );
    return data;
  } catch (err) {
    setRenderStatus(String(err.message || err));
    return null;
  }
}

async function loadScore(slug) {
  activeSlug = slug;
  highlightActive();
  setLibraryOpen(false);
  showScoreWorkspace(true);
  setStatus("Loading…");
  pagesEl.innerHTML = "";
  pageViews = [];
  timeline = null;
  measures = [];
  clearSelection();
  chatHistory = [];
  renderTranscript();
  stopPlayheadLoop();
  audioEl.pause();

  try {
    const metaRes = await fetch(`/seed/${slug}/meta.json`);
    if (!metaRes.ok) throw new Error(`meta HTTP ${metaRes.status}`);
    const meta = await metaRes.json();
    seedMeta = meta;
    activeTitle = meta.title || slug;

    await loadSeedVisuals(slug, meta);

    stopBtn.hidden = true;
    setSelectMode(selectMode);
    setAudioStatus(
      `${meta.title} · tap to seek · Select or long-press measures`,
    );
    setStatus("");
    updatePlayhead(0);
    window.addEventListener("resize", paintSelectionOverlays);
    await openSession(slug, activeTitle);
  } catch (err) {
    setStatus(String(err.message || err), true);
  }
}

function highlightActive() {
  for (const btn of scoreListEl.querySelectorAll(".score-item")) {
    btn.classList.toggle("active", btn.dataset.slug === activeSlug);
  }
}

async function loadCatalog() {
  scoreListEl.textContent = "Loading…";
  try {
    const res = await fetch("/api/catalog");
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    const scores = data.scores || [];
    if (!scores.length) {
      scoreListEl.textContent = "No seeded scores found.";
      return;
    }
    scoreListEl.innerHTML = "";
    for (const score of scores) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "score-item";
      btn.dataset.slug = score.slug;
      btn.innerHTML = `
        <span class="name">${escapeHtml(score.title)}</span>
        <span class="meta">${score.pageCount} pages · ${escapeHtml(formatDuration(score.durationMs))}</span>
      `;
      btn.addEventListener("click", () => {
        setLibraryOpen(false);
        loadScore(score.slug);
      });
      scoreListEl.appendChild(btn);
    }
  } catch (err) {
    scoreListEl.textContent = String(err.message || err);
  }
}

/* ---------- Command rail / agent ---------- */

function showReply(text, isError = false) {
  commandReply.hidden = false;
  commandReply.textContent = text;
  commandReply.classList.toggle("error", isError);
}

function renderTranscript() {
  if (!chatHistory.length) {
    commandTranscript.innerHTML =
      '<div class="transcript-empty">Ask Copland to edit the score. Selection is sent with each command.</div>';
    return;
  }
  commandTranscript.innerHTML = chatHistory
    .map(
      (t) => `
      <div class="turn">
        <div class="role">${escapeHtml(t.role)}</div>
        <div>${escapeHtml(t.content)}</div>
      </div>`,
    )
    .join("");
  commandTranscript.scrollTop = commandTranscript.scrollHeight;
}

async function submitCommand(message) {
  const text = message.trim();
  if (!text) return;
  commandSend.disabled = true;
  showReply("Thinking…");

  const body = {
    message: text,
    score_slug: activeSlug,
    score_title: activeTitle,
    selection: selectionContext(),
    history: chatHistory.map((t) => ({ role: t.role, content: t.content })),
  };

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    const reply = data.reply || data.error || "No reply";
    const isErr = Boolean(data.error) && data.error !== "missing_api_key";
    showReply(reply, isErr && res.status >= 500);

    chatHistory.push({ role: "user", content: text });
    chatHistory.push({ role: "assistant", content: reply });
    if (chatHistory.length > 40) chatHistory = chatHistory.slice(-40);
    renderTranscript();

    if (Array.isArray(data.planned_ops) && data.planned_ops.length) {
      const ops = data.planned_ops
        .map((op) => `${op.tool}: ${op.detail || op.status}`)
        .join(" · ");
      showReply(`${reply}\n\n${ops}`, false);
    }

    if (data.score_assets) {
      await applyScoreAssets(data.score_assets);
    }

    for (const op of data.planned_ops || []) {
      if (op.tool === "play_selection" && op.status === "applied") {
        playSelectionRange();
      }
      if (op.tool === "set_selection" && op.status === "applied") {
        setSelectionRange(op.args.measure_start, op.args.measure_end);
      }
      if (op.tool === "clear_selection" && op.status === "applied") {
        clearSelection();
      }
    }
  } catch (err) {
    showReply(String(err.message || err), true);
  } finally {
    commandSend.disabled = false;
  }
}

commandForm.addEventListener("submit", (ev) => {
  ev.preventDefault();
  const value = commandInput.value;
  commandInput.value = "";
  submitCommand(value);
});

commandInput.addEventListener("keydown", (ev) => {
  if (ev.key === "Enter" && !ev.shiftKey) {
    ev.preventDefault();
    commandForm.requestSubmit();
  }
});

/* ---------- Click edit tools ---------- */

function requireSelection() {
  if (!selection) {
    showReply("Select measures first (Select mode or Shift+click).", true);
    return null;
  }
  return selectionContext();
}

async function applyTool(tool, args = {}) {
  if (!activeSlug) {
    showReply("Load a score first.", true);
    return;
  }
  const body = {
    tool,
    args,
    score_slug: activeSlug,
    score_title: activeTitle,
    selection: selectionContext(),
  };
  showReply(`Applying ${tool}…`);
  try {
    const res = await fetch("/api/session/apply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || `HTTP ${res.status}`);
    const op = data.op || {};
    showReply(op.detail || op.status || "Done", op.status === "error");
    if (data.score_assets) await applyScoreAssets(data.score_assets);
    if (tool === "play_selection" && op.status === "applied") playSelectionRange();
    if (tool === "clear_selection") clearSelection();
  } catch (err) {
    showReply(String(err.message || err), true);
  }
}

function playSelectionRange() {
  if (!selection || !measures.length) return;
  const picked = measures.filter(
    (m) => m.measure >= selection.measureStart && m.measure <= selection.measureEnd,
  );
  if (!picked.length) return;
  const startMs = Math.min(...picked.map((m) => m.startMs));
  audioEl.currentTime = startMs / 1000;
  audioEl
    .play()
    .then(() => {
      setAudioStatus("Playing selection");
      startPlayheadLoop();
    })
    .catch((err) => setAudioStatus(String(err.message || err)));
}

editToolbar.addEventListener("click", async (ev) => {
  const btn = ev.target.closest("[data-edit]");
  if (!btn) return;
  const action = btn.getAttribute("data-edit");
  switch (action) {
    case "transpose-up":
      if (!requireSelection()) return;
      await applyTool("transpose_selection", { semitones: 1 });
      break;
    case "transpose-down":
      if (!requireSelection()) return;
      await applyTool("transpose_selection", { semitones: -1 });
      break;
    case "delete-selection":
      if (!requireSelection()) return;
      await applyTool("delete_selection", {});
      break;
    case "duplicate":
      if (!requireSelection()) return;
      await applyTool("duplicate_measures", {
        measure_start: selection.measureStart,
        measure_end: selection.measureEnd,
        insert_after: selection.measureEnd,
      });
      break;
    case "set-duration":
      if (!requireSelection()) return;
      await applyTool("set_note_duration", { duration: durationSelect.value });
      break;
    case "insert-measure":
      await applyTool("insert_measures", {
        count: 1,
        after_measure: selection?.measureEnd || 0,
      });
      break;
    case "delete-measures":
      if (!requireSelection()) return;
      await applyTool("delete_measures", {
        measure_start: selection.measureStart,
        measure_end: selection.measureEnd,
      });
      break;
    case "copy":
      if (!requireSelection()) return;
      await applyTool("copy_selection", {});
      break;
    case "cut":
      if (!requireSelection()) return;
      await applyTool("cut_selection", {});
      break;
    case "paste":
      await applyTool("paste_selection", {
        target: selection?.measureEnd || 0,
      });
      break;
    case "undo":
      await applyTool("undo", {});
      break;
    case "redo":
      await applyTool("redo", {});
      break;
    case "play-selection":
      if (!requireSelection()) return;
      await applyTool("play_selection", {});
      break;
    case "reset-session": {
      if (!activeSlug) return;
      const res = await fetch("/api/session/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ score_slug: activeSlug, score_title: activeTitle }),
      });
      const data = await res.json();
      if (seedMeta) await loadSeedVisuals(activeSlug, seedMeta);
      showReply("Score session reset to seed.");
      setRenderStatus(data.render?.detail || "Reset");
      break;
    }
    default:
      break;
  }
});

/* ---------- Transport ---------- */

playBtn.addEventListener("click", async () => {
  try {
    await audioEl.play();
    stopBtn.hidden = false;
    setAudioStatus("Playing");
    startPlayheadLoop();
  } catch (err) {
    setAudioStatus(String(err.message || err));
  }
});

stopBtn.addEventListener("click", () => {
  stopPlayheadLoop();
  audioEl.pause();
  audioEl.currentTime = 0;
  hidePlayheads();
  setAudioStatus("Stopped");
});

selectModeBtn.addEventListener("click", () => setSelectMode(!selectMode));
clearSelBtn.addEventListener("click", () => clearSelection());

document.addEventListener("keydown", (ev) => {
  const typing =
    ev.target instanceof HTMLElement &&
    (ev.target.tagName === "INPUT" ||
      ev.target.tagName === "TEXTAREA" ||
      ev.target.isContentEditable);
  if (ev.key === "Escape") {
    if (document.body.classList.contains("agent-expanded")) {
      setAgentExpanded(false);
      return;
    }
    if (document.body.classList.contains("library-open")) {
      setLibraryOpen(false);
      return;
    }
    if (selectMode) setSelectMode(false);
    clearSelection();
    return;
  }
  if (typing) return;
  if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === "z") {
    ev.preventDefault();
    applyTool(ev.shiftKey ? "redo" : "undo", {});
  }
  if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === "c" && selection) {
    ev.preventDefault();
    applyTool("copy_selection", {});
  }
  if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === "x" && selection) {
    ev.preventDefault();
    applyTool("cut_selection", {});
  }
  if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === "v") {
    ev.preventDefault();
    applyTool("paste_selection", { target: selection?.measureEnd || 0 });
  }
  if ((ev.key === "Delete" || ev.key === "Backspace") && selection) {
    ev.preventDefault();
    applyTool("delete_selection", {});
  }
});

audioEl.addEventListener("ended", () => {
  stopPlayheadLoop();
  setAudioStatus("Finished");
});
audioEl.addEventListener("pause", () => {
  stopPlayheadLoop();
  if (!audioEl.ended && audioEl.currentTime > 0) setAudioStatus("Paused");
});
audioEl.addEventListener("play", () => {
  setAudioStatus("Playing");
  startPlayheadLoop();
});
audioEl.addEventListener("seeked", () => updatePlayhead(audioEl.currentTime * 1000));

initTheme();
initLibraryShell();
initAgentRail();
showScoreWorkspace(false);
renderTranscript();
loadCatalog();
