"""Las reglas de la licencia: qué se acepta, qué se rechaza y por qué motivo.

`lddl/licencia.py` es un módulo puro, igual que `calculo_cobro` o `carrito`:
no abre ficheros, no mira el reloj y no sabe en qué computadora está. Todo
eso -el texto, la fecha de hoy y la huella de la máquina- se lo dan hecho.
Por eso se puede probar un vencimiento sin tocar la hora de Windows.

Las llaves de aquí son de mentira y se generan en el momento. La de verdad no
tiene nada que hacer en el repositorio.

    python -m unittest discover -s pruebas -v
"""

import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from herramientas.firma import firmar, llave_publica_de  # noqa: E402
from lddl import licencia  # noqa: E402


PRIVADA = bytes(range(32))
PUBLICA = llave_publica_de(PRIVADA)
OTRA_PRIVADA = bytes(range(100, 132))

MAQUINA = "A7K2-3M4P-XR7T"
HOY = datetime.date(2026, 9, 15)


def licencia_de_prueba(negocio="Bodega La Esquina", maquina=MAQUINA,
                       desde="2026-09-15", hasta="2027-09-15",
                       edicion="completa", privada=PRIVADA):
    """El texto completo de un licencia.lic recién emitido."""
    datos = {"negocio": negocio, "maquina": maquina, "desde": desde,
             "hasta": hasta, "edicion": edicion}
    return licencia.componer(datos, firmar(privada, licencia.texto_canonico(datos)))


class UnaLicenciaEnRegla(unittest.TestCase):

    def test_dentro_de_fecha_y_en_su_maquina_esta_activa(self):
        v = licencia.verificar(licencia_de_prueba(), PUBLICA, MAQUINA, HOY)
        self.assertEqual(v.estado, licencia.ACTIVA)
        self.assertEqual(v.negocio, "Bodega La Esquina")
        self.assertEqual(v.edicion, "completa")
        self.assertEqual(v.hasta, datetime.date(2027, 9, 15))

    def test_el_texto_compuesto_se_vuelve_a_leer_igual(self):
        texto = licencia_de_prueba(negocio="El Rincón")
        self.assertTrue(texto.startswith(licencia.CABECERA))
        v = licencia.verificar(texto, PUBLICA, MAQUINA, HOY)
        self.assertEqual(v.estado, licencia.ACTIVA)
        self.assertEqual(v.negocio, "El Rincón")

    def test_un_negocio_con_tildes_y_enes_se_verifica(self):
        """El doble acento de PowerShell ya ha mordido en este proyecto; si
        la firma se calculara sobre otra codificación, esto fallaría."""
        texto = licencia_de_prueba(negocio="Panadería La Ñapa de José")
        v = licencia.verificar(texto, PUBLICA, MAQUINA, HOY)
        self.assertEqual(v.estado, licencia.ACTIVA)
        self.assertEqual(v.negocio, "Panadería La Ñapa de José")

    def test_windows_puede_guardarlo_con_crlf_y_sigue_valiendo(self):
        """El cliente lo va a abrir con el Bloc de notas tarde o temprano."""
        texto = licencia_de_prueba().replace("\n", "\r\n") + "\r\n\r\n"
        self.assertEqual(licencia.verificar(texto, PUBLICA, MAQUINA, HOY).estado,
                         licencia.ACTIVA)

    def test_espacios_de_sobra_alrededor_de_los_valores_no_estorban(self):
        texto = licencia_de_prueba().replace("negocio: ", "negocio:   ") + "   "
        self.assertEqual(licencia.verificar(texto, PUBLICA, MAQUINA, HOY).estado,
                         licencia.ACTIVA)


class ElCalendario(unittest.TestCase):
    """Los avisos y el vencimiento, sin tocar el reloj de la máquina."""

    def estado_a(self, dias_antes_de_vencer):
        hasta = datetime.date(2027, 9, 15)
        hoy = hasta - datetime.timedelta(days=dias_antes_de_vencer)
        return licencia.verificar(licencia_de_prueba(), PUBLICA, MAQUINA, hoy)

    def test_con_mas_de_treinta_dias_por_delante_no_molesta(self):
        self.assertEqual(self.estado_a(31).estado, licencia.ACTIVA)

    def test_a_treinta_dias_empieza_a_avisar(self):
        v = self.estado_a(30)
        self.assertEqual(v.estado, licencia.POR_VENCER)
        self.assertEqual(v.dias_restantes, 30)

    def test_a_ocho_dias_sigue_siendo_aviso_suave(self):
        self.assertEqual(self.estado_a(8).estado, licencia.POR_VENCER)

    def test_a_siete_dias_el_aviso_se_pone_serio(self):
        self.assertEqual(self.estado_a(7).estado, licencia.URGENTE)

    def test_el_ultimo_dia_todavia_se_puede_vender(self):
        v = self.estado_a(0)
        self.assertEqual(v.estado, licencia.URGENTE)
        self.assertEqual(v.dias_restantes, 0)

    def test_al_dia_siguiente_se_acabo(self):
        v = self.estado_a(-1)
        self.assertEqual(v.estado, licencia.VENCIDA)
        self.assertEqual(v.negocio, "Bodega La Esquina",
                         "vencida o no, hay que poder decir de quien es")

    def test_una_licencia_de_tecnico_no_pasa_la_vida_avisando(self):
        """Dura tres días: si entrara en el aviso de los siete, saldría el
        cartel de renovar cada vez que se abre, y no es una renovación."""
        texto = licencia_de_prueba(desde="2026-09-15", hasta="2026-09-18",
                                   edicion="tecnico")
        v = licencia.verificar(texto, PUBLICA, MAQUINA, datetime.date(2026, 9, 17))
        self.assertEqual(v.estado, licencia.ACTIVA)
        self.assertEqual(v.edicion, "tecnico")

    def test_una_licencia_de_tecnico_tambien_vence(self):
        texto = licencia_de_prueba(desde="2026-09-15", hasta="2026-09-18",
                                   edicion="tecnico")
        v = licencia.verificar(texto, PUBLICA, MAQUINA, datetime.date(2026, 9, 19))
        self.assertEqual(v.estado, licencia.VENCIDA)

    def test_si_hoy_es_anterior_a_la_emision_el_reloj_esta_mal(self):
        """Nadie tiene una licencia emitida el mes que viene. O el reloj de
        Windows está atrasado, o alguien lo ha atrasado a propósito."""
        v = licencia.verificar(licencia_de_prueba(desde="2026-09-15"), PUBLICA,
                               MAQUINA, datetime.date(2026, 9, 14))
        self.assertEqual(v.estado, licencia.RELOJ_ATRASADO)


