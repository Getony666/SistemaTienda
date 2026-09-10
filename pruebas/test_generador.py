"""Las herramientas de quien vende: crear el par de llaves y emitir licencias.

Nada de esto se compila en el ejecutable. Se prueba igual porque un error
aquí se descubre con el cliente delante: una licencia emitida con la fecha
mal o con el código de máquina mal copiado no se nota hasta que el otro
intenta abrir el programa.

Todo sobre carpetas temporales y llaves de mentira.

    python -m unittest discover -s pruebas -v
"""

import datetime
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from herramientas import generar_licencia, generar_llaves  # noqa: E402
from herramientas.firma import llave_publica_de  # noqa: E402
from lddl import licencia  # noqa: E402

MAQUINA = "A7K2-3M4P-XR7T"
PRIVADA = bytes(range(32))
PUBLICA = llave_publica_de(PRIVADA)


class CrearElParDeLlaves(unittest.TestCase):

    def setUp(self):
        self.temporal = tempfile.mkdtemp(prefix="mitienda-llaves-")

    def tearDown(self):
        shutil.rmtree(self.temporal, ignore_errors=True)

    def ruta(self, nombre):
        return os.path.join(self.temporal, nombre)

    def test_la_publica_que_escribe_le_corresponde_a_la_privada(self):
        privada, publica = generar_llaves.crear_par(self.ruta("privada.key"),
                                                    self.ruta("publica.key"))
        self.assertEqual(len(privada), 32)
        self.assertEqual(llave_publica_de(privada), publica)

    def test_dos_pares_seguidos_no_salen_iguales(self):
        uno, _ = generar_llaves.crear_par(self.ruta("a.key"), self.ruta("a.pub"))
        otro, _ = generar_llaves.crear_par(self.ruta("b.key"), self.ruta("b.pub"))
        self.assertNotEqual(uno, otro)

    def test_no_pisa_una_llave_que_ya_existe(self):
        """Sobrescribir la privada por accidente deja sin renovacion posible
        a todos los clientes que ya tienen el programa. Que cueste."""
        generar_llaves.crear_par(self.ruta("privada.key"), self.ruta("publica.key"))
        with self.assertRaises(FileExistsError):
            generar_llaves.crear_par(self.ruta("privada.key"), self.ruta("publica.key"))

    def test_la_privada_se_puede_volver_a_leer_del_fichero(self):
        privada, _ = generar_llaves.crear_par(self.ruta("privada.key"),
                                              self.ruta("publica.key"))
        self.assertEqual(generar_llaves.leer_llave(self.ruta("privada.key")), privada)


class EmitirUnaLicencia(unittest.TestCase):

    def test_lo_que_emite_lo_acepta_el_programa(self):
        texto = generar_licencia.emitir(PRIVADA, "Bodega La Esquina", MAQUINA,
                                        meses=12, desde=datetime.date(2026, 9, 15))
        v = licencia.verificar(texto, PUBLICA, MAQUINA, datetime.date(2026, 10, 1))
        self.assertEqual(v.estado, licencia.ACTIVA)
        self.assertEqual(v.negocio, "Bodega La Esquina")

    def test_doce_meses_son_un_ano_justo(self):
        texto = generar_licencia.emitir(PRIVADA, "X", MAQUINA, meses=12,
                                        desde=datetime.date(2026, 9, 15))
        v = licencia.verificar(texto, PUBLICA, MAQUINA, datetime.date(2026, 9, 15))
        self.assertEqual(v.hasta, datetime.date(2027, 9, 15))

    def test_un_mes_desde_el_31_cae_en_el_ultimo_dia_del_mes_corto(self):
        """Sumar meses no es sumar dias: el 31 de enero mas un mes no existe
        en febrero, y hay que decidir donde cae en vez de reventar."""
        texto = generar_licencia.emitir(PRIVADA, "X", MAQUINA, meses=1,
                                        desde=datetime.date(2027, 1, 31))
        v = licencia.verificar(texto, PUBLICA, MAQUINA, datetime.date(2027, 1, 31))
        self.assertEqual(v.hasta, datetime.date(2027, 2, 28))

    def test_se_puede_emitir_por_dias_en_vez_de_por_meses(self):
        texto = generar_licencia.emitir(PRIVADA, "X", MAQUINA, dias=3,
                                        desde=datetime.date(2026, 9, 15))
        v = licencia.verificar(texto, PUBLICA, MAQUINA, datetime.date(2026, 9, 15))
        self.assertEqual(v.hasta, datetime.date(2026, 9, 18))

    def test_la_de_tecnico_sale_marcada_como_tal(self):
        texto = generar_licencia.emitir(PRIVADA, "X", MAQUINA, dias=3,
                                        edicion="tecnico",
                                        desde=datetime.date(2026, 9, 15))
        v = licencia.verificar(texto, PUBLICA, MAQUINA, datetime.date(2026, 9, 16))
        self.assertEqual(v.edicion, "tecnico")

    def test_el_codigo_de_maquina_se_guarda_con_guiones_aunque_llegue_pegado(self):
        """Se copia de WhatsApp de las dos formas; en el fichero queda una."""
        texto = generar_licencia.emitir(PRIVADA, "X", "a7k23m4pxr7t", meses=12,
                                        desde=datetime.date(2026, 9, 15))
        self.assertIn("maquina: A7K2-3M4P-XR7T", texto)


class LoQueElGeneradorSeNiegaAHacer(unittest.TestCase):
    """Vale mas negarse aqui que emitir una licencia que no va a abrir nada
    y descubrirlo cuando el cliente la pegue al otro lado de la isla."""

    def test_un_codigo_de_maquina_con_una_errata(self):
        for malo in ("A7K2-9M4P", "A7K2-3M4P-XR7T0", "A7K2-9M4P-XR3O", ""):
            with self.subTest(codigo=malo):
                with self.assertRaises(ValueError):
                    generar_licencia.emitir(PRIVADA, "X", malo, meses=12)

    def test_un_negocio_sin_nombre(self):
        for malo in ("", "   "):
            with self.subTest(negocio=repr(malo)):
                with self.assertRaises(ValueError):
                    generar_licencia.emitir(PRIVADA, malo, MAQUINA, meses=12)

    def test_una_licencia_que_no_dura_nada(self):
        with self.assertRaises(ValueError):
            generar_licencia.emitir(PRIVADA, "X", MAQUINA, dias=0)

    def test_una_edicion_que_no_existe(self):
        with self.assertRaises(ValueError):
            generar_licencia.emitir(PRIVADA, "X", MAQUINA, meses=12, edicion="eterna")

    def test_un_salto_de_linea_metido_en_el_nombre_del_negocio(self):
        """Un nombre con un salto dentro partiria el fichero en dos y podria
        colar un campo falso. Se corta aqui."""
        with self.assertRaises(ValueError):
            generar_licencia.emitir(PRIVADA, "Bodega\nhasta: 2099-01-01", MAQUINA,
                                    meses=12)


if __name__ == "__main__":
    unittest.main()
