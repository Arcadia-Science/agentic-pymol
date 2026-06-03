"""
End-to-end tests for the MCP tools in `agentic_pymol.tools`.

Each test drives a tool function directly (the FastMCP decorator is a no-op at
the function level) against a real plugin server backed by `FakeCmd`. We assert
two things per tool: the value returned to the agent, and the underlying
`cmd.*` invocation recorded by `FakeCmd.calls`.
"""

from __future__ import annotations
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from .conftest import FakeCmd


@pytest.fixture
def tool_client(running_plugin: tuple[str, int], server_module: Any) -> Iterator[None]:
    """
    Point the module-level `agentic_pymol.app.client` singleton at the
    running plugin server, then restore.
    """
    host, port = running_plugin
    client = server_module.app.client
    saved = (
        client.host,
        client.port,
        client._sock,
        client._token,
        client.timeout,
    )
    if client._sock is not None:
        client._close()
    client.host = host
    client.port = port
    client._sock = None
    client._token = None
    client.timeout = 5.0
    yield
    client._close()
    (
        client.host,
        client.port,
        client._sock,
        client._token,
        client.timeout,
    ) = saved


@pytest.fixture
def tools(server_module: Any, tool_client: None) -> Any:
    from agentic_pymol import tools as tool_pkg

    return tool_pkg


def _last_call(fake: FakeCmd, name: str) -> tuple[tuple[Any, ...], dict[str, Any]]:
    matching = [(args, kwargs) for n, args, kwargs in fake.calls if n == name]
    assert matching, f"expected at least one call to {name!r}, got {[c[0] for c in fake.calls]}"
    return matching[-1]


class TestAlign:
    def test_align_method(self, tools: Any, fake_pymol: FakeCmd) -> None:
        result = tools.align.align("mob", "tgt", method="align", cycles=3, cutoff=1.8)
        assert result.rmsd_refined == 1.5
        assert result.n_atoms_refined == 100
        assert result.n_residues_aligned == 95
        args, kwargs = _last_call(fake_pymol, "align")
        assert args == ("mob", "tgt")
        assert kwargs["cycles"] == 3
        assert kwargs["cutoff"] == 1.8
        assert kwargs["transform"] == 1

    def test_super_method(self, tools: Any, fake_pymol: FakeCmd) -> None:
        result = tools.align.align("mob", "tgt", method="super", transform=False)
        assert result.rmsd_refined == 0.8
        args, kwargs = _last_call(fake_pymol, "super")
        assert args == ("mob", "tgt")
        assert kwargs["transform"] == 0

    def test_cealign(self, tools: Any, fake_pymol: FakeCmd) -> None:
        result = tools.align.cealign("mob", "tgt")
        assert result.RMSD == 2.3
        assert result.alignment_length == 75
        assert len(result.rotation_matrix) == 9
        args, _ = _last_call(fake_pymol, "cealign")
        assert args == ("tgt", "mob")

    def test_align_object_name_passed(self, tools: Any, fake_pymol: FakeCmd) -> None:
        tools.align.align("mob", "tgt", method="align", object_name="aln1")
        _, kwargs = _last_call(fake_pymol, "align")
        assert kwargs["object"] == "aln1"

    @pytest.mark.parametrize(("fit", "expected_fn"), [(True, "rms"), (False, "rms_cur")])
    def test_rms(self, tools: Any, fake_pymol: FakeCmd, fit: bool, expected_fn: str) -> None:
        result = tools.align.rms("mob", "tgt", fit=fit, matchmaker=1)
        assert isinstance(result, float)
        args, kwargs = _last_call(fake_pymol, expected_fn)
        assert args == ("mob", "tgt")
        assert kwargs == {"matchmaker": 1}


