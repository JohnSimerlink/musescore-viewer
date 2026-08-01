"""Unit tests for score load + apply layer (TDD core)."""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from copland_agent.apply.engine import ApplyEngine
from copland_agent.models import SelectionContext
from copland_agent.score.load import load_score, score_from_mscz_bytes
from copland_agent.score.mscx import parse_mscx

FIXTURE = Path(__file__).parent / "fixtures" / "mini.mscx"
SEED_MSCZ = (
    Path(__file__).resolve().parents[2]
    / "public"
    / "seed"
    / "dance-with-you"
    / "score.mscz"
)


@pytest.fixture
def mini_doc():
    return parse_mscx(FIXTURE.read_bytes(), source_name="mini.mscx")


@pytest.fixture
def engine(mini_doc):
    eng = ApplyEngine(mini_doc)
    eng.auto = False  # type: ignore[attr-defined]
    return eng


def test_load_mini_fixture(mini_doc):
    assert mini_doc.measure_count() == 6
    summary = mini_doc.summary()
    assert summary["note_count"] >= 8
    assert summary["pitch_min"] == 60


@pytest.mark.skipif(not SEED_MSCZ.exists(), reason="seed mscz missing")
def test_load_seed_score():
    doc = load_score(SEED_MSCZ)
    assert doc.measure_count() >= 4
    assert doc.summary()["note_count"] > 0


def test_mscz_roundtrip_bytes(mini_doc):
    raw = mini_doc.to_mscz_bytes()
    assert raw[:2] == b"PK"
    with zipfile.ZipFile(BytesIO(raw)) as zf:
        assert any(n.endswith(".mscx") for n in zf.namelist())
    again = score_from_mscz_bytes(raw)
    assert again.measure_count() == mini_doc.measure_count()


def test_transpose_applies(engine):
    sel = SelectionContext(measure_start=4, measure_end=6)
    before = [n.pitch for n in engine.document.iter_notes(measure_start=4, measure_end=6)]
    result = engine.apply(
        "transpose_selection",
        {"semitones": 1, "selection": sel},
    )
    assert result.op.status == "applied"
    after = [n.pitch for n in engine.document.iter_notes(measure_start=4, measure_end=6)]
    assert after == [p + 1 for p in before]


def test_delete_selection_applies(engine):
    sel = SelectionContext(measure_start=2, measure_end=2)
    result = engine.apply("delete_selection", {"selection": sel})
    assert result.op.status == "applied"
    notes = list(engine.document.iter_notes(measure_start=2, measure_end=2))
    assert notes == []


def test_set_duration_applies(engine):
    sel = SelectionContext(measure_start=1, measure_end=1)
    result = engine.apply(
        "set_note_duration",
        {"duration": "half", "selection": sel},
    )
    assert result.op.status == "applied"
    for ref in engine.document.iter_notes(measure_start=1, measure_end=1):
        dur = None
        for c in ref.chord:
            if c.tag.endswith("durationType") or c.tag == "durationType":
                dur = c.text
        assert dur == "half"


def test_duplicate_measures_applies(engine):
    before = engine.document.measure_count()
    result = engine.apply(
        "duplicate_measures",
        {"measure_start": 1, "measure_end": 2, "insert_after": 2},
    )
    assert result.op.status == "applied"
    assert engine.document.measure_count() == before + 2


def test_undo_redo_transpose(engine):
    sel = SelectionContext(measure_start=1, measure_end=1)
    original = [n.pitch for n in engine.document.iter_notes(measure_start=1, measure_end=1)]
    engine.apply("transpose_selection", {"semitones": 2, "selection": sel})
    up = [n.pitch for n in engine.document.iter_notes(measure_start=1, measure_end=1)]
    assert up == [p + 2 for p in original]
    undo = engine.apply("undo", {})
    assert undo.op.status == "applied"
    restored = [n.pitch for n in engine.document.iter_notes(measure_start=1, measure_end=1)]
    assert restored == original
    redo = engine.apply("redo", {})
    assert redo.op.status == "applied"
    redone = [n.pitch for n in engine.document.iter_notes(measure_start=1, measure_end=1)]
    assert redone == up


