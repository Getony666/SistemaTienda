"""Levanta la aplicación contra una COPIA de la base, para ensayar.

Nunca toca `tienda.db`: copia la base de pruebas a una carpeta temporal y
trabaja ahí. Al cerrarlo, la copia se queda en el temporal del sistema y se
puede borrar sin miedo.

    python servir.py              # puerto 8000, con los datos de prueba
    python servir.py 8131         # otro puerto
    python servir.py 8131 virgen  # base vacía, como una tienda estrenada
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

from mitienda import rutas  # noqa: E402

ORIGEN = os.path.join(AQUI, "pruebas", "tienda_de_pruebas.db")
CONFIG = os.path.join(AQUI, "pruebas", "config_de_pruebas.json")

puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
virgen = len(sys.argv) > 2 and sys.argv[2] == "virgen"

copia = tempfile.mkdtemp(prefix="mitienda-ensayo-")
shutil.copy2(ORIGEN, os.path.join(copia, "tienda.db"))
if os.path.exists(CONFIG):
    shutil.copy2(CONFIG, os.path.join(copia, "config_caja.json"))
rutas.fijar_directorio_base(copia)

if virgen:
    # Para ensayar el primer arranque: sin usuarios y sin datos, igual que
    # lo que se le entrega a un negocio nuevo.
    import sqlite3
    con = sqlite3.connect(os.path.join(copia, "tienda.db"))
    for (tabla,) in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        if not tabla.startswith("sqlite_"):
            con.execute(f'DELETE FROM "{tabla}"')
    con.commit()
    con.close()

import uvicorn  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from mitienda.api import app  # noqa: E402

app.mount("/", StaticFiles(directory=os.path.join(AQUI, "interfaz", "dist"),
                           html=True), name="interfaz")

print(f"Base de ensayo: {copia}{'  (VIRGEN)' if virgen else ''}")
print(f"http://127.0.0.1:{puerto}/")
uvicorn.run(app, host="127.0.0.1", port=puerto, log_level="warning")
