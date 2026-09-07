"""Lectura y escritura de ventas, deudas y cobros."""

import datetime
import json

from .caja import actualizar_fondo
from .rutas import conectar_db, consulta


def _obtener_total_cobros(venta_id):
    try:
        with consulta() as (_conn, cursor):
            cursor.execute("SELECT SUM(monto) FROM cobros_deudas WHERE venta_id = ?", (venta_id,))
            total = cursor.fetchone()[0]
        return total if total is not None else 0.0
    except Exception:
        return 0.0

def _fila_historial_es_del_producto(tipo_accion, detalles_json, producto_id, producto_nombre):
    """¿Esta fila del historial habla del producto pedido?

    Cada tipo_accion guarda el producto de una forma distinta: las salidas y
    mermas con "producto_id", el alta/edición/baja con "id", y el alta a veces
    sólo con el nombre. Se compara sobre el JSON ya parseado porque un LIKE
    sobre el texto confunde el producto 1 con el 12."""
    try:
        detalles = json.loads(detalles_json) if detalles_json else {}
    except (ValueError, TypeError):
        return False
    if not isinstance(detalles, dict):
        return False

    def _mismo_id(valor):
        try:
            return int(valor) == producto_id
        except (TypeError, ValueError):
            return False

    if _mismo_id(detalles.get("producto_id")):
        return True
    if tipo_accion in ("Actualización de Producto", "Eliminación de Producto") and _mismo_id(detalles.get("id")):
        return True
    if producto_nombre and detalles.get("nombre") == producto_nombre:
        return True
    return False


def _texto_productos(nombres):
    """Resume para la columna Producto los artículos de una línea."""
    if not nombres:
        return ""
    if len(nombres) <= 2:
        return ", ".join(nombres)
    return f"{nombres[0]}, {nombres[1]} +{len(nombres) - 2}"


def _productos_por_venta(cursor, ids_ventas):
    """Nombres de los productos de cada venta.

    Va por lotes porque SQLite limita el número de variables de un IN."""
    nombres = {}
    for inicio in range(0, len(ids_ventas), 400):
        lote = ids_ventas[inicio:inicio + 400]
        marcadores = ",".join("?" * len(lote))
        cursor.execute(f'''
            SELECT dv.venta_id, p.nombre
            FROM detalles_venta dv
            JOIN productos p ON dv.producto_id = p.id
            WHERE dv.venta_id IN ({marcadores})
            ORDER BY p.nombre
        ''', lote)
        for venta_id, nombre in cursor.fetchall():
            nombres.setdefault(venta_id, []).append(nombre)
    return nombres


def _producto_de_historial(cursor, detalles_json):
    """Nombre del producto al que se refiere una fila del historial.

    Unas acciones lo guardan literal y otras sólo dejan el id."""
    try:
        detalles = json.loads(detalles_json) if detalles_json else {}
    except (ValueError, TypeError):
        return ""
    if not isinstance(detalles, dict):
        return ""
    if detalles.get("nombre"):
        return detalles["nombre"]
    for clave in ("producto_id", "id"):
        if detalles.get(clave) is not None:
            cursor.execute("SELECT nombre FROM productos WHERE id = ?", (detalles[clave],))
            fila = cursor.fetchone()
            if fila:
                return fila[0]
    return ""