def test_nl_style_select_and_transpose(engine):
    """Equivalent of: select m4–6 and transpose up a half step."""
    set_sel = engine.apply(
        "set_selection",
        {"measure_start": 4, "measure_end": 6},
    )
    assert set_sel.op.status == "applied"
    before = [n.pitch for n in engine.document.iter_notes(measure_start=4, measure_end=6)]
    result = engine.apply("transpose_selection", {"semitones": 1})
    assert result.op.status == "applied"
    after = [n.pitch for n in engine.document.iter_notes(measure_start=4, measure_end=6)]
    assert after == [p + 1 for p in before]


def test_copy_cut_paste_and_insert_delete(engine):
    engine.apply("set_selection", {"measure_start": 1, "measure_end": 1})
    assert engine.apply("copy_selection", {}).op.status == "applied"
    before = engine.document.measure_count()
    assert engine.apply("paste_selection", {"target": 1}).op.status == "applied"
    assert engine.document.measure_count() == before + 1
    assert engine.apply(
        "insert_measures", {"count": 1, "after_measure": 1}
    ).op.status == "applied"
    mid = engine.document.measure_count()
    assert engine.apply(
        "delete_measures", {"measure_start": mid, "measure_end": mid}
    ).op.status == "applied"


def test_remaining_mvp_tools_registered(engine):
    tools = [
        ("add_note", {"pitch": 60, "duration": "quarter", "measure": 5}),
        ("add_rest", {"duration": "quarter", "measure": 5}),
        ("set_time_signature", {"numerator": 3, "denominator": 4, "measure": 1}),
        ("set_key_signature", {"fifths": 1, "measure": 1}),
        ("set_tempo", {"bpm": 120, "measure": 1}),
        ("add_dynamic", {"marking": "mf", "measure": 1}),
        ("set_lyrics", {"text": "la", "measure": 1}),
        ("set_selection_voices", {"voices": ["1"], "staves": ["1"]}),
        ("play_selection", {}),
    ]
    engine.apply("set_selection", {"measure_start": 1, "measure_end": 2})
    for name, args in tools:
        result = engine.apply(name, args)
        assert result.op.status == "applied", f"{name}: {result.op.detail}"


def test_no_silent_stub_for_transpose(engine):
    engine.apply("set_selection", {"measure_start": 1, "measure_end": 1})
    op = engine.apply("transpose_selection", {"semitones": -1}).op
    assert op.status == "applied"
    assert op.status != "stub"
    assert "Would" not in (op.detail or "")


def test_mutation_log_hop_and_label(engine):
    sel = SelectionContext(measure_start=1, measure_end=1)
    root_id = engine.log.head_id
    engine.apply("transpose_selection", {"semitones": 1, "selection": sel})
    mid = engine.log.head_id
    engine.apply("transpose_selection", {"semitones": 1, "selection": sel})
    tip = engine.log.head_id
    assert tip != mid != root_id
    label = engine.apply("label_version", {"name": "v3.1"})
    assert label.op.status == "applied"
    assert engine.log.labels["v3.1"] == tip
    hop = engine.apply("hop_to", {"id": root_id})
    assert hop.op.status == "applied"
    assert engine.log.head_id == root_id
    pitches = [n.pitch for n in engine.document.iter_notes(measure_start=1, measure_end=1)]
    engine.apply("hop_to", {"id": tip})
    tipped = [n.pitch for n in engine.document.iter_notes(measure_start=1, measure_end=1)]
    assert tipped == [p + 2 for p in pitches]
    hist = engine.log.public_history()
    assert hist["head_id"] == tip
    assert "v3.1" in hist["labels"]
