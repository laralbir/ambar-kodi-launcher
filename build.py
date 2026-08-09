import importlib.util
import os
import shutil
import subprocess
import sys

APP_NAME = "Ambar"

# Datos de usuario que vive junto al ejecutable en tiempo de ejecucion (ver
# ambar/bootstrap.py:_get_data_dir), NO generados por PyInstaller. En
# Windows esa carpeta es la misma que --clean borra y recrea entera en cada
# build (dist/Ambar/), asi que sin este backup/restore un `python build.py`
# borraba silenciosamente la config de Kodi/Spotify (credenciales, CD
# autorizado) del usuario -- confirmado en vivo que se perdio asi. En macOS
# no hace falta (_get_data_dir ya usa la carpeta *contenedora* del .app,
# que PyInstaller no toca), pero preservarlo ahi tambien es inofensivo.
PRESERVE_FILES = ["config.json", ".spotify-cache", "cd_cache.json"]
PRESERVE_DIRS = ["skins"]


def _dist_dir() -> str:
    name = f"{APP_NAME}.app" if sys.platform == "darwin" else APP_NAME
    return os.path.join("dist", name)


def backup_runtime_data(backup_dir: str) -> None:
    dist_dir = _dist_dir()
    if not os.path.isdir(dist_dir):
        return
    if os.path.exists(backup_dir):
        shutil.rmtree(backup_dir)
    os.makedirs(backup_dir)
    for name in PRESERVE_FILES:
        src = os.path.join(dist_dir, name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(backup_dir, name))
    for name in PRESERVE_DIRS:
        src = os.path.join(dist_dir, name)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(backup_dir, name))


def restore_runtime_data(backup_dir: str) -> None:
    if not os.path.isdir(backup_dir):
        return
    dist_dir = _dist_dir()
    os.makedirs(dist_dir, exist_ok=True)
    for name in PRESERVE_FILES:
        src = os.path.join(backup_dir, name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(dist_dir, name))
    for name in PRESERVE_DIRS:
        src = os.path.join(backup_dir, name)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(dist_dir, name))
    shutil.rmtree(backup_dir)


def read_version():
    version_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION")
    with open(version_file) as f:
        return f.read().strip()


def version_tuple(version: str) -> tuple[int, int, int, int]:
    # El recurso de version de Windows (FixedFileInfo) es 4 enteros de 16
    # bits -- no puede representar un sufijo de pre-release semver
    # ("0.2.0-beta.1"), asi que se descarta aqui. El string completo
    # (con el sufijo) se sigue mostrando tal cual en FileVersion/
    # ProductVersion (StringStruct), solo el tuple numerico lo pierde.
    release_part = version.split("-")[0]
    parts = [int(p) for p in release_part.split(".")]
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts[:4])


def check_platform_dependencies():
    """Falla pronto y con un mensaje claro si faltan dependencias especificas
    de la plataforma, en vez de compilar un .app/.exe que arranca pero le
    falta un modulo en tiempo de ejecucion (ej. el VU-metro quedando
    inactivo con 'No module named CoreMedia' por no haber reinstalado
    requirements.txt tras un pull)."""
    if sys.platform == "win32":
        required = ["soundcard", "pycaw", "comtypes"]
    elif sys.platform == "darwin":
        required = ["ScreenCaptureKit", "CoreMedia"]
    else:
        required = []

    missing = [m for m in required if importlib.util.find_spec(m) is None]
    if missing:
        print(f"ERROR: faltan dependencias en este entorno: {', '.join(missing)}")
        print("Reinstala con: pip install -r requirements.txt (dentro del venv)")
        sys.exit(1)


