"""El carrito de la ventana real se comporta igual que el módulo.

Conduce la aplicación oculta: llena la tabla de productos, selecciona uno y
usa el botón de "Agregar al Carrito" como lo haría la cajera.

Esta prueba pasa tanto antes como después de que la interfaz empiece a usar
`lddl/carrito.py`: es la red que permite hacer el cambio sin ir a ciegas.

    python -m unittest discover -s pruebas -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import base  # noqa: E402

from lddl import carrito as c  # noqa: E402

try:
    import ttkbootstrap as tb
    from lddl.ui import VentanaVentas
    HAY_PANTALLA = True
except Exception:
    HAY_PANTALLA = False


# Estas pruebas abren la ventana de verdad, y la ventana lee la base al
# construirse. Se la cambiamos por una copia de la de pruebas antes de que
# se monte nada, y se deshace al terminar el fichero.
_CARPETA = None


def setUpModule():
    global _CARPETA
    _CARPETA = base.empezar_modulo()


def tearDownModule():
    base.terminar_modulo(_CARPETA)


@unittest.skipUnless(HAY_PANTALLA, "hace falta entorno gráfico")
class ElCarritoDeLaVentana(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.root = tb.Window(themename="flatly")
        cls.root.withdraw()
        cls.v = VentanaVentas(cls.root)
        cls.v.mostrar_mensaje = lambda *a, **k: True

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def setUp(self):
        self.v.carrito = []
        self.v.transferencia_var.set(0)
        self.v.actualizar_carrito()

    def _seleccionar_producto_con_stock(self):
        """Deja seleccionado en la tabla el primer producto que tenga stock."""
        self.v.cargar_productos()
        for item in self.v.tabla_resultados.get_children():
            valores = self.v.tabla_resultados.item(item)["values"]
            if float(valores[3]) > 0:
                self.v.tabla_resultados.selection_set(item)
                return valores
        self.skipTest("no hay ningún producto con stock en la base")

    def test_agregar_desde_la_tabla_mete_una_unidad(self):
        valores = self._seleccionar_producto_con_stock()
        self.v.agregar_desde_resultados()

        self.assertEqual(len(self.v.carrito), 1)
        linea = self.v.carrito[0]
        self.assertEqual(linea["id"], int(valores[0]))
        self.assertEqual(linea["nombre"], valores[1])
        self.assertEqual(linea["cantidad"], 1)

    def test_agregar_dos_veces_acumula_en_la_misma_linea(self):
        self._seleccionar_producto_con_stock()
        self.v.agregar_desde_resultados()
        self.v.agregar_desde_resultados()

        self.assertEqual(len(self.v.carrito), 1)
        self.assertEqual(self.v.carrito[0]["cantidad"], 2)

    def test_el_total_de_la_pantalla_coincide_con_el_del_modulo(self):
        self._seleccionar_producto_con_stock()
        self.v.agregar_desde_resultados()
        self.v.agregar_desde_resultados()

        esperado = c.total(self.v.carrito)
        self.assertAlmostEqual(float(self.v.total_var.get()), esperado, places=6)

    def test_la_tabla_muestra_lo_mismo_que_filas_para_tabla(self):
        self._seleccionar_producto_con_stock()
        self.v.agregar_desde_resultados()

        filas_modulo = c.filas_para_tabla(self.v.carrito)
        hijos = self.v.tabla_carrito.get_children()
        self.assertEqual(len(hijos), len(filas_modulo))

        mostrado = self.v.tabla_carrito.item(hijos[0])["values"]
        esperado = filas_modulo[0]
        self.assertEqual(str(mostrado[0]), esperado["nombre"])
        self.assertEqual(str(mostrado[1]), esperado["cantidad"])
        self.assertEqual(str(mostrado[2]), esperado["precio"])
        self.assertEqual(str(mostrado[3]), esperado["subtotal"])

    def test_con_la_pastilla_de_transferencia_lo_pagado_sigue_al_total(self):
        self._seleccionar_producto_con_stock()
        self.v.agregar_desde_resultados()
        self.v.transferencia_var.set(1)
        self.v.actualizar_carrito()

        self.assertEqual(self.v.pagado_var.get(), self.v.total_var.get())
        self.assertEqual(self.v.vuelto_var.get(), "0.00")

    def test_el_carrito_vacio_deja_el_total_en_cero(self):
        self.v.carrito = []
        self.v.actualizar_carrito()
        self.assertEqual(self.v.total_var.get(), "0.00")
        self.assertEqual(len(self.v.tabla_carrito.get_children()), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
