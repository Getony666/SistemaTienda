"""Caja: fondo del día, efectivo en CUP, fondo de divisas y cambio de moneda.

El efectivo en CUP no se guarda en ninguna columna: se deriva sumando las ventas
en efectivo, los cobros, las entradas y las salidas del día. El fondo que guarda
config_caja.json es sólo el dinero con el que se abre la jornada."""

import datetime
import json
import os

from . import sesion
from .historial import registrar_historial
from .rutas import conectar_db, consulta, obtener_ruta_config


def cargar_fondo_por_fecha(fecha):
    ruta_config = obtener_ruta_config()
    if os.path.exists(ruta_config):
        try:
            with open(ruta_config, 'r', encoding='utf-8') as f:
                fondos = json.load(f)
                return fondos.get(fecha, 0.0)
        except:
            return 0.0
    return 0.0

def guardar_fondo_por_fecha(fecha, fondo):
    ruta_config = obtener_ruta_config()
    try:
        fondos = {}
        if os.path.exists(ruta_config):
            try:
                with open(ruta_config, 'r', encoding='utf-8') as f:
                    fondos = json.load(f)
            except:
                fondos = {}
        fondos[fecha] = fondo
        with open(ruta_config, 'w', encoding='utf-8') as f:
            json.dump(fondos, f, indent=4, ensure_ascii=False)
        return True
    except:
        return False

def obtener_saldo_divisas(fecha):
    with consulta() as (conexion, cursor):
        cursor.execute("SELECT moneda, cantidad FROM fondo_divisas WHERE fecha = ?", (fecha,))
        resultados = cursor.fetchall()
        saldo = {}
        for r in resultados:
            saldo[r[0]] = r[1]
        return saldo

def obtener_gasto_compras_divisas(fecha):
    with consulta() as (conexion, cursor):
        cursor.execute('''
            SELECT SUM(monto_cup) FROM operaciones_cambio
            WHERE fecha LIKE ? AND tipo = 'compra'
        ''', (f"{fecha}%",))
        total = cursor.fetchone()[0] or 0.0
        return total

def obtener_efectivo_disponible_cup(fecha):
    with consulta() as (conexion, cursor):
        fecha_like = f"{fecha}%"

        # Ventas en efectivo del día (no deudas, no canceladas)
        cursor.execute('''
            SELECT SUM(monto_efectivo) FROM ventas
            WHERE fecha LIKE ? AND cancelada = 0 AND es_deuda = 0
        ''', (fecha_like,))
        ventas_efectivo = cursor.fetchone()[0] or 0.0

        # Cobros de deudas en efectivo CUP del día
        cursor.execute('''
            SELECT SUM(c.monto) FROM cobros_deudas c
            WHERE c.fecha LIKE ? AND c.metodo_pago = 'Efectivo' AND c.moneda = 'CUP'
        ''', (fecha_like,))
        cobros_efectivo = cursor.fetchone()[0] or 0.0

        # Entradas de efectivo CUP del día
        cursor.execute('''
            SELECT SUM(monto) FROM entradas_efectivo
            WHERE fecha LIKE ? AND moneda = 'CUP'
        ''', (fecha_like,))
        entradas_efectivo = cursor.fetchone()[0] or 0.0

        # Salidas de efectivo CUP del día
        cursor.execute('''
            SELECT SUM(monto) FROM salidas_efectivo
            WHERE fecha LIKE ? AND moneda = 'CUP'
        ''', (fecha_like,))
        salidas_efectivo = cursor.fetchone()[0] or 0.0

        # Obtener el fondo de caja para la fecha
        fondo_caja = cargar_fondo_por_fecha(fecha)

        # Calcular efectivo disponible incluyendo el fondo
        efectivo_caja = fondo_caja + ventas_efectivo + cobros_efectivo + entradas_efectivo - salidas_efectivo
    
        return efectivo_caja

