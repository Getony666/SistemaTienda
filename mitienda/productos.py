"""Alta, modificación, borrado y búsqueda de productos."""

from .historial import registrar_historial
from .rutas import consulta, quitar_tildes, transaccion

# Doce categorías fijas, "Otros" siempre la última: así queda un cajón donde
# cae todo lo que no encaja, sin que el menú desplegable se vaya alargando
# solo. El orden es el que ve quien elige la categoría.
CATEGORIAS = (
    "Alimentos", "Bebidas", "Confituras", "Cárnicos y embutidos", "Lácteos",
    "Conservas", "Panadería y dulcería", "Aseo personal", "Limpieza del hogar",
    "Cigarros y tabaco", "Misceláneas", "Otros",
)


def normalizar_categoria(categoria):
    """La categoría no es obligatoria: lo que no sea una de las doce válidas
    -vacía, None, inventada- se guarda como "Otros". La usan tanto el alta
    como la actualización, para que un producto nunca quede con una categoría
    que el desplegable ni siquiera ofrece."""
    categoria = (categoria or "").strip()
    return categoria if categoria in CATEGORIAS else "Otros"


def agregar_producto(nombre, categoria, precio_compra, precio_venta, stock, proveedor, tipo_producto="unidad", unidad_medida="unidad", fecha_vencimiento=""):
    categoria = normalizar_categoria(categoria)
    precio_compra = 0.0 if precio_compra is None else precio_compra
    precio_venta = 0.0 if precio_venta is None else precio_venta
    stock = 0.0 if stock is None else stock
    proveedor = "" if proveedor is None else proveedor
    tipo_producto = "unidad" if tipo_producto is None else tipo_producto
    unidad_medida = "unidad" if unidad_medida is None else unidad_medida
    fecha_vencimiento = "" if fecha_vencimiento is None else fecha_vencimiento
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


def actualizar_producto(id, nombre, categoria=None, precio_compra=None, precio_venta=None,
                         stock=None, proveedor=None, tipo_producto=None, unidad_medida=None,
                         fecha_vencimiento=None):
    """Cambia los datos de un producto.

    Un campo que llega como None significa "no cambiar": se conserva lo que
    ya había en la base. Hace falta porque alguna pantalla no conoce cierto
    campo -hoy el proveedor- y lo manda vacío sin querer, y eso no puede
    borrar lo que ya estaba guardado. El 0 de precio_compra, precio_venta y
    stock SÍ es un valor real: por eso se compara con `is None`, nunca con
    "si no hay valor", que confundiría el cero con "no cambiar".
    """
    try:
        with transaccion() as (_conexion, cursor):
            cursor.execute('''
                SELECT nombre, categoria, precio_compra, precio_venta, stock,
                       proveedor, tipo_producto, unidad_medida, fecha_vencimiento
                FROM productos WHERE id=?
            ''', (id,))
            antiguo = cursor.fetchone()
            # Sin fila que consultar (id inexistente) no hay "valor actual" que
            # conservar; se usa un relleno neutro y de todos modos la UPDATE de
            # abajo no va a tocar ninguna fila.
            base = antiguo or (nombre, "", 0.0, 0.0, 0.0, "", "unidad", "unidad", "")
            (nombre_antes, categoria_antes, precio_compra_antes, precio_venta_antes,
             stock_antes, proveedor_antes, tipo_antes, unidad_antes, fecha_antes) = base

            nombre = nombre_antes if nombre is None else nombre
            categoria = normalizar_categoria(categoria_antes if categoria is None else categoria)
            precio_compra = precio_compra_antes if precio_compra is None else precio_compra
            precio_venta = precio_venta_antes if precio_venta is None else precio_venta
            stock = stock_antes if stock is None else stock
            proveedor = proveedor_antes if proveedor is None else proveedor
            tipo_producto = tipo_antes if tipo_producto is None else tipo_producto
            unidad_medida = unidad_antes if unidad_medida is None else unidad_medida
            fecha_vencimiento = fecha_antes if fecha_vencimiento is None else fecha_vencimiento

            cursor.execute('''
                UPDATE productos
                SET nombre=?, categoria=?, precio_compra=?, precio_venta=?, stock=?, proveedor=?, tipo_producto=?, unidad_medida=?, fecha_vencimiento=?
                WHERE id=?
            ''', (nombre, categoria, float(precio_compra), float(precio_venta), float(stock), proveedor, tipo_producto, unidad_medida, fecha_vencimiento, id))
    except Exception as e:
        return False, f"Error: {str(e)}"

    if antiguo:
        cambios = []
        if nombre_antes != nombre:
            cambios.append(f"nombre: {nombre_antes} -> {nombre}")
        if precio_compra_antes != float(precio_compra):
            cambios.append(f"precio_compra: {precio_compra_antes} -> {precio_compra}")
        if precio_venta_antes != float(precio_venta):
            cambios.append(f"precio_venta: {precio_venta_antes} -> {precio_venta}")
        if stock_antes != float(stock):
            cambios.append(f"stock: {stock_antes} -> {stock}")
        if proveedor_antes != proveedor:
            cambios.append(f"proveedor: {proveedor_antes} -> {proveedor}")
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
