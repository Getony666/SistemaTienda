"""El cobro de deudas no puede cambiar.

DEUDA guarda lo que el diálogo de Pagar Deuda enviaba a la base antes de sacar
la aritmética a `mitienda/calculo_deuda.py`. Se obtuvo conduciendo el diálogo real
con un espía en lugar de `registrar_cobro_deuda_en_db`, sobre una copia de la
base: ningún cobro llegó a guardarse.

    python -m unittest discover -s pruebas -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mitienda.calculo_deuda import (  # noqa: E402
    Abono,
    calcular_cobro,
    observaciones_del_cobro,
    resumen_del_cobro,
    total_pagado,
    vuelto_en_cup_a_entregar,
)

SALDO = 1000.0

# (nombre, moneda, metodo, tasa, efectivo, efectivo_cup, transferencia, vuelto_moneda)
ESCENARIOS = [
    ("CUP parcial",           "CUP", "Efectivo",      1.0,   300.0, 0.0,   0.0,   0.0),
    ("CUP total exacto",      "CUP", "Efectivo",      1.0,  1000.0, 0.0,   0.0,   0.0),
    ("CUP total con vuelto",  "CUP", "Efectivo",      1.0,  1200.0, 0.0,   0.0,   0.0),
    ("CUP transferencia",     "CUP", "Transferencia", 1.0,     0.0, 0.0, 1000.0,  0.0),
    ("CUP mixto",             "CUP", "Mixto",         1.0,   400.0, 0.0,  600.0,  0.0),
    ("USD parcial",           "USD", "Efectivo",    400.0,     2.0, 0.0,   0.0,   0.0),
    ("USD con CUP adicional", "USD", "Efectivo",    400.0,     2.0, 200.0, 0.0,   0.0),
    ("USD total con vuelto",  "USD", "Efectivo",    400.0,     3.0, 0.0,   0.0,   0.0),
]

DEUDA = {
    "CUP parcial": {"moneda": "CUP", "tasa": 1.0, "metodo": "Efectivo", "efectivo": 300.0,
                    "transferencia": 0.0, "efectivo_cup": 0.0, "vuelto_cup": 0.0,
                    "vuelto_moneda": 0.0, "total_pagado_moneda": 300.0,
                    "total_pagado_cup": 300.0, "nuevo_saldo": 700.0, "pagada": 0,
                    "metodo_pago_real": "Efectivo"},
    "CUP total exacto": {"moneda": "CUP", "tasa": 1.0, "metodo": "Efectivo", "efectivo": 1000.0,
                         "transferencia": 0.0, "efectivo_cup": 0.0, "vuelto_cup": 0.0,
                         "vuelto_moneda": 0.0, "total_pagado_moneda": 1000.0,
                         "total_pagado_cup": 1000.0, "nuevo_saldo": 0.0, "pagada": 1,
                         "metodo_pago_real": "Efectivo"},
    "CUP total con vuelto": {"moneda": "CUP", "tasa": 1.0, "metodo": "Efectivo", "efectivo": 1200.0,
                             "transferencia": 0.0, "efectivo_cup": 0.0, "vuelto_cup": 200.0,
                             "vuelto_moneda": 0.0, "total_pagado_moneda": 1200.0,
                             "total_pagado_cup": 1200.0, "nuevo_saldo": 0.0, "pagada": 1,
                             "metodo_pago_real": "Efectivo"},
    "CUP transferencia": {"moneda": "CUP", "tasa": 1.0, "metodo": "Transferencia", "efectivo": 0.0,
                          "transferencia": 1000.0, "efectivo_cup": 0.0, "vuelto_cup": 0.0,
                          "vuelto_moneda": 0.0, "total_pagado_moneda": 1000.0,
                          "total_pagado_cup": 1000.0, "nuevo_saldo": 0.0, "pagada": 1,
                          "metodo_pago_real": "Transferencia"},
    "CUP mixto": {"moneda": "CUP", "tasa": 1.0, "metodo": "Mixto", "efectivo": 400.0,
                  "transferencia": 600.0, "efectivo_cup": 0.0, "vuelto_cup": 0.0,
                  "vuelto_moneda": 0.0, "total_pagado_moneda": 1000.0,
                  "total_pagado_cup": 1000.0, "nuevo_saldo": 0.0, "pagada": 1,
                  "metodo_pago_real": "Mixto"},
    "USD parcial": {"moneda": "USD", "tasa": 400.0, "metodo": "Efectivo", "efectivo": 2.0,
                    "transferencia": 0.0, "efectivo_cup": 0.0, "vuelto_cup": 0.0,
                    "vuelto_moneda": 0.0, "total_pagado_moneda": 2.0,
                    "total_pagado_cup": 800.0, "nuevo_saldo": 200.0, "pagada": 0,
                    "metodo_pago_real": "Efectivo"},
    "USD con CUP adicional": {"moneda": "USD", "tasa": 400.0, "metodo": "Efectivo", "efectivo": 2.0,
                              "transferencia": 0.0, "efectivo_cup": 200.0, "vuelto_cup": 0.0,
                              "vuelto_moneda": 0.0, "total_pagado_moneda": 2.0,
                              "total_pagado_cup": 1000.0, "nuevo_saldo": 0.0, "pagada": 1,
                              "metodo_pago_real": "Mixto (USD+CUP)"},
    "USD total con vuelto": {"moneda": "USD", "tasa": 400.0, "metodo": "Efectivo", "efectivo": 3.0,
                             "transferencia": 0.0, "efectivo_cup": 0.0, "vuelto_cup": 200.0,
                             "vuelto_moneda": 0.0, "total_pagado_moneda": 3.0,
                             "total_pagado_cup": 1200.0, "nuevo_saldo": 0.0, "pagada": 1,
                             "metodo_pago_real": "Efectivo"},
}


def abono_del_escenario(moneda, metodo, tasa, efectivo, efectivo_cup, transferencia, vuelto_moneda):
    return Abono(saldo_pendiente=SALDO, moneda=moneda, tasa=tasa, metodo=metodo,
                 efectivo=efectivo, efectivo_cup=efectivo_cup,
                 transferencia=transferencia, vuelto_en_moneda=vuelto_moneda)


class CoincideConLaReferencia(unittest.TestCase):

    def test_todos_los_escenarios(self):
        for escenario in ESCENARIOS:
            nombre = escenario[0]
            with self.subTest(escenario=nombre):
                cobro = calcular_cobro(abono_del_escenario(*escenario[1:]))
                self.assertIsNone(cobro.error, f"[{nombre}] devolvió {cobro.error}")
                for campo, valor in DEUDA[nombre].items():
                    obtenido = getattr(cobro, campo)
                    if isinstance(valor, float):
                        self.assertAlmostEqual(obtenido, valor, places=6,
                                               msg=f"[{nombre}] {campo}")
                    else:
                        self.assertEqual(obtenido, valor, msg=f"[{nombre}] {campo}")


class Reglas(unittest.TestCase):

    def test_el_abono_parcial_deja_saldo(self):
        c = calcular_cobro(Abono(saldo_pendiente=1000, efectivo=250))
        self.assertEqual(c.pagada, 0)
        self.assertAlmostEqual(c.nuevo_saldo, 750.0)
        self.assertEqual(c.vuelto_cup, 0.0)

    def test_pagar_justo_no_deja_vuelto(self):
        c = calcular_cobro(Abono(saldo_pendiente=1000, efectivo=1000))
        self.assertEqual(c.pagada, 1)
        self.assertEqual(c.vuelto_cup, 0.0)

    def test_en_divisa_el_cup_adicional_suma(self):
        c = calcular_cobro(Abono(saldo_pendiente=1000, moneda="USD", tasa=400,
                                 efectivo=2, efectivo_cup=200))
        self.assertAlmostEqual(c.total_pagado_cup, 1000.0)
        self.assertEqual(c.metodo_pago_real, "Mixto (USD+CUP)")

    def test_en_divisa_solo_se_admite_efectivo(self):
        c = calcular_cobro(Abono(saldo_pendiente=1000, moneda="USD", tasa=400,
                                 metodo="Transferencia", efectivo=3))
        self.assertEqual(c.error, "divisa_solo_efectivo")

    def test_el_mixto_solo_existe_en_cup(self):
        c = calcular_cobro(Abono(saldo_pendiente=1000, moneda="USD", tasa=400,
                                 metodo="Mixto", efectivo=1, transferencia=1))
        self.assertIn(c.error, ("divisa_solo_efectivo", "mixto_solo_cup"))

    def test_el_mixto_necesita_las_dos_partes(self):
        c = calcular_cobro(Abono(saldo_pendiente=1000, metodo="Mixto",
                                 efectivo=1000, transferencia=0))
        self.assertEqual(c.error, "mixto_necesita_ambos")

    def test_tasa_cero_es_error(self):
        c = calcular_cobro(Abono(saldo_pendiente=1000, moneda="USD", tasa=0, efectivo=3))
        self.assertEqual(c.error, "tasa_invalida")

    def test_montos_negativos(self):
        c = calcular_cobro(Abono(saldo_pendiente=1000, efectivo=-5))
        self.assertEqual(c.error, "montos_negativos")

    def test_el_vuelto_en_divisa_no_puede_exceder(self):
        c = calcular_cobro(Abono(saldo_pendiente=1000, moneda="USD", tasa=400,
                                 efectivo=3, vuelto_en_moneda=2))
        self.assertEqual(c.error, "vuelto_moneda_excede")

    def test_vuelto_repartido_entre_divisa_y_cup(self):
        # 4 USD a 400 = 1600 sobre 1000 -> vuelto 600; 1 USD son 400, quedan 200
        c = calcular_cobro(Abono(saldo_pendiente=1000, moneda="USD", tasa=400,
                                 efectivo=4, vuelto_en_moneda=1))
        self.assertAlmostEqual(c.vuelto_cup, 600.0)
        self.assertAlmostEqual(vuelto_en_cup_a_entregar(c), 200.0)

    def test_lo_que_sale_de_la_caja_sin_divisa_es_todo_el_vuelto(self):
        c = calcular_cobro(Abono(saldo_pendiente=1000, efectivo=1200))
        self.assertAlmostEqual(vuelto_en_cup_a_entregar(c), 200.0)

    def test_total_pagado_en_transferencia(self):
        abono = Abono(saldo_pendiente=1000, metodo="Transferencia", transferencia=900)
        self.assertEqual(total_pagado(abono), (900.0, 900.0))


class Textos(unittest.TestCase):

    def test_observaciones_de_un_pago_parcial(self):
        c = calcular_cobro(Abono(saldo_pendiente=1000, efectivo=300))
        self.assertEqual(
            observaciones_del_cobro("nota previa", c),
            "nota previa | Pago parcial de 300.00 CUP, saldo restante 700.00 CUP")

    def test_observaciones_de_un_pago_total(self):
        c = calcular_cobro(Abono(saldo_pendiente=1000, efectivo=1000))
        self.assertEqual(
            observaciones_del_cobro("", c),
            " | Pagada totalmente (abonado 1000.00 CUP)")

    def test_resumen_parcial(self):
        c = calcular_cobro(Abono(saldo_pendiente=1000, efectivo=300))
        self.assertEqual(resumen_del_cobro(c),
                         "Pago parcial registrado. Saldo restante: 700.00 CUP")

    def test_resumen_total_con_vuelto_en_divisa(self):
        c = calcular_cobro(Abono(saldo_pendiente=1000, moneda="USD", tasa=400,
                                 efectivo=4, vuelto_en_moneda=1))
        self.assertEqual(resumen_del_cobro(c),
                         "Deuda pagada completamente. Vuelto: 600.00 CUP (en USD: 1.00)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
