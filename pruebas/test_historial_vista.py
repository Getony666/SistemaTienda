"""Lo que el historial enseña por pantalla: signo, concepto, totales y detalle.

Estas pruebas no miran cuentas -de eso se encargan las de cálculo-, sino que
lo que llega a la pantalla se pueda leer: que una salida de caja diga que el
dinero sale, que una deuda a medio cobrar diga cuánto lleva abonado, y que el
filtro de método de pago no deje pasar lo que no se cobró de ninguna manera.

    python -m unittest discover -s pruebas -v
"""

import os
import shutil
import sqlite3
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import base  # noqa: E402
from lddl import rutas  # noqa: E402


class SobreUnaCopia(unittest.TestCase):

    def setUp(self):
        self.temporal = base.carpeta_con_copia("mitienda-vista-")
        rutas.fijar_directorio_base(self.temporal)

    def tearDown(self):
        rutas.fijar_directorio_base(None)
        shutil.rmtree(self.temporal, ignore_errors=True)

    def conexion(self):
        return sqlite3.connect(os.path.join(self.temporal, "tienda.db"))

    def un_producto(self):
        con = self.conexion()
        try:
            fila = con.execute(
                "SELECT id, nombre FROM productos WHERE stock >= 1 LIMIT 1").fetchone()
        finally:
            con.close()
        if not fila:
            self.skipTest("hace falta un producto en la base")
        return fila

    def vender(self, producto_id, total=100, metodo_real="Efectivo", utilidad=30):
        con = self.conexion()
        try:
            cur = con.cursor()
            cur.execute(
                "INSERT INTO ventas (fecha, total, metodo_pago, es_deuda, pagada,"
                " es_mensajeria, metodo_pago_real, cancelada, utilidad, moneda_pago,"
                " tasa_cambio, pago_texto, vuelto_texto)"
                " VALUES ('2026-09-09 10:00:00', ?, 'Efectivo', 0, 1, 0, ?, 0, ?,"
                " 'CUP', 1.0, '200.00 CUP', '100.00 CUP')",
                (total, metodo_real, utilidad))
            venta_id = cur.lastrowid
            cur.execute(
                "INSERT INTO detalles_venta (venta_id, producto_id, cantidad, precio_unitario)"
                " VALUES (?, ?, 2, ?)", (venta_id, producto_id, total / 2))
            con.commit()
            return venta_id
        finally:
            con.close()

    def fiar(self, producto_id, total=1000, cliente="Mariela la del CDR", abonos=()):
        """Una deuda, opcionalmente con abonos ya cobrados."""
        con = self.conexion()
        try:
            cur = con.cursor()
            abonado = sum(abonos)
            cur.execute(
                "INSERT INTO ventas (fecha, total, metodo_pago, es_deuda, pagada,"
                " saldo_pendiente, es_mensajeria, cancelada, observaciones)"
                " VALUES ('2026-09-09 11:00:00', ?, 'Deuda', 1, 0, ?, 0, 0, ?)",
                (total, total - abonado, cliente))
            deuda_id = cur.lastrowid
            cur.execute(
                "INSERT INTO detalles_venta (venta_id, producto_id, cantidad, precio_unitario)"
                " VALUES (?, ?, 1, ?)", (deuda_id, producto_id, total))
            for monto in abonos:
                cur.execute(
                    "INSERT INTO cobros_deudas (venta_id, fecha, monto, metodo_pago,"
                    " moneda, tasa, monto_cup)"
                    " VALUES (?, '2026-09-10 09:00:00', ?, 'Efectivo', 'CUP', 1.0, ?)",
                    (deuda_id, monto, monto))
            con.commit()
            return deuda_id
        finally:
            con.close()

    def mover_caja(self, tabla, monto, descripcion):
        con = self.conexion()
        try:
            con.execute(
                f"INSERT INTO {tabla} (fecha, moneda, monto, descripcion, usuario)"
                " VALUES ('2026-09-09 12:00:00', 'CUP', ?, ?, 'Getony')",
                (monto, descripcion))
            con.commit()
        finally:
            con.close()

    def cambiar_divisa(self, tipo_op="compra", cantidad=100, tasa=420):
        con = self.conexion()
        try:
            cur = con.cursor()
            cur.execute(
                "INSERT INTO operaciones_cambio (fecha, tipo, moneda, cantidad, tasa, monto_cup)"
                " VALUES ('2026-09-09 13:00:00', ?, 'USD', ?, ?, ?)",
                (tipo_op, cantidad, tasa, cantidad * tasa))
            con.commit()
            return cur.lastrowid
        finally:
            con.close()

    def por_id(self, registros, id_reg, tipo=None):
        for r in registros:
            if r["id"] == id_reg and (tipo is None or r["tipo"] == tipo):
                return r
        self.fail(f"no salió el registro {id_reg}")


