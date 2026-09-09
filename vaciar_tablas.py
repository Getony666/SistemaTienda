"""Deja la base de datos virgen, lista para entregar a un negocio nuevo.

Borra TODO: productos, ventas, deudas, historial, caja y divisas. La
estructura de las tablas se queda; lo que desaparece son los datos.

    python vaciar_tablas.py              # pregunta antes de borrar
    python vaciar_tablas.py --si         # sin preguntar
    python vaciar_tablas.py otra.db      # sobre otro fichero

Antes de borrar nada guarda una copia con la fecha y la hora en el nombre,
al lado de la base. Si algo sale mal, ahí está todo como estaba.

Se vacía también `config_caja.json`, que guarda el fondo de caja por fecha:
una instalación nueva no puede arrancar con el dinero de otro negocio.
"""

import datetime
import os
import shutil
import sqlite3
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))


def respaldar(ruta):
    """Copia el fichero con la fecha en el nombre. Devuelve la copia."""
    sello = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    copia = f"{ruta}.antes-de-vaciar-{sello}"
    shutil.copy2(ruta, copia)
    return copia


def vaciar_base_datos(ruta_db):
    """Borra las filas de todas las tablas, productos incluidos."""
    conexion = sqlite3.connect(ruta_db)
    cursor = conexion.cursor()
    try:
        # Se apagan las claves foráneas: si no, el orden en que se vacían
        # las tablas importaría, y hay tablas que se apuntan entre ellas.
        cursor.execute("PRAGMA foreign_keys = OFF;")

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tablas = [t[0] for t in cursor.fetchall()
                  if not t[0].startswith("sqlite_")]

        for tabla in tablas:
            antes = cursor.execute(f'SELECT COUNT(*) FROM "{tabla}"').fetchone()[0]
            cursor.execute(f'DELETE FROM "{tabla}";')
            print(f"  {tabla:24} {antes:6} filas borradas")

        # Que el primer producto del negocio nuevo sea el id 1, no el 309.
        cursor.execute("DELETE FROM sqlite_sequence;")

        cursor.execute("PRAGMA foreign_keys = ON;")
        conexion.commit()
    except Exception as error:
        conexion.rollback()
        print(f"\nError: no se borró nada. {error}")
        return False
    finally:
        conexion.close()

    # VACUUM va fuera de la transacción: recorta el fichero al tamaño real.
    conexion = sqlite3.connect(ruta_db)
    conexion.execute("VACUUM;")
    conexion.close()
    return True


def vaciar_config(ruta_config):
    """Deja el fondo de caja sin ninguna fecha."""
    if not os.path.exists(ruta_config):
        return None
    copia = respaldar(ruta_config)
    with open(ruta_config, "w", encoding="utf-8") as f:
        f.write("{}")
    return copia


def main():
    argumentos = [a for a in sys.argv[1:] if a != "--si"]
    sin_preguntar = "--si" in sys.argv[1:]

    ruta_db = argumentos[0] if argumentos else os.path.join(AQUI, "tienda.db")
    ruta_db = os.path.abspath(ruta_db)
    if not os.path.exists(ruta_db):
        sys.exit(f"No existe: {ruta_db}")
    ruta_config = os.path.join(os.path.dirname(ruta_db), "config_caja.json")

    con = sqlite3.connect(ruta_db)
    filas = {t[0]: con.execute(f'SELECT COUNT(*) FROM "{t[0]}"').fetchone()[0]
             for t in con.execute(
                 "SELECT name FROM sqlite_master WHERE type='table'")
             if not t[0].startswith("sqlite_")}
    con.close()

    print(f"Base de datos: {ruta_db}")
    print(f"Contiene ahora mismo: {sum(filas.values())} filas en total")
    for tabla, n in sorted(filas.items()):
        if n:
            print(f"  {tabla:24} {n:6}")

    if not sin_preguntar:
        print("\nEsto BORRA todo lo anterior, productos incluidos.")
        if input("Escribe VACIAR para continuar: ").strip() != "VACIAR":
            sys.exit("Cancelado. No se ha tocado nada.")

    copia_db = respaldar(ruta_db)
    print(f"\nCopia de seguridad: {copia_db}")

    print("\nVaciando:")
    if not vaciar_base_datos(ruta_db):
        sys.exit(1)

    copia_config = vaciar_config(ruta_config)
    if copia_config:
        print(f"  config_caja.json         vaciado (copia en {os.path.basename(copia_config)})")

    print("\nBase de datos virgen. Un negocio nuevo puede empezar desde cero.")


if __name__ == "__main__":
    main()
