"""Edit history with undo / redo (command pattern on the session's plain data).

An :class:`EditOperation` addresses a value by a JSON path ``target`` (a list: the
session attribute, then dict keys / list indices, e.g. ``["results", "peaks", 3,
"energy"]``) and records the value before and after.  ``apply`` / ``revert`` mutate
the session; values are deep-copied so the log never aliases live state.

Kinds
-----
``add_peak`` / ``remove_peak``  insert / delete the list element at ``target``.
``set_*``                       replace the value at ``target`` (``before_exists`` False
                                means the key did not exist, ``revert`` removes it).
``relocate_spectrum``           new path of the spectrum file (same SHA-256).
``replace_peaks``               the whole peak list after a manual refit (``details`` holds
                                the fit region, positions and options, so it can be repeated).

Every op also stores the session ``status`` it found (``status_before``) and restores it
on revert, so undo gives back exactly the previous state, including the staleness flags.
Kinds in :data:`STALE_KINDS` mark downstream results as requiring an update (they are
never recalculated here) and clear the "reviewed" flag.

The log is never shortened: undone ops stay in ``ops`` with ``undone=True``; a new
edit only empties the redo stack.  ``seal()`` (called when results are recomputed)
empties both stacks because the recorded list positions no longer apply.
"""
from __future__ import annotations

import copy
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from .common import from_known, new_id, utc_now

EDIT_KINDS = ("add_peak", "remove_peak", "set_peak_field", "set_sample_field", "set_setting",
              "set_context", "relocate_spectrum", "replace_peaks")
REASON_REQUIRED = ("remove_peak", "set_peak_field")
STALE_KINDS = ("add_peak", "remove_peak", "set_peak_field", "set_sample_field", "set_setting",
               "set_context", "replace_peaks")


def current_user() -> str:
    return os.environ.get("USERNAME") or os.environ.get("USER") or ""


def _parent(root, target: list):
    """(container, last key) of `target`; target[0] is an attribute of `root`."""
    if len(target) == 1:
        return root, target[0]
    obj = getattr(root, target[0])
    for k in target[1:-1]:
        obj = obj[k]
    return obj, target[-1]


def _get(root, target: list) -> tuple[bool, Any]:
    c, k = _parent(root, target)
    if c is root:
        return True, getattr(root, k)
    if isinstance(c, dict):
        return (k in c), c.get(k)
    return True, c[k]


def _set(root, target: list, value) -> None:
    c, k = _parent(root, target)
    if c is root:
        setattr(root, k, value)
    else:
        c[k] = value


@dataclass
class EditOperation:
    kind: str
    target: list
    after: Any = None
    before: Any = None
    before_exists: bool = True
    reason: str = ""
    user: str = field(default_factory=current_user)
    op_id: str = field(default_factory=new_id)
    timestamp: str = field(default_factory=utc_now)
    undone: bool = False
    status_before: Optional[dict] = None
    details: Optional[dict] = None      # e.g. manual-fit region and options (replace_peaks)

    def __post_init__(self):
        if self.kind not in EDIT_KINDS:
            raise ValueError(f"unknown edit kind {self.kind!r}")
        if self.kind in REASON_REQUIRED and not self.reason.strip():
            raise ValueError(f"a reason is required for '{self.kind}'")
        self.target = list(self.target)

    def capture(self, session) -> None:
        """Record the current value at `target` as `before` (not for add_peak)."""
        if self.kind != "add_peak":
            self.before_exists, v = _get(session, self.target)
            self.before = copy.deepcopy(v)

    def apply(self, session) -> None:
        self.status_before = copy.deepcopy(session.status)
        if self.kind == "add_peak":
            c, i = _parent(session, self.target)
            c.insert(i, copy.deepcopy(self.after))
        elif self.kind == "remove_peak":
            c, i = _parent(session, self.target)
            del c[i]
        else:
            _set(session, self.target, copy.deepcopy(self.after))
        if self.kind in STALE_KINDS:
            session.mark_stale(self.describe())

    def revert(self, session) -> None:
        if self.kind == "add_peak":
            c, i = _parent(session, self.target)
            del c[i]
        elif self.kind == "remove_peak":
            c, i = _parent(session, self.target)
            c.insert(i, copy.deepcopy(self.before))
        elif self.before_exists:
            _set(session, self.target, copy.deepcopy(self.before))
        else:
            c, k = _parent(session, self.target)
            del c[k]
        if self.status_before is not None:
            session.status = copy.deepcopy(self.status_before)

    def describe(self) -> str:
        path = ".".join(str(t) for t in self.target)
        s = f"{self.kind} {path}"
        return s + (f" ({self.reason})" if self.reason else "")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "EditOperation":
        return from_known(cls, d)


@dataclass
class EditHistory:
    ops: list[EditOperation] = field(default_factory=list)   # full log, creation order
    undo_stack: list[str] = field(default_factory=list)      # op ids, last = next to undo
    redo_stack: list[str] = field(default_factory=list)

    def _op(self, op_id: str) -> EditOperation:
        return next(o for o in self.ops if o.op_id == op_id)

    def do(self, op: EditOperation, session) -> EditOperation:
        op.capture(session)
        op.apply(session)
        self.ops.append(op)
        self.undo_stack.append(op.op_id)
        for oid in self.redo_stack:       # abandoned branch: kept in the log, stays undone
            self._op(oid).undone = True
        self.redo_stack.clear()
        return op

    def can_undo(self) -> bool:
        return bool(self.undo_stack)

    def can_redo(self) -> bool:
        return bool(self.redo_stack)

    def undo(self, session) -> Optional[EditOperation]:
        if not self.undo_stack:
            return None
        op = self._op(self.undo_stack.pop())
        op.revert(session)
        op.undone = True
        self.redo_stack.append(op.op_id)
        return op

    def redo(self, session) -> Optional[EditOperation]:
        if not self.redo_stack:
            return None
        op = self._op(self.redo_stack.pop())
        op.apply(session)
        op.undone = False
        self.undo_stack.append(op.op_id)
        return op

    def seal(self) -> None:
        """Forget undo/redo positions (log kept) - e.g. after the results were recomputed."""
        self.undo_stack.clear()
        self.redo_stack.clear()

    def to_dict(self) -> dict:
        return {"ops": [o.to_dict() for o in self.ops], "undo_stack": list(self.undo_stack),
                "redo_stack": list(self.redo_stack)}

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "EditHistory":
        d = d or {}
        return cls([EditOperation.from_dict(o) for o in d.get("ops", [])],
                   list(d.get("undo_stack", [])), list(d.get("redo_stack", [])))
