"""Mutable MuseScore MSCX document helpers."""

from __future__ import annotations

import copy
import io
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator
from xml.etree import ElementTree as ET

DURATION_TYPES = {
    "whole",
    "half",
    "quarter",
    "eighth",
    "16th",
    "sixteenth",
    "32nd",
    "64th",
    "dotted-half",
    "dotted-quarter",
    "dotted-eighth",
    "measure",
}

# MuseScore uses 16th not sixteenth
DURATION_ALIASES = {
    "sixteenth": "16th",
    "dotted-half": "half",  # dots handled separately when possible
    "dotted-quarter": "quarter",
    "dotted-eighth": "eighth",
}


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _child(el: ET.Element, name: str) -> ET.Element | None:
    for c in el:
        if _local(c.tag) == name:
            return c
    return None


def _children(el: ET.Element, name: str) -> list[ET.Element]:
    return [c for c in el if _local(c.tag) == name]


def _text_int(el: ET.Element | None, default: int | None = None) -> int | None:
    if el is None or el.text is None or el.text.strip() == "":
        return default
    return int(el.text.strip())


def _set_text(parent: ET.Element, name: str, value: str) -> ET.Element:
    node = _child(parent, name)
    if node is None:
        node = ET.SubElement(parent, name)
    node.text = value
    return node


@dataclass
class NoteRef:
    staff_id: str
    measure_index: int  # 0-based within staff
    measure_number: int  # 1-based logical
    voice_index: int
    chord: ET.Element
    note: ET.Element
    pitch: int
    tpc: int | None


