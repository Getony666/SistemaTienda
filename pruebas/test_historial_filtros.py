"""Los filtros del historial: mensajería y producto.

Se trabaja siempre sobre una COPIA de la base de pruebas.

    python -m unittest discover -s pruebas -v
"""

import os
import shutil
import sqlite3
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import base  # noqa: E402
from lddl import rutas  # noqa: E402


class SobreUnaCopia(unittest.TestCase):

    def setUp(self):
        self.temporal = base.carpeta_con_copia("mitienda-hist-")
        rutas.fijar_directorio_base(self.temporal)

    def tearDown(self):
        rutas.fijar_directorio_base(None)
        shutil.rmtree(self.temporal, ignore_errors=True)

    def conexion(self):
        return sqlite3.connect(os.path.join(self.temporal, "tienda.db"))

    def dos_productos(self):
        con = self.conexion()
        try:
            filas = con.execute(
                "SELECT id, nombre FROM productos WHERE stock >= 1 LIMIT 2").fetchall()
        finally:
            con.close()
        if len(filas) < 2:
            self.skipTest("hacen falta dos productos en la base")
        return filas

    def vender(self, producto_id, mensajeria):
        """Mete una venta directamente, para no depender del cobro."""
        con = self.conexion()
        try:
            cur = con.cursor()
            cur.execute(
                "INSERT INTO ventas (fecha, total, metodo_pago, es_deuda, pagada,"
                " es_mensajeria, metodo_pago_real, cancelada)"
                " VALUES ('2026-09-09 10:00:00', 100, 'Efectivo', 0, 1, ?, 'Efectivo', 0)",
                (1 if mensajeria else 0,))
            venta_id = cur.lastrowid
            cur.execute(
                "INSERT INTO detalles_venta (venta_id, producto_id, cantidad, precio_unitario)"
                " VALUES (?, ?, 1, 100)", (venta_id, producto_id))
            con.commit()
            return venta_id
        finally:
            con.close()


class FiltroDeMensajeria(SobreUnaCopia):

    def test_solo_devuelve_las_marcadas(self):
        from lddl.ventas_datos import obtener_ventas

        (id_a, _), (id_b, _) = self.dos_productos()
        con_mensajeria = self.vender(id_a, mensajeria=True)
        sin_mensajeria = self.vender(id_b, mensajeria=False)

        ids = {r["id"] for r in obtener_ventas(filtro_tipo="mensajeria")}
        self.assertIn(con_mensajeria, ids)
        self.assertNotIn(sin_mensajeria, ids)

    def test_cada_venta_dice_si_es_mensajeria_sin_abrir_el_detalle(self):
        """La tabla pinta la columna con esto, no con detalle_extra."""
        from lddl.ventas_datos import obtener_ventas

        (id_a, _), (id_b, _) = self.dos_productos()
        marcada = self.vender(id_a, mensajeria=True)
        normal = self.vender(id_b, mensajeria=False)

        por_id = {r["id"]: r for r in obtener_ventas(filtro_tipo="ventas")}
        self.assertEqual(por_id[marcada]["es_mensajeria"], 1)
        self.assertEqual(por_id[normal]["es_mensajeria"], 0)

    def test_una_deuda_marcada_tambien_sale(self):
        """La mensajería es una marca, no un tipo: puede ir sobre una deuda."""
        from lddl.ventas_datos import obtener_ventas

        (id_a, _), _b = self.dos_productos()
        con = self.conexion()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO ventas (fecha, total, metodo_pago, es_deuda, pagada,"
            " saldo_pendiente, es_mensajeria, cancelada)"
            " VALUES ('2026-09-09 11:00:00', 200, 'Efectivo', 1, 0, 200, 1, 0)")
        deuda_id = cur.lastrowid
        cur.execute(
            "INSERT INTO detalles_venta (venta_id, producto_id, cantidad, precio_unitario)"
            " VALUES (?, ?, 1, 200)", (deuda_id, id_a))
        con.commit()
        con.close()

        ids = {r["id"] for r in obtener_ventas(filtro_tipo="mensajeria")}
        self.assertIn(deuda_id, ids)

    def test_sin_filtro_salen_las_dos(self):
        from lddl.ventas_datos import obtener_ventas

        (id_a, _), (id_b, _) = self.dos_productos()
        a = self.vender(id_a, mensajeria=True)
        b = self.vender(id_b, mensajeria=False)
        ids = {r["id"] for r in obtener_ventas(filtro_tipo="todos")}
        self.assertIn(a, ids)
        self.assertIn(b, ids)

    def test_no_arrastra_movimientos_de_caja(self):
        """Un cambio de divisa no es una mensajería y no debe colarse."""
        from lddl.ventas_datos import obtener_ventas

        con = self.conexion()
        con.execute(
            "INSERT INTO operaciones_cambio (fecha, tipo, moneda, cantidad, tasa, monto_cup)"
            " VALUES ('2026-09-09 12:00:00', 'Compra', 'USD', 10, 400, 4000)")
        con.commit()
        con.close()

        tipos = {r["tipo"] for r in obtener_ventas(filtro_tipo="mensajeria")}
        self.assertNotIn("Cambio de Divisa", tipos)


class FiltroDeProducto(SobreUnaCopia):

    def test_solo_las_lineas_que_llevan_ese_producto(self):
        from lddl.ventas_datos import obtener_ventas

        (id_a, _), (id_b, _) = self.dos_productos()
        con_a = self.vender(id_a, mensajeria=False)
        con_b = self.vender(id_b, mensajeria=False)

        ids = {r["id"] for r in obtener_ventas(producto_id=id_a)}
        self.assertIn(con_a, ids)
        self.assertNotIn(con_b, ids)

    def test_recoge_tambien_lo_que_no_son_ventas(self):
        """Una merma de ese producto tiene que aparecer con las ventas."""
        from lddl.inventario import registrar_merma_de_carrito
        from lddl.ventas_datos import obtener_ventas

        (id_a, nombre_a), _b = self.dos_productos()
        self.vender(id_a, mensajeria=False)
        self.assertTrue(registrar_merma_de_carrito(
            [{"producto_id": id_a, "cantidad": 1}])[0])

        registros = obtener_ventas(producto_id=id_a)
        tipos = {r["tipo"] for r in registros}
        self.assertIn("Venta", tipos)
        self.assertIn("Merma", tipos, "la merma del producto tiene que salir")

    def test_los_movimientos_de_caja_se_quedan_fuera(self):
        """No tienen producto, asi que no pueden ser de ninguno."""
        from lddl.ventas_datos import obtener_ventas

        (id_a, _), _b = self.dos_productos()
        con = self.conexion()
        con.execute(
            "INSERT INTO entradas_efectivo (fecha, moneda, monto, descripcion)"
            " VALUES ('2026-09-09 12:00:00', 'CUP', 500, 'prueba')")
        con.commit()
        con.close()

        tipos = {r["tipo"] for r in obtener_ventas(producto_id=id_a)}
        self.assertNotIn("Entrada de efectivo", tipos)


if __name__ == "__main__":
    unittest.main(verbosity=2)