def write_windows_version_file(version: str) -> str:
    """Genera el fichero de recurso de version que PyInstaller incrusta en
    el .exe (--version-file). El nombre/identidad del binario no lleva la
    version (ver APP_NAME); la version solo vive aqui, en el manifest.

    NOTA: sin verificar en Windows real en esta sesion (desarrollada en
    macOS) -- revisar al compilar en el mini PC.
    """
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo, StringFileInfo, StringTable, StringStruct,
        VarFileInfo, VarStruct, VSVersionInfo,
    )

    vtuple = version_tuple(version)
    info = VSVersionInfo(
        ffi=FixedFileInfo(
            filevers=vtuple,
            prodvers=vtuple,
            mask=0x3F,
            flags=0x0,
            OS=0x40004,
            fileType=0x1,
            subtype=0x0,
            date=(0, 0),
        ),
        kids=[
            StringFileInfo([
                StringTable("040904B0", [
                    StringStruct("CompanyName", "laralbir"),
                    StringStruct("FileDescription", "Ámbar — launcher HiFi"),
                    StringStruct("FileVersion", version),
                    StringStruct("InternalName", APP_NAME),
                    StringStruct("OriginalFilename", f"{APP_NAME}.exe"),
                    StringStruct("ProductName", "Ámbar"),
                    StringStruct("ProductVersion", version),
                ]),
            ]),
            VarFileInfo([VarStruct("Translation", [1033, 1200])]),
        ],
    )
    version_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_version_info.txt")
    with open(version_file, "w", encoding="utf-8") as f:
        f.write(str(info))
    return version_file


def set_macos_bundle_version(version: str) -> None:
    """Escribe la version en el Info.plist del .app tras compilar (PyInstaller
    no expone un flag de CLI para CFBundleShortVersionString, a diferencia
    de --version-file en Windows)."""
    plist_path = os.path.join("dist", f"{APP_NAME}.app", "Contents", "Info.plist")
    if not os.path.exists(plist_path):
        return
    for key in ("CFBundleShortVersionString", "CFBundleVersion"):
        # "Set" solo funciona si la clave ya existe en el Info.plist que
        # genera PyInstaller (CFBundleShortVersionString si, CFBundleVersion
        # no) -- si Set falla, se prueba con Add para crearla.
        result = subprocess.run(
            ["/usr/libexec/PlistBuddy", "-c", f"Set :{key} {version}", plist_path],
            capture_output=True,
        )
        if result.returncode != 0:
            subprocess.run(
                ["/usr/libexec/PlistBuddy", "-c", f"Add :{key} string {version}", plist_path],
                check=False,
            )


def build():
    version = read_version()
    print(f"Construyendo el ejecutable para Ámbar Kodi Launcher v{version}...")
    check_platform_dependencies()
    sep = ';' if sys.platform == 'win32' else ':'

    spec_file = f"{APP_NAME}.spec"
    if os.path.exists(spec_file):
        os.remove(spec_file)

    cmd = [
        "pyinstaller",
        "--clean",
        "--noconfirm",
        "--windowed",
        f"--name={APP_NAME}",
        f"--add-data=index.html{sep}.",
        "--icon=ambar_icon.png",
        "--collect-all=engineio",
        "--collect-all=socketio",
        "--hidden-import=websocket",
        "--hidden-import=spotipy",
        "--hidden-import=simple_websocket",
    ]

    if sys.platform == "win32":
        cmd.append("--hidden-import=soundcard")
        cmd.append("--hidden-import=pycaw")
        cmd.append("--hidden-import=comtypes")
        cmd.append(f"--version-file={write_windows_version_file(version)}")
    elif sys.platform == "darwin":
        cmd += [
            "--collect-all=ScreenCaptureKit",
            "--collect-all=CoreMedia",
            # Identificador de bundle ESTABLE (no depende de la version ni
            # va en --name): sin esto, macOS trata cada build como una app
            # "nueva" a efectos de permisos (TCC) -- p.ej. el permiso de
            # Grabacion de pantalla del VU-metro se perderia en cada
            # version nueva. Con firma ad-hoc (sin certificado de Developer
            # ID) el permiso igualmente puede resetearse en cada
            # recompilacion aunque el identifier sea estable -- ver
            # CLAUDE.md / TODO.md para el fix completo (certificado local).
            "--osx-bundle-identifier=com.laralbir.ambar",
        ]

    cmd.append("kiosk_server.py")

    backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_build_data_backup")
    backup_runtime_data(backup_dir)

    print("Ejecutando:", " ".join(cmd))
    subprocess.run(cmd, check=True)

    restore_runtime_data(backup_dir)

    if sys.platform == "darwin":
        set_macos_bundle_version(version)

    print(f"¡Construcción completada! El ejecutable ({APP_NAME}) se encuentra en la carpeta 'dist'.")

if __name__ == "__main__":
    build()
