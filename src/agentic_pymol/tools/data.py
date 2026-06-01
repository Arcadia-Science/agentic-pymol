from __future__ import annotations
from typing import Any

from agentic_pymol.app import client, mcp
from agentic_pymol.types import Atom, Model


@mcp.tool()
def iterate(selection: str, properties: list[str], state: int = -1) -> list[dict[str, Any]]:
    """
    Iterate atoms in a selection and return per-atom property dicts. Coordinates
    (x, y, z) and any state-dependent attributes are available.

    `properties`: list of PyMOL atom attribute names —
        e.g. ["resi", "resn", "name", "chain", "b", "x", "y", "z"].
    `state`: PyMOL convention — -1 (default) = current state, 1..N = specific
        state. state=0 means "all states" and yields N_atoms × N_states rows;
        reach for it only when you genuinely want every frame.

    Capped at 200 000 rows. Selection identifiers must be valid Python attribute names.

    The dict shape is caller-defined via `properties`, so this tool returns
    `list[dict]` rather than a typed dataclass.
    """
    response = client.iterate(selection, properties, state, "iterate")
    return response.value


@mcp.tool()
def alter(selection: str, expression: str) -> int:
    """
    Modify atom attributes from a Python expression evaluated once per atom.
    Mirror of iterate but with assignment.

    Examples:
        alter("resi 50-60", "b=99.0")            # set B-factor
        alter("chain A", "chain='X'")            # rename chain A → X
        alter("name CA", "vdw=1.7")              # set CA radii

    Returns the number of atoms altered.
    """
    response = client.call("alter", [selection, expression], {}, "alter")
    return int(response.value)


@mcp.tool()
def get_model(selection: str = "all", state: int = 1) -> Model:
    """
    Structured snapshot of atoms in a selection. For just coordinates use
    get_coords; for a caller-chosen subset of properties use iterate.
    """
    response = client.call("get_model", [selection], {"state": state}, "get_model")
    val = response.value
    atoms = [Atom(**a) for a in val["atoms"]]
    return Model(atoms=atoms, n_atoms=val["n_atoms"])


@mcp.tool()
def get_fastastr(selection: str = "all", state: int = -1) -> str:
    """Return the FASTA-formatted protein sequence(s) of a selection."""
    response = client.call("get_fastastr", [selection], {"state": state}, "get_fastastr")
    return response.value
