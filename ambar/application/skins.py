import os


class SkinService:
    """Lista las skins personalizadas cargadas por el usuario en /skins, junto
    al ejecutable (no forman parte del bundle de PyInstaller). Una skin es una
    carpeta con un style.css que se inyecta despues de los estilos por
    defecto, asi que solo necesita sobreescribir lo que quiera cambiar."""

    def __init__(self, skins_dir: str):
        self._skins_dir = skins_dir

    def list_skins(self) -> list[str]:
        if not os.path.isdir(self._skins_dir):
            return []
        return sorted(
            name for name in os.listdir(self._skins_dir)
            if os.path.isfile(os.path.join(self._skins_dir, name, "style.css"))
        )
