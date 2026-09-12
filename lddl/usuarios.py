"""Usuarios, roles y permisos.

Los permisos son DATOS, no código: viven en la tabla `permisos_rol` y el
Admin los cambia cuando quiere. Aquí sólo están la lista de los que existen,
los valores con los que arranca una tienda nueva, y las cuentas de quién
puede qué.

El PIN nunca se guarda tal cual. Se guarda `sal$huella`, donde la huella sale
de pbkdf2 con muchas vueltas: de ahí no se saca el PIN de vuelta. Eso impide
LEERLO, no impide que quien pueda editar el fichero de la base se lo salte;
para un programa de escritorio, con la base al lado del ejecutable, eso es lo
que hay, y conviene no engañarse.
"""

import datetime
import hashlib
import hmac
import os

from .rutas import consulta, transaccion

ADMIN = "Admin"
BOSS = "Boss"
EMPLEADO = "Empleado"
ROLES = (ADMIN, BOSS, EMPLEADO)

# (clave, texto para la pantalla). El orden es el que se ve en el panel.
PERMISOS = (
    ("vender", "Vender"),
    ("cobrar_deudas", "Cobrar deudas"),
    ("salida_inventario", "Registrar salidas de inventario"),
    ("merma", "Registrar mermas"),
    ("cambio_divisa", "Cambiar divisa"),
    ("entrada_efectivo", "Registrar entradas de efectivo"),
    ("salida_efectivo", "Registrar salidas de efectivo"),
    ("fondo_caja", "Fijar el fondo de caja"),
    ("ver_corte", "Ver el corte de caja"),
    ("cerrar_caja", "Cerrar la caja del día"),
    ("ver_historial", "Ver el historial"),
    ("crear_producto", "Crear productos"),
    ("actualizar_producto", "Actualizar productos"),
    ("eliminar_producto", "Eliminar productos"),
    ("eliminar_historial", "Eliminar del historial"),
    ("ver_almacen", "Ver el almacén"),
    ("gestionar_usuarios", "Gestionar usuarios y permisos"),
)

CLAVES = tuple(clave for clave, _ in PERMISOS)

# Éste no se toca: si se pudiera quitar a Admin, un descuido dejaría la
# tienda sin nadie capaz de administrarla, y eso sólo se arregla metiendo
# mano a la base. Si se pudiera dar a Boss, dejaría de ser "sólo de Admin".
PERMISO_FIJO = "gestionar_usuarios"

# Con lo que arranca una tienda nueva. A partir de ahí manda la base.
POR_DEFECTO = {
    ADMIN: set(CLAVES),
    BOSS: set(CLAVES) - {PERMISO_FIJO},
    EMPLEADO: {
        "vender", "cobrar_deudas", "salida_inventario", "merma",
        "cambio_divisa", "ver_corte", "ver_historial",
        # Quien cuenta el dinero por la noche es ella, así que es ella quien
        # cierra. Poner el fondo por la mañana sigue siendo de los otros dos.
        "cerrar_caja",
    },
}


class ErrorDeUsuarios(Exception):
    """Algo que la persona puede corregir: nombre repetido, PIN corto..."""


# ------------------------------------------------------------------- el PIN

VUELTAS = 200_000


def cifrar_pin(pin):
    """Devuelve 'sal$huella'. De la huella no se vuelve al PIN."""
    pin = (pin or "").strip()
    if len(pin) < 4:
        raise ErrorDeUsuarios("El PIN tiene que tener al menos 4 caracteres")
    sal = os.urandom(16)
    huella = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), sal, VUELTAS)
    return f"{sal.hex()}${huella.hex()}"


def comprobar_pin(pin, guardado):
    """Compara sin dar pistas por el tiempo que tarda."""
    if not guardado or "$" not in guardado:
        return False
    sal_hex, huella_hex = guardado.split("$", 1)
    try:
        sal = bytes.fromhex(sal_hex)
    except ValueError:
        return False
    intento = hashlib.pbkdf2_hmac("sha256", (pin or "").encode("utf-8"), sal, VUELTAS)
    return hmac.compare_digest(intento.hex(), huella_hex)


