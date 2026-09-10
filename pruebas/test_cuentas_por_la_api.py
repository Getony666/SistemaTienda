"""El camino nuevo -React llamando a la API- tiene que dar las mismas cuentas
que el viejo.

`test_equivalencia_con_la_app.py` y `test_registro_de_venta.py` protegen el
cálculo puro (`lddl/calculo_cobro.py`) conduciendo... nada: ya no hay ventana
de tkinter que conducir, así que comparan contra el acta que dejó grabada
antes de irse. Eso deja cubierto el módulo, pero la pantalla que se entrega
hoy -React, en `interfaz/src/PanelVentas.jsx` y `DialogoDeuda.jsx`- no llama
al módulo: llama a la API por HTTP. Nada obliga a que `lddl/api.py` traduzca
bien esas llamadas; este archivo lo comprueba.

Hace pasar las MISMAS tablas de `pruebas/casos.py` -CASOS/REFERENCIA y
ESCENARIOS/FINALIZAR- por los endpoints que la pantalla nueva usa de verdad
para cerrar una venta:

- `/cobro/vuelto` y `/cobro/desglose`: lo que `PanelVentas.jsx` pide en cada
  tecla (ver el `useEffect` que llama a `enviar("/cobro/vuelto", ...)`),
  antes de dejar confirmar. El cuerpo que manda -`datosDelPago()`- tiene
  EXACTAMENTE los mismos campos que el dataclass `Pago`; por eso basta con
  volcar el `Pago` de cada caso a un diccionario (`_cuerpo_de_pago`) para
  reproducir la petición real, sin reescribir la tabla.
- `POST /ventas`: lo que se dispara al pulsar "Finalizar venta". Cierra la
  venta de verdad, así que aquí sí se comprueba lo que queda en la tabla
  `ventas` -de donde comen después el corte de caja y el historial-, no sólo
  la respuesta HTTP.
- `/inventario/salidas/carrito` y `/inventario/mermas/carrito`: los modos
  "Salida" y "Merma" del carrito entero (objeto `MODOS` en `PanelVentas.jsx`),
  que la ventana vieja no tenía y por tanto ninguna prueba de
  caracterización llegó a cubrir.
- `/deudas/{id}/cobros`: el diálogo de cobrar una deuda (`DialogoDeuda.jsx`),
  que usa `calculo_deuda` en vez de `calculo_cobro`.

No se inventan casos para lo que ya tiene tabla congelada: si una fila de
`casos.py` no se puede expresar tal cual por la API, se documenta y se deja
fuera (ver `ElAutorrellenoDeTransferenciaNoTieneEndpoint`). Sí se añade
cobertura nueva -al final del archivo- para lo que React hace y la ventana
vieja no hacía: el carrito con varias líneas, la salida/merma de carrito
completo, y el vuelto mixto en divisa combinado con pago adicional en CUP.

    python -m unittest discover -s pruebas -v
"""

import dataclasses
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import base  # noqa: E402
from casos import (  # noqa: E402
    CASOS,
    ESCENARIOS,
    FINALIZAR,
    REFERENCIA,
    pago_del_caso,
    pago_del_escenario,
)

try:
    from fastapi.testclient import TestClient

    from lddl import calculo_cobro as cc
    from lddl.api import app
    from lddl.rutas import consulta
    HAY_API = True
except Exception:  # sin fastapi instalado
    HAY_API = False


# Igual que en test_api.py: hasta las pruebas de sólo lectura necesitan datos
# que leer, y tienda.db se entrega vacía a cada negocio nuevo.
_CARPETA = None


def setUpModule():
    global _CARPETA
    _CARPETA = base.empezar_modulo()


def tearDownModule():
    base.terminar_modulo(_CARPETA)


