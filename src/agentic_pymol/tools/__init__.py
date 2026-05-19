"""
Importing this subpackage triggers every `@mcp.tool()` decorator below to
register against the shared FastMCP instance from `agentic_pymol.app`.
"""

from agentic_pymol.tools import align, data, io, query, session

__all__ = ["align", "data", "io", "query", "session"]
