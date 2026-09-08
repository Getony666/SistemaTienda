"""Alta, modificación, borrado y búsqueda de productos."""

from .historial import registrar_historial
from .rutas import consulta, quitar_tildes, transaccion


def agregar_producto(nombre, categoria, precio_compra, precio_venta, stock, proveedor, tipo_producto="unidad", unidad_medida="unidad", fecha_vencimiento=""):
    try:
        with transaccion() as (_conexion, cursor):
            cursor.execute('''
                INSERT INTO productos
                (nombre, categoria, precio_compra, precio_venta, stock, proveedor, tipo_producto, unidad_medida, fecha_vencimiento)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (nombre, categoria, float(precio_compra), float(precio_venta), float(stock), proveedor, tipo_producto, unidad_medida, fecha_vencimiento))
    except Exception as e:
        return False, f"Error: {str(e)}"
    registrar_historial(
        "Entrada de Producto",
        f"Producto: {nombre}",
        {"nombre": nombre, "precio_compra": precio_compra, "precio_venta": precio_venta, "stock": stock, "proveedor": proveedor}
    )
    return True, "Producto agregado exitosamente"


def actualizar_producto(id, nombre, categoria, precio_compra, precio_venta, stock, proveedor, tipo_producto, unidad_medida, fecha_vencimiento):
    try:
        with transaccion() as (_conexion, cursor):
            cursor.execute("SELECT nombre, precio_compra, precio_venta, stock, proveedor FROM productos WHERE id=?", (id,))
            antiguo = cursor.fetchone()
            cursor.execute('''
                UPDATE productos
                SET nombre=?, categoria=?, precio_compra=?, precio_venta=?, stock=?, proveedor=?, tipo_producto=?, unidad_medida=?, fecha_vencimiento=?
                WHERE id=?
            ''', (nombre, categoria, float(precio_compra), float(precio_venta), float(stock), proveedor, tipo_producto, unidad_medida, fecha_vencimiento, id))
    except Exception as e:
        return False, f"Error: {str(e)}"

    if antiguo:
        cambios = []
        if antiguo[0] != nombre:
            cambios.append(f"nombre: {antiguo[0]} -> {nombre}")
        if antiguo[1] != float(precio_compra):
            cambios.append(f"precio_compra: {antiguo[1]} -> {precio_compra}")
        if antiguo[2] != float(precio_venta):
            cambios.append(f"precio_venta: {antiguo[2]} -> {precio_venta}")
        if antiguo[3] != float(stock):
            cambios.append(f"stock: {antiguo[3]} -> {stock}")
        if antiguo[4] != proveedor:
            cambios.append(f"proveedor: {antiguo[4]} -> {proveedor}")
        desc = f"Producto ID {id}: " + "; ".join(cambios) if cambios else "Sin cambios"
        registrar_historial("Actualización de Producto", desc, {"id": id, "cambios": cambios})
    return True, "Producto actualizado exitosamente"


def eliminar_producto(id):
    try:
        with transaccion() as (_conexion, cursor):
            cursor.execute('SELECT COUNT(*) FROM detalles_venta WHERE producto_id=?', (id,))
            if cursor.fetchone()[0] > 0:
                return False, "No se puede eliminar: el producto tiene ventas asociadas"
            cursor.execute("SELECT nombre FROM productos WHERE id=?", (id,))
            fila = cursor.fetchone()
            if not fila:
                return False, "El producto ya no existe"
            nombre = fila[0]
            cursor.execute('DELETE FROM productos WHERE id=?', (id,))
    except Exception as e:
        return False, f"Error: {str(e)}"
    registrar_historial("Eliminación de Producto", f"Producto: {nombre} (ID {id})", {"id": id, "nombre": nombre})
    return True, "Producto eliminado exitosamente"


def buscar_productos(texto_busqueda):
    with consulta() as (_conexion, cursor):
        # El precio de compra va al final a propósito: los paneles de tkinter
        # leen estas tuplas por posición (p[0] a p[5]) y así no se enteran.
        cursor.execute('''
            SELECT id, nombre, precio_venta, stock, tipo_producto, unidad_medida,
                   precio_compra
            FROM productos
            ORDER BY nombre
        ''')
        todos = cursor.fetchall()
    if not texto_busqueda or len(texto_busqueda.strip()) == 0:
        return todos
    texto_normalizado = quitar_tildes(texto_busqueda.lower().strip())
    return [p for p in todos if texto_normalizado in quitar_tildes(p[1].lower())]
