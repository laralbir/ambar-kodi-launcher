import os
import subprocess
import sys

def build():
    print("Construyendo el ejecutable para Ámbar Kodi Launcher...")
    sep = ';' if sys.platform == 'win32' else ':'
    
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--windowed",
        f"--add-data=index.html{sep}.",
        "--icon=ambar_icon.png",
        "kiosk_server.py"
    ]
    
    print("Ejecutando:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print("¡Construcción completada! El ejecutable se encuentra en la carpeta 'dist'.")

if __name__ == "__main__":
    build()
