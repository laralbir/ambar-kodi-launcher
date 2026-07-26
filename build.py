import os
import subprocess
import sys

def read_version():
    version_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION")
    with open(version_file) as f:
        return f.read().strip()

def build():
    version = read_version()
    print(f"Construyendo el ejecutable para Ámbar Kodi Launcher v{version}...")
    sep = ';' if sys.platform == 'win32' else ':'

    if os.path.exists("kiosk_server.spec"):
        os.remove("kiosk_server.spec")

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
        "kiosk_server.py"
    ]

    print("Ejecutando:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print("¡Construcción completada! El ejecutable se encuentra en la carpeta 'dist'.")

if __name__ == "__main__":
    build()
