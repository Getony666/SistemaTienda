"""El cuadre del corte de caja: qué debería haber en la gaveta y por qué.

La pantalla de Corte enseña tres monedas -CUP, USD y EUR- y, de cada una, una
cadena de sumas y restas que termina en la cifra que debería estar en la
gaveta. Aquí se arma esa cadena.

Dos reglas que conviene tener presentes al leer esto:

- **Nada se arrastra de un día para otro.** La gaveta se vacía todas las
  noches y el fondo se teclea cada mañana, así que cada día se calcula con
  los movimientos de ese día y nada más. Para las divisas eso ya era así:
  `fondo_divisas` guarda una fila por fecha y empieza en cero.

- **La cadena y la lista de movimientos tienen que cuadrar entre sí.** Lo que
  se suma aquí es exactamente lo que `obtener_movimientos_del_dia` enseña, ni
  una línea más ni una menos. Por eso las dos excluyen las mismas filas.

Dos clases de fila de `entradas_efectivo` se dejan fuera a propósito:

- Las que dicen `Pago de deuda #...`: son el rastro de un cobro que ya se
  cuenta por `cobros_deudas`. Contarlas sería contar el dinero dos veces.
- Las que dicen `Venta de ... (tasa ...)`: las escribe `registrar_operacion_cambio`
  cuando se vende divisa, y esa operación ya entra por `operaciones_cambio`.

Mirar la descripción para reconocerlas no es bonito, pero es lo que hay: esas
filas no llevan ninguna marca que las distinga, y el resto del programa
-`obtener_resumen_caja`, `revertir_registro`- ya las reconoce igual.
"""

from .caja import (
    RASTRO_DE_CAMBIO,
    RASTRO_DE_COBRO,
    cargar_fondo_por_fecha,
    obtener_saldo_divisas,
)
from .rutas import consulta

MONEDAS = ("CUP", "USD", "EUR")
DIVISAS = ("USD", "EUR")


def _uno(cursor, sql, parametros):
    """Primera columna de la primera fila, o 0.0 si no hay nada."""
    cursor.execute(sql, parametros)
    fila = cursor.fetchone()
    return (fila[0] or 0.0) if fila else 0.0


def _dos(cursor, sql, parametros):
    """(cantidad, total) de una consulta que devuelve COUNT y SUM."""
    cursor.execute(sql, parametros)
    fila = cursor.fetchone()
    if not fila:
        return 0, 0.0
    return int(fila[0] or 0), float(fila[1] or 0.0)


def _linea(clave, titulo, signo, monto, cuenta=""):
    return {
        "clave": clave,
        "titulo": titulo,
        "signo": signo,
        "monto": round(monto, 2),
        "cuenta": cuenta,
    }


def _plural(n, singular, plural):
    return f"{n} {singular if n == 1 else plural}"


# --------------------------------------------------------------------- CUP

def _cadena_cup(cursor, fecha):
    ff = f"{fecha}%"

    fondo = cargar_fondo_por_fecha(fecha)

    ventas_cant, ventas_total = _dos(cursor, '''
        SELECT COUNT(*), SUM(monto_efectivo) FROM ventas
        WHERE fecha LIKE ? AND cancelada = 0 AND es_deuda = 0 AND monto_efectivo > 0
    ''', (ff,))

    cobros_cant, cobros_total = _dos(cursor, '''
        SELECT COUNT(*), SUM(monto) FROM cobros_deudas
        WHERE fecha LIKE ? AND metodo_pago = 'Efectivo' AND moneda = 'CUP'
    ''', (ff,))

    vendidas_cant, vendidas_total = _dos(cursor, '''
        SELECT COUNT(*), SUM(monto_cup) FROM operaciones_cambio
        WHERE fecha LIKE ? AND tipo = 'venta'
    ''', (ff,))

    entradas_cant, entradas_total = _dos(cursor, f'''
        SELECT COUNT(*), SUM(monto) FROM entradas_efectivo
        WHERE fecha LIKE ? AND moneda = 'CUP'
          AND COALESCE(descripcion, '') NOT LIKE ?
          AND COALESCE(descripcion, '') NOT LIKE ?
    ''', (ff, RASTRO_DE_COBRO, RASTRO_DE_CAMBIO))

    salidas_cant, salidas_total = _dos(cursor, '''
        SELECT COUNT(*), SUM(monto) FROM salidas_efectivo
        WHERE fecha LIKE ? AND moneda = 'CUP'
    ''', (ff,))

    compradas_cant, compradas_total = _dos(cursor, '''
        SELECT COUNT(*), SUM(monto_cup) FROM operaciones_cambio
        WHERE fecha LIKE ? AND tipo = 'compra'
    ''', (ff,))

    # El fondo se queda siempre, aunque sea cero: que esté en blanco a media
    # mañana es justo lo que hay que ver.
    lineas = [_linea("fondo", "Fondo con que se abrió", "", fondo,
                     "" if fondo else "todavía sin poner")]
    lineas += [
        _linea("ventas", "Ventas cobradas en efectivo", "+", ventas_total,
               _plural(ventas_cant, "venta", "ventas")),
        _linea("cobros", "Cobros de deudas en efectivo", "+", cobros_total,
               _plural(cobros_cant, "cobro", "cobros")),
        _linea("venta_divisa", "Venta de divisas", "+", vendidas_total,
               _plural(vendidas_cant, "operación", "operaciones")),
        _linea("entradas", "Otras entradas de efectivo", "+", entradas_total,
               _plural(entradas_cant, "apunte", "apuntes")),
        _linea("salidas", "Salidas de efectivo", "-", salidas_total,
               _plural(salidas_cant, "apunte", "apuntes")),
        _linea("compra_divisa", "Compra de divisas", "-", compradas_total,
               _plural(compradas_cant, "operación", "operaciones")),
    ]

    esperado = (fondo + ventas_total + cobros_total + vendidas_total
                + entradas_total - salidas_total - compradas_total)
    return lineas, round(esperado, 2)


