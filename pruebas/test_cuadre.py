"""El cuadre del corte de caja y el cierre del día.

Dos cosas se comprueban aquí, y las dos son las que hacen que la pantalla de
Corte sirva para algo:

- Que la cadena de sumas y restas **cuadre con su propio total**. Si la
  pantalla dice que deberían quedar 3 900 y las líneas de arriba no suman
  3 900, la explicación no explica nada.
- Que la cadena y la lista de movimientos **cuenten lo mismo**. Una venta de
  divisa deja rastro en dos tablas, y contarla dos veces sería el error más
  fácil de cometer y el más difícil de ver.

Y una tercera, que es una regla del negocio: **nada se arrastra de un día
para otro**. La gaveta se vacía todas las noches.
"""

import datetime
import os
import shutil
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import base  # noqa: E402  (tiene que ir después de tocar sys.path)

from lddl import caja, cierres, cuadre, rutas, sesion, usuarios  # noqa: E402

HOY = datetime.date.today().isoformat()
MANANA = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()


def _suma_de_la_cadena(cadena):
    """Lo que suman las líneas tal y como la pantalla las enseña."""
    total = 0.0
    for linea in cadena:
        if linea["signo"] == "-":
            total -= linea["monto"]
        else:
            total += linea["monto"]
    return round(total, 2)


def _linea(cadena, clave):
    for linea in cadena:
        if linea["clave"] == clave:
            return linea
    return None


class SobreUnaCopia(unittest.TestCase):
    """Cada prueba con su copia de la base y su sesión abierta."""

    def setUp(self):
        self.temporal = base.carpeta_con_copia()
        usuarios.crear_usuario("Cajera", usuarios.ADMIN, "1234")
        sesion.entrar("Cajera", "1234")

    def tearDown(self):
        sesion.salir()
        rutas.fijar_directorio_base(None)
        shutil.rmtree(self.temporal, ignore_errors=True)


class LaCadenaDelCup(SobreUnaCopia):

    def test_las_lineas_suman_exactamente_lo_esperado(self):
        caja.guardar_fondo_por_fecha(HOY, 5000.0)
        caja.registrar_entrada_efectivo("CUP", 1500.0, "Aporte del dueño")
        caja.registrar_salida_efectivo("CUP", 600.0, "Compra de bolsas")
        caja.registrar_operacion_cambio("compra", "USD", 10.0, 200.0)

        cup = cuadre.armar_cuadre(HOY)["CUP"]
        self.assertAlmostEqual(_suma_de_la_cadena(cup["cadena"]), cup["esperado"])
        self.assertAlmostEqual(cup["esperado"], 5000.0 + 1500.0 - 600.0 - 2000.0)

    def test_el_fondo_se_queda_en_la_cadena_aunque_sea_cero(self):
        """A media mañana, ver el fondo en blanco es justo lo que hace falta."""
        cadena = cuadre.armar_cuadre(HOY)["CUP"]["cadena"]
        fondo = _linea(cadena, "fondo")
        self.assertIsNotNone(fondo)
        self.assertEqual(fondo["monto"], 0.0)
        self.assertEqual(fondo["cuenta"], "todavía sin poner")

    def test_el_cobro_de_una_deuda_no_se_cuenta_por_las_dos_tablas(self):
        """El apunte 'Pago de deuda #' es rastro de un cobro, no otra entrada."""
        caja.registrar_entrada_efectivo("CUP", 300.0, "Pago de deuda #99 - Efectivo CUP")
        cadena = cuadre.armar_cuadre(HOY)["CUP"]["cadena"]
        self.assertIsNone(_linea(cadena, "entradas"))


