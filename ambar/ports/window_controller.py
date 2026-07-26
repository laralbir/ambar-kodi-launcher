from typing import Protocol


class WindowController(Protocol):
    """Puerto hacia la ventana nativa del kiosko (pywebview u otra shell de escritorio)."""

    def toggle_fullscreen(self) -> None: ...

    def close(self) -> None: ...
