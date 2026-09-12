"""Quién está usando el programa ahora mismo.

Un programa de escritorio es un proceso y una ventana: hay un solo usuario
dentro, y con guardarlo aquí basta. Ésta es la pieza que el día que el panel
salga a internet habrá que cambiar por un identificador por cada cliente;
todo lo demás -los permisos, las comprobaciones- se queda como está.

La comprobación vive en la API, no en la pantalla. Esconder un botón es una
comodidad; lo que impide de verdad es que la ruta conteste 403 y no toque la
base.
"""

from . import usuarios

_usuario = None


class SinPermiso(Exception):
    """El usuario de ahora no puede hacer eso."""

    def __init__(self, permiso, mensaje=None):
        self.permiso = permiso
        super().__init__(mensaje or f"Tu usuario no tiene permiso para {permiso}")


def entrar(nombre, pin):
    """Comprueba el PIN y deja la sesión abierta. Devuelve (exito, mensaje)."""
    global _usuario
    usuario = usuarios.buscar_por_nombre(nombre)
    # Mismo mensaje si el usuario no existe o si el PIN falla: decir cuál de
    # las dos cosas ha fallado es regalar media contraseña.
    if not usuario or not usuario["activo"]:
        usuarios.comprobar_pin(pin, "0" * 32 + "$" + "0" * 64)  # tarda lo mismo
        return False, "Usuario o PIN incorrectos"
    if not usuarios.comprobar_pin(pin, usuario["pin"]):
        return False, "Usuario o PIN incorrectos"

    _usuario = {"id": usuario["id"], "nombre": usuario["nombre"], "rol": usuario["rol"]}
    return True, f"Hola, {usuario['nombre']}"


def salir():
    global _usuario
    _usuario = None


def fijar_usuario(usuario):
    """Pone la sesión a mano. Para las pruebas y para el primer arranque."""
    global _usuario
    _usuario = usuario


def sesion_actual():
    return dict(_usuario) if _usuario else None


def hay_sesion():
    return _usuario is not None


def usuario_actual():
    """El nombre, para sellar con él lo que se guarde. Vacío si no hay nadie."""
    return _usuario["nombre"] if _usuario else ""


def rol_actual():
    return _usuario["rol"] if _usuario else None


def permisos_actuales():
    if not _usuario:
        return set()
    return usuarios.permisos_de(_usuario["rol"])


def puede(permiso):
    if not _usuario:
        return False
    return permiso in usuarios.permisos_de(_usuario["rol"])


def exigir(permiso):
    """Deja pasar, o levanta SinPermiso. Es lo que llaman las rutas."""
    if not _usuario:
        raise SinPermiso(permiso, "Hay que entrar en el programa primero")
    if not puede(permiso):
        etiqueta = dict(usuarios.PERMISOS).get(permiso, permiso)
        raise SinPermiso(
            permiso,
            f"{_usuario['nombre']} ({_usuario['rol']}) no tiene permiso para: {etiqueta}")
