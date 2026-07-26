class WebviewWindowController:
    """Adapter hacia la ventana nativa de pywebview. Cada metodo importa
    pywebview de forma perezosa y no hace nada si no hay ventana abierta
    (p. ej. cuando se ejecuta con --no-window)."""

    def toggle_fullscreen(self) -> None:
        try:
            import webview
            if webview.windows:
                webview.windows[0].toggle_fullscreen()
        except Exception:
            pass

    def close(self) -> None:
        try:
            import webview
            if webview.windows:
                webview.windows[0].destroy()
        except Exception:
            pass
