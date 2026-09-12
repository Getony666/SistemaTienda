"""El candado de la licencia, donde de verdad cierra: en la API.

Esconder los botones de la pantalla es una comodidad. Quien sepa la dirección
puede llamar a la ruta desde la consola del navegador, así que lo que impide
vender con la licencia vencida es que la ruta conteste 402 y no toque la base.
Es la misma decisión que se tomó con los permisos, y aquí se comprueba igual:
llamando a las rutas de verdad.

Lo que tiene que seguir funcionando con la licencia vencida es tan importante
como lo que se bloquea: el cliente consulta su historial, ve a quién le deben
y exporta. Sus datos son suyos.

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
from mitienda import almacen_licencia, estado_licencia, licencia, rutas, sesion, usuarios  # noqa: E402
from mitienda.esquema import preparar_base  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
from mitienda.api import app  # noqa: E402

PRIVADA = bytes(range(32))
PUBLICA = llave_publica_de(PRIVADA)
MAQUINA = "A7K2-3M4P-XR7T"
CLAVE_DE_PRUEBAS = r"Software\MiTienda-pruebas"
HOY = datetime.date.today()  # la API usa el reloj de verdad


def borrar_clave_de_pruebas():
    try:
        import winreg
    except ImportError:
        return
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, CLAVE_DE_PRUEBAS)
    except OSError:
        pass


class ConLaApiEnPie(unittest.TestCase):

    def setUp(self):
        self.temporal = base.carpeta_con_copia("mitienda-api-lic-")
        rutas.fijar_directorio_base(self.temporal)
        preparar_base()

        self.clave_real = almacen_licencia.CLAVE_REGISTRO
        almacen_licencia.CLAVE_REGISTRO = CLAVE_DE_PRUEBAS
        borrar_clave_de_pruebas()
        base.quitar_licencia(self.temporal)

        self.llave_real = estado_licencia.LLAVE_PUBLICA
        estado_licencia.LLAVE_PUBLICA = PUBLICA
        self.maquina_real = estado_licencia.leer_maquina
        estado_licencia.leer_maquina = lambda: MAQUINA

        self.vaciar_historial()
        estado_licencia.olvidar()

        # Admin dentro: lo que se comprueba aqui es la licencia, no el permiso.
        usuarios.crear_usuario("Jefa", usuarios.ADMIN, "1234")
        sesion.entrar("Jefa", "1234")
        self.cliente = TestClient(app)

    def tearDown(self):
        self.cliente.close()
        sesion.salir()
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

    def con_licencia_vencida(self):
        almacen_licencia.guardar_licencia(
            emitir(PRIVADA, "Bodega La Esquina", MAQUINA, dias=10,
                   desde=HOY - datetime.timedelta(days=400)))
        estado_licencia.olvidar()
        estado_licencia.comprobar(HOY)

    def con_licencia_al_dia(self):
        almacen_licencia.guardar_licencia(
            emitir(PRIVADA, "Bodega La Esquina", MAQUINA, meses=12, desde=HOY))
        estado_licencia.olvidar()
        estado_licencia.comprobar(HOY)


class ConLaLicenciaVencida(ConLaApiEnPie):

    def test_no_se_puede_cobrar_una_venta(self):
        self.con_licencia_vencida()
        r = self.cliente.post("/ventas", json={
            "productos": [], "total": 100, "pago_efectivo": 100,
            "pago_transferencia": 0, "es_deuda": False})
        self.assertEqual(r.status_code, 402, r.text)

    def test_no_se_puede_dar_de_alta_un_producto(self):
        self.con_licencia_vencida()
        r = self.cliente.post("/productos", json={"nombre": "Cafe"})
        self.assertEqual(r.status_code, 402, r.text)

    def test_no_se_puede_sacar_dinero_de_la_caja(self):
        self.con_licencia_vencida()
        r = self.cliente.post("/caja/salidas", json={"monto": 500, "motivo": "x"})
        self.assertEqual(r.status_code, 402, r.text)

    def test_no_se_puede_borrar_del_historial(self):
        self.con_licencia_vencida()
        self.assertEqual(self.cliente.delete("/historial/1").status_code, 402)

    def test_la_respuesta_explica_que_pasa_y_no_solo_que_fallo(self):
        self.con_licencia_vencida()
        detalle = self.cliente.post("/productos", json={"nombre": "Cafe"}).json()["detail"]
        self.assertIn("licencia", detalle.lower())

    def test_nada_de_eso_llego_a_escribirse_en_la_base(self):
        """402 y basta: si escribiera y luego se quejara, el candado no
        serviria de nada."""
        self.con_licencia_vencida()
        antes = self.cliente.get("/productos").json()
        self.cliente.post("/productos", json={"nombre": "Producto Colado"})
        self.assertEqual(self.cliente.get("/productos").json(), antes)


class LoQueSiguePudiendoHacerse(ConLaApiEnPie):
    """Los datos del negocio son del negocio, tambien con la licencia vencida."""

    def test_se_puede_consultar_el_corte_de_caja(self):
        self.con_licencia_vencida()
        r = self.cliente.get(f"/corte/{HOY.isoformat()}")
        self.assertEqual(r.status_code, 200, r.text)

    def test_se_pueden_ver_las_ventas_y_las_deudas(self):
        self.con_licencia_vencida()
        self.assertEqual(self.cliente.get("/ventas").status_code, 200)

    def test_se_puede_consultar_el_catalogo(self):
        self.con_licencia_vencida()
        self.assertEqual(self.cliente.get("/productos").status_code, 200)

    def test_se_puede_ver_el_almacen(self):
        self.con_licencia_vencida()
        self.assertEqual(self.cliente.get("/almacen").status_code, 200)

    def test_se_puede_entrar_y_salir_del_programa(self):
        """Sin esto no se llega ni a la pantalla de licencia."""
        self.con_licencia_vencida()
        sesion.salir()
        r = self.cliente.post("/sesion", json={"nombre": "Jefa", "pin": "1234"})
        self.assertEqual(r.status_code, 200, r.text)

    def test_la_calculadora_del_vuelto_sigue_respondiendo(self):
        """Es aritmetica: no toca la base y la pantalla la llama en cada tecla."""
        self.con_licencia_vencida()
        r = self.cliente.post("/cobro/vuelto", json={
            "total_cup": 100, "moneda": "CUP", "efectivo": 200})
        self.assertEqual(r.status_code, 200, r.text)


class ConLaLicenciaAlDia(ConLaApiEnPie):

    def test_se_puede_dar_de_alta_un_producto(self):
        self.con_licencia_al_dia()
        r = self.cliente.post("/productos", json={"nombre": "Cafe de Prueba"})
        self.assertEqual(r.status_code, 201, r.text)


class LaRutaDeLaLicencia(ConLaApiEnPie):
    """Lo que usa la pantalla de licencia. Nunca se bloquea a si misma."""

    def test_dice_el_codigo_de_maquina_aunque_no_haya_licencia(self):
        estado_licencia.olvidar()
        estado_licencia.comprobar(HOY)
        datos = self.cliente.get("/licencia").json()
        self.assertEqual(datos["maquina"], MAQUINA)

    def test_se_consulta_con_la_licencia_vencida(self):
        self.con_licencia_vencida()
        datos = self.cliente.get("/licencia").json()
        self.assertEqual(datos["estado"], licencia.VENCIDA)
        self.assertFalse(datos["puede_escribir"])
        self.assertTrue(datos["explicacion"])

    def test_pegar_una_licencia_buena_desbloquea_el_programa(self):
        self.con_licencia_vencida()
        nueva = emitir(PRIVADA, "Bodega La Esquina", MAQUINA, meses=12, desde=HOY)
        r = self.cliente.post("/licencia", json={"texto": nueva})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.cliente.post("/productos",
                                           json={"nombre": "Ya Se Puede"}).status_code,
                         201)

    def test_pegar_la_licencia_de_otro_programa_se_rechaza_con_su_motivo(self):
        self.con_licencia_vencida()
        ajena = emitir(PRIVADA, "La de Otro", MAQUINA, meses=12, desde=HOY,
                       producto="MiBodega")
        r = self.cliente.post("/licencia", json={"texto": ajena})
        self.assertEqual(r.status_code, 400)
        self.assertIn("otro programa", r.json()["detail"])

    def test_pegar_una_licencia_de_otra_maquina_se_rechaza_con_su_motivo(self):
        self.con_licencia_vencida()
        ajena = emitir(PRIVADA, "La Ajena", "B3F5-2QW7-LM6D", meses=12, desde=HOY)
        r = self.cliente.post("/licencia", json={"texto": ajena})
        self.assertEqual(r.status_code, 400)
        self.assertIn("otra computadora", r.json()["detail"])


class NingunaRutaQueEscribeSeQuedaSinLicencia(ConLaApiEnPie):
    """Si alguien anade una ruta nueva y olvida la licencia, esto lo caza."""

    SIN_LICENCIA_A_PROPOSITO = {
        # Aritmetica pura: no tocan la base.
        ("POST", "/cobro/vuelto"),
        ("POST", "/cobro/desglose"),
        ("POST", "/deudas/{venta_id}/simular"),
        # Entrar y salir: sin esto no se llega a la pantalla de licencia.
        ("POST", "/sesion"),
        ("DELETE", "/sesion"),
        ("POST", "/sesion/primer-admin"),
        # La propia activacion no puede bloquearse a si misma.
        ("POST", "/licencia"),
    }

    def test_todas_las_rutas_que_escriben_exigen_licencia(self):
        from mitienda.api import guardian_de_licencia

        sospechosas = set()
        for ruta in app.routes:
            camino = getattr(ruta, "path", "")
            for metodo in getattr(ruta, "methods", set()):
                if metodo not in ("POST", "PUT", "PATCH", "DELETE"):
                    continue
                if (metodo, camino) in self.SIN_LICENCIA_A_PROPOSITO:
                    continue
                llamadas = [getattr(d, "dependency", None)
                            for d in getattr(ruta, "dependencies", [])]
                if guardian_de_licencia not in llamadas:
                    sospechosas.add((metodo, camino))
        self.assertEqual(
            sospechosas, set(),
            "Rutas que escriben sin exigir licencia. Ponles exige_licencia(), o "
            "apuntalas en SIN_LICENCIA_A_PROPOSITO si de verdad no hace falta.")


if __name__ == "__main__":
    unittest.main()