class ScoreDocument:
    """In-memory MSCX score with measure/note mutators."""

    def __init__(self, root: ET.Element, *, source_name: str = "score.mscx"):
        self.root = root
        self.source_name = source_name
        self._ensure_score()

    def _ensure_score(self) -> ET.Element:
        if _local(self.root.tag) == "museScore":
            score = _child(self.root, "Score")
            if score is None:
                raise ValueError("MSCX missing Score element")
            return score
        if _local(self.root.tag) == "Score":
            return self.root
        raise ValueError(f"Unexpected root tag: {self.root.tag}")

    @property
    def score_el(self) -> ET.Element:
        return self._ensure_score()

    def clone(self) -> "ScoreDocument":
        return ScoreDocument(copy.deepcopy(self.root), source_name=self.source_name)

    def to_bytes(self) -> bytes:
        # MuseScore expects declaration
        buf = io.BytesIO()
        tree = ET.ElementTree(self.root)
        ET.indent(tree, space="  ")
        tree.write(buf, encoding="utf-8", xml_declaration=True)
        return buf.getvalue()

    def to_mscz_bytes(self) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(self.source_name, self.to_bytes())
            zf.writestr(
                "META-INF/container.xml",
                (
                    '<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<container>\n'
                    " <rootfiles>\n"
                    f'  <rootfile full-path="{self.source_name}"/>\n'
                    "  </rootfiles>\n"
                    "</container>\n"
                ),
            )
        return buf.getvalue()

    def staff_elements(self) -> list[ET.Element]:
        # Top-level Staff elements under Score (not Part/Staff)
        return [
            el
            for el in self.score_el
            if _local(el.tag) == "Staff" and el.get("id") is not None
        ]

    def measures_for_staff(self, staff: ET.Element) -> list[ET.Element]:
        return _children(staff, "Measure")

    def measure_count(self) -> int:
        staffs = self.staff_elements()
        if not staffs:
            return 0
        return max(len(self.measures_for_staff(s)) for s in staffs)

    def iter_notes(
        self,
        *,
        measure_start: int | None = None,
        measure_end: int | None = None,
        staff_ids: set[str] | None = None,
        voices: set[int] | None = None,
    ) -> Iterator[NoteRef]:
        start = measure_start or 1
        end = measure_end or self.measure_count()
        for staff in self.staff_elements():
            sid = staff.get("id") or ""
            if staff_ids and sid not in staff_ids:
                continue
            measures = self.measures_for_staff(staff)
            for mi, measure in enumerate(measures):
                mnum = mi + 1
                if mnum < start or mnum > end:
                    continue
                for vi, voice in enumerate(_children(measure, "voice")):
                    if voices is not None and (vi + 1) not in voices:
                        continue
                    for chord in _children(voice, "Chord"):
                        for note in _children(chord, "Note"):
                            pitch_el = _child(note, "pitch")
                            if pitch_el is None or pitch_el.text is None:
                                continue
                            tpc_el = _child(note, "tpc")
                            yield NoteRef(
                                staff_id=sid,
                                measure_index=mi,
                                measure_number=mnum,
                                voice_index=vi,
                                chord=chord,
                                note=note,
                                pitch=int(pitch_el.text),
                                tpc=_text_int(tpc_el),
                            )

    def transpose_selection(
        self,
        semitones: int,
        *,
        measure_start: int,
        measure_end: int,
        staff_ids: set[str] | None = None,
        voices: set[int] | None = None,
    ) -> int:
        changed = 0
        for ref in self.iter_notes(
            measure_start=measure_start,
            measure_end=measure_end,
            staff_ids=staff_ids,
            voices=voices,
        ):
            new_pitch = max(0, min(127, ref.pitch + semitones))
            _set_text(ref.note, "pitch", str(new_pitch))
            if ref.tpc is not None:
                _set_text(ref.note, "tpc", str(ref.tpc + semitones))
            # Drop accidentals; MuseScore will recompute on open/render
            for acc in list(_children(ref.note, "Accidental")):
                ref.note.remove(acc)
            changed += 1
        return changed

    def delete_selection(
        self,
        *,
        measure_start: int,
        measure_end: int,
        staff_ids: set[str] | None = None,
        voices: set[int] | None = None,
    ) -> int:
        """Replace chords in range with rests of the same duration."""
        removed = 0
        for staff in self.staff_elements():
            sid = staff.get("id") or ""
            if staff_ids and sid not in staff_ids:
                continue
            measures = self.measures_for_staff(staff)
            for mi, measure in enumerate(measures):
                mnum = mi + 1
                if mnum < measure_start or mnum > measure_end:
                    continue
                for vi, voice in enumerate(_children(measure, "voice")):
                    if voices is not None and (vi + 1) not in voices:
                        continue
                    for chord in list(_children(voice, "Chord")):
                        dur = _child(chord, "durationType")
                        dur_text = dur.text if dur is not None and dur.text else "quarter"
                        rest = ET.Element("Rest")
                        ET.SubElement(rest, "durationType").text = dur_text
                        # preserve dots if present
                        dots = _child(chord, "dots")
                        if dots is not None:
                            rest.append(copy.deepcopy(dots))
                        idx = list(voice).index(chord)
                        voice.remove(chord)
                        voice.insert(idx, rest)
                        removed += 1
        return removed

    def set_note_duration(
        self,
        duration: str,
        *,
        measure_start: int | None = None,
        measure_end: int | None = None,
        staff_ids: set[str] | None = None,
        voices: set[int] | None = None,
    ) -> int:
        dur = DURATION_ALIASES.get(duration, duration)
        if dur not in DURATION_TYPES and duration not in DURATION_TYPES:
            raise ValueError(f"Unsupported duration '{duration}'")
        # map alias for storage
        store = DURATION_ALIASES.get(duration, duration)
        if store == "sixteenth":
            store = "16th"
        dotted = duration.startswith("dotted-")
        changed = 0
        seen_chords: set[int] = set()
        for ref in self.iter_notes(
            measure_start=measure_start,
            measure_end=measure_end,
            staff_ids=staff_ids,
            voices=voices,
        ):
            cid = id(ref.chord)
            if cid in seen_chords:
                continue
            seen_chords.add(cid)
            _set_text(ref.chord, "durationType", store)
            existing_dots = _child(ref.chord, "dots")
            if dotted:
                if existing_dots is None:
                    ET.SubElement(ref.chord, "dots").text = "1"
                else:
                    existing_dots.text = "1"
            elif existing_dots is not None:
                ref.chord.remove(existing_dots)
            changed += 1
        return changed

    def duplicate_measures(
        self,
        measure_start: int,
        measure_end: int,
        insert_after: int | None = None,
    ) -> int:
        """Clone measure range after insert_after (default: measure_end). Returns # measures inserted per staff."""
        if measure_start < 1 or measure_end < measure_start:
            raise ValueError("Invalid measure range")
        target = insert_after if insert_after is not None else measure_end
        inserted = 0
        for staff in self.staff_elements():
            measures = self.measures_for_staff(staff)
            if measure_end > len(measures) or target > len(measures):
                raise ValueError("Measure range out of bounds")
            clones = [
                copy.deepcopy(measures[i])
                for i in range(measure_start - 1, measure_end)
            ]
            # Insert after target: position = target (0-based insert index = target)
            insert_at = target
            # measures are direct children; find index of Measure elements among staff children
            measure_nodes = [(i, el) for i, el in enumerate(list(staff)) if _local(el.tag) == "Measure"]
            if not measure_nodes:
                continue
            # absolute child index of measure at `target` (1-based)
            abs_idx = measure_nodes[target - 1][0]
            # insert after that measure
            for offset, clone in enumerate(clones):
                staff.insert(abs_idx + 1 + offset, clone)
            inserted = len(clones)
        return inserted

    def insert_measures(self, count: int, after_measure: int) -> int:
        if count < 1:
            raise ValueError("count must be >= 1")
        if after_measure < 0:
            raise ValueError("after_measure must be >= 0")
        for staff in self.staff_elements():
            measures = self.measures_for_staff(staff)
            template = measures[min(after_measure, max(0, len(measures) - 1))] if measures else None
            measure_nodes = [(i, el) for i, el in enumerate(list(staff)) if _local(el.tag) == "Measure"]
            if after_measure == 0:
                insert_at = measure_nodes[0][0] if measure_nodes else len(list(staff))
                abs_idx = insert_at - 1
            else:
                if after_measure > len(measures):
                    raise ValueError("after_measure out of bounds")
                abs_idx = measure_nodes[after_measure - 1][0]
            for offset in range(count):
                if template is not None:
                    m = copy.deepcopy(template)
                    # clear to whole rest in each voice
                    for voice in _children(m, "voice"):
                        for child in list(voice):
                            voice.remove(child)
                        rest = ET.SubElement(voice, "Rest")
                        ET.SubElement(rest, "durationType").text = "measure"
                else:
                    m = ET.Element("Measure")
                    voice = ET.SubElement(m, "voice")
                    rest = ET.SubElement(voice, "Rest")
                    ET.SubElement(rest, "durationType").text = "measure"
                staff.insert(abs_idx + 1 + offset, m)
        return count

    def delete_measures(self, measure_start: int, measure_end: int) -> int:
        if measure_start < 1 or measure_end < measure_start:
            raise ValueError("Invalid measure range")
        deleted = 0
        for staff in self.staff_elements():
            measures = self.measures_for_staff(staff)
            if measure_end > len(measures):
                raise ValueError("Measure range out of bounds")
            for i in range(measure_end - 1, measure_start - 2, -1):
                staff.remove(measures[i])
            deleted = measure_end - measure_start + 1
        return deleted

    def set_time_signature(self, numerator: int, denominator: int, measure: int = 1) -> None:
        for staff in self.staff_elements():
            measures = self.measures_for_staff(staff)
            if measure < 1 or measure > len(measures):
                raise ValueError("Measure out of bounds")
            m = measures[measure - 1]
            voices = _children(m, "voice")
            if not voices:
                voice = ET.SubElement(m, "voice")
                voices = [voice]
            voice = voices[0]
            ts = _child(voice, "TimeSig")
            if ts is None:
                ts = ET.Element("TimeSig")
                voice.insert(0, ts)
            _set_text(ts, "sigN", str(numerator))
            _set_text(ts, "sigD", str(denominator))

    def set_key_signature(self, fifths: int, measure: int = 1) -> None:
        for staff in self.staff_elements():
            measures = self.measures_for_staff(staff)
            if measure < 1 or measure > len(measures):
                raise ValueError("Measure out of bounds")
            m = measures[measure - 1]
            voices = _children(m, "voice")
            if not voices:
                voice = ET.SubElement(m, "voice")
                voices = [voice]
            voice = voices[0]
            ks = _child(voice, "KeySig")
            if ks is None:
                ks = ET.Element("KeySig")
                voice.insert(0, ks)
            _set_text(ks, "concertKey", str(fifths))

    def set_tempo(self, bpm: float, measure: int = 1) -> None:
        staffs = self.staff_elements()
        if not staffs:
            raise ValueError("No staves")
        measures = self.measures_for_staff(staffs[0])
        if measure < 1 or measure > len(measures):
            raise ValueError("Measure out of bounds")
        m = measures[measure - 1]
        voices = _children(m, "voice")
        if not voices:
            voice = ET.SubElement(m, "voice")
        else:
            voice = voices[0]
        tempo = ET.Element("Tempo")
        ET.SubElement(tempo, "tempo").text = str(bpm / 60.0)  # MuseScore stores beats per second
        ET.SubElement(tempo, "text").text = f"♩ = {int(bpm)}"
        voice.insert(0, tempo)

    def add_dynamic(self, marking: str, measure: int, beat: float = 1.0, staff_id: str | None = None) -> None:
        staffs = self.staff_elements()
        staff = None
        if staff_id:
            staff = next((s for s in staffs if s.get("id") == staff_id), None)
        if staff is None:
            staff = staffs[0]
        measures = self.measures_for_staff(staff)
        if measure < 1 or measure > len(measures):
            raise ValueError("Measure out of bounds")
        m = measures[measure - 1]
        voices = _children(m, "voice")
        voice = voices[0] if voices else ET.SubElement(m, "voice")
        dyn = ET.Element("Dynamic")
        ET.SubElement(dyn, "subtype").text = marking
        ET.SubElement(dyn, "text").text = marking
        # place roughly at beat via optional offset; MuseScore ignores unknown tags safely
        ET.SubElement(dyn, "velocity").text = "80"
        voice.insert(0, dyn)
        _ = beat  # reserved for finer placement

    def set_lyrics(
        self,
        text: str,
        measure: int,
        beat: float = 1.0,
        verse: int = 0,
        staff_id: str | None = None,
    ) -> int:
        staffs = self.staff_elements()
        staff = None
        if staff_id:
            staff = next((s for s in staffs if s.get("id") == staff_id), None)
        if staff is None:
            staff = staffs[0]
        measures = self.measures_for_staff(staff)
        if measure < 1 or measure > len(measures):
            raise ValueError("Measure out of bounds")
        m = measures[measure - 1]
        # attach to first chord in first voice
        for voice in _children(m, "voice"):
            for chord in _children(voice, "Chord"):
                notes = _children(chord, "Note")
                if not notes:
                    continue
                note = notes[0]
                # remove existing lyrics for verse
                for lyr in list(_children(note, "Lyrics")):
                    no = _child(lyr, "no")
                    if no is not None and no.text and int(no.text) != verse:
                        continue
                    note.remove(lyr)
                lyrics = ET.SubElement(note, "Lyrics")
                if verse:
                    ET.SubElement(lyrics, "no").text = str(verse)
                ET.SubElement(lyrics, "text").text = text
                _ = beat
                return 1
        return 0

    def add_note(
        self,
        pitch: int,
        duration: str,
        measure: int,
        beat: float = 1.0,
        staff_id: str | None = None,
        voice: int = 1,
    ) -> None:
        store = DURATION_ALIASES.get(duration, duration)
        if store == "sixteenth":
            store = "16th"
        staffs = self.staff_elements()
        staff = next((s for s in staffs if s.get("id") == staff_id), None) if staff_id else staffs[0]
        if staff is None:
            raise ValueError("Staff not found")
        measures = self.measures_for_staff(staff)
        if measure < 1 or measure > len(measures):
            raise ValueError("Measure out of bounds")
        m = measures[measure - 1]
        voices = _children(m, "voice")
        while len(voices) < voice:
            voices.append(ET.SubElement(m, "voice"))
            voices = _children(m, "voice")
        v = voices[voice - 1]
        # Replace first rest if present, else append chord
        chord = ET.Element("Chord")
        ET.SubElement(chord, "durationType").text = store
        note = ET.SubElement(chord, "Note")
        ET.SubElement(note, "pitch").text = str(pitch)
        # rough tpc from pitch class (C=14)
        pc = pitch % 12
        tpc_map = {0: 14, 1: 21, 2: 16, 3: 11, 4: 18, 5: 13, 6: 20, 7: 15, 8: 22, 9: 17, 10: 12, 11: 19}
        ET.SubElement(note, "tpc").text = str(tpc_map.get(pc, 14))
        rests = _children(v, "Rest")
        if rests:
            idx = list(v).index(rests[0])
            v.remove(rests[0])
            v.insert(idx, chord)
        else:
            v.append(chord)
        _ = beat

    def add_rest(
        self,
        duration: str,
        measure: int,
        beat: float = 1.0,
        staff_id: str | None = None,
        voice: int = 1,
    ) -> None:
        store = DURATION_ALIASES.get(duration, duration)
        if store == "sixteenth":
            store = "16th"
        staffs = self.staff_elements()
        staff = next((s for s in staffs if s.get("id") == staff_id), None) if staff_id else staffs[0]
        if staff is None:
            raise ValueError("Staff not found")
        measures = self.measures_for_staff(staff)
        if measure < 1 or measure > len(measures):
            raise ValueError("Measure out of bounds")
        m = measures[measure - 1]
        voices = _children(m, "voice")
        while len(voices) < voice:
            voices.append(ET.SubElement(m, "voice"))
            voices = _children(m, "voice")
        v = voices[voice - 1]
        rest = ET.Element("Rest")
        ET.SubElement(rest, "durationType").text = store
        v.append(rest)
        _ = beat

    def delete_note_at(
        self,
        *,
        measure: int,
        pitch: int | None = None,
        staff_id: str | None = None,
    ) -> int:
        removed = 0
        for ref in list(
            self.iter_notes(
                measure_start=measure,
                measure_end=measure,
                staff_ids={staff_id} if staff_id else None,
            )
        ):
            if pitch is not None and ref.pitch != pitch:
                continue
            notes = _children(ref.chord, "Note")
            if len(notes) <= 1:
                # replace whole chord with rest
                parent = None
                for staff in self.staff_elements():
                    for m in self.measures_for_staff(staff):
                        for voice in _children(m, "voice"):
                            if ref.chord in list(voice):
                                parent = voice
                                break
                if parent is not None:
                    dur = _child(ref.chord, "durationType")
                    rest = ET.Element("Rest")
                    ET.SubElement(rest, "durationType").text = (
                        dur.text if dur is not None and dur.text else "quarter"
                    )
                    idx = list(parent).index(ref.chord)
                    parent.remove(ref.chord)
                    parent.insert(idx, rest)
                    removed += 1
            else:
                ref.chord.remove(ref.note)
                removed += 1
            if pitch is not None:
                break
        return removed

    def summary(self) -> dict[str, Any]:
        pitches = [n.pitch for n in self.iter_notes()]
        return {
            "measure_count": self.measure_count(),
            "staff_count": len(self.staff_elements()),
            "note_count": len(pitches),
            "pitch_min": min(pitches) if pitches else None,
            "pitch_max": max(pitches) if pitches else None,
        }


def parse_mscx(data: bytes | str, *, source_name: str = "score.mscx") -> ScoreDocument:
    if isinstance(data, bytes):
        root = ET.fromstring(data)
    else:
        root = ET.fromstring(data.encode("utf-8"))
    return ScoreDocument(root, source_name=source_name)


def write_mscx(doc: ScoreDocument, path: Path) -> None:
    path.write_bytes(doc.to_bytes())
