from __future__ import annotations


class PyMOLError(RuntimeError):
    """Raised when the plugin reports a failed call."""

    def __init__(self, error_type: str, message: str, traceback_text: str, stdout: str):
        super().__init__(f"{error_type}: {message}")
        self.error_type = error_type
        self.message = message
        self.traceback_text = traceback_text
        self.stdout = stdout
