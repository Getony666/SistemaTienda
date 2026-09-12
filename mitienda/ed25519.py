"""Verificación de firmas Ed25519, en Python puro y sin dependencias.

Aquí sólo se COMPRUEBAN firmas; no se hacen. Firmar necesita la llave privada
y eso vive en `herramientas/`, fuera del ejecutable que se entrega: dentro del
.exe que va a una tienda no puede haber nada capaz de emitir una licencia.

Por qué escrito a mano y no con una librería: `cryptography` arrastra OpenSSL
y engorda el ejecutable unos 10 MB, y todo esto se usa una vez por arranque
para comprobar 64 octetos. Esto son unas ciento y pico líneas y tarda del
orden de 15 ms.

La aritmética sigue paso por paso la ilustración en Python del apéndice A del
RFC 8032, y por eso los nombres de las funciones internas se quedan como allí
(`point_add`, `point_mul`, `recover_x`...) en lugar de traducirse: quien tenga
que auditar esto va a leerlo con el RFC al lado, y que las dos cosas se
llamen igual vale más que la coherencia con el resto del programa.

`pruebas/test_ed25519.py` compara contra los vectores oficiales del RFC. Sin
esa prueba en verde este fichero no vale nada: una curva mal implementada
acepta firmas falsas sin quejarse.
"""

import hashlib

# Cuerpo primo de la curva y orden del subgrupo principal.
P = 2 ** 255 - 19
L = 2 ** 252 + 27742317777372353535851937790883648493


def _inverso(x):
    """Inverso multiplicativo módulo P, por el pequeño teorema de Fermat."""
    return pow(x, P - 2, P)


D = -121665 * _inverso(121666) % P
RAIZ_DE_MENOS_UNO = pow(2, (P - 1) // 4, P)


# ------------------------------------------------------------------- la curva
#
# Los puntos van en coordenadas extendidas (X, Y, Z, T), con x = X/Z, y = Y/Z
# y x*y = T/Z. Se usan éstas y no las llanas (x, y) porque sumar en llanas
# obliga a invertir -que es una exponenciación modular- en CADA suma, y una
# verificación hace centenares. En extendidas no se invierte ni una vez.


def _point_add(Pt, Q):
    a = (Pt[1] - Pt[0]) * (Q[1] - Q[0]) % P
    b = (Pt[1] + Pt[0]) * (Q[1] + Q[0]) % P
    c = 2 * Pt[3] * Q[3] * D % P
    e = 2 * Pt[2] * Q[2] % P
    f, g, h, i = b - a, e - c, e + c, b + a
    return (f * g % P, h * i % P, g * h % P, f * i % P)


def _point_mul(escalar, Pt):
    """Multiplicación por duplicación y suma.

    No es de tiempo constante, y aquí da igual: el escalar que se multiplica
    sale de la firma y de la llave PÚBLICA, que son datos que cualquiera puede
    leer. Nada secreto pasa por esta función.
    """
    Q = (0, 1, 1, 0)  # el neutro
    while escalar > 0:
        if escalar & 1:
            Q = _point_add(Q, Pt)
        Pt = _point_add(Pt, Pt)
        escalar >>= 1
    return Q


def _point_equal(Pt, Q):
    """Dos puntos son el mismo si x1/z1 == x2/z2 e y1/z1 == y2/z2.

    Se comparan en cruz (x1*z2 == x2*z1) para no tener que dividir.
    """
    if (Pt[0] * Q[2] - Q[0] * Pt[2]) % P != 0:
        return False
    return (Pt[1] * Q[2] - Q[1] * Pt[2]) % P == 0


def _recover_x(y, signo):
    """La x que le corresponde a una y, o None si esa y no está en la curva.

    Devolver None y no reventar es deliberado: la y sale de un fichero que
    puede haber tocado cualquiera, y una excepción sin recoger dejaría el
    programa sin arrancar por una licencia mal copiada.
    """
    if y >= P:
        return None
    x2 = (y * y - 1) * _inverso(D * y * y + 1) % P
    if x2 == 0:
        return None if signo else 0
    x = pow(x2, (P + 3) // 8, P)
    if (x * x - x2) % P != 0:
        x = x * RAIZ_DE_MENOS_UNO % P
    if (x * x - x2) % P != 0:
        return None
    if (x & 1) != signo:
        x = P - x
    return x


def _descomprimir(octetos):
    """Los 32 octetos de un punto vuelven a ser un punto, o None si no lo son."""
    if len(octetos) != 32:
        return None
    y = int.from_bytes(octetos, "little")
    signo = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, signo)
    if x is None:
        return None
    return (x, y, 1, x * y % P)


_GENERADOR_Y = 4 * _inverso(5) % P
_GENERADOR_X = _recover_x(_GENERADOR_Y, 0)
GENERADOR = (_GENERADOR_X, _GENERADOR_Y, 1, _GENERADOR_X * _GENERADOR_Y % P)


def sha512_mod_l(datos):
    """SHA-512 leído como entero en little-endian y reducido módulo L.

    La comparte el firmador de `herramientas/`, que por eso no la lleva con
    subrayado: es parte de lo que este módulo ofrece a quien firma.
    """
    return int.from_bytes(hashlib.sha512(datos).digest(), "little") % L


# ------------------------------------------------------------------- la puerta

def verificar(llave_publica, mensaje, firma):
    """¿Firmó esta llave este mensaje? Devuelve True o False, y nada más.

    Nunca levanta una excepción, pase lo que pase con lo que se le dé: la
    llamada esto con el contenido de `licencia.lic`, que es un fichero de
    texto en la carpeta del cliente. Un octeto de más, un recorte al copiar y
    pegar o basura entera tienen que dar un "no", no un programa que no abre.
    """
    try:
        if len(llave_publica) != 32 or len(firma) != 64:
            return False

        punto_llave = _descomprimir(llave_publica)
        if punto_llave is None:
            return False

        r_comprimido = firma[:32]
        punto_r = _descomprimir(r_comprimido)
        if punto_r is None:
            return False

        s = int.from_bytes(firma[32:], "little")
        # s tiene que quedar por debajo del orden del grupo. Sin esta línea se
        # aceptarían varias firmas distintas para el mismo mensaje, que es una
        # puerta de atrás conocida de las implementaciones descuidadas.
        if s >= L:
            return False

        h = sha512_mod_l(r_comprimido + bytes(llave_publica) + bytes(mensaje))
        return _point_equal(_point_mul(s, GENERADOR),
                            _point_add(punto_r, _point_mul(h, punto_llave)))
    except (TypeError, ValueError):
        return False
