"""Emite un licencia.lic para un cliente.

    python herramientas/generar_licencia.py "Bodega La Esquina" A7K2-3M4P-XR7T --meses 12
    python herramientas/generar_licencia.py "Bodega La Esquina" A7K2-3M4P-XR7T --dias 3 --tecnico

El código de máquina lo enseña MiTienda en la pantalla de licencia, en la
computadora del cliente. Llega por WhatsApp; el licencia.lic vuelve por el
mismo camino y se copia junto al .exe.

Se comprueba todo ANTES de firmar. Emitir una licencia con el código mal
copiado no se nota hasta que el cliente la pega al otro lado de la isla y
llama diciendo que no abre.
"""

import argparse
import calendar
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from herramientas.firma import firmar  # noqa: E402
from herramientas.generar_llaves import RUTA_PRIVADA, leer_llave  # noqa: E402
from lddl import NOMBRE_APP, licencia  # noqa: E402

# El alfabeto de base32, que es de donde sale el codigo de maquina. No tiene
# 0, 1, 8 ni 9, asi que un codigo con esas cifras esta mal copiado seguro.
ALFABETO = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567")


def validar_maquina(codigo):
    """El código en su forma canónica `XXXX-XXXX-XXXX`, o ValueError."""
    limpio = licencia.normalizar_maquina(codigo)
    if len(limpio) != 12 or not set(limpio) <= ALFABETO:
        raise ValueError(
            f"'{codigo}' no es un codigo de maquina: son doce caracteres del "
            "alfabeto base32 (sin 0, 1, 8 ni 9), como A7K2-3M4P-XR7T. "
            "Pideselo otra vez al cliente.")
    return f"{limpio[:4]}-{limpio[4:8]}-{limpio[8:12]}"


def sumar_meses(fecha, meses):
    """Sumar meses no es sumar días: el 31 de enero más un mes no existe.

    Cuando el día no cabe en el mes de destino, cae en el último que haya.
    """
    total = fecha.month - 1 + meses
    ano = fecha.year + total // 12
    mes = total % 12 + 1
    return datetime.date(ano, mes, min(fecha.day, calendar.monthrange(ano, mes)[1]))


def emitir(privada, negocio, maquina, meses=None, dias=None,
           edicion="completa", desde=None, producto=None):
    """El texto completo de un licencia.lic, ya firmado.

    `producto` sale por defecto del NOMBRE_APP de esta copia del proyecto, así
    que el generador de cada producto acierta solo y no hay que acordarse de
    escribirlo. Es lo que impide que la licencia de un programa abra otro.
    """
    negocio = str(negocio or "").strip()
    producto = str(producto if producto is not None else NOMBRE_APP).strip()
    if not negocio:
        raise ValueError("hace falta el nombre del negocio")
    if not producto:
        raise ValueError("hace falta el nombre del producto")
    for texto, que in ((negocio, "del negocio"), (producto, "del producto")):
        # Un salto de linea partiria el fichero y dejaria colar un campo
        # falso detras del nombre.
        if "\n" in texto or "\r" in texto:
            raise ValueError(f"el nombre {que} no puede llevar saltos de linea")
    if edicion not in licencia.EDICIONES:
        raise ValueError(f"edicion desconocida: {edicion}. "
                         f"Las que hay: {', '.join(licencia.EDICIONES)}")

    maquina = validar_maquina(maquina)
    desde = desde or datetime.date.today()

    if (meses is None) == (dias is None):
        raise ValueError("hay que decir --meses o --dias, uno de los dos")
    if meses is not None:
        if meses < 1:
            raise ValueError("una licencia de cero meses no sirve de nada")
        hasta = sumar_meses(desde, meses)
    else:
        if dias < 1:
            raise ValueError("una licencia de cero dias no sirve de nada")
        hasta = desde + datetime.timedelta(days=dias)

    datos = {"producto": producto, "negocio": negocio, "maquina": maquina,
             "desde": desde.isoformat(), "hasta": hasta.isoformat(),
             "edicion": edicion}
    return licencia.componer(datos, firmar(privada, licencia.texto_canonico(datos)))


def main(argumentos=None):
    analizador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analizador.add_argument("negocio", help="nombre del negocio, entre comillas")
    analizador.add_argument("maquina", help="codigo de maquina del cliente")
    analizador.add_argument("--meses", type=int)
    analizador.add_argument("--dias", type=int)
    analizador.add_argument("--tecnico", action="store_true",
                            help="licencia corta de soporte, marcada como tal")
    analizador.add_argument("--producto", default=NOMBRE_APP,
                            help=f"para que programa vale (por defecto {NOMBRE_APP})")
    analizador.add_argument("--llave", default=RUTA_PRIVADA)
    analizador.add_argument("--salida", default="licencia.lic")
    opciones = analizador.parse_args(argumentos)

    meses, dias = opciones.meses, opciones.dias
    if meses is None and dias is None:
        dias, meses = (3, None) if opciones.tecnico else (None, 12)

    try:
        privada = leer_llave(opciones.llave)
    except OSError:
        print(f"No se pudo leer la llave privada en {opciones.llave}")
        print("Si es la primera vez: python herramientas/generar_llaves.py")
        return 1

    try:
        texto = emitir(privada, opciones.negocio, opciones.maquina, meses=meses,
                       dias=dias, producto=opciones.producto,
                       edicion="tecnico" if opciones.tecnico else "completa")
    except ValueError as error:
        print(f"No se emitio nada: {error}")
        return 1

    with open(opciones.salida, "w", encoding="utf-8", newline="\n") as fichero:
        fichero.write(texto)

    datos, _firma = licencia.analizar(texto)
    print(f"Escrito en {opciones.salida}")
    print()
    print(f"  Producto {datos['producto']}")
    print(f"  Negocio  {datos['negocio']}")
    print(f"  Maquina  {datos['maquina']}")
    print(f"  Vale de  {datos['desde']}  hasta  {datos['hasta']}")
    print(f"  Edicion  {datos['edicion']}")
    print()
    print("Repasa el nombre y la maquina antes de mandarlo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
