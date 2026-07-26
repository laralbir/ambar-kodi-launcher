class NullWakeLock:
    """Adapter no-op: fallback seguro cuando no hay forma de evitar la
    suspension de pantalla en esta plataforma. El resto de la app sigue
    funcionando con normalidad, sin proteccion contra el salvapantallas."""

    def acquire(self) -> None:
        pass

    def release(self) -> None:
        pass
