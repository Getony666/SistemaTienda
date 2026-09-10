"""La consulta del almacén: margen, valor de costo y qué se vende.

Todo sobre una COPIA de la base de pruebas.

    python -m unittest discover -s pruebas -v
"""

import datetime
import os
import shutil
import sqlite3
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import base  # noqa: E402
from lddl import rutas  # noqa: E402
from lddl.almacen import obtener_almacen  # noqa: E402
from lddl.inventario import registrar_merma  # noqa: E402
from lddl.productos import CATEGORIAS, agregar_producto  # noqa: E402


class SobreUnaCopia(unittest.TestCase):
    """Cada prueba arranca con una copia limpia de la base."""

    def setUp(self):
        self.temporal = base.carpeta_con_copia("mitienda-almacen-")
        rutas.fijar_directorio_base(self.temporal)

    def tearDown(self):
        rutas.fijar_directorio_base(None)
        shutil.rmtree(self.temporal, ignore_errors=True)

    def conexion(self):
        return sqlite3.connect(os.path.join(self.temporal, "tienda.db"))

    def crear_producto(self, nombre, precio_compra=100, precio_venta=150, stock=50,
                        categoria="Alimentos", proveedor="Casa Rubio"):
        exito, mensaje = agregar_producto(
            nombre, categoria, precio_compra, precio_venta, stock, proveedor)
        self.assertTrue(exito, mensaje)
        con = self.conexion()
        try:
            return con.execute(
                "SELECT id FROM productos WHERE nombre=?", (nombre,)).fetchone()[0]
        finally:
            con.close()

    def vender(self, producto_id, cantidad, hace_dias=0, metodo_pago="Efectivo", cancelada=0):
        """Mete una fila en ventas/detalles_venta directamente -o de tipo
        'Salida' si se pide ese método-, con la fecha que haga falta para
        probar el período. No usa registrar_venta_en_db para poder fijar la
        fecha a mano."""
        fecha = (datetime.datetime.now()
                 - datetime.timedelta(days=hace_dias)).strftime("%Y-%m-%d %H:%M:%S")
        con = self.conexion()
        try:
            cur = con.cursor()
            cur.execute(
                "INSERT INTO ventas (fecha, total, metodo_pago, es_deuda, pagada,"
                " metodo_pago_real, cancelada) VALUES (?, 100, ?, 0, 1, 'Efectivo', ?)",
                (fecha, metodo_pago, cancelada))
            venta_id = cur.lastrowid
            cur.execute(
                "INSERT INTO detalles_venta (venta_id, producto_id, cantidad, precio_unitario)"
                " VALUES (?, ?, ?, 100)", (venta_id, producto_id, cantidad))
            con.commit()
            return venta_id
        finally:
            con.close()


class ElMargen(SobreUnaCopia):

    def test_se_calcula_bien(self):
        self.crear_producto("Colado A", precio_compra=100, precio_venta=150)
        productos = obtener_almacen(buscar="Colado A")["productos"]
        self.assertEqual(len(productos), 1)
        self.assertAlmostEqual(productos[0]["margen"], 50.0)

    def test_con_precio_de_compra_cero_no_revienta(self):
        self.crear_producto("Colado B", precio_compra=0, precio_venta=150)
        productos = obtener_almacen(buscar="Colado B")["productos"]
        self.assertEqual(productos[0]["margen"], 0.0)


