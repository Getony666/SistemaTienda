"""Movimientos de inventario que no son ventas: salidas a trabajador y mermas."""

import datetime

from .historial import registrar_historial
from .rutas import consulta as abrir_consulta, transaccion


def registrar_salida(producto_id, cantidad, precio_costo, motivo="Salida a trabajador"):
    try:
        with transaccion() as (_conexion, cursor):
            cursor.execute("SELECT stock, nombre FROM productos WHERE id=?", (producto_id,))
            fila = cursor.fetchone()
            if not fila:
                return False, "El producto no existe"
            stock_actual, nombre = fila
            if cantidad > stock_actual:
                return False, f"Stock insuficiente. Disponible: {stock_actual:.2f}"
            total_cup = cantidad * precio_costo
            fecha_venta = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute('''
                INSERT INTO ventas 
                (fecha, total, metodo_pago, moneda_pago, tasa_cambio, es_mensajeria, es_deuda, pagada, fecha_pago, cancelada, saldo_pendiente, metodo_pago_real, observaciones, pago_texto, vuelto_texto)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (fecha_venta, total_cup, "Salida", "CUP", 1.0, 0, 1, 0, None, 0, total_cup, '', motivo, "Deuda generada", "0.00 CUP"))
            venta_id = cursor.lastrowid
            cursor.execute('''
                INSERT INTO detalles_venta (venta_id, producto_id, cantidad, precio_unitario)
                VALUES (?, ?, ?, ?)
            ''', (venta_id, producto_id, cantidad, precio_costo))
            cursor.execute('UPDATE productos SET stock = stock - ? WHERE id = ?', (cantidad, producto_id))
            cursor.execute('''
                INSERT INTO salidas_inventario (fecha, producto_id, cantidad, precio_costo, motivo)
                VALUES (?, ?, ?, ?, ?)
            ''', (fecha_venta, producto_id, cantidad, precio_costo, motivo))
            ref_id = cursor.lastrowid
    except Exception as e:
        return False, f"Error al registrar salida: {str(e)}"

    registrar_historial(
        "Salida de Producto",
        f"Producto: {nombre}, Cantidad: {cantidad}",
        {"producto_id": producto_id, "nombre": nombre, "cantidad": cantidad, "motivo": motivo, "precio_costo": precio_costo, "venta_id": venta_id, "ref_id": ref_id}
    )
    return True, "Salida registrada y deuda generada automáticamente"


def registrar_merma(producto_id, cantidad, motivo="Merma"):
    try:
        with transaccion() as (_conexion, cursor):
            cursor.execute("SELECT stock, nombre, precio_compra FROM productos WHERE id=?", (producto_id,))
            fila = cursor.fetchone()
            if not fila:
                return False, "El producto no existe"
            stock_actual, nombre, precio_compra = fila
            if cantidad > stock_actual:
                return False, f"Stock insuficiente. Disponible: {stock_actual:.2f}"
            fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute('UPDATE productos SET stock = stock - ? WHERE id = ?', (cantidad, producto_id))
            cursor.execute('''
                INSERT INTO salidas_inventario (fecha, producto_id, cantidad, precio_costo, motivo)
                VALUES (?, ?, ?, ?, ?)
            ''', (fecha, producto_id, cantidad, precio_compra, motivo))
            ref_id = cursor.lastrowid
    except Exception as e:
        return False, f"Error al registrar merma: {str(e)}"

    registrar_historial(
        "Merma",
        f"Producto: {nombre}, Cantidad: {cantidad}",
        {"producto_id": producto_id, "nombre": nombre, "cantidad": cantidad, "motivo": motivo, "precio_costo": precio_compra, "ref_id": ref_id}
    )
    return True, f"Merma registrada: {cantidad:.2f} unidades de producto"


def obtener_salidas(filtro_fecha="hoy"):
    consulta = '''
        SELECT s.id, s.fecha, p.nombre, s.cantidad, s.precio_costo, s.motivo
        FROM salidas_inventario s
        JOIN productos p ON s.producto_id = p.id
        WHERE 1=1
    '''
    parametros = []
    hoy = datetime.datetime.now()
    if filtro_fecha == "hoy":
        fecha_str = hoy.strftime("%Y-%m-%d")
        consulta += " AND s.fecha LIKE ?"
        parametros.append(f"{fecha_str}%")
    elif filtro_fecha == "ayer":
        ayer = hoy - datetime.timedelta(days=1)
        fecha_str = ayer.strftime("%Y-%m-%d")
        consulta += " AND s.fecha LIKE ?"
        parametros.append(f"{fecha_str}%")
    elif filtro_fecha == "semana":
        inicio_semana = hoy - datetime.timedelta(days=hoy.weekday())
        inicio_str = inicio_semana.strftime("%Y-%m-%d")
        consulta += " AND s.fecha >= ?"
        parametros.append(inicio_str)
    elif filtro_fecha == "mes":
        mes_str = hoy.strftime("%Y-%m")
        consulta += " AND s.fecha LIKE ?"
        parametros.append(f"{mes_str}%")
    consulta += " ORDER BY s.fecha DESC"
    with abrir_consulta() as (_conexion, cursor):
        cursor.execute(consulta, parametros)
        return cursor.fetchall()
