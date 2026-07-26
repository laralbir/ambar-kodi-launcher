import json
import os


class JsonConfigRepository:
    """Adapter de persistencia de configuracion sobre un fichero JSON en disco."""

    def __init__(self, path: str):
        self._path = path

    def load(self) -> dict:
        if os.path.exists(self._path):
            try:
                with open(self._path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save(self, data: dict) -> None:
        try:
            with open(self._path, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print("Error al guardar config:", e)
