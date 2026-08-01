#!/usr/bin/env bash
# Pre-render MuseScore files into public/seed/<slug>/ for frontend-only deploys.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SEED_DIR="$ROOT/public/seed"
MSCORE="${MSCORE_BIN:-/Applications/MuseScore 4.app/Contents/MacOS/mscore}"

if [[ ! -x "$MSCORE" ]]; then
  echo "MuseScore CLI not found at: $MSCORE" >&2
  exit 1
fi

mkdir -p "$SEED_DIR"

slugify() {
  echo "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//; s/-+/-/g' | cut -c1-60
}

prepare_one() {
  local src="$1"
  local title="$2"
  local slug
  slug="$(slugify "$title")"
  local out="$SEED_DIR/$slug"
  local tmp
  tmp="$(mktemp -d)"

  echo "==> $title ($slug)"
  mkdir -p "$out"
  cp "$src" "$out/score.mscz"

  "$MSCORE" -o "$tmp/page.svg" "$src" >/dev/null
  "$MSCORE" -o "$tmp/score.spos" "$src" >/dev/null
  "$MSCORE" -o "$tmp/score.mp3" "$src" >/dev/null

  python3 - "$tmp" "$out" "$title" "$slug" <<'PY'
import json, re, shutil, sys
from pathlib import Path

tmp = Path(sys.argv[1])
out = Path(sys.argv[2])
title = sys.argv[3]
slug = sys.argv[4]
svgs = sorted(tmp.glob("*.svg"), key=lambda p: p.name)
if not svgs:
    raise SystemExit(f"no svg for {title}")
pages = []
for i, p in enumerate(svgs):
    dest = out / f"page-{i+1}.svg"
    shutil.copy2(p, dest)
    pages.append(dest.name)

spos = next(tmp.glob("*.spos"), None)
mp3 = next(tmp.glob("*.mp3"), None)
if not spos or not mp3:
    raise SystemExit(f"missing spos/mp3 for {title}")

xml = spos.read_text(encoding="utf-8", errors="replace")
elements = {}
for m in re.finditer(r"<element\s+([^/>]+)/>", xml):
    attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
    eid = int(attrs["id"])
    elements[str(eid)] = {
        "id": eid,
        "x": float(attrs["x"]),
        "y": float(attrs["y"]),
        "sx": float(attrs["sx"]),
        "sy": float(attrs["sy"]),
        "page": int(attrs["page"]),
    }
events = [
    {"elid": int(a), "positionMs": int(b)}
    for a, b in re.findall(r'<event\s+elid="(\d+)"\s+position="(\d+)"\s*/>', xml)
]
events.sort(key=lambda e: e["positionMs"])
(out / "timeline.json").write_text(
    json.dumps({"unit": 12, "elements": elements, "events": events}),
    encoding="utf-8",
)
shutil.copy2(mp3, out / "audio.mp3")
meta = {
    "slug": slug,
    "title": title,
    "pages": pages,
    "audio": "audio.mp3",
    "timeline": "timeline.json",
    "score": "score.mscz",
    "pageCount": len(pages),
    "durationMs": events[-1]["positionMs"] if events else None,
}
(out / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
print(f"   pages={len(pages)} events={len(events)} audio={(out/'audio.mp3').stat().st_size} bytes")
PY

  rm -rf "$tmp"
}

# Seed set
prepare_one \
  "/Users/johnsimerlink/Documents/MuseScore4/Scores/DanceWithYouNotMuted.mscz" \
  "Dance With You"

prepare_one \
  "/Users/johnsimerlink/Documents/incommon/Man I Need (Olivia Dean).mscz" \
  "Man I Need (Olivia Dean)"

prepare_one \
  "/Users/johnsimerlink/Documents/incommon/Mad World (Tears for Fears) SATB_A_Cappella 2024-08-31.mscz" \
  "Mad World"

prepare_one \
  "/Users/johnsimerlink/Documents/incommon/Winter Wonderland 2024-11-29.mscz" \
  "Winter Wonderland"

# Catalog index
python3 - <<PY
import json
from pathlib import Path
seed = Path("$SEED_DIR")
items = []
for meta_path in sorted(seed.glob("*/meta.json")):
    meta = json.loads(meta_path.read_text())
    items.append({
        "slug": meta["slug"],
        "title": meta["title"],
        "pageCount": meta["pageCount"],
        "durationMs": meta.get("durationMs"),
        "metaPath": f"/seed/{meta['slug']}/meta.json",
    })
(seed / "catalog.json").write_text(json.dumps({"scores": items}, indent=2), encoding="utf-8")
print("catalog:", len(items), "scores")
for s in items:
    print(" -", s["title"], f"({s['slug']})")
PY

echo "Done. Seed assets in $SEED_DIR"