def _cuerpo_de_pago(pago):
    """El JSON que manda React para cobrar o cerrar una venta.

    Los campos del dataclass `Pago` (`lddl/calculo_cobro.py`) son uno a uno
    los de `PagoEntrante` (`lddl/api.py`) y los que arma `datosDelPago()` en
    `PanelVentas.jsx`: no hace falta traducir nada, sólo volcarlo.
    """
    return dataclasses.asdict(pago)


# =========================================================================
#  /cobro/vuelto y /cobro/desglose -no tocan la base, no hace falta sesión.
# =========================================================================

@unittest.skipUnless(HAY_API, "hace falta fastapi (ver requisitos-api.txt)")
class ElCobroPorLaApiCoincideConLaReferencia(unittest.TestCase):
    """Los mismos CASOS de siempre, pero pedidos por HTTP en vez de en
    proceso. Es justo lo que hace PanelVentas.jsx antes de dejar pulsar
    "Finalizar venta": pedirle el vuelto y el reparto a la API."""

    @classmethod
    def setUpClass(cls):
        cls.cliente = TestClient(app)

    def test_el_vuelto_coincide_con_la_referencia(self):
        for caso in CASOS:
            nombre = caso[0]
            with self.subTest(caso=nombre):
                pago = pago_del_caso(*caso[1:])
                r = self.cliente.post("/cobro/vuelto", json=_cuerpo_de_pago(pago))
                self.assertEqual(r.status_code, 200, r.text)
                d = r.json()

                # El núcleo ya se probó a fondo en test_equivalencia_con_la_app.py;
                # aquí lo que importa es que el viaje por HTTP (serializar el
                # Pago, reconstruirlo, calcular, volver a serializar) no cambie
                # ni una cifra respecto de llamarlo en el mismo proceso.
                esperado = cc.calcular_vuelto(pago)
                self.assertEqual(d["error"], esperado.error, msg=f"[{nombre}]")
                self.assertEqual(d["cubre"], esperado.cubre, msg=f"[{nombre}]")
                self.assertAlmostEqual(d["falta_cup"], esperado.falta_cup, places=6, msg=f"[{nombre}]")
                self.assertAlmostEqual(d["vuelto_moneda"], esperado.vuelto_moneda, places=6, msg=f"[{nombre}]")
                self.assertAlmostEqual(d["vuelto_cup_restante"], esperado.vuelto_cup_restante,
                                        places=6, msg=f"[{nombre}]")

                # Y la cifra final tiene que seguir siendo la que daba la app
                # vieja: la razón de ser de toda esta tabla.
                obtenido = 0.0 if d["error"] else d["vuelto_cup"]
                self.assertAlmostEqual(
                    obtenido, REFERENCIA[nombre], places=6,
                    msg=f"[{nombre}] la API da {obtenido}, la referencia dice {REFERENCIA[nombre]}")

                # Los textos son el contrato propio de la API (cc.texto_vuelto /
                # cc.texto_resumen_pago), no las cadenas de TEXTOS en casos.py:
                # esas llevan una corrección deliberada de cómo lo pintaba la
                # pantalla vieja (ver el comentario en casos.py) y ya se
                # comparan contra el acta en test_equivalencia_con_la_app.py.
                self.assertEqual(d["texto"], cc.texto_vuelto(esperado, pago.moneda), msg=f"[{nombre}]")
                self.assertEqual(d["resumen_pago"], cc.texto_resumen_pago(pago), msg=f"[{nombre}]")

    def test_el_desglose_reparte_igual_que_el_nucleo(self):
        """El reparto entre efectivo, transferencia y divisa -incluidos los
        casos de pago mixto- para guardar la venta, pedido por HTTP."""
        for caso in CASOS:
            nombre = caso[0]
            pago = pago_del_caso(*caso[1:])
            vuelto = cc.calcular_vuelto(pago)
            if vuelto.error or not vuelto.cubre:
                # /cobro/desglose es una previsualización del reparto, no un
                # intento de cerrar la venta: no valida que el pago alcance
                # (eso lo hace /ventas antes de guardar, y se prueba más abajo
                # contra estos mismos tres casos: "CUP no alcanza", "CUP nada"
                # y "CUP mixto no alcanza"). Pedirle un desglose a un pago que
                # no cubre no tiene una respuesta de referencia con la que
                # comparar, así que se saltan aquí.
                continue
            with self.subTest(caso=nombre):
                r = self.cliente.post("/cobro/desglose", json=_cuerpo_de_pago(pago))
                self.assertEqual(r.status_code, 200, r.text)
                d = r.json()

                esperado = cc.desglosar_para_registro(pago)
                self.assertEqual(d["metodo_pago_real"], esperado.metodo_pago_real, msg=f"[{nombre}]")
                self.assertEqual(d["moneda_pago"], esperado.moneda_pago, msg=f"[{nombre}]")
                self.assertAlmostEqual(d["tasa_cambio"], esperado.tasa_cambio, places=6, msg=f"[{nombre}]")
                self.assertAlmostEqual(d["monto_efectivo_cup"], esperado.monto_efectivo_cup,
                                        places=6, msg=f"[{nombre}]")
                self.assertAlmostEqual(d["monto_transferencia_cup"], esperado.monto_transferencia_cup,
                                        places=6, msg=f"[{nombre}]")
                self.assertAlmostEqual(d["pago_divisa"], esperado.pago_divisa, places=6, msg=f"[{nombre}]")
                self.assertAlmostEqual(d["vuelto_moneda"], esperado.vuelto_moneda, places=6, msg=f"[{nombre}]")
                self.assertAlmostEqual(d["salida_efectivo_extra"], esperado.salida_efectivo_extra,
                                        places=6, msg=f"[{nombre}]")


