from __future__ import annotations

from agentic_pymol.app import client, mcp
from agentic_pymol.types import RunResult, Status


@mcp.tool()
def status() -> Status:
    """
    Return a snapshot of the PyMOL session.

    Useful as a connectivity probe: if this succeeds, the plugin is reachable.
    """
    objects = client.call("get_object_list", ["all"], {}, "status").value
    selections = client.call("get_names", ["selections"], {}, "status").value
    frame = client.call("get_frame", [], {}, "status").value
    state = client.call("get_state", [], {}, "status").value
    return Status(objects=objects, selections=selections, frame=frame, state=state)


@mcp.tool()
def do(command: str) -> str:
    """
    ESCAPE HATCH — use only when no dedicated tool covers the operation.

    Runs a PyMOL command-line string verbatim through `cmd.do(...)`. The return
    is unstructured stdout text, so you lose the typed results the dedicated
    tools provide. Prefer any dedicated tool over `do` whenever one fits; reach
    for `do` only for PyMOL CLI operations with no first-class tool.
    Multi-statement strings separated by `;` are fine.

    Caveat: `cmd.do` does NOT raise on PyMOL errors — failures come back as
    text in the returned string, so inspect the output.
    """
    response = client.call("do", [command], {}, "do")
    return response.stdout


@mcp.tool()
def run(code: str, return_expr: str = "") -> RunResult:
    """
    ESCAPE HATCH OF LAST RESORT — use only when neither a dedicated tool nor
    `do` will work.

    Executes arbitrary Python in the PyMOL plugin's namespace. `cmd`, `pymol`,
    and (if available) `np` are pre-imported. If `return_expr` is non-empty,
    the plugin evaluates it after `exec` and returns its value serialized.
    Stdout and the optional return value come back unstructured.

    Fallback order: prefer a dedicated tool, then `do` for PyMOL CLI commands,
    then `run`. `run` is appropriate only when you need Python control flow,
    numpy operations, or PyMOL API surface not exposed via the CLI or other
    tools.

    Security: this is an unsandboxed Python `exec` inside the PyMOL process.
    Anything Python can do — open files, make network calls, import modules,
    shell out — is in scope. The only thing standing between this tool and
    full remote code execution on the host is the shared-secret auth token
    (`~/.config/pymol-mcp/token` or `PYMOL_MCP_TOKEN`). Treat that token like
    an SSH key: don't share it, don't commit it, and don't expose the plugin's
    TCP port beyond localhost.
    """
    return_expr_arg = return_expr if return_expr else None
    response = client.exec_code(code, return_expr_arg, "run")
    return RunResult(stdout=response.stdout, value=response.value)
