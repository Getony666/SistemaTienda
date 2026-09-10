"""Dónde vive la licencia y cómo se recuerda qué día fue el último.

Todo lo que tiene efectos secundarios -disco, base y registro de Windows-
está aquí, para que `licencia.py` se quede siendo un módulo puro que se puede
probar con fechas inventadas.

**La marca de agua.** El truco más fácil para estirar una licencia es atrasar
el reloj de Windows. Contra eso, el programa recuerda la fecha más alta que
ha visto, y se guarda por triplicado:

1. La tabla `marcas_licencia` de `tienda.db`.
2. `HKCU\\Software\\MiTienda`, en el registro. Va en HKCU y no en HKLM para no
   necesitar permisos de administrador.
3. `MAX(fecha)` de la tabla `historial`, que se escribe sola con cada
   operación y que nadie mira como si fuera un candado.

Se toma el máximo de las tres. Borrar `tienda.db` para empezar de cero -que
es lo primero que se le ocurre a cualquiera- no basta, porque el registro
sigue ahí; y borrar el registro tampoco, porque el historial delata el día.

Nada de aquí levanta excepciones. Si el registro no se deja escribir o el
fichero llega en una codificación rara, el programa tiene que seguir hasta la
pantalla de licencia para poder explicarlo.
"""

import datetime
import os

from .rutas import consulta, obtener_ruta_licencia, transaccion

CLAVE_REGISTRO = r"Software\MiTienda"
VALOR_MARCA = "um"
VALOR_PRIMER_ARRANQUE = "pa"

# Dos días de margen: husos horarios, el cambio de hora y las pilas de placa
# base gastadas hacen que un reloj se vaya un poco sin que nadie haga trampa.
# Bloquear a un cliente honesto por un día sería peor el remedio.
DIAS_DE_MARGEN = 2


# ------------------------------------------------------------------- el fichero

def leer_licencia():
    """El texto de `licencia.lic`, o "" si no hay o no se deja leer."""
    try:
        with open(obtener_ruta_licencia(), encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def guardar_licencia(texto):
    """Escribe `licencia.lic`. Devuelve si pudo.

    Siempre en UTF-8 explícito: los nombres de negocio llevan tildes y eñes, y
    dejar que Windows elija la codificación es exactamente como salen los
    acentos dobles que ya han mordido en este proyecto.
    """
    try:
        with open(obtener_ruta_licencia(), "w", encoding="utf-8", newline="\n") as f:
            f.write(texto)
        return True
    except OSError:
        return False


# -------------------------------------------------------------- el registro

def _leer_del_registro(valor):
    try:
        import winreg
    except ImportError:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLAVE_REGISTRO) as clave:
            guardado, _tipo = winreg.QueryValueEx(clave, valor)
            return str(guardado)
    except OSError:
        return None


def _escribir_en_el_registro(valor, texto):
    try:
        import winreg
    except ImportError:
        return
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, CLAVE_REGISTRO) as clave:
            winreg.SetValueEx(clave, valor, 0, winreg.REG_SZ, texto)
    except OSError:
        pass


# ------------------------------------------------------------------ la base

def _leer_de_la_base(clave):
    try:
        with consulta() as (_conexion, cursor):
            cursor.execute("SELECT valor FROM marcas_licencia WHERE clave=?", (clave,))
            fila = cursor.fetchone()
            return fila[0] if fila else None
    except Exception:  # noqa: BLE001
        return None


def _escribir_en_la_base(clave, texto):
    try:
        with transaccion() as (_conexion, cursor):
            cursor.execute(
                "INSERT INTO marcas_licencia (clave, valor) VALUES (?, ?) "
                "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor",
                (clave, texto))
    except Exception:  # noqa: BLE001
        pass


def _ultima_del_historial():
    """El día de la última operación registrada, o None.

    El historial se escribe solo con cada venta, cada merma y cada movimiento
    de caja. No está puesto ahí como candado, y por eso es el que menos
    probable es que a alguien se le ocurra tocar.
    """
    try:
        with consulta() as (_conexion, cursor):
            cursor.execute("SELECT MAX(fecha) FROM historial")
            fila = cursor.fetchone()
    except Exception:  # noqa: BLE001
        return None
    return _a_fecha(fila[0][:10] if fila and fila[0] else None)


# ------------------------------------------------------------- la marca de agua

def _a_fecha(texto):
    if not texto:
        return None
    try:
        return datetime.date.fromisoformat(str(texto)[:10])
    except ValueError:
        return None


def marca_maxima():
    """La fecha más alta que este programa ha visto, o None si no hay ninguna."""
    candidatas = [_a_fecha(_leer_de_la_base(VALOR_MARCA)),
                  _a_fecha(_leer_del_registro(VALOR_MARCA)),
                  _ultima_del_historial()]
    vistas = [f for f in candidatas if f]
    return max(vistas) if vistas else None


def anotar_marca(hoy):
    """Sube la marca a `hoy`, si es más alta que la que había.

    Nunca baja: si bajara, bastaría con abrir el programa una vez con el reloj
    atrasado para borrar el rastro y volver a empezar.
    """
    anterior = marca_maxima()
    if anterior and anterior >= hoy:
        return
    texto = hoy.isoformat()
    _escribir_en_la_base(VALOR_MARCA, texto)
    _escribir_en_el_registro(VALOR_MARCA, texto)


def reloj_atrasado(hoy, marca):
    """¿El reloj del sistema va por detrás de lo que este programa ya vio?

    Función pura a propósito: la decisión se prueba con dos fechas, sin tocar
    la hora de Windows.
    """
    if marca is None:
        return False
    return hoy < marca - datetime.timedelta(days=DIAS_DE_MARGEN)


# --------------------------------------------------------------- la cortesía

def primer_arranque(hoy):
    """El día en que este programa se abrió por primera vez aquí.

    Lo fija la primera vez y no se mueve más: si se moviera, los siete días de
    cortesía no se acabarían nunca. Se guarda en los mismos dos sitios que la
    marca, por la misma razón.
    """
    guardado = _a_fecha(_leer_de_la_base(VALOR_PRIMER_ARRANQUE) or
                        _leer_del_registro(VALOR_PRIMER_ARRANQUE))
    if guardado:
        return guardado
    texto = hoy.isoformat()
    _escribir_en_la_base(VALOR_PRIMER_ARRANQUE, texto)
    _escribir_en_el_registro(VALOR_PRIMER_ARRANQUE, texto)
    return hoy