@unittest.skipUnless(HAY_API, "hace falta fastapi (ver requisitos-api.txt)")
class ElAutorrellenoDeTransferenciaNoTieneEndpoint(unittest.TestCase):
    """CASOS_MIXTO / MIXTO (en casos.py) no pasan por la API: no hay nada que
    llamar.

    Esas dos tablas capturan un relleno automático exclusivo de la ventana de
    tkinter: tecleabas sólo en "Pagado (Transferencia)" y el campo "Efectivo"
    se rellenaba solo con el resto (ver el comentario de casos.py: "El otro
    camino de cálculo"). Ni `calculo_cobro.py` reproduce ese relleno -es
    puramente de pantalla- ni `PanelVentas.jsx` lo hace: ahí "Pagado
    (efectivo)" y "Pagado (transferencia)" son dos campos totalmente
    independientes, sin relleno cruzado. No existe, por tanto, un endpoint
    que ejercite ese camino; se documenta aquí en vez de forzarlo.
    """

    def test_no_hay_endpoint_para_el_autorrelleno_de_transferencia(self):
        self.skipTest(
            "CASOS_MIXTO/MIXTO de casos.py describen un autorrelleno de la "
            "ventana de tkinter que ni el módulo ni PanelVentas.jsx "
            "reproducen; no hay endpoint de la API que lo ejercite.")


# =========================================================================
#  Rutas que escriben: cada clase trabaja sobre su propia copia de la base,
#  con un Admin propio -igual que LaApiEscribeDeVerdad en test_api.py.
# =========================================================================

