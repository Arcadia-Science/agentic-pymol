from __future__ import annotations
from typing import Any, Literal

from agentic_pymol.app import client, mcp
from agentic_pymol.types import AlignResult, CEAlignResult


@mcp.tool()
def align(
    mobile: str,
    target: str,
    method: Literal["align", "super"] = "align",
    cycles: int = 5,
    cutoff: float = 2.0,
    transform: bool = True,
    object_name: str = "",
) -> AlignResult:
    """
    Structurally align two selections by sequence-aware or structure-aware refinement.

    `method`:
        - "align" — sequence-aware (Needleman-Wunsch + iterative refinement).
                    Best for >30% identity.
        - "super" — structure-aware refinement, better for distant homologs.

    For sequence-independent alignment of very distant homologs, use `cealign`.

    `transform=False` computes the alignment without moving `mobile`.
    `object_name` creates a named alignment object linking matched atoms.
    """
    kwargs: dict[str, Any] = {
        "cycles": cycles,
        "cutoff": cutoff,
        "transform": 1 if transform else 0,
    }
    if object_name:
        kwargs["object"] = object_name
    response = client.call(method, [mobile, target], kwargs, "align")
    return AlignResult(*response.value)


@mcp.tool()
def cealign(mobile: str, target: str, transform: bool = True) -> CEAlignResult:
    """
    Combinatorial Extension structural alignment — sequence-independent.
    Best for very low sequence identity. For sequence-aware alignment, use `align`.

    `transform=False` computes the alignment without moving `mobile`.
    """
    kwargs: dict[str, Any] = {"transform": 1 if transform else 0}
    response = client.call("cealign", [target, mobile], kwargs, "cealign")
    return CEAlignResult(**response.value)


@mcp.tool()
def rms(mobile: str, target: str, fit: bool = False, matchmaker: int = 0) -> float:
    """
    Compute RMSD between two selections without superposition.

    `fit=True` calls `cmd.rms` (allows iterative outlier rejection).
    `fit=False` calls `cmd.rms_cur` (pure RMSD on current coordinates).
    `matchmaker`: 0 = atoms must match by selection order, 1 = match by identifier.
    """
    fn = "rms" if fit else "rms_cur"
    response = client.call(fn, [mobile, target], {"matchmaker": matchmaker}, "rms")
    return float(response.value)