class TestData:
    def test_iterate_returns_rows(self, tools: Any, fake_pymol: FakeCmd) -> None:
        fake_pymol.iterate_rows = [
            {"resi": "1", "name": "CA"},
            {"resi": "2", "name": "CB"},
        ]
        result = tools.data.iterate("chain A", ["resi", "name"], state=-1)
        assert result == fake_pymol.iterate_rows
        args, _ = _last_call(fake_pymol, "iterate_state")
        assert args[0] == -1
        assert args[1] == "chain A"
        assert '"resi": resi' in args[2] and '"name": name' in args[2]

    def test_iterate_with_state_uses_iterate_state(self, tools: Any, fake_pymol: FakeCmd) -> None:
        fake_pymol.iterate_rows = [{"x": 1.0}]
        tools.data.iterate("all", ["x"], state=2)
        args, _ = _last_call(fake_pymol, "iterate_state")
        assert args[0] == 2

    def test_get_model_unwraps_serialized_payload(self, tools: Any, fake_pymol: FakeCmd) -> None:
        from agentic_pymol.types import Atom

        result = tools.data.get_model("chain A", state=1)
        assert result.n_atoms == 1
        assert result.atoms == [Atom(name="CA", resi="1")]
        _, kwargs = _last_call(fake_pymol, "get_model")
        assert kwargs == {"state": 1}


class TestIO:
    def test_fetch_passes_async_zero(self, tools: Any, fake_pymol: FakeCmd) -> None:
        result = tools.io.fetch("1ubq", name="ubq", type="pdb")
        assert result == "ubq"
        args, kwargs = _last_call(fake_pymol, "fetch")
        assert args == ("1ubq",)
        assert kwargs["async_"] == 0
        assert kwargs["type"] == "pdb"
        assert kwargs["name"] == "ubq"

    def test_fetch_defaults_name_to_code(self, tools: Any, fake_pymol: FakeCmd) -> None:
        result = tools.io.fetch("4hhb")
        assert result == "4hhb"

    def test_load_uses_filename_stem(self, tools: Any, fake_pymol: FakeCmd, tmp_path: Path) -> None:
        pdb = tmp_path / "structure.pdb"
        pdb.write_text("HEADER\n")
        result = tools.io.load(str(pdb))
        assert result == "structure"
        args, kwargs = _last_call(fake_pymol, "load")
        assert args == (str(pdb.resolve()),)
        assert kwargs["object"] == "structure"

    def test_save_returns_resolved_path(
        self, tools: Any, fake_pymol: FakeCmd, tmp_path: Path
    ) -> None:
        out = tmp_path / "out.pdb"
        result = tools.io.save(str(out), selection="chain A", state=0)
        assert result == str(out.resolve())
        args, kwargs = _last_call(fake_pymol, "save")
        assert args == (str(out.resolve()),)
        assert kwargs["selection"] == "chain A"
        assert kwargs["state"] == 0

    def test_render_invokes_png(self, tools: Any, fake_pymol: FakeCmd, tmp_path: Path) -> None:
        out = tmp_path / "render.png"
        result = tools.io.render(str(out), width=320, height=240, ray=False)
        assert result == str(out.resolve())
        _, kwargs = _last_call(fake_pymol, "png")
        assert kwargs["width"] == 320
        assert kwargs["height"] == 240
        assert kwargs["ray"] == 0

    def test_screenshot_returns_png_bytes(self, tools: Any, fake_pymol: FakeCmd) -> None:
        image = tools.io.screenshot(width=400, height=300, ray=False)
        assert image.data == fake_pymol.png_payload
        _, kwargs = _last_call(fake_pymol, "png")
        assert kwargs["ray"] == 0


