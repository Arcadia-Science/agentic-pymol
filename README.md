# Agentic PyMOL

A lightweight Model Context Protocol (MCP) server that exposes PyMOL as a typed tool surface for general-purpose agents.

Use it with Claude Code, Claude Desktop, Codex, or any MCP-compatible client to let your agent control an open PyMOL session, inspect molecular structures, run PyMOL-native analyses, and render what it sees.

Agentic PyMOL is not an embedded chatbot and not a molecular workbench. It is a small bridge between a capable agent and the PyMOL session you already use.

## Why this exists

PyMOL is more than a visualization tool. It is also a mature structural-biology analysis environment: it knows about selections, objects, chains, states, coordinates, alignments, RMSD, distances, atom tables, scenes, views, and rendered molecular figures.

Most LLM/PyMOL integrations focus on one of two patterns:

1. put a chat interface inside PyMOL, or
2. expose PyMOL as a mostly untyped command runner.

Agentic PyMOL takes a narrower approach: expose PyMOL itself as a typed, composable tool that an external agent can use alongside everything else it already knows how to use: files, shell, git, papers, notebooks, local data, and other MCP servers.

The key difference is two-way communication. The agent can take action in your live PyMOL session -- fetch structures, change representations, make selections, align objects, render figures -- and it can also read structured information back out of that same session: loaded objects, chains, atom counts, coordinates, distances, RMSDs, views, sequences, and errors. That makes PyMOL usable not only as something the agent drives, but as something the agent can inspect, reason over, summarize for the user, and pass into downstream work.

This keeps the project deliberately small. Agentic PyMOL does not bundle docking, conservation analysis, sequence search, structure prediction, or external biology APIs. Those are valuable workflows that belong elsewhere. This server focuses on giving agents reliable two-way access to PyMOL-native capabilities.

## What you can do

Ask your agent to use PyMOL directly:

```text
Fetch ubiquitin, show it as cartoon, color by secondary structure, and render a PNG.
```

```text
Create a table of residues that are in contact with DNA in the DNA-binding protein 6EDC.
```

```text
Load these two structures, align chain A, report the RMSD, and show the regions that moved the most.
```

```text
Which of these 10 binders trigger a conformational shift in the target activation loop?
```

Because the tool surface is typed, agents can reason over results instead of merely seeing that a command succeeded. Distances, RMSDs, object lists, atom counts, coordinates, and views come back as data.

## Design goals

- **Use the PyMOL you already have.** Works with your existing PyMOL installation; PyMOL 2.6+ is supported.
- **No insular chatbot.** PyMOL is exposed to your general-purpose agent rather than wrapping PyMOL in its own chat interface.
- **Two-way communication.** The agent can manipulate the live PyMOL session and read structured information back out for reasoning, answers, and downstream work.
- **Typed over textual.** Return objects, chains, coordinates, distances, RMSDs, views, sequences, and errors as data -- not just “succeeded.”
- **PyMOL-native first.** Stay focused on visualization, selection logic, geometry, alignments, rendering, and session inspection.
- **Lightweight and composable.** Do not bundle docking, sequence search, conservation analysis, prediction services, or external biology APIs; let other tools handle those jobs.

## Install

Requires:

