"""Consulta del almacén: qué hay, cuánto vale y qué se vende.

Vive aparte de `productos.py` porque ahí está el alta/baja/edición -quien
manda sobre los datos- y aquí sólo se pregunta sobre ellos: se busca, se
filtra, se ordena y se cruza con las ventas para saber qué se mueve.
"""

import datetime

from .productos import CATEGORIAS
from .rutas import consulta, quitar_tildes


def _umbral_de_fecha(dias):
    """Desde cuándo cuentan las ventas, o None para todo el historial.

    `dias` en 0 (o cualquier valor sin marcar) es "todo": no hay umbral.
    """
    if not dias:
        return None
    inicio = datetime.datetime.now() - datetime.timedelta(days=dias)
    return inicio.strftime("%Y-%m-%d 00:00:00")


def _vendidos_por_producto(cursor, umbral):
    """Unidades vendidas de cada producto en el período: {producto_id: cantidad}.

    Se suma `cantidad` de detalles_venta cruzado con ventas por fecha, pero no
    toda fila de ventas es una venta de verdad:

    - Una "Salida de inventario" (a un trabajador) escribe también en
      ventas/detalles_venta -con metodo_pago = 'Salida'- para poder generarle
      una deuda y cobrarla igual que cualquier otra. No es una venta: es un
      traspaso a precio de costo, así que queda fuera.
    - Una venta cancelada (`cancelada = 1`) nunca llegó a salir de verdad del
      almacén.
    - La Merma no hace falta excluirla aquí: no toca ventas ni detalles_venta
      en absoluto, sólo salidas_inventario (ver `lddl/inventario.py`), así que
      ya queda fuera de esta suma sin tener que filtrarla.
    """
    sentencia = '''
        SELECT dv.producto_id, SUM(dv.cantidad)
        FROM detalles_venta dv
        JOIN ventas v ON v.id = dv.venta_id
        WHERE v.metodo_pago != 'Salida' AND v.cancelada = 0
    '''
    parametros = []
    if umbral:
        sentencia += " AND v.fecha >= ?"
        parametros.append(umbral)
    sentencia += " GROUP BY dv.producto_id"
    cursor.execute(sentencia, parametros)
    return {producto_id: cantidad or 0 for producto_id, cantidad in cursor.fetchall()}


def _margen(precio_compra, precio_venta):
    """(venta - compra) / compra * 100, a un decimal. Sin costo no hay margen
    que calcular -y menos aún dividir por cero-, así que da 0.0."""
    if not precio_compra:
        return 0.0
    return round((precio_venta - precio_compra) / precio_compra * 100, 1)


def obtener_almacen(buscar="", proveedor="", categoria="", orden="nombre", dias=30):
    """Productos del almacén con lo que hay que enseñar, más un resumen.

    `dias` es el período de "vendidos": 30, 90 o 0 para todo el historial.
    `orden` es "nombre" (alfabético, sin acentos) o "vendidos" (de más a
    menos, con empate alfabético). `buscar` (subcadena del nombre), `proveedor`
    y `categoria` (los dos exactos) son opcionales y se combinan entre sí.
    """
    with consulta() as (_conexion, cursor):
        cursor.execute('''
            SELECT id, nombre, categoria, proveedor, precio_compra, precio_venta,
                   stock, tipo_producto, unidad_medida, fecha_vencimiento
            FROM productos
        ''')
        filas = cursor.fetchall()

        vendidos_por_id = _vendidos_por_producto(cursor, _umbral_de_fecha(dias))

        # Todos los proveedores que existen en la base, sin filtrar: es para
        # llenar el desplegable del filtro, no la lista que se está pidiendo.
        cursor.execute('''
            SELECT DISTINCT proveedor FROM productos
            WHERE proveedor IS NOT NULL AND TRIM(proveedor) != ''
        ''')
        proveedores = sorted((fila[0].strip() for fila in cursor.fetchall()),
                             key=quitar_tildes)

    buscar_normalizado = quitar_tildes(buscar.strip()) if buscar else ""

    productos = []
    for (id_, nombre, cat, prov, precio_compra, precio_venta, stock,
         tipo, unidad, vencimiento) in filas:
        if buscar_normalizado and buscar_normalizado not in quitar_tildes(nombre):
            continue
        if proveedor and prov != proveedor:
            continue
        if categoria and cat != categoria:
            continue
        productos.append({
            "id": id_,
            "nombre": nombre,
            "categoria": cat,
            "proveedor": prov or "",
            "precio_compra": precio_compra,
            "precio_venta": precio_venta,
            "margen": _margen(precio_compra, precio_venta),
            "stock": stock,
            "tipo_producto": tipo or "unidad",
            "unidad_medida": unidad or "unidad",
            "fecha_vencimiento": vencimiento or "",
            "vendidos": vendidos_por_id.get(id_, 0),
        })

    if orden == "vendidos":
        productos.sort(key=lambda p: (-p["vendidos"], quitar_tildes(p["nombre"])))
    else:
        productos.sort(key=lambda p: quitar_tildes(p["nombre"]))

    resumen = {
        "total": len(productos),
        "valor_costo": round(sum(p["precio_compra"] * p["stock"] for p in productos), 2),
        "sin_existencia": sum(1 for p in productos if p["stock"] <= 0),
    }

    return {
        "productos": productos,
        "resumen": resumen,
        "proveedores": proveedores,
        "categorias": list(CATEGORIAS),
    }
