"""Shared instances: the FastMCP application and the singleton PyMOLClient."""

from __future__ import annotations
import os

from mcp.server.fastmcp import FastMCP

from agentic_pymol.client import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT_SECONDS,
    PyMOLClient,
)

mcp = FastMCP("pymol")

client = PyMOLClient(
    host=os.environ.get("PYMOL_MCP_HOST", DEFAULT_HOST),
    port=int(os.environ.get("PYMOL_MCP_PORT", DEFAULT_PORT)),
    timeout=float(os.environ.get("PYMOL_MCP_TIMEOUT", DEFAULT_TIMEOUT_SECONDS)),
)
