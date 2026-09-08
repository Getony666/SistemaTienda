"""MiTienda con la interfaz en React, dentro de una ventana de escritorio.

Un solo programa, sin navegador a la vista y sin conexión a internet:

1. Arranca la API en 127.0.0.1, en un puerto libre, dentro de este proceso.
2. Sirve desde ahí la interfaz de React ya compilada.
3. Abre una ventana nativa de Windows con WebView2 dentro, que en Windows 10
   y 11 ya viene instalado.

Ésta es la interfaz del programa. Están los cuatro paneles: Ventas,
Historial, Cambio de Divisa y Corte de Caja.

La ventana de tkinter (`python ventas.py`) se queda en el repositorio porque
de ella cuelgan las pruebas de caracterización, que son las que garantizan
que las cuentas no cambiaron al mudarse. Ya no se trabaja ni se compila.
Las dos abren la misma base de datos.

    cd interfaz && npm install && npm run build
    cd .. && python escritorio.py
"""

import mimetypes
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request

if getattr(sys, "frozen", False):
    # Empaquetado: la interfaz viaja dentro del ejecutable y PyInstaller la
    # descomprime en una carpeta temporal. La base de datos NO va ahí: la
    # busca `lddl/rutas.py` junto al .exe, que es donde debe estar.
    RAIZ = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
else:
    RAIZ = os.path.dirname(os.path.abspath(__file__))

DIST = os.path.join(RAIZ, "interfaz", "dist")

# Windows guarda los tipos MIME en el registro, y en muchas máquinas .js está
# apuntado a "text/plain". Python lee de ahí, así que el navegador rechazaba el
# módulo de React -"Expected a JavaScript module, got text/plain"- y la ventana
# salía en blanco. Se declaran a mano antes de servir nada.
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")


def puerto_libre():
    """Un puerto que nadie esté usando, para no chocar con nada."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def esperar_a_que_responda(url, segundos=20):
    limite = time.time() + segundos
    while time.time() < limite:
        try:
            with urllib.request.urlopen(url, timeout=1):
                return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.15)
    return False


def main():
    if not os.path.isdir(DIST):
        sys.exit("Falta interfaz/dist.\n"
                 "Compila la interfaz primero:\n"
                 "    cd interfaz && npm install && npm run build")

    import uvicorn
    import webview
    from fastapi.staticfiles import StaticFiles

    from lddl import TITULO_VENTANA
    from lddl.api import app

    # Se monta al final para que las rutas de la API ganen sobre los ficheros.
    app.mount("/", StaticFiles(directory=DIST, html=True), name="interfaz")

    puerto = puerto_libre()
    servidor = uvicorn.Server(uvicorn.Config(
        app, host="127.0.0.1", port=puerto, log_level="warning"))
    threading.Thread(target=servidor.run, daemon=True).start()

    direccion = f"http://127.0.0.1:{puerto}/"
    if not esperar_a_que_responda(direccion + "salud"):
        sys.exit("La API no arrancó a tiempo.")

    webview.create_window(TITULO_VENTANA, direccion,
                          width=1360, height=860, min_size=(1024, 700))
    webview.start()

    servidor.should_exit = True


if __name__ == "__main__":
    main()