@unittest.skipUnless(HAY_API, "hace falta fastapi (ver requisitos-api.txt)")
class BaseConSesionDeAdmin(unittest.TestCase):
    """No tiene pruebas propias: da la copia de base y la sesión a sus hijas.

    Cada subclase llama a `setUpClass`/`tearDownClass` con su propio `cls`,
    así que cada una trabaja sobre SU copia, aislada de las demás y de la que
    usa el resto del módulo.
    """

    @classmethod
    def setUpClass(cls):
        if cls is BaseConSesionDeAdmin:
            raise unittest.SkipTest("clase base, sin pruebas propias")

        from lddl import rutas, sesion, usuarios

        cls._rutas = rutas
        cls._sesion = sesion
        cls.temporal = base.carpeta_con_copia()
        rutas.fijar_directorio_base(cls.temporal)
        usuarios.crear_usuario("PruebaAdmin", usuarios.ADMIN, "1234")
        sesion.entrar("PruebaAdmin", "1234")
        cls.cliente = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        if cls is BaseConSesionDeAdmin:
            return
        import shutil
        cls._sesion.salir()
        cls._rutas.fijar_directorio_base(_CARPETA)
        shutil.rmtree(cls.temporal, ignore_errors=True)

    def _fila_de_venta(self, venta_id):
        with consulta() as (_conexion, cursor):
            cursor.execute('''
                SELECT total, metodo_pago, moneda_pago, tasa_cambio, metodo_pago_real,
                       monto_efectivo, monto_transferencia, monto_divisa_neto,
                       pago_texto, vuelto_texto, saldo_pendiente, pagada
                FROM ventas WHERE id = ?
            ''', (venta_id,))
            fila = cursor.fetchone()
        campos = ("total", "metodo_pago", "moneda_pago", "tasa_cambio", "metodo_pago_real",
                  "monto_efectivo", "monto_transferencia", "monto_divisa_neto",
                  "pago_texto", "vuelto_texto", "saldo_pendiente", "pagada")
        return dict(zip(campos, fila))

    def _stock_de(self, producto_id):
        with consulta() as (_conexion, cursor):
            cursor.execute("SELECT stock FROM productos WHERE id = ?", (producto_id,))
            return cursor.fetchone()[0]

    def _salida_efectivo_de(self, venta_id):
        with consulta() as (_conexion, cursor):
            cursor.execute(
                "SELECT SUM(monto) FROM salidas_efectivo WHERE venta_id = ?", (venta_id,))
            total = cursor.fetchone()[0]
        return total or 0.0