class TestQuery:
    def test_get_extent(self, tools: Any, fake_pymol: FakeCmd) -> None:
        result = tools.query.get_extent("all")
        assert result.min == [-1.0, -2.0, -3.0]
        assert result.max == [4.0, 5.0, 6.0]

    def test_get_names(self, tools: Any, fake_pymol: FakeCmd) -> None:
        result = tools.query.get_names(type="selections", enabled_only=True)
        assert result == ["sel1"]
        args, kwargs = _last_call(fake_pymol, "get_names")
        assert args == ("selections",)
        assert kwargs == {"enabled_only": 1}

    def test_set_view_validates_length(self, tools: Any, fake_pymol: FakeCmd) -> None:
        with pytest.raises(ValueError, match="must be 18 floats"):
            tools.query.set_view([0.0, 1.0])

    def test_set_view_passes_animate(self, tools: Any, fake_pymol: FakeCmd) -> None:
        view = [float(i) for i in range(18)]
        tools.query.set_view(view, animate=0.5)
        args, kwargs = _last_call(fake_pymol, "set_view")
        assert args == (view,)
        assert kwargs == {"animate": 0.5}

    def test_get_coords_handles_none(self, tools: Any, fake_pymol: FakeCmd) -> None:
        fake_pymol.get_coords_return = None
        assert tools.query.get_coords("empty") == []

    def test_get_coords_unwraps_ndarray_envelope(self, tools: Any, fake_pymol: FakeCmd) -> None:
        fake_pymol.get_coords_return = {  # type: ignore
            "_kind": "ndarray",
            "shape": [2, 3],
            "dtype": "float32",
            "data": [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]],
        }
        result = tools.query.get_coords("chain A")
        assert result == [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]


class TestSession:
    def test_status_aggregates_state(self, tools: Any, fake_pymol: FakeCmd) -> None:
        from agentic_pymol.types import Status

        result = tools.session.status()
        assert result == Status(
            objects=["obj1", "obj2"],
            selections=["sel1"],
            frame=7,
            state=3,
        )

    def test_do_returns_stdout(self, tools: Any, fake_pymol: FakeCmd) -> None:
        result = tools.session.do("show cartoon")
        assert "did: show cartoon" in result
        args, _ = _last_call(fake_pymol, "do")
        assert args == ("show cartoon",)

    def test_run_executes_code_and_returns_value(self, tools: Any, fake_pymol: FakeCmd) -> None:
        result = tools.session.run("x = cmd.echo(11)", return_expr="x")
        assert result.value == 11
        assert fake_pymol.echo_calls == [11]

    def test_run_without_return_expr_is_none(self, tools: Any, fake_pymol: FakeCmd) -> None:
        result = tools.session.run("cmd.echo(99)")
        assert result.value is None
        assert fake_pymol.echo_calls == [99]


