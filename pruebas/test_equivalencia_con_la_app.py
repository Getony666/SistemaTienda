"""El vuelto no puede cambiar: ni el de la app ni el del módulo.

REFERENCIA guarda lo que la aplicación calculaba antes de sacar la aritmética
a `lddl/calculo_cobro.py`. Los números se tomaron ejecutando la app tal como
estaba, no a mano.

Las dos pruebas comparan contra esa referencia, no entre sí. Así siguen
sirviendo aunque la interfaz pase a usar el módulo -o aunque algún día se
cambie tkinter por otra cosa-.

    python -m unittest discover -s pruebas -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import base  # noqa: E402
from lddl.calculo_cobro import Pago, a_numero, calcular_vuelto, cup_faltante  # noqa: E402

try:
    import ttkbootstrap as tb
    from lddl.ui import VentanaVentas
    HAY_PANTALLA = True
except Exception:  # sin entorno gráfico solo se puede probar el módulo
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


# (descripcion, total, moneda, tasa, pagado, transferencia, cup_ef, cup_tr, vuelto_moneda)
CASOS = [
    ("CUP justo",                 2250, "CUP", "1.00", "2250", "",     "",     "",     ""),
    ("CUP de mas",                2250, "CUP", "1.00", "2300", "",     "",     "",     ""),
    ("CUP no alcanza",            2250, "CUP", "1.00", "2000", "",     "",     "",     ""),
    ("CUP nada",                  2250, "CUP", "1.00", "",     "",     "",     "",     ""),
    ("CUP mixto justo",           1000, "CUP", "1.00", "400",  "600",  "",     "",     ""),
    ("CUP mixto de mas",          1000, "CUP", "1.00", "400",  "700",  "",     "",     ""),
    ("CUP mixto no alcanza",      1000, "CUP", "1.00", "200",  "300",  "",     "",     ""),
    ("CUP solo transferencia",    1000, "CUP", "1.00", "",     "1000", "",     "",     ""),
    ("CUP centavos",             99.99, "CUP", "1.00", "100",  "",     "",     "",     ""),

    ("USD justo",                 4000, "USD", "400.00", "10", "",     "",     "",     ""),
    ("USD de mas",                5000, "USD", "400.00", "15", "",     "",     "",     ""),
    ("USD no alcanza sin CUP",    5000, "USD", "400.00", "10", "",     "",     "",     ""),
    ("USD con CUP efectivo",      5000, "USD", "400.00", "10", "",     "1000", "",     ""),
    ("USD con CUP de mas",        5000, "USD", "400.00", "10", "",     "1500", "",     ""),
    ("USD con CUP transferencia", 5000, "USD", "400.00", "10", "",     "",     "1000", ""),
    ("USD con los dos CUP",       5000, "USD", "400.00", "8",  "",     "1000", "1000", ""),
    ("USD vuelto repartido",      5000, "USD", "400.00", "15", "",     "",     "",     "2"),
    ("USD vuelto todo en divisa", 5000, "USD", "400.00", "15", "",     "",     "",     "2.5"),
    ("USD sin divisa solo CUP",    500, "USD", "400.00", "",   "",     "500",  "",     ""),
    ("EUR de mas",                3000, "EUR", "450.00", "8",  "",     "",     "",     ""),
]

# Vuelto en CUP que la aplicación daba antes de la extracción.
REFERENCIA = {
    "CUP justo": 0.0,
    "CUP de mas": 50.0,
    "CUP no alcanza": 0.0,
    "CUP nada": 0.0,
    "CUP mixto justo": 0.0,
    "CUP mixto de mas": 100.0,
    "CUP mixto no alcanza": 0.0,
    "CUP solo transferencia": 0.0,
    "CUP centavos": 0.01,
    "USD justo": 0.0,
    "USD de mas": 1000.0,
    "USD no alcanza sin CUP": 0.0,
    "USD con CUP efectivo": 0.0,
    "USD con CUP de mas": 500.0,
    "USD con CUP transferencia": 0.0,
    "USD con los dos CUP": 200.0,
    "USD vuelto repartido": 1000.0,
    "USD vuelto todo en divisa": 1000.0,
    "USD sin divisa solo CUP": 0.0,
    "EUR de mas": 600.0,
}


# Lo que la cajera ve en pantalla. Tomado de la app antes de extraer, con una
# corrección deliberada: el monto del vuelto ya no lleva la moneda, porque la
# etiqueta de al lado ya la muestra y se leía "1000.00 CUP CUP".
# (vuelto, resumen del pago, resto en CUP, campo de CUP adicional).
TEXTOS = {
    "CUP justo": ('0.00', 'Efectivo: 2250.00', '', ''),
    "CUP de mas": ('50.00', 'Efectivo: 2300.00', '', ''),
    "CUP no alcanza": ('0.00', 'Faltan 250.00 CUP', '', ''),
    "CUP nada": ('0.00', '', '', ''),
    "CUP mixto justo": ('0.00', 'Efectivo: 400.00 | Transferencia: 600.00', '', ''),
    "CUP mixto de mas": ('100.00', 'Efectivo: 400.00 | Transferencia: 700.00', '', ''),
    "CUP mixto no alcanza": ('0.00', 'Faltan 500.00 CUP', '', ''),
    "CUP solo transferencia": ('0.00', 'Transferencia: 1000.00', '', ''),
    "CUP centavos": ('0.01', 'Efectivo: 100.00', '', ''),
    "USD justo": ('0.00', '10.00 USD (=4000.00 CUP)', '', ''),
    "USD de mas": ('1000.00', '15.00 USD (=6000.00 CUP)', 'Todo el vuelto en CUP', ''),
    "USD no alcanza sin CUP": ('0.00', '10.00 USD (=4000.00 CUP) + 1000.00 CUP (efectivo)', '', '1000.00'),
    "USD con CUP efectivo": ('0.00', '10.00 USD (=4000.00 CUP) + 1000.00 CUP (efectivo)', '', '1000'),
    "USD con CUP de mas": ('500.00', '10.00 USD (=4000.00 CUP) + 1500.00 CUP (efectivo)', 'Todo el vuelto en CUP', '1500'),
    "USD con CUP transferencia": ('0.00', '10.00 USD (=4000.00 CUP) + 1000.00 CUP (transferencia)', '', ''),
    "USD con los dos CUP": ('200.00', '8.00 USD (=3200.00 CUP) + 1000.00 CUP (efectivo) + 1000.00 CUP (transferencia)', 'Todo el vuelto en CUP', '1000'),
    "USD vuelto repartido": ('2.00 USD + 200.00 CUP', '15.00 USD (=6000.00 CUP)', 'Resto en CUP: 200.00', ''),
    "USD vuelto todo en divisa": ('2.50 USD', '15.00 USD (=6000.00 CUP)', 'Todo el vuelto en moneda de pago', ''),
    "USD sin divisa solo CUP": ('0.00', '500.00 CUP (efectivo)', '', '500'),
    "EUR de mas": ('600.00', '8.00 EUR (=3600.00 CUP)', 'Todo el vuelto en CUP', ''),
}


def pago_del_caso(total, moneda, tasa, pagado, transferencia, cup_ef, cup_tr, vuelto_moneda):
    """Traduce un caso de la tabla a un Pago, aplicando el autorrelleno de CUP.

    Cuando se paga en divisa y no alcanza, la interfaz rellena sola el CUP que
    falta y lo da por cobrado. Eso es comodidad de pantalla, no aritmética, así
    que vive fuera del módulo; aquí se reproduce para poder comparar.
    """
    pago = Pago(
        total_cup=float(total),
        moneda=moneda,
        tasa=a_numero(tasa),
        efectivo=a_numero(pagado),
        transferencia=a_numero(transferencia),
        cup_efectivo=a_numero(cup_ef),
        cup_transferencia=a_numero(cup_tr),
        vuelto_en_moneda=a_numero(vuelto_moneda),
    )
    if moneda != "CUP" and pago.efectivo > 0 and not cup_ef and not cup_tr:
        falta = cup_faltante(float(total), pago.efectivo, pago.tasa)
        if falta > 0:
            pago.cup_efectivo = falta
    return pago


class ElModuloDaLaReferencia(unittest.TestCase):
    """No necesita pantalla: es aritmética pura."""

    def test_todos_los_casos(self):
        for caso in CASOS:
            nombre = caso[0]
            with self.subTest(caso=nombre):
                vuelto = calcular_vuelto(pago_del_caso(*caso[1:]))
                obtenido = 0.0 if vuelto.error else vuelto.vuelto_cup
                self.assertAlmostEqual(
                    obtenido, REFERENCIA[nombre], places=6,
                    msg=f"[{nombre}] el módulo da {obtenido}, la referencia dice {REFERENCIA[nombre]}")


@unittest.skipUnless(HAY_PANTALLA, "hace falta entorno gráfico")
class LaAppDaLaReferencia(unittest.TestCase):
    """Recorre la ventana real, oculta, sin mostrarla."""

    @classmethod
    def setUpClass(cls):
        cls.root = tb.Window(themename="flatly")
        cls.root.withdraw()
        cls.v = VentanaVentas(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def _ejecutar(self, caso):
        (nombre, total, moneda, tasa, pagado, transferencia,
         cup_ef, cup_tr, vuelto_moneda) = caso
        v = self.v
        v.transferencia_var.set(0)
        v.deuda_var.set(0)
        v.mensajeria_var.set(0)
        v._pago_cup_adicional_auto_valor = None
        v.vuelto_total_cup = 0.0
        v.total_var.set(f"{total:.2f}")
        v.moneda_pago.set(moneda)
        v.tasa_cambio.set(tasa)
        v.pagado_var.set(pagado)
        v.pago_transferencia_var.set(transferencia)
        v.pago_cup_adicional_var.set(cup_ef)
        v.pago_transferencia_adicional_var.set(cup_tr)
        v.vuelto_moneda_var.set(vuelto_moneda)
        v._calcular_vuelto_interno(silencioso=True)

    def test_los_textos_en_pantalla_no_cambian(self):
        for caso in CASOS:
            nombre = caso[0]
            with self.subTest(caso=nombre):
                self._ejecutar(caso)
                obtenido = (
                    self.v.vuelto_var.get(),
                    self.v.label_pago_efectivo_resto.cget("text"),
                    self.v.label_resto_cup.cget("text"),
                    self.v.pago_cup_adicional_var.get(),
                )
                self.assertEqual(obtenido, TEXTOS[nombre], msg=f"[{nombre}]")

    def test_todos_los_casos(self):
        v = self.v
        for (nombre, total, moneda, tasa, pagado, transferencia,
             cup_ef, cup_tr, vuelto_moneda) in CASOS:
            with self.subTest(caso=nombre):
                v.transferencia_var.set(0)
                v.deuda_var.set(0)
                v.mensajeria_var.set(0)
                v._pago_cup_adicional_auto_valor = None
                v.vuelto_total_cup = 0.0
                v.total_var.set(f"{total:.2f}")
                v.moneda_pago.set(moneda)
                v.tasa_cambio.set(tasa)
                v.pagado_var.set(pagado)
                v.pago_transferencia_var.set(transferencia)
                v.pago_cup_adicional_var.set(cup_ef)
                v.pago_transferencia_adicional_var.set(cup_tr)
                v.vuelto_moneda_var.set(vuelto_moneda)

                v._calcular_vuelto_interno(silencioso=True)

                self.assertAlmostEqual(
                    v.vuelto_total_cup, REFERENCIA[nombre], places=6,
                    msg=f"[{nombre}] la app da {v.vuelto_total_cup}, "
                        f"la referencia dice {REFERENCIA[nombre]}")


# El otro camino de cálculo: teclear en "Pagado (Transferencia)".
# (descripcion, total, pagado, transferencia)
CASOS_MIXTO = [
    ("transferencia parcial",  "1000.00", "",     "400"),
    ("transferencia total",    "1000.00", "",     "1000"),
    ("transferencia de mas",   "1000.00", "",     "1500"),
    ("transferencia negativa", "1000.00", "",     "-5"),
    ("sin transferencia",      "1000.00", "1200", ""),
    ("efectivo insuficiente",  "1000.00", "500",  ""),
]

# (vuelto, resumen, vuelto en CUP, efectivo que la app rellena sola)
MIXTO = {
    "transferencia parcial": ('0.00', 'Efectivo: 600.00 | Transferencia: 400.00', 0.0, '600.00'),
    "transferencia total": ('0.00', 'Transferencia: 1000.00', 0.0, '0.00'),
    "transferencia de mas": ('0.00', '', 0.0, ''),
    "transferencia negativa": ('0.00', '', 0.0, ''),
    "sin transferencia": ('200.00', 'Efectivo: 1200.00', 200.0, '1200'),
    "efectivo insuficiente": ('0.00', 'Efectivo: 500.00', 0.0, '500'),
}


@unittest.skipUnless(HAY_PANTALLA, "hace falta entorno gráfico")
class TecleandoEnTransferencia(unittest.TestCase):
    """El vuelto al escribir en el campo de transferencia.

    Este camino formateaba el resumen con doble espacio alrededor de la barra
    y repetía la moneda en el monto. Ambas cosas se unificaron con el otro
    camino; estos valores reflejan ya la corrección.
    """

    @classmethod
    def setUpClass(cls):
        cls.root = tb.Window(themename="flatly")
        cls.root.withdraw()
        cls.v = VentanaVentas(cls.root)
        cls.v.mostrar_mensaje = lambda *a, **k: True

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def test_todos_los_casos(self):
        v = self.v
        for nombre, total, pagado, transferencia in CASOS_MIXTO:
            with self.subTest(caso=nombre):
                v.transferencia_var.set(0)
                v.moneda_pago.set("CUP")
                v.total_var.set(total)
                v.pagado_var.set(pagado)
                v.pago_transferencia_var.set(transferencia)
                v.vuelto_total_cup = 0.0
                v.vuelto_var.set("")
                v.label_pago_efectivo_resto.config(text="")

                v.calcular_vuelto_con_pago_mixto()

                obtenido = (
                    v.vuelto_var.get(),
                    v.label_pago_efectivo_resto.cget("text"),
                    round(v.vuelto_total_cup, 6),
                    v.pagado_var.get(),
                )
                self.assertEqual(obtenido, MIXTO[nombre], msg=f"[{nombre}]")


if __name__ == "__main__":
    unittest.main(verbosity=2)
