import importlib.util
import os
import subprocess
import sys

def read_version():
    version_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION")
    with open(version_file) as f:
        return f.read().strip()

def check_platform_dependencies():
    """Falla pronto y con un mensaje claro si faltan dependencias especificas
    de la plataforma, en vez de compilar un .app/.exe que arranca pero le
    falta un modulo en tiempo de ejecucion (ej. el VU-metro quedando
    inactivo con 'No module named CoreMedia' por no haber reinstalado
    requirements.txt tras un pull)."""
    if sys.platform == "win32":
        required = ["soundcard"]
    elif sys.platform == "darwin":
        required = ["ScreenCaptureKit", "CoreMedia"]
    else:
        required = []

    missing = [m for m in required if importlib.util.find_spec(m) is None]
    if missing:
        print(f"ERROR: faltan dependencias en este entorno: {', '.join(missing)}")
        print("Reinstala con: pip install -r requirements.txt (dentro del venv)")
        sys.exit(1)

def build():
    version = read_version()
    print(f"Construyendo el ejecutable para Ámbar Kodi Launcher v{version}...")
    check_platform_dependencies()
    sep = ';' if sys.platform == 'win32' else ':'

    spec_file = f"Ambar-{version}.spec"
    if os.path.exists(spec_file):
        os.remove(spec_file)

    cmd = [
        "pyinstaller",
        "--clean",
        "--noconfirm",
        "--windowed",
        f"--name=Ambar-{version}",
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
    elif sys.platform == "darwin":
        cmd += [
            "--collect-all=ScreenCaptureKit",
            "--collect-all=CoreMedia",
            # Identificador de bundle ESTABLE (no depende de la version, a
            # diferencia de --name): sin esto, macOS trata cada build como
            # una app "nueva" a efectos de permisos (TCC) -- p.ej. el
            # permiso de Grabacion de pantalla del VU-metro se perderia en
            # cada version nueva. Con firma ad-hoc (sin certificado de
            # Developer ID) el permiso igualmente puede resetearse en cada
            # recompilacion aunque el identifier sea estable -- ver
            # CLAUDE.md / TODO.md para el fix completo (certificado local).
            "--osx-bundle-identifier=com.laralbir.ambar",
        ]

    cmd.append("kiosk_server.py")

    print("Ejecutando:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print("¡Construcción completada! El ejecutable se encuentra en la carpeta 'dist'.")

if __name__ == "__main__":
    build()
