"""Load ScoreDocument from MSCZ / MSCX paths or bytes."""

from __future__ import annotations

import zipfile
from pathlib import Path

from .mscx import ScoreDocument, parse_mscx


def _pick_mscx_name(names: list[str]) -> str:
    mscx = [n for n in names if n.lower().endswith(".mscx") and not n.startswith("__")]
    if not mscx:
        raise ValueError("MSCZ archive contains no .mscx score")
    # Prefer non-nested root-ish names
    mscx.sort(key=lambda n: (n.count("/"), len(n)))
    return mscx[0]


def score_from_mscz_bytes(data: bytes) -> ScoreDocument:
    with zipfile.ZipFile(__import__("io").BytesIO(data)) as zf:
        name = _pick_mscx_name(zf.namelist())
        raw = zf.read(name)
        return parse_mscx(raw, source_name=Path(name).name)


def score_from_mscx_bytes(data: bytes, *, source_name: str = "score.mscx") -> ScoreDocument:
    return parse_mscx(data, source_name=source_name)


def load_score(path: str | Path) -> ScoreDocument:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    data = p.read_bytes()
    if p.suffix.lower() == ".mscz":
        return score_from_mscz_bytes(data)
    if p.suffix.lower() in {".mscx", ".xml"}:
        return score_from_mscx_bytes(data, source_name=p.name)
    # Try zip first, then raw xml
    if data[:2] == b"PK":
        return score_from_mscz_bytes(data)
    return score_from_mscx_bytes(data, source_name=p.name)


def resolve_seed_score_path(seed_dir: Path, slug: str) -> Path:
    base = seed_dir / slug
    for name in ("score.mscz", "score.mscx", "score.musicxml", "score.xml"):
        cand = base / name
        if cand.exists():
            return cand
    raise FileNotFoundError(f"No score file under {base}")
