"""El código de máquina: qué identifica a una computadora y qué no.

Lo que se calcula a partir de datos dados es puro y se prueba entero. Lo que
sale del registro de Windows y del volumen del sistema sólo se comprueba por
encima -que devuelve algo con la forma correcta y que dos llamadas seguidas
dan lo mismo-, porque depende de la máquina donde corran las pruebas.

    python -m unittest discover -s pruebas -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mitienda import maquina  # noqa: E402
from mitienda.licencia import normalizar_maquina  # noqa: E402

GUID = "4c4c4544-0037-3810-8043-b1c04f435331"
SERIE = 3735928559


class LaHuella(unittest.TestCase):
    """La parte pura: dos datos entran, un código sale."""

    def test_tiene_la_forma_que_se_dicta_por_telefono(self):
        codigo = maquina.huella_de(GUID, SERIE)
        self.assertRegex(codigo, r"^[A-Z2-7]{4}-[A-Z2-7]{4}-[A-Z2-7]{4}$")

    def test_no_lleva_letras_que_se_confundan_con_numeros(self):
        """Base32 no tiene 0, 1, 8 ni 9, asi que O/0 y I/1 no se pueden
        confundir al dictarlo. Esto lo deja escrito por si alguien cambia
        la codificacion algun dia."""
        codigo = maquina.huella_de(GUID, SERIE)
        for confuso in "0189":
            self.assertNotIn(confuso, codigo)

    def test_la_misma_computadora_da_siempre_el_mismo_codigo(self):
        self.assertEqual(maquina.huella_de(GUID, SERIE), maquina.huella_de(GUID, SERIE))

    def test_otra_computadora_da_otro_codigo(self):
        otro_guid = "aaaaaaaa-0037-3810-8043-b1c04f435331"
        self.assertNotEqual(maquina.huella_de(GUID, SERIE),
                            maquina.huella_de(otro_guid, SERIE))

    def test_el_mismo_windows_en_otro_disco_da_otro_codigo(self):
        self.assertNotEqual(maquina.huella_de(GUID, SERIE),
                            maquina.huella_de(GUID, SERIE + 1))

    def test_sin_guid_todavia_hay_codigo(self):
        """Un Windows raro o sin permisos no puede dejar al cliente sin
        poder activar: se sigue adelante con lo que haya."""
        codigo = maquina.huella_de(None, SERIE)
        self.assertRegex(codigo, r"^[A-Z2-7]{4}-[A-Z2-7]{4}-[A-Z2-7]{4}$")

    def test_sin_guid_el_codigo_no_es_el_mismo_que_con_guid(self):
        """Si coincidieran, una maquina donde falla el registro podria
        colarse en la licencia de otra."""
        self.assertNotEqual(maquina.huella_de(None, SERIE),
                            maquina.huella_de(GUID, SERIE))

    def test_sin_disco_todavia_hay_codigo(self):
        codigo = maquina.huella_de(GUID, None)
        self.assertRegex(codigo, r"^[A-Z2-7]{4}-[A-Z2-7]{4}-[A-Z2-7]{4}$")

    def test_sin_nada_no_hay_codigo_que_valga(self):
        """Devolver "" y no inventarse uno: un codigo fijo para todas las
        maquinas sin datos seria una llave maestra."""
        self.assertEqual(maquina.huella_de(None, None), "")

    def test_el_guid_da_igual_como_venga_escrito(self):
        """El registro puede devolverlo con llaves o en mayusculas segun la
        version de Windows."""
        self.assertEqual(maquina.huella_de(GUID, SERIE),
                         maquina.huella_de("{" + GUID.upper() + "}", SERIE))


class EstaComputadora(unittest.TestCase):
    """Lo que de verdad lee la maquina donde corre esto."""

    def test_devuelve_un_codigo_con_la_forma_correcta(self):
        codigo = maquina.codigo_de_esta_maquina()
        self.assertRegex(codigo, r"^[A-Z2-7]{4}-[A-Z2-7]{4}-[A-Z2-7]{4}$",
                         "sin codigo no se puede activar ninguna licencia")

    def test_dos_llamadas_seguidas_dan_lo_mismo(self):
        self.assertEqual(maquina.codigo_de_esta_maquina(),
                         maquina.codigo_de_esta_maquina())

    def test_el_codigo_sobrevive_a_normalizar_maquina(self):
        """Es el que se compara con el de la licencia, asi que las dos
        normalizaciones tienen que entenderse."""
        codigo = maquina.codigo_de_esta_maquina()
        self.assertEqual(normalizar_maquina(codigo), codigo.replace("-", ""))

    def test_leer_la_maquina_nunca_revienta(self):
        """Pase lo que pase con el registro o con el disco, el programa tiene
        que llegar a la pantalla de licencia para poder explicarlo."""
        try:
            maquina.codigo_de_esta_maquina()
        except Exception as error:  # noqa: BLE001
            self.fail(f"no puede levantar excepciones y levanto {error!r}")


if __name__ == "__main__":
    unittest.main()