def obtener_resumen_caja(fecha):
    with consulta() as (conexion, cursor):
        fecha_like = f"{fecha}%"
    
        # ===== 1. VENTAS NORMALES (NO DEUDAS) =====
        cursor.execute('''
            SELECT monto_efectivo, monto_transferencia, total
            FROM ventas
            WHERE fecha LIKE ? AND cancelada = 0 AND es_deuda = 0
        ''', (fecha_like,))
        ventas_normales = cursor.fetchall()
    
        ventas_efectivo_total = 0.0
        ventas_efectivo_cant = 0
        ventas_transferencia_total = 0.0
        ventas_transferencia_cant = 0
        total_ventas_normales = 0.0
    
        for monto_ef, monto_trans, total in ventas_normales:
            total_ventas_normales += total
            if monto_ef > 0:
                ventas_efectivo_total += monto_ef
                ventas_efectivo_cant += 1
            if monto_trans > 0:
                ventas_transferencia_total += monto_trans
                ventas_transferencia_cant += 1
    
        # ===== 2. DEUDAS GENERADAS HOY =====
        cursor.execute('''
            SELECT SUM(total) FROM ventas
            WHERE fecha LIKE ? AND cancelada = 0 AND es_deuda = 1 AND metodo_pago != 'Salida'
        ''', (fecha_like,))
        total_deudas_generadas_hoy = cursor.fetchone()[0] or 0.0
    
        # ===== 3. COBROS DE DEUDAS =====
        cursor.execute('''
            SELECT 
                c.id, 
                c.venta_id, 
                c.monto, 
                c.metodo_pago, 
                c.moneda, 
                c.tasa, 
                c.monto_cup, 
                v.metodo_pago as venta_metodo_pago, 
                v.es_deuda,
                c.fecha as fecha_cobro,
                v.fecha as fecha_venta
            FROM cobros_deudas c
            JOIN ventas v ON c.venta_id = v.id
            WHERE c.fecha LIKE ?
        ''', (fecha_like,))
        cobros = cursor.fetchall()
    
        # ===== 4. VUELTOS DE DEUDAS =====
        cursor.execute('''
            SELECT id, fecha, monto, descripcion
            FROM salidas_efectivo
            WHERE fecha LIKE ? AND moneda = 'CUP' AND descripcion LIKE '%vuelto%'
        ''', (fecha_like,))
        salidas_vueltos = cursor.fetchall()
    
        # Diccionario para sumar los vueltos por venta
        vueltos_por_venta = {}
        for salida_id, fecha_salida, monto, descripcion in salidas_vueltos:
            if 'deuda #' in descripcion:
                try:
                    venta_id_str = descripcion.split('deuda #')[1].split()[0]
                    venta_id = int(venta_id_str)
                    if venta_id not in vueltos_por_venta:
                        vueltos_por_venta[venta_id] = 0.0
                    vueltos_por_venta[venta_id] += monto
                except:
                    pass
    
        # ===== 5. PROCESAR COBROS DE DEUDAS =====
        cobros_deudas_efectivo_total = 0.0
        cobros_deudas_efectivo_cant = 0
        cobros_deudas_transferencia_total = 0.0
        cobros_deudas_transferencia_cant = 0
    
        cobros_efectivo_total = 0.0
        cobros_efectivo_cant = 0
        cobros_transferencia_total = 0.0
        cobros_transferencia_cant = 0
    
        # ===== VARIABLE PRINCIPAL PARA EFECTIVO EN CAJA =====
        efectivo_caja_total = ventas_efectivo_total
    
        # Variable para acumular SOLO los vueltos de deudas del MISMO día pagadas en CUP
        # Estos vueltos ya están descontados en monto_neto, así que no debemos restarlos de nuevo
        vueltos_cup_mismo_dia_a_no_restar = 0.0
    
        for id_cobro, venta_id, monto, metodo_pago, moneda, tasa, monto_cup, venta_metodo_pago, es_deuda, fecha_cobro, fecha_venta in cobros:
            fecha_venta_str = fecha_venta.split()[0] if fecha_venta else ""
            fecha_hoy = datetime.datetime.now().strftime("%Y-%m-%d")
            es_deuda_del_dia = (fecha_venta_str == fecha_hoy)
        
            # Calcular el monto neto (restando el vuelto)
            monto_neto = monto
            if metodo_pago == "Efectivo" and venta_id in vueltos_por_venta:
                monto_neto = monto - vueltos_por_venta[venta_id]
                if monto_neto < 0:
                    monto_neto = 0
                # SOLO si es deuda del mismo día Y pagada en CUP, marcamos este vuelto para no restarlo
                if es_deuda_del_dia and moneda == "CUP":
                    vueltos_cup_mismo_dia_a_no_restar += vueltos_por_venta[venta_id]
        
            # ===== PROCESAR SEGÚN EL TIPO DE PAGO =====
            if es_deuda_del_dia and venta_metodo_pago != 'Salida':
                # DEUDA DEL DÍA - SÍ suma a ventas del día
                if moneda == "CUP" and metodo_pago == "Efectivo":
                    cobros_deudas_efectivo_total += monto_neto
                    cobros_deudas_efectivo_cant += 1
                    cobros_efectivo_total += monto_neto
                    cobros_efectivo_cant += 1
                    efectivo_caja_total += monto_neto
                
                elif moneda != "CUP" and metodo_pago == "Efectivo":
                    # Para pagos en USD/EUR de deudas del mismo día
                    # El vuelto en CUP YA está restado en monto_neto
                    # Pero como es pago en USD, el vuelto en CUP SÍ debe afectar la caja
                    # El monto_neto para USD no incluye el vuelto en CUP porque monto es en USD
                    # Así que aquí no sumamos ni restamos nada adicional
                    # El vuelto en CUP se restará normalmente en salidas_efectivo
                    pass
                
                elif moneda == "CUP" and metodo_pago == "Transferencia":
                    cobros_deudas_transferencia_total += monto_neto
                    cobros_deudas_transferencia_cant += 1
                    cobros_transferencia_total += monto_neto
                    cobros_transferencia_cant += 1
                
            else:
                # DEUDA DE DÍAS ANTERIORES
                if moneda == "CUP" and metodo_pago == "Efectivo":
                    # Para deudas de días anteriores pagadas en CUP
                    # El monto_neto ya tiene el vuelto descontado
                    # El vuelto en CUP se restará en salidas_efectivo normalmente
                    efectivo_caja_total += monto_neto
                elif moneda != "CUP" and metodo_pago == "Efectivo":
                    # Para pagos en USD de deudas anteriores
                    # No afecta el efectivo en CUP directamente
                    # El vuelto en CUP se restará en salidas_efectivo normalmente
                    pass
    
        # ===== 6. OBTENER ENTRADAS Y SALIDAS DE EFECTIVO =====
        cursor.execute('''
            SELECT id, monto, descripcion FROM entradas_efectivo
            WHERE fecha LIKE ? AND moneda = 'CUP'
        ''', (fecha_like,))
        entradas_efectivo_detalle = cursor.fetchall()
    
        entradas_efectivo_netas = 0.0
        for entrada_id, entrada_monto, entrada_desc in entradas_efectivo_detalle:
            if not entrada_desc or 'Pago de deuda #' not in str(entrada_desc):
                entradas_efectivo_netas += entrada_monto
    
        efectivo_caja_total += entradas_efectivo_netas
    
        # Obtener salidas de efectivo CUP
        cursor.execute('''
            SELECT SUM(monto) FROM salidas_efectivo
            WHERE fecha LIKE ? AND moneda = 'CUP'
        ''', (fecha_like,))
        salidas_efectivo_cup = cursor.fetchone()[0] or 0.0
    
        # ===== CORRECCIÓN CLAVE: Restar las salidas de efectivo PERO sin los vueltos de deudas del mismo día pagadas en CUP =====
        # Los vueltos de deudas del mismo día pagadas en CUP ya fueron descontados al calcular monto_neto
        # Pero los vueltos de deudas pagadas en USD SÍ deben restarse porque no están en monto_neto
        salidas_efectivo_a_restar = salidas_efectivo_cup - vueltos_cup_mismo_dia_a_no_restar
        efectivo_caja_total -= salidas_efectivo_a_restar
    
        # ===== 7. DEUDAS PENDIENTES =====
        cursor.execute('''
            SELECT COUNT(*), SUM(saldo_pendiente) FROM ventas
            WHERE fecha LIKE ? AND es_deuda=1 AND pagada=0 AND cancelada=0 AND metodo_pago != 'Salida'
        ''', (fecha_like,))
        deudas_pend = cursor.fetchone()
        deudas_pend_cant = deudas_pend[0] if deudas_pend[0] else 0
        deudas_pend_monto = deudas_pend[1] if deudas_pend[1] else 0.0
    
        # ===== 8. SALIDAS PENDIENTES =====
        cursor.execute('''
            SELECT COUNT(*), SUM(saldo_pendiente) FROM ventas
            WHERE fecha LIKE ? AND es_deuda=1 AND pagada=0 AND cancelada=0 AND metodo_pago = 'Salida'
        ''', (fecha_like,))
        salidas_pend = cursor.fetchone()
        salidas_pend_cant = salidas_pend[0] if salidas_pend[0] else 0
        salidas_pend_monto = salidas_pend[1] if salidas_pend[1] else 0.0
    
        # ===== 9. DIVISAS Y GASTOS =====
        saldo_divisas = obtener_saldo_divisas(fecha)
        gasto_divisas = obtener_gasto_compras_divisas(fecha)
    
        # ===== 10. CALCULAR TOTAL ESPERADO =====
        efectivo_caja_neto = efectivo_caja_total - gasto_divisas
    
        fondo = cargar_fondo_por_fecha(fecha)
        total_esperado = fondo + efectivo_caja_neto
    
        # ===== 11. UTILIDAD =====
        cursor.execute('''
            SELECT SUM(utilidad) FROM ventas
            WHERE fecha LIKE ? 
            AND cancelada = 0 
            AND metodo_pago != 'Salida'
        ''', (fecha_like,))
        utilidad_total = cursor.fetchone()[0] or 0.0
    
        # ===== 12. TOTAL VENTAS DÍA =====
        total_ventas_dia = total_ventas_normales + total_deudas_generadas_hoy
    
        # ===== 13. OBTENER TOTAL DE SALIDAS DE EFECTIVO (para mostrar) =====
        cursor.execute('''
            SELECT SUM(monto) FROM salidas_efectivo
            WHERE fecha LIKE ? AND moneda = 'CUP'
        ''', (fecha_like,))
        total_salidas_efectivo = cursor.fetchone()[0] or 0.0
    
        # ===== 14. ARMAR RESULTADO =====
        resumen = {
            "ventas_efectivo": {
                "cantidad": ventas_efectivo_cant + cobros_deudas_efectivo_cant, 
                "total": ventas_efectivo_total + cobros_deudas_efectivo_total
            },
            "ventas_transferencia": {
                "cantidad": ventas_transferencia_cant + cobros_deudas_transferencia_cant, 
                "total": ventas_transferencia_total + cobros_deudas_transferencia_total
            },
            "cobros_efectivo": {
                "cantidad": cobros_efectivo_cant, 
                "total": cobros_efectivo_total
            },
            "cobros_transferencia": {
                "cantidad": cobros_transferencia_cant, 
                "total": cobros_transferencia_total
            },
            "deudas_pendientes_dia": {
                "cantidad": deudas_pend_cant + salidas_pend_cant, 
                "total": deudas_pend_monto + salidas_pend_monto
            },
            "deudas_pendientes_netas": {
                "cantidad": deudas_pend_cant, 
                "total": deudas_pend_monto
            },
            "salidas_pendientes": {
                "cantidad": salidas_pend_cant, 
                "total": salidas_pend_monto
            },
            "total_ventas_dia": total_ventas_dia,
            "saldo_divisas": saldo_divisas,
            "gasto_divisas": gasto_divisas,
            "total_salidas_efectivo": total_salidas_efectivo,
            "efectivo_caja": efectivo_caja_neto,
            "fondo": fondo,
            "total_esperado": total_esperado,
            "utilidad_total": utilidad_total
        }
        return resumen

