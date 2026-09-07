"""Punto de entrada de La Despensa de Leslia.

    python3 ventas.py

El código vive en el paquete lddl/ (ver lddl/__init__.py para el mapa de módulos).
"""

import ttkbootstrap as tb

from lddl.ui import VentanaVentas


def main():
    root = tb.Window(themename="flatly")
    VentanaVentas(root)
    root.mainloop()


if __name__ == "__main__":
    main()