class ElSignoDelDinero(SobreUnaCopia):
    """Lo que entra y lo que sale no puede verse igual."""

    def test_una_venta_entra(self):
        from lddl.ventas_datos import obtener_ventas

        id_p, _ = self.un_producto()
        venta = self.vender(id_p)
        self.assertEqual(self.por_id(obtener_ventas(), venta, "Venta")["signo"], "entra")

    def test_una_salida_de_caja_sale(self):
        from lddl.ventas_datos import obtener_ventas

        self.mover_caja("salidas_efectivo", 12500, "Pago al proveedor")
        registros = [r for r in obtener_ventas() if r["tipo"] == "Salida de efectivo"]
        self.assertTrue(registros)
        self.assertEqual(registros[0]["signo"], "sale")

    def test_una_entrada_de_caja_entra(self):
        from lddl.ventas_datos import obtener_ventas

        self.mover_caja("entradas_efectivo", 5000, "Fondo del día")
        registros = [r for r in obtener_ventas() if r["tipo"] == "Entrada de efectivo"]
        self.assertTrue(registros)
        self.assertEqual(registros[0]["signo"], "entra")

    def test_una_deuda_no_mueve_dinero_todavia(self):
        """Lo fiado ni entró ni salió: está pendiente."""
        from lddl.ventas_datos import obtener_ventas

        id_p, _ = self.un_producto()
        deuda = self.fiar(id_p)
        self.assertEqual(self.por_id(obtener_ventas(), deuda, "Deuda")["signo"], "neutro")

    def test_comprar_divisa_la_mete_y_venderla_la_saca(self):
        from lddl.ventas_datos import obtener_ventas

        compra = self.cambiar_divisa("compra")
        venta = self.cambiar_divisa("venta")
        registros = [r for r in obtener_ventas() if r["tipo"] == "Cambio de Divisa"]
        self.assertEqual(self.por_id(registros, compra)["signo"], "entra")
        self.assertEqual(self.por_id(registros, venta)["signo"], "sale")

    def test_una_merma_sale(self):
        from lddl.inventario import registrar_merma_de_carrito
        from lddl.ventas_datos import obtener_ventas

        id_p, _ = self.un_producto()
        self.assertTrue(registrar_merma_de_carrito([{"producto_id": id_p, "cantidad": 1}])[0])
        mermas = [r for r in obtener_ventas() if r["tipo"] == "Merma"]
        self.assertTrue(mermas)
        self.assertEqual(mermas[0]["signo"], "sale")


class LasDeudas(SobreUnaCopia):

    def test_dice_cuanto_lleva_abonado(self):
        from lddl.ventas_datos import obtener_ventas

        id_p, _ = self.un_producto()
        deuda = self.fiar(id_p, total=1000, abonos=(200, 300))
        registro = self.por_id(obtener_ventas(), deuda, "Deuda")
        self.assertEqual(registro["abonado"], 500)
        self.assertEqual(registro["total_deuda"], 1000)
        self.assertEqual(registro["monto"], 500, "la columna enseña lo que falta")

    def test_el_concepto_es_el_cliente_y_no_los_productos(self):
        """Lo que se busca de una deuda es de quién es."""
        from lddl.ventas_datos import obtener_ventas

        id_p, _ = self.un_producto()
        deuda = self.fiar(id_p, cliente="Yordanis el de la esquina")
        registro = self.por_id(obtener_ventas(), deuda, "Deuda")
        self.assertEqual(registro["concepto"], "Yordanis el de la esquina")
        self.assertIn("Debe", registro["subconcepto"])

    def test_el_registro_de_abonos_no_se_confunde_con_un_nombre(self):
        """Cada cobro parcial pega su línea a la observación de la venta.

        En una deuda con abonos ese campo deja de ser el nombre del cliente y
        pasa a ser un registro de pagos; encabezar la fila con él dejaba una
        línea ilegible de trescientos caracteres.
        """
        from lddl.ventas_datos import obtener_ventas

        id_p, nombre = self.un_producto()
        deuda = self.fiar(
            id_p, total=1220,
            cliente="| Pago parcial de 220.00 CUP, saldo restante 1000.00 CUP",
            abonos=(220,))
        registro = self.por_id(obtener_ventas(), deuda, "Deuda")
        self.assertNotIn("Pago parcial", registro["concepto"])
        self.assertEqual(registro["concepto"], nombre, "se cae a los productos")

    def test_sin_abonos_lo_dice(self):
        from lddl.ventas_datos import obtener_ventas

        id_p, _ = self.un_producto()
        deuda = self.fiar(id_p)
        self.assertIn("sin abonos", self.por_id(obtener_ventas(), deuda, "Deuda")["subconcepto"])