class LoQueSeVende(SobreUnaCopia):

    def test_un_producto_sin_ventas_aparece_con_cero(self):
        self.crear_producto("Sin ventas")
        productos = obtener_almacen(buscar="Sin ventas")["productos"]
        self.assertEqual(len(productos), 1)
        self.assertEqual(productos[0]["vendidos"], 0)

    def test_suma_las_ventas_normales(self):
        pid = self.crear_producto("Con ventas")
        self.vender(pid, 3)
        self.vender(pid, 2)
        productos = obtener_almacen(buscar="Con ventas")["productos"]
        self.assertEqual(productos[0]["vendidos"], 5)

    def test_no_cuenta_la_salida_de_inventario(self):
        """Una Salida a trabajador deja fila en ventas/detalles_venta -para
        poder cobrarla como deuda- pero no es una venta: es un traspaso a
        precio de costo."""
        pid = self.crear_producto("Con salida")
        self.vender(pid, 3, metodo_pago="Efectivo")
        self.vender(pid, 10, metodo_pago="Salida")
        productos = obtener_almacen(buscar="Con salida")["productos"]
        self.assertEqual(productos[0]["vendidos"], 3)

    def test_no_cuenta_la_merma(self):
        """La Merma no toca ventas/detalles_venta en absoluto: sólo
        salidas_inventario. No hace falta excluirla a mano, pero si algún día
        cambia de tabla, esta prueba lo nota."""
        pid = self.crear_producto("Con merma", stock=20)
        self.vender(pid, 4)
        exito, mensaje = registrar_merma(pid, 5)
        self.assertTrue(exito, mensaje)
        productos = obtener_almacen(buscar="Con merma")["productos"]
        self.assertEqual(productos[0]["vendidos"], 4)

    def test_no_cuenta_una_venta_cancelada(self):
        pid = self.crear_producto("Cancelada")
        self.vender(pid, 7, cancelada=1)
        productos = obtener_almacen(buscar="Cancelada")["productos"]
        self.assertEqual(productos[0]["vendidos"], 0)

    def test_respeta_el_periodo(self):
        pid = self.crear_producto("Periodo")
        self.vender(pid, 2, hace_dias=5)
        self.vender(pid, 9, hace_dias=200)
        self.assertEqual(
            obtener_almacen(buscar="Periodo", dias=30)["productos"][0]["vendidos"], 2)
        self.assertEqual(
            obtener_almacen(buscar="Periodo", dias=90)["productos"][0]["vendidos"], 2)
        self.assertEqual(
            obtener_almacen(buscar="Periodo", dias=0)["productos"][0]["vendidos"], 11)

    def test_el_orden_por_vendidos_desempata_alfabetico(self):
        a = self.crear_producto("Zeta")
        b = self.crear_producto("Beta")
        self.vender(a, 5)
        self.vender(b, 5)
        nombres = [p["nombre"] for p in obtener_almacen(orden="vendidos")["productos"]
                   if p["nombre"] in ("Zeta", "Beta")]
        self.assertEqual(nombres, ["Beta", "Zeta"])

    def test_el_orden_por_vendidos_va_de_mas_a_menos(self):
        poco = self.crear_producto("Vende poco")
        mucho = self.crear_producto("Vende mucho")
        self.vender(poco, 1)
        self.vender(mucho, 20)
        nombres = [p["nombre"] for p in obtener_almacen(orden="vendidos")["productos"]
                   if p["nombre"] in ("Vende poco", "Vende mucho")]
        self.assertEqual(nombres, ["Vende mucho", "Vende poco"])


class ElResumen(SobreUnaCopia):

    def test_total_valor_de_costo_y_sin_existencia(self):
        self.crear_producto("Resumen A", precio_compra=10, stock=5)
        self.crear_producto("Resumen B", precio_compra=20, stock=0)
        datos = obtener_almacen(buscar="Resumen")
        self.assertEqual(datos["resumen"]["total"], 2)
        self.assertAlmostEqual(datos["resumen"]["valor_costo"], 50.0)
        self.assertEqual(datos["resumen"]["sin_existencia"], 1)

    def test_el_resumen_cuenta_solo_lo_filtrado(self):
        self.crear_producto("Solo yo", categoria="Bebidas")
        datos = obtener_almacen(buscar="Solo yo")
        self.assertEqual(datos["resumen"]["total"], 1)


class LosFiltros(SobreUnaCopia):

    def test_buscar_es_insensible_a_mayusculas_y_acentos(self):
        self.crear_producto("Cárnico Especial")
        productos = obtener_almacen(buscar="carnico especial")["productos"]
        self.assertEqual(len(productos), 1)

    def test_categoria_y_proveedor_son_exactos_y_se_combinan(self):
        self.crear_producto("Filtro A", categoria="Bebidas", proveedor="Casa Rubio")
        self.crear_producto("Filtro B", categoria="Bebidas", proveedor="Distribuidora Sur")
        datos = obtener_almacen(categoria="Bebidas", proveedor="Casa Rubio")
        nombres = [p["nombre"] for p in datos["productos"]]
        self.assertIn("Filtro A", nombres)
        self.assertNotIn("Filtro B", nombres)


class LasListasFijas(SobreUnaCopia):

    def test_categorias_siempre_las_doce_completas(self):
        self.assertEqual(obtener_almacen()["categorias"], list(CATEGORIAS))

    def test_proveedores_sale_ordenado_y_sin_vacios(self):
        self.crear_producto("Con proveedor", proveedor="Zeta Distribuciones")
        self.crear_producto("Sin proveedor", proveedor="")
        proveedores = obtener_almacen()["proveedores"]
        self.assertIn("Zeta Distribuciones", proveedores)
        self.assertNotIn("", proveedores)
        self.assertEqual(proveedores, sorted(proveedores, key=str.lower))

    def test_fecha_de_vencimiento_nunca_es_null(self):
        self.crear_producto("Sin vencimiento")
        productos = obtener_almacen(buscar="Sin vencimiento")["productos"]
        self.assertEqual(productos[0]["fecha_vencimiento"], "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
