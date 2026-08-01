import express from "express";
import fs from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT || 5177);
const SEED_DIR = path.join(__dirname, "public", "seed");

const app = express();
app.use(express.static(path.join(__dirname, "public")));

app.get("/api/health", (_req, res) => {
  res.json({
    ok: true,
    mode: "frontend-seed",
    seedDir: existsSync(SEED_DIR),
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

app.listen(PORT, () => {
  console.log(`MuseScore viewer (frontend seed) → http://localhost:${PORT}`);
});
