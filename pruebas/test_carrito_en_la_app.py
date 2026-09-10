"""El carrito de la ventana real se comportaba igual que el módulo.

No hay aquí una tabla de casos que mover a `pruebas/casos.py`: estas pruebas
no comparaban números fijos, sino que la ventana, al pulsar "Agregar al
Carrito" con un producto real de `tienda_de_pruebas.db`, hiciera exactamente
lo mismo que hoy hace `lddl/carrito.py`. Esa comprobación se hizo mientras
`lddl/ui/` seguía en el proyecto; el producto que se usó y lo que la ventana
contestó para él quedaron grabados en `pruebas/acta_de_la_app_vieja.json`
justo antes de retirarla (`pruebas/test_carrito_en_la_app.py` en el acta).

`ElActaDeLaVentanaViejaLoConfirma` ya no abre ninguna ventana: reconstruye,
con las funciones puras de `lddl/carrito.py`, lo que la pantalla hacía con
ese mismo producto, y compara contra lo que quedó grabado. Donde el
comportamiento no vivía en el módulo -que al marcar la pastilla de
"Transferencia" lo pagado se ajuste solo al total, o que un carrito vacío
deje el total en cero- lo que se comprueba es que el acta lo recogió tal
como se esperaba; esa parte de la interfaz se fue con la ventana.

    python -m unittest discover -s pruebas -v
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lddl import carrito as c  # noqa: E402

_AQUI = os.path.dirname(os.path.abspath(__file__))
_RUTA_ACTA = os.path.join(_AQUI, "acta_de_la_app_vieja.json")
with open(_RUTA_ACTA, encoding="utf-8") as _f:
    _ACTA = json.load(_f)["carrito_en_la_app"]

_PRODUCTO = _ACTA["producto_usado"]


def _agregar(carrito):
    nuevo, motivo = c.agregar_unidad(
        carrito, _PRODUCTO["id"], _PRODUCTO["nombre"], _PRODUCTO["precio"],
        _PRODUCTO["stock"], _PRODUCTO["tipo"], _PRODUCTO["unidad"])
    assert motivo is None, f"agregar_unidad devolvió {motivo!r}"
    return nuevo


class ElActaDeLaVentanaViejaLoConfirma(unittest.TestCase):
    """Compara `lddl/carrito.py` contra lo que la ventana real hacía.

    El producto usado (`_PRODUCTO`) es el mismo que la ventana encontró en
    `tienda_de_pruebas.db` al levantar el acta: el primero con stock de la
    tabla de resultados, tal como lo hacía `agregar_desde_resultados`.
    """

    def test_agregar_desde_la_tabla_mete_una_unidad(self):
        carrito = _agregar([])
        esperado = _ACTA["agregar_una_unidad"]["carrito"]
        self.assertEqual(carrito, esperado)
        self.assertEqual(len(carrito), 1)
        self.assertEqual(carrito[0]["id"], _PRODUCTO["id"])
        self.assertEqual(carrito[0]["nombre"], _PRODUCTO["nombre"])
        self.assertEqual(carrito[0]["cantidad"], 1)

    def test_agregar_dos_veces_acumula_en_la_misma_linea(self):
        carrito = _agregar(_agregar([]))
        esperado = _ACTA["agregar_dos_veces"]["carrito"]
        self.assertEqual(carrito, esperado)
        self.assertEqual(len(carrito), 1)
        self.assertEqual(carrito[0]["cantidad"], 2)

    def test_el_total_de_la_pantalla_coincide_con_el_del_modulo(self):
        carrito = _agregar(_agregar([]))
        total = c.total(carrito)
        datos = _ACTA["total_de_pantalla"]
        self.assertAlmostEqual(total, datos["total_modulo"], places=6)
        self.assertAlmostEqual(total, float(datos["total_var"]), places=6)

    def test_la_tabla_muestra_lo_mismo_que_filas_para_tabla(self):
        carrito = _agregar([])
        datos = _ACTA["tabla_muestra_lo_mismo"]
        self.assertEqual(carrito, datos["carrito"])

        filas = c.filas_para_tabla(carrito)
        self.assertEqual(filas, datos["filas_modulo"])

        mostrado = datos["tabla_mostrada"][0]
        esperado = filas[0]
        self.assertEqual(str(mostrado[0]), esperado["nombre"])
        self.assertEqual(str(mostrado[1]), esperado["cantidad"])
        self.assertEqual(str(mostrado[2]), esperado["precio"])
        self.assertEqual(str(mostrado[3]), esperado["subtotal"])

    def test_con_la_pastilla_de_transferencia_lo_pagado_sigue_al_total(self):
        """Esto vivía en `actualizar_carrito`, no en el módulo: se comprueba
        que quedó grabado como se esperaba, no se recalcula."""
        datos = _ACTA["pastilla_transferencia"]
        self.assertEqual(datos["pagado_var"], datos["total_var"])
        self.assertEqual(datos["vuelto_var"], "0.00")

    def test_el_carrito_vacio_deja_el_total_en_cero(self):
        datos = _ACTA["carrito_vacio"]
        self.assertEqual(datos["total_var"], "0.00")
        self.assertEqual(datos["hijos_tabla"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
