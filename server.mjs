import express from "express";
import multer from "multer";
import fs from "node:fs/promises";
import { createReadStream, existsSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn, execFile } from "node:child_process";
import { promisify } from "node:util";
import { createHash, randomUUID } from "node:crypto";

const execFileAsync = promisify(execFile);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT || 5177);
const CACHE_DIR = path.join(os.tmpdir(), "msviewer-cache");

const SCORE_DIRS = [
  path.join(os.homedir(), "Documents/MuseScore4/Scores"),
  path.join(os.homedir(), "Documents/incommon"),
].filter((d) => existsSync(d));

const MSCORE_CANDIDATES = [
  "/Applications/MuseScore 4.app/Contents/MacOS/mscore",
  "/Applications/MuseScore 3.app/Contents/MacOS/mscore",
];

const mscoreBin = MSCORE_CANDIDATES.find((p) => existsSync(p));
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 80 * 1024 * 1024 },
});

/** @type {Map<string, { mtimeMs: number, info: object }>} */
const versionCache = new Map();

const app = express();
app.use(express.static(path.join(__dirname, "public")));
app.use(
  "/vendor/webmscore",
  express.static(path.join(__dirname, "node_modules/webmscore"))
);

function isScoreName(name) {
  return /\.(mscz|mscx)$/i.test(name);
}

function parseMuseScoreVersion(xmlHead) {
  const ver =
    xmlHead.match(/<museScore[^>]*\bversion="([^"]+)"/i)?.[1] || null;
  const programVersion =
    xmlHead.match(/<programVersion>([^<]+)<\/programVersion>/i)?.[1] || null;
  let major = null;
  if (ver?.startsWith("4")) major = 4;
  else if (ver?.startsWith("3")) major = 3;
  else if (ver?.startsWith("2")) major = 2;
  else if (programVersion?.startsWith("4")) major = 4;
  else if (programVersion?.startsWith("3")) major = 3;
  return {
    major,
    version: ver,
    programVersion,
    label: major ? `MS${major}` : "unknown",
  };
}

async function detectScoreVersion(filePath, mtimeMs) {
  const cached = versionCache.get(filePath);
  if (cached && cached.mtimeMs === mtimeMs) return cached.info;

  let info = { major: null, version: null, programVersion: null, label: "unknown" };
  try {
    if (filePath.toLowerCase().endsWith(".mscx")) {
      const fh = await fs.open(filePath, "r");
      try {
        const buf = Buffer.alloc(4096);
        const { bytesRead } = await fh.read(buf, 0, 4096, 0);
        info = parseMuseScoreVersion(buf.slice(0, bytesRead).toString("utf8"));
      } finally {
        await fh.close();
      }
    } else {
      const { stdout: listing } = await execFileAsync("unzip", ["-Z1", filePath], {
        maxBuffer: 2 * 1024 * 1024,
      });
      const mscx = listing
        .split("\n")
        .map((s) => s.trim())
        .find(
          (n) =>
            n.toLowerCase().endsWith(".mscx") &&
            !n.toLowerCase().includes("thumbnail")
        );
      if (mscx) {
        const { stdout: xml } = await execFileAsync(
          "unzip",
          ["-p", filePath, mscx],
          { maxBuffer: 8 * 1024 * 1024 }
        );
        info = parseMuseScoreVersion(String(xml).slice(0, 8192));
      }
    }
  } catch {
    // leave unknown
  }

  versionCache.set(filePath, { mtimeMs, info });
  return info;
}

async function listScores() {
  const out = [];
  for (const dir of SCORE_DIRS) {
    let entries = [];
    try {
      entries = await fs.readdir(dir, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const ent of entries) {
      if (!ent.isFile() || !isScoreName(ent.name)) continue;
      if (ent.name.includes(".bak")) continue;
      const full = path.join(dir, ent.name);
      const st = await fs.stat(full);
      const ms = await detectScoreVersion(full, st.mtimeMs);
      out.push({
        name: ent.name,
        dir,
        path: full,
        size: st.size,
        mtime: st.mtimeMs,
        msMajor: ms.major,
        msVersion: ms.version,
        programVersion: ms.programVersion,
        msLabel: ms.label,
      });
    }
  }
  out.sort((a, b) => b.mtime - a.mtime);
  return out;
}

function resolveListedScore(filePath) {
  const resolved = path.resolve(filePath);
  const allowed = SCORE_DIRS.some(
    (d) => resolved === d || resolved.startsWith(d + path.sep)
  );
  if (!allowed || !isScoreName(resolved) || !existsSync(resolved)) {
    return null;
  }
  return resolved;
}

function run(cmd, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(cmd, args, {
      stdio: ["ignore", "pipe", "pipe"],
      env: { ...process.env },
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (d) => (stdout += d));
    child.stderr.on("data", (d) => (stderr += d));
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) resolve({ stdout, stderr });
      else reject(new Error(`exit ${code}: ${stderr || stdout}`));
    });
  });
}

