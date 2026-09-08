"""Pruebas de la API.

Usan el cliente de pruebas de FastAPI: no hace falta levantar el servidor ni
abrir un puerto.

    python -m unittest discover -s pruebas -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from fastapi.testclient import TestClient
    from lddl.api import app
    HAY_API = True
except Exception:  # sin fastapi instalado
    HAY_API = False


@unittest.skipUnless(HAY_API, "hace falta fastapi (ver requisitos-api.txt)")
class LaApiResponde(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cliente = TestClient(app)

    def test_salud(self):
        r = self.cliente.get("/salud")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["estado"], "ok")
        self.assertEqual(r.json()["base_de_datos"], "ok")

    def test_productos_devuelve_la_forma_esperada(self):
        r = self.cliente.get("/productos", params={"buscar": "aceite"})
        self.assertEqual(r.status_code, 200)
        datos = r.json()
        self.assertGreater(len(datos), 0)
        for campo in ("id", "nombre", "precio", "stock", "tipo", "unidad"):
            self.assertIn(campo, datos[0])

    def test_ventas_rechaza_una_fecha_mal_escrita(self):
        self.assertEqual(self.cliente.get("/ventas", params={"fecha": "07-09-2026"}).status_code, 422)
        self.assertEqual(self.cliente.get("/ventas", params={"fecha": "2026-13-40"}).status_code, 422)

    def test_corte_devuelve_el_resumen_del_dia(self):
        r = self.cliente.get("/corte/2026-09-07")
        self.assertEqual(r.status_code, 200)
        datos = r.json()
        for campo in ("total_esperado", "utilidad_total", "fondo_registrado",
                      "saldo_divisas", "fecha"):
            self.assertIn(campo, datos)

    def test_corte_rechaza_fecha_invalida(self):
        self.assertEqual(self.cliente.get("/corte/hoy").status_code, 422)


@unittest.skipUnless(HAY_API, "hace falta fastapi (ver requisitos-api.txt)")
class ElCobroPorHttpDaLoMismoQueLaCaja(unittest.TestCase):
    """La API no puede calcular distinto que la ventana: usa el mismo módulo."""

    @classmethod
    def setUpClass(cls):
        cls.cliente = TestClient(app)

    def test_vuelto_en_cup(self):
        r = self.cliente.post("/cobro/vuelto",
                              json={"total_cup": 2250, "efectivo": 2300})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(d["cubre"])
        self.assertAlmostEqual(d["vuelto_cup"], 50.0)
        self.assertEqual(d["texto"], "50.00 CUP")

    def test_vuelto_en_divisa_repartido(self):
        r = self.cliente.post("/cobro/vuelto", json={
            "total_cup": 5000, "moneda": "USD", "tasa": 400,
            "efectivo": 15, "vuelto_en_moneda": 2})
        d = r.json()
        self.assertAlmostEqual(d["vuelto_cup"], 1000.0)
        self.assertAlmostEqual(d["vuelto_moneda"], 2.0)
        self.assertAlmostEqual(d["vuelto_cup_restante"], 200.0)
        self.assertEqual(d["texto"], "2.00 USD + 200.00 CUP")

    def test_no_alcanza(self):
        r = self.cliente.post("/cobro/vuelto",
                              json={"total_cup": 1000, "efectivo": 400})
        d = r.json()
        self.assertFalse(d["cubre"])
        self.assertAlmostEqual(d["falta_cup"], 600.0)

    def test_vuelto_en_divisa_que_excede_se_avisa(self):
        r = self.cliente.post("/cobro/vuelto", json={
            "total_cup": 5000, "moneda": "USD", "tasa": 400,
            "efectivo": 15, "vuelto_en_moneda": 5})
        self.assertEqual(r.json()["error"], "vuelto_moneda_excede")

    def test_desglose_reparte_el_cobro(self):
        r = self.cliente.post("/cobro/desglose", json={
            "total_cup": 1000, "efectivo": 200, "transferencia": 900})
        d = r.json()
        self.assertEqual(d["metodo_pago_real"], "Mixto")
        self.assertAlmostEqual(d["monto_efectivo_cup"], 100.0)
        self.assertAlmostEqual(d["monto_transferencia_cup"], 900.0)

    def test_desglose_de_una_deuda(self):
        r = self.cliente.post("/cobro/desglose",
                              json={"total_cup": 1220}, params={"es_deuda": "true"})
        d = r.json()
        self.assertEqual(d["pagada"], 0)
        self.assertAlmostEqual(d["saldo_pendiente"], 1220.0)

    def test_desglose_avisa_del_pago_invalido(self):
        r = self.cliente.post("/cobro/desglose", json={
            "total_cup": 100, "moneda": "USD", "tasa": 0, "efectivo": 1})
        self.assertEqual(r.status_code, 422)

    def test_cup_que_falta(self):
        r = self.cliente.get("/cobro/faltante", params={
            "total_cup": 5000, "pago_divisa": 10, "tasa": 400})
        self.assertAlmostEqual(r.json()["falta_cup"], 1000.0)


@unittest.skipUnless(HAY_API, "hace falta fastapi (ver requisitos-api.txt)")
class LaApiNoEscribe(unittest.TestCase):
    """Ninguna ruta de datos debe permitir modificar nada."""

    def test_solo_hay_lectura_en_los_datos(self):
        for ruta in app.routes:
            metodos = getattr(ruta, "methods", set())
            camino = getattr(ruta, "path", "")
            if camino.startswith("/cobro"):
                continue  # aritmética pura, no toca la base
            self.assertFalse(
                metodos & {"POST", "PUT", "PATCH", "DELETE"},
                f"{camino} expone {metodos}: los datos son de sólo lectura")


if __name__ == "__main__":
    unittest.main(verbosity=2)
