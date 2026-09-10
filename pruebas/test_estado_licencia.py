"""El veredicto del arranque: qué puede hacer hoy este programa, en esta PC.

Es la pieza que junta todo lo demás -el fichero, la huella de la máquina, la
marca contra el reloj y las reglas puras- y deja escrito un estado que la API
consulta en cada ruta que escribe.

Con llave de mentira, carpeta temporal y clave de registro aparte: nada de
esto toca la instalación de verdad.

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
from herramientas.firma import llave_publica_de  # noqa: E402
from herramientas.generar_licencia import emitir  # noqa: E402
from lddl import almacen_licencia, estado_licencia, licencia, rutas  # noqa: E402

PRIVADA = bytes(range(32))
PUBLICA = llave_publica_de(PRIVADA)
CLAVE_DE_PRUEBAS = r"Software\MiTienda-pruebas"
HOY = datetime.date(2026, 9, 15)


def borrar_clave_de_pruebas():
    try:
        import winreg
    except ImportError:
        return
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, CLAVE_DE_PRUEBAS)
    except OSError:
        pass


class ConTodoAparte(unittest.TestCase):

    def setUp(self):
        self.temporal = base.carpeta_con_copia("mitienda-estado-")
        rutas.fijar_directorio_base(self.temporal)

        self.clave_real = almacen_licencia.CLAVE_REGISTRO
        almacen_licencia.CLAVE_REGISTRO = CLAVE_DE_PRUEBAS
        borrar_clave_de_pruebas()
        base.quitar_licencia(self.temporal)

        self.llave_real = estado_licencia.LLAVE_PUBLICA
        estado_licencia.LLAVE_PUBLICA = PUBLICA

        # La maquina tambien se fija, para que las pruebas no dependan de en
        # que computadora corran.
        self.maquina_real = estado_licencia.leer_maquina
        estado_licencia.leer_maquina = lambda: "A7K2-3M4P-XR7T"

        # La base de pruebas trae historial con fechas viejas; sin vaciarlo,
        # la marca de agua saldria de ahi y no de lo que apunte cada prueba.
        self.vaciar_historial()
        estado_licencia.olvidar()

    def tearDown(self):
        estado_licencia.olvidar()
        estado_licencia.leer_maquina = self.maquina_real
        estado_licencia.LLAVE_PUBLICA = self.llave_real
        borrar_clave_de_pruebas()
        almacen_licencia.CLAVE_REGISTRO = self.clave_real
        rutas.fijar_directorio_base(None)
        shutil.rmtree(self.temporal, ignore_errors=True)

    def vaciar_historial(self):
        import sqlite3
        con = sqlite3.connect(rutas.obtener_ruta_db())
        try:
            con.execute("DELETE FROM historial")
            con.commit()
        finally:
            con.close()

    def poner_licencia(self, **como):
        como.setdefault("maquina", "A7K2-3M4P-XR7T")
        como.setdefault("desde", HOY)
        como.setdefault("meses", 12)
        almacen_licencia.guardar_licencia(
            emitir(PRIVADA, como.pop("negocio", "Bodega La Esquina"),
                   como.pop("maquina"), **como))


class ConLicenciaEnRegla(ConTodoAparte):

    def test_el_programa_abre_y_puede_vender(self):
        self.poner_licencia()
        v = estado_licencia.comprobar(HOY)
        self.assertEqual(v.estado, licencia.ACTIVA)
        self.assertTrue(estado_licencia.puede_escribir())

    def test_el_nombre_del_negocio_queda_a_mano_para_la_ventana(self):
        self.poner_licencia(negocio="Panadería La Ñapa")
        self.assertEqual(estado_licencia.comprobar(HOY).negocio, "Panadería La Ñapa")

    def test_exigir_escritura_deja_pasar(self):
        self.poner_licencia()
        estado_licencia.comprobar(HOY)
        estado_licencia.exigir_escritura()  # no debe levantar nada

    def test_a_veinte_dias_avisa_pero_deja_trabajar(self):
        self.poner_licencia(dias=20, meses=None)
        v = estado_licencia.comprobar(HOY)
        self.assertEqual(v.estado, licencia.POR_VENCER)
        self.assertTrue(estado_licencia.puede_escribir())

    def test_comprobar_deja_apuntada_la_fecha_de_hoy(self):
        """Si no la apuntara, atrasar el reloj no dejaria rastro."""
        self.poner_licencia()
        estado_licencia.comprobar(HOY)
        self.assertEqual(almacen_licencia.marca_maxima(), HOY)


class LaCortesiaDeLosPrimerosDias(ConTodoAparte):
    """Sirve para dejar instalado e irse, y para hacer demostraciones."""

    def test_el_primer_dia_sin_licencia_funciona_igual(self):
        v = estado_licencia.comprobar(HOY)
        self.assertEqual(v.estado, licencia.CORTESIA)
        self.assertTrue(estado_licencia.puede_escribir())

    def test_dice_cuantos_dias_quedan(self):
        v = estado_licencia.comprobar(HOY)
        self.assertEqual(v.dias_restantes, estado_licencia.DIAS_DE_CORTESIA)

    def test_el_ultimo_dia_de_cortesia_todavia_abre(self):
        estado_licencia.comprobar(HOY)
        estado_licencia.olvidar()
        ultimo = HOY + datetime.timedelta(days=estado_licencia.DIAS_DE_CORTESIA)
        self.assertEqual(estado_licencia.comprobar(ultimo).estado, licencia.CORTESIA)

    def test_al_dia_siguiente_se_acabo(self):
        estado_licencia.comprobar(HOY)
        estado_licencia.olvidar()
        pasado = HOY + datetime.timedelta(days=estado_licencia.DIAS_DE_CORTESIA + 1)
        v = estado_licencia.comprobar(pasado)
        self.assertEqual(v.estado, licencia.SIN_LICENCIA)
        self.assertFalse(estado_licencia.puede_escribir())

    def test_poner_la_licencia_durante_la_cortesia_la_sustituye(self):
        estado_licencia.comprobar(HOY)
        self.poner_licencia()
        estado_licencia.olvidar()
        self.assertEqual(estado_licencia.comprobar(HOY).estado, licencia.ACTIVA)


class CuandoNoSePuedeVender(ConTodoAparte):

    def test_una_licencia_vencida_bloquea_la_escritura(self):
        self.poner_licencia(dias=10, meses=None)
        v = estado_licencia.comprobar(HOY + datetime.timedelta(days=11))
        self.assertEqual(v.estado, licencia.VENCIDA)
        self.assertFalse(estado_licencia.puede_escribir())

    def test_vencida_pero_todavia_se_sabe_de_quien_es(self):
        """Hace falta para poder ponerlo en la pantalla de renovacion."""
        self.poner_licencia(dias=10, meses=None, negocio="Bodega La Esquina")
        v = estado_licencia.comprobar(HOY + datetime.timedelta(days=11))
        self.assertEqual(v.negocio, "Bodega La Esquina")

    def test_exigir_escritura_levanta_licencia_vencida(self):
        self.poner_licencia(dias=10, meses=None)
        estado_licencia.comprobar(HOY + datetime.timedelta(days=11))
        with self.assertRaises(estado_licencia.LicenciaVencida):
            estado_licencia.exigir_escritura()

    def test_la_licencia_de_otra_computadora_no_abre_esta(self):
        self.poner_licencia(maquina="B3F5-2QW7-LM6D")
        v = estado_licencia.comprobar(HOY)
        self.assertEqual(v.estado, licencia.SIN_LICENCIA)
        self.assertEqual(v.motivo, licencia.OTRA_MAQUINA)
        self.assertFalse(estado_licencia.puede_escribir())

    def test_con_el_reloj_atrasado_no_se_abre_aunque_la_licencia_valga(self):
        """El caso de verdad: licencia buena del ano pasado y el reloj de
        Windows puesto al ano pasado."""
        self.poner_licencia()
        estado_licencia.comprobar(HOY)
        estado_licencia.olvidar()
        v = estado_licencia.comprobar(HOY - datetime.timedelta(days=300))
        self.assertEqual(v.estado, licencia.RELOJ_ATRASADO)
        self.assertFalse(estado_licencia.puede_escribir())

    def test_un_licencia_lic_manipulado_a_mano(self):
        self.poner_licencia()
        texto = almacen_licencia.leer_licencia()
        almacen_licencia.guardar_licencia(texto.replace("2027-", "2037-"))
        v = estado_licencia.comprobar(HOY)
        self.assertEqual(v.motivo, licencia.FIRMA)
        self.assertFalse(estado_licencia.puede_escribir())


class ActivarDesdeLaPantalla(ConTodoAparte):
    """Lo que pasa cuando el cliente suelta el licencia.lic en la ventana."""

    def test_una_licencia_buena_se_guarda_y_abre_el_programa(self):
        estado_licencia.comprobar(HOY)
        texto = emitir(PRIVADA, "Bodega La Esquina", "A7K2-3M4P-XR7T",
                       meses=12, desde=HOY)
        bien, v = estado_licencia.activar(texto, HOY)
        self.assertTrue(bien)
        self.assertEqual(v.estado, licencia.ACTIVA)
        self.assertIn("Bodega La Esquina", almacen_licencia.leer_licencia())

    def test_una_licencia_de_otra_maquina_no_se_guarda(self):
        """Si se guardara, pisaria la buena que pudiera haber."""
        self.poner_licencia(negocio="La Buena")
        estado_licencia.comprobar(HOY)
        ajena = emitir(PRIVADA, "La Ajena", "B3F5-2QW7-LM6D", meses=12, desde=HOY)
        bien, v = estado_licencia.activar(ajena, HOY)
        self.assertFalse(bien)
        self.assertEqual(v.motivo, licencia.OTRA_MAQUINA)
        self.assertIn("La Buena", almacen_licencia.leer_licencia())

    def test_pegar_cualquier_cosa_no_rompe_nada(self):
        estado_licencia.comprobar(HOY)
        bien, v = estado_licencia.activar("hola que tal", HOY)
        self.assertFalse(bien)
        self.assertEqual(v.motivo, licencia.FORMATO)


class LoQueLee_LaCajera(ConTodoAparte):
    """Los mensajes salen tal cual en pantalla y en el error de la API, asi
    que dicen que pasa Y que hacer, no solo que algo fallo."""

    def test_las_fechas_van_en_castellano_y_no_en_iso(self):
        """A mano y no con locale: en una caja con Windows en ingles, locale
        sacaria 'August 16' en medio de una frase en castellano."""
        self.assertEqual(
            estado_licencia.en_castellano(datetime.date(2027, 8, 16)),
            "16 de agosto de 2027")

    def test_sin_fecha_no_inventa_ninguna(self):
        self.assertEqual(estado_licencia.en_castellano(None), "")

    def test_la_vencida_dice_cuando_vencio_y_que_hay_que_hacer(self):
        self.poner_licencia(dias=10, meses=None)
        v = estado_licencia.comprobar(HOY + datetime.timedelta(days=11))
        mensaje = estado_licencia.explicar(v)
        self.assertIn("25 de septiembre de 2026", mensaje)
        self.assertIn("renovarla", mensaje)
        self.assertNotIn("2026-09-25", mensaje, "la fecha en ISO no se ensena")

    def test_la_de_otra_maquina_lo_dice_con_esas_palabras(self):
        """'Licencia no valida' obliga a llamar por telefono; esto no."""
        self.poner_licencia(maquina="B3F5-2QW7-LM6D")
        v = estado_licencia.comprobar(HOY)
        self.assertIn("otra computadora", estado_licencia.explicar(v))

    def test_el_reloj_atrasado_dice_donde_se_arregla(self):
        self.poner_licencia()
        estado_licencia.comprobar(HOY)
        estado_licencia.olvidar()
        v = estado_licencia.comprobar(HOY - datetime.timedelta(days=300))
        self.assertIn("Windows", estado_licencia.explicar(v))


class ElCodigoParaPedirLaLicencia(ConTodoAparte):

    def test_siempre_hay_codigo_de_maquina_que_ensenar(self):
        """Es lo primero que necesita el cliente para pedir su licencia, y
        tiene que salir aunque no haya licencia ninguna."""
        v = estado_licencia.comprobar(HOY)
        self.assertEqual(estado_licencia.codigo_de_maquina(), "A7K2-3M4P-XR7T")
        self.assertEqual(v.estado, licencia.CORTESIA)


if __name__ == "__main__":
    unittest.main()
