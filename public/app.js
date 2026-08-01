import WebMscore from "/vendor/webmscore/webmscore.mjs";

const statusEl = document.getElementById("status");
const metaEl = document.getElementById("meta");
const pagesEl = document.getElementById("pages");
const scoreListEl = document.getElementById("scoreList");
const filterCountEl = document.getElementById("filterCount");
const fileInput = document.getElementById("fileInput");
const preferEl = document.getElementById("prefer");
const reloadBtn = document.getElementById("reloadScores");
const filtersEl = document.getElementById("filters");
const playerBar = document.getElementById("playerBar");
const playBtn = document.getElementById("playBtn");
const stopBtn = document.getElementById("stopBtn");
const audioEl = document.getElementById("audioEl");
const audioStatus = document.getElementById("audioStatus");

let activePath = null;
let activeFile = null;
let activeFilename = "";
let allScores = [];
let versionFilter = "all";
let audioObjectUrl = null;

let webmscoreReady = WebMscore.ready.catch((err) => {
  console.warn("webmscore failed to init", err);
  return null;
});

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

function clearAudio() {
  audioEl.pause();
  audioEl.removeAttribute("src");
  audioEl.load();
  if (audioObjectUrl) {
    URL.revokeObjectURL(audioObjectUrl);
    audioObjectUrl = null;
  }
  stopBtn.hidden = true;
  playBtn.disabled = false;
  setAudioStatus("");
}

function showResult({ title, pages, method, fallbackFrom }) {
  metaEl.hidden = false;
  metaEl.innerHTML = `
    <strong>${escapeHtml(title || "Untitled")}</strong>
    · ${pages.length} page${pages.length === 1 ? "" : "s"}
    · via <code>${escapeHtml(method)}</code>
    ${
      fallbackFrom?.length
        ? `<div class="fallback">Fell back after: ${escapeHtml(
            fallbackFrom.join(" · ")
          )}</div>`
        : ""
    }
  `;
  pagesEl.innerHTML = "";
  for (const svg of pages) {
    const wrap = document.createElement("div");
    wrap.className = "page";
    wrap.innerHTML = svg;
    pagesEl.appendChild(wrap);
  }
  playerBar.hidden = false;
  clearAudio();
  setStatus("Rendered.");
}

async function bytesFromPath(filePath) {
  const res = await fetch(`/api/scores/file?path=${encodeURIComponent(filePath)}`);
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || `HTTP ${res.status}`);
  }
  return new Uint8Array(await res.arrayBuffer());
}

/** webmscore often "succeeds" on MuseScore 4 files with empty white SVGs. */
function isBlankSvg(svg) {
  if (!svg || svg.length < 800) return true;
  const paths = (svg.match(/<path\b/gi) || []).length;
  const texts = (svg.match(/<text\b/gi) || []).length;
  const uses = (svg.match(/<use\b/gi) || []).length;
  return paths + texts + uses < 8;
}

function assertUsefulPages(pages) {
  if (!pages?.length) throw new Error("no pages");
  if (pages.every(isBlankSvg)) {
    throw new Error("blank SVG pages (likely unsupported MuseScore 4 format)");
  }
}

async function renderWithWebmscore(data, filename) {
  await webmscoreReady;
  if (!WebMscore?.load) throw new Error("webmscore not initialized");
  const format = filename.toLowerCase().endsWith(".mscx") ? "mscx" : "mscz";
  const score = await WebMscore.load(format, data);
  try {
    const title = await score.title();
    const npages = await score.npages();
    const pages = [];
    for (let i = 0; i < npages; i++) {
      pages.push(await score.saveSvg(i, true));
    }
    assertUsefulPages(pages);
    return { title, pages, method: "webmscore" };
  } finally {
    score.destroy();
  }
}