class ElRegistroDeVentaPorLaApiCoincideConLaReferencia(BaseConSesionDeAdmin):
    """POST /ventas: lo que se dispara al pulsar "Finalizar venta".

    Cierra la venta de verdad -no simula nada- y compara lo que queda escrito
    en la tabla `ventas` contra FINALIZAR, la misma referencia que ya protege
    `test_registro_de_venta.py` para el módulo puro. De ahí comen después el
    corte de caja y el historial: si la API guardara distinto, esas dos
    pantallas mentirían sin que ninguna prueba del núcleo lo notara.
    """

    PRODUCTO_ID = 3
    PRODUCTO_NOMBRE = "Aceite 1000 ml"

    def _carrito(self, total):
        return [{"id": self.PRODUCTO_ID, "nombre": self.PRODUCTO_NOMBRE, "cantidad": 1,
                 "precio": total, "tipo": "unidad", "unidad": "unidad"}]

    def test_todos_los_escenarios_quedan_guardados_como_la_referencia(self):
        for escenario in ESCENARIOS:
            nombre = escenario[0]
            es_deuda = escenario[2]
            with self.subTest(escenario=nombre):
                pago = pago_del_escenario(*escenario[1:])
                stock_antes = self._stock_de(self.PRODUCTO_ID)

                r = self.cliente.post("/ventas", json={
                    "carrito": self._carrito(pago.total_cup),
                    "pago": _cuerpo_de_pago(pago),
                    "es_deuda": bool(es_deuda),
                })
                self.assertEqual(r.status_code, 201, f"[{nombre}] {r.text}")
                venta_id = r.json()["venta_id"]

                esperado = FINALIZAR[nombre]
                self.assertEqual(r.json()["vuelto_texto"], esperado["vuelto_texto"], msg=f"[{nombre}]")

                fila = self._fila_de_venta(venta_id)
                for campo_venta, campo_referencia in (
                    ("metodo_pago", "metodo_pago"),
                    ("moneda_pago", "moneda_pago"),
                    ("tasa_cambio", "tasa_cambio"),
                    ("metodo_pago_real", "metodo_pago_real"),
                    ("monto_efectivo", "monto_efectivo_cup"),
                    ("monto_transferencia", "monto_transferencia_cup"),
                    ("pago_texto", "pago_texto"),
                    ("vuelto_texto", "vuelto_texto"),
                    ("saldo_pendiente", "saldo_pendiente"),
                    ("pagada", "pagada"),
                ):
                    obtenido, esperado_valor = fila[campo_venta], esperado[campo_referencia]
                    if isinstance(esperado_valor, float):
                        self.assertAlmostEqual(
                            obtenido, esperado_valor, places=6,
                            msg=f"[{nombre}] {campo_venta}: {obtenido!r} en vez de {esperado_valor!r}")
                    else:
                        self.assertEqual(
                            obtenido, esperado_valor,
                            msg=f"[{nombre}] {campo_venta}: {obtenido!r} en vez de {esperado_valor!r}")

                # monto_divisa_neto y la salida de efectivo del vuelto no son
                # columnas de FINALIZAR (ese diccionario habla en el
                # vocabulario del desglose, no del esquema), pero se calculan
                # a partir de sus propios campos y también quedan guardados.
                moneda_pago = esperado["moneda_pago"]
                divisa_neta_esperada = (
                    esperado["pago_divisa"] - esperado["vuelto_moneda"]
                    if not es_deuda and moneda_pago in ("USD", "EUR") and esperado["pago_divisa"] > 0
                    else 0.0)
                self.assertAlmostEqual(fila["monto_divisa_neto"], divisa_neta_esperada, places=6,
                                        msg=f"[{nombre}] monto_divisa_neto")

                salida_extra = self._salida_efectivo_de(venta_id)
                self.assertAlmostEqual(salida_extra, esperado["salida_efectivo_extra"], places=6,
                                        msg=f"[{nombre}] salida_efectivo_extra")

                self.assertAlmostEqual(self._stock_de(self.PRODUCTO_ID), stock_antes - 1, places=6,
                                        msg=f"[{nombre}] no descontó el stock del carrito")


class LasVentasQueNoAlcanzanSeRechazan(BaseConSesionDeAdmin):
    """Los 3 casos de CASOS que no cubren el total.

    `/cobro/desglose` los deja pasar -es sólo repartir, no intenta cerrar
    nada- pero `/ventas`, la ruta que de verdad guarda algo, los tiene que
    rechazar antes de tocar la base. Por eso esta prueba sí necesita sesión:
    a diferencia de `/cobro/*`, `/ventas` exige el permiso "vender".
    """

    def test_no_pueden_cerrarse_por_la_api(self):
        no_cubren = [c for c in CASOS if not cc.calcular_vuelto(pago_del_caso(*c[1:])).cubre]
        self.assertEqual(
            {c[0] for c in no_cubren}, {"CUP no alcanza", "CUP nada", "CUP mixto no alcanza"})

        for caso in no_cubren:
            nombre, total = caso[0], caso[1]
            with self.subTest(caso=nombre):
                stock_antes = self._stock_de(3)
                pago = pago_del_caso(*caso[1:])
                r = self.cliente.post("/ventas", json={
                    "carrito": [{"id": 3, "nombre": "Aceite 1000 ml", "cantidad": 1,
                                 "precio": total, "tipo": "unidad", "unidad": "unidad"}],
                    "pago": _cuerpo_de_pago(pago),
                })
                self.assertEqual(r.status_code, 422, msg=f"[{nombre}] {r.text}")
                self.assertAlmostEqual(self._stock_de(3), stock_antes,
                                        msg=f"[{nombre}] no debió tocar el stock")


