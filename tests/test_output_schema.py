"""Check advertised output schemas against registered MCP calls."""

from __future__ import annotations
import asyncio
from dataclasses import fields
from typing import Any

import pytest

from .test_tools import tool_client as tool_client
from .test_tools import tools as tools


@pytest.mark.parametrize(
    ("name", "result_type"),
    [
        ("align", "AlignResult"),
        ("cealign", "CEAlignResult"),
        ("get_model", "Model"),
        ("get_extent", "Extent"),
        ("status", "Status"),
        ("run", "RunResult"),
    ],
)
def test_required_output_fields(tools: Any, name: str, result_type: str) -> None:
    from agentic_pymol import types
    from agentic_pymol.app import mcp

    registered = {tool.name: tool for tool in asyncio.run(mcp.list_tools())}
    schema = registered[name].outputSchema
    assert schema is not None, f"{name} has no output schema"
    expected = {field.name for field in fields(getattr(types, result_type))}
    assert set(schema["required"]) == expected
    assert set(schema["properties"]) == expected
    if name == "get_model":
        atom_schema = schema["$defs"]["Atom"]
        assert set(atom_schema["properties"]) == {field.name for field in fields(types.Atom)}
        assert atom_schema.get("required", []) == []


@pytest.mark.parametrize(
    ("name", "arguments", "field", "expected"),
    [
        ("align", {"mobile": "mob", "target": "tgt"}, "rmsd_refined", 1.5),
        ("cealign", {"mobile": "mob", "target": "tgt"}, "RMSD", 2.3),
        ("get_model", {}, "n_atoms", 1),
        ("get_extent", {}, "min", [-1.0, -2.0, -3.0]),
        ("status", {}, "objects", ["obj1", "obj2"]),
        ("run", {"code": "x = 42", "return_expr": "x"}, "value", 42),
    ],
)
def test_structured_tool_results(
    tools: Any, name: str, arguments: dict[str, Any], field: str, expected: Any
) -> None:
    from agentic_pymol.app import mcp

    result = asyncio.run(mcp.call_tool(name, arguments))
    assert isinstance(result, tuple), f"{name} returned only unstructured content"
    structured = result[1]
    assert isinstance(structured, dict)
    assert structured[field] == expected
    if name == "get_model":
        assert structured["atoms"][0]["name"] == "CA"
        # The transport fixture omits coordinates; Atom defaults them to None.
        assert structured["atoms"][0]["coord"] is None