def obtener_ventas(filtro_fecha=None, filtro_metodo="todos", filtro_tipo="todos", producto_id=None):
    with consulta() as (conexion, cursor):
        resultados = []

        # El alta de producto sólo deja el nombre en el historial, así que hace
        # falta para poder cruzarla con el producto elegido.
        producto_nombre = None
        if producto_id is not None:
            cursor.execute("SELECT nombre FROM productos WHERE id = ?", (producto_id,))
            fila_producto = cursor.fetchone()
            if fila_producto:
                producto_nombre = fila_producto[0]

        if filtro_tipo in ("todos", "ventas", "deudas"):
            sentencia = '''
                SELECT v.id, v.fecha, v.total, v.metodo_pago, v.cancelada, v.es_deuda, v.pagada, v.saldo_pendiente,
                       v.metodo_pago_real, v.observaciones, v.moneda_pago, v.tasa_cambio, v.pago_texto, v.vuelto_texto, v.es_mensajeria
                FROM ventas v
                WHERE v.metodo_pago != 'Salida'
            '''
            params = []
            if filtro_fecha:
                sentencia += " AND v.fecha LIKE ?"
                params.append(f"{filtro_fecha}%")
            if filtro_metodo == "efectivo":
                sentencia += " AND v.metodo_pago_real = 'Efectivo'"
            elif filtro_metodo == "transferencia":
                sentencia += " AND v.metodo_pago_real = 'Transferencia'"
            elif filtro_metodo == "mixto":
                sentencia += " AND v.metodo_pago_real = 'Mixto'"
            if filtro_tipo == "deudas":
                sentencia += " AND v.es_deuda = 1"
            elif filtro_tipo == "ventas":
                sentencia += " AND v.es_deuda = 0"
            if producto_id is not None:
                sentencia += " AND EXISTS (SELECT 1 FROM detalles_venta dv WHERE dv.venta_id = v.id AND dv.producto_id = ?)"
                params.append(producto_id)
            sentencia += " ORDER BY v.fecha DESC"
            cursor.execute(sentencia, params)
            filas_ventas = cursor.fetchall()
            productos_de_venta = _productos_por_venta(cursor, [f[0] for f in filas_ventas]) if filas_ventas else {}
            for row in filas_ventas:
                (id_reg, fecha, total, metodo_pago, cancelada, es_deuda, pagada,
                 saldo_pendiente, metodo_pago_real, observaciones, moneda_pago,
                 tasa_cambio, pago_texto, vuelto_texto, es_mensajeria) = row
                if cancelada:
                    continue
                if es_deuda and pagada == 0:
                    tipo = "Deuda"
                    monto = saldo_pendiente if saldo_pendiente is not None else total
                    moneda = "CUP"
                    obs = observaciones if observaciones else ""
                    metodo_pago_mostrar = ""
                    detalle_extra = {"es_deuda": es_deuda, "pagada": pagada, "saldo_pendiente": saldo_pendiente, "total": total, "moneda_pago": moneda_pago, "tasa_cambio": tasa_cambio, "metodo_pago_real": metodo_pago_real, "pago_texto": pago_texto, "vuelto_texto": vuelto_texto, "es_mensajeria": es_mensajeria}
                elif es_deuda and pagada == 1:
                    tipo = "Venta"
                    monto = total
                    moneda = "CUP"
                    obs = observaciones if observaciones else "Deuda pagada"
                    metodo_pago_mostrar = metodo_pago_real if metodo_pago_real else metodo_pago
                    detalle_extra = {"es_deuda": es_deuda, "pagada": pagada, "saldo_pendiente": saldo_pendiente, "total": total, "moneda_pago": moneda_pago, "tasa_cambio": tasa_cambio, "metodo_pago_real": metodo_pago_real, "pago_texto": pago_texto, "vuelto_texto": vuelto_texto, "es_mensajeria": es_mensajeria}
                else:
                    tipo = "Venta"
                    if metodo_pago == "Efectivo" and moneda_pago != "CUP" and not es_deuda:
                        monto = total / tasa_cambio if tasa_cambio and tasa_cambio > 0 else total
                        moneda = moneda_pago
                    else:
                        monto = total
                        moneda = "CUP"
                    obs = observaciones if observaciones else ""
                    metodo_pago_mostrar = metodo_pago_real if metodo_pago_real else metodo_pago
                    detalle_extra = {"es_deuda": es_deuda, "pagada": pagada, "saldo_pendiente": saldo_pendiente, "total": total, "moneda_pago": moneda_pago, "tasa_cambio": tasa_cambio, "metodo_pago_real": metodo_pago_real, "pago_texto": pago_texto, "vuelto_texto": vuelto_texto, "es_mensajeria": es_mensajeria}
                resultados.append({
                    "tipo": tipo,
                    "id": id_reg,
                    "fecha": fecha,
                    "monto": monto,
                    "moneda": moneda,
                    "metodo_pago": metodo_pago_mostrar,
                    "producto": _texto_productos(productos_de_venta.get(id_reg, [])),
                    "observaciones": obs,
                    "detalle_extra": detalle_extra
                })

        # Los cambios de divisa y los movimientos de caja no tienen producto:
        # si se está filtrando por uno, no pintan nada en la lista.
        if filtro_tipo in ("todos", "cambio") and producto_id is None:
            sentencia = '''
                SELECT id, fecha, tipo, moneda, cantidad, tasa, monto_cup, observaciones
                FROM operaciones_cambio
                WHERE 1=1
            '''
            params = []
            if filtro_fecha:
                sentencia += " AND fecha LIKE ?"
                params.append(f"{filtro_fecha}%")
            sentencia += " ORDER BY fecha DESC"
            cursor.execute(sentencia, params)
            for row in cursor.fetchall():
                id_reg, fecha, tipo_op, moneda, cantidad, tasa, monto_cup, obs = row
                resultados.append({
                    # Igual que en los movimientos de efectivo, este texto es el
                    # que reconocen el panel de detalle y el borrado.
                    "tipo": "Cambio de Divisa",
                    "id": id_reg,
                    "fecha": fecha,
                    "monto": cantidad,
                    "moneda": moneda,
                    "metodo_pago": "Efectivo",
                    "producto": "",
                    "observaciones": f"Monto CUP: {monto_cup:.2f}",
                    "detalle_extra": {"tipo_op": tipo_op, "tasa": tasa, "moneda_original": moneda, "cantidad": cantidad, "monto_cup": monto_cup, "obs": obs}
                })

        if filtro_tipo in ("todos", "entrada_efectivo") and producto_id is None:
            sentencia = '''
                SELECT id, fecha, moneda, monto, descripcion
                FROM entradas_efectivo
                WHERE 1=1
            '''
            params = []
            if filtro_fecha:
                sentencia += " AND fecha LIKE ?"
                params.append(f"{filtro_fecha}%")
            sentencia += " ORDER BY fecha DESC"
            cursor.execute(sentencia, params)
            for row in cursor.fetchall():
                id_reg, fecha, moneda, monto, desc = row
                resultados.append({
                    # Este texto es el que leen el panel de detalle y el borrado
                    # del historial, que lo esperan escrito así.
                    "tipo": "Entrada de efectivo",
                    "id": id_reg,
                    "fecha": fecha,
                    "monto": monto,
                    "moneda": moneda,
                    "metodo_pago": "Efectivo",
                    "producto": "",
                    "observaciones": desc or "",
                    "detalle_extra": {}
                })

        if filtro_tipo in ("todos", "salida_efectivo") and producto_id is None:
            sentencia = '''
                SELECT id, fecha, moneda, monto, descripcion
                FROM salidas_efectivo
                WHERE 1=1
            '''
            params = []
            if filtro_fecha:
                sentencia += " AND fecha LIKE ?"
                params.append(f"{filtro_fecha}%")
            sentencia += " ORDER BY fecha DESC"
            cursor.execute(sentencia, params)
            for row in cursor.fetchall():
                id_reg, fecha, moneda, monto, desc = row
                resultados.append({
                    "tipo": "Salida de efectivo",
                    "id": id_reg,
                    "fecha": fecha,
                    "monto": monto,
                    "moneda": moneda,
                    "metodo_pago": "Efectivo",
                    "producto": "",
                    "observaciones": desc or "",
                    "detalle_extra": {}
                })

        # ===== SECCIÓN MODIFICADA: MANEJO DE MERMAS =====
        # Las mermas ahora se obtienen directamente de salidas_inventario
        # y se incluyen en "todos" y "merma"
        if filtro_tipo in ("todos", "merma"):
            consulta_salidas = '''
                SELECT s.id, s.fecha, p.nombre, s.cantidad, s.precio_costo, s.motivo
                FROM salidas_inventario s
                JOIN productos p ON s.producto_id = p.id
                WHERE s.motivo LIKE '%Merma%'
            '''
            params_salidas = []
            if filtro_fecha:
                consulta_salidas += " AND s.fecha LIKE ?"
                params_salidas.append(f"{filtro_fecha}%")
            if producto_id is not None:
                consulta_salidas += " AND s.producto_id = ?"
                params_salidas.append(producto_id)
            consulta_salidas += " ORDER BY s.fecha DESC"
            cursor.execute(consulta_salidas, params_salidas)
            for row in cursor.fetchall():
                id_sal, fecha, nombre, cantidad, precio_costo, motivo = row
                resultados.append({
                    "tipo": "Merma",
                    "id": id_sal,  # ID numérico directamente de la tabla
                    "fecha": fecha,
                    "monto": precio_costo * cantidad,  # Monto total de la merma
                    "moneda": "CUP",
                    "metodo_pago": "",
                    "producto": nombre,
                    "observaciones": f"Cantidad: {cantidad} - {motivo}",
                    "detalle_extra": {"origen": "salidas_inventario", "producto": nombre, "cantidad": cantidad}
                })

        # ===== SECCIÓN MODIFICADA: HISTORIAL EXCLUYENDO MERMAS =====
        # Las mermas ya no se obtienen del historial para evitar duplicados
        tipos_historial = ["Entrada de Producto", "Actualización de Producto", "Eliminación de Producto", "Salida de Producto"]
    
        # "entrada_producto" es el valor que manda el radiobutton del panel; sin
        # él este bloque no se ejecutaba y ese filtro salía siempre vacío.
        if filtro_tipo in ("todos", "salidas", "entrada_producto") + tuple(tipos_historial):
            consulta_hist = '''
                SELECT id, fecha, tipo_accion, descripcion, detalles
                FROM historial
                WHERE 1=1
            '''
            params_hist = []
            if filtro_fecha:
                consulta_hist += " AND fecha LIKE ?"
                params_hist.append(f"{filtro_fecha}%")
            if filtro_tipo == "salidas":
                consulta_hist += " AND tipo_accion = 'Salida de Producto'"
            elif filtro_tipo == "entrada_producto":
                consulta_hist += " AND tipo_accion = 'Entrada de Producto'"
            elif filtro_tipo == "actualizacion_producto":
                consulta_hist += " AND tipo_accion = 'Actualización de Producto'"
            elif filtro_tipo == "eliminacion_producto":
                consulta_hist += " AND tipo_accion = 'Eliminación de Producto'"
        
            # Estas acciones ya salen de su tabla propia (salidas_inventario,
            # entradas/salidas_efectivo, operaciones_cambio); en el historial
            # sólo hay una copia que duplicaría la línea.
            consulta_hist += " AND tipo_accion NOT IN ('Merma')"
            consulta_hist += " AND tipo_accion NOT IN ('Entrada de efectivo', 'Salida de efectivo', 'Cambio de Divisa')"

            consulta_hist += " ORDER BY fecha DESC"
            cursor.execute(consulta_hist, params_hist)
            for row in cursor.fetchall():
                id_reg, fecha, tipo_accion, desc, detalles_json = row
                if producto_id is not None and not _fila_historial_es_del_producto(tipo_accion, detalles_json, producto_id, producto_nombre):
                    continue
                monto = 0.0
                moneda = "CUP"
                metodo_pago = ""
                observaciones = desc
                detalle_extra = {}
            
                if tipo_accion == "Salida de Producto":
                    try:
                        detalles = json.loads(detalles_json)
                        monto_calc = detalles.get("cantidad", 0) * detalles.get("precio_costo", 0)
                        observaciones = detalles.get("motivo", "")
                        venta_id = detalles.get("venta_id")
                        detalle_extra["venta_id"] = venta_id
                        if venta_id:
                            cursor2 = conexion.cursor()
                            cursor2.execute("SELECT pagada, saldo_pendiente, observaciones FROM ventas WHERE id = ?", (venta_id,))
                            fila = cursor2.fetchone()
                            if fila:
                                pagada = fila[0]
                                saldo_pendiente = fila[1]
                                obs_venta = fila[2]
                                detalle_extra["pagada"] = pagada
                                if pagada == 0:
                                    monto = saldo_pendiente if saldo_pendiente is not None else monto_calc
                                else:
                                    monto = monto_calc
                                if obs_venta:
                                    observaciones = obs_venta
                            else:
                                monto = monto_calc
                            cursor2.close()
                        else:
                            monto = monto_calc
                    except:
                        monto = 0.0
                elif tipo_accion == "Entrada de Producto":
                    observaciones = desc
                elif tipo_accion == "Actualización de Producto":
                    observaciones = desc
                elif tipo_accion == "Eliminación de Producto":
                    observaciones = desc
                
                resultados.append({
                    "tipo": tipo_accion,
                    "id": id_reg,
                    "fecha": fecha,
                    "monto": monto,
                    "moneda": moneda,
                    "metodo_pago": metodo_pago,
                    "producto": _producto_de_historial(cursor, detalles_json),
                    "observaciones": observaciones,
                    "detalle_extra": detalle_extra
                })

        # Cada bloque viene ordenado por su cuenta, así que la lista completa
        # queda agrupada por tipo. Se reordena entera para que el historial se
        # lea de lo más reciente a lo más antiguo. Las fechas son
        # 'YYYY-MM-DD HH:MM:SS', que ordena igual como texto que como fecha.
        resultados.sort(key=lambda reg: reg["fecha"] or "", reverse=True)

        return resultados

