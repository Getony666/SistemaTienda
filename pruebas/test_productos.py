"""Alta y edición de productos: categoría por defecto y "None = no cambiar".

Todo sobre una COPIA de la base de pruebas.

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
from mitienda import rutas  # noqa: E402
from mitienda.esquema import preparar_base  # noqa: E402
from mitienda.productos import (  # noqa: E402
    CATEGORIAS, actualizar_producto, agregar_producto, normalizar_categoria,
)


class SobreUnaCopia(unittest.TestCase):
    """Cada prueba arranca con una copia limpia de la base."""

    def setUp(self):
        self.temporal = base.carpeta_con_copia("mitienda-prod-")
        rutas.fijar_directorio_base(self.temporal)

    def tearDown(self):
        rutas.fijar_directorio_base(None)
        shutil.rmtree(self.temporal, ignore_errors=True)

    def conexion(self):
        return sqlite3.connect(os.path.join(self.temporal, "tienda.db"))

    def fila(self, producto_id):
        con = self.conexion()
        try:
            return con.execute(
                "SELECT nombre, categoria, precio_compra, precio_venta, stock, proveedor,"
                " tipo_producto, unidad_medida, fecha_vencimiento FROM productos WHERE id=?",
                (producto_id,)).fetchone()
        finally:
            con.close()

    def crear(self, **kwargs):
        datos = dict(nombre="Producto de prueba", categoria="", precio_compra=10,
                     precio_venta=20, stock=5, proveedor="Casa Rubio")
        datos.update(kwargs)
        exito, mensaje = agregar_producto(**datos)
        self.assertTrue(exito, mensaje)
        con = self.conexion()
        try:
            return con.execute(
                "SELECT id FROM productos WHERE nombre=? ORDER BY id DESC LIMIT 1",
                (datos["nombre"],)).fetchone()[0]
        finally:
            con.close()


class LaCategoriaPorDefecto(SobreUnaCopia):
    """La categoría no es obligatoria: lo que no encaje cae en "Otros"."""

    def test_vacia_se_guarda_como_otros(self):
        pid = self.crear(categoria="")
        self.assertEqual(self.fila(pid)[1], "Otros")

    def test_none_se_guarda_como_otros(self):
        pid = self.crear(categoria=None)
        self.assertEqual(self.fila(pid)[1], "Otros")

    def test_una_inventada_se_guarda_como_otros(self):
        pid = self.crear(categoria="Ferretería")
        self.assertEqual(self.fila(pid)[1], "Otros")

    def test_una_valida_se_respeta(self):
        pid = self.crear(categoria="Lácteos")
        self.assertEqual(self.fila(pid)[1], "Lácteos")

    def test_normalizar_categoria_a_pelo(self):
        self.assertEqual(normalizar_categoria(""), "Otros")
        self.assertEqual(normalizar_categoria(None), "Otros")
        self.assertEqual(normalizar_categoria("   "), "Otros")
        self.assertEqual(normalizar_categoria("Bebidas"), "Bebidas")
        self.assertEqual(CATEGORIAS[-1], "Otros")


class ActualizarNoBorraLoQueNoLlega(SobreUnaCopia):
    """None significa "no cambiar"; una cadena vacía es un valor real."""

    def test_sin_mandar_proveedor_no_lo_borra(self):
        """El bug de verdad: una pantalla sin ese campo mandaba proveedor=''
        y se comía lo que ya había. Con None no pasa."""
        pid = self.crear(proveedor="Distribuidora Sur")
        exito, mensaje = actualizar_producto(pid, "Producto de prueba", proveedor=None)
        self.assertTrue(exito, mensaje)
        self.assertEqual(self.fila(pid)[5], "Distribuidora Sur")

    def test_mandando_proveedor_vacio_si_lo_borra(self):
        pid = self.crear(proveedor="Distribuidora Sur")
        actualizar_producto(pid, "Producto de prueba", proveedor="")
        self.assertEqual(self.fila(pid)[5], "")

    def test_stock_en_cero_si_se_aplica(self):
        """El cero es un valor real: "None = no cambiar" no se lo puede comer."""
        pid = self.crear(stock=8)
        exito, mensaje = actualizar_producto(pid, "Producto de prueba", stock=0)
        self.assertTrue(exito, mensaje)
        self.assertEqual(self.fila(pid)[4], 0.0)

    def test_precio_compra_en_cero_si_se_aplica(self):
        pid = self.crear(precio_compra=15)
        actualizar_producto(pid, "Producto de prueba", precio_compra=0)
        self.assertEqual(self.fila(pid)[2], 0.0)

    def test_sin_mandar_nada_conserva_todo(self):
        pid = self.crear(categoria="Aseo personal", precio_compra=12, precio_venta=25,
                         stock=9, proveedor="Casa Rubio", tipo_producto="peso",
                         unidad_medida="kg", fecha_vencimiento="2027-01-01")
        antes = self.fila(pid)
        exito, mensaje = actualizar_producto(pid, "Producto de prueba")
        self.assertTrue(exito, mensaje)
        self.assertEqual(self.fila(pid), antes)

    def test_categoria_none_conserva_la_actual(self):
        pid = self.crear(categoria="Confituras")
        actualizar_producto(pid, "Producto de prueba", categoria=None)
        self.assertEqual(self.fila(pid)[1], "Confituras")

    def test_categoria_vacia_al_actualizar_tambien_cae_en_otros(self):
        pid = self.crear(categoria="Confituras")
        actualizar_producto(pid, "Producto de prueba", categoria="")
        self.assertEqual(self.fila(pid)[1], "Otros")


class LaMigracionDeCategorias(SobreUnaCopia):
    """`preparar_base` deja "Otros" a los productos viejos, sin tocar los que
    ya tenían una categoría válida, y correrla de más no cambia nada."""

    def test_deja_otros_a_los_productos_sin_categoria(self):
        con = self.conexion()
        con.execute("UPDATE productos SET categoria = ''")
        con.commit()
        con.close()

        preparar_base()

        con = self.conexion()
        vacias = con.execute(
            "SELECT COUNT(*) FROM productos WHERE categoria IS NULL OR TRIM(categoria) = ''"
        ).fetchone()[0]
        total_otros = con.execute(
            "SELECT COUNT(*) FROM productos WHERE categoria = 'Otros'").fetchone()[0]
        con.close()
        self.assertEqual(vacias, 0)
        self.assertGreater(total_otros, 0)

    def test_no_toca_una_categoria_ya_valida(self):
        con = self.conexion()
        con.execute("UPDATE productos SET categoria = 'Lácteos' WHERE id = "
                    "(SELECT id FROM productos LIMIT 1)")
        con.commit()
        producto_id = con.execute("SELECT id FROM productos LIMIT 1").fetchone()[0]
        con.close()

        preparar_base()

        con = self.conexion()
        categoria = con.execute(
            "SELECT categoria FROM productos WHERE id = ?", (producto_id,)).fetchone()[0]
        con.close()
        self.assertEqual(categoria, "Lácteos")

    def test_correrla_dos_veces_no_cambia_nada_la_segunda(self):
        con = self.conexion()
        con.execute("UPDATE productos SET categoria = '' WHERE id = "
                    "(SELECT id FROM productos LIMIT 1)")
        con.commit()
        con.close()

        preparar_base()
        con = self.conexion()
        despues_de_una = con.execute(
            "SELECT id, categoria FROM productos ORDER BY id").fetchall()
        con.close()

        preparar_base()
        con = self.conexion()
        despues_de_dos = con.execute(
            "SELECT id, categoria FROM productos ORDER BY id").fetchall()
        con.close()

        self.assertEqual(despues_de_una, despues_de_dos)


if __name__ == "__main__":
    unittest.main(verbosity=2)
