"""El firmador de `herramientas/`, contra los mismos vectores del RFC 8032.

Este código NO va en el ejecutable que se entrega: firmar necesita la llave
privada, y dentro del .exe de una tienda no puede haber nada capaz de emitir
una licencia. Vive en `herramientas/` y sólo corre en la máquina de quien
vende el programa.

Reproducir exactamente las firmas del RFC -no sólo "firmar y que verifique"-
es lo que demuestra que firmador y verificador no comparten el mismo error.
Dos implementaciones equivocadas de la misma manera se darían la razón entre
ellas todo el día.

    python -m unittest discover -s pruebas -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lddl.ed25519 import verificar  # noqa: E402
from herramientas.firma import firmar, llave_publica_de  # noqa: E402
from test_ed25519 import VECTORES_RFC_8032, octetos  # noqa: E402


class ContraLosVectoresDelRFC(unittest.TestCase):

    def test_la_llave_publica_sale_de_la_privada(self):
        for i, (privada, publica, _mensaje, _firma) in enumerate(VECTORES_RFC_8032, 1):
            with self.subTest(vector=i):
                self.assertEqual(llave_publica_de(octetos(privada)), octetos(publica))

    def test_las_cuatro_firmas_oficiales_se_reproducen_octeto_a_octeto(self):
        for i, (privada, _publica, mensaje, firma) in enumerate(VECTORES_RFC_8032, 1):
            with self.subTest(vector=i):
                self.assertEqual(firmar(octetos(privada), octetos(mensaje)),
                                 octetos(firma))


class ElViajeDeIdaYVuelta(unittest.TestCase):
    """Lo que se firma aquí lo tiene que aceptar el verificador del programa."""

    def setUp(self):
        self.privada = bytes(range(32))
        self.publica = llave_publica_de(self.privada)

    def test_una_licencia_firmada_aqui_vale_alla(self):
        mensaje = "negocio: Bodega La Esquina\nhasta: 2027-09-15".encode("utf-8")
        self.assertTrue(verificar(self.publica, mensaje, firmar(self.privada, mensaje)))

    def test_un_mensaje_con_tildes_y_enes_sobrevive_al_viaje(self):
        """Los nombres de negocio cubanos llevan tildes y eñes, y el doble
        acento de PowerShell ya ha mordido antes en este proyecto."""
        mensaje = "negocio: Panadería La Ñapa de José".encode("utf-8")
        self.assertTrue(verificar(self.publica, mensaje, firmar(self.privada, mensaje)))

    def test_cambiar_una_letra_del_mensaje_invalida_la_firma(self):
        mensaje = "hasta: 2027-09-15".encode("utf-8")
        firma = firmar(self.privada, mensaje)
        self.assertFalse(verificar(self.publica, "hasta: 2037-09-15".encode("utf-8"), firma))

    def test_otra_llave_privada_no_produce_una_firma_que_valga(self):
        """Si esto fallara, cualquiera podría emitir licencias con su propia
        llave y el programa las aceptaría."""
        mensaje = b"lo que sea"
        firma_de_otro = firmar(bytes(range(1, 33)), mensaje)
        self.assertFalse(verificar(self.publica, mensaje, firma_de_otro))

    def test_la_llave_privada_tiene_que_medir_32_octetos(self):
        with self.assertRaises(ValueError):
            firmar(b"corta", b"mensaje")


if __name__ == "__main__":
    unittest.main()