class ElFiltroDeMetodo(SobreUnaCopia):
    """Antes dejaba pasar lo que no se cobró de ninguna manera."""

    def test_transferencia_no_arrastra_mermas_ni_cambios(self):
        from lddl.inventario import registrar_merma_de_carrito
        from lddl.ventas_datos import obtener_ventas

        id_p, _ = self.un_producto()
        self.vender(id_p, metodo_real="Transferencia")
        self.cambiar_divisa()
        self.mover_caja("salidas_efectivo", 500, "Compra de bolsas")
        registrar_merma_de_carrito([{"producto_id": id_p, "cantidad": 1}])

        tipos = {r["tipo"] for r in obtener_ventas(filtro_metodo="transferencia")}
        self.assertNotIn("Merma", tipos)
        self.assertNotIn("Cambio de Divisa", tipos)
        self.assertNotIn("Salida de efectivo", tipos)
        self.assertIn("Venta", tipos)

    def test_efectivo_si_trae_los_movimientos_de_caja(self):
        """Una salida de caja es efectivo, y con ese filtro tiene que salir."""
        from lddl.ventas_datos import obtener_ventas

        self.mover_caja("salidas_efectivo", 500, "Compra de bolsas")
        self.cambiar_divisa()
        tipos = {r["tipo"] for r in obtener_ventas(filtro_metodo="efectivo")}
        self.assertIn("Salida de efectivo", tipos)
        self.assertIn("Cambio de Divisa", tipos)

    def test_sin_filtro_sigue_saliendo_todo(self):
        from lddl.inventario import registrar_merma_de_carrito
        from lddl.ventas_datos import obtener_ventas

        id_p, _ = self.un_producto()
        registrar_merma_de_carrito([{"producto_id": id_p, "cantidad": 1}])
        self.assertIn("Merma", {r["tipo"] for r in obtener_ventas(filtro_metodo="todos")})


class ElRecorte(SobreUnaCopia):

    def test_limite_devuelve_los_mas_recientes(self):
        from lddl.ventas_datos import obtener_ventas

        id_p, _ = self.un_producto()
        for _ in range(5):
            self.vender(id_p)
        todos = obtener_ventas()
        primeros = obtener_ventas(limite=2)
        self.assertEqual(len(primeros), 2)
        self.assertEqual([r["id"] for r in primeros], [r["id"] for r in todos[:2]])

    def test_desde_salta_los_ya_vistos(self):
        from lddl.ventas_datos import obtener_ventas

        id_p, _ = self.un_producto()
        for _ in range(5):
            self.vender(id_p)
        todos = obtener_ventas()
        segunda_tanda = obtener_ventas(limite=2, desde=2)
        self.assertEqual([r["id"] for r in segunda_tanda], [r["id"] for r in todos[2:4]])

    def test_sin_limite_sigue_viniendo_todo(self):
        from lddl.ventas_datos import obtener_ventas

        id_p, _ = self.un_producto()
        for _ in range(4):
            self.vender(id_p)
        self.assertGreaterEqual(len(obtener_ventas()), 4)


class LaBusqueda(SobreUnaCopia):

    def test_encuentra_al_cliente_de_una_deuda(self):
        from lddl.ventas_datos import obtener_ventas

        id_p, _ = self.un_producto()
        deuda = self.fiar(id_p, cliente="Yordanis el de la esquina")
        self.vender(id_p)
        ids = {r["id"] for r in obtener_ventas(buscar="yordanis")}
        self.assertIn(deuda, ids)

    def test_no_le_importan_las_tildes(self):
        from lddl.ventas_datos import obtener_ventas

        id_p, _ = self.un_producto()
        deuda = self.fiar(id_p, cliente="Ramón el del camión")
        self.assertIn(deuda, {r["id"] for r in obtener_ventas(buscar="ramon")})
        self.assertIn(deuda, {r["id"] for r in obtener_ventas(buscar="RAMÓN")})

    def test_lo_que_no_coincide_se_queda_fuera(self):
        from lddl.ventas_datos import obtener_ventas

        id_p, _ = self.un_producto()
        self.fiar(id_p, cliente="Mariela")
        self.assertEqual(obtener_ventas(buscar="zzzz-no-existe"), [])

    def test_encuentra_por_la_descripcion_de_un_movimiento_de_caja(self):
        from lddl.ventas_datos import obtener_ventas

        self.mover_caja("salidas_efectivo", 800, "Compra de nailon y bolsas")
        encontrados = obtener_ventas(buscar="nailon")
        self.assertEqual(len(encontrados), 1)
        self.assertEqual(encontrados[0]["tipo"], "Salida de efectivo")


