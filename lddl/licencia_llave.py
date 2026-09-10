"""La llave pública de MiTienda. Un solo dato, en su propio fichero.

Está separada de `licencia.py` a propósito: así se ve de un vistazo cuál es y
cuándo cambió, y quien lea el módulo de las reglas no se la encuentra en medio.

Que esta llave la vea cualquiera es irrelevante y está previsto. Con ella se
COMPRUEBA una firma; para HACERLA hace falta la privada, que vive fuera del
repositorio y nunca entra en el ejecutable.

Cambiar este valor invalida de golpe todas las licencias emitidas hasta la
fecha. Sólo tiene sentido si la llave privada se pierde o se filtra, y aun así
habría que reinstalar el programa en cada tienda.

Generada el 2026-09-10 con `herramientas/generar_llaves.py`.
"""

LLAVE_PUBLICA = bytes.fromhex(
    "6223b021e304c668f29724c7c9904511fa477391a5e75cf9223b22a25c6e4f87")
