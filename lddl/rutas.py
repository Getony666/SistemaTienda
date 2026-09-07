"""Rutas de los ficheros de datos y acceso a la base de datos.

Todo el programa abre la base a través de este módulo. Los gestores de contexto
`consulta` y `transaccion` garantizan que la conexión se cierre también cuando la
operación falla a mitad, que era la vía por la que se quedaban conexiones abiertas.
"""

import contextlib
import os
import sqlite3
import sys
import unicodedata


# Directorio donde viven tienda.db y config_caja.json. Se puede cambiar con
# fijar_directorio_base() para trabajar sobre una copia (pruebas, ensayos).
_directorio_base = None


def fijar_directorio_base(ruta):
    global _directorio_base
    _directorio_base = ruta


def obtener_ruta_base():
    if _directorio_base:
        return _directorio_base
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def obtener_ruta_db():
    return os.path.join(obtener_ruta_base(), "tienda.db")


def obtener_ruta_config():
    return os.path.join(obtener_ruta_base(), "config_caja.json")


def conectar_db():
    return sqlite3.connect(obtener_ruta_db())


@contextlib.contextmanager
def consulta():
    """Conexión de sólo lectura que se cierra pase lo que pase.

    Uso:  with consulta() as (conn, cursor): ...
    """
    conn = conectar_db()
    try:
        yield conn, conn.cursor()
    finally:
        conn.close()


@contextlib.contextmanager
def transaccion():
    """Conexión en transacción: confirma al salir bien, deshace si algo falla.

    Uso:  with transaccion() as (conn, cursor): ...
    """
    conn = conectar_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn, conn.cursor()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def quitar_tildes(texto):
    if not texto:
        return ""
    texto = str(texto)
    nfkd = unicodedata.normalize('NFKD', texto)
    return ''.join([c for c in nfkd if not unicodedata.combining(c)]).lower()
