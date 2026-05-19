# pyright: reportMissingImports=false
"""
TCP socket server that accepts framed JSON requests and dispatches them.
Runs on a background daemon thread; each connection gets its own worker thread,
so a fresh connection (e.g. `op="interrupt"`) is served concurrently with any
in-flight request.
"""

from __future__ import annotations
import logging
import socket
import threading
import traceback

from pymol_plugin.auth import get_token
from pymol_plugin.framing import recv_message, send_message
from pymol_plugin.handlers import dispatch

DEFAULT_PORT = 9876

logger = logging.getLogger("pymol-mcp-plugin")


class SocketServer:
    def __init__(self, host: str = "127.0.0.1", port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self.socket: socket.socket | None = None
        self.running = False
        self.thread: threading.Thread | None = None

    def start(self) -> bool:
        if self.running:
            return False
        get_token()
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        return True

    def stop(self) -> None:
        self.running = False
        if self.thread:
            self.thread.join(2.0)
        if self.socket:
            try:
                self.socket.close()
            except OSError:
                pass
        self.socket = None
        self.thread = None

    def _run(self) -> None:
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(4)
            self.socket.settimeout(0.1)
            logger.info(f"PyMOL MCP socket server listening on {self.host}:{self.port}")
            while self.running:
                try:
                    client, address = self.socket.accept()
                except TimeoutError:
                    continue
                except OSError as e:
                    logger.info(f"accept error: {e}")
                    break
                logger.info(f"PyMOL MCP client connected: {address}")
                threading.Thread(target=self._serve_client, args=(client,), daemon=True).start()
        except Exception as e:
            logger.info(f"PyMOL MCP socket server error: {e}")
            traceback.print_exc()
        finally:
            if self.socket:
                try:
                    self.socket.close()
                except OSError:
                    pass
            logger.info("PyMOL MCP socket server stopped")

    def _serve_client(self, client: socket.socket) -> None:
        client.settimeout(None)
        try:
            while self.running:
                request = recv_message(client)
                response = dispatch(request)
                send_message(client, response)
        except (ConnectionError, OSError) as e:
            logger.info(f"PyMOL MCP client disconnected: {e}")
        except Exception as e:
            logger.info(f"PyMOL MCP client handler crashed: {e}")
            traceback.print_exc()
        finally:
            try:
                client.close()
            except OSError:
                pass
