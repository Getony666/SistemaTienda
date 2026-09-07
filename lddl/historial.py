"""Registro del historial y reversión de sus asientos.

revertir_registro deshace un registro con todos sus efectos: devuelve el stock,
saca del fondo la divisa que entró y borra los movimientos de caja asociados."""

import datetime
import json

from .rutas import conectar_db, transaccion


def registrar_historial(tipo_accion, descripcion, detalles=None):
    try:
        with transaccion() as (_conn, cursor):
            fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute('''
                INSERT INTO historial (fecha, tipo_accion, descripcion, detalles)
                VALUES (?, ?, ?, ?)
            ''', (fecha, tipo_accion, descripcion, json.dumps(detalles) if detalles else None))
        return True
    except Exception as e:
        print(f"Error al registrar historial: {e}")
        return False

def _ajustar_fondo_divisas(cursor, fecha, moneda, delta):
    """Suma `delta` (puede ser negativo) al fondo de esa divisa en la fecha indicada.

    A diferencia de actualizar_fondo, trabaja sobre la fecha del registro que se
    revierte y no sobre la de hoy: revertir una venta de ayer no puede descuadrar
    la caja de hoy.
    """
    if not moneda or moneda == "CUP" or not delta:
        return
    cursor.execute("SELECT cantidad FROM fondo_divisas WHERE fecha = ? AND moneda = ?", (fecha, moneda))
    fila = cursor.fetchone()
    if fila:
        cursor.execute("UPDATE fondo_divisas SET cantidad = ? WHERE fecha = ? AND moneda = ?",
                       (fila[0] + delta, fecha, moneda))
    else:
        cursor.execute("INSERT INTO fondo_divisas (fecha, moneda, cantidad) VALUES (?, ?, ?)",
                       (fecha, moneda, delta))


def _movimientos_de_venta(cursor, tabla, venta_id):
    """Entradas o salidas de efectivo generadas por una venta o deuda."""
    filas = cursor.execute(
        f"SELECT id, fecha, moneda, monto FROM {tabla} WHERE venta_id = ?", (venta_id,)
    ).fetchall()
    if filas:
        return filas
    # Registros anteriores a la columna venta_id: se reconocen por la descripción,
    # que siempre termina en "#<id>" o lo lleva seguido de un espacio.
    return cursor.execute(
        f"""SELECT id, fecha, moneda, monto FROM {tabla}
            WHERE venta_id IS NULL AND (descripcion LIKE ? OR descripcion LIKE ?)""",
        (f"%#{venta_id}", f"%#{venta_id} %")
    ).fetchall()


def _borrar_historial_por_ref(cursor, tipo_accion, ref_id):
    """Borra el apunte del historial que corresponde a un registro concreto.

    Sólo borra si el apunte declara el ref_id que se le pasa: sin esa marca
    (registros antiguos) se prefiere dejar el rastro antes que borrar el ajeno.
    """
    cursor.execute("SELECT id, detalles FROM historial WHERE tipo_accion = ?", (tipo_accion,))
    for hist_id, detalles_json in cursor.fetchall():
        if not detalles_json:
            continue
        try:
            detalles = json.loads(detalles_json)
        except (ValueError, TypeError):
            continue
        if detalles.get("ref_id") == ref_id:
            cursor.execute("DELETE FROM historial WHERE id = ?", (hist_id,))
            return True
    return False


def _divisa_neta_de_venta(cursor, venta):
    """Divisa que entró al fondo por una venta.

    Las ventas nuevas lo guardan en monto_divisa_neto. Para las anteriores a esa
    columna se deduce: lo que no se cobró en CUP se cobró en divisa, más lo que
    salió de caja como vuelto.
    """
    if venta["moneda_pago"] not in ("USD", "EUR") or not venta["tasa_cambio"]:
        return 0.0
    if venta["monto_divisa_neto"]:
        return venta["monto_divisa_neto"]
    salidas = _movimientos_de_venta(cursor, "salidas_efectivo", venta["id"])
    vuelto_cup = sum(m for (_i, _f, mon, m) in salidas if mon == "CUP")
    aportado_cup = venta["total"] - (venta["monto_efectivo"] or 0.0) - (venta["monto_transferencia"] or 0.0) + vuelto_cup
    return round(aportado_cup / venta["tasa_cambio"], 6) if aportado_cup > 0 else 0.0


