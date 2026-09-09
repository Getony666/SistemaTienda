"""Salidas y mermas de un carrito entero.

Todo se ejecuta sobre una COPIA de la base, con `fijar_directorio_base`.

    python -m unittest discover -s pruebas -v
"""

import os
import shutil
import sqlite3
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import base  # noqa: E402
from lddl import rutas  # noqa: E402


class SobreUnaCopia(unittest.TestCase):
    """Cada prueba arranca con una copia limpia de la base."""

    def setUp(self):
        self.temporal = base.carpeta_con_copia("mitienda-inv-")
        rutas.fijar_directorio_base(self.temporal)

    def tearDown(self):
        rutas.fijar_directorio_base(None)
        shutil.rmtree(self.temporal, ignore_errors=True)

    # ---------------------------------------------------------- ayudas

    def consultar(self, sql, parametros=()):
        con = sqlite3.connect(os.path.join(self.temporal, "tienda.db"))
        try:
            return con.execute(sql, parametros).fetchall()
        finally:
            con.close()

    def stock(self, producto_id):
        return self.consultar("SELECT stock FROM productos WHERE id=?", (producto_id,))[0][0]

    def dos_productos_con_stock(self):
        filas = self.consultar(
            "SELECT id, stock, precio_compra FROM productos WHERE stock >= 2 LIMIT 2")
        if len(filas) < 2:
            self.skipTest("hacen falta dos productos con stock en la base")
        return filas


class SalidaDeCarrito(SobreUnaCopia):

    def test_saca_todas_las_lineas_y_genera_una_sola_deuda(self):
        from lddl.inventario import registrar_salida_de_carrito

        (id_a, stock_a, costo_a), (id_b, stock_b, costo_b) = self.dos_productos_con_stock()
        deudas_antes = self.consultar("SELECT COUNT(*) FROM ventas WHERE metodo_pago='Salida'")[0][0]

        exito, mensaje = registrar_salida_de_carrito(
            [{"producto_id": id_a, "cantidad": 2}, {"producto_id": id_b, "cantidad": 1}])
        self.assertTrue(exito, mensaje)

        self.assertAlmostEqual(self.stock(id_a), stock_a - 2)
        self.assertAlmostEqual(self.stock(id_b), stock_b - 1)

        deudas = self.consultar(
            "SELECT id, total FROM ventas WHERE metodo_pago='Salida' ORDER BY id DESC")
        self.assertEqual(len(deudas) - deudas_antes, 1, "debe generarse una sola deuda")
        venta_id, total = deudas[0]
        self.assertAlmostEqual(total, 2 * costo_a + 1 * costo_b)

        detalles = self.consultar(
            "SELECT COUNT(*) FROM detalles_venta WHERE venta_id=?", (venta_id,))[0][0]
        self.assertEqual(detalles, 2)

    def test_se_valora_al_costo_del_almacen_no_al_de_venta(self):
        from lddl.inventario import registrar_salida_de_carrito

        (id_a, _stock, costo_a), _b = self.dos_productos_con_stock()
        registrar_salida_de_carrito([{"producto_id": id_a, "cantidad": 2}])
        total = self.consultar(
            "SELECT total FROM ventas WHERE metodo_pago='Salida' ORDER BY id DESC LIMIT 1")[0][0]
        self.assertAlmostEqual(total, 2 * costo_a)

    def test_si_una_linea_no_tiene_stock_no_se_guarda_ninguna(self):
        from lddl.inventario import registrar_salida_de_carrito

        (id_a, stock_a, _), (id_b, stock_b, _) = self.dos_productos_con_stock()
        exito, motivo = registrar_salida_de_carrito([
            {"producto_id": id_a, "cantidad": 1},
            {"producto_id": id_b, "cantidad": stock_b + 999},
        ])
        self.assertFalse(exito)
        self.assertIn("insuficiente", motivo.lower())
        self.assertAlmostEqual(self.stock(id_a), stock_a, msg="no debio tocar la primera linea")
        self.assertAlmostEqual(self.stock(id_b), stock_b)

    def test_un_producto_inexistente_lo_rechaza_entero(self):
        from lddl.inventario import registrar_salida_de_carrito

        (id_a, stock_a, _), _b = self.dos_productos_con_stock()
        exito, _motivo = registrar_salida_de_carrito([
            {"producto_id": id_a, "cantidad": 1},
            {"producto_id": 999999, "cantidad": 1},
        ])
        self.assertFalse(exito)
        self.assertAlmostEqual(self.stock(id_a), stock_a)

    def test_el_carrito_vacio_se_rechaza(self):
        from lddl.inventario import registrar_salida_de_carrito
        self.assertFalse(registrar_salida_de_carrito([])[0])

    def test_revertirla_devuelve_el_stock_de_TODAS_las_lineas(self):
        """Lo que se rompia si la salida de varias lineas se guardaba a la vieja."""
        from lddl.historial import revertir_registro
        from lddl.inventario import registrar_salida_de_carrito

        (id_a, stock_a, _), (id_b, stock_b, _) = self.dos_productos_con_stock()
        self.assertTrue(registrar_salida_de_carrito(
            [{"producto_id": id_a, "cantidad": 2}, {"producto_id": id_b, "cantidad": 1}])[0])

        registro = self.consultar(
            "SELECT id FROM historial WHERE tipo_accion='Salida de Producto' ORDER BY id DESC LIMIT 1")
        exito, mensaje = revertir_registro(registro[0][0], "Salida de Producto")
        self.assertTrue(exito, mensaje)

        self.assertAlmostEqual(self.stock(id_a), stock_a, msg="la primera linea no volvio")
        self.assertAlmostEqual(self.stock(id_b), stock_b, msg="la segunda linea no volvio")

    def test_revertirla_borra_la_deuda_y_las_filas_del_almacen(self):
        from lddl.historial import revertir_registro
        from lddl.inventario import registrar_salida_de_carrito

        (id_a, _sa, _), (id_b, _sb, _) = self.dos_productos_con_stock()
        salidas_antes = self.consultar("SELECT COUNT(*) FROM salidas_inventario")[0][0]
        deudas_antes = self.consultar("SELECT COUNT(*) FROM ventas WHERE metodo_pago='Salida'")[0][0]

        registrar_salida_de_carrito(
            [{"producto_id": id_a, "cantidad": 2}, {"producto_id": id_b, "cantidad": 1}])
        registro = self.consultar(
            "SELECT id FROM historial WHERE tipo_accion='Salida de Producto' ORDER BY id DESC LIMIT 1")
        revertir_registro(registro[0][0], "Salida de Producto")

        self.assertEqual(self.consultar("SELECT COUNT(*) FROM salidas_inventario")[0][0],
                         salidas_antes)
        self.assertEqual(
            self.consultar("SELECT COUNT(*) FROM ventas WHERE metodo_pago='Salida'")[0][0],
            deudas_antes)


