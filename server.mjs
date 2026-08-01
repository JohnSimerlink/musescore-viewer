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
app.use(express.json({ limit: "1mb" }));
app.use(express.static(path.join(__dirname, "public")));

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

app.post("/api/chat", async (req, res) => {
  try {
    const r = await fetch(`${AGENT_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req.body || {}),
      signal: AbortSignal.timeout(60_000),
    });
    const text = await r.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      data = { reply: text, error: "invalid_agent_response" };
    }
    res.status(r.status).json(data);
  } catch (err) {
    res.status(503).json({
      reply:
        "Copland agent is not reachable. Start it with `npm run agent` (Python sidecar on :5178).",
      error: "agent_unreachable",
      detail: String(err.message || err),
      tool_calls: [],
      planned_ops: [],
    });
  }
});

app.listen(PORT, () => {
  console.log(`Copland viewer → http://localhost:${PORT}`);
  console.log(`Agent proxy → ${AGENT_URL}`);
});