def registrar_entrada_efectivo(moneda, monto, descripcion=""):
    conn = conectar_db()
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE")
        fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute('''
            INSERT INTO entradas_efectivo (fecha, moneda, monto, descripcion, usuario)
            VALUES (?, ?, ?, ?, ?)
        ''', (fecha, moneda, monto, descripcion, sesion.usuario_actual()))
        ref_id = cursor.lastrowid
        if moneda in ("USD", "EUR"):
            exito, msg, nuevo_saldo = actualizar_fondo(moneda, monto, "entrada", conn, cursor)
            if not exito:
                conn.rollback()
                conn.close()
                return False, msg
        conn.commit()
        conn.close()
        registrar_historial(
            "Entrada de efectivo",
            f"{moneda} +{monto:.2f} - {descripcion or 'Sin descripción'}",
            {"moneda": moneda, "monto": monto, "descripcion": descripcion, "ref_id": ref_id}
        )
        return True, f"Entrada de efectivo registrada correctamente. {moneda} +{monto:.2f}"
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"Error al registrar entrada de efectivo: {str(e)}"

def registrar_salida_efectivo(moneda, monto, descripcion=""):
    conn = conectar_db()
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE")
        fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fecha_corta = datetime.datetime.now().strftime("%Y-%m-%d")
        if moneda == "CUP":
            disponible = obtener_efectivo_disponible_cup(fecha_corta)
            if monto > disponible:
                conn.rollback()
                conn.close()
                return False, f"No hay suficiente efectivo en caja. Disponible: {disponible:.2f} CUP"
        else:
            exito, msg, nuevo_saldo = actualizar_fondo(moneda, monto, "venta", conn, cursor)
            if not exito:
                conn.rollback()
                conn.close()
                return False, msg

        cursor.execute('''
            INSERT INTO salidas_efectivo (fecha, moneda, monto, descripcion, usuario)
            VALUES (?, ?, ?, ?, ?)
        ''', (fecha, moneda, monto, descripcion, sesion.usuario_actual()))
        ref_id = cursor.lastrowid
        conn.commit()
        conn.close()
        registrar_historial(
            "Salida de efectivo",
            f"{moneda} -{monto:.2f} - {descripcion or 'Sin descripción'}",
            {"moneda": moneda, "monto": monto, "descripcion": descripcion, "ref_id": ref_id}
        )
        return True, f"Salida de efectivo registrada correctamente. {moneda} -{monto:.2f}"
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"Error al registrar salida de efectivo: {str(e)}"

