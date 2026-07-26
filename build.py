import os
import subprocess
import sys

def build():
    print("Construyendo el ejecutable para Ámbar Kodi Launcher...")
    # Separador para add-data depende del SO: ';' en Windows, ':' en Unix
    sep = ';' if sys.platform == 'win32' else ':'
    
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--windowed",       # No muestra la consola
        f"--add-data=index.html{sep}.",
        "kiosk_server.py"
    ]
    
    print("Ejecutando:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print("¡Construcción completada! El ejecutable se encuentra en la carpeta 'dist'.")

if __name__ == "__main__":
    build()