# --------------------------------------------------------------- los permisos

def permisos_de(rol):
    """Los permisos concedidos a un rol, leídos de la base."""
    if rol == ADMIN:
        # Admin lo puede todo, pase lo que pase en la tabla. Es la salida de
        # emergencia: ningún cambio de permisos puede dejar la tienda muerta.
        return set(CLAVES)
    with consulta() as (_conexion, cursor):
        cursor.execute(
            "SELECT permiso FROM permisos_rol WHERE rol = ? AND concedido = 1", (rol,))
        concedidos = {fila[0] for fila in cursor.fetchall()}
    return concedidos - {PERMISO_FIJO}


def mapa_de_permisos():
    """Todos los roles con todos sus permisos, para pintar el panel."""
    return {rol: sorted(permisos_de(rol)) for rol in ROLES}


def fijar_permiso(rol, permiso, concedido):
    """Concede o quita un permiso a un rol. Devuelve (exito, mensaje)."""
    if rol not in ROLES:
        return False, f"El rol {rol} no existe"
    if permiso not in CLAVES:
        return False, f"El permiso {permiso} no existe"
    if permiso == PERMISO_FIJO:
        return False, ("Gestionar usuarios y permisos es sólo de Admin: "
                       "no se puede dar ni quitar")
    if rol == ADMIN:
        return False, "Admin tiene todos los permisos y no se le quitan"

    with transaccion() as (_conexion, cursor):
        cursor.execute(
            "INSERT INTO permisos_rol (rol, permiso, concedido) VALUES (?, ?, ?)"
            " ON CONFLICT(rol, permiso) DO UPDATE SET concedido = excluded.concedido",
            (rol, permiso, 1 if concedido else 0))
    verbo = "concedido a" if concedido else "quitado a"
    return True, f"Permiso {verbo} {rol}"


# --------------------------------------------------------------- los usuarios

def _fila_a_usuario(fila):
    return {"id": fila[0], "nombre": fila[1], "rol": fila[2], "activo": bool(fila[3])}


def listar_usuarios(incluir_inactivos=False):
    sentencia = "SELECT id, nombre, rol, activo FROM usuarios"
    if not incluir_inactivos:
        sentencia += " WHERE activo = 1"
    sentencia += " ORDER BY rol, nombre"
    with consulta() as (_conexion, cursor):
        cursor.execute(sentencia)
        return [_fila_a_usuario(f) for f in cursor.fetchall()]


def hay_usuarios():
    """Falso en una tienda recién estrenada: entonces se crea el primer Admin."""
    with consulta() as (_conexion, cursor):
        cursor.execute("SELECT COUNT(*) FROM usuarios WHERE activo = 1")
        return cursor.fetchone()[0] > 0


def buscar_por_nombre(nombre):
    with consulta() as (_conexion, cursor):
        cursor.execute(
            "SELECT id, nombre, rol, activo, pin FROM usuarios WHERE nombre = ?",
            ((nombre or "").strip(),))
        fila = cursor.fetchone()
    if not fila:
        return None
    usuario = _fila_a_usuario(fila)
    usuario["pin"] = fila[4]
    return usuario


