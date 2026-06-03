"""MCP server entry point.

Importing this module triggers tool registration. `main()` runs the
FastMCP server over stdio.
"""

from __future__ import annotations
import logging

import agentic_pymol.tools as tools
from agentic_pymol.app import mcp

__all__ = ["tools"]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    mcp.run()


if __name__ == "__main__":
    main()