async function resolveInputPath(req) {
  if (req.file) {
    const name = req.file.originalname || "score.mscz";
    const tmpUpload = path.join(
      os.tmpdir(),
      `msviewer-upload-${randomUUID()}${path.extname(name) || ".mscz"}`
    );
    await fs.writeFile(tmpUpload, req.file.buffer);
    return { inputPath: tmpUpload, tmpUpload };
  }
  if (req.body?.path) {
    const inputPath = resolveListedScore(String(req.body.path));
    if (!inputPath) {
      const err = new Error("score not found");
      err.status = 404;
      throw err;
    }
    return { inputPath, tmpUpload: null };
  }
  const err = new Error("Provide a file upload or path");
  err.status = 400;
  throw err;
}

async function renderWithMuseScoreCli(inputPath) {
  if (!mscoreBin) {
    throw new Error("MuseScore CLI not found (looked for MuseScore 3/4 apps)");
  }
  const tmp = await fs.mkdtemp(path.join(os.tmpdir(), "msviewer-"));
  const outSvg = path.join(tmp, "page.svg");
  try {
    await run(mscoreBin, ["-o", outSvg, inputPath]);
    const files = (await fs.readdir(tmp))
      .filter((f) => f.endsWith(".svg"))
      .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
    if (!files.length) throw new Error("MuseScore produced no SVG pages");
    const pages = [];
    for (const f of files) {
      pages.push(await fs.readFile(path.join(tmp, f), "utf8"));
    }
    return {
      title: path.basename(inputPath, path.extname(inputPath)),
      pages,
      method: "musescore-cli",
    };
  } finally {
    await fs.rm(tmp, { recursive: true, force: true }).catch(() => {});
  }
}

async function cacheKeyFor(inputPath) {
  const st = await fs.stat(inputPath);
  return createHash("sha1")
    .update(`${inputPath}|${st.mtimeMs}|${st.size}`)
    .digest("hex");
}

async function exportAudioMp3(inputPath) {
  if (!mscoreBin) {
    throw new Error("MuseScore CLI not found (looked for MuseScore 3/4 apps)");
  }
  await fs.mkdir(CACHE_DIR, { recursive: true });
  const key = await cacheKeyFor(inputPath);
  const cached = path.join(CACHE_DIR, `${key}.mp3`);
  if (existsSync(cached)) {
    const st = await fs.stat(cached);
    if (st.size > 1000) return cached;
  }

  const tmp = await fs.mkdtemp(path.join(os.tmpdir(), "msviewer-audio-"));
  const outMp3 = path.join(tmp, "score.mp3");
  try {
    await run(mscoreBin, ["-o", outMp3, inputPath]);
    if (!existsSync(outMp3)) {
      // MuseScore sometimes names from input basename
      const alt = (await fs.readdir(tmp)).find((f) => f.endsWith(".mp3"));
      if (!alt) throw new Error("MuseScore produced no MP3");
      await fs.copyFile(path.join(tmp, alt), cached);
    } else {
      await fs.copyFile(outMp3, cached);
    }
    return cached;
  } finally {
    await fs.rm(tmp, { recursive: true, force: true }).catch(() => {});
  }
}

app.get("/api/health", (_req, res) => {
  res.json({
    ok: true,
    scoreDirs: SCORE_DIRS,
    mscoreBin: mscoreBin || null,
  });
});

app.get("/api/scores", async (_req, res) => {
  try {
    res.json({ scores: await listScores() });
  } catch (err) {
    res.status(500).json({ error: String(err.message || err) });
  }
});

app.get("/api/scores/file", async (req, res) => {
  const filePath = resolveListedScore(String(req.query.path || ""));
  if (!filePath) return res.status(404).json({ error: "score not found" });
  res.setHeader("Content-Type", "application/octet-stream");
  res.setHeader(
    "Content-Disposition",
    `inline; filename="${path.basename(filePath)}"`
  );
  createReadStream(filePath).pipe(res);
});

/** Server-side render via MuseScore CLI (reliable for MuseScore 4). */
app.post("/api/render", upload.single("file"), async (req, res) => {
  let tmpUpload = null;
  try {
    const resolved = await resolveInputPath(req);
    tmpUpload = resolved.tmpUpload;
    const result = await renderWithMuseScoreCli(resolved.inputPath);
    res.json(result);
  } catch (err) {
    res.status(err.status || 500).json({ error: String(err.message || err) });
  } finally {
    if (tmpUpload) await fs.rm(tmpUpload, { force: true }).catch(() => {});
  }
});

/** Export audio (MP3) via MuseScore CLI and stream it. */
app.post("/api/audio", upload.single("file"), async (req, res) => {
  let tmpUpload = null;
  try {
    const resolved = await resolveInputPath(req);
    tmpUpload = resolved.tmpUpload;
    const mp3Path = await exportAudioMp3(resolved.inputPath);
    res.setHeader("Content-Type", "audio/mpeg");
    res.setHeader(
      "Content-Disposition",
      `inline; filename="${path.basename(resolved.inputPath, path.extname(resolved.inputPath))}.mp3"`
    );
    createReadStream(mp3Path).pipe(res);
  } catch (err) {
    res.status(err.status || 500).json({ error: String(err.message || err) });
  } finally {
    if (tmpUpload) await fs.rm(tmpUpload, { force: true }).catch(() => {});
  }
});

app.listen(PORT, () => {
  console.log(`MuseScore viewer → http://localhost:${PORT}`);
  console.log(`Score dirs: ${SCORE_DIRS.join(", ") || "(none)"}`);
  console.log(`MuseScore CLI: ${mscoreBin || "(missing)"}`);
});
