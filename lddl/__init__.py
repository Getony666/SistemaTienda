"""La Despensa de Leslia — sistema de ventas, caja e inventario.

El paquete separa la lógica de datos de la interfaz:

    rutas.py         rutas de ficheros y acceso a la base de datos
    esquema.py       creación y migración de tablas
    historial.py     asientos del historial y su reversión
    caja.py          fondo, efectivo, divisas y cambio de moneda
    productos.py     alta, modificación y búsqueda de productos
    inventario.py    salidas a trabajador y mermas
    ventas_datos.py  ventas, deudas y cobros
    ui/              la ventana y sus paneles
"""
