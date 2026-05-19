from __future__ import annotations
import os
from pathlib import Path

from agentic_pymol.errors import PyMOLError

TOKEN_PATH = Path.home() / ".config" / "pymol-mcp" / "token"


def load_token() -> str:
    env = os.environ.get("PYMOL_MCP_TOKEN")
    if env:
        return env.strip()
    if not TOKEN_PATH.exists():
        raise PyMOLError(
            "AuthTokenMissing",
            f"shared-secret token not found at {TOKEN_PATH}. Start the PyMOL plugin "
            f"first (it generates the token on first listen), or set PYMOL_MCP_TOKEN.",
            "",
            "",
        )
    return TOKEN_PATH.read_text().strip()
