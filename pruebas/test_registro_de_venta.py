"""Lo que se guarda con cada venta no puede cambiar.

FINALIZAR recoge lo que `finalizar_venta` enviaba a la base de datos antes de
usar `lddl/calculo_cobro.py`. Se obtuvo ejecutando la aplicación con un espía
en lugar de `registrar_venta_en_db`, de modo que ninguna venta llegó a
guardarse.

    python -m unittest discover -s pruebas -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import base  # noqa: E402

from lddl.calculo_cobro import Pago, a_numero, desglosar_para_registro  # noqa: E402

TOTAL = 1000.0

# (nombre, solo_transferencia, es_deuda, moneda, tasa, pagado, transf_cup, cup_ef, cup_tr, vuelto_moneda)
ESCENARIOS = [
    ("CUP justo",             0, 0, "CUP", "1.00",   "1000", "",     "",    "", ""),
    ("CUP de mas",            0, 0, "CUP", "1.00",   "1200", "",     "",    "", ""),
    ("CUP mixto",             0, 0, "CUP", "1.00",   "200",  "900",  "",    "", ""),
    ("CUP mixto vuelto alto", 0, 0, "CUP", "1.00",   "50",   "1200", "",    "", ""),
    ("Pastilla transferencia",1, 0, "CUP", "1.00",   "",     "",     "",    "", ""),
    ("Deuda",                 0, 1, "CUP", "1.00",   "",     "",     "",    "", ""),
    ("USD justo",             0, 0, "USD", "200.00", "5",    "",     "",    "", ""),
    ("USD de mas",            0, 0, "USD", "400.00", "5",    "",     "",    "", ""),
    ("USD con CUP",           0, 0, "USD", "100.00", "5",    "",     "600", "", ""),
    ("USD vuelto en divisa",  0, 0, "USD", "400.00", "5",    "",     "",    "", "1"),
]

# Valores que la aplicación guardaba antes de la extracción.
FINALIZAR = {
    "CUP justo": {"metodo_pago": "Efectivo", "moneda_pago": "CUP", "tasa_cambio": 1.0,
                  "metodo_pago_real": "Efectivo", "monto_efectivo_cup": 1000.0,
                  "monto_transferencia_cup": 0.0, "salida_efectivo_extra": 0.0,
                  "pago_divisa": 0.0, "vuelto_moneda": 0.0,
                  "pago_texto": "Efectivo: 1000.00 CUP", "vuelto_texto": "0.00 CUP",
                  "saldo_pendiente": 0.0, "pagada": 1},
    "CUP de mas": {"metodo_pago": "Efectivo", "moneda_pago": "CUP", "tasa_cambio": 1.0,
                   "metodo_pago_real": "Efectivo", "monto_efectivo_cup": 1000.0,
                   "monto_transferencia_cup": 0.0, "salida_efectivo_extra": 0.0,
                   "pago_divisa": 0.0, "vuelto_moneda": 0.0,
                   "pago_texto": "Efectivo: 1200.00 CUP", "vuelto_texto": "200.00 CUP",
                   "saldo_pendiente": 0.0, "pagada": 1},
    "CUP mixto": {"metodo_pago": "Efectivo", "moneda_pago": "CUP", "tasa_cambio": 1.0,
                  "metodo_pago_real": "Mixto", "monto_efectivo_cup": 100.0,
                  "monto_transferencia_cup": 900.0, "salida_efectivo_extra": 0.0,
                  "pago_divisa": 0.0, "vuelto_moneda": 0.0,
                  "pago_texto": "Efectivo: 200.00 CUP + Transferencia: 900.00 CUP",
                  "vuelto_texto": "100.00 CUP", "saldo_pendiente": 0.0, "pagada": 1},
    "CUP mixto vuelto alto": {"metodo_pago": "Efectivo", "moneda_pago": "CUP", "tasa_cambio": 1.0,
                              "metodo_pago_real": "Mixto", "monto_efectivo_cup": 0.0,
                              "monto_transferencia_cup": 1000.0, "salida_efectivo_extra": 0.0,
                              "pago_divisa": 0.0, "vuelto_moneda": 0.0,
                              "pago_texto": "Efectivo: 50.00 CUP + Transferencia: 1200.00 CUP",
                              "vuelto_texto": "250.00 CUP", "saldo_pendiente": 0.0, "pagada": 1},
    "Pastilla transferencia": {"metodo_pago": "Transferencia", "moneda_pago": "CUP", "tasa_cambio": 1.0,
                               "metodo_pago_real": "Transferencia", "monto_efectivo_cup": 0.0,
                               "monto_transferencia_cup": 1000.0, "salida_efectivo_extra": 0.0,
                               "pago_divisa": 0.0, "vuelto_moneda": 0.0,
                               "pago_texto": "Transferencia: 1000.00 CUP", "vuelto_texto": "0.00 CUP",
                               "saldo_pendiente": 0.0, "pagada": 1},
    "Deuda": {"metodo_pago": "Efectivo", "moneda_pago": "CUP", "tasa_cambio": 1.0,
              "metodo_pago_real": "", "monto_efectivo_cup": 0.0,
              "monto_transferencia_cup": 0.0, "salida_efectivo_extra": 0.0,
              "pago_divisa": 0.0, "vuelto_moneda": 0.0,
              "pago_texto": "Deuda registrada", "vuelto_texto": "0.00 CUP",
              "saldo_pendiente": 1000.0, "pagada": 0},
    "USD justo": {"metodo_pago": "Efectivo", "moneda_pago": "USD", "tasa_cambio": 200.0,
                  "metodo_pago_real": "Efectivo", "monto_efectivo_cup": 0.0,
                  "monto_transferencia_cup": 0.0, "salida_efectivo_extra": 0.0,
                  "pago_divisa": 5.0, "vuelto_moneda": 0.0,
                  "pago_texto": "5.00 USD", "vuelto_texto": "0.00 CUP",
                  "saldo_pendiente": 0.0, "pagada": 1},
    "USD de mas": {"metodo_pago": "Efectivo", "moneda_pago": "USD", "tasa_cambio": 400.0,
                   "metodo_pago_real": "Efectivo", "monto_efectivo_cup": 0.0,
                   "monto_transferencia_cup": 0.0, "salida_efectivo_extra": 1000.0,
                   "pago_divisa": 5.0, "vuelto_moneda": 0.0,
                   "pago_texto": "5.00 USD", "vuelto_texto": "1000.00 CUP",
                   "saldo_pendiente": 0.0, "pagada": 1},
    "USD con CUP": {"metodo_pago": "Efectivo", "moneda_pago": "USD", "tasa_cambio": 100.0,
                    "metodo_pago_real": "Mixto", "monto_efectivo_cup": 500.0,
                    "monto_transferencia_cup": 0.0, "salida_efectivo_extra": 0.0,
                    "pago_divisa": 5.0, "vuelto_moneda": 0.0,
                    "pago_texto": "5.00 USD + 600.00 CUP (efectivo)", "vuelto_texto": "100.00 CUP",
                    "saldo_pendiente": 0.0, "pagada": 1},
    "USD vuelto en divisa": {"metodo_pago": "Efectivo", "moneda_pago": "USD", "tasa_cambio": 400.0,
                             "metodo_pago_real": "Efectivo", "monto_efectivo_cup": 0.0,
                             "monto_transferencia_cup": 0.0, "salida_efectivo_extra": 600.0,
                             "pago_divisa": 5.0, "vuelto_moneda": 1.0,
                             "pago_texto": "5.00 USD", "vuelto_texto": "1.00 USD + 600.00 CUP",
                             "saldo_pendiente": 0.0, "pagada": 1},
}


def pago_del_escenario(solo_transferencia, es_deuda, moneda, tasa, pagado,
                       transf_cup, cup_ef, cup_tr, vuelto_moneda):
    return Pago(
        total_cup=TOTAL,
        moneda=moneda,
        tasa=a_numero(tasa, 1.0),
        efectivo=a_numero(pagado),
        transferencia=a_numero(transf_cup),
        cup_efectivo=a_numero(cup_ef),
        cup_transferencia=a_numero(cup_tr),
        vuelto_en_moneda=a_numero(vuelto_moneda),
        solo_transferencia=bool(solo_transferencia),
    )


class ElDesgloseCoincideConLaReferencia(unittest.TestCase):

    def test_todos_los_escenarios(self):
        for escenario in ESCENARIOS:
            nombre, _, es_deuda = escenario[0], escenario[1], escenario[2]
            with self.subTest(escenario=nombre):
                pago = pago_del_escenario(*escenario[1:])
                d = desglosar_para_registro(pago, es_deuda=bool(es_deuda))
                self.assertIsNone(d.error, f"[{nombre}] devolvió error {d.error}")

                esperado = FINALIZAR[nombre]
                for campo, valor in esperado.items():
                    obtenido = getattr(d, campo)
                    if isinstance(valor, float):
                        self.assertAlmostEqual(
                            obtenido, valor, places=6,
                            msg=f"[{nombre}] {campo}: {obtenido} en vez de {valor}")
                    else:
                        self.assertEqual(
                            obtenido, valor,
                            msg=f"[{nombre}] {campo}: {obtenido!r} en vez de {valor!r}")

    def test_lo_cobrado_nunca_supera_la_venta(self):
        """Efectivo + transferencia guardados no pueden pasar del total."""
        for escenario in ESCENARIOS:
            nombre, es_deuda = escenario[0], escenario[2]
            if es_deuda:
                continue
            with self.subTest(escenario=nombre):
                d = desglosar_para_registro(pago_del_escenario(*escenario[1:]))
                self.assertLessEqual(
                    round(d.monto_efectivo_cup + d.monto_transferencia_cup, 6), TOTAL,
                    msg=f"[{nombre}] se guardaría más de lo que costó la venta")


try:
    import ttkbootstrap as tb
    from lddl.ui import VentanaVentas
    from lddl.ui import cobro as modulo_cobro
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
class LaAppEnviaLaReferencia(unittest.TestCase):
    """Cierra ventas en la ventana real con un espía en lugar de la base.

    Ninguna venta llega a guardarse: `registrar_venta_en_db` se sustituye por
    una función que sólo anota lo que habría recibido.
    """

    @classmethod
    def setUpClass(cls):
        cls.capturado = {}

        def espia(carrito, datos):
            cls.capturado.clear()
            cls.capturado.update(datos)
            return True, 1

        cls.registrar_original = modulo_cobro.registrar_venta_en_db
        modulo_cobro.registrar_venta_en_db = espia

        cls.root = tb.Window(themename="flatly")
        cls.root.withdraw()
        cls.v = VentanaVentas(cls.root)
        cls.v.mostrar_mensaje = lambda tipo, titulo, mensaje="", **kw: True

    @classmethod
    def tearDownClass(cls):
        modulo_cobro.registrar_venta_en_db = cls.registrar_original
        cls.root.destroy()

    def test_todos_los_escenarios(self):
        v = self.v
        for (nombre, solo_transf, es_deuda, moneda, tasa, pagado,
             transf_cup, cup_ef, cup_tr, vuelto_moneda) in ESCENARIOS:
            with self.subTest(escenario=nombre):
                v.carrito = [{"id": 3, "nombre": "Aceite 1000 ml", "precio": 200.0,
                              "cantidad": 5.0, "tipo": "unidad", "unidad": "unidad"}]
                v.total_var.set(f"{TOTAL:.2f}")
                v.transferencia_var.set(solo_transf)
                v.deuda_var.set(es_deuda)
                v.mensajeria_var.set(0)
                v.observaciones_deuda_var.set("prueba" if es_deuda else "")
                v.moneda_pago.set(moneda)
                v.tasa_cambio.set(tasa)
                v.pagado_var.set(pagado)
                v.pago_transferencia_var.set(transf_cup)
                v.pago_cup_adicional_var.set(cup_ef)
                v.pago_transferencia_adicional_var.set(cup_tr)
                v.vuelto_moneda_var.set(vuelto_moneda)
                v._pago_cup_adicional_auto_valor = None
                v.vuelto_total_cup = 0.0

                self.capturado.clear()
                v.finalizar_venta()

                self.assertTrue(self.capturado,
                                f"[{nombre}] la venta no llegó a registrarse")

                for campo, valor in FINALIZAR[nombre].items():
                    obtenido = self.capturado[campo]
                    if isinstance(valor, float):
                        self.assertAlmostEqual(
                            obtenido, valor, places=6,
                            msg=f"[{nombre}] {campo}: {obtenido} en vez de {valor}")
                    else:
                        self.assertEqual(
                            obtenido, valor,
                            msg=f"[{nombre}] {campo}: {obtenido!r} en vez de {valor!r}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
