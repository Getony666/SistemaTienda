"""Lo que el historial enseña por pantalla: los totales y el detalle de una fila.

Aquí no se calcula nada nuevo. Se lee lo que ya está guardado y se traduce a
frases: la pantalla no tiene por qué saber que una deuda a medio cobrar vive
en `saldo_pendiente`, ni el cajero tiene por qué leer `metodo_pago_real`.

El detalle se pide de uno en uno, cuando alguien selecciona una fila. Por eso
la lista puede seguir siendo ligera: las líneas de cada venta, que son lo que
más pesa, sólo se leen de la que se está mirando.
"""

import datetime
import json

from .rutas import consulta
from .ventas_datos import _nombre_del_cliente, obtener_ventas

MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre")


def _plata(monto):
    """Un número de dinero como se lee en la tienda: 42 000.00, no 42000.0."""
    return f"{(monto or 0):,.2f}".replace(",", " ")


def _cuando(fecha):
    """La fecha dicha como la diría una persona: 'Hoy 20:17', '8 sep 14:25'."""
    if not fecha:
        return ""
    try:
        momento = datetime.datetime.strptime(fecha[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return fecha
    hoy = datetime.date.today()
    dias = (hoy - momento.date()).days
    hora = momento.strftime("%H:%M")
    if dias == 0:
        return f"Hoy {hora}"
    if dias == 1:
        return f"Ayer {hora}"
    return f"{momento.day} de {MESES[momento.month - 1]} {hora}"


def _seccion(nombre, tipo, filas):
    """Una sección del detalle, o nada si no hay qué enseñar."""
    filas = [f for f in filas if f]
    return {"nombre": nombre, "tipo": tipo, "filas": filas} if filas else None


def _par(texto, valor, color=None):
    """Una línea 'etiqueta → valor'. Si el valor viene vacío, no hay línea."""
    if valor in (None, "", "0.00 CUP"):
        return None
    fila = {"texto": texto, "derecha": str(valor)}
    if color:
        fila["color"] = color
    return fila


def resumen_historial(filtro_fecha=None, filtro_metodo="todos", filtro_tipo="todos",
                      producto_id=None, buscar=None, filtro_usuario=None):
    """Las cifras de arriba de la pantalla: cuánto entró, cuánto salió, cuánto falta.

    Resume el filtro entero, no la página que se está viendo: si alguien filtra
    por "hoy" quiere saber cuánto se vendió hoy, no cuánto suman las cincuenta
    líneas que le caben en la pantalla. Por eso pide la lista sin recortar.
    """
    registros = obtener_ventas(filtro_fecha=filtro_fecha, filtro_metodo=filtro_metodo,
                               filtro_tipo=filtro_tipo, producto_id=producto_id,
                               buscar=buscar, filtro_usuario=filtro_usuario)
    entro = salio = por_cobrar = ganancia = 0.0
    divisas = {}
    for registro in registros:
        monto = registro.get("monto") or 0.0
        moneda = registro.get("moneda") or "CUP"
        signo = registro.get("signo")
        if registro.get("tipo") == "Deuda":
            # Una deuda no es dinero que entró ni que salió: es dinero que falta.
            por_cobrar += monto
        elif moneda == "CUP":
            if signo == "entra":
                entro += monto
            elif signo == "sale":
                salio += monto
        else:
            neto = monto if signo == "entra" else -monto if signo == "sale" else 0.0
            divisas[moneda] = round(divisas.get(moneda, 0.0) + neto, 4)
        if registro.get("utilidad"):
            ganancia += registro["utilidad"]

    return {
        "registros": len(registros),
        "entro": round(entro, 2),
        "salio": round(salio, 2),
        "por_cobrar": round(por_cobrar, 2),
        "ganancia": round(ganancia, 2),
        "divisas": divisas,
        "usuarios": _quienes_han_registrado_algo(),
    }


def _quienes_han_registrado_algo():
    """Los nombres que aparecen en el historial, para el selector de usuario.

    No se sacan de la tabla de usuarios porque esa ruta pide permiso de Admin y
    el selector tiene que verlo cualquiera que pueda mirar el historial. Y no
    se sacan tampoco de los registros ya filtrados: si al elegir a alguien la
    lista se quedara con ese solo nombre, no habría forma de volver atrás.
    """
    nombres = set()
    with consulta() as (_conexion, cursor):
        for tabla in ("ventas", "entradas_efectivo", "salidas_efectivo",
                      "operaciones_cambio", "salidas_inventario", "historial"):
            try:
                cursor.execute(
                    f"SELECT DISTINCT usuario FROM {tabla} WHERE usuario IS NOT NULL AND usuario != ''")
            except Exception:
                # Una base vieja puede no tener todavía la columna usuario en
                # alguna de estas tablas; no es motivo para quedarse sin lista.
                continue
            nombres.update(fila[0] for fila in cursor.fetchall())
    return sorted(nombres)


def detalle_de_registro(tipo, id_reg):
    """Todo lo que se sabe de una fila, ya escrito para leerse.

    Devuelve None si el registro no existe: quien llame decide si eso es un 404.
    """
    with consulta() as (_conexion, cursor):
        if tipo in ("Venta", "Deuda"):
            return _detalle_de_venta(cursor, id_reg, tipo)
        if tipo in ("Entrada de efectivo", "Salida de efectivo"):
            return _detalle_de_caja(cursor, id_reg, tipo)
        if tipo in ("Cambio de Divisa", "cambio"):
            return _detalle_de_cambio(cursor, id_reg)
        if tipo == "Merma":
            return _detalle_de_merma(cursor, id_reg)
        return _detalle_de_historial(cursor, id_reg, tipo)


def _lineas_de_venta(cursor, venta_id, total):
    """Qué se llevó el cliente, con su cuenta al pie."""
    filas = []
    cursor.execute('''
        SELECT p.nombre, dv.cantidad, dv.precio_unitario
        FROM detalles_venta dv JOIN productos p ON dv.producto_id = p.id
        WHERE dv.venta_id = ? ORDER BY p.nombre
    ''', (venta_id,))
    for nombre, cantidad, precio in cursor.fetchall():
        filas.append({"texto": nombre,
                      "medio": f"{cantidad:g} × {_plata(precio)}",
                      "derecha": _plata(cantidad * precio)})
    if filas:
        filas.append({"texto": "Total", "medio": "", "derecha": _plata(total), "fuerte": True})
    return filas


def _detalle_de_venta(cursor, venta_id, tipo):
    cursor.execute('''
        SELECT fecha, total, metodo_pago_real, metodo_pago, moneda_pago, tasa_cambio,
               pago_texto, vuelto_texto, utilidad, es_deuda, saldo_pendiente,
               observaciones, usuario, es_mensajeria
        FROM ventas WHERE id = ?
    ''', (venta_id,))
    fila = cursor.fetchone()
    if not fila:
        return None
    (fecha, total, metodo_real, metodo, moneda, tasa, pago_texto, vuelto_texto,
     utilidad, es_deuda, saldo, observaciones, usuario, es_mensajeria) = fila

    metodo_visible = metodo_real or metodo or ""
    secciones = [_seccion("Qué se llevó", "lineas", _lineas_de_venta(cursor, venta_id, total))]

    if es_deuda and not _esta_pagada(cursor, venta_id):
        abonos = cursor.execute('''
            SELECT fecha, metodo_pago, monto, moneda FROM cobros_deudas
            WHERE venta_id = ? ORDER BY fecha
        ''', (venta_id,)).fetchall()
        abonado = sum(m for (_f, _m, m, _mo) in abonos)
        secciones.append(_seccion("La deuda", "pares", [
            _par("Cliente", _nombre_del_cliente(observaciones) or None),
            _par("Total de la deuda", f"{_plata(total)} CUP"),
            _par("Lleva abonado", f"{_plata(abonado)} CUP", "verde" if abonado else None),
            _par("Falta", f"{_plata(saldo if saldo is not None else total)} CUP", "ocre"),
        ]))
        secciones.append(_seccion("Abonos", "lineas", [
            {"texto": _cuando(f_abono), "medio": metodo_abono or "",
             "derecha": f"{_plata(monto)} {moneda_abono or 'CUP'}"}
            for f_abono, metodo_abono, monto, moneda_abono in abonos
        ]))
        titulo = f"Deuda nº {venta_id} · falta {_plata(saldo if saldo is not None else total)} CUP"
    else:
        cobro = [
            _par("Método", metodo_visible),
            _par("Pagó", pago_texto),
            _par("Vuelto", vuelto_texto),
        ]
        if moneda and moneda != "CUP" and tasa:
            cobro.append(_par("Tasa del día", f"{tasa:g} CUP por {moneda}"))
            cobro.append(_par("En pesos", f"{_plata(total)} CUP"))
        if utilidad:
            cobro.append(_par("Ganancia de esta venta", f"+{_plata(utilidad)} CUP", "verde"))
        secciones.append(_seccion("El cobro", "pares", cobro))
        if observaciones:
            secciones.append(_seccion("Nota", "pares", [_par("Se apuntó", observaciones)]))
        titulo = f"Venta nº {venta_id} · {_plata(total)} CUP"

    quien = f" · cobró {usuario}" if usuario else ""
    reparto = " · mensajería" if es_mensajeria else ""
    return {
        "titulo": titulo,
        "subtitulo": f"{_cuando(fecha)}{quien}{reparto}",
        "secciones": [s for s in secciones if s],
    }


def _esta_pagada(cursor, venta_id):
    fila = cursor.execute("SELECT pagada FROM ventas WHERE id = ?", (venta_id,)).fetchone()
    return bool(fila and fila[0])


def _detalle_de_caja(cursor, id_reg, tipo):
    tabla = "entradas_efectivo" if tipo == "Entrada de efectivo" else "salidas_efectivo"
    fila = cursor.execute(
        f"SELECT fecha, moneda, monto, descripcion, usuario FROM {tabla} WHERE id = ?",
        (id_reg,)).fetchone()
    if not fila:
        return None
    fecha, moneda, monto, descripcion, usuario = fila
    entra = tipo == "Entrada de efectivo"
    return {
        "titulo": f"{tipo} · {_plata(monto)} {moneda or 'CUP'}",
        "subtitulo": f"{_cuando(fecha)}{f' · lo registró {usuario}' if usuario else ''}",
        "secciones": [s for s in [_seccion("El movimiento", "pares", [
            _par("Concepto", descripcion),
            _par("Moneda", moneda or "CUP"),
            _par("Entra a la caja" if entra else "Sale de la caja",
                 f"{_plata(monto)} {moneda or 'CUP'}", "verde" if entra else "rojo"),
        ])] if s],
    }


def _detalle_de_cambio(cursor, id_reg):
    fila = cursor.execute('''
        SELECT fecha, tipo, moneda, cantidad, tasa, monto_cup, observaciones, usuario
        FROM operaciones_cambio WHERE id = ?
    ''', (id_reg,)).fetchone()
    if not fila:
        return None
    fecha, tipo_op, moneda, cantidad, tasa, monto_cup, observaciones, usuario = fila
    comprando = str(tipo_op or "").lower() == "compra"
    return {
        "titulo": f"{'Compra' if comprando else 'Venta'} de {_plata(cantidad)} {moneda}",
        "subtitulo": f"{_cuando(fecha)}{f' · la hizo {usuario}' if usuario else ''}",
        "secciones": [s for s in [_seccion("La operación", "pares", [
            _par("Divisa", f"{_plata(cantidad)} {moneda}",
                 "verde" if comprando else "rojo"),
            _par("Tasa", f"{tasa:g} CUP por {moneda}"),
            _par("Salieron de la caja" if comprando else "Entraron a la caja",
                 f"{_plata(monto_cup)} CUP", "rojo" if comprando else "verde"),
            _par("Nota", observaciones),
        ])] if s],
    }


def _detalle_de_merma(cursor, id_reg):
    fila = cursor.execute('''
        SELECT s.fecha, p.nombre, s.cantidad, s.precio_costo, s.motivo, s.usuario
        FROM salidas_inventario s JOIN productos p ON s.producto_id = p.id
        WHERE s.id = ?
    ''', (id_reg,)).fetchone()
    if not fila:
        return None
    fecha, nombre, cantidad, costo, motivo, usuario = fila
    return {
        "titulo": f"Merma · {_plata(cantidad * costo)} CUP",
        "subtitulo": f"{_cuando(fecha)}{f' · la apuntó {usuario}' if usuario else ''}",
        "secciones": [s for s in [_seccion("Lo que se perdió", "pares", [
            _par("Producto", nombre),
            _par("Cantidad", f"{cantidad:g}"),
            _par("Costo de cada uno", f"{_plata(costo)} CUP"),
            _par("Costo total", f"{_plata(cantidad * costo)} CUP", "rojo"),
            _par("Motivo", motivo),
        ])] if s],
    }


def _detalle_de_historial(cursor, id_reg, tipo):
    """Altas, bajas, correcciones de ficha y salidas de mercancía.

    Lo que se guardó en su día es un JSON suelto, distinto en cada acción. Se
    enseña lo que se reconoce, y lo demás se deja pasar en silencio antes que
    escupir nombres de columna por pantalla.
    """
    fila = cursor.execute(
        "SELECT fecha, tipo_accion, descripcion, detalles, usuario FROM historial WHERE id = ?",
        (id_reg,)).fetchone()
    if not fila:
        return None
    fecha, tipo_accion, descripcion, detalles_json, usuario = fila
    try:
        detalles = json.loads(detalles_json) if detalles_json else {}
    except (ValueError, TypeError):
        detalles = {}
    if not isinstance(detalles, dict):
        detalles = {}

    pares = [_par("Qué pasó", descripcion)]

    # Las correcciones de ficha se guardan como pares "algo_antes"/"algo_ahora".
    # Enseñarlas como "180.00 → 200.00" es lo único que le interesa a nadie.
    for clave in sorted(detalles):
        if not clave.endswith("_antes"):
            continue
        raiz = clave[:-len("_antes")]
        if f"{raiz}_ahora" in detalles:
            etiqueta = raiz.replace("_", " ").capitalize()
            pares.append(_par(etiqueta, f"{detalles[clave]} → {detalles[f'{raiz}_ahora']}"))

    for clave, etiqueta in (("nombre", "Producto"), ("cantidad", "Cantidad"),
                            ("motivo", "Motivo"), ("proveedor", "Proveedor"),
                            ("categoria", "Categoría")):
        if detalles.get(clave) is not None:
            pares.append(_par(etiqueta, detalles[clave]))

    secciones = [_seccion("El movimiento", "pares", pares)]

    lineas = detalles.get("lineas")
    if lineas:
        nombres = {f[0]: f[1] for f in cursor.execute("SELECT id, nombre FROM productos")}
        secciones.append(_seccion("Lo que salió", "lineas", [
            {"texto": nombres.get(linea.get("producto_id"), "Producto borrado"),
             "medio": f"{linea.get('cantidad', 0):g}", "derecha": ""}
            for linea in lineas
        ]))

    return {
        "titulo": tipo_accion or tipo,
        "subtitulo": f"{_cuando(fecha)}{f' · lo hizo {usuario}' if usuario else ''}",
        "secciones": [s for s in secciones if s],
    }
