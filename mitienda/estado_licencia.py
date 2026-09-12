"""El veredicto del arranque: qué puede hacer hoy este programa, en esta PC.

Junta las cuatro piezas -el fichero, la huella de la máquina, la marca contra
el reloj atrasado y las reglas puras de `licencia.py`- y deja el resultado
guardado en el módulo, exactamente igual que `sesion.py` guarda quién entró.

Un programa de escritorio es un proceso y una ventana: con guardarlo aquí
basta. El día que el panel del dueño salga a internet, esta pieza tendrá que
cambiar por un estado por cada cliente, igual que la sesión.

**Dónde está el candado.** En la API, no en la pantalla. Cada ruta que escribe
llama a `exigir_escritura()` y contesta 402 sin tocar la base. Esconder los
botones es una comodidad; quien sepa la dirección puede llamar a la ruta desde
la consola del navegador. Es la misma decisión que se tomó con los permisos, y
por el mismo motivo.

**Qué se bloquea y qué no.** Vencida la licencia, no se puede vender, ni tocar
el inventario, ni mover dinero. Sí se puede consultar el historial, ver a
quién se le debe qué y exportar. Los datos del negocio son del negocio:
secuestrárselos es lo que empuja a un cliente molesto a buscarse una copia
parcheada en vez de pagar.
"""

import datetime

from . import NOMBRE_APP, almacen_licencia, licencia, maquina
from .licencia_llave import LLAVE_PUBLICA  # noqa: F401  (las pruebas lo cambian)

# Para qué programa vale una licencia. Va firmado dentro, así que la licencia
# de un producto no abre otro aunque los dos usen la misma llave.
PRODUCTO = NOMBRE_APP

DIAS_DE_CORTESIA = 7

_veredicto = None
_codigo_maquina = None


class LicenciaVencida(Exception):
    """No se puede escribir con la licencia como está.

    Lleva el estado dentro para que la pantalla sepa si toca decir "renueva",
    "esta licencia es de otra computadora" o "corrige la fecha de Windows".
    """

    def __init__(self, veredicto, mensaje=None):
        self.veredicto = veredicto
        self.estado = veredicto.estado
        self.motivo = veredicto.motivo
        super().__init__(mensaje or explicar(veredicto))


def leer_maquina():
    """Indirección a propósito: las pruebas la cambian para no depender de en
    qué computadora corran."""
    return maquina.codigo_de_esta_maquina()


MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre")


def en_castellano(fecha):
    """«16 de agosto de 2027».

    A mano y no con `locale`: en Windows el idioma del sistema decide, y una
    caja configurada en inglés sacaría «August 16» en medio de una frase en
    castellano.
    """
    if not fecha:
        return ""
    return f"{fecha.day} de {MESES[fecha.month - 1]} de {fecha.year}"


def explicar(veredicto):
    """El motivo en castellano, para enseñarlo tal cual.

    Lo lee la cajera: en la pantalla de licencia y también en el error que
    devuelve la API cuando alguien intenta cobrar con la licencia vencida.
    Por eso cada frase dice qué pasa y qué hacer, no sólo que algo falló.
    """
    if veredicto.estado == licencia.VENCIDA:
        return (f"La licencia de MiTienda venció el "
                f"{en_castellano(veredicto.hasta)}. Hay que renovarla.")
    if veredicto.estado == licencia.RELOJ_ATRASADO:
        return ("La fecha de esta computadora está atrasada. Corrígela en "
                "Windows y vuelve a abrir el programa.")
    return {
        licencia.NO_HAY_ARCHIVO: "Este MiTienda todavía no tiene licencia.",
        licencia.OTRA_MAQUINA: ("Esta licencia es de otra computadora. Hace "
                                "falta una para ésta."),
        licencia.OTRO_PRODUCTO: (f"Esta licencia es de otro programa, no de "
                                 f"{PRODUCTO}. Pide la que corresponde."),
        licencia.FIRMA: ("El fichero de licencia está alterado y no vale. "
                         "Pide uno nuevo."),
        licencia.FORMATO: ("El fichero de licencia no se entiende. Pide uno "
                           "nuevo."),
    }.get(veredicto.motivo, "Hace falta una licencia para usar MiTienda.")