def obtener_fondo_hoy(moneda):
    with consulta() as (conn, cursor):
        hoy = datetime.datetime.now().strftime("%Y-%m-%d")
        cursor.execute('''
            SELECT cantidad FROM fondo_divisas
            WHERE fecha = ? AND moneda = ?
        ''', (hoy, moneda))
        fila = cursor.fetchone()
        return fila[0] if fila else 0.0

def actualizar_fondo(moneda, cantidad, tipo, conn=None, cursor=None):
    if conn is None or cursor is None:
        conn = conectar_db()
        cursor = conn.cursor()
        usar_nueva_conexion = True
    else:
        usar_nueva_conexion = False

    hoy = datetime.datetime.now().strftime("%Y-%m-%d")
    cursor.execute('''
        SELECT cantidad FROM fondo_divisas
        WHERE fecha = ? AND moneda = ?
    ''', (hoy, moneda))
    fila = cursor.fetchone()
    saldo_actual = fila[0] if fila else 0.0

    if tipo == "venta":
        nuevo_saldo = saldo_actual - cantidad
        if nuevo_saldo < 0:
            if usar_nueva_conexion:
                conn.close()
            return False, f"No hay suficiente {moneda} en caja. Disponible: {saldo_actual:.2f}", None
    elif tipo in ("compra", "entrada"):
        nuevo_saldo = saldo_actual + cantidad
    else:
        if usar_nueva_conexion:
            conn.close()
        return False, f"Tipo de operación desconocido: {tipo}", None

    if fila:
        cursor.execute('''
            UPDATE fondo_divisas
            SET cantidad = ?
            WHERE fecha = ? AND moneda = ?
        ''', (nuevo_saldo, hoy, moneda))
    else:
        cursor.execute('''
            INSERT INTO fondo_divisas (fecha, moneda, cantidad)
            VALUES (?, ?, ?)
        ''', (hoy, moneda, nuevo_saldo))

    if usar_nueva_conexion:
        conn.commit()
        conn.close()

    return True, "Fondo actualizado correctamente", nuevo_saldo

