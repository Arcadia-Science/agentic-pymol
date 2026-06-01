from __future__ import annotations
from typing import Any, Literal

from agentic_pymol.app import client, mcp, surface_pymol_error
from agentic_pymol.types import Extent


@mcp.tool()
@surface_pymol_error
def get_distance(atom1: str, atom2: str, state: int = -1) -> float:
    """
    Distance in Ångströms between two single-atom selections.
    """
    response = client.call("get_distance", [atom1, atom2], {"state": state}, "get_distance")
    return float(response.value)


@mcp.tool()
@surface_pymol_error
def get_extent(selection: str = "all") -> Extent:
    """
    Axis-aligned bounding box of a selection. Coordinates in Ångströms.
    """
    response = client.call("get_extent", [selection], {}, "get_extent")
    return Extent(*response.value)


@mcp.tool()
@surface_pymol_error
def get_object_list(selection: str = "(all)") -> list[str]:
    """List loaded molecular object names matching a selection."""
    response = client.call("get_object_list", [selection], {}, "get_object_list")
    return response.value


@mcp.tool()
@surface_pymol_error
def get_names(
    type: Literal[
        "objects",
        "selections",
        "all",
        "public_objects",
        "public_selections",
        "public_nongroup_objects",
        "public_objects_all_states",
    ] = "objects",
    enabled_only: bool = False,
) -> list[str]:
    """
    List names by category. Use `objects` for molecular objects, `selections` for
    user-defined selections, `all` for both. `enabled_only=True` filters to visible
    items.
    """
    kwargs: dict[str, Any] = {"enabled_only": 1 if enabled_only else 0}
    response = client.call("get_names", [type], kwargs, "get_names")
    return response.value


@mcp.tool()
@surface_pymol_error
def get_chains(selection: str = "all") -> list[str]:
    """Return chain identifiers present in a selection."""
    response = client.call("get_chains", [selection], {}, "get_chains")
    return response.value


@mcp.tool()
@surface_pymol_error
def count_atoms(selection: str = "all", state: int = -1) -> int:
    """Count atoms matching a selection. `state=-1` uses the current state."""
    response = client.call("count_atoms", [selection], {"state": state}, "count_atoms")
    return int(response.value)


@mcp.tool()
@surface_pymol_error
def count_states(selection: str = "all") -> int:
    """Number of states (frames / NMR models / MD frames) for an object."""
    response = client.call("count_states", [selection], {}, "count_states")
    return int(response.value)


@mcp.tool()
@surface_pymol_error
def get_view() -> list[float]:
    """
    Return the 18-float view matrix: 9 (rotation) + 3 (camera position) + 3
    (frame origin) + 3 (clipping/orthoscopic). Pair with set_view to
    reproduce a framing.
    """
    response = client.call("get_view", [], {}, "get_view")
    return response.value


@mcp.tool()
@surface_pymol_error
def set_view(view: list[float], animate: float = 0.0) -> None:
    """
    Restore a view matrix returned by get_view. `animate>0` interpolates
    over that many seconds.
    """
    if len(view) != 18:
        raise ValueError(f"view must be 18 floats, got {len(view)}")
    client.call("set_view", [list(view)], {"animate": animate}, "set_view")


@mcp.tool()
@surface_pymol_error
def get_coords(selection: str = "all", state: int = 1) -> list[list[float]]:
    """
    Return Nx3 atom coordinates as a list of [x, y, z]. Returns [] for an
    empty selection — PyMOL's `cmd.get_coords` returns None in that case.
    """
    response = client.call("get_coords", [selection], {"state": state}, "get_coords")
    val = response.value
    if val is None:
        return []
    if isinstance(val, dict):
        return val["data"]
    return val