def _decidir(texto, huella, hoy):
    """La cadena de comprobaciones, en orden. Sin guardar nada.

    El orden importa: con el reloj mal, ni "activa" ni "vencida" significan
    nada, así que eso se mira primero.
    """
    if almacen_licencia.reloj_atrasado(hoy, almacen_licencia.marca_maxima()):
        return licencia.Veredicto(licencia.RELOJ_ATRASADO)

    veredicto = licencia.verificar(texto, LLAVE_PUBLICA, huella, hoy, PRODUCTO)

    # Sólo se estrena la cortesía cuando NO hay fichero. Una licencia vencida,
    # manipulada o de otra máquina no vuelve a abrir la puerta de los siete
    # días: si no, bastaría con borrar el .lic para renovarse solo.
    if veredicto.estado == licencia.SIN_LICENCIA and veredicto.motivo == licencia.NO_HAY_ARCHIVO:
        empezo = almacen_licencia.primer_arranque(hoy)
        quedan = DIAS_DE_CORTESIA - (hoy - empezo).days
        if quedan >= 0:
            return licencia.Veredicto(licencia.CORTESIA, dias_restantes=quedan)

    return veredicto


def comprobar(hoy=None):
    """Mira todo y deja el veredicto guardado. Lo llama la API al arrancar."""
    global _veredicto, _codigo_maquina
    hoy = hoy or datetime.date.today()

    _codigo_maquina = leer_maquina()
    _veredicto = _decidir(almacen_licencia.leer_licencia(), _codigo_maquina, hoy)

    # Apuntar el día siempre, incluso sin licencia: es lo que deja rastro
    # para que atrasar el reloj mañana no cuele. No se apunta si el reloj ya
    # está atrasado, porque entonces la fecha de hoy no vale nada.
    if _veredicto.estado != licencia.RELOJ_ATRASADO:
        almacen_licencia.anotar_marca(hoy)

    return _veredicto


def olvidar():
    """Borra el veredicto guardado. Para las pruebas y para reactivar."""
    global _veredicto, _codigo_maquina
    _veredicto = None
    _codigo_maquina = None


def actual():
    """El veredicto de este arranque, comprobándolo si aún no se hizo."""
    return _veredicto if _veredicto is not None else comprobar()


def codigo_de_maquina():
    """El código que hay que enseñar para pedir una licencia.

    Tiene que salir siempre, sobre todo cuando no hay licencia: es lo primero
    que necesita el cliente para poder pedir la suya.
    """
    global _codigo_maquina
    if _codigo_maquina is None:
        _codigo_maquina = leer_maquina()
    return _codigo_maquina


def puede_escribir():
    return actual().estado in licencia.ESTADOS_QUE_ESCRIBEN


def exigir_escritura():
    """Deja pasar, o levanta LicenciaVencida. Es lo que llaman las rutas."""
    veredicto = actual()
    if veredicto.estado not in licencia.ESTADOS_QUE_ESCRIBEN:
        raise LicenciaVencida(veredicto)


def activar(texto, hoy=None):
    """Guarda una licencia que llega de la pantalla. Devuelve (bien, veredicto).

    Se comprueba ANTES de escribir: si no, una licencia de otra computadora o
    un fichero pegado a medias pisaría la buena que pudiera haber, y el
    cliente se quedaría sin poder vender por intentar renovar.
    """
    global _veredicto
    hoy = hoy or datetime.date.today()
    huella = codigo_de_maquina()

    veredicto = _decidir(texto, huella, hoy)
    if veredicto.estado not in licencia.ESTADOS_QUE_ESCRIBEN:
        return False, veredicto

    if not almacen_licencia.guardar_licencia(texto):
        return False, licencia.Veredicto(licencia.SIN_LICENCIA, licencia.NO_HAY_ARCHIVO)

    _veredicto = veredicto
    return True, veredicto


def para_la_pantalla():
    """Lo que la interfaz necesita saber, en un diccionario suelto."""
    veredicto = actual()
    return {
        "estado": veredicto.estado,
        "motivo": veredicto.motivo,
        "explicacion": "" if puede_escribir() else explicar(veredicto),
        "negocio": veredicto.negocio,
        "producto": veredicto.producto,
        "edicion": veredicto.edicion,
        "hasta": veredicto.hasta.isoformat() if veredicto.hasta else "",
        "dias_restantes": veredicto.dias_restantes,
        "puede_escribir": puede_escribir(),
        "maquina": codigo_de_maquina(),
    }
