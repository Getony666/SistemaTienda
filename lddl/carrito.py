"""El carrito de la venta, sin interfaz.

Aquí vive lo que antes estaba repartido por `lddl/ui/panel_ventas.py`: añadir
un producto, acumular cuando ya está, cambiarle la cantidad, quitarlo y sumar
el total. Ninguna función sabe que existe una pantalla.

Una línea del carrito es un diccionario, la misma forma que ya espera
`registrar_venta_en_db`:

    {"id": 3, "nombre": "Aceite 1000 ml", "cantidad": 2.0,
     "precio": 200.0, "tipo": "unidad", "unidad": "unidad"}

Las funciones que cambian el carrito **no lo modifican**: devuelven una lista
nueva y, si algo no cuadra, un motivo. Así el mismo cálculo sirve igual desde
tkinter, desde la API o desde una interfaz web.

Dos reglas del negocio viven aquí, no en la pantalla:

- Los productos por peso se cobran redondeando el subtotal al múltiplo de
  5 CUP más cercano, y de ahí sale el precio por unidad de peso.
- Si un producto ya está en el carrito y se añade más, el precio de la línea
  pasa a ser el **promedio ponderado** de lo que había y lo que entra.
"""

from .calculo_cobro import redondear_subtotal_peso

MOTIVOS = {
    "sin_stock": "El producto no tiene stock",
    "stock_insuficiente": "No hay suficiente stock",
    "cantidad_invalida": "La cantidad debe ser mayor que 0",
    "linea_inexistente": "Esa línea no está en el carrito",
}


def subtotal(linea):
    """Lo que cuesta una línea."""
    return linea["cantidad"] * linea["precio"]


def total(carrito):
    """Lo que cuesta la venta entera."""
    return sum(subtotal(linea) for linea in carrito)


def buscar(carrito, producto_id):
    """Posición del producto en el carrito, o None si no está."""
    for i, linea in enumerate(carrito):
        if linea["id"] == producto_id:
            return i
    return None


def precio_unitario(cantidad, precio, tipo):
    """Precio por unidad, aplicando el redondeo de los productos por peso.

    En peso, el cliente paga un múltiplo de 5 CUP, así que el precio por libra
    deja de ser el de catálogo y sale de repartir ese total redondeado.
    """
    if tipo != "peso" or cantidad <= 0:
        return precio
    return redondear_subtotal_peso(cantidad, precio) / cantidad


def promediar_precio(cantidad_actual, precio_actual, cantidad_nueva, precio_nuevo):
    """Precio ponderado al juntar lo que ya había con lo que entra."""
    cantidad_total = cantidad_actual + cantidad_nueva
    if cantidad_total <= 0:
        return precio_nuevo
    return ((precio_actual * cantidad_actual) + (precio_nuevo * cantidad_nueva)) / cantidad_total


def _copia(carrito):
    return [dict(linea) for linea in carrito]


def linea_nueva(producto_id, nombre, cantidad, precio, tipo="unidad", unidad="unidad"):
    return {"id": producto_id, "nombre": nombre, "cantidad": cantidad,
            "precio": precio, "tipo": tipo, "unidad": unidad}


def agregar_unidad(carrito, producto_id, nombre, precio, stock, tipo="unidad", unidad="unidad"):
    """Suma una unidad: lo que hace el botón "Agregar al Carrito".

    Devuelve (carrito_nuevo, motivo). Si motivo no es None, el carrito vuelve
    sin cambios.
    """
    if stock <= 0:
        return carrito, "sin_stock"

    nuevo = _copia(carrito)
    i = buscar(nuevo, producto_id)
    if i is not None:
        if nuevo[i]["cantidad"] + 1 > stock:
            return carrito, "stock_insuficiente"
        nuevo[i]["cantidad"] += 1
        return nuevo, None

    nuevo.append(linea_nueva(producto_id, nombre, 1, precio, tipo, unidad))
    return nuevo, None


def agregar_cantidad(carrito, producto_id, nombre, cantidad, precio, stock,
                     tipo="unidad", unidad="unidad"):
    """Añade una cantidad concreta, la que se teclea en el diálogo.

    Si el producto ya está en el carrito, las dos líneas se funden y el precio
    pasa a ser el promedio ponderado.

    OJO: el stock se comprueba contra la cantidad que entra, no contra la suma
    con lo que ya hubiera en el carrito. Es el comportamiento que tiene hoy la
    aplicación y se conserva tal cual; ver `pruebas/test_carrito.py`.
    """
    if cantidad <= 0:
        return carrito, "cantidad_invalida"
    if cantidad > stock:
        return carrito, "stock_insuficiente"

    unitario = precio_unitario(cantidad, precio, tipo)
    nuevo = _copia(carrito)
    i = buscar(nuevo, producto_id)

    if i is not None:
        linea = nuevo[i]
        linea["precio"] = promediar_precio(linea["cantidad"], linea["precio"],
                                           cantidad, unitario)
        linea["cantidad"] = linea["cantidad"] + cantidad
        return nuevo, None

    nuevo.append(linea_nueva(producto_id, nombre, cantidad, unitario, tipo, unidad))
    return nuevo, None


def fijar_cantidad(carrito, indice, cantidad, stock):
    """Cambia la cantidad de una línea que ya está en el carrito.

    Sustituye, no suma: es lo que hace el diálogo al editar una línea. El
    precio se recalcula con el de la propia línea, que en los productos por
    peso ya viene ajustado por el redondeo anterior.
    """
    if indice < 0 or indice >= len(carrito):
        return carrito, "linea_inexistente"
    if cantidad <= 0:
        return carrito, "cantidad_invalida"
    if cantidad > stock:
        return carrito, "stock_insuficiente"

    nuevo = _copia(carrito)
    linea = nuevo[indice]
    linea["precio"] = precio_unitario(cantidad, linea["precio"], linea["tipo"])
    linea["cantidad"] = cantidad
    return nuevo, None


def quitar(carrito, indice):
    """Saca una línea del carrito."""
    if indice < 0 or indice >= len(carrito):
        return carrito, "linea_inexistente"
    nuevo = _copia(carrito)
    del nuevo[indice]
    return nuevo, None


def vaciar():
    """Carrito recién empezado."""
    return []


def texto_cantidad(cantidad, unidad="unidad"):
    """Cómo se escribe la cantidad en la tabla: sin decimales si son enteros."""
    if isinstance(cantidad, float) and cantidad.is_integer():
        cantidad = int(cantidad)
    return f"{cantidad} {unidad}"


def filas_para_tabla(carrito):
    """Las líneas ya formateadas, en el orden en que se muestran."""
    return [
        {
            "nombre": linea["nombre"],
            "cantidad": texto_cantidad(linea["cantidad"], linea.get("unidad", "unidad")),
            "precio": f"{linea['precio']:.2f}",
            "subtotal": f"{subtotal(linea):.2f}",
        }
        for linea in carrito
    ]