class ElResumen(SobreUnaCopia):
    """La base de pruebas ya trae movimientos suyos, así que se mide la
    diferencia que introduce cada prueba y no el total absoluto."""

    def test_separa_lo_que_entro_de_lo_que_salio(self):
        from lddl.historial_vista import resumen_historial

        antes = resumen_historial()
        id_p, _ = self.un_producto()
        self.vender(id_p, total=1000, utilidad=250)
        self.mover_caja("salidas_efectivo", 400, "Bolsas")
        self.mover_caja("entradas_efectivo", 100, "Devolución")

        ahora = resumen_historial()
        self.assertEqual(ahora["entro"] - antes["entro"], 1100)
        self.assertEqual(ahora["salio"] - antes["salio"], 400)
        self.assertEqual(ahora["ganancia"] - antes["ganancia"], 250)

    def test_lo_fiado_va_a_por_cobrar_y_no_a_lo_que_entro(self):
        from lddl.historial_vista import resumen_historial

        antes = resumen_historial()
        id_p, _ = self.un_producto()
        self.fiar(id_p, total=1000, abonos=(200,))
        ahora = resumen_historial()
        self.assertEqual(ahora["por_cobrar"] - antes["por_cobrar"], 800)
        self.assertEqual(ahora["entro"], antes["entro"], "lo fiado no entró a la caja")

    def test_la_divisa_va_aparte_de_los_pesos(self):
        from lddl.historial_vista import resumen_historial

        antes = resumen_historial()
        self.cambiar_divisa("compra", cantidad=100)
        ahora = resumen_historial()
        self.assertEqual(ahora["divisas"].get("USD"), 100)
        self.assertEqual(ahora["entro"], antes["entro"], "los USD no se suman a los CUP")

    def test_resume_el_filtro_entero_y_no_la_pagina(self):
        from lddl.historial_vista import resumen_historial

        antes = resumen_historial()["registros"]
        id_p, _ = self.un_producto()
        for _ in range(6):
            self.vender(id_p, total=100, utilidad=0)
        self.assertEqual(resumen_historial()["registros"] - antes, 6)

    def test_respeta_la_busqueda(self):
        from lddl.historial_vista import resumen_historial

        self.mover_caja("salidas_efectivo", 800, "Compra de nailon")
        self.mover_caja("salidas_efectivo", 300, "Otra cosa")
        self.assertEqual(resumen_historial(buscar="nailon")["salio"], 800)