class ElCarritoPorLaApi(BaseConSesionDeAdmin):
    """Varias líneas, cantidades y el stock resultante.

    Las tablas de casos.py siempre traen una sola línea -son casos de
    cálculo del cobro, no del carrito-, así que ese camino queda sin probar
    si no se ejercita aparte. Es justo lo que hace PanelVentas.jsx: sumar
    todas las líneas del carrito para llegar al total que luego se cobra.
    """

    def test_varias_lineas_descuentan_el_stock_de_cada_una(self):
        aceite_antes = self._stock_de(3)
        arroz_antes = self._stock_de(311)

        total = 3 * 200.0 + 2 * 193.0  # 986.0
        r = self.cliente.post("/ventas", json={
            "carrito": [
                {"id": 3, "nombre": "Aceite 1000 ml", "cantidad": 3,
                 "precio": 200.0, "tipo": "unidad", "unidad": "unidad"},
                {"id": 311, "nombre": "arrozxlibra", "cantidad": 2,
                 "precio": 193.0, "tipo": "peso", "unidad": "libra"},
            ],
            "pago": {"total_cup": total, "efectivo": total},
        })
        self.assertEqual(r.status_code, 201, r.text)
        venta_id = r.json()["venta_id"]

        self.assertAlmostEqual(self._stock_de(3), aceite_antes - 3)
        self.assertAlmostEqual(self._stock_de(311), arroz_antes - 2)

        fila = self._fila_de_venta(venta_id)
        self.assertAlmostEqual(fila["total"], total)
        self.assertEqual(fila["pagada"], 1)
        self.assertAlmostEqual(fila["monto_efectivo"], total)

        with consulta() as (_conexion, cursor):
            cursor.execute(
                "SELECT producto_id, cantidad, precio_unitario FROM detalles_venta "
                "WHERE venta_id = ? ORDER BY producto_id", (venta_id,))
            lineas = cursor.fetchall()
        self.assertEqual(lineas, [(3, 3.0, 200.0), (311, 2.0, 193.0)])


class LasDeudasPorLaApi(BaseConSesionDeAdmin):
    """Una venta que deja deuda, y su cobro por partes hasta saldarse.

    Usa el camino real de `DialogoDeuda.jsx`: `/deudas/{id}/cobros`, que
    calcula con `calculo_deuda.py` -no con `calculo_cobro.py`- y por tanto no
    está cubierto por las tablas CASOS/ESCENARIOS de este archivo.
    """

    def test_una_deuda_se_cobra_por_partes_hasta_saldarse(self):
        r = self.cliente.post("/ventas", json={
            "carrito": [{"id": 3, "nombre": "Aceite 1000 ml", "cantidad": 1,
                         "precio": 700.0, "tipo": "unidad", "unidad": "unidad"}],
            "pago": {"total_cup": 700.0},
            "es_deuda": True,
            "observaciones": "cliente de prueba",
        })
        self.assertEqual(r.status_code, 201, r.text)
        venta_id = r.json()["venta_id"]

        fila = self._fila_de_venta(venta_id)
        self.assertEqual(fila["pagada"], 0)
        self.assertAlmostEqual(fila["saldo_pendiente"], 700.0)

        abono = self.cliente.post(f"/deudas/{venta_id}/cobros", json={"efectivo": 300.0})
        self.assertEqual(abono.status_code, 201, abono.text)
        self.assertEqual(abono.json()["pagada"], 0)
        self.assertAlmostEqual(abono.json()["nuevo_saldo"], 400.0)
        self.assertAlmostEqual(self._fila_de_venta(venta_id)["saldo_pendiente"], 400.0)

        final = self.cliente.post(f"/deudas/{venta_id}/cobros", json={"efectivo": 400.0})
        self.assertEqual(final.status_code, 201, final.text)
        self.assertEqual(final.json()["pagada"], 1)
        self.assertAlmostEqual(final.json()["nuevo_saldo"], 0.0)
        self.assertAlmostEqual(final.json()["vuelto_cup"], 0.0)

        fila_final = self._fila_de_venta(venta_id)
        self.assertEqual(fila_final["pagada"], 1)
        self.assertAlmostEqual(fila_final["saldo_pendiente"], 0.0)

        with consulta() as (_conexion, cursor):
            cursor.execute(
                "SELECT monto, metodo_pago, moneda, monto_cup FROM cobros_deudas "
                "WHERE venta_id = ? ORDER BY id", (venta_id,))
            cobros = cursor.fetchall()
        self.assertEqual(cobros, [
            (300.0, "Efectivo", "CUP", 300.0),
            (400.0, "Efectivo", "CUP", 400.0),
        ])


