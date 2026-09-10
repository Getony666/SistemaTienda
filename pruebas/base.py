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

import datetime
import os
import shutil
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(AQUI, "tienda_de_pruebas.db")
CONFIG = os.path.join(AQUI, "config_de_pruebas.json")

sys.path.insert(0, os.path.dirname(AQUI))

# ------------------------------------------------------------------ licencia
#
# Desde que existe el sistema de licencias, la API comprueba una al arrancar.
# Sin esto, TODA prueba que levante la API se encontraría sin licencia y con
# dos efectos feos: escribiría la marca en el registro de Windows de verdad, y
# la suite empezaría a fallar sola en cuanto se acabaran los siete días de
# cortesía. Así que las pruebas se traen su propia licencia, igual que se
# traen su propia base.
#
# La llave es de mentira y está aquí a la vista: firmar con la de verdad
# obligaría a tenerla en el repositorio, que es justo lo que no puede pasar.

PRIVADA_DE_PRUEBAS = bytes(range(32))
MAQUINA_DE_PRUEBAS = "A7K2-3M4P-XR7T"
CLAVE_REGISTRO_DE_PRUEBAS = r"Software\MiTienda-pruebas"


def _preparar_licencias():
    """Apunta el sistema de licencias a la llave, la máquina y el registro
    de pruebas. Se hace una vez, al importar este módulo."""
    from herramientas.firma import llave_publica_de
    from lddl import almacen_licencia, estado_licencia

    almacen_licencia.CLAVE_REGISTRO = CLAVE_REGISTRO_DE_PRUEBAS
    estado_licencia.LLAVE_PUBLICA = llave_publica_de(PRIVADA_DE_PRUEBAS)
    estado_licencia.leer_maquina = lambda: MAQUINA_DE_PRUEBAS


_preparar_licencias()


def poner_licencia(carpeta):
    """Deja un licencia.lic válido en esa carpeta.

    Diez años y emitida ayer: ni vence a mitad de una suite ni parece venida
    del futuro cuando alguien corra las pruebas con el reloj un poco movido.
    """
    from herramientas.generar_licencia import emitir
    from lddl import estado_licencia

    texto = emitir(PRIVADA_DE_PRUEBAS, "Tienda de Pruebas", MAQUINA_DE_PRUEBAS,
                   meses=120, desde=datetime.date.today() - datetime.timedelta(days=1))
    with open(os.path.join(carpeta, "licencia.lic"), "w",
              encoding="utf-8", newline="\n") as fichero:
        fichero.write(texto)
    estado_licencia.olvidar()


def quitar_licencia(carpeta):
    """Deja la carpeta sin licencia, como una instalacion recien entregada.

    Lo usan las pruebas del propio sistema de licencias, que necesitan
    empezar en blanco: las demas se quedan con la que pone
    `carpeta_con_copia`.
    """
    from lddl import estado_licencia

    ruta = os.path.join(carpeta, "licencia.lic")
    if os.path.exists(ruta):
        os.remove(ruta)
    estado_licencia.olvidar()


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
    poner_licencia(temporal)
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