class LaCadenaDeLasDivisas(SobreUnaCopia):

    def test_lo_esperado_es_el_saldo_que_guarda_el_programa(self):
        caja.registrar_operacion_cambio("compra", "USD", 40.0, 200.0)
        usd = cuadre.armar_cuadre(HOY)["USD"]
        self.assertAlmostEqual(usd["esperado"], 40.0)
        self.assertAlmostEqual(
            usd["esperado"], caja.obtener_saldo_divisas(HOY).get("USD", 0.0))

    def test_sin_desfase_no_aparece_la_linea_de_ajustes(self):
        caja.registrar_operacion_cambio("compra", "EUR", 25.0, 210.0)
        cadena = cuadre.armar_cuadre(HOY)["EUR"]["cadena"]
        self.assertIsNone(_linea(cadena, "ajuste"))
        self.assertAlmostEqual(_suma_de_la_cadena(cadena), 25.0)

    def test_vender_divisa_la_saca_de_la_gaveta(self):
        caja.registrar_operacion_cambio("compra", "USD", 40.0, 200.0)
        caja.registrar_operacion_cambio("venta", "USD", 15.0, 210.0)
        usd = cuadre.armar_cuadre(HOY)["USD"]
        self.assertAlmostEqual(usd["esperado"], 25.0)
        self.assertAlmostEqual(_linea(usd["cadena"], "venta_divisa")["monto"], 15.0)


class LaCadenaYLaListaCuentanLoMismo(SobreUnaCopia):

    def test_la_venta_de_divisa_sale_una_sola_vez(self):
        """Deja un apunte en entradas_efectivo además de su propia fila.

        Si la lista lo enseñara dos veces, o la cadena lo sumara dos veces,
        el corte diría que hay más dinero del que hay.
        """
        caja.registrar_operacion_cambio("compra", "USD", 40.0, 200.0)
        caja.registrar_operacion_cambio("venta", "USD", 10.0, 210.0)

        movimientos = caja.obtener_movimientos_del_dia(HOY)
        ventas = [m for m in movimientos if m["tipo"] == "Venta de divisa"]
        self.assertEqual(len(ventas), 1)
        self.assertAlmostEqual(ventas[0]["monto"], 2100.0)
        self.assertAlmostEqual(ventas[0]["monto_2"], -10.0)
        self.assertEqual([m["concepto"] for m in movimientos].count(
            ventas[0]["concepto"]), 1)

        cadena = cuadre.armar_cuadre(HOY)["CUP"]["cadena"]
        self.assertAlmostEqual(_linea(cadena, "venta_divisa")["monto"], 2100.0)
        self.assertIsNone(_linea(cadena, "entradas"))

    def test_la_compra_de_divisa_sale_como_una_linea_con_sus_dos_lados(self):
        caja.registrar_operacion_cambio("compra", "USD", 10.0, 200.0)
        compra = caja.obtener_movimientos_del_dia(HOY)[0]
        self.assertEqual(compra["tipo"], "Compra de divisa")
        self.assertAlmostEqual(compra["monto"], -2000.0)
        self.assertEqual(compra["moneda"], "CUP")
        self.assertAlmostEqual(compra["monto_2"], 10.0)
        self.assertEqual(compra["moneda_2"], "USD")

    def test_las_entradas_y_salidas_a_mano_llevan_su_signo(self):
        caja.registrar_entrada_efectivo("CUP", 500.0, "Aporte")
        caja.registrar_salida_efectivo("CUP", 200.0, "Mensajero")
        por_concepto = {m["concepto"]: m for m in caja.obtener_movimientos_del_dia(HOY)}
        self.assertAlmostEqual(por_concepto["Aporte"]["monto"], 500.0)
        self.assertAlmostEqual(por_concepto["Mensajero"]["monto"], -200.0)

    def test_quien_lo_hizo_viaja_con_el_movimiento(self):
        caja.registrar_entrada_efectivo("CUP", 100.0, "Aporte")
        self.assertEqual(caja.obtener_movimientos_del_dia(HOY)[0]["usuario"], "Cajera")


class NadaSeArrastra(SobreUnaCopia):

    def test_el_dia_siguiente_empieza_en_cero(self):
        caja.guardar_fondo_por_fecha(HOY, 5000.0)
        caja.registrar_operacion_cambio("compra", "USD", 40.0, 200.0)

        manana = cuadre.armar_cuadre(MANANA)
        self.assertEqual(manana["CUP"]["esperado"], 0.0)
        self.assertEqual(manana["USD"]["esperado"], 0.0)
        self.assertEqual(manana["EUR"]["esperado"], 0.0)
        self.assertEqual(caja.obtener_movimientos_del_dia(MANANA), [])

    def test_manana_solo_queda_la_linea_del_fondo_sin_poner(self):
        cadena = cuadre.armar_cuadre(MANANA)["CUP"]["cadena"]
        self.assertEqual([ln["clave"] for ln in cadena], ["fondo"])


