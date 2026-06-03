from __future__ import annotations
import tempfile
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import Image

from agentic_pymol.app import client, mcp, surface_pymol_error


@mcp.tool()
@surface_pymol_error
def fetch(code: str, name: str = "", type: str = "cif", path: str = "") -> str:
    """
    Fetch a structure from RCSB and load it. Synchronous (async_=0).

    `code`: PDB code, or space-separated codes to fetch several at once.
    `name`: optional object name (defaults to `code`).
    `type`: file type — "cif" (default), "pdb", "pdb1", "2fofc", "fofc", "mmtf".
    `path`: download cache directory; empty string uses PyMOL default.

    Returns the loaded object name(s).
    """
    kwargs: dict[str, Any] = {"async_": 0, "type": type}
    if name:
        kwargs["name"] = name
    if path:
        kwargs["path"] = str(Path(path).expanduser())
    client.call("fetch", [code], kwargs, "fetch")
    return name or code


@mcp.tool()
@surface_pymol_error
def load(filename: str, object_name: str = "", state: int = 0, format: str = "") -> str:
    """
    Load a local structure file (PDB, CIF, MOL2, SDF, MAE, ...).

    `filename`: path to the file (absolute or relative to PyMOL's cwd).
    `object_name`: defaults to the filename stem.
    `state`: 0 appends as new state, 1+ overwrites that state.
    `format`: empty string lets PyMOL detect from extension.

    Returns the object name actually used.
    """
    resolved = Path(filename).expanduser().resolve()
    derived_name = object_name or resolved.stem
    kwargs: dict[str, Any] = {"object": derived_name, "state": state}
    if format:
        kwargs["format"] = format
    client.call("load", [str(resolved)], kwargs, "load")
    return derived_name


@mcp.tool()
@surface_pymol_error
def save(filename: str, selection: str = "all", state: int = -1, format: str = "") -> str:
    """
    Save a selection to disk. Format is detected from the extension if not given.

    `state`: -1 saves the current state, 0 saves all states (multi-model PDB / multi-frame CIF).

    Returns the absolute path written.
    """
    resolved = Path(filename).expanduser().resolve()
    kwargs: dict[str, Any] = {"selection": selection, "state": state}
    if format:
        kwargs["format"] = format
    client.call("save", [str(resolved)], kwargs, "save")
    return str(resolved)


@mcp.tool()
@surface_pymol_error
def render(
    filename: str, width: int = 1024, height: int = 768, dpi: float = -1.0, ray: bool = True
) -> str:
    """
    Render the current view to a PNG.

    `ray=True` (default) uses ray tracing — slower but high quality.
    `width`/`height` in pixels. `dpi=-1.0` keeps PyMOL's current setting.

    Returns the absolute path written.
    """
    resolved = Path(filename).expanduser().resolve()
    kwargs = {"width": width, "height": height, "dpi": dpi, "ray": 1 if ray else 0}
    client.call("png", [str(resolved)], kwargs, "render")
    return str(resolved)


@mcp.tool()
@surface_pymol_error
def screenshot(width: int = 800, height: int = 600, ray: bool = False) -> Image:
    """
    Capture the current PyMOL viewport and return the PNG inline so the model
    can see the result of preceding commands.

    `ray=False` (default) takes an instant viewport snapshot — what's drawn in
    the GL window right now. `ray=True` does a slow ray-traced render. For
    visual feedback during a multi-step workflow, leave `ray=False`.

    Use after applying display changes (`do("show cartoon, ...")`, alignments,
    etc.) to verify the result. For producing artifacts on disk use `render`
    instead.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.close()
    tmp_path = Path(tmp.name)
    try:
        kwargs = {"width": width, "height": height, "ray": 1 if ray else 0}
        client.call("png", [str(tmp_path)], kwargs, "screenshot")
        data = tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)
    return Image(data=data, format="png")
