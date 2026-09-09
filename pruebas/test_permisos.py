"""Usuarios, roles y permisos.

Lo que se comprueba aquí, y por qué:

- Que el PIN no se pueda leer de la base.
- Que quien no tiene permiso NO pueda, y que eso lo diga la API, no la
  pantalla: esconder un botón no impide nada.
- Que no haya forma de dejar la tienda sin nadie capaz de administrarla.

Todo sobre una COPIA de la base de pruebas.

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
from lddl import rutas, sesion, usuarios  # noqa: E402
from lddl.esquema import preparar_base  # noqa: E402

try:
    from fastapi.testclient import TestClient
    from lddl.api import app
    HAY_API = True
except Exception:
    HAY_API = False


class SobreUnaCopia(unittest.TestCase):
    """Cada prueba arranca con base limpia, tablas al día y sin nadie dentro."""

    def setUp(self):
        self.temporal = base.carpeta_con_copia("mitienda-perm-")
        rutas.fijar_directorio_base(self.temporal)
        preparar_base()
        sesion.salir()

    def tearDown(self):
        sesion.salir()
        rutas.fijar_directorio_base(None)
        shutil.rmtree(self.temporal, ignore_errors=True)

    def consultar(self, sql, parametros=()):
        con = sqlite3.connect(os.path.join(self.temporal, "tienda.db"))
        try:
            return con.execute(sql, parametros).fetchall()
        finally:
            con.close()

    def crear(self, nombre, rol, pin="1234"):
        exito, mensaje = usuarios.crear_usuario(nombre, rol, pin)
        self.assertTrue(exito, mensaje)
        return usuarios.buscar_por_nombre(nombre)["id"]


class ElPin(SobreUnaCopia):

    def test_no_se_guarda_tal_cual(self):
        self.crear("Ana", usuarios.ADMIN, "9876")
        guardado = self.consultar("SELECT pin FROM usuarios WHERE nombre='Ana'")[0][0]
        self.assertNotIn("9876", guardado)
        self.assertIn("$", guardado, "debe ser sal$huella")

    def test_dos_usuarios_con_el_mismo_pin_no_se_parecen(self):
        """Sin sal, dos PIN iguales darian la misma huella y se notaria."""
        self.crear("Ana", usuarios.ADMIN, "1111")
        self.crear("Luis", usuarios.EMPLEADO, "1111")
        huellas = [f[0] for f in self.consultar("SELECT pin FROM usuarios")]
        self.assertNotEqual(huellas[0], huellas[1])

    def test_el_pin_correcto_entra_y_el_de_al_lado_no(self):
        self.crear("Ana", usuarios.ADMIN, "4321")
        self.assertTrue(sesion.entrar("Ana", "4321")[0])
        sesion.salir()
        self.assertFalse(sesion.entrar("Ana", "4322")[0])

    def test_un_pin_corto_se_rechaza(self):
        exito, motivo = usuarios.crear_usuario("Ana", usuarios.ADMIN, "12")
        self.assertFalse(exito)
        self.assertIn("4", motivo)

    def test_el_error_no_dice_si_fallo_el_usuario_o_el_pin(self):
        """Decir cual de los dos fallo es regalar media contrasena."""
        self.crear("Ana", usuarios.ADMIN, "4321")
        _, sin_usuario = sesion.entrar("Nadie", "4321")
        _, mal_pin = sesion.entrar("Ana", "0000")
        self.assertEqual(sin_usuario, mal_pin)


class LosPermisosPorDefecto(SobreUnaCopia):

    def test_admin_lo_puede_todo(self):
        self.assertEqual(usuarios.permisos_de(usuarios.ADMIN), set(usuarios.CLAVES))

    def test_boss_puede_todo_menos_gestionar(self):
        permisos = usuarios.permisos_de(usuarios.BOSS)
        self.assertNotIn("gestionar_usuarios", permisos)
        self.assertEqual(permisos, set(usuarios.CLAVES) - {"gestionar_usuarios"})

    def test_el_empleado_no_toca_los_productos_ni_borra_del_historial(self):
        """Lo que pidio el dueno, tal cual."""
        permisos = usuarios.permisos_de(usuarios.EMPLEADO)
        for prohibido in ("crear_producto", "actualizar_producto",
                          "eliminar_producto", "eliminar_historial"):
            self.assertNotIn(prohibido, permisos)

    def test_el_empleado_si_puede_vender(self):
        permisos = usuarios.permisos_de(usuarios.EMPLEADO)
        for necesario in ("vender", "cobrar_deudas", "merma", "salida_inventario"):
            self.assertIn(necesario, permisos)


class CambiarLosPermisos(SobreUnaCopia):

    def test_el_admin_puede_dar_un_permiso_al_empleado(self):
        self.assertNotIn("crear_producto", usuarios.permisos_de(usuarios.EMPLEADO))
        exito, _ = usuarios.fijar_permiso(usuarios.EMPLEADO, "crear_producto", True)
        self.assertTrue(exito)
        self.assertIn("crear_producto", usuarios.permisos_de(usuarios.EMPLEADO))

    def test_y_tambien_quitarselo(self):
        usuarios.fijar_permiso(usuarios.EMPLEADO, "vender", False)
        self.assertNotIn("vender", usuarios.permisos_de(usuarios.EMPLEADO))

    def test_gestionar_usuarios_no_se_le_puede_dar_a_boss(self):
        """Dijo el dueno que eso es solo de Admin."""
        exito, motivo = usuarios.fijar_permiso(usuarios.BOSS, "gestionar_usuarios", True)
        self.assertFalse(exito)
        self.assertIn("Admin", motivo)
        self.assertNotIn("gestionar_usuarios", usuarios.permisos_de(usuarios.BOSS))

    def test_a_admin_no_se_le_quita_nada(self):
        """Si se pudiera, un descuido dejaria la tienda sin administrador."""
        exito, _ = usuarios.fijar_permiso(usuarios.ADMIN, "vender", False)
        self.assertFalse(exito)
        self.assertEqual(usuarios.permisos_de(usuarios.ADMIN), set(usuarios.CLAVES))

    def test_aunque_alguien_toque_la_tabla_a_mano_admin_sigue_pudiendo(self):
        """La salida de emergencia: Admin no depende de lo que diga la tabla."""
        con = sqlite3.connect(os.path.join(self.temporal, "tienda.db"))
        con.execute("UPDATE permisos_rol SET concedido = 0 WHERE rol = 'Admin'")
        con.commit()
        con.close()
        self.assertEqual(usuarios.permisos_de(usuarios.ADMIN), set(usuarios.CLAVES))

    def test_un_rol_inventado_se_rechaza(self):
        self.assertFalse(usuarios.fijar_permiso("Jefazo", "vender", True)[0])

    def test_un_permiso_inventado_se_rechaza(self):
        self.assertFalse(usuarios.fijar_permiso(usuarios.EMPLEADO, "volar", True)[0])


class NoQuedarseSinAdmin(SobreUnaCopia):

    def test_no_se_desactiva_al_unico_admin(self):
        admin = self.crear("Ana", usuarios.ADMIN)
        exito, motivo = usuarios.desactivar_usuario(admin)
        self.assertFalse(exito)
        self.assertIn("único Admin", motivo)

    def test_no_se_le_cambia_el_rol_al_unico_admin(self):
        admin = self.crear("Ana", usuarios.ADMIN)
        exito, _ = usuarios.cambiar_rol(admin, usuarios.EMPLEADO)
        self.assertFalse(exito)

    def test_con_dos_admins_si_se_puede(self):
        self.crear("Ana", usuarios.ADMIN)
        otro = self.crear("Beto", usuarios.ADMIN)
        self.assertTrue(usuarios.desactivar_usuario(otro)[0])

    def test_desactivar_no_borra_la_fila(self):
        """Lo que hizo tiene que seguir teniendo nombre."""
        self.crear("Ana", usuarios.ADMIN)
        luis = self.crear("Luis", usuarios.EMPLEADO)
        usuarios.desactivar_usuario(luis)
        self.assertEqual(
            self.consultar("SELECT COUNT(*) FROM usuarios WHERE nombre='Luis'")[0][0], 1)

    def test_un_usuario_apagado_no_entra(self):
        self.crear("Ana", usuarios.ADMIN)
        luis = self.crear("Luis", usuarios.EMPLEADO, "5555")
        usuarios.desactivar_usuario(luis)
        self.assertFalse(sesion.entrar("Luis", "5555")[0])


class ElAdminRestableceElPin(SobreUnaCopia):

    def test_le_pone_pin_nuevo_a_cualquiera_sin_saber_el_viejo(self):
        luis = self.crear("Luis", usuarios.EMPLEADO, "1111")
        exito, mensaje = usuarios.restablecer_pin(luis, "8888")
        self.assertTrue(exito, mensaje)
        self.assertFalse(sesion.entrar("Luis", "1111")[0], "el viejo ya no vale")
        self.assertTrue(sesion.entrar("Luis", "8888")[0])

    def test_el_pin_nuevo_tambien_tiene_que_ser_largo(self):
        luis = self.crear("Luis", usuarios.EMPLEADO)
        self.assertFalse(usuarios.restablecer_pin(luis, "1")[0])


class LaSesion(SobreUnaCopia):

    def test_sin_nadie_dentro_no_se_puede_nada(self):
        for clave in usuarios.CLAVES:
            self.assertFalse(sesion.puede(clave))

    def test_exigir_avisa_de_que_hay_que_entrar(self):
        with self.assertRaises(sesion.SinPermiso):
            sesion.exigir("vender")

    def test_el_empleado_choca_donde_debe(self):
        self.crear("Luis", usuarios.EMPLEADO, "1111")
        sesion.entrar("Luis", "1111")
        sesion.exigir("vender")  # esto no levanta nada
        with self.assertRaises(sesion.SinPermiso):
            sesion.exigir("eliminar_producto")

    def test_el_mensaje_dice_quien_es_y_que_le_falta(self):
        self.crear("Luis", usuarios.EMPLEADO, "1111")
        sesion.entrar("Luis", "1111")
        try:
            sesion.exigir("eliminar_historial")
            self.fail("tenia que haber levantado SinPermiso")
        except sesion.SinPermiso as sin_permiso:
            texto = str(sin_permiso)
            self.assertIn("Luis", texto)
            self.assertIn("Empleado", texto)


class LoQueSeGuardaLlevaNombre(SobreUnaCopia):

    def test_una_merma_queda_a_nombre_de_quien_la_hizo(self):
        from lddl.inventario import registrar_merma_de_carrito

        self.crear("Luis", usuarios.EMPLEADO, "1111")
        sesion.entrar("Luis", "1111")
        producto = self.consultar(
            "SELECT id FROM productos WHERE stock >= 1 LIMIT 1")[0][0]
        self.assertTrue(registrar_merma_de_carrito(
            [{"producto_id": producto, "cantidad": 1}])[0])

        self.assertEqual(
            self.consultar(
                "SELECT usuario FROM salidas_inventario ORDER BY id DESC LIMIT 1")[0][0],
            "Luis")

    def test_una_entrada_de_efectivo_tambien(self):
        from lddl.caja import registrar_entrada_efectivo

        self.crear("Ana", usuarios.ADMIN, "1111")
        sesion.entrar("Ana", "1111")
        registrar_entrada_efectivo("CUP", 100, "prueba")
        self.assertEqual(
            self.consultar(
                "SELECT usuario FROM entradas_efectivo ORDER BY id DESC LIMIT 1")[0][0],
            "Ana")

    def test_el_historial_lo_ensena(self):
        from lddl.caja import registrar_entrada_efectivo
        from lddl.ventas_datos import obtener_ventas

        self.crear("Ana", usuarios.ADMIN, "1111")
        sesion.entrar("Ana", "1111")
        registrar_entrada_efectivo("CUP", 100, "prueba")
        entradas = [r for r in obtener_ventas() if r["tipo"] == "Entrada de efectivo"]
        self.assertTrue(entradas)
        self.assertEqual(entradas[0]["usuario"], "Ana")

    def test_TODAS_las_filas_del_historial_traen_el_campo(self):
        """Se me habia olvidado en las altas de producto: sin campo, la
        columna de la tabla salia en blanco sin que nadie se enterara."""
        from lddl.caja import registrar_entrada_efectivo, registrar_operacion_cambio
        from lddl.inventario import registrar_merma_de_carrito
        from lddl.productos import agregar_producto
        from lddl.ventas_datos import obtener_ventas

        self.crear("Ana", usuarios.ADMIN, "1111")
        sesion.entrar("Ana", "1111")

        agregar_producto("Colado de prueba", "", 10, 20, 5, "", "unidad", "unidad", "")
        registrar_entrada_efectivo("CUP", 100, "prueba")
        registrar_operacion_cambio("compra", "USD", 5, 400, "prueba")
        producto = self.consultar("SELECT id FROM productos WHERE stock >= 1 LIMIT 1")[0][0]
        registrar_merma_de_carrito([{"producto_id": producto, "cantidad": 1}])

        registros = obtener_ventas()
        self.assertTrue(registros)
        sin_campo = [r["tipo"] for r in registros if "usuario" not in r]
        self.assertEqual(sin_campo, [], "estos tipos no traen el campo usuario")

    def test_sin_sesion_se_guarda_sin_nombre_pero_no_revienta(self):
        """Las pruebas viejas y los scripts no abren sesion: no pueden fallar."""
        from lddl.caja import registrar_entrada_efectivo

        exito, _ = registrar_entrada_efectivo("CUP", 50, "sin nadie dentro")
        self.assertTrue(exito)
        self.assertEqual(
            self.consultar(
                "SELECT usuario FROM entradas_efectivo ORDER BY id DESC LIMIT 1")[0][0],
            "")


@unittest.skipUnless(HAY_API, "hace falta fastapi (ver requisitos-api.txt)")
class LaApiEsLaQueImpide(SobreUnaCopia):
    """Lo importante: la barrera está en la ruta, no en la pantalla."""

    def setUp(self):
        super().setUp()
        self.cliente = TestClient(app)

    def test_sin_sesion_una_ruta_que_escribe_contesta_401(self):
        r = self.cliente.post("/caja/entradas",
                              json={"moneda": "CUP", "monto": 100, "descripcion": "x"})
        self.assertEqual(r.status_code, 401)

    def test_el_empleado_no_puede_crear_productos_por_http(self):
        self.crear("Ana", usuarios.ADMIN)
        self.crear("Luis", usuarios.EMPLEADO, "1111")
        sesion.entrar("Luis", "1111")
        r = self.cliente.post("/productos", json={"nombre": "Colado", "precio_venta": 10})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(
            self.consultar("SELECT COUNT(*) FROM productos WHERE nombre='Colado'")[0][0],
            0, "no basta con contestar 403: no puede haber escrito")

    def test_ni_borrar_del_historial(self):
        self.crear("Luis", usuarios.EMPLEADO, "1111")
        sesion.entrar("Luis", "1111")
        r = self.cliente.delete("/historial/1", params={"tipo": "Merma"})
        self.assertEqual(r.status_code, 403)

    def test_el_admin_si_puede(self):
        self.crear("Ana", usuarios.ADMIN, "1111")
        sesion.entrar("Ana", "1111")
        r = self.cliente.post("/productos", json={"nombre": "Colado", "precio_venta": 10})
        self.assertEqual(r.status_code, 201, r.text)

    def test_boss_no_gestiona_usuarios(self):
        self.crear("Ana", usuarios.ADMIN)
        self.crear("Jefe", usuarios.BOSS, "2222")
        sesion.entrar("Jefe", "2222")
        self.assertEqual(self.cliente.get("/usuarios").status_code, 403)
        self.assertEqual(self.cliente.get("/permisos").status_code, 403)

    def test_pero_boss_si_vende(self):
        self.crear("Ana", usuarios.ADMIN)
        self.crear("Jefe", usuarios.BOSS, "2222")
        sesion.entrar("Jefe", "2222")
        r = self.cliente.post("/productos", json={"nombre": "Colado", "precio_venta": 10})
        self.assertEqual(r.status_code, 201, r.text)

    def test_al_conceder_el_permiso_el_empleado_pasa(self):
        """El cambio de permisos tiene efecto sin reiniciar nada."""
        self.crear("Ana", usuarios.ADMIN)
        self.crear("Luis", usuarios.EMPLEADO, "1111")
        sesion.entrar("Luis", "1111")
        self.assertEqual(
            self.cliente.post("/productos",
                              json={"nombre": "Colado", "precio_venta": 10}).status_code,
            403)

        usuarios.fijar_permiso(usuarios.EMPLEADO, "crear_producto", True)
        self.assertEqual(
            self.cliente.post("/productos",
                              json={"nombre": "Colado", "precio_venta": 10}).status_code,
            201)

    def test_leer_no_pide_permiso(self):
        """La caja tiene que poder buscar productos aunque no haya nadie dentro."""
        self.assertEqual(self.cliente.get("/productos").status_code, 200)
        self.assertEqual(self.cliente.get("/salud").status_code, 200)

    def test_el_primer_admin_solo_se_crea_una_vez(self):
        r = self.cliente.post("/sesion/primer-admin",
                              json={"nombre": "Duena", "pin": "1234"})
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()["sesion"]["rol"], usuarios.ADMIN)

        otra = self.cliente.post("/sesion/primer-admin",
                                 json={"nombre": "Colado", "pin": "1234"})
        self.assertEqual(otra.status_code, 409, "esa puerta se cierra al entrar")

    def test_entrar_y_salir_por_http(self):
        self.crear("Ana", usuarios.ADMIN, "1234")
        r = self.cliente.post("/sesion", json={"nombre": "Ana", "pin": "1234"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["sesion"]["nombre"], "Ana")
        self.assertIn("vender", r.json()["permisos"])

        self.assertEqual(self.cliente.delete("/sesion").status_code, 200)
        self.assertIsNone(self.cliente.get("/sesion").json()["sesion"])

    def test_el_pin_malo_da_401(self):
        self.crear("Ana", usuarios.ADMIN, "1234")
        r = self.cliente.post("/sesion", json={"nombre": "Ana", "pin": "0000"})
        self.assertEqual(r.status_code, 401)


@unittest.skipUnless(HAY_API, "hace falta fastapi")
class NingunaRutaQueEscribeSeQuedaSinGuardia(SobreUnaCopia):
    """Si alguien añade una ruta nueva y olvida el permiso, esto lo caza."""

    SIN_GUARDIA_A_PROPOSITO = {
        # Aritmetica pura: no tocan la base.
        ("POST", "/cobro/vuelto"),
        ("POST", "/cobro/desglose"),
        ("POST", "/deudas/{venta_id}/simular"),
        # La propia puerta de entrada, y la creacion del primer Admin, que se
        # cierra sola en cuanto hay usuarios.
        ("POST", "/sesion"),
        ("DELETE", "/sesion"),
        ("POST", "/sesion/primer-admin"),
    }

    def test_todas_llevan_permiso(self):
        sospechosas = set()
        for ruta in app.routes:
            camino = getattr(ruta, "path", "")
            metodos = getattr(ruta, "methods", set())
            for metodo in metodos:
                if metodo not in ("POST", "PUT", "PATCH", "DELETE"):
                    continue
                if (metodo, camino) in self.SIN_GUARDIA_A_PROPOSITO:
                    continue
                if not getattr(ruta, "dependencies", None):
                    sospechosas.add((metodo, camino))
        self.assertEqual(
            sospechosas, set(),
            "Rutas que escriben sin comprobar permiso. Ponles exige(...), o "
            "apuntalas en SIN_GUARDIA_A_PROPOSITO si de verdad no hacen falta.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
