"""Dónde vive la licencia y cómo se recuerda qué día fue el último.

Dos trabajos, los dos con efectos secundarios y por eso separados de las
reglas puras de `mitienda/licencia.py`:

1. Leer y escribir `licencia.lic`, al lado del .exe.
2. La marca de agua contra el reloj atrasado. Se guarda por triplicado -en la
   base, en el registro de Windows y en la propia tabla del historial- para
   que borrar una cosa no baste.

El registro de verdad NO se toca: estas pruebas apuntan a una clave aparte y
la borran al terminar.

    python -m unittest discover -s pruebas -v
"""

import datetime
import os
import shutil
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import base  # noqa: E402
from mitienda import almacen_licencia, rutas  # noqa: E402

CLAVE_DE_PRUEBAS = r"Software\MiTienda-pruebas"


def borrar_clave_de_pruebas():
    try:
        import winreg
    except ImportError:
        return
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, CLAVE_DE_PRUEBAS)
    except OSError:
        pass


class SobreUnaCopia(unittest.TestCase):
    """Carpeta temporal para los ficheros y clave aparte para el registro."""

    def setUp(self):
        self.temporal = base.carpeta_con_copia("mitienda-lic-")
        rutas.fijar_directorio_base(self.temporal)
        self.clave_real = almacen_licencia.CLAVE_REGISTRO
        almacen_licencia.CLAVE_REGISTRO = CLAVE_DE_PRUEBAS
        borrar_clave_de_pruebas()
        base.quitar_licencia(self.temporal)

    def tearDown(self):
        borrar_clave_de_pruebas()
        almacen_licencia.CLAVE_REGISTRO = self.clave_real
        rutas.fijar_directorio_base(None)
        shutil.rmtree(self.temporal, ignore_errors=True)

    def poner_base_virgen(self):
        """Deja la base como la que se entrega a un negocio nuevo.

        No vale con borrar `tienda.db` a secas: `preparar_base()` no sabe
        crear el esquema desde cero -da por hecho que la tabla `ventas` ya
        existe-, así que un cliente que la borrara se quedaría sin programa.
        Lo que haría de verdad es traerse la base virgen de la entrega. Eso
        es lo que se simula: estructura entera, sin un solo dato.
        """
        import sqlite3
        shutil.copy2(base.BASE, rutas.obtener_ruta_db())
        from mitienda.esquema import preparar_base
        preparar_base()
        con = sqlite3.connect(rutas.obtener_ruta_db())
        try:
            con.execute("DELETE FROM historial")
            con.execute("DELETE FROM marcas_licencia")
            con.commit()
        finally:
            con.close()


class ElFicheroDeLicencia(SobreUnaCopia):

    def test_sin_fichero_no_hay_texto_pero_tampoco_error(self):
        self.assertEqual(almacen_licencia.leer_licencia(), "")

    def test_va_al_lado_del_ejecutable(self):
        self.assertEqual(rutas.obtener_ruta_licencia(),
                         os.path.join(self.temporal, "licencia.lic"))

    def test_lo_que_se_guarda_se_vuelve_a_leer(self):
        almacen_licencia.guardar_licencia("MiTienda-Licencia-v1\nnegocio: X\n")
        self.assertIn("negocio: X", almacen_licencia.leer_licencia())

    def test_un_negocio_con_tildes_sobrevive_al_disco(self):
        """Guardar en la codificacion de Windows y leer en UTF-8 es
        exactamente como salen los acentos dobles."""
        almacen_licencia.guardar_licencia("negocio: Panadería La Ñapa\n")
        self.assertIn("Panadería La Ñapa", almacen_licencia.leer_licencia())

    def test_un_fichero_ilegible_no_tumba_el_programa(self):
        """Puede llegar en cualquier codificacion: lo manda un cliente."""
        with open(rutas.obtener_ruta_licencia(), "wb") as fichero:
            fichero.write(b"\xff\xfe\x00basura binaria\x00")
        try:
            almacen_licencia.leer_licencia()
        except Exception as error:  # noqa: BLE001
            self.fail(f"leer no puede levantar excepciones y levanto {error!r}")


