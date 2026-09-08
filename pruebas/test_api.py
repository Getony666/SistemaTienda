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


# Rutas que tocan la base. Están escritas a mano a propósito: si alguien añade
# una nueva y no la apunta aquí, la prueba falla y le obliga a acordarse de que
# esta API no puede salir a internet tal cual.
RUTAS_QUE_ESCRIBEN = {
    ("POST", "/ventas"),
    ("POST", "/deudas/{venta_id}/cobros"),
    ("POST", "/productos"),
    ("PUT", "/productos/{producto_id}"),
    ("DELETE", "/productos/{producto_id}"),
    ("POST", "/inventario/salidas"),
    ("POST", "/inventario/mermas"),
    ("POST", "/caja/entradas"),
    ("POST", "/caja/salidas"),
    ("PUT", "/caja/fondo/{fecha}"),
    ("POST", "/cambio"),
    ("DELETE", "/historial/{registro_id}"),
}


@unittest.skipUnless(HAY_API, "hace falta fastapi (ver requisitos-api.txt)")
class QueRutasEscriben(unittest.TestCase):

    def _rutas_que_modifican(self):
        encontradas = set()
        for ruta in app.routes:
            camino = getattr(ruta, "path", "")
            # /cobro es aritmética pura y /simular sólo consulta y calcula:
            # son POST porque reciben datos, no porque escriban.
            if camino.startswith("/cobro") or camino.endswith("/simular"):
                continue
            for metodo in getattr(ruta, "methods", set()):
                if metodo in ("POST", "PUT", "PATCH", "DELETE"):
                    encontradas.add((metodo, camino))
        return encontradas

    def test_no_hay_escrituras_sin_declarar(self):
        nuevas = self._rutas_que_modifican() - RUTAS_QUE_ESCRIBEN
        self.assertEqual(
            nuevas, set(),
            "Rutas que escriben y no están declaradas en RUTAS_QUE_ESCRIBEN. "
            "Recuerda que esta API no puede exponerse a internet tal cual.")

    def test_las_declaradas_siguen_existiendo(self):
        self.assertEqual(RUTAS_QUE_ESCRIBEN - self._rutas_que_modifican(), set())

    def test_consultar_nunca_modifica(self):
        for metodo, camino in self._rutas_que_modifican():
            if camino in ("/salud", "/corte/{fecha}"):
                self.fail(f"{camino} deberia ser de solo lectura")