class ElCierreDelDia(SobreUnaCopia):

    def _dia_con_movimiento(self):
        caja.guardar_fondo_por_fecha(HOY, 5000.0)
        caja.registrar_entrada_efectivo("CUP", 1000.0, "Aporte")
        caja.registrar_operacion_cambio("compra", "USD", 20.0, 200.0)

    def test_guarda_lo_esperado_lo_contado_y_la_diferencia(self):
        self._dia_con_movimiento()
        esperado = cuadre.armar_cuadre(HOY)["CUP"]["esperado"]

        exito, _ = cierres.cerrar_caja(HOY, {"CUP": esperado - 120.0, "USD": 20.0})
        self.assertTrue(exito)

        cierre = cierres.obtener_cierre(HOY)
        self.assertAlmostEqual(cierre["esperado"]["CUP"], esperado)
        self.assertAlmostEqual(cierre["diferencia"]["CUP"], -120.0)
        self.assertAlmostEqual(cierre["diferencia"]["USD"], 0.0)
        self.assertEqual(cierre["usuario"], "Cajera")
        self.assertEqual(len(cierre["hora"]), 5)

    def test_lo_esperado_lo_calcula_el_servidor_no_quien_cierra(self):
        """Mandar una cifra esperada que convenga no cambia nada."""
        self._dia_con_movimiento()
        esperado = cuadre.armar_cuadre(HOY)["CUP"]["esperado"]
        cierres.cerrar_caja(HOY, {"CUP": 0.0, "USD": 0.0, "EUR": 0.0})
        self.assertAlmostEqual(
            cierres.obtener_cierre(HOY)["esperado"]["CUP"], esperado)

    def test_el_mensaje_dice_si_cuadro_o_cuanto_falta(self):
        self._dia_con_movimiento()
        esperado = cuadre.armar_cuadre(HOY)["CUP"]["esperado"]

        _, mensaje = cierres.cerrar_caja(HOY, {"CUP": esperado, "USD": 20.0})
        self.assertIn("cuadra", mensaje)

        _, mensaje = cierres.cerrar_caja(HOY, {"CUP": esperado - 50.0, "USD": 20.0})
        self.assertIn("-50.00", mensaje)

    def test_cerrar_dos_veces_sustituye_la_foto(self):
        self._dia_con_movimiento()
        cierres.cerrar_caja(HOY, {"CUP": 100.0})
        cierres.cerrar_caja(HOY, {"CUP": 200.0})
        self.assertEqual(len(cierres.ultimos_cierres(10)), 1)
        self.assertAlmostEqual(cierres.obtener_cierre(HOY)["contado"]["CUP"], 200.0)

    def test_reabrir_borra_el_cierre(self):
        self._dia_con_movimiento()
        cierres.cerrar_caja(HOY, {"CUP": 100.0})
        exito, _ = cierres.reabrir_caja(HOY)
        self.assertTrue(exito)
        self.assertIsNone(cierres.obtener_cierre(HOY))

    def test_reabrir_un_dia_que_no_estaba_cerrado_avisa(self):
        exito, mensaje = cierres.reabrir_caja(HOY)
        self.assertFalse(exito)
        self.assertIn("no estaba cerrado", mensaje)

    def test_un_dia_sin_cerrar_no_tiene_cierre(self):
        self.assertIsNone(cierres.obtener_cierre(HOY))

    def test_avisa_de_los_movimientos_llegados_despues_de_cerrar(self):
        """Cerrar no traba nada, así que la venta de las 20:30 es posible.

        La hora se pone a mano: dentro de la misma prueba el cierre y el
        movimiento caen en el mismo segundo, y no habría nada que detectar.
        """
        self._dia_con_movimiento()
        cierres.cerrar_caja(HOY, {"CUP": 100.0})
        self.assertEqual(cierres.obtener_cierre(HOY)["movimientos_despues"], 0)

        caja.registrar_entrada_efectivo("CUP", 300.0, "Venta tardía")
        with rutas.transaccion() as (_, cursor):
            cursor.execute(
                "UPDATE entradas_efectivo SET fecha = ? WHERE descripcion = ?",
                (f"{HOY} 23:59:00", "Venta tardía"))
        self.assertEqual(cierres.obtener_cierre(HOY)["movimientos_despues"], 1)


if __name__ == "__main__":
    unittest.main()