class MermaDeCarrito(SobreUnaCopia):

    def test_baja_el_stock_sin_mover_dinero(self):
        from lddl.inventario import registrar_merma_de_carrito

        (id_a, stock_a, _), (id_b, stock_b, _) = self.dos_productos_con_stock()
        ventas_antes = self.consultar("SELECT COUNT(*) FROM ventas")[0][0]
        efectivo_antes = self.consultar("SELECT COUNT(*) FROM entradas_efectivo")[0][0]

        exito, mensaje = registrar_merma_de_carrito(
            [{"producto_id": id_a, "cantidad": 2}, {"producto_id": id_b, "cantidad": 1}])
        self.assertTrue(exito, mensaje)

        self.assertAlmostEqual(self.stock(id_a), stock_a - 2)
        self.assertAlmostEqual(self.stock(id_b), stock_b - 1)
        self.assertEqual(self.consultar("SELECT COUNT(*) FROM ventas")[0][0], ventas_antes,
                         "una merma no genera ninguna venta ni deuda")
        self.assertEqual(self.consultar("SELECT COUNT(*) FROM entradas_efectivo")[0][0],
                         efectivo_antes)

    def test_cada_linea_queda_como_su_propia_merma(self):
        from lddl.inventario import registrar_merma_de_carrito

        (id_a, _sa, _), (id_b, _sb, _) = self.dos_productos_con_stock()
        antes = self.consultar("SELECT COUNT(*) FROM salidas_inventario")[0][0]
        registrar_merma_de_carrito(
            [{"producto_id": id_a, "cantidad": 2}, {"producto_id": id_b, "cantidad": 1}])
        self.assertEqual(self.consultar("SELECT COUNT(*) FROM salidas_inventario")[0][0],
                         antes + 2)

    def test_si_una_linea_falla_no_se_guarda_ninguna(self):
        from lddl.inventario import registrar_merma_de_carrito

        (id_a, stock_a, _), (id_b, stock_b, _) = self.dos_productos_con_stock()
        exito, _motivo = registrar_merma_de_carrito([
            {"producto_id": id_a, "cantidad": 1},
            {"producto_id": id_b, "cantidad": stock_b + 999},
        ])
        self.assertFalse(exito)
        self.assertAlmostEqual(self.stock(id_a), stock_a)

    def test_revertir_una_linea_devuelve_solo_esa(self):
        from lddl.historial import revertir_registro
        from lddl.inventario import registrar_merma_de_carrito

        (id_a, stock_a, _), (id_b, stock_b, _) = self.dos_productos_con_stock()
        registrar_merma_de_carrito(
            [{"producto_id": id_a, "cantidad": 2}, {"producto_id": id_b, "cantidad": 1}])

        fila = self.consultar(
            "SELECT id FROM salidas_inventario WHERE producto_id=? ORDER BY id DESC LIMIT 1",
            (id_a,))
        exito, mensaje = revertir_registro(fila[0][0], "Merma")
        self.assertTrue(exito, mensaje)
        self.assertAlmostEqual(self.stock(id_a), stock_a)
        self.assertAlmostEqual(self.stock(id_b), stock_b - 1, msg="la otra no debio moverse")


class ElCostoViajaEnLaLista(SobreUnaCopia):

    def test_buscar_productos_devuelve_el_precio_de_compra(self):
        from lddl.productos import buscar_productos

        productos = buscar_productos("")
        self.assertTrue(productos)
        self.assertEqual(len(productos[0]), 7, "falta el precio de compra al final")

    def test_las_posiciones_de_siempre_no_se_movieron(self):
        """Los paneles de tkinter leen estas tuplas por indice."""
        from lddl.productos import buscar_productos

        p = buscar_productos("")[0]
        con = sqlite3.connect(os.path.join(self.temporal, "tienda.db"))
        fila = con.execute(
            "SELECT id, nombre, precio_venta, stock, tipo_producto, unidad_medida, precio_compra"
            " FROM productos WHERE id=?", (p[0],)).fetchone()
        con.close()
        self.assertEqual(tuple(p), tuple(fila))


if __name__ == "__main__":
    unittest.main(verbosity=2)