async function renderWithCli({ file, path: filePath }) {
  const fd = new FormData();
  if (file) fd.set("file", file, file.name);
  if (filePath) fd.set("path", filePath);
  const res = await fetch("/api/render", { method: "POST", body: fd });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

async function renderScore({ file = null, path: filePath = null, filename = "" }) {
  activeFile = file;
  activePath = filePath;
  activeFilename = filename || file?.name || filePath || "score.mscz";
  highlightActive();

  setStatus("Rendering… this can take a few seconds.");
  metaEl.hidden = true;
  playerBar.hidden = true;
  pagesEl.innerHTML = "";
  clearAudio();

  const prefer = preferEl.value;
  const errors = [];
  const name = activeFilename;

  if (prefer === "webmscore" || prefer === "auto") {
    try {
      const data = file
        ? new Uint8Array(await file.arrayBuffer())
        : await bytesFromPath(filePath);
      const result = await renderWithWebmscore(data, name);
      showResult(result);
      return;
    } catch (err) {
      errors.push(`webmscore: ${err.message || err}`);
      if (prefer === "webmscore") {
        setStatus(errors.join(" | "), true);
        return;
      }
      setStatus(
        `webmscore produced unusable output, using MuseScore CLI… (${err.message || err})`
      );
    }
  }

  try {
    const result = await renderWithCli({ file, path: filePath });
    if (errors.length) result.fallbackFrom = errors;
    showResult(result);
  } catch (err) {
    errors.push(`cli: ${err.message || err}`);
    setStatus(errors.join(" | "), true);
  }
}

async function playAudio() {
  if (!activePath && !activeFile) {
    setAudioStatus("Load a score first.");
    return;
  }
  playBtn.disabled = true;
  setAudioStatus("Exporting audio via MuseScore…");
  try {
    const fd = new FormData();
    if (activeFile) fd.set("file", activeFile, activeFile.name);
    if (activePath) fd.set("path", activePath);
    const res = await fetch("/api/audio", { method: "POST", body: fd });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.error || `HTTP ${res.status}`);
    }
    const blob = await res.blob();
    if (audioObjectUrl) URL.revokeObjectURL(audioObjectUrl);
    audioObjectUrl = URL.createObjectURL(blob);
    audioEl.src = audioObjectUrl;
    stopBtn.hidden = false;
    setAudioStatus("Playing");
    await audioEl.play();
  } catch (err) {
    setAudioStatus(String(err.message || err));
  } finally {
    playBtn.disabled = false;
  }
}

function stopAudio() {
  audioEl.pause();
  audioEl.currentTime = 0;
  setAudioStatus("Stopped");
}

function highlightActive() {
  for (const btn of scoreListEl.querySelectorAll(".score-item")) {
    btn.classList.toggle("active", btn.dataset.path === activePath);
  }
}

function filteredScores() {
  if (versionFilter === "all") return allScores;
  if (versionFilter === "unknown") {
    return allScores.filter((s) => s.msMajor == null);
  }
  const major = Number(versionFilter);
  return allScores.filter((s) => s.msMajor === major);
}

function renderScoreList() {
  const scores = filteredScores();
  const counts = {
    all: allScores.length,
    2: allScores.filter((s) => s.msMajor === 2).length,
    3: allScores.filter((s) => s.msMajor === 3).length,
    4: allScores.filter((s) => s.msMajor === 4).length,
    unknown: allScores.filter((s) => s.msMajor == null).length,
  };
  filterCountEl.textContent = `Showing ${scores.length} of ${allScores.length}`;
  for (const btn of filtersEl.querySelectorAll(".filter")) {
    const key = btn.dataset.filter;
    const n = counts[key] ?? 0;
    btn.textContent =
      key === "all" ? `All (${n})` : key === "unknown" ? `Unknown (${n})` : `MS${key} (${n})`;
    btn.classList.toggle("active", key === versionFilter);
  }

  if (!scores.length) {
    scoreListEl.textContent = "No scores match this filter.";
    return;
  }

  scoreListEl.innerHTML = "";
  for (const score of scores) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "score-item";
    btn.dataset.path = score.path;
    const badge = score.msLabel || "unknown";
    btn.innerHTML = `
      <span class="name">${escapeHtml(score.name)}</span>
      <span class="meta">
        <span class="badge ms-${escapeHtml(String(score.msMajor || "u"))}">${escapeHtml(badge)}</span>
        ${escapeHtml(score.dir)}
      </span>
    `;
    btn.addEventListener("click", async () => {
      await renderScore({ path: score.path, filename: score.name });
    });
    scoreListEl.appendChild(btn);
  }
  highlightActive();
}

async function loadScores() {
  scoreListEl.textContent = "Loading…";
  try {
    const res = await fetch("/api/scores");
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    allScores = data.scores || [];
    renderScoreList();
  } catch (err) {
    scoreListEl.textContent = String(err.message || err);
  }
}

filtersEl.addEventListener("click", (e) => {
  const btn = e.target.closest(".filter");
  if (!btn) return;
  versionFilter = btn.dataset.filter;
  renderScoreList();
});

fileInput.addEventListener("change", async () => {
  const file = fileInput.files?.[0];
  if (!file) return;
  await renderScore({ file, filename: file.name });
  fileInput.value = "";
});

playBtn.addEventListener("click", () => playAudio());
stopBtn.addEventListener("click", () => stopAudio());
audioEl.addEventListener("ended", () => setAudioStatus("Finished"));
audioEl.addEventListener("pause", () => {
  if (!audioEl.ended && audioEl.currentTime > 0) setAudioStatus("Paused");
});
audioEl.addEventListener("play", () => setAudioStatus("Playing"));

reloadBtn.addEventListener("click", () => loadScores());
loadScores();
