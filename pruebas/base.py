"""La base de datos que usan las pruebas.

Las pruebas NO pueden depender de `tienda.db`, la del programa: esa se
entrega vacía a cada negocio nuevo, y con ella vacía media suite se quedaba
sin nada que comprobar y pasaba en verde sin haber probado nada.

Aquí al lado vive `tienda_de_pruebas.db`, con el catálogo y las ventas que
había cuando se congelaron los valores de referencia de
`test_equivalencia_con_la_app.py` y `test_registro_de_venta.py`. Si se
cambia, esos valores dejan de significar lo que dicen que significan.

Nadie escribe en ella: cada prueba trabaja sobre una copia en una carpeta
temporal, que se borra al terminar.
"""

import os
import shutil
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(AQUI, "tienda_de_pruebas.db")
CONFIG = os.path.join(AQUI, "config_de_pruebas.json")


def carpeta_con_copia(prefijo="mitienda-pruebas-"):
    """Carpeta temporal con una copia de la base y de la configuración.

    La copia se migra antes de devolverla, igual que hace el programa al
    abrirse: así el fichero de pruebas guarda DATOS y no tiene que ir
    persiguiendo cada columna nueva. Al migrarla hay que apuntar ahí primero,
    de modo que esta función deja ya fijado el directorio base.

    Devuelve la ruta. Quien la pida se encarga de borrarla, normalmente en
    un tearDown con `shutil.rmtree(ruta, ignore_errors=True)`.
    """
    from lddl import rutas
    from lddl.esquema import preparar_base

    temporal = tempfile.mkdtemp(prefix=prefijo)
    shutil.copy2(BASE, os.path.join(temporal, "tienda.db"))
    if os.path.exists(CONFIG):
        shutil.copy2(CONFIG, os.path.join(temporal, "config_caja.json"))

    rutas.fijar_directorio_base(temporal)
    preparar_base()
    return temporal


def empezar_modulo():
    """Apunta todo el programa a una copia, para un fichero de pruebas entero.

    Se usa desde `setUpModule`, que unittest llama antes que cualquier
    `setUpClass`. Hace falta en las pruebas que conducen la ventana de
    verdad: la ventana lee la base al construirse, así que redirigirla más
    tarde llegaría tarde.
    """
    from lddl import rutas

    carpeta = carpeta_con_copia()
    rutas.fijar_directorio_base(carpeta)
    return carpeta


def terminar_modulo(carpeta):
    """Devuelve el programa a su base normal y borra la copia."""
    from lddl import rutas

    rutas.fijar_directorio_base(None)
    shutil.rmtree(carpeta, ignore_errors=True)