* PyMOL 2.6+
* [uv](https://docs.astral.sh/uv/)
* an MCP client, such as Claude Code or Claude Desktop

### 1. Clone and sync

```bash
git clone https://github.com/Arcadia-Science/agentic-pymol.git
cd agentic-pymol
uv sync
```

`uv sync` installs the `agentic-pymol` console script into `.venv/bin/agentic-pymol`.

### 2. Install the PyMOL plugin

In PyMOL:

1. Open **Plugin → Plugin Manager → Install New Plugin → Choose file…**
2. Select `pymol_plugin/__init__.py` from this repo.
3. Open **Plugin → agentic-pymol plugin → Start Listening**.

### 3. Register the MCP server

For Claude Code:

```bash
claude mcp add --scope user pymol /absolute/path/to/agentic-pymol/.venv/bin/agentic-pymol
```

For Claude Desktop, add this to `~/Library/Application Support/Claude/claude_desktop_config.json`:

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

Start a new conversation in your MCP client and ask:

```text
Use the PyMOL status tool and tell me what is currently loaded.
```

If PyMOL is running and the plugin is listening, the tool should return a structured `Status` snapshot.

Then try:

```text
Fetch ubiquitin in PyMOL and visualize it as a cartoon.
```

You should see PyMOL update live.

## Architecture

```text
Agent --> MCP (stdio) -->  agentic_pymol/server.py --> TCP/JSON --> PyMOL plugin --> cmd.* --> PyMOL
```

Agentic PyMOL has two pieces:

1. an MCP server launched by your client over stdio, and
2. a small PyMOL plugin that listens on a local TCP socket.

The MCP server is a thin bridge. It validates tool inputs, sends requests to the PyMOL plugin, and returns structured outputs to the agent.

The plugin runs inside PyMOL and dispatches requests to `pymol.cmd`.

The wire protocol between the server and plugin is length-prefixed JSON:

```text
4-byte big-endian payload length + UTF-8 JSON body
```

Messages are capped at 4 MB.

### Authentication

The plugin binds to `127.0.0.1` only and requires a shared-secret token on every request.

On first listen, the plugin auto-generates a token at:

```text
~/.config/pymol-mcp/token
```

The file is written with mode `0600`. The MCP server reads the same path by default, or you can override it with `PYMOL_MCP_TOKEN`.

### Port discovery

The plugin writes its actually-bound port to `~/.config/pymol-mcp/port` once the listening socket is up, and removes the file on shutdown. The MCP server reads that file when `PYMOL_MCP_PORT` is unset, so changing the port in the plugin's dialog doesn't require any matching change on the server side. Precedence: `PYMOL_MCP_PORT` env > `~/.config/pymol-mcp/port` > default (9877).

## Development

```bash
make test         # pytest
make typecheck    # pyright
make lint         # ruff check + ruff format --check
make format       # ruff format + ruff check --fix
make pre-commit   # run all hooks against all files
```

## Similar projects

Agentic PyMOL is not the first PyMOL/LLM integration. Agentic PyMOL is intentionally narrow: a lightweight, typed MCP bridge to the PyMOL installation you already use. These projects explore nearby ideas with different emphases.

- [`vrtejus/pymol-mcp`](https://github.com/vrtejus/pymol-mcp) - Early demonstrator of the core value of connecting PyMOL to LLM agents through MCP. Agentic PyMOL builds on that idea with typed tool outputs, structured session readback, and shared-secret authentication.
- [MCPymol](https://github.com/chemrich/MCPymol) - a PyMOL MCP server that leverages the MCP as a thin command tunnel to carry out specific visualization-oriented workflows. In comparison, Agentic PyMOL is focused on supporting a lightweight and unopinionated tool surface that returns structured data to the LLM instead of simple "command succeeded" messages.
- [`nagarh/pymol-claude-code`](https://github.com/nagarh/pymol-claude-code) - a compact Claude Code-only MCP that controls PyMOL through its XML-RPC mode (`pymol -R`) that requires launching PyMOL from the command line. This shares the goal of giving agents live access to PyMOL, but opts for just three MCP tools (`run_command`, `run_python`, `pymol_get`). In contrast, Agentic PyMOL surfaces discoverable tools with structured readback.
- [ChatMol](https://chatmol.github.io/ChatMol/) - a broader molecular-design assistant with a PyMOL plugin, PyMOL skill, Streamlit interface, Python package, and copilot-style workflows. It is closer to a molecular-agent environment than a bridge between your existing LLM agent and PyMOL. Creates an insular environment.
- [`ravishar313/PyMolAI`](https://github.com/ravishar313/PyMolAI) - an AI-oriented fork of open-source PyMOL with a Qt chat panel, internal PyMOL tools, model-provider integration, and optional OpenBio tools. Creates an insular environment.
- [`pymol-agent-bridge`](https://github.com/ANaka/pymol-agent-bridge) - an interesting MCP-less socket bridge that lets terminal-capable agents send Python/PyMOL commands to a live PyMOL session. `pymol-agent-bridge` is a CLI/library bridge.
