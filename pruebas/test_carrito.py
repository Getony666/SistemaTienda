"""Pruebas del carrito.

Se ejecutan sin abrir la aplicación:

    python -m unittest discover -s pruebas -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mitienda import carrito as c  # noqa: E402

ACEITE = dict(producto_id=3, nombre="Aceite 1000 ml", precio=200.0,
              tipo="unidad", unidad="unidad")
QUESO = dict(producto_id=7, nombre="Queso Gouda", precio=950.0,
             tipo="peso", unidad="lb")


class Sumas(unittest.TestCase):

    def test_total_de_varias_lineas(self):
        carro = [c.linea_nueva(1, "Arroz", 2, 420.0),
                 c.linea_nueva(2, "Aceite", 1, 650.0)]
        self.assertAlmostEqual(c.total(carro), 1490.0)

    def test_carrito_vacio_no_cuesta_nada(self):
        self.assertEqual(c.total(c.vaciar()), 0)

    def test_buscar_encuentra_y_no_inventa(self):
        carro = [c.linea_nueva(3, "Aceite", 1, 200.0)]
        self.assertEqual(c.buscar(carro, 3), 0)
        self.assertIsNone(c.buscar(carro, 99))


class ProductosPorPeso(unittest.TestCase):

    def test_el_subtotal_se_redondea_a_multiplos_de_cinco(self):
        # 0.8 lb a 950 = 760, ya es múltiplo de 5
        self.assertAlmostEqual(c.precio_unitario(0.8, 950.0, "peso") * 0.8, 760.0)

    def test_el_precio_por_libra_sale_del_total_redondeado(self):
        # 0.3 lb a 123 = 36.9 -> se cobra 35 -> la libra sale a 116.67
        unitario = c.precio_unitario(0.3, 123.0, "peso")
        self.assertAlmostEqual(unitario * 0.3, 35.0)
        self.assertAlmostEqual(unitario, 35.0 / 0.3)

    def test_por_unidad_el_precio_no_se_toca(self):
        self.assertEqual(c.precio_unitario(3, 200.0, "unidad"), 200.0)

    def test_cantidad_cero_no_divide_entre_cero(self):
        self.assertEqual(c.precio_unitario(0, 950.0, "peso"), 950.0)


class AgregarUnaUnidad(unittest.TestCase):

    def test_producto_nuevo_entra_con_cantidad_uno(self):
        carro, motivo = c.agregar_unidad(c.vaciar(), stock=10, **ACEITE)
        self.assertIsNone(motivo)
        self.assertEqual(len(carro), 1)
        self.assertEqual(carro[0]["cantidad"], 1)

    def test_producto_repetido_suma_uno(self):
        carro, _ = c.agregar_unidad(c.vaciar(), stock=10, **ACEITE)
        carro, motivo = c.agregar_unidad(carro, stock=10, **ACEITE)
        self.assertIsNone(motivo)
        self.assertEqual(len(carro), 1)
        self.assertEqual(carro[0]["cantidad"], 2)

    def test_sin_stock_no_entra(self):
        carro, motivo = c.agregar_unidad(c.vaciar(), stock=0, **ACEITE)
        self.assertEqual(motivo, "sin_stock")
        self.assertEqual(carro, [])

    def test_no_se_puede_pasar_del_stock(self):
        carro, _ = c.agregar_unidad(c.vaciar(), stock=2, **ACEITE)
        carro, _ = c.agregar_unidad(carro, stock=2, **ACEITE)
        carro, motivo = c.agregar_unidad(carro, stock=2, **ACEITE)
        self.assertEqual(motivo, "stock_insuficiente")
        self.assertEqual(carro[0]["cantidad"], 2)

    def test_el_carrito_original_no_se_toca(self):
        original = c.vaciar()
        c.agregar_unidad(original, stock=10, **ACEITE)
        self.assertEqual(original, [])


class AgregarUnaCantidad(unittest.TestCase):

    def test_cantidad_concreta(self):
        carro, motivo = c.agregar_cantidad(c.vaciar(), cantidad=3, stock=10, **ACEITE)
        self.assertIsNone(motivo)
        self.assertEqual(carro[0]["cantidad"], 3)
        self.assertAlmostEqual(c.total(carro), 600.0)

    def test_cantidad_cero_o_negativa(self):
        for mala in (0, -1):
            _, motivo = c.agregar_cantidad(c.vaciar(), cantidad=mala, stock=10, **ACEITE)
            self.assertEqual(motivo, "cantidad_invalida")

    def test_mas_de_lo_que_hay(self):
        _, motivo = c.agregar_cantidad(c.vaciar(), cantidad=11, stock=10, **ACEITE)
        self.assertEqual(motivo, "stock_insuficiente")

    def test_repetir_promedia_el_precio(self):
        # 2 unidades a 200 y luego 2 a 300 -> 4 unidades a 250
        carro, _ = c.agregar_cantidad(c.vaciar(), cantidad=2, stock=10, **ACEITE)
        otro = dict(ACEITE, precio=300.0)
        carro, _ = c.agregar_cantidad(carro, cantidad=2, stock=10, **otro)
        self.assertEqual(carro[0]["cantidad"], 4)
        self.assertAlmostEqual(carro[0]["precio"], 250.0)
        self.assertAlmostEqual(c.total(carro), 1000.0)

    def test_peso_entra_con_el_precio_ya_ajustado(self):
        carro, _ = c.agregar_cantidad(c.vaciar(), cantidad=0.3, stock=5, **QUESO)
        self.assertAlmostEqual(c.total(carro), 285.0)  # 0.3 x 950 = 285, ya multiplo de 5

    def test_no_se_puede_pasar_del_stock_acumulando(self):
        """El stock se mide contra la suma, no contra la cantidad que entra.

        Antes se podían meter 5 y luego 5 más de algo de lo que quedaban 8, y
        la venta dejaba el almacén en negativo.
        """
        carro, m1 = c.agregar_cantidad(c.vaciar(), cantidad=5, stock=8, **ACEITE)
        carro, m2 = c.agregar_cantidad(carro, cantidad=5, stock=8, **ACEITE)
        self.assertIsNone(m1)
        self.assertEqual(m2, "stock_insuficiente")
        self.assertEqual(carro[0]["cantidad"], 5)

    def test_se_puede_completar_justo_hasta_el_stock(self):
        carro, _ = c.agregar_cantidad(c.vaciar(), cantidad=5, stock=8, **ACEITE)
        carro, motivo = c.agregar_cantidad(carro, cantidad=3, stock=8, **ACEITE)
        self.assertIsNone(motivo)
        self.assertEqual(carro[0]["cantidad"], 8)

    def test_lo_que_queda_por_anadir_descuenta_el_carrito(self):
        vacio = c.vaciar()
        self.assertAlmostEqual(c.disponible_para_anadir(vacio, 3, 8), 8.0)
        carro, _ = c.agregar_cantidad(vacio, cantidad=5, stock=8, **ACEITE)
        self.assertAlmostEqual(c.disponible_para_anadir(carro, 3, 8), 3.0)

    def test_lo_que_queda_por_anadir_nunca_es_negativo(self):
        carro = [c.linea_nueva(3, "Aceite", 10, 200.0)]
        self.assertEqual(c.disponible_para_anadir(carro, 3, 8), 0.0)


class CambiarYQuitar(unittest.TestCase):

    def test_fijar_sustituye_no_suma(self):
        carro, _ = c.agregar_cantidad(c.vaciar(), cantidad=3, stock=10, **ACEITE)
        carro, motivo = c.fijar_cantidad(carro, 0, cantidad=5, stock=10)
        self.assertIsNone(motivo)
        self.assertEqual(carro[0]["cantidad"], 5)

    def test_fijar_respeta_el_stock(self):
        carro, _ = c.agregar_cantidad(c.vaciar(), cantidad=3, stock=10, **ACEITE)
        _, motivo = c.fijar_cantidad(carro, 0, cantidad=11, stock=10)
        self.assertEqual(motivo, "stock_insuficiente")

    def test_fijar_una_linea_que_no_existe(self):
        _, motivo = c.fijar_cantidad(c.vaciar(), 0, cantidad=1, stock=10)
        self.assertEqual(motivo, "linea_inexistente")

    def test_quitar(self):
        carro, _ = c.agregar_unidad(c.vaciar(), stock=10, **ACEITE)
        carro, motivo = c.quitar(carro, 0)
        self.assertIsNone(motivo)
        self.assertEqual(carro, [])

    def test_quitar_una_linea_que_no_existe(self):
        _, motivo = c.quitar(c.vaciar(), 3)
        self.assertEqual(motivo, "linea_inexistente")


class ComoSeMuestra(unittest.TestCase):

    def test_las_cantidades_enteras_van_sin_decimales(self):
        self.assertEqual(c.texto_cantidad(2.0, "unidad"), "2 unidad")
        self.assertEqual(c.texto_cantidad(0.8, "lb"), "0.8 lb")

    def test_filas_para_la_tabla(self):
        carro = [c.linea_nueva(1, "Arroz Blanco 5lb", 2.0, 420.0)]
        fila = c.filas_para_tabla(carro)[0]
        self.assertEqual(fila["nombre"], "Arroz Blanco 5lb")
        self.assertEqual(fila["cantidad"], "2 unidad")
        self.assertEqual(fila["precio"], "420.00")
        self.assertEqual(fila["subtotal"], "840.00")


if __name__ == "__main__":
    unittest.main(verbosity=2)
