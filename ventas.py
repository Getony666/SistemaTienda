"""Punto de entrada de La Despensa de Leslia.

    python3 ventas.py

El código vive en el paquete lddl/ (ver lddl/__init__.py para el mapa de módulos).
"""

import tkinter as tk

from lddl.ui import VentanaVentas


def main():
    root = tk.Tk()
    VentanaVentas(root)
    root.mainloop()


if __name__ == "__main__":
    main()
