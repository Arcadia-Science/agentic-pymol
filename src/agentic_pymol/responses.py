"""Typed envelope for plugin responses.

The plugin wire protocol returns one of two shapes on every op:

    success: {"ok": true,  "value": <Any>,  "stdout": <str>}
    failure: {"ok": false, "error": {"type", "message", "traceback"}, "stdout": <str>}

`OkResponse` is the parsed success envelope.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from agentic_pymol.errors import PyMOLError


@dataclass(frozen=True, slots=True)
class OkResponse:
    value: Any
    stdout: str

    @classmethod
    def from_envelope(cls, raw: dict[str, Any]) -> OkResponse:
        ok = raw.get("ok")
        stdout = raw.get("stdout", "")
        if not isinstance(stdout, str):
            raise PyMOLError(
                "MalformedResponse",
                f"'stdout' must be a string, got {type(stdout).__name__}",
                "",
                "",
            )
        if ok is False:
            err = raw.get("error")
            if not isinstance(err, dict):
                raise PyMOLError(
                    "MalformedResponse",
                    f"failed response missing 'error' object: {_clip(raw)}",
                    "",
                    stdout,
                )
            raise PyMOLError(
                str(err.get("type", "PyMOLError")),
                str(err.get("message", "unknown error")),
                str(err.get("traceback", "")),
                stdout,
            )
        if ok is not True:
            raise PyMOLError(
                "MalformedResponse",
                f"missing or non-bool 'ok' field: {_clip(raw)}",
                "",
                stdout,
            )
        if "value" not in raw:
            raise PyMOLError(
                "MalformedResponse",
                f"ok response missing 'value' field: {_clip(raw)}",
                "",
                stdout,
            )
        return cls(value=raw["value"], stdout=stdout)


def _clip(raw: dict[str, Any]) -> str:
    text = repr(raw)
    if len(text) <= 500:
        return text
    return text[:500] + "…"
