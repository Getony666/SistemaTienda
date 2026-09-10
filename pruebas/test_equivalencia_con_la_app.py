"""El vuelto no puede cambiar: ni el de la app ni el del módulo.

Las tablas de casos (CASOS, REFERENCIA, TEXTOS, CASOS_MIXTO, MIXTO) viven en
`pruebas/casos.py`: son los números que la aplicación calculaba antes de
sacar la aritmética a `lddl/calculo_cobro.py`, tomados ejecutando la app tal
como estaba, no a mano.

La ventana de tkinter que las produjo (`ventas.py`, `lddl/ui/`) ya no está en
el proyecto. Antes de retirarla se la hizo repasar estos mismos casos una
última vez, y lo que contestó quedó grabado en
`pruebas/acta_de_la_app_vieja.json`. `ElModuloDaLaReferencia` compara el
módulo contra la tabla; `ElActaDeLaVentanaViejaLoConfirma` compara la tabla
contra el acta. Entre las dos queda cerrado el círculo sin necesitar pantalla
ni tkinter instalado.

    python -m unittest discover -s pruebas -v
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from casos import CASOS, MIXTO, REFERENCIA, TEXTOS, pago_del_caso  # noqa: E402
from lddl.calculo_cobro import calcular_vuelto  # noqa: E402

_AQUI = os.path.dirname(os.path.abspath(__file__))
_RUTA_ACTA = os.path.join(_AQUI, "acta_de_la_app_vieja.json")
with open(_RUTA_ACTA, encoding="utf-8") as _f:
    _ACTA = json.load(_f)["equivalencia_con_la_app"]


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


class ElActaDeLaVentanaViejaLoConfirma(unittest.TestCase):
    """Las tablas de arriba coinciden con lo que la ventana real contestó.

    No abre nada: compara contra `acta_de_la_app_vieja.json`, el testimonio
    que se grabó ejecutando la ventana de verdad justo antes de retirarla del
    proyecto. Si alguna de estas pruebas falla, es la tabla de `casos.py` la
    que se apartó de lo que la app decía, no al revés.
    """

    def test_la_referencia_coincide_con_el_acta(self):
        for nombre, vuelto in REFERENCIA.items():
            with self.subTest(caso=nombre):
                self.assertAlmostEqual(
                    vuelto, _ACTA["referencia"][nombre], places=6,
                    msg=f"[{nombre}] la tabla dice {vuelto}, el acta dice {_ACTA['referencia'][nombre]}")

    def test_los_textos_coinciden_con_el_acta(self):
        for nombre, textos in TEXTOS.items():
            with self.subTest(caso=nombre):
                self.assertEqual(list(textos), _ACTA["textos"][nombre], msg=f"[{nombre}]")

    def test_el_pago_mixto_coincide_con_el_acta(self):
        for nombre, valores in MIXTO.items():
            with self.subTest(caso=nombre):
                obtenido = list(valores)
                obtenido[2] = round(obtenido[2], 6)
                self.assertEqual(obtenido, _ACTA["mixto"][nombre], msg=f"[{nombre}]")


if __name__ == "__main__":
    unittest.main(verbosity=2)
