from __future__ import annotations
import os
from pathlib import Path

from agentic_pymol.errors import PyMOLError

TOKEN_PATH = Path.home() / ".config" / "pymol-mcp" / "token"


def load_token() -> str:
    env = os.environ.get("PYMOL_MCP_TOKEN", "").strip()
    if env:
        return env
    if not TOKEN_PATH.exists():
        raise PyMOLError(
            "AuthTokenMissing",
            f"shared-secret token not found at {TOKEN_PATH}. Start the PyMOL plugin "
            f"first (it generates the token on first listen), or set PYMOL_MCP_TOKEN.",
            "",
            "",
        )
    token = TOKEN_PATH.read_text().strip()
    if not token:
        raise PyMOLError(
            "AuthTokenMissing",
            f"shared-secret token file at {TOKEN_PATH} is empty. Delete it and "
            f"restart the PyMOL plugin to regenerate, or set PYMOL_MCP_TOKEN.",
            "",
            "",
        )
    return token