class TestSurfacePyMOLError:
    """The `surface_pymol_error` decorator must fold the plugin's captured
    stdout and traceback into the `ToolError` message, since FastMCP only
    surfaces `str(exception)` to the agent.
    """

    def test_surfaces_type_message_stdout_and_traceback(self) -> None:
        from mcp.server.fastmcp.exceptions import ToolError

        from agentic_pymol.app import surface_pymol_error
        from agentic_pymol.errors import PyMOLError

        @surface_pymol_error
        def boom() -> None:
            raise PyMOLError(
                "KeyError",
                "'missing'",
                (
                    "Traceback (most recent call last):\n"
                    '  File "x.py", line 3, in boom\n'
                    '    x["missing"]'
                ),
                "step 1 done\nstep 2 done",
            )

        with pytest.raises(ToolError) as excinfo:
            boom()
        message = str(excinfo.value)
        assert "KeyError: 'missing'" in message
        assert "--- stdout ---" in message
        assert "step 1 done" in message
        assert "step 2 done" in message
        assert "--- traceback ---" in message
        assert "in boom" in message
        assert isinstance(excinfo.value.__cause__, PyMOLError)

    def test_omits_empty_stdout_and_traceback_sections(self) -> None:
        from mcp.server.fastmcp.exceptions import ToolError

        from agentic_pymol.app import surface_pymol_error
        from agentic_pymol.errors import PyMOLError

        @surface_pymol_error
        def boom() -> None:
            raise PyMOLError("CmdException", "Selection name invalid", "", "")

        with pytest.raises(ToolError) as excinfo:
            boom()
        message = str(excinfo.value)
        assert message == "CmdException: Selection name invalid"

    def test_non_pymol_errors_pass_through_unchanged(self) -> None:
        from agentic_pymol.app import surface_pymol_error

        @surface_pymol_error
        def boom() -> None:
            raise ValueError("not a PyMOL error")

        with pytest.raises(ValueError, match="not a PyMOL error"):
            boom()

    def test_signature_preserved_for_fastmcp_introspection(self) -> None:
        """FastMCP calls `inspect.signature(func, eval_str=True)` (default
        `follow_wrapped=True`) to build the tool's input schema. The
        decorator must keep that signature accessible — `@functools.wraps`
        sets `__wrapped__`, which `inspect.signature` follows automatically.
        """
        import inspect

        from agentic_pymol.app import surface_pymol_error

        @surface_pymol_error
        def example(a: int, b: str = "default") -> bool:  # noqa: ARG001
            return True

        sig = inspect.signature(example, eval_str=True)
        params = list(sig.parameters.values())
        assert [p.name for p in params] == ["a", "b"]
        assert params[0].annotation is int
        assert params[1].annotation is str
        assert params[1].default == "default"
        assert sig.return_annotation is bool

    def test_decoration_applied_to_every_registered_tool(self, server_module: Any) -> None:
        """Guard against forgetting `@surface_pymol_error` on a future tool.

        Every public tool function across the five tool modules must be wrapped
        by the decorator. The wrapped function exposes `__wrapped__` (via
        `functools.wraps`), so the check is just: `__wrapped__` exists and the
        outer `__qualname__` is `inner` (the wrapper inside
        `surface_pymol_error`).
        """
        from agentic_pymol.tools import align, data, io, query, session

        tool_modules = [align, data, io, query, session]
        offenders: list[str] = []
        for module in tool_modules:
            for name in dir(module):
                fn = getattr(module, name)
                if not callable(fn) or name.startswith("_") or not hasattr(fn, "__module__"):
                    continue
                if fn.__module__ != module.__name__:
                    continue
                if not hasattr(fn, "__wrapped__"):
                    offenders.append(f"{module.__name__}.{name} is missing @surface_pymol_error")
        assert not offenders, "\n".join(offenders)


class TestEnvelopeValidation:
    """`OkResponse.from_envelope` must reject malformed plugin responses with PyMOLError."""

    def test_missing_ok_field_raises(self, server_module: Any) -> None:
        from agentic_pymol.responses import OkResponse

        with pytest.raises(server_module.PyMOLError) as excinfo:
            OkResponse.from_envelope({"value": 1, "stdout": ""})
        assert excinfo.value.error_type == "MalformedResponse"

    def test_failed_response_without_error_object_raises(self, server_module: Any) -> None:
        from agentic_pymol.responses import OkResponse

        with pytest.raises(server_module.PyMOLError) as excinfo:
            OkResponse.from_envelope({"ok": False, "stdout": ""})
        assert excinfo.value.error_type == "MalformedResponse"

    def test_ok_response_without_value_raises(self, server_module: Any) -> None:
        from agentic_pymol.responses import OkResponse

        with pytest.raises(server_module.PyMOLError) as excinfo:
            OkResponse.from_envelope({"ok": True, "stdout": ""})
        assert excinfo.value.error_type == "MalformedResponse"

    def test_failed_response_surfaces_plugin_error(self, server_module: Any) -> None:
        from agentic_pymol.responses import OkResponse

        with pytest.raises(server_module.PyMOLError) as excinfo:
            OkResponse.from_envelope(
                {
                    "ok": False,
                    "error": {
                        "type": "BadRequest",
                        "message": "boom",
                        "traceback": "tb",
                    },
                    "stdout": "out",
                }
            )
        assert excinfo.value.error_type == "BadRequest"
        assert excinfo.value.message == "boom"
        assert excinfo.value.traceback_text == "tb"
        assert excinfo.value.stdout == "out"

    def test_ok_envelope_parsed(self, server_module: Any) -> None:
        from agentic_pymol.responses import OkResponse

        env = OkResponse.from_envelope({"ok": True, "value": [1, 2, 3], "stdout": "hi"})
        assert env.value == [1, 2, 3]
        assert env.stdout == "hi"