class SalidaYMermaDeCarritoPorLaApi(BaseConSesionDeAdmin):
    """Los modos "Salida" y "Merma" del carrito entero.

    Son el objeto `MODOS` de `PanelVentas.jsx`: la misma pantalla de ventas,
    pero marcando la pastilla "Salida" o "Merma" en vez de cobrar. La ventana
    de tkinter no los tenía, así que ninguna prueba de caracterización llegó
    a cubrirlos -son cobertura genuinamente nueva, no una tabla congelada.
    """

    def test_la_salida_de_carrito_genera_una_sola_deuda_a_precio_de_costo(self):
        aceite_antes = self._stock_de(3)
        arroz_antes = self._stock_de(311)
        motivo = "Salida de prueba API"

        r = self.cliente.post("/inventario/salidas/carrito", json={
            "lineas": [{"producto_id": 3, "cantidad": 2},
                       {"producto_id": 311, "cantidad": 1}],
            "motivo": motivo,
        })
        self.assertEqual(r.status_code, 201, r.text)

        self.assertAlmostEqual(self._stock_de(3), aceite_antes - 2)
        self.assertAlmostEqual(self._stock_de(311), arroz_antes - 1)

        # El precio de costo lo pone el almacén, no quien llama (ver
        # `_leer_lineas` en lddl/inventario.py): en la base de pruebas, el
        # precio_compra de ambos productos es 100.0.
        total_esperado = 2 * 100.0 + 1 * 100.0
        with consulta() as (_conexion, cursor):
            cursor.execute(
                "SELECT total, es_deuda, pagada, metodo_pago, saldo_pendiente "
                "FROM ventas WHERE observaciones = ?", (motivo,))
            fila = cursor.fetchone()
        self.assertIsNotNone(fila, "la salida de carrito no dejó venta ni deuda")
        total, es_deuda, pagada, metodo_pago, saldo_pendiente = fila
        self.assertAlmostEqual(total, total_esperado)
        self.assertEqual((es_deuda, pagada, metodo_pago), (1, 0, "Salida"))
        self.assertAlmostEqual(saldo_pendiente, total_esperado)

    def test_la_merma_de_carrito_no_cobra_ni_genera_deuda(self):
        aceite_antes = self._stock_de(3)
        arroz_antes = self._stock_de(311)
        motivo = "Merma de prueba API"

        r = self.cliente.post("/inventario/mermas/carrito", json={
            "lineas": [{"producto_id": 3, "cantidad": 1},
                       {"producto_id": 311, "cantidad": 1}],
            "motivo": motivo,
        })
        self.assertEqual(r.status_code, 201, r.text)

        self.assertAlmostEqual(self._stock_de(3), aceite_antes - 1)
        self.assertAlmostEqual(self._stock_de(311), arroz_antes - 1)

        # Sin venta, sin deuda, sin caja: sólo baja el almacén.
        with consulta() as (_conexion, cursor):
            cursor.execute(
                "SELECT COUNT(*) FROM ventas WHERE observaciones LIKE ?", (f"%{motivo}%",))
            self.assertEqual(cursor.fetchone()[0], 0)

        # Y aparece en la misma lista que consulta la pantalla de historial:
        # GET /ventas?tipo=merma.
        mermas = self.cliente.get("/ventas", params={"tipo": "merma"}).json()
        productos_en_merma = {m["producto"] for m in mermas if motivo in m["observaciones"]}
        self.assertEqual(productos_en_merma, {"Aceite 1000 ml", "arrozxlibra"})