def revertir_registro(id_reg, tipo):
    """Elimina un registro del historial deshaciendo todos sus efectos.

    Devuelve (True, mensaje) o (False, motivo). El objetivo es que la base quede
    igual que antes de crear el registro: stock, fondo de divisas y movimientos de
    caja incluidos. El fondo inicial de caja del día nunca se toca, porque no es
    donde se acumula el dinero de las ventas: el efectivo se deriva de las tablas.
    """
    conn = conectar_db()
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE")

        if tipo in ("Venta", "Deuda"):
            cursor.execute('''
                SELECT id, fecha, total, metodo_pago, moneda_pago, tasa_cambio, es_deuda,
                       monto_efectivo, monto_transferencia, monto_divisa_neto
                FROM ventas WHERE id = ?
            ''', (id_reg,))
            fila = cursor.fetchone()
            if not fila:
                conn.rollback()
                conn.close()
                return False, "Venta no encontrada"
            venta = {
                "id": fila[0], "fecha": fila[1], "total": fila[2], "metodo_pago": fila[3],
                "moneda_pago": fila[4], "tasa_cambio": fila[5], "es_deuda": fila[6],
                "monto_efectivo": fila[7], "monto_transferencia": fila[8],
                "monto_divisa_neto": fila[9],
            }
            fecha_venta = (venta["fecha"] or "")[:10]

            # 1. Devolver al inventario todo lo que salió con la venta.
            cursor.execute("SELECT producto_id, cantidad FROM detalles_venta WHERE venta_id = ?", (id_reg,))
            for prod_id, cant in cursor.fetchall():
                cursor.execute("UPDATE productos SET stock = stock + ? WHERE id = ?", (cant, prod_id))

            # 2. Sacar del fondo la divisa que entró con la venta.
            divisa_neta = _divisa_neta_de_venta(cursor, venta)
            if divisa_neta:
                _ajustar_fondo_divisas(cursor, fecha_venta, venta["moneda_pago"], -divisa_neta)

            # 3. Deshacer los cobros: la divisa vuelve a salir del fondo y el CUP
            #    desaparece al borrar la fila, porque la caja se deriva de esta tabla.
            cursor.execute('''
                SELECT id, fecha, monto, moneda, monto_divisa_neto
                FROM cobros_deudas WHERE venta_id = ?
            ''', (id_reg,))
            for cobro_id, fecha_cobro, monto, moneda_cobro, neto_cobro in cursor.fetchall():
                if moneda_cobro and moneda_cobro != "CUP":
                    neto = neto_cobro if neto_cobro else monto
                    _ajustar_fondo_divisas(cursor, (fecha_cobro or "")[:10], moneda_cobro, -neto)
            cursor.execute("DELETE FROM cobros_deudas WHERE venta_id = ?", (id_reg,))

            # 4. Deshacer los movimientos de caja que generó (vueltos entregados y
            #    cobros en CUP registrados aparte).
            for tabla in ("salidas_efectivo", "entradas_efectivo"):
                for mov_id, fecha_mov, moneda_mov, monto_mov in _movimientos_de_venta(cursor, tabla, id_reg):
                    if moneda_mov and moneda_mov != "CUP":
                        signo = 1 if tabla == "salidas_efectivo" else -1
                        _ajustar_fondo_divisas(cursor, (fecha_mov or "")[:10], moneda_mov, signo * monto_mov)
                    cursor.execute(f"DELETE FROM {tabla} WHERE id = ?", (mov_id,))

            # 5. Si venía de una salida a trabajador, retirar también su rastro.
            if venta["metodo_pago"] == "Salida":
                cursor.execute("SELECT producto_id, cantidad FROM detalles_venta WHERE venta_id = ?", (id_reg,))
                for prod_id, cant in cursor.fetchall():
                    cursor.execute('''DELETE FROM salidas_inventario WHERE id = (
                                          SELECT id FROM salidas_inventario
                                          WHERE producto_id = ? AND cantidad = ? AND motivo NOT LIKE '%Merma%'
                                          ORDER BY id DESC LIMIT 1)''', (prod_id, cant))
                _borrar_historial_por_ref(cursor, "Salida de Producto", id_reg)

            cursor.execute("DELETE FROM detalles_venta WHERE venta_id = ?", (id_reg,))
            cursor.execute("DELETE FROM ventas WHERE id = ?", (id_reg,))
            conn.commit()
            conn.close()
            return True, "Venta eliminada y todos sus efectos revertidos"

        elif tipo == "Salida de Producto":
            cursor.execute("SELECT detalles FROM historial WHERE id = ?", (id_reg,))
            fila = cursor.fetchone()
            if not fila:
                conn.rollback()
                conn.close()
                return False, "Registro de historial no encontrado"
            try:
                detalles = json.loads(fila[0])
            except (ValueError, TypeError):
                conn.rollback()
                conn.close()
                return False, "Error al parsear detalles"

            producto_id = detalles.get("producto_id")
            cantidad = detalles.get("cantidad")
            venta_id = detalles.get("venta_id")
            ref_id = detalles.get("ref_id")

            if producto_id and cantidad:
                cursor.execute("UPDATE productos SET stock = stock + ? WHERE id = ?", (cantidad, producto_id))
            if venta_id:
                cursor.execute("SELECT id FROM ventas WHERE id = ? AND metodo_pago = 'Salida'", (venta_id,))
                if cursor.fetchone():
                    cursor.execute("DELETE FROM cobros_deudas WHERE venta_id = ?", (venta_id,))
                    cursor.execute("DELETE FROM detalles_venta WHERE venta_id = ?", (venta_id,))
                    cursor.execute("DELETE FROM ventas WHERE id = ?", (venta_id,))
            if ref_id:
                cursor.execute("DELETE FROM salidas_inventario WHERE id = ?", (ref_id,))
            elif producto_id and cantidad:
                cursor.execute('''DELETE FROM salidas_inventario WHERE id = (
                                      SELECT id FROM salidas_inventario
                                      WHERE producto_id = ? AND cantidad = ? AND motivo NOT LIKE '%Merma%'
                                      ORDER BY id DESC LIMIT 1)''', (producto_id, cantidad))
            cursor.execute("DELETE FROM historial WHERE id = ?", (id_reg,))
            conn.commit()
            conn.close()
            return True, "Salida eliminada y stock restaurado"

        elif tipo == "Entrada de Producto":
            cursor.execute("SELECT detalles FROM historial WHERE id = ?", (id_reg,))
            fila = cursor.fetchone()
            if not fila:
                conn.rollback()
                conn.close()
                return False, "Registro de historial no encontrado"
            try:
                detalles = json.loads(fila[0])
            except (ValueError, TypeError):
                conn.rollback()
                conn.close()
                return False, "Error al procesar la entrada de producto"
            nombre = detalles.get("nombre")
            cursor.execute("SELECT id FROM productos WHERE nombre = ?", (nombre,))
            prod = cursor.fetchone()
            if prod:
                producto_id = prod[0]
                cursor.execute("SELECT COUNT(*) FROM detalles_venta WHERE producto_id = ?", (producto_id,))
                if cursor.fetchone()[0] > 0:
                    conn.rollback()
                    conn.close()
                    return False, "No se puede eliminar porque el producto ya tiene ventas"
                cursor.execute("DELETE FROM productos WHERE id = ?", (producto_id,))
            cursor.execute("DELETE FROM historial WHERE id = ?", (id_reg,))
            conn.commit()
            conn.close()
            return True, "Entrada de producto eliminada y producto removido"

        elif tipo == "Merma":
            cursor.execute("SELECT producto_id, cantidad FROM salidas_inventario WHERE id = ?", (id_reg,))
            fila = cursor.fetchone()
            if not fila:
                conn.rollback()
                conn.close()
                return False, "Merma no encontrada"
            producto_id, cantidad = fila
            cursor.execute("UPDATE productos SET stock = stock + ? WHERE id = ?", (cantidad, producto_id))
            cursor.execute("DELETE FROM salidas_inventario WHERE id = ?", (id_reg,))
            _borrar_historial_por_ref(cursor, "Merma", id_reg)
            conn.commit()
            conn.close()
            return True, "Merma eliminada y stock restaurado"

        elif tipo == "Entrada de efectivo":
            cursor.execute("SELECT fecha, moneda, monto FROM entradas_efectivo WHERE id = ?", (id_reg,))
            fila = cursor.fetchone()
            if not fila:
                conn.rollback()
                conn.close()
                return False, "Entrada de efectivo no encontrada"
            fecha_mov, moneda, monto = fila
            _ajustar_fondo_divisas(cursor, (fecha_mov or "")[:10], moneda, -monto)
            cursor.execute("DELETE FROM entradas_efectivo WHERE id = ?", (id_reg,))
            _borrar_historial_por_ref(cursor, "Entrada de efectivo", id_reg)
            conn.commit()
            conn.close()
            return True, "Entrada de efectivo revertida"

        elif tipo == "Salida de efectivo":
            cursor.execute("SELECT fecha, moneda, monto FROM salidas_efectivo WHERE id = ?", (id_reg,))
            fila = cursor.fetchone()
            if not fila:
                conn.rollback()
                conn.close()
                return False, "Salida de efectivo no encontrada"
            fecha_mov, moneda, monto = fila
            _ajustar_fondo_divisas(cursor, (fecha_mov or "")[:10], moneda, monto)
            cursor.execute("DELETE FROM salidas_efectivo WHERE id = ?", (id_reg,))
            _borrar_historial_por_ref(cursor, "Salida de efectivo", id_reg)
            conn.commit()
            conn.close()
            return True, "Salida de efectivo revertida"

        elif tipo in ("Cambio de Divisa", "cambio"):
            cursor.execute("SELECT fecha, tipo, moneda, cantidad, monto_cup FROM operaciones_cambio WHERE id = ?", (id_reg,))
            fila = cursor.fetchone()
            if not fila:
                conn.rollback()
                conn.close()
                return False, "Operación de cambio no encontrada"
            fecha_op, tipo_op, moneda, cantidad, monto_cup = fila
            fecha_corta = (fecha_op or "")[:10]
            # Una compra de divisa sumó al fondo y una venta lo restó.
            _ajustar_fondo_divisas(cursor, fecha_corta, moneda, -cantidad if tipo_op == "compra" else cantidad)
            if tipo_op == "venta":
                cursor.execute('''DELETE FROM entradas_efectivo WHERE id = (
                                      SELECT id FROM entradas_efectivo
                                      WHERE moneda = 'CUP' AND monto = ? AND descripcion LIKE ?
                                      ORDER BY id DESC LIMIT 1)''',
                               (monto_cup, f"Venta de {cantidad}%{moneda}%"))
            cursor.execute("DELETE FROM operaciones_cambio WHERE id = ?", (id_reg,))
            _borrar_historial_por_ref(cursor, "Cambio de Divisa", id_reg)
            conn.commit()
            conn.close()
            return True, "Operación de cambio revertida"

        else:
            conn.rollback()
            conn.close()
            return False, f"No se puede eliminar automáticamente el tipo '{tipo}'"

    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"Error: {str(e)}"
