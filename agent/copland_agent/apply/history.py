"""Append-only mutation log (tree-friendly substrate for versions / collab)."""

from __future__ import annotations

import itertools
import time
from dataclasses import dataclass, field
from typing import Any

from ..score.mscx import ScoreDocument


@dataclass
class MutationEvent:
    """One applied edit (or root). Document snapshot is the state AFTER this event."""

    id: str
    parent_id: str | None
    tool: str
    args: dict[str, Any]
    detail: str | None
    document: ScoreDocument
    created_at: float = field(default_factory=time.time)
    labels: list[str] = field(default_factory=list)

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "tool": self.tool,
            "args": self.args,
            "detail": self.detail,
            "created_at": self.created_at,
            "labels": list(self.labels),
        }


class MutationLog:
    """Tree of mutations with a current head; linear undo/redo along a spine."""

    def __init__(self, root_document: ScoreDocument):
        self._ids = itertools.count(1)
        root_id = self._next_id()
        self.events: dict[str, MutationEvent] = {
            root_id: MutationEvent(
                id=root_id,
                parent_id=None,
                tool="root",
                args={},
                detail="Initial score state",
                document=root_document.clone(),
            )
        }
        self.head_id = root_id
        # Children map for redo along preferred child (last written)
        self._children: dict[str, list[str]] = {root_id: []}
        self._preferred_child: dict[str, str] = {}
        self.labels: dict[str, str] = {}  # label -> event id

    def _next_id(self) -> str:
        return f"m{next(self._ids)}"

    @property
    def head(self) -> MutationEvent:
        return self.events[self.head_id]

    def document(self) -> ScoreDocument:
        return self.head.document

    def can_undo(self) -> bool:
        return self.head.parent_id is not None

    def can_redo(self) -> bool:
        return self.head_id in self._preferred_child

    def append(
        self,
        *,
        tool: str,
        args: dict[str, Any],
        detail: str | None,
        document: ScoreDocument,
    ) -> MutationEvent:
        eid = self._next_id()
        parent = self.head_id
        ev = MutationEvent(
            id=eid,
            parent_id=parent,
            tool=tool,
            args=dict(args),
            detail=detail,
            document=document.clone(),
        )
        self.events[eid] = ev
        self._children.setdefault(parent, []).append(eid)
        self._children.setdefault(eid, [])
        self._preferred_child[parent] = eid
        # New edit clears redo preference beyond this branch tip
        self._preferred_child.pop(eid, None)
        self.head_id = eid
        return ev

    def undo(self) -> MutationEvent | None:
        parent = self.head.parent_id
        if parent is None:
            return None
        self._preferred_child[parent] = self.head_id
        self.head_id = parent
        return self.head

    def redo(self) -> MutationEvent | None:
        child = self._preferred_child.get(self.head_id)
        if child is None:
            return None
        self.head_id = child
        return self.head

    def hop_to(self, event_id: str) -> MutationEvent:
        if event_id not in self.events:
            raise KeyError(f"Unknown mutation id '{event_id}'")
        self.head_id = event_id
        return self.head

    def hop_to_index(self, index: int) -> MutationEvent:
        """Hop along the path from root to the current tip's lineage index.

        Index 0 = root. Uses the ancestry of the furthest tip reachable via
        preferred children from root if head is mid-spine; otherwise ancestry of head.
        """
        spine = self.spine_ids()
        if index < 0 or index >= len(spine):
            raise IndexError(f"Mutation index {index} out of range 0..{len(spine) - 1}")
        return self.hop_to(spine[index])

    def spine_ids(self) -> list[str]:
        """Path from root → current head."""
        path: list[str] = []
        cur: str | None = self.head_id
        while cur is not None:
            path.append(cur)
            cur = self.events[cur].parent_id
        path.reverse()
        return path

    def label_current(self, name: str) -> MutationEvent:
        label = name.strip()
        if not label:
            raise ValueError("Label must be non-empty")
        self.labels[label] = self.head_id
        if label not in self.head.labels:
            self.head.labels.append(label)
        return self.head

    def hop_to_label(self, name: str) -> MutationEvent:
        if name not in self.labels:
            raise KeyError(f"Unknown label '{name}'")
        return self.hop_to(self.labels[name])

    def public_history(self, *, limit: int = 40) -> dict[str, Any]:
        spine = self.spine_ids()
        events = [self.events[i].public() for i in spine[-limit:]]
        return {
            "head_id": self.head_id,
            "spine": spine,
            "events": events,
            "labels": dict(self.labels),
            "can_undo": self.can_undo(),
            "can_redo": self.can_redo(),
            "index": len(spine) - 1,
        }
