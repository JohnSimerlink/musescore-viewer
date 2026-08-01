import express from "express";
import fs from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT || 5177);
const SEED_DIR = path.join(__dirname, "public", "seed");
const AGENT_URL = (process.env.COPLAND_AGENT_URL || "http://127.0.0.1:5178").replace(/\/$/, "");

const app = express();
app.use(express.json({ limit: "2mb" }));
app.use(express.static(path.join(__dirname, "public")));

async function proxyJson(req, res, agentPath, { method } = {}) {
  try {
    const r = await fetch(`${AGENT_URL}${agentPath}`, {
      method: method || req.method,
      headers: { "Content-Type": "application/json" },
      body: ["GET", "HEAD"].includes(method || req.method)
        ? undefined
        : JSON.stringify(req.body || {}),
      signal: AbortSignal.timeout(120_000),
    });
    const text = await r.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      data = { error: "invalid_agent_response", raw: text.slice(0, 500) };
    }
    res.status(r.status).json(data);
  } catch (err) {
    res.status(503).json({
      error: "agent_unreachable",
      detail: String(err.message || err),
      reply:
        "Copland agent is not reachable. Start it with `npm run agent` (Python sidecar on :5178).",
    });
  }
}

async function proxyBinary(req, res, agentPath) {
  try {
    const r = await fetch(`${AGENT_URL}${agentPath}`, {
      method: "GET",
      signal: AbortSignal.timeout(60_000),
    });
    if (!r.ok) {
      const text = await r.text();
      return res.status(r.status).send(text);
    }
    const ctype = r.headers.get("content-type") || "application/octet-stream";
    res.setHeader("Content-Type", ctype);
    const buf = Buffer.from(await r.arrayBuffer());
    res.status(r.status).send(buf);
  } catch (err) {
    res.status(503).json({
      error: "agent_unreachable",
      detail: String(err.message || err),
    });
  }
}

app.get("/api/health", async (_req, res) => {
  let agent = { ok: false, reachable: false };
  try {
    const r = await fetch(`${AGENT_URL}/api/health`, { signal: AbortSignal.timeout(1500) });
    agent = { reachable: true, ...(await r.json()) };
  } catch (err) {
    agent = { ok: false, reachable: false, error: String(err.message || err) };
  }
  res.json({
    ok: true,
    mode: "frontend-seed",
    seedDir: existsSync(SEED_DIR),
    agentUrl: AGENT_URL,
    agent,
  });
});

app.get("/api/catalog", async (_req, res) => {
  try {
    const catalogPath = path.join(SEED_DIR, "catalog.json");
    if (!existsSync(catalogPath)) {
      return res.json({ scores: [] });
    }
    const catalog = JSON.parse(await fs.readFile(catalogPath, "utf8"));
    res.json(catalog);
  } catch (err) {
    res.status(500).json({ error: String(err.message || err) });
  }
});

app.post("/api/chat", (req, res) => proxyJson(req, res, "/api/chat"));
app.post("/api/session/open", (req, res) => proxyJson(req, res, "/api/session/open"));
app.post("/api/session/reset", (req, res) => proxyJson(req, res, "/api/session/reset"));
app.post("/api/session/apply", (req, res) => proxyJson(req, res, "/api/session/apply"));
app.get("/api/session/:slug", (req, res) =>
  proxyJson(req, res, `/api/session/${encodeURIComponent(req.params.slug)}`, { method: "GET" }),
);
app.post("/api/session/:slug/render", (req, res) =>
  proxyJson(req, res, `/api/session/${encodeURIComponent(req.params.slug)}/render`),
);
app.get("/api/session/:slug/assets/:name", (req, res) => {
  const q = req.url.includes("?") ? req.url.slice(req.url.indexOf("?")) : "";
  return proxyBinary(
    req,
    res,
    `/api/session/${encodeURIComponent(req.params.slug)}/assets/${encodeURIComponent(req.params.name)}${q}`,
  );
});

app.listen(PORT, () => {
  console.log(`Copland viewer → http://localhost:${PORT}`);
  console.log(`Agent proxy → ${AGENT_URL}`);
});
