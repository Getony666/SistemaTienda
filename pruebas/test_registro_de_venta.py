"""Lo que se guarda con cada venta no puede cambiar.

La tabla de casos (ESCENARIOS, FINALIZAR) vive en `pruebas/casos.py`: es lo
que `finalizar_venta` enviaba a la base de datos antes de usar
`lddl/calculo_cobro.py`. Se obtuvo ejecutando la aplicación con un espía en
lugar de `registrar_venta_en_db`, de modo que ninguna venta llegó a
guardarse.

La ventana que lo produjo (`ventas.py`, `lddl/ui/`) ya no está en el
proyecto. Antes de retirarla se le hizo repasar estos mismos escenarios una
última vez, con el mismo espía, y quedó grabado en
`pruebas/acta_de_la_app_vieja.json`. `ElDesgloseCoincideConLaReferencia`
compara el módulo contra la tabla; `ElActaDeLaVentanaViejaLoConfirma` compara
la tabla contra el acta.

    python -m unittest discover -s pruebas -v
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from casos import ESCENARIOS, FINALIZAR, TOTAL, pago_del_escenario  # noqa: E402
from lddl.calculo_cobro import desglosar_para_registro  # noqa: E402

_AQUI = os.path.dirname(os.path.abspath(__file__))
_RUTA_ACTA = os.path.join(_AQUI, "acta_de_la_app_vieja.json")
with open(_RUTA_ACTA, encoding="utf-8") as _f:
    _ACTA = json.load(_f)["registro_de_venta"]["finalizar"]


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


class ElActaDeLaVentanaViejaLoConfirma(unittest.TestCase):
    """FINALIZAR coincide con lo que la ventana real envió a registrar.

    No abre nada: compara contra `acta_de_la_app_vieja.json`, grabado
    ejecutando la ventana de verdad -con el mismo espía en lugar de
    `registrar_venta_en_db`- justo antes de retirarla del proyecto. Si esta
    prueba falla, es la tabla de `casos.py` la que se apartó de lo que la app
    mandaba guardar, no al revés.
    """

    def test_finalizar_coincide_con_el_acta(self):
        for nombre, esperado in FINALIZAR.items():
            with self.subTest(escenario=nombre):
                obtenido = _ACTA[nombre]
                for campo, valor in esperado.items():
                    if isinstance(valor, float):
                        self.assertAlmostEqual(
                            obtenido[campo], valor, places=6,
                            msg=f"[{nombre}] {campo}: acta={obtenido[campo]!r} tabla={valor!r}")
                    else:
                        self.assertEqual(
                            obtenido[campo], valor,
                            msg=f"[{nombre}] {campo}: acta={obtenido[campo]!r} tabla={valor!r}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
