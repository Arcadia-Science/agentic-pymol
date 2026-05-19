# pyright: reportMissingImports=false
"""Shared-secret token: load from env or file, auto-generate on first listen."""

from __future__ import annotations
import hmac
import logging
import os
import secrets
from pathlib import Path
from typing import Any

TOKEN_PATH = Path.home() / ".config" / "pymol-mcp" / "token"
TOKEN_BYTES = 32

logger = logging.getLogger("pymol-mcp-plugin")
_token: str | None = None


def _load_or_create_token() -> str:
    env = os.environ.get("PYMOL_MCP_TOKEN")
    if env:
        return env.strip()
    if TOKEN_PATH.exists():
        return TOKEN_PATH.read_text().strip()
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(TOKEN_BYTES)
    TOKEN_PATH.write_text(token)
    TOKEN_PATH.chmod(0o600)
    logger.info(f"PyMOL MCP: generated new shared-secret token at {TOKEN_PATH}")
    return token


def get_token() -> str:
    global _token
    if _token is None:
        _token = _load_or_create_token()
    return _token


def token_ok(presented: Any) -> bool:
    if not isinstance(presented, str):
        return False
    return hmac.compare_digest(presented, get_token())
