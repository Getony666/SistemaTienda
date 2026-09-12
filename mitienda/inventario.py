"""Movimientos de inventario que no son ventas: salidas a trabajador y mermas."""

import datetime

from . import sesion
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
                (fecha, total, metodo_pago, moneda_pago, tasa_cambio, es_mensajeria, es_deuda, pagada, fecha_pago, cancelada, saldo_pendiente, metodo_pago_real, observaciones, pago_texto, vuelto_texto, usuario)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (fecha_venta, total_cup, "Salida", "CUP", 1.0, 0, 1, 0, None, 0, total_cup, '', motivo, "Deuda generada", "0.00 CUP", sesion.usuario_actual()))
            venta_id = cursor.lastrowid
            cursor.execute('''
                INSERT INTO detalles_venta (venta_id, producto_id, cantidad, precio_unitario)
                VALUES (?, ?, ?, ?)
            ''', (venta_id, producto_id, cantidad, precio_costo))
            cursor.execute('UPDATE productos SET stock = stock - ? WHERE id = ?', (cantidad, producto_id))
            cursor.execute('''
                INSERT INTO salidas_inventario (fecha, producto_id, cantidad, precio_costo, motivo, usuario)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (fecha_venta, producto_id, cantidad, precio_costo, motivo, sesion.usuario_actual()))
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
                INSERT INTO salidas_inventario (fecha, producto_id, cantidad, precio_costo, motivo, usuario)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (fecha, producto_id, cantidad, precio_compra, motivo, sesion.usuario_actual()))
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


def _leer_lineas(cursor, lineas):
    """Comprueba las líneas contra el almacén antes de tocar nada.

    Devuelve (preparadas, error). Se valida todo primero para no dejar medio
    carrito descontado si la tercera línea no tiene stock.
    """
    preparadas = []
    for linea in lineas:
        producto_id = linea["producto_id"]
        cantidad = float(linea["cantidad"])
        if cantidad <= 0:
            return None, "Las cantidades deben ser mayores que 0"

        cursor.execute("SELECT nombre, stock, precio_compra FROM productos WHERE id=?",
                       (producto_id,))
        fila = cursor.fetchone()
        if not fila:
            return None, f"El producto {producto_id} no existe"
        nombre, stock, precio_compra = fila
        if cantidad > stock:
            return None, f"Stock insuficiente de {nombre}. Disponible: {stock:.2f}"

        # El costo lo pone el almacén, no quien llama: así nadie puede valorar
        # una salida por debajo de lo que costó.
        preparadas.append({
            "producto_id": producto_id,
            "nombre": nombre,
            "cantidad": cantidad,
            "precio_costo": precio_compra,
        })
    return preparadas, None


def registrar_salida_de_carrito(lineas, motivo="Salida a trabajador"):
    """Saca varios productos del almacén de una vez, a precio de costo.

    Genera UNA sola deuda por el total del carrito, no una por producto: es lo
    que se espera cuando un trabajador se lleva varias cosas a la vez.

    `lineas` son diccionarios con producto_id y cantidad. Devuelve
    (True, mensaje) o (False, motivo), y no escribe nada si algo falla.
    """
    if not lineas:
        return False, "No hay nada que sacar"

    try:
        with transaccion() as (_conexion, cursor):
            preparadas, error = _leer_lineas(cursor, lineas)
            if error:
                return False, error

            total_cup = sum(l["cantidad"] * l["precio_costo"] for l in preparadas)
            fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute('''
                INSERT INTO ventas
                (fecha, total, metodo_pago, moneda_pago, tasa_cambio, es_mensajeria,
                 es_deuda, pagada, fecha_pago, cancelada, saldo_pendiente,
                 metodo_pago_real, observaciones, pago_texto, vuelto_texto, usuario)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (fecha, total_cup, "Salida", "CUP", 1.0, 0, 1, 0, None, 0,
                  total_cup, '', motivo, "Deuda generada", "0.00 CUP",
                  sesion.usuario_actual()))
            venta_id = cursor.lastrowid

            for linea in preparadas:
                cursor.execute(
                    'INSERT INTO detalles_venta (venta_id, producto_id, cantidad, precio_unitario)'
                    ' VALUES (?, ?, ?, ?)',
                    (venta_id, linea["producto_id"], linea["cantidad"], linea["precio_costo"]))
                cursor.execute('UPDATE productos SET stock = stock - ? WHERE id = ?',
                               (linea["cantidad"], linea["producto_id"]))
                cursor.execute(
                    'INSERT INTO salidas_inventario (fecha, producto_id, cantidad, precio_costo, motivo, usuario)'
                    ' VALUES (?, ?, ?, ?, ?, ?)',
                    (fecha, linea["producto_id"], linea["cantidad"],
                     linea["precio_costo"], motivo, sesion.usuario_actual()))
                linea["ref_id"] = cursor.lastrowid
    except Exception as e:
        return False, f"Error al registrar la salida: {str(e)}"

    descripcion = ", ".join(f"{l['nombre']} x{l['cantidad']:g}" for l in preparadas)
    registrar_historial(
        "Salida de Producto",
        f"Salida de {len(preparadas)} producto(s): {descripcion}",
        # `lineas` es lo que distingue esta salida de las de un solo producto;
        # revertir_registro mira ese campo para saber qué forma tiene.
        {"lineas": preparadas, "venta_id": venta_id, "motivo": motivo,
         "total_cup": total_cup},
    )
    return True, (f"Salida registrada: {len(preparadas)} producto(s) por "
                  f"{total_cup:.2f} CUP. Deuda generada automáticamente")


def registrar_merma_de_carrito(lineas, motivo="Merma"):
    """Da de baja varios productos de una vez, sin cobrar nada.

    Cada línea queda como su propia merma en el almacén, igual que si se
    hubieran registrado una a una: así siguen viéndose y revirtiéndose por
    separado en el historial. Lo que cambia es que o entran todas o ninguna.
    """
    if not lineas:
        return False, "No hay nada que dar de baja"

    try:
        with transaccion() as (_conexion, cursor):
            preparadas, error = _leer_lineas(cursor, lineas)
            if error:
                return False, error

            fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for linea in preparadas:
                cursor.execute('UPDATE productos SET stock = stock - ? WHERE id = ?',
                               (linea["cantidad"], linea["producto_id"]))
                cursor.execute(
                    'INSERT INTO salidas_inventario (fecha, producto_id, cantidad, precio_costo, motivo, usuario)'
                    ' VALUES (?, ?, ?, ?, ?, ?)',
                    (fecha, linea["producto_id"], linea["cantidad"],
                     linea["precio_costo"], motivo, sesion.usuario_actual()))
                linea["ref_id"] = cursor.lastrowid
    except Exception as e:
        return False, f"Error al registrar la merma: {str(e)}"

    for linea in preparadas:
        registrar_historial(
            "Merma",
            f"Producto: {linea['nombre']}, Cantidad: {linea['cantidad']}",
            {"producto_id": linea["producto_id"], "nombre": linea["nombre"],
             "cantidad": linea["cantidad"], "motivo": motivo,
             "precio_costo": linea["precio_costo"], "ref_id": linea["ref_id"]},
        )

    total = sum(l["cantidad"] * l["precio_costo"] for l in preparadas)
    return True, (f"Merma registrada: {len(preparadas)} producto(s), "
                  f"{total:.2f} CUP de coste")

