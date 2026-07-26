"""Punto de entrada de Ámbar. La logica vive en el paquete ambar/
(arquitectura hexagonal: dominio -> aplicacion -> puertos -> adapters),
compuesta en ambar/bootstrap.py.
"""

import os

from ambar.bootstrap import run

if __name__ == "__main__":
    run(app_dir=os.path.dirname(os.path.abspath(__file__)))