class ElVueltoMixtoEnDivisaConCupAdicionalPorLaApi(BaseConSesionDeAdmin):
    """Cobertura nueva: "pago adicional en CUP" + "vuelto repartido en
    divisa" a la vez.

    `PanelVentas.jsx` deja usar los dos bloques de la pantalla de Pago al
    mismo tiempo (el "Pago adicional en CUP" y el "Vuelto en <moneda>" son
    secciones independientes), pero ninguna fila de CASOS los combina -las
    que tienen `cup_ef`/`cup_tr` dejan `vuelto_moneda` vacío, y la única con
    `vuelto_moneda` no usa `cup_ef`/`cup_tr`- así que la ventana vieja nunca
    llegó a caracterizar esa combinación. El núcleo (`calculo_cobro.py`) ya
    la soporta sin cambios -no hay nada que arreglar-; esto sólo comprueba
    que el camino HTTP y el guardado en la base no la rompen.
    """

    def test_vuelto_y_desglose_combinan_las_dos_cosas(self):
        # 5000 CUP a pagar; 12 USD a 400 (=4800) + 300 CUP adicionales = 5100:
        # sobran 100 CUP de vuelto, de los que 0.20 USD (=80 CUP) se devuelven
        # en divisa y el resto (20 CUP) en CUP.
        pago = cc.Pago(total_cup=5000.0, moneda="USD", tasa=400.0,
                       efectivo=12.0, cup_efectivo=300.0, vuelto_en_moneda=0.2)

        r = self.cliente.post("/cobro/vuelto", json=_cuerpo_de_pago(pago))
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertIsNone(d["error"])
        self.assertTrue(d["cubre"])
        self.assertAlmostEqual(d["vuelto_cup"], 100.0)
        self.assertAlmostEqual(d["vuelto_moneda"], 0.2)
        self.assertAlmostEqual(d["vuelto_cup_restante"], 20.0)
        self.assertEqual(d["texto"], "0.20 USD + 20.00 CUP")

        rd = self.cliente.post("/cobro/desglose", json=_cuerpo_de_pago(pago))
        self.assertEqual(rd.status_code, 200, rd.text)
        desg = rd.json()
        self.assertEqual(desg["metodo_pago_real"], "Mixto")
        self.assertAlmostEqual(desg["monto_efectivo_cup"], 280.0)
        self.assertAlmostEqual(desg["monto_transferencia_cup"], 0.0)
        self.assertAlmostEqual(desg["salida_efectivo_extra"], 0.0)

        # Y la venta cierra de verdad, con lo mismo guardado en la base.
        r_venta = self.cliente.post("/ventas", json={
            "carrito": [{"id": 3, "nombre": "Aceite 1000 ml", "cantidad": 1,
                         "precio": 5000.0, "tipo": "unidad", "unidad": "unidad"}],
            "pago": _cuerpo_de_pago(pago),
        })
        self.assertEqual(r_venta.status_code, 201, r_venta.text)
        venta_id = r_venta.json()["venta_id"]
        self.assertEqual(r_venta.json()["vuelto_texto"], "0.20 USD + 20.00 CUP")

        fila = self._fila_de_venta(venta_id)
        self.assertEqual(fila["moneda_pago"], "USD")
        self.assertAlmostEqual(fila["tasa_cambio"], 400.0)
        self.assertEqual(fila["metodo_pago_real"], "Mixto")
        self.assertAlmostEqual(fila["monto_efectivo"], 280.0)
        self.assertAlmostEqual(fila["monto_transferencia"], 0.0)
        self.assertAlmostEqual(fila["monto_divisa_neto"], 12.0 - 0.2)
        self.assertAlmostEqual(self._salida_efectivo_de(venta_id), 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