@unittest.skipUnless(HAY_API, "hace falta fastapi (ver requisitos-api.txt)")
class LaApiEscribeDeVerdad(unittest.TestCase):
    """Escrituras contra una COPIA de la base, nunca contra la real.

    `fijar_directorio_base` existe justo para esto: se copian tienda.db y
    config_caja.json a una carpeta temporal, se trabaja allí y al terminar se
    borra y se devuelve el programa a su sitio.
    """

    @classmethod
    def setUpClass(cls):
        import shutil
        import tempfile

        from lddl import rutas

        cls.rutas = rutas
        raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.temporal = tempfile.mkdtemp(prefix="mitienda-pruebas-")
        for nombre in ("tienda.db", "config_caja.json"):
            origen = os.path.join(raiz, nombre)
            if os.path.exists(origen):
                shutil.copy2(origen, os.path.join(cls.temporal, nombre))
        rutas.fijar_directorio_base(cls.temporal)
        cls.cliente = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        import shutil

        cls.rutas.fijar_directorio_base(None)
        shutil.rmtree(cls.temporal, ignore_errors=True)

    def test_la_copia_no_es_la_base_real(self):
        self.assertIn("mitienda-pruebas-", self.rutas.obtener_ruta_db())

    # ---------------------------------------------------------- productos

    def test_alta_edicion_y_baja_de_un_producto(self):
        alta = self.cliente.post("/productos", json={
            "nombre": "Producto de prueba", "precio_venta": 100.0, "stock": 5.0})
        self.assertEqual(alta.status_code, 201, alta.text)

        listado = self.cliente.get("/productos", params={"buscar": "Producto de prueba"}).json()
        self.assertEqual(len(listado), 1)
        creado = listado[0]
        self.assertAlmostEqual(creado["precio"], 100.0)

        edicion = self.cliente.put(f"/productos/{creado['id']}", json={
            "nombre": "Producto de prueba", "categoria": "", "precio_compra": 60.0,
            "precio_venta": 150.0, "stock": 5.0, "proveedor": "",
            "tipo_producto": "unidad", "unidad_medida": "unidad", "fecha_vencimiento": ""})
        self.assertEqual(edicion.status_code, 200, edicion.text)

        tras_editar = self.cliente.get("/productos", params={"buscar": "Producto de prueba"}).json()
        self.assertAlmostEqual(tras_editar[0]["precio"], 150.0)

        baja = self.cliente.delete(f"/productos/{creado['id']}")
        self.assertEqual(baja.status_code, 200, baja.text)
        self.assertEqual(
            self.cliente.get("/productos", params={"buscar": "Producto de prueba"}).json(), [])

    def test_no_se_puede_borrar_un_producto_con_ventas(self):
        r = self.cliente.delete("/productos/3")
        self.assertEqual(r.status_code, 422)

    # -------------------------------------------------------------- caja

    def test_entrada_y_salida_de_efectivo(self):
        entrada = self.cliente.post("/caja/entradas",
                                    json={"moneda": "CUP", "monto": 500.0,
                                          "descripcion": "prueba"})
        self.assertEqual(entrada.status_code, 201, entrada.text)

        salida = self.cliente.post("/caja/salidas",
                                   json={"moneda": "CUP", "monto": 100.0,
                                         "descripcion": "prueba"})
        self.assertEqual(salida.status_code, 201, salida.text)

    def test_no_se_puede_sacar_mas_efectivo_del_que_hay(self):
        r = self.cliente.post("/caja/salidas",
                              json={"moneda": "CUP", "monto": 9_999_999.0})
        self.assertEqual(r.status_code, 422)
        self.assertIn("suficiente", r.json()["detail"].lower())

    def test_fijar_el_fondo_del_dia(self):
        r = self.cliente.put("/caja/fondo/2026-09-08", json={"fondo": 1500.0})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertAlmostEqual(
            self.cliente.get("/corte/2026-09-08").json()["fondo_registrado"], 1500.0)

    def test_el_fondo_rechaza_una_fecha_mal_escrita(self):
        self.assertEqual(
            self.cliente.put("/caja/fondo/manana", json={"fondo": 10.0}).status_code, 422)

    # ------------------------------------------------------------ ventas

    def _stock_de(self, producto_id):
        for p in self.cliente.get("/productos").json():
            if p["id"] == producto_id:
                return p["stock"]
        self.fail(f"no existe el producto {producto_id}")

    def test_una_venta_completa_descuenta_el_stock(self):
        antes = self._stock_de(3)
        r = self.cliente.post("/ventas", json={
            "carrito": [{"id": 3, "nombre": "Aceite 1000 ml", "cantidad": 2,
                         "precio": 200.0, "tipo": "unidad", "unidad": "unidad"}],
            "pago": {"total_cup": 400.0, "efectivo": 500.0},
        })
        self.assertEqual(r.status_code, 201, r.text)
        self.assertIn("venta_id", r.json())
        self.assertEqual(r.json()["vuelto_texto"], "100.00 CUP")
        self.assertAlmostEqual(self._stock_de(3), antes - 2)

    def test_una_venta_que_no_se_paga_entera_se_rechaza(self):
        antes = self._stock_de(3)
        r = self.cliente.post("/ventas", json={
            "carrito": [{"id": 3, "nombre": "Aceite 1000 ml", "cantidad": 2,
                         "precio": 200.0}],
            "pago": {"total_cup": 400.0, "efectivo": 100.0},
        })
        self.assertEqual(r.status_code, 422)
        self.assertAlmostEqual(self._stock_de(3), antes, msg="no debio tocar el stock")

    def test_una_venta_a_deuda_no_exige_pago(self):
        r = self.cliente.post("/ventas", json={
            "carrito": [{"id": 3, "nombre": "Aceite 1000 ml", "cantidad": 1,
                         "precio": 200.0}],
            "pago": {"total_cup": 200.0},
            "es_deuda": True,
            "observaciones": "cliente conocido",
        })
        self.assertEqual(r.status_code, 201, r.text)

    def test_el_carrito_vacio_se_rechaza(self):
        r = self.cliente.post("/ventas", json={
            "carrito": [], "pago": {"total_cup": 0.0}})
        self.assertEqual(r.status_code, 422)

    # ------------------------------------------------------- inventario

    def test_una_merma_mayor_que_el_stock_se_rechaza(self):
        r = self.cliente.post("/inventario/mermas",
                              json={"producto_id": 3, "cantidad": 99999.0})
        self.assertEqual(r.status_code, 422)
        self.assertIn("insuficiente", r.json()["detail"].lower())

    def test_una_merma_normal_descuenta_el_stock(self):
        antes = self._stock_de(3)
        r = self.cliente.post("/inventario/mermas",
                              json={"producto_id": 3, "cantidad": 1.0,
                                    "motivo": "prueba"})
        self.assertEqual(r.status_code, 201, r.text)
        self.assertAlmostEqual(self._stock_de(3), antes - 1)

    # ----------------------------------------------------------- cambio

    def test_comprar_divisa(self):
        r = self.cliente.post("/cambio", json={
            "tipo": "compra", "moneda": "USD", "cantidad": 10.0, "tasa": 400.0})
        self.assertEqual(r.status_code, 201, r.text)

    # ----------------------------------------------------------- deudas

    def _id_de_una_deuda(self):
        for v in self.cliente.get("/ventas", params={"tipo": "deudas"}).json():
            if v.get("detalle_extra", {}).get("pagada") == 0:
                return v["id"], v["detalle_extra"]["saldo_pendiente"]
        self.skipTest("no hay deudas pendientes en la copia")

    def test_simular_un_abono_no_guarda_nada(self):
        venta_id, saldo = self._id_de_una_deuda()
        r = self.cliente.post(f"/deudas/{venta_id}/simular",
                              json={"efectivo": saldo / 2})
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertEqual(d["pagada"], 0)
        self.assertAlmostEqual(d["nuevo_saldo"], saldo / 2)

        # y la deuda sigue igual
        _, saldo_despues = self._id_de_una_deuda()
        self.assertAlmostEqual(saldo_despues, saldo)

    def test_un_abono_parcial_deja_la_deuda_abierta(self):
        venta_id, saldo = self._id_de_una_deuda()
        r = self.cliente.post(f"/deudas/{venta_id}/cobros", json={"efectivo": 100.0})
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()["pagada"], 0)
        self.assertAlmostEqual(r.json()["nuevo_saldo"], saldo - 100.0)

    def test_no_se_puede_cobrar_una_venta_que_no_es_deuda(self):
        r = self.cliente.post("/deudas/999999/cobros", json={"efectivo": 10.0})
        self.assertEqual(r.status_code, 404)

    def test_el_mixto_necesita_las_dos_partes(self):
        venta_id, _ = self._id_de_una_deuda()
        r = self.cliente.post(f"/deudas/{venta_id}/simular",
                              json={"metodo": "Mixto", "efectivo": 100.0,
                                    "transferencia": 0.0})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"], "mixto_necesita_ambos")

    def test_en_divisa_solo_se_admite_efectivo(self):
        venta_id, _ = self._id_de_una_deuda()
        r = self.cliente.post(f"/deudas/{venta_id}/simular",
                              json={"moneda": "USD", "tasa": 400.0,
                                    "metodo": "Transferencia", "efectivo": 1.0})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"], "divisa_solo_efectivo")


if __name__ == "__main__":
    unittest.main(verbosity=2)
