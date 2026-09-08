"""Pruebas del cálculo de pago y vuelto.

Se ejecutan sin abrir la aplicación:

    python -m unittest discover -s pruebas -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lddl.calculo_cobro import (  # noqa: E402
    Pago,
    a_numero,
    calcular_vuelto,
    cup_faltante,
    desglosar_para_registro,
    maximo_vuelto_en_moneda,
    redondear_subtotal_peso,
    texto_pago_para_registro,
    texto_vuelto,
)


class PagoEnCup(unittest.TestCase):

    def test_paga_justo(self):
        v = calcular_vuelto(Pago(total_cup=2250.0, efectivo=2250.0))
        self.assertTrue(v.cubre)
        self.assertEqual(v.vuelto_cup, 0.0)
        self.assertEqual(v.falta_cup, 0.0)

    def test_paga_de_mas(self):
        v = calcular_vuelto(Pago(total_cup=2250.0, efectivo=2300.0))
        self.assertTrue(v.cubre)
        self.assertAlmostEqual(v.vuelto_cup, 50.0)

    def test_no_alcanza(self):
        v = calcular_vuelto(Pago(total_cup=2250.0, efectivo=2000.0))
        self.assertFalse(v.cubre)
        self.assertAlmostEqual(v.falta_cup, 250.0)
        self.assertEqual(v.vuelto_cup, 0.0)

    def test_sin_pagar_nada_no_cubre(self):
        v = calcular_vuelto(Pago(total_cup=100.0))
        self.assertFalse(v.cubre)
        self.assertAlmostEqual(v.falta_cup, 100.0)

    def test_efectivo_mas_transferencia(self):
        v = calcular_vuelto(Pago(total_cup=1000.0, efectivo=400.0, transferencia=700.0))
        self.assertTrue(v.cubre)
        self.assertAlmostEqual(v.vuelto_cup, 100.0)

    def test_pastilla_transferencia_cubre_el_total(self):
        v = calcular_vuelto(Pago(total_cup=1000.0, solo_transferencia=True))
        self.assertTrue(v.cubre)
        self.assertEqual(v.vuelto_cup, 0.0)


class PagoEnDivisa(unittest.TestCase):

    def test_divisa_cubre_justo(self):
        v = calcular_vuelto(Pago(total_cup=4000.0, moneda="USD", tasa=400.0, efectivo=10.0))
        self.assertTrue(v.cubre)
        self.assertEqual(v.vuelto_cup, 0.0)

    def test_divisa_de_mas_devuelve_en_cup(self):
        v = calcular_vuelto(Pago(total_cup=5000.0, moneda="USD", tasa=400.0, efectivo=15.0))
        self.assertTrue(v.cubre)
        self.assertAlmostEqual(v.vuelto_cup, 1000.0)
        self.assertAlmostEqual(v.vuelto_cup_restante, 1000.0)
        self.assertEqual(v.vuelto_moneda, 0.0)

    def test_divisa_no_alcanza(self):
        v = calcular_vuelto(Pago(total_cup=5000.0, moneda="USD", tasa=400.0, efectivo=10.0))
        self.assertFalse(v.cubre)
        self.assertAlmostEqual(v.falta_cup, 1000.0)

    def test_divisa_mas_cup_adicional(self):
        v = calcular_vuelto(Pago(total_cup=5000.0, moneda="USD", tasa=400.0,
                                 efectivo=10.0, cup_efectivo=1000.0))
        self.assertTrue(v.cubre)
        self.assertEqual(v.vuelto_cup, 0.0)

    def test_vuelto_repartido_entre_divisa_y_cup(self):
        v = calcular_vuelto(Pago(total_cup=5000.0, moneda="USD", tasa=400.0,
                                 efectivo=15.0, vuelto_en_moneda=2.0))
        self.assertTrue(v.cubre)
        self.assertAlmostEqual(v.vuelto_cup, 1000.0)
        self.assertAlmostEqual(v.vuelto_moneda, 2.0)
        self.assertAlmostEqual(v.vuelto_cup_restante, 200.0)

    def test_todo_el_vuelto_en_divisa(self):
        v = calcular_vuelto(Pago(total_cup=5000.0, moneda="USD", tasa=400.0,
                                 efectivo=15.0, vuelto_en_moneda=2.5))
        self.assertAlmostEqual(v.vuelto_moneda, 2.5)
        self.assertAlmostEqual(v.vuelto_cup_restante, 0.0)

    def test_vuelto_en_divisa_que_excede_es_error(self):
        v = calcular_vuelto(Pago(total_cup=5000.0, moneda="USD", tasa=400.0,
                                 efectivo=15.0, vuelto_en_moneda=5.0))
        self.assertEqual(v.error, "vuelto_moneda_excede")

    def test_tasa_cero_es_error(self):
        v = calcular_vuelto(Pago(total_cup=100.0, moneda="USD", tasa=0.0, efectivo=1.0))
        self.assertEqual(v.error, "tasa_invalida")

    def test_montos_negativos_son_error(self):
        self.assertEqual(
            calcular_vuelto(Pago(total_cup=100.0, moneda="USD", tasa=400.0,
                                 efectivo=1.0, cup_efectivo=-5.0)).error,
            "cup_efectivo_negativo")
        self.assertEqual(
            calcular_vuelto(Pago(total_cup=100.0, moneda="USD", tasa=400.0,
                                 efectivo=1.0, cup_transferencia=-5.0)).error,
            "cup_transferencia_negativo")


class Ayudas(unittest.TestCase):

    def test_cup_que_falta_al_pagar_en_divisa(self):
        self.assertAlmostEqual(cup_faltante(5000.0, 10.0, 400.0), 1000.0)

    def test_cup_que_falta_nunca_es_negativo(self):
        self.assertEqual(cup_faltante(4000.0, 15.0, 400.0), 0.0)

    def test_maximo_vuelto_en_moneda(self):
        self.assertAlmostEqual(maximo_vuelto_en_moneda(1000.0, 400.0), 2.5)

    def test_a_numero_tolera_vacios_y_basura(self):
        self.assertEqual(a_numero(""), 0.0)
        self.assertEqual(a_numero("  "), 0.0)
        self.assertEqual(a_numero("abc"), 0.0)
        self.assertEqual(a_numero(None), 0.0)
        self.assertEqual(a_numero(" 12.5 "), 12.5)

    def test_peso_se_redondea_a_multiplos_de_cinco(self):
        self.assertEqual(redondear_subtotal_peso(0.8, 950.0), 760)
        self.assertEqual(redondear_subtotal_peso(1.0, 123.0), 125)
        self.assertEqual(redondear_subtotal_peso(1.0, 122.0), 120)


class DesgloseParaGuardar(unittest.TestCase):

    def test_cup_sin_vuelto(self):
        d = desglosar_para_registro(Pago(total_cup=1000.0, efectivo=1000.0))
        self.assertEqual(d.metodo_pago_real, "Efectivo")
        self.assertAlmostEqual(d.monto_efectivo_cup, 1000.0)
        self.assertEqual(d.vuelto_texto, "0.00 CUP")

    def test_cup_con_vuelto_se_descuenta_del_efectivo(self):
        d = desglosar_para_registro(Pago(total_cup=1000.0, efectivo=1200.0))
        self.assertAlmostEqual(d.monto_efectivo_cup, 1000.0)
        self.assertEqual(d.vuelto_texto, "200.00 CUP")

    def test_mixto_el_vuelto_sale_primero_del_efectivo(self):
        # 200 en efectivo + 900 por transferencia para una venta de 1000:
        # el vuelto de 100 se descuenta del efectivo, la transferencia no se toca.
        d = desglosar_para_registro(Pago(total_cup=1000.0, efectivo=200.0, transferencia=900.0))
        self.assertEqual(d.metodo_pago_real, "Mixto")
        self.assertAlmostEqual(d.monto_efectivo_cup, 100.0)
        self.assertAlmostEqual(d.monto_transferencia_cup, 900.0)
        self.assertAlmostEqual(d.monto_efectivo_cup + d.monto_transferencia_cup, 1000.0)

    def test_mixto_cuando_el_vuelto_supera_el_efectivo_recibido(self):
        # 50 en efectivo + 1200 por transferencia para una venta de 1000:
        # el vuelto de 250 se lleva los 50 de efectivo y 200 de la transferencia.
        d = desglosar_para_registro(Pago(total_cup=1000.0, efectivo=50.0, transferencia=1200.0))
        self.assertAlmostEqual(d.monto_efectivo_cup, 0.0)
        self.assertAlmostEqual(d.monto_transferencia_cup, 1000.0)
        self.assertAlmostEqual(d.monto_efectivo_cup + d.monto_transferencia_cup, 1000.0)

    def test_pastilla_transferencia(self):
        d = desglosar_para_registro(Pago(total_cup=1000.0, solo_transferencia=True))
        self.assertEqual(d.metodo_pago, "Transferencia")
        self.assertAlmostEqual(d.monto_transferencia_cup, 1000.0)
        self.assertAlmostEqual(d.monto_efectivo_cup, 0.0)

    def test_divisa_el_vuelto_se_descuenta_del_cup_entregado(self):
        d = desglosar_para_registro(Pago(total_cup=5000.0, moneda="USD", tasa=400.0,
                                         efectivo=10.0, cup_efectivo=1500.0))
        self.assertEqual(d.metodo_pago_real, "Mixto")
        self.assertAlmostEqual(d.monto_efectivo_cup, 1000.0)
        self.assertAlmostEqual(d.salida_efectivo_extra, 0.0)

    def test_divisa_el_vuelto_que_no_cubre_el_cup_sale_de_la_caja(self):
        d = desglosar_para_registro(Pago(total_cup=5000.0, moneda="USD", tasa=400.0,
                                         efectivo=15.0))
        self.assertAlmostEqual(d.monto_efectivo_cup, 0.0)
        self.assertAlmostEqual(d.salida_efectivo_extra, 1000.0)

    def test_divisa_sin_divisa_la_venta_pasa_a_cup(self):
        d = desglosar_para_registro(Pago(total_cup=500.0, moneda="USD", tasa=400.0,
                                         efectivo=0.0, cup_efectivo=500.0))
        self.assertEqual(d.moneda_pago, "CUP")
        self.assertEqual(d.tasa_cambio, 1.0)

    def test_deuda_deja_el_saldo_pendiente(self):
        d = desglosar_para_registro(Pago(total_cup=1220.0, efectivo=0.0), es_deuda=True)
        self.assertEqual(d.pagada, 0)
        self.assertAlmostEqual(d.saldo_pendiente, 1220.0)
        self.assertEqual(d.pago_texto, "Deuda registrada")
        self.assertAlmostEqual(d.monto_efectivo_cup, 0.0)


class Textos(unittest.TestCase):

    def test_pago_en_cup_mixto(self):
        p = Pago(total_cup=1000.0, efectivo=400.0, transferencia=700.0)
        self.assertEqual(texto_pago_para_registro(p),
                         "Efectivo: 400.00 CUP + Transferencia: 700.00 CUP")

    def test_pago_en_divisa_con_cup_encima(self):
        p = Pago(total_cup=5000.0, moneda="USD", tasa=400.0, efectivo=10.0, cup_efectivo=1000.0)
        self.assertEqual(texto_pago_para_registro(p),
                         "10.00 USD + 1000.00 CUP (efectivo)")

    def test_vuelto_repartido(self):
        p = Pago(total_cup=5000.0, moneda="USD", tasa=400.0, efectivo=15.0, vuelto_en_moneda=2.0)
        self.assertEqual(texto_vuelto(calcular_vuelto(p), "USD"), "2.00 USD + 200.00 CUP")

    def test_vuelto_solo_en_cup(self):
        p = Pago(total_cup=5000.0, moneda="USD", tasa=400.0, efectivo=15.0)
        self.assertEqual(texto_vuelto(calcular_vuelto(p), "USD"), "1000.00 CUP")

    def test_sin_vuelto(self):
        p = Pago(total_cup=1000.0, efectivo=1000.0)
        self.assertEqual(texto_vuelto(calcular_vuelto(p), "CUP"), "0.00 CUP")


if __name__ == "__main__":
    unittest.main(verbosity=2)
