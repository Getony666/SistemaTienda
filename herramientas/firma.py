"""Firmar con Ed25519. La otra mitad de lddl/ed25519.py.

La aritmética de la curva se importa de allí en vez de repetirla, para que
firmador y verificador no puedan separarse nunca: cualquier arreglo en la
curva vale para los dos a la vez.

Lo que sí está sólo aquí es el manejo de la llave privada, y eso es
deliberado. Este fichero no se compila en el ejecutable que va a una tienda.

Sigue la sección 5.1.6 del RFC 8032. `pruebas/test_firma.py` comprueba que
reproduce sus firmas oficiales octeto a octeto.
"""

import hashlib

from lddl.ed25519 import (
    GENERADOR, L, P, _inverso, _point_mul, sha512_mod_l,
)


def _comprimir(punto):
    """Un punto de la curva vuelve a ser 32 octetos.

    Es la única vez en todo el cálculo que hace falta invertir: se sale de
    las coordenadas extendidas para quedarse con la y y el bit de signo de la
    x, que es lo que se guarda.
    """
    inverso_z = _inverso(punto[2])
    x = punto[0] * inverso_z % P
    y = punto[1] * inverso_z % P
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _escalar_secreto(semilla):
    """Los 32 octetos de la izquierda del hash, con los bits podados.

    La poda no es adorno: fija el bit 254 y borra los tres de abajo para que
    el escalar caiga siempre en el subgrupo correcto y tenga la misma
    longitud. Sin ella, la firma filtra información sobre la llave.
    """
    h = hashlib.sha512(semilla).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def llave_publica_de(privada):
    """Los 32 octetos públicos que le corresponden a una llave privada.

    Ésta es la que se compila dentro del programa. La privada no sale de aquí.
    """
    if len(privada) != 32:
        raise ValueError("una llave privada Ed25519 mide 32 octetos")
    a, _prefijo = _escalar_secreto(privada)
    return _comprimir(_point_mul(a, GENERADOR))


def firmar(privada, mensaje):
    """Los 64 octetos de firma de este mensaje con esta llave.

    El azar de la firma no es azar: sale de mezclar la llave con el mensaje,
    así que firmar dos veces lo mismo da lo mismo. Es lo que dice el RFC, y
    quita de en medio el generador de números aleatorios, que es por donde se
    han roto otras firmas.
    """
    if len(privada) != 32:
        raise ValueError("una llave privada Ed25519 mide 32 octetos")

    a, prefijo = _escalar_secreto(privada)
    publica = _comprimir(_point_mul(a, GENERADOR))

    r = sha512_mod_l(prefijo + mensaje)
    punto_r = _comprimir(_point_mul(r, GENERADOR))

    s = (r + sha512_mod_l(punto_r + publica + mensaje) * a) % L
    return punto_r + s.to_bytes(32, "little")
