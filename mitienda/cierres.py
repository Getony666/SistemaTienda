"""El cierre de caja del día: la foto que queda cuando se cuenta el dinero.

Cerrar no traba nada. Es a propósito: en una tienda de barrio el cliente
entra a las ocho y media aunque la caja ya se haya contado, y dejar a la
dependienta sin poder cobrar sería peor que tener que volver a contar. Lo que
se guarda es una foto con hora; si después de esa hora hubo movimientos, la
pantalla lo dice y ofrece volver a contar.

Cada día se guarda entero y ninguno alimenta al siguiente: la gaveta se vacía
todas las noches y el fondo se teclea cada mañana. Estas filas sirven para
mirar hacia atrás, no para arrastrar nada hacia delante.

El cierre no se apunta en el Historial. Allí sólo van cosas que se pueden
deshacer una a una, y un cierre no se deshace: se reabre y se vuelve a
contar, que es otra cosa.
"""

import datetime

from .caja import cargar_fondo_por_fecha
from .cuadre import MONEDAS, armar_cuadre
from .rutas import consulta, transaccion
from . import sesion

# Las tablas donde puede aparecer actividad posterior a un cierre. La columna
# de la fecha se llama igual en todas.
TABLAS_CON_MOVIMIENTO = (
    "ventas", "cobros_deudas", "entradas_efectivo",
    "salidas_efectivo", "operaciones_cambio",
)


def _ahora():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _contar_movimientos_despues(cursor, fecha, momento):
    """Cuántos apuntes de ese día llegaron después de la hora del cierre."""
    total = 0
    for tabla in TABLAS_CON_MOVIMIENTO:
        cursor.execute(
            f"SELECT COUNT(*) FROM {tabla} WHERE fecha LIKE ? AND fecha > ?",
            (f"{fecha}%", momento),
        )
        fila = cursor.fetchone()
        total += int(fila[0] or 0) if fila else 0
    return total


def _fila_a_cierre(fila, movimientos_despues=0):
    (fecha, cerrado_en, usuario, esperado_cup, contado_cup, esperado_usd,
     contado_usd, esperado_eur, contado_eur, fondo, ventas_dia, utilidad_dia,
     transferencias, deudas_pendientes, nota) = fila

    esperado = {"CUP": esperado_cup, "USD": esperado_usd, "EUR": esperado_eur}
    contado = {"CUP": contado_cup, "USD": contado_usd, "EUR": contado_eur}
    return {
        "fecha": fecha,
        "cerrado_en": cerrado_en,
        "hora": (cerrado_en or "")[11:16],
        "usuario": usuario or "",
        "esperado": {m: round(esperado[m] or 0.0, 2) for m in MONEDAS},
        "contado": {m: round(contado[m] or 0.0, 2) for m in MONEDAS},
        "diferencia": {m: round((contado[m] or 0.0) - (esperado[m] or 0.0), 2)
                       for m in MONEDAS},
        "fondo": round(fondo or 0.0, 2),
        "ventas_dia": round(ventas_dia or 0.0, 2),
        "utilidad_dia": round(utilidad_dia or 0.0, 2),
        "transferencias": round(transferencias or 0.0, 2),
        "deudas_pendientes": round(deudas_pendientes or 0.0, 2),
        "nota": nota or "",
        "movimientos_despues": movimientos_despues,
    }


COLUMNAS = '''fecha, cerrado_en, usuario, esperado_cup, contado_cup,
              esperado_usd, contado_usd, esperado_eur, contado_eur, fondo,
              ventas_dia, utilidad_dia, transferencias, deudas_pendientes, nota'''


def obtener_cierre(fecha):
    """El cierre de ese día, o None si todavía no se ha cerrado."""
    with consulta() as (_, cursor):
        cursor.execute(f"SELECT {COLUMNAS} FROM cierres_caja WHERE fecha = ?", (fecha,))
        fila = cursor.fetchone()
        if not fila:
            return None
        despues = _contar_movimientos_despues(cursor, fecha, fila[1])
        return _fila_a_cierre(fila, despues)


def ultimos_cierres(limite=10):
    """Los últimos días cerrados, del más reciente al más viejo."""
    with consulta() as (_, cursor):
        cursor.execute(
            f"SELECT {COLUMNAS} FROM cierres_caja ORDER BY fecha DESC LIMIT ?",
            (int(limite),),
        )
        return [_fila_a_cierre(fila) for fila in cursor.fetchall()]


def cerrar_caja(fecha, contado, nota=""):
    """Guarda la foto del día. Vuelto a llamar sobre el mismo día, la sustituye.

    `contado` es lo que la persona contó de cada moneda. Lo esperado no se
    recibe: se calcula aquí en el momento de cerrar, para que nadie pueda
    mandar una cifra esperada que le convenga.
    """
    cuadre = armar_cuadre(fecha)
    esperado = {m: cuadre[m]["esperado"] for m in MONEDAS}
    contado = {m: round(float(contado.get(m, 0.0) or 0.0), 2) for m in MONEDAS}

    from .caja import obtener_resumen_caja
    resumen = obtener_resumen_caja(fecha)

    momento = _ahora()
    try:
        with transaccion() as (conexion, cursor):
            cursor.execute(f'''
                INSERT OR REPLACE INTO cierres_caja ({COLUMNAS})
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                fecha, momento, sesion.usuario_actual(),
                esperado["CUP"], contado["CUP"],
                esperado["USD"], contado["USD"],
                esperado["EUR"], contado["EUR"],
                cargar_fondo_por_fecha(fecha),
                resumen.get("total_ventas_dia", 0.0),
                resumen.get("utilidad_total", 0.0),
                resumen.get("ventas_transferencia", {}).get("total", 0.0),
                resumen.get("deudas_pendientes_dia", {}).get("total", 0.0),
                (nota or "").strip(),
            ))
    except Exception as e:
        return False, f"No se pudo cerrar la caja: {e}"

    diferencias = [f"{m} {contado[m] - esperado[m]:+.2f}"
                   for m in MONEDAS if abs(contado[m] - esperado[m]) >= 0.01]
    if diferencias:
        return True, "Caja cerrada. Diferencia: " + ", ".join(diferencias)
    return True, "Caja cerrada. Todo cuadra."


def reabrir_caja(fecha):
    """Borra el cierre de ese día para poder volver a contar."""
    try:
        with transaccion() as (conexion, cursor):
            cursor.execute("DELETE FROM cierres_caja WHERE fecha = ?", (fecha,))
            if cursor.rowcount == 0:
                return False, "Ese día no estaba cerrado"
    except Exception as e:
        return False, f"No se pudo reabrir la caja: {e}"
    return True, "Caja reabierta. Vuelve a contar y ciérrala otra vez."
