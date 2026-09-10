"""Crea el par de llaves de MiTienda. Se ejecuta UNA vez en la vida.

    python herramientas/generar_llaves.py

La privada firma las licencias y no sale nunca de esta computadora. La
pública se copia a mano dentro de lddl/licencia_llave.py y viaja en el .exe
de todos los clientes.

Dos avisos que no son retórica:

- **Si se pierde la privada, no se le puede renovar la licencia a ningún
  cliente nunca más.** No hay recuperación: habría que compilar una versión
  nueva con otra llave y reinstalarla en cada tienda. Dos respaldos, en
  soportes distintos, y uno fuera de esta computadora.

- **Si se filtra, cualquiera emite licencias infinitas**, y tampoco hay
  revocación posible sin recompilar y reinstalar a todos. No llevarla nunca
  en una USB a casa de un cliente: las licencias de técnico se generan desde
  aquí y se mandan por WhatsApp.

Por eso `crear_par` se niega a pisar una llave que ya exista.
"""

import argparse
import binascii
import os
import secrets
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from herramientas.firma import llave_publica_de  # noqa: E402

# Fuera del repositorio a propósito: la carpeta LDDL se sube a GitHub.
RUTA_PRIVADA = os.path.join(os.path.expanduser("~"), "Documents", "Py", "!Salva",
                            "llaves", "mitienda_privada.key")
RUTA_PUBLICA = os.path.join(os.path.dirname(RUTA_PRIVADA), "mitienda_publica.key")


def leer_llave(ruta):
    """Los 32 octetos de una llave guardada en hexadecimal.

    El fichero lleva una línea de comentario arriba que dice qué llave es.
    Está para quien lo abra dentro de dos años y no se acuerde, así que hay
    que saltársela al leer.
    """
    with open(ruta, encoding="ascii") as fichero:
        utiles = [l for l in fichero if not l.lstrip().startswith("#")]
    return binascii.unhexlify("".join("".join(utiles).split()))


def _escribir_llave(ruta, octetos, encabezado):
    os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)
    with open(ruta, "w", encoding="ascii", newline="\n") as fichero:
        fichero.write(f"# {encabezado}\n")
        fichero.write(binascii.hexlify(octetos).decode("ascii") + "\n")


def crear_par(ruta_privada, ruta_publica):
    """Genera el par y lo escribe. Devuelve (privada, publica) en octetos.

    Levanta FileExistsError si alguna de las dos ya está: sobrescribir la
    privada por accidente es el peor error posible de todo este sistema, así
    que tiene que costar.
    """
    for ruta in (ruta_privada, ruta_publica):
        if os.path.exists(ruta):
            raise FileExistsError(
                f"{ruta} ya existe. Si de verdad hace falta una llave nueva, "
                "mueve la vieja a mano primero -y recuerda que las licencias "
                "ya emitidas dejaran de valer.")

    privada = secrets.token_bytes(32)
    publica = llave_publica_de(privada)

    _escribir_llave(ruta_privada, privada, "MiTienda - LLAVE PRIVADA - no compartir")
    _escribir_llave(ruta_publica, publica, "MiTienda - llave publica")
    return privada, publica


def main(argumentos=None):
    analizador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analizador.add_argument("--privada", default=RUTA_PRIVADA)
    analizador.add_argument("--publica", default=RUTA_PUBLICA)
    opciones = analizador.parse_args(argumentos)

    try:
        _privada, publica = crear_par(opciones.privada, opciones.publica)
    except FileExistsError as error:
        print(f"No se hizo nada: {error}")
        return 1

    print(f"Llave privada -> {opciones.privada}")
    print(f"Llave publica -> {opciones.publica}")
    print()
    print("Copia esta linea dentro de lddl/licencia_llave.py:")
    print()
    print(f"    LLAVE_PUBLICA = bytes.fromhex(\"{binascii.hexlify(publica).decode()}\")")
    print()
    print("Y respalda la privada en dos sitios distintos AHORA.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
