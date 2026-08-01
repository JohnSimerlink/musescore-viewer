"""Render MSCZ/MSCX via MuseScore CLI when available."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from ..score.mscx import ScoreDocument


@dataclass
class RenderResult:
    ok: bool
    mode: str  # "musescore" | "unavailable" | "error"
    pages: list[str] = field(default_factory=list)  # relative names page-N.svg
    timeline: dict | None = None
    audio_name: str | None = None
    detail: str | None = None
    out_dir: str | None = None


def find_mscore() -> Path | None:
    env = os.environ.get("MSCORE_BIN")
    candidates = []
    if env:
        candidates.append(Path(env))
    which = shutil.which("mscore") or shutil.which("mscore4") or shutil.which("musescore4")
    if which:
        candidates.append(Path(which))
    candidates.extend(
        [
            Path("/Applications/MuseScore 4.app/Contents/MacOS/mscore"),
            Path("/usr/bin/mscore"),
            Path("/usr/local/bin/mscore"),
        ]
    )
    for c in candidates:
        if c and c.exists() and os.access(c, os.X_OK):
            return c
    return None


def _parse_spos(spos_path: Path) -> dict:
    xml = spos_path.read_text(encoding="utf-8", errors="replace")
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
    return {"unit": 12, "elements": elements, "events": events}


def render_score(
    document: ScoreDocument,
    out_dir: Path,
    *,
    include_audio: bool = False,
    timeout_s: float = 120.0,
) -> RenderResult:
    mscore = find_mscore()
    if mscore is None:
        return RenderResult(
            ok=False,
            mode="unavailable",
            detail=(
                "MuseScore CLI not found. Score mutations still apply in-memory; "
                "SVG re-render requires MuseScore 4 locally (set MSCORE_BIN)."
            ),
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="copland-render-") as tmp:
        tmp_path = Path(tmp)
        mscz_path = tmp_path / "score.mscz"
        mscz_path.write_bytes(document.to_mscz_bytes())
        svg_out = tmp_path / "page.svg"
        spos_out = tmp_path / "score.spos"
        try:
            subprocess.run(
                [str(mscore), "-o", str(svg_out), str(mscz_path)],
                check=True,
                capture_output=True,
                timeout=timeout_s,
            )
            subprocess.run(
                [str(mscore), "-o", str(spos_out), str(mscz_path)],
                check=True,
                capture_output=True,
                timeout=timeout_s,
            )
            if include_audio:
                subprocess.run(
                    [str(mscore), "-o", str(tmp_path / "score.mp3"), str(mscz_path)],
                    check=True,
                    capture_output=True,
                    timeout=timeout_s,
                )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
            return RenderResult(
                ok=False,
                mode="error",
                detail=f"MuseScore render failed: {exc}",
            )

        svgs = sorted(tmp_path.glob("*.svg"), key=lambda p: p.name)
        if not svgs:
            return RenderResult(ok=False, mode="error", detail="No SVG pages produced.")
        pages: list[str] = []
        for i, p in enumerate(svgs, start=1):
            name = f"page-{i}.svg"
            shutil.copy2(p, out_dir / name)
            pages.append(name)

        spos = next(tmp_path.glob("*.spos"), None)
        timeline = _parse_spos(spos) if spos else None
        if timeline is not None:
            (out_dir / "timeline.json").write_text(
                json.dumps(timeline), encoding="utf-8"
            )

        audio_name = None
        mp3 = next(tmp_path.glob("*.mp3"), None)
        if mp3:
            audio_name = "audio.mp3"
            shutil.copy2(mp3, out_dir / audio_name)

        meta = {
            "pages": pages,
            "timeline": "timeline.json" if timeline else None,
            "audio": audio_name,
            "renderMode": "musescore",
        }
        (out_dir / "meta.render.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )

        return RenderResult(
            ok=True,
            mode="musescore",
            pages=pages,
            timeline=timeline,
            audio_name=audio_name,
            out_dir=str(out_dir),
            detail=f"Rendered {len(pages)} page(s) via MuseScore.",
        )