def crear_usuario(nombre, rol, pin):
    nombre = (nombre or "").strip()
    if not nombre:
        return False, "Hace falta un nombre"
    if rol not in ROLES:
        return False, f"El rol tiene que ser uno de: {', '.join(ROLES)}"
    try:
        cifrado = cifrar_pin(pin)
    except ErrorDeUsuarios as error:
        return False, str(error)

    with consulta() as (_conexion, cursor):
        cursor.execute("SELECT 1 FROM usuarios WHERE nombre = ?", (nombre,))
        if cursor.fetchone():
            return False, f"Ya hay un usuario que se llama {nombre}"

    with transaccion() as (_conexion, cursor):
        cursor.execute(
            "INSERT INTO usuarios (nombre, rol, pin, activo, creado)"
            " VALUES (?, ?, ?, 1, ?)",
            (nombre, rol, cifrado,
             datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    return True, f"Usuario {nombre} creado como {rol}"


def cambiar_rol(usuario_id, rol):
    if rol not in ROLES:
        return False, f"El rol tiene que ser uno de: {', '.join(ROLES)}"
    with consulta() as (_conexion, cursor):
        cursor.execute("SELECT nombre, rol FROM usuarios WHERE id = ?", (usuario_id,))
        fila = cursor.fetchone()
    if not fila:
        return False, "Ese usuario no existe"
    nombre, rol_viejo = fila
    if rol_viejo == ADMIN and rol != ADMIN and _admins_activos() <= 1:
        return False, ("Es el único Admin que queda: si le cambias el rol, "
                       "nadie podrá administrar el programa")

    with transaccion() as (_conexion, cursor):
        cursor.execute("UPDATE usuarios SET rol = ? WHERE id = ?", (rol, usuario_id))
    return True, f"{nombre} pasa a ser {rol}"


def restablecer_pin(usuario_id, pin_nuevo):
    """El Admin le pone un PIN nuevo a cualquiera. No hace falta el viejo."""
    try:
        cifrado = cifrar_pin(pin_nuevo)
    except ErrorDeUsuarios as error:
        return False, str(error)
    with consulta() as (_conexion, cursor):
        cursor.execute("SELECT nombre FROM usuarios WHERE id = ?", (usuario_id,))
        fila = cursor.fetchone()
    if not fila:
        return False, "Ese usuario no existe"

    with transaccion() as (_conexion, cursor):
        cursor.execute("UPDATE usuarios SET pin = ? WHERE id = ?", (cifrado, usuario_id))
    return True, f"PIN de {fila[0]} restablecido"


def desactivar_usuario(usuario_id):
    """No se borra: se apaga. Así lo que hizo sigue teniendo nombre."""
    with consulta() as (_conexion, cursor):
        cursor.execute("SELECT nombre, rol FROM usuarios WHERE id = ?", (usuario_id,))
        fila = cursor.fetchone()
    if not fila:
        return False, "Ese usuario no existe"
    nombre, rol = fila
    if rol == ADMIN and _admins_activos() <= 1:
        return False, "Es el único Admin que queda: no se puede desactivar"

    with transaccion() as (_conexion, cursor):
        cursor.execute("UPDATE usuarios SET activo = 0 WHERE id = ?", (usuario_id,))
    return True, f"Usuario {nombre} desactivado"


def _admins_activos():
    with consulta() as (_conexion, cursor):
        cursor.execute(
            "SELECT COUNT(*) FROM usuarios WHERE rol = ? AND activo = 1", (ADMIN,))
        return cursor.fetchone()[0]


# ------------------------------------------------------------------- arranque

def sembrar_permisos_si_hace_falta():
    """Deja en la tabla los permisos de arranque, sin pisar los ya cambiados.

    En una tienda nueva la tabla está vacía y aquí se siembra todo. En una
    que ya venía de antes, sólo hacen falta las claves que todavía no existen
    para ningún rol -así un permiso añadido en una versión nueva del programa
    (como ver_almacen) llega también a las bases existentes, con su valor por
    defecto, sin tocar los permisos que el Admin ya haya cambiado a mano.
    """
    with transaccion() as (_conexion, cursor):
        cursor.execute("SELECT COUNT(*) FROM permisos_rol")
        vacia = cursor.fetchone()[0] == 0
        cursor.execute("SELECT rol, permiso FROM permisos_rol")
        existentes = set(cursor.fetchall())
        for rol in ROLES:
            for clave in CLAVES:
                if (rol, clave) in existentes:
                    continue
                cursor.execute(
                    "INSERT INTO permisos_rol (rol, permiso, concedido) VALUES (?, ?, ?)",
                    (rol, clave, 1 if clave in POR_DEFECTO[rol] else 0))
    return vacia
