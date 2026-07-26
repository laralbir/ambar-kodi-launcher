import subprocess


class MacVolumeController:
    """Control del volumen maestro de salida en macOS via `osascript`
    (AppleScript `get/set volume`) -- sin dependencias nativas adicionales,
    igual de simple que pedirle el volumen al propio Ajustes del Sistema."""

    def get(self) -> dict:
        try:
            out = subprocess.run(
                ["osascript", "-e", "get volume settings"],
                capture_output=True, text=True, timeout=2, check=True,
            ).stdout
            # Formato: "output volume:50, input volume:75, alert volume:100,
            # output muted:false"
            parts = dict(p.strip().split(":") for p in out.strip().split(","))
            return {
                "level": int(parts.get("output volume", 0)),
                "muted": parts.get("output muted", "false") == "true",
            }
        except Exception:
            return {"level": 0, "muted": False}

    def set_level(self, level: int) -> None:
        level = max(0, min(100, int(level)))
        try:
            subprocess.run(
                ["osascript", "-e", f"set volume output volume {level}"],
                capture_output=True, timeout=2,
            )
        except Exception:
            pass

    def set_muted(self, muted: bool) -> None:
        try:
            subprocess.run(
                ["osascript", "-e", f"set volume output muted {'true' if muted else 'false'}"],
                capture_output=True, timeout=2,
            )
        except Exception:
            pass