class LoQueSeRechaza(unittest.TestCase):
    """Cada rechazo con su motivo: "esta licencia es de otra computadora"
    ahorra una llamada de soporte que "licencia no valida" no ahorra."""

    def test_sin_fichero_no_hay_licencia(self):
        for vacio in (None, "", "   \n  "):
            with self.subTest(texto=repr(vacio)):
                v = licencia.verificar(vacio, PUBLICA, MAQUINA, HOY)
                self.assertEqual(v.estado, licencia.SIN_LICENCIA)
                self.assertEqual(v.motivo, licencia.NO_HAY_ARCHIVO)

    def test_un_fichero_que_no_es_una_licencia(self):
        v = licencia.verificar("hola que tal", PUBLICA, MAQUINA, HOY)
        self.assertEqual(v.estado, licencia.SIN_LICENCIA)
        self.assertEqual(v.motivo, licencia.FORMATO)

    def test_una_cabecera_de_otra_version(self):
        texto = licencia_de_prueba().replace(licencia.CABECERA, "MiTienda-Licencia-v9")
        self.assertEqual(licencia.verificar(texto, PUBLICA, MAQUINA, HOY).motivo,
                         licencia.FORMATO)

    def test_si_falta_un_campo_no_se_intenta_adivinar(self):
        texto = "\n".join(l for l in licencia_de_prueba().splitlines()
                          if not l.startswith("edicion:"))
        self.assertEqual(licencia.verificar(texto, PUBLICA, MAQUINA, HOY).motivo,
                         licencia.FORMATO)

    def test_una_fecha_que_no_es_una_fecha(self):
        texto = licencia_de_prueba(hasta="el año que viene")
        self.assertEqual(licencia.verificar(texto, PUBLICA, MAQUINA, HOY).motivo,
                         licencia.FORMATO)

    def test_una_edicion_inventada(self):
        texto = licencia_de_prueba(edicion="ilimitada")
        self.assertEqual(licencia.verificar(texto, PUBLICA, MAQUINA, HOY).motivo,
                         licencia.FORMATO)

    def test_cambiarle_la_fecha_a_mano_invalida_la_firma(self):
        """El ataque más obvio de todos: abrir el fichero y estirar el año."""
        texto = licencia_de_prueba().replace("hasta: 2027-09-15", "hasta: 2037-09-15")
        v = licencia.verificar(texto, PUBLICA, MAQUINA, HOY)
        self.assertEqual(v.estado, licencia.SIN_LICENCIA)
        self.assertEqual(v.motivo, licencia.FIRMA)

    def test_cambiarle_el_negocio_a_mano_tambien(self):
        texto = licencia_de_prueba().replace("Bodega La Esquina", "Bodega La Otra")
        self.assertEqual(licencia.verificar(texto, PUBLICA, MAQUINA, HOY).motivo,
                         licencia.FIRMA)

    def test_una_licencia_firmada_por_otro_no_vale(self):
        texto = licencia_de_prueba(privada=OTRA_PRIVADA)
        self.assertEqual(licencia.verificar(texto, PUBLICA, MAQUINA, HOY).motivo,
                         licencia.FIRMA)

    def test_una_firma_recortada_al_copiar_y_pegar(self):
        texto = licencia_de_prueba()
        texto = texto[:texto.rindex("\n") - 10]
        self.assertEqual(licencia.verificar(texto, PUBLICA, MAQUINA, HOY).estado,
                         licencia.SIN_LICENCIA)

    def test_la_licencia_del_vecino_no_abre_esta_caja(self):
        """Esto es lo que impide que un cliente le pase la carpeta a otro."""
        v = licencia.verificar(licencia_de_prueba(), PUBLICA, "B3F5-2QW7-LM6D", HOY)
        self.assertEqual(v.estado, licencia.SIN_LICENCIA)
        self.assertEqual(v.motivo, licencia.OTRA_MAQUINA)
        self.assertEqual(v.negocio, "Bodega La Esquina",
                         "hace falta para poder decirle de quien es la que tiene")

    def test_el_codigo_de_maquina_no_distingue_mayusculas_ni_guiones(self):
        """La cajera lo va a dictar por telefono y a teclear a mano."""
        for escrito_asi in ("a7k2-3m4p-xr7t", "A7K23M4PXR7T", " A7K2-3M4P-XR7T "):
            with self.subTest(maquina=escrito_asi):
                v = licencia.verificar(licencia_de_prueba(), PUBLICA, escrito_asi, HOY)
                self.assertEqual(v.estado, licencia.ACTIVA)


if __name__ == "__main__":
    unittest.main()