def registrar_operacion_cambio(tipo, moneda, cantidad, tasa, observaciones=""):
    conn = conectar_db()
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE")
        monto_cup = cantidad * tasa
        fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute('''
            INSERT INTO operaciones_cambio (fecha, tipo, moneda, cantidad, tasa, monto_cup, observaciones, usuario)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (fecha, tipo, moneda, cantidad, tasa, monto_cup, observaciones,
              sesion.usuario_actual()))
        ref_id = cursor.lastrowid

        exito, msg, nuevo_saldo = actualizar_fondo(moneda, cantidad, tipo, conn, cursor)
        if not exito:
            conn.rollback()
            conn.close()
            return False, msg

        if tipo == "venta":
            cursor.execute('''
                INSERT INTO entradas_efectivo (fecha, moneda, monto, descripcion, usuario)
                VALUES (?, ?, ?, ?, ?)
            ''', (fecha, "CUP", monto_cup,
                  f"Venta de {cantidad} {moneda} (tasa {tasa})",
                  sesion.usuario_actual()))

        conn.commit()
        conn.close()
        registrar_historial(
            "Cambio de Divisa",
            f"{'Compra' if tipo == 'compra' else 'Venta'} de {cantidad:.2f} {moneda} a tasa {tasa:.2f}",
            {"tipo": tipo, "moneda": moneda, "cantidad": cantidad, "tasa": tasa, "monto_cup": monto_cup, "ref_id": ref_id}
        )
        return True, f"Operación registrada exitosamente. Nuevo saldo de {moneda}: {nuevo_saldo:.2f}"
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"Error al registrar operación: {str(e)}"


# ----------------------------------------------------- movimientos del día

# Dos clases de fila de entradas_efectivo no son movimientos por sí mismas,
# sino el rastro de algo que ya se cuenta por otro lado: el cobro de una deuda
# -que vive en cobros_deudas- y la venta de divisa -que vive en
# operaciones_cambio-. Se reconocen por la descripción porque no llevan
# ninguna otra marca; las escribe cada una un único sitio del programa.
RASTRO_DE_COBRO = "Pago de deuda #%"
RASTRO_DE_CAMBIO = "Venta de % (tasa %"


def obtener_movimientos_del_dia(fecha):
    """Entradas, salidas y cambios de divisa de un día, del más nuevo al más viejo.

    Es la lista que acompaña al cuadre en la pantalla de Corte, y deja fuera
    exactamente las mismas filas que la cadena de mitienda.cuadre: si una suma
    allí, aparece aquí, y al revés.

    Una operación de cambio sale como una sola línea con sus dos lados -lo que
    entró y lo que salió-, no como dos apuntes sueltos.
    """
    fecha_like = f"{fecha}%"
    movimientos = []
    with consulta() as (conexion, cursor):
        cursor.execute('''
            SELECT id, fecha, moneda, monto, descripcion, usuario
            FROM entradas_efectivo
            WHERE fecha LIKE ?
              AND COALESCE(descripcion, '') NOT LIKE ?
              AND COALESCE(descripcion, '') NOT LIKE ?
        ''', (fecha_like, RASTRO_DE_COBRO, RASTRO_DE_CAMBIO))
        for id_mov, cuando, moneda, monto, descripcion, usuario in cursor.fetchall():
            movimientos.append({
                "id": id_mov, "fecha": cuando, "tipo": "Entrada",
                "concepto": descripcion or "Sin descripción",
                "moneda": moneda, "monto": round(monto or 0.0, 2),
                "moneda_2": None, "monto_2": 0.0,
                "usuario": usuario or "",
            })

        cursor.execute('''
            SELECT id, fecha, moneda, monto, descripcion, usuario
            FROM salidas_efectivo
            WHERE fecha LIKE ?
        ''', (fecha_like,))
        for id_mov, cuando, moneda, monto, descripcion, usuario in cursor.fetchall():
            movimientos.append({
                "id": id_mov, "fecha": cuando, "tipo": "Salida",
                "concepto": descripcion or "Sin descripción",
                "moneda": moneda, "monto": -round(monto or 0.0, 2),
                "moneda_2": None, "monto_2": 0.0,
                "usuario": usuario or "",
            })

        cursor.execute('''
            SELECT id, fecha, tipo, moneda, cantidad, tasa, monto_cup, usuario
            FROM operaciones_cambio
            WHERE fecha LIKE ?
        ''', (fecha_like,))
        for id_mov, cuando, tipo, moneda, cantidad, tasa, monto_cup, usuario in cursor.fetchall():
            es_compra = tipo == "compra"
            movimientos.append({
                "id": id_mov,
                "fecha": cuando,
                "tipo": "Compra de divisa" if es_compra else "Venta de divisa",
                "concepto": (f"{'Compra' if es_compra else 'Venta'} de "
                             f"{cantidad:.2f} {moneda} a tasa {tasa:.2f}"),
                "moneda": "CUP",
                "monto": round(-monto_cup if es_compra else monto_cup, 2),
                "moneda_2": moneda,
                "monto_2": round(cantidad if es_compra else -cantidad, 2),
                "usuario": usuario or "",
            })

    movimientos.sort(key=lambda m: (m["fecha"] or "", m["id"]), reverse=True)
    return movimientos
