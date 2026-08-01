const statusEl = document.getElementById("status");
const metaEl = document.getElementById("meta");
const pagesEl = document.getElementById("pages");
const scoreListEl = document.getElementById("scoreList");
const playerBar = document.getElementById("playerBar");
const playBtn = document.getElementById("playBtn");
const stopBtn = document.getElementById("stopBtn");
const audioEl = document.getElementById("audioEl");
const audioStatus = document.getElementById("audioStatus");

let activeSlug = null;
/** @type {null | { unit: number, elements: Record<string, any>, events: {elid:number, positionMs:number}[] }} */
let timeline = null;
let pageViews = [];
let rafId = 0;

function setStatus(text, isError = false) {
  statusEl.textContent = text;
  statusEl.classList.toggle("error", isError);
}

function setAudioStatus(text) {
  audioStatus.textContent = text || "";
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

function onScoreClick(ev, pageIndex, svg) {
  if (!timeline?.events?.length) return;
  const pt = svgPointFromClient(svg, ev.clientX, ev.clientY);
  if (!pt) return;
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
    audioEl.play().then(() => {
      setAudioStatus("Playing");
      startPlayheadLoop();
    }).catch(() => setAudioStatus(`Seeked to ${seekSec.toFixed(1)}s`));
  } else {
    setAudioStatus(`Seeked to ${seekSec.toFixed(1)}s`);
  }
}

async function loadScore(slug) {
  activeSlug = slug;
  highlightActive();
  setStatus("Loading score…");
  metaEl.hidden = true;
  playerBar.hidden = true;
  pagesEl.innerHTML = "";
  pageViews = [];
  timeline = null;
  stopPlayheadLoop();
  audioEl.pause();

  try {
    const metaRes = await fetch(`/seed/${slug}/meta.json`);
    if (!metaRes.ok) throw new Error(`meta HTTP ${metaRes.status}`);
    const meta = await metaRes.json();

    const [timelineRes, ...pageRes] = await Promise.all([
      fetch(`/seed/${slug}/${meta.timeline}`),
      ...meta.pages.map((p) => fetch(`/seed/${slug}/${p}`)),
    ]);
    if (!timelineRes.ok) throw new Error("timeline missing");
    timeline = await timelineRes.json();

    const pages = [];
    for (const res of pageRes) {
      if (!res.ok) throw new Error("page missing");
      pages.push(await res.text());
    }

    metaEl.hidden = false;
    metaEl.innerHTML = `
      <strong>${escapeHtml(meta.title)}</strong>
      · ${pages.length} page${pages.length === 1 ? "" : "s"}
      · ${escapeHtml(formatDuration(meta.durationMs))}
      · <span class="cursor-hint">click score to seek</span>
    `;

    pages.forEach((svg, pageIndex) => {
      const wrap = document.createElement("div");
      wrap.className = "page";
      wrap.innerHTML = `
        <div class="page-stage">
          ${svg}
          <div class="playhead" hidden></div>
        </div>
      `;
      const stage = wrap.querySelector(".page-stage");
      const svgEl = stage.querySelector("svg");
      const playhead = stage.querySelector(".playhead");
      stage.addEventListener("click", (ev) => onScoreClick(ev, pageIndex, svgEl));
      pagesEl.appendChild(wrap);
      pageViews.push({ page: pageIndex, wrap, svg: svgEl, playhead, stage });
    });

    audioEl.src = `/seed/${slug}/${meta.audio}`;
    playerBar.hidden = false;
    stopBtn.hidden = true;
    setAudioStatus("Ready");
    setStatus("Loaded. Press Play, or click the score to jump.");
    updatePlayhead(0);
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
      btn.addEventListener("click", () => loadScore(score.slug));
      scoreListEl.appendChild(btn);
    }
  } catch (err) {
    scoreListEl.textContent = String(err.message || err);
  }
}

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

loadCatalog();