class ElDetalle(SobreUnaCopia):

    def test_una_venta_enseña_sus_lineas_y_su_ganancia(self):
        from lddl.historial_vista import detalle_de_registro

        id_p, nombre = self.un_producto()
        venta = self.vender(id_p, total=1000, utilidad=250)
        detalle = detalle_de_registro("Venta", venta)

        self.assertIn(str(venta), detalle["titulo"])
        nombres = [s["nombre"] for s in detalle["secciones"]]
        self.assertIn("Qué se llevó", nombres)
        lineas = next(s for s in detalle["secciones"] if s["nombre"] == "Qué se llevó")
        self.assertEqual(lineas["filas"][0]["texto"], nombre)
        self.assertTrue(lineas["filas"][-1]["fuerte"], "la última línea es el total")

        cobro = next(s for s in detalle["secciones"] if s["nombre"] == "El cobro")
        etiquetas = [f["texto"] for f in cobro["filas"]]
        self.assertIn("Ganancia de esta venta", etiquetas)

    def test_el_detalle_no_habla_en_nombres_de_columna(self):
        """Lo que se lee tiene que ser español, no el esquema de la base."""
        from lddl.historial_vista import detalle_de_registro

        id_p, _ = self.un_producto()
        detalle = detalle_de_registro("Venta", self.vender(id_p))
        crudo = str(detalle)
        for fea in ("es_deuda", "metodo_pago_real", "pago_texto", "saldo_pendiente",
                    "es_mensajeria", "detalle_extra"):
            self.assertNotIn(fea, crudo, f"'{fea}' no puede salir por pantalla")

    def test_una_deuda_enseña_sus_abonos_uno_a_uno(self):
        from lddl.historial_vista import detalle_de_registro

        id_p, _ = self.un_producto()
        deuda = self.fiar(id_p, total=1000, abonos=(200, 300))
        detalle = detalle_de_registro("Deuda", deuda)

        abonos = next(s for s in detalle["secciones"] if s["nombre"] == "Abonos")
        self.assertEqual(len(abonos["filas"]), 2)
        resumen = next(s for s in detalle["secciones"] if s["nombre"] == "La deuda")
        etiquetas = [f["texto"] for f in resumen["filas"]]
        self.assertIn("Lleva abonado", etiquetas)
        self.assertIn("Falta", etiquetas)

    def test_un_movimiento_de_caja_dice_hacia_donde_va_el_dinero(self):
        from lddl.historial_vista import detalle_de_registro
        from lddl.ventas_datos import obtener_ventas

        self.mover_caja("salidas_efectivo", 800, "Compra de nailon")
        registro = [r for r in obtener_ventas() if r["tipo"] == "Salida de efectivo"][0]
        detalle = detalle_de_registro("Salida de efectivo", registro["id"])
        etiquetas = [f["texto"] for s in detalle["secciones"] for f in s["filas"]]
        self.assertIn("Sale de la caja", etiquetas)

    def test_un_cambio_de_divisa_enseña_la_tasa(self):
        from lddl.historial_vista import detalle_de_registro

        cambio = self.cambiar_divisa("compra", cantidad=100, tasa=420)
        detalle = detalle_de_registro("Cambio de Divisa", cambio)
        etiquetas = [f["texto"] for s in detalle["secciones"] for f in s["filas"]]
        self.assertIn("Tasa", etiquetas)

    def test_las_casillas_vacias_no_ocupan_linea(self):
        """Antes salían filas en blanco porque el campo estaba vacío."""
        from lddl.historial_vista import detalle_de_registro

        id_p, _ = self.un_producto()
        con = self.conexion()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO ventas (fecha, total, metodo_pago, es_deuda, pagada,"
            " es_mensajeria, metodo_pago_real, cancelada, pago_texto, vuelto_texto,"
            " observaciones) VALUES ('2026-09-09 10:00:00', 500, 'Efectivo', 0, 1, 0,"
            " 'Efectivo', 0, '', '', '')")
        venta = cur.lastrowid
        cur.execute("INSERT INTO detalles_venta (venta_id, producto_id, cantidad,"
                    " precio_unitario) VALUES (?, ?, 1, 500)", (venta, id_p))
        con.commit()
        con.close()

        detalle = detalle_de_registro("Venta", venta)
        for seccion in detalle["secciones"]:
            for fila in seccion["filas"]:
                self.assertTrue(str(fila.get("derecha", "x")).strip(),
                                f"fila vacía: {fila}")

    def test_un_registro_que_no_existe_no_devuelve_nada(self):
        from lddl.historial_vista import detalle_de_registro

        self.assertIsNone(detalle_de_registro("Venta", 999999))


class PorLaApi(SobreUnaCopia):
    """Las dos rutas nuevas, tal como las llama la pantalla."""

    def cliente(self):
        from fastapi.testclient import TestClient

        from lddl.api import app
        return TestClient(app)

    def test_el_resumen_contesta_con_las_cifras(self):
        id_p, _ = self.un_producto()
        self.vender(id_p, total=1000, utilidad=250)
        with self.cliente() as cliente:
            r = cliente.get("/historial/resumen")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["entro"], 1000)

    def test_el_detalle_contesta_con_secciones(self):
        id_p, _ = self.un_producto()
        venta = self.vender(id_p)
        with self.cliente() as cliente:
            r = cliente.get("/historial/detalle", params={"tipo": "Venta", "id": venta})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["secciones"])

    def test_el_detalle_de_lo_que_no_existe_es_un_404(self):
        with self.cliente() as cliente:
            r = cliente.get("/historial/detalle", params={"tipo": "Venta", "id": 999999})
        self.assertEqual(r.status_code, 404)

    def test_la_lista_acepta_limite_y_desde(self):
        id_p, _ = self.un_producto()
        for _ in range(5):
            self.vender(id_p)
        with self.cliente() as cliente:
            r = cliente.get("/ventas", params={"limite": 2, "desde": 1})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 2)

    def test_resumen_rechaza_una_fecha_mal_escrita(self):
        with self.cliente() as cliente:
            self.assertEqual(
                cliente.get("/historial/resumen", params={"fecha": "09-2026-10"}).status_code,
                422)


if __name__ == "__main__":
    unittest.main(verbosity=2)