def registrar_venta_en_db(carrito, datos):
    """Escribe una venta y todos sus efectos colaterales en una sola transacción.

    `datos` lleva los importes ya calculados por la pantalla de ventas. Devuelve
    (True, venta_id) o (False, mensaje_de_error).
    """
    moneda_pago = datos["moneda_pago"]
    pago_divisa = datos.get("pago_divisa", 0.0)
    vuelto_moneda = datos.get("vuelto_moneda", 0.0)
    if not datos["es_deuda"] and moneda_pago in ("USD", "EUR") and pago_divisa > 0:
        divisa_neta = pago_divisa - vuelto_moneda
    else:
        divisa_neta = 0.0

    conexion = conectar_db()
    cursor = conexion.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE")
        fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute('''
            INSERT INTO ventas
            (fecha, total, metodo_pago, moneda_pago, tasa_cambio, es_mensajeria, es_deuda, pagada, fecha_pago, cancelada, saldo_pendiente, metodo_pago_real, observaciones, pago_texto, vuelto_texto, monto_efectivo, monto_transferencia, utilidad, monto_divisa_neto)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            fecha,
            datos["total_cup"],
            datos["metodo_pago"],
            datos["moneda_pago"],
            datos["tasa_cambio"],
            datos["es_mensajeria"],
            datos["es_deuda"],
            datos["pagada"],
            datos["fecha_pago"],
            0,
            datos["saldo_pendiente"],
            datos["metodo_pago_real"],
            datos["observaciones"],
            datos["pago_texto"],
            datos["vuelto_texto"],
            datos["monto_efectivo_cup"],
            datos["monto_transferencia_cup"],
            datos["utilidad_total"],
            divisa_neta
        ))
        venta_id = cursor.lastrowid

        for item in carrito:
            cursor.execute('INSERT INTO detalles_venta (venta_id, producto_id, cantidad, precio_unitario) VALUES (?, ?, ?, ?)',
                        (venta_id, item["id"], item["cantidad"], item["precio"]))
            cursor.execute('UPDATE productos SET stock = stock - ? WHERE id = ?', (item["cantidad"], item["id"]))

        if divisa_neta > 0:
            exito, msg, _ = actualizar_fondo(moneda_pago, divisa_neta, "entrada", conexion, cursor)
            if not exito:
                conexion.rollback()
                conexion.close()
                return False, f"Error al actualizar fondo de divisas: {msg}"
        elif divisa_neta < 0:
            conexion.rollback()
            conexion.close()
            return False, "El vuelto en divisa excede el pago en divisa"

        salida_efectivo_extra = datos.get("salida_efectivo_extra", 0.0)
        if salida_efectivo_extra > 0:
            cursor.execute('''
                INSERT INTO salidas_efectivo (fecha, moneda, monto, descripcion, venta_id)
                VALUES (?, ?, ?, ?, ?)
            ''', (fecha, "CUP", salida_efectivo_extra, f"Vuelto en CUP de venta #{venta_id} (no cubierto por pago en CUP)", venta_id))

        conexion.commit()
        conexion.close()
        return True, venta_id
    except Exception as e:
        conexion.rollback()
        conexion.close()
        return False, f"Error al guardar: {str(e)}"


def registrar_cobro_deuda_en_db(venta_id, datos):
    """Escribe el cobro de una deuda y sus efectos en caja, en una sola transacción.

    Devuelve (True, "") o (False, mensaje_de_error).
    """
    moneda = datos["moneda"]
    tasa = datos["tasa"]
    metodo = datos["metodo"]
    efectivo = datos.get("efectivo", 0.0)
    transferencia = datos.get("transferencia", 0.0)
    efectivo_cup = datos.get("efectivo_cup", 0.0)
    vuelto_cup = datos.get("vuelto_cup", 0.0)
    vuelto_moneda = datos.get("vuelto_moneda", 0.0)

    conn = conectar_db()
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE")
        fecha_actual = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if moneda != "CUP":
            if efectivo > 0:
                # monto es lo que entregó el cliente; monto_divisa_neto es lo que queda
                # realmente en caja tras el vuelto en divisa, que es lo que hay que
                # deshacer si luego se elimina el registro.
                cursor.execute('''
                    INSERT INTO cobros_deudas (venta_id, fecha, monto, metodo_pago, moneda, tasa, monto_cup, monto_divisa_neto)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (venta_id, fecha_actual, efectivo, "Efectivo", moneda, tasa, efectivo * tasa, efectivo - vuelto_moneda))
            if efectivo_cup > 0:
                cursor.execute('''
                    INSERT INTO cobros_deudas (venta_id, fecha, monto, metodo_pago, moneda, tasa, monto_cup)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (venta_id, fecha_actual, efectivo_cup, "Efectivo", "CUP", 1.0, efectivo_cup))
        else:
            if metodo == "Mixto":
                cursor.execute('''
                    INSERT INTO cobros_deudas (venta_id, fecha, monto, metodo_pago, moneda, tasa, monto_cup)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (venta_id, fecha_actual, efectivo, "Efectivo", "CUP", 1.0, efectivo))
                cursor.execute('''
                    INSERT INTO cobros_deudas (venta_id, fecha, monto, metodo_pago, moneda, tasa, monto_cup)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (venta_id, fecha_actual, transferencia, "Transferencia", "CUP", 1.0, transferencia))
            else:
                cursor.execute('''
                    INSERT INTO cobros_deudas (venta_id, fecha, monto, metodo_pago, moneda, tasa, monto_cup)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (venta_id, fecha_actual, datos["total_pagado_moneda"], metodo, "CUP", 1.0, datos["total_pagado_cup"]))

        cursor.execute('''
            UPDATE ventas
            SET saldo_pendiente = ?, pagada = ?, fecha_pago = ?, metodo_pago_real = ?, observaciones = ?
            WHERE id = ?
        ''', (datos["nuevo_saldo"], datos["pagada"], datos["fecha_pago"], datos["metodo_pago_real"], datos["observaciones"], venta_id))

        if moneda != "CUP":
            neto_moneda = efectivo - vuelto_moneda
            if neto_moneda > 0:
                exito, msg, _ = actualizar_fondo(moneda, neto_moneda, "entrada", conn, cursor)
                if not exito:
                    raise Exception(msg)
            elif neto_moneda < 0:
                exito, msg, _ = actualizar_fondo(moneda, -neto_moneda, "venta", conn, cursor)
                if not exito:
                    raise Exception(msg)

        if vuelto_cup > 0:
            vuelto_cup_restante = vuelto_cup - (vuelto_moneda * tasa) if vuelto_moneda > 0 else vuelto_cup
            if vuelto_cup_restante > 0:
                cursor.execute('''
                    INSERT INTO salidas_efectivo (fecha, moneda, monto, descripcion, venta_id)
                    VALUES (?, ?, ?, ?, ?)
                ''', (fecha_actual, "CUP", vuelto_cup_restante, f"Vuelto en CUP de deuda #{venta_id}", venta_id))

        # El cobro en CUP ya se contabiliza vía cobros_deudas; esta entrada queda como
        # rastro del movimiento de caja y por eso obtener_resumen_caja la excluye por
        # descripción para no contarla dos veces.
        if efectivo_cup > 0:
            cursor.execute('''
                INSERT INTO entradas_efectivo (fecha, moneda, monto, descripcion, venta_id)
                VALUES (?, ?, ?, ?, ?)
            ''', (fecha_actual, "CUP", efectivo_cup, f"Pago de deuda #{venta_id} - Efectivo CUP", venta_id))

        conn.commit()
        conn.close()
        return True, ""
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, str(e)