class LaMarcaDeAgua(SobreUnaCopia):
    """Lo que impide estirar la licencia atrasando el reloj de Windows."""

    def test_sin_anotar_nada_la_marca_sale_del_historial(self):
        """La base de pruebas trae ventas, y cada una lleva su fecha: aunque
        alguien borre el registro, el propio historial delata el dia."""
        self.assertIsNotNone(almacen_licencia.marca_maxima())

    def test_lo_anotado_se_recuerda(self):
        almacen_licencia.anotar_marca(datetime.date(2030, 5, 4))
        self.assertEqual(almacen_licencia.marca_maxima(), datetime.date(2030, 5, 4))

    def test_la_marca_nunca_retrocede(self):
        """Si retrocediera, bastaria con abrir el programa una vez con el
        reloj atrasado para borrar el rastro."""
        almacen_licencia.anotar_marca(datetime.date(2030, 5, 4))
        almacen_licencia.anotar_marca(datetime.date(2027, 1, 1))
        self.assertEqual(almacen_licencia.marca_maxima(), datetime.date(2030, 5, 4))

    def test_cambiar_la_base_por_una_virgen_no_borra_la_marca(self):
        """El truco obvio: tirar tienda.db y traerse la virgen de la entrega,
        para que el programa crea que acaba de instalarse. La copia del
        registro sobrevive y lo delata."""
        almacen_licencia.anotar_marca(datetime.date(2030, 5, 4))
        self.poner_base_virgen()
        self.assertEqual(almacen_licencia.marca_maxima(), datetime.date(2030, 5, 4))


class ElRelojAtrasado(unittest.TestCase):
    """La decision en si es pura: dos fechas entran, un si o un no sale."""

    MARCA = datetime.date(2027, 6, 15)

    def test_al_dia_no_pasa_nada(self):
        self.assertFalse(almacen_licencia.reloj_atrasado(self.MARCA, self.MARCA))

    def test_hacia_adelante_nunca_es_sospechoso(self):
        futuro = self.MARCA + datetime.timedelta(days=400)
        self.assertFalse(almacen_licencia.reloj_atrasado(futuro, self.MARCA))

    def test_un_dia_de_menos_entra_en_el_margen(self):
        """Husos horarios, cambios de hora y pilas de placa base gastadas.
        Bloquear a un cliente honesto por un dia seria peor el remedio."""
        self.assertFalse(almacen_licencia.reloj_atrasado(
            self.MARCA - datetime.timedelta(days=1), self.MARCA))

    def test_dos_dias_de_menos_todavia_entran(self):
        self.assertFalse(almacen_licencia.reloj_atrasado(
            self.MARCA - datetime.timedelta(days=2), self.MARCA))

    def test_tres_dias_de_menos_ya_no(self):
        self.assertTrue(almacen_licencia.reloj_atrasado(
            self.MARCA - datetime.timedelta(days=3), self.MARCA))

    def test_un_ano_atras_es_el_caso_de_verdad(self):
        self.assertTrue(almacen_licencia.reloj_atrasado(
            self.MARCA - datetime.timedelta(days=365), self.MARCA))

    def test_sin_marca_no_hay_nada_que_comparar(self):
        """Primera vez que se abre el programa: no hay historia todavia."""
        self.assertFalse(almacen_licencia.reloj_atrasado(self.MARCA, None))


class ElPrimerArranque(SobreUnaCopia):
    """La fecha desde la que cuentan los siete dias de cortesia."""

    def test_la_primera_vez_se_apunta_hoy(self):
        hoy = datetime.date(2026, 9, 15)
        self.assertEqual(almacen_licencia.primer_arranque(hoy), hoy)

    def test_las_siguientes_veces_no_se_mueve(self):
        """Si se moviera, la cortesia no se acabaria nunca."""
        primero = datetime.date(2026, 9, 15)
        almacen_licencia.primer_arranque(primero)
        despues = almacen_licencia.primer_arranque(datetime.date(2026, 9, 30))
        self.assertEqual(despues, primero)

    def test_sobrevive_a_que_cambien_la_base_por_una_virgen(self):
        """Si no sobreviviera, la cortesia se renovaria sola cada siete dias
        con solo copiar otra vez el tienda.db de la entrega."""
        primero = datetime.date(2026, 9, 15)
        almacen_licencia.primer_arranque(primero)
        self.poner_base_virgen()
        self.assertEqual(almacen_licencia.primer_arranque(datetime.date(2026, 9, 30)),
                         primero)


if __name__ == "__main__":
    unittest.main()
