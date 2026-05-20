# agentic-pymol

A Model Context Protocol server that gives PyMOL to language-model agents (Claude Code, Claude Desktop, or any MCP-compatible client) as a typed tool surface, with shared-secret auth and timeout-triggered cancellation.

## Architecture

```
Agent  ── MCP (stdio) ──>  agentic_pymol/server.py  ── TCP/JSON ──>  PyMOL plugin  ── cmd.* ──>  PyMOL
```

The MCP server is a thin bridge to a small companion plugin running inside PyMOL. The wire is length-prefixed JSON: a 4-byte big-endian payload length followed by a UTF-8 JSON body, capped at 4 MB per message. The plugin binds 127.0.0.1 only and requires a shared-secret token on every request.

## Features

- **Shared-secret auth.** The plugin auto-generates a token at `~/.config/pymol-mcp/token` (mode 0600) the first time it starts listening. The MCP server reads from the same path (or `PYMOL_MCP_TOKEN`). Closes the original "anything on localhost can `exec()` arbitrary Python in PyMOL" hole.
- **Timeout-triggered interrupt.** When a tool call exceeds its timeout, the MCP server opens a fresh side connection and fires `op="interrupt"`, which calls PyMOL's lock-free `cmd.interrupt()`. Long C-layer routines (notably ray tracing) poll PyMOL's global interrupt flag and bail out cleanly, so a runaway `ray` returns to interactive state instead of wedging the session. Pure-Python loops inside `run` won't be interrupted — that's a known limitation of this mechanism.
- **Tests.** A real test suite (auth, dispatch, interrupt) runs against the plugin in-process with a fake `pymol.cmd`.
- **uv + Make + pre-commit.** Project infrastructure for local dev.

## Tool surface

Same set as upstream, plus `do` (CLI passthrough) and `run` (Python escape hatch).

Tools register on the MCP side under the `mcp__pymol__` namespace (e.g. `mcp__pymol__status`); the table lists the bare names defined in `agentic_pymol/tools/`.

| Group | Tools |
|---|---|
| Session / escape hatches | `status`, `do`, `run` |
| Loading / saving | `fetch`, `load`, `save`, `render` |
| Visual feedback | `screenshot` (returns the PNG inline) |
| Alignment & RMSD | `align`, `cealign`, `rms` |
| Introspection | `get_object_list`, `get_names`, `get_chains`, `count_atoms`, `count_states` |
| Geometry | `get_distance`, `get_extent`, `get_coords`, `get_view`, `set_view` |
| Atom-level data | `iterate`, `alter`, `get_model`, `get_fastastr` |

Tool failures surface as `PyMOLError` (`error_type`, `message`, original PyMOL traceback). New error type: `TransportTimeout`, raised by the MCP server when a call exceeds its timeout — the interrupt has already been fired by the time the model sees the error.

## Install

### Prerequisites

- PyMOL 2.6+
- [uv](https://docs.astral.sh/uv/) (project uses uv for env + deps)
- An MCP client (Claude Code, Claude Desktop, etc.)

### 1. Clone and sync

```bash
git clone <this repo>
cd agentic-pymol
uv sync
```

`uv sync` installs the `agentic-pymol` console script into `.venv/bin/agentic-pymol`, which is the MCP server entry point.

### 2. Install the PyMOL plugin

1. Open PyMOL → Plugin → Plugin Manager → Install New Plugin → Choose file...
2. Select `pymol_plugin/__init__.py` from the cloned repo.
3. Plugin → agentic-pymol plugin → **Start Listening**. Status turns green; on first run the plugin prints the path of the freshly generated token file.

### 3. Register the MCP server with your client

For **Claude Code**:

```bash
claude mcp add pymol /absolute/path/to/agentic-pymol/.venv/bin/agentic-pymol
```

For **Claude Desktop**, edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "pymol": {
      "command": "/absolute/path/to/agentic-pymol/.venv/bin/agentic-pymol"
    }
  }
}
```

### 4. Verify

In your MCP client, ask the model to run the `status` tool. It should return a `Status` snapshot (objects, selections, frame, state). If it fails, see Troubleshooting.

## Configuration

| Env var | Default | Meaning |
|---|---|---|
| `PYMOL_MCP_HOST` | `127.0.0.1` | Plugin socket host |
| `PYMOL_MCP_PORT` | `9877` | Plugin socket port |
| `PYMOL_MCP_TIMEOUT` | `60.0` | Per-call timeout (seconds). On expiry, an interrupt is fired and `TransportTimeout` is raised. |
| `PYMOL_MCP_TOKEN` | *(reads `~/.config/pymol-mcp/token`)* | Override the shared-secret token. Useful when PyMOL and the MCP server live on different machines and you copy the token explicitly. |

The `iterate` op is capped at 200 000 rows.

## Development

```bash
make test         # pytest
make typecheck    # pyright
make lint         # ruff check + ruff format --check
make format       # ruff format + ruff check --fix
make pre-commit   # run all hooks against all files
```

`uv run pre-commit install` wires the format / lint / typecheck hooks into git. Tests are not part of the commit gate; run `make test` manually before pushing.

### Test layout

```
tests/
├── conftest.py            # FakeCmd, plugin-loader fixture, ephemeral SocketServer
├── test_auth.py           # token validation
├── test_dispatch.py       # call / exec / iterate / unknown op / identifier checks
├── test_interrupt.py      # op=interrupt direct + timeout-triggered side-channel
├── test_serialization.py  # plugin-side serialize.py + framing size cap
└── test_tools.py          # tool wrappers + OkResponse.from_envelope validation
```

Tests run against the real plugin code with a `FakeCmd` injected as `pymol.cmd` (the plugin imports `pymol` lazily inside handlers, so this works without a running PyMOL).

## Troubleshooting

- **`ConnectionError: could not connect to PyMOL plugin`** — PyMOL isn't running, the plugin isn't started, or the port is wrong.
- **`AuthTokenMissing`** — `~/.config/pymol-mcp/token` doesn't exist yet. Click *Start Listening* in PyMOL once; the plugin generates it. Or set `PYMOL_MCP_TOKEN`.
- **`Unauthorized`** — token mismatch. Easiest cause: token rotated (file deleted) on one side but not the other. Stop the plugin, delete the token file, restart — both sides will pick up the new value.
- **`TransportTimeout`** — call exceeded `PYMOL_MCP_TIMEOUT`. The interrupt has already been sent; PyMOL should be back to interactive state. Bump the timeout for slow ray-traces, or simplify the call.
- **`PyMOLError: CmdException: ...`** — PyMOL rejected the call. Original error and traceback are passed through.
- **`IterateOverflow`** — narrow the selection (200 000-row cap).
- **Stale connection after restarting PyMOL** — the next tool call reconnects automatically.

## License

MIT.
