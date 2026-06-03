"""Shared dataclasses for tool return values.

Each MCP tool publishes a JSON output schema derived from its return annotation, so
heterogeneous-shape returns live here as named dataclasses. The schema flows back to the
LLM as part of the tool definition.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Status:
    objects: list[str]
    selections: list[str]
    frame: int
    state: int


@dataclass(frozen=True, slots=True)
class RunResult:
    stdout: str
    value: Any


@dataclass(frozen=True, slots=True)
class Extent:
    min: list[float]
    max: list[float]


@dataclass(frozen=True, slots=True)
class Atom:
    """
    The plugin's ChempyModel serializer (`pymol_plugin/serialize.py`) gates each atom
    field on `hasattr`, so atoms loaded from minimal sources may omit some fields.
    `Atom` therefore declares every field with a `None` default so `Atom(**wire_dict)`
    works regardless of which fields the wire payload contains.
    """

    name: str | None = None
    resn: str | None = None
    resi: str | None = None
    chain: str | None = None
    segi: str | None = None
    elem: str | None = None
    ss: str | None = None
    b: float | None = None
    q: float | None = None
    vdw: float | None = None
    partial_charge: float | None = None
    formal_charge: float | None = None
    index: int | None = None
    id: int | None = None
    coord: list[float] | None = None


@dataclass(frozen=True, slots=True)
class Model:
    atoms: list[Atom]
    n_atoms: int


@dataclass(frozen=True, slots=True)
class AlignResult:
    rmsd_refined: float
    n_atoms_refined: int
    n_cycles: int
    rmsd_initial: float
    n_atoms_initial: int
    raw_score: float
    n_residues_aligned: int


@dataclass(frozen=True, slots=True)
class CEAlignResult:
    RMSD: float
    alignment_length: int
    rotation_matrix: list[float]
