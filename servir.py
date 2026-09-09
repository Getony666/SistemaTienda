"""Levanta la aplicación contra una COPIA de la base, para ensayar.

Nunca toca `tienda.db`: copia la base de pruebas a una carpeta temporal y
trabaja ahí. Al cerrarlo, la copia se queda en el temporal del sistema y se
puede borrar sin miedo.

    python servir.py            # puerto 8000
    python servir.py 8131       # otro puerto
"""

import mimetypes
import os
import shutil
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")

from lddl import rutas  # noqa: E402

ORIGEN = os.path.join(AQUI, "pruebas", "tienda_de_pruebas.db")
CONFIG = os.path.join(AQUI, "pruebas", "config_de_pruebas.json")

copia = tempfile.mkdtemp(prefix="mitienda-ensayo-")
shutil.copy2(ORIGEN, os.path.join(copia, "tienda.db"))
if os.path.exists(CONFIG):
    shutil.copy2(CONFIG, os.path.join(copia, "config_caja.json"))
rutas.fijar_directorio_base(copia)

import uvicorn  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from lddl.api import app  # noqa: E402

app.mount("/", StaticFiles(directory=os.path.join(AQUI, "interfaz", "dist"),
                           html=True), name="interfaz")

puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
print(f"Base de ensayo: {copia}")
print(f"http://127.0.0.1:{puerto}/")
uvicorn.run(app, host="127.0.0.1", port=puerto, log_level="warning")
