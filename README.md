# Agentic PyMOL

A Model Context Protocol (MCP) server that exposes PyMOL as a typed tool surface to your agent (Claude Code/Desktop, Codex, or any MCP-compatible client). Practically speaking, this means that your agent (who uses PyMOL better than most scientists) can directly control your open PyMOL application and you can watch it happen live.

## Install

Requires PyMOL 2.6+, [uv](https://docs.astral.sh/uv/), and an MCP client (e.g. Claude Code).

1. Clone and sync:

   ```bash
   git clone https://github.com/Arcadia-Science/agentic-pymol.git
   cd agentic-pymol
   uv sync
   ```

2. In PyMOL: **Plugin → Plugin Manager → Install New Plugin → Choose file…** and select `pymol_plugin/__init__.py` from this repo. Then **Plugin → agentic-pymol plugin → Start Listening**.

3. Register the MCP server. For Claude Code:

   ```bash
   claude mcp add pymol /absolute/path/to/agentic-pymol/.venv/bin/agentic-pymol
   ```

   For Claude Desktop, add to `~/Library/Application Support/Claude/claude_desktop_config.json`:
   ```json
   {"mcpServers": {"pymol": {"command": "/absolute/path/to/agentic-pymol/.venv/bin/agentic-pymol"}}}
   ```

After registering the MCP server, start a new conversation and ask the agent to "fetch ubiquitin and visualize as cartoon" run the pymol `status` tool — it should return a `Status` snapshot.

## Architecture

```
Agent  ── MCP (stdio) ──>  agentic_pymol/server.py  ── TCP/JSON ──>  PyMOL plugin  ── cmd.* ──>  PyMOL
```

The MCP server is a thin bridge to a small companion plugin running inside PyMOL. The wire is length-prefixed JSON (4-byte big-endian length + UTF-8 body, capped at 4 MB). The plugin binds 127.0.0.1 only and requires a shared-secret token on every request.

**Auth.** The plugin auto-generates a token at `~/.config/pymol-mcp/token` (mode 0600) on first listen; the MCP server reads the same path (or `PYMOL_MCP_TOKEN`).

**Cancellation.** When a tool call exceeds its timeout, the MCP server opens a side connection and fires `op="interrupt"`, which calls PyMOL's lock-free `cmd.interrupt()`. Long C-layer routines (notably ray tracing) bail out cleanly. Pure-Python loops inside `run` won't be interrupted — known limitation.

## Tool surface

Tools register under the `mcp__pymol__` namespace (e.g. `mcp__pymol__status`).

Failures surface as `PyMOLError` with `error_type`, `message`, and the original PyMOL traceback. `TransportTimeout` is raised when a call exceeds its timeout (interrupt already fired).

## Configuration

| Env var | Default | Meaning |
|---|---|---|
| `PYMOL_MCP_HOST` | `127.0.0.1` | Plugin socket host |
| `PYMOL_MCP_PORT` | `9877` | Plugin socket port |
| `PYMOL_MCP_TIMEOUT` | `60.0` | Per-call timeout (seconds) |
| `PYMOL_MCP_TOKEN` | reads `~/.config/pymol-mcp/token` | Override shared-secret token (useful when PyMOL and MCP server are on different machines) |

The `iterate` op is capped at 200 000 rows.

## Development

```bash
make test         # pytest
make typecheck    # pyright
make lint         # ruff check + ruff format --check
make format       # ruff format + ruff check --fix
make pre-commit   # run all hooks against all files
```