# ----------------------------------------------------------------- divisas

def _cadena_divisa(cursor, fecha, moneda):
    ff = f"{fecha}%"

    compradas_cant, compradas_total = _dos(cursor, '''
        SELECT COUNT(*), SUM(cantidad) FROM operaciones_cambio
        WHERE fecha LIKE ? AND tipo = 'compra' AND moneda = ?
    ''', (ff, moneda))

    ventas_cant, ventas_total = _dos(cursor, '''
        SELECT COUNT(*), SUM(monto_divisa_neto) FROM ventas
        WHERE fecha LIKE ? AND cancelada = 0 AND es_deuda = 0
          AND moneda_pago = ? AND monto_divisa_neto > 0
    ''', (ff, moneda))

    # Un cobro en divisa puede dejar saldo negativo: pasa cuando el vuelto en
    # divisa es mayor que lo que el cliente entregó en divisa. Sale de la
    # gaveta, así que va como resta y no como suma en negativo.
    cobros_cant, cobros_total = _dos(cursor, '''
        SELECT COUNT(*), SUM(monto_divisa_neto) FROM cobros_deudas
        WHERE fecha LIKE ? AND metodo_pago = 'Efectivo' AND moneda = ?
          AND monto_divisa_neto > 0
    ''', (ff, moneda))
    vueltos_cant, vueltos_total = _dos(cursor, '''
        SELECT COUNT(*), -SUM(monto_divisa_neto) FROM cobros_deudas
        WHERE fecha LIKE ? AND metodo_pago = 'Efectivo' AND moneda = ?
          AND monto_divisa_neto < 0
    ''', (ff, moneda))

    entradas_cant, entradas_total = _dos(cursor, '''
        SELECT COUNT(*), SUM(monto) FROM entradas_efectivo
        WHERE fecha LIKE ? AND moneda = ?
    ''', (ff, moneda))

    salidas_cant, salidas_total = _dos(cursor, '''
        SELECT COUNT(*), SUM(monto) FROM salidas_efectivo
        WHERE fecha LIKE ? AND moneda = ?
    ''', (ff, moneda))

    vendidas_cant, vendidas_total = _dos(cursor, '''
        SELECT COUNT(*), SUM(cantidad) FROM operaciones_cambio
        WHERE fecha LIKE ? AND tipo = 'venta' AND moneda = ?
    ''', (ff, moneda))

    lineas = [
        _linea("compra_divisa", "Divisas compradas", "+", compradas_total,
               _plural(compradas_cant, "operación", "operaciones")),
        _linea("ventas", f"Ventas cobradas en {moneda}", "+", ventas_total,
               _plural(ventas_cant, "venta", "ventas")),
        _linea("cobros", "Cobros de deudas", "+", cobros_total,
               _plural(cobros_cant, "cobro", "cobros")),
        _linea("entradas", "Otras entradas", "+", entradas_total,
               _plural(entradas_cant, "apunte", "apuntes")),
        _linea("vueltos", "Vueltos en divisa", "-", vueltos_total,
               _plural(vueltos_cant, "vuelto", "vueltos")),
        _linea("salidas", "Salidas", "-", salidas_total,
               _plural(salidas_cant, "apunte", "apuntes")),
        _linea("venta_divisa", "Divisas vendidas", "-", vendidas_total,
               _plural(vendidas_cant, "operación", "operaciones")),
    ]

    calculado = (compradas_total + ventas_total + cobros_total + entradas_total
                 - vueltos_total - salidas_total - vendidas_total)

    # La cifra que manda es la guardada en `fondo_divisas`: es contra ella
    # contra la que el programa comprueba si se puede sacar divisa de la
    # caja. Si por lo que sea no coincide con lo que suman las líneas, la
    # diferencia se enseña en vez de esconderse.
    guardado = round(float(obtener_saldo_divisas(fecha).get(moneda, 0.0) or 0.0), 2)
    desfase = round(guardado - round(calculado, 2), 2)
    if abs(desfase) >= 0.01:
        lineas.append(_linea("ajuste", "Ajustes sin clasificar",
                             "+" if desfase > 0 else "-", abs(desfase)))

    return lineas, guardado


# ------------------------------------------------------------------ armado

def armar_cuadre(fecha):
    """Las tres monedas, cada una con su cadena y su cifra esperada.

    Las líneas en cero se van: una cadena de diez renglones donde ocho dicen
    0.00 no explica nada. El fondo del CUP se queda siempre.
    """
    cuadre = {}
    with consulta() as (_, cursor):
        for moneda in MONEDAS:
            if moneda == "CUP":
                lineas, esperado = _cadena_cup(cursor, fecha)
            else:
                lineas, esperado = _cadena_divisa(cursor, fecha, moneda)
            cuadre[moneda] = {
                "esperado": esperado,
                "cadena": [ln for ln in lineas
                           if ln["monto"] or ln["clave"] == "fondo"],
            }
    return cuadre
