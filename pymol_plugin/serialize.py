# pyright: reportMissingImports=false
"""
Serialize PyMOL return values into JSON-friendly shapes.

NumPy arrays become {_kind: "ndarray", shape, dtype, data}.
ChemPy `Indexed` models become {_kind: "model", atoms: [...], n_atoms}.
Anything else not natively JSON-serializable gets a repr-truncated fallback.

Non-finite floats (NaN, +/-inf) are coerced to `None` so the resulting
payload is strict JSON: Python's `json.dumps` would otherwise emit the
non-standard `NaN` / `Infinity` tokens, which most strict parsers reject.
The coercion applies recursively to floats inside lists, dicts, ndarray
data, and atom fields.
"""

from __future__ import annotations
import math
from typing import Any


def serialize(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (list, tuple)):
        return [serialize(v) for v in value]
    if isinstance(value, dict):
        return {str(k): serialize(v) for k, v in value.items()}
    np = _maybe_numpy()
    if np is not None and isinstance(value, np.ndarray):
        return {
            "_kind": "ndarray",
            "shape": list(value.shape),
            "dtype": str(value.dtype),
            "data": serialize(value.tolist()),
        }
    indexed_cls = _maybe_chempy_indexed()
    if indexed_cls is not None and isinstance(value, indexed_cls):
        return {
            "_kind": "model",
            "atoms": [_serialize_atom(a) for a in value.atom],
            "n_atoms": len(value.atom),
        }
    return {"_kind": "repr", "value": repr(value)[:2000]}


def _serialize_atom(atom: Any) -> dict[str, Any]:
    fields = (
        "name",
        "resn",
        "resi",
        "chain",
        "segi",
        "elem",
        "ss",
        "b",
        "q",
        "vdw",
        "partial_charge",
        "formal_charge",
        "index",
        "id",
    )
    out: dict[str, Any] = {}
    for f in fields:
        if hasattr(atom, f):
            out[f] = serialize(getattr(atom, f))
    if hasattr(atom, "coord"):
        out["coord"] = serialize(list(atom.coord))
    return out


def _maybe_numpy():
    try:
        import numpy

        return numpy
    except ImportError:
        return None


def _maybe_chempy_indexed():
    try:
        from chempy import Indexed

        return Indexed
    except ImportError:
        return None
