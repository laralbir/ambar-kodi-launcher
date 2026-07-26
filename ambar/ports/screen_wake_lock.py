from typing import Protocol


class ScreenWakeLock(Protocol):
    """Puerto que implementan los adapters que evitan que la pantalla se
    apague, salte el salvapantallas o el equipo entre en reposo mientras
    Ambar esta en ejecucion -- un kiosko se supone siempre visible."""

    def acquire(self) -> None: ...

    def release(self) -> None: ...
