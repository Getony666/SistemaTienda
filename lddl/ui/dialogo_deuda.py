"""Ventana de cobro de una deuda pendiente."""

import datetime
import json
import tkinter as tk
from tkinter import ttk

from ..caja import obtener_efectivo_disponible_cup
from ..rutas import consulta
from ..ventas_datos import registrar_cobro_deuda_en_db


class DialogoDeudaMixin:
    """Ventana para cobrar una deuda pendiente."""

    def pagar_deuda(self):
        seleccion = self.tabla_ventas.selection()
        if not seleccion:
            self.mostrar_mensaje("warning", "Advertencia", "Selecciona una deuda de la lista")
            return

        valores = self.tabla_ventas.item(seleccion[0])['values']
        tipo = valores[2]
        venta_id = None

        if tipo == "Deuda" or tipo == "Venta":
            venta_id = int(valores[0]) if str(valores[0]).isdigit() else None
        elif tipo == "Salida de Producto":
            id_hist = int(valores[0]) if str(valores[0]).isdigit() else None
            if id_hist:
                with consulta() as (conn, cursor):
                    cursor.execute("SELECT detalles FROM historial WHERE id=?", (id_hist,))
                    fila = cursor.fetchone()
                if fila:
                    try:
                        detalles = json.loads(fila[0])
                        venta_id = detalles.get("venta_id")
                    except:
                        pass
        else:
            self.mostrar_mensaje("warning", "Advertencia", "El registro seleccionado no es una deuda válida.")
            return

        if not venta_id:
            self.mostrar_mensaje("error", "Error", "No se pudo identificar la deuda.")
            return

        with consulta() as (conn, cursor):
            cursor.execute('''
                SELECT es_deuda, pagada, saldo_pendiente, total, observaciones, fecha
                FROM ventas
                WHERE id = ?
            ''', (venta_id,))
            fila = cursor.fetchone()

        if not fila:
            self.mostrar_mensaje("error", "Error", "Venta no encontrada")
            return

        es_deuda, pagada, saldo_pendiente, total, obs_actual, fecha_venta = fila

        if es_deuda != 1:
            self.mostrar_mensaje("warning", "Aviso", "Esta venta no es una deuda")
            return
        if pagada == 1:
            self.mostrar_mensaje("info", "Información", "Esta deuda ya está pagada")
            return

        # Determinar si la deuda es del día actual
        fecha_venta_str = fecha_venta.split()[0] if fecha_venta else ""
        fecha_hoy = datetime.datetime.now().strftime("%Y-%m-%d")
        es_deuda_del_dia = (fecha_venta_str == fecha_hoy)

        ventana = tk.Toplevel(self.root)
        ventana.title("Pagar Deuda")
        ventana.geometry("700x800")
        ventana.resizable(False, False)
        ventana.transient(self.root)
        ventana.grab_set()

        moneda_pago = tk.StringVar(value="CUP")
        tasa_var = tk.StringVar(value="1.00")
        metodo_pago = tk.StringVar(value="Efectivo")
        monto_efectivo = tk.StringVar()  # Monto en USD/EUR
        monto_efectivo_cup = tk.StringVar()  # Monto en CUP adicional
        monto_transferencia = tk.StringVar()
        vuelto_moneda_var = tk.StringVar()
        vuelto_total_cup = 0.0
        deuda_restante_cup = saldo_pendiente  # Para cálculos en tiempo real

        def actualizar_moneda(*args):
            nonlocal deuda_restante_cup
            moneda = moneda_pago.get()
            if moneda == "CUP":
                entry_tasa.config(state="disabled")
                tasa_var.set("1.00")
                radio_efectivo.config(state="normal")
                radio_transferencia.config(state="normal")
                radio_mixto.config(state="normal")
                if metodo_pago.get() == "Mixto":
                    entry_efectivo.config(state="normal")
                    entry_efectivo_cup.config(state="disabled")
                    entry_transferencia.config(state="normal")
                else:
                    entry_efectivo.config(state="normal" if metodo_pago.get() == "Efectivo" else "disabled")
                    entry_efectivo_cup.config(state="disabled")
                    entry_transferencia.config(state="normal" if metodo_pago.get() == "Transferencia" else "disabled")
                # Limpiar el campo de CUP adicional
                monto_efectivo_cup.set("")
                label_efectivo.config(text="Efectivo:")
                label_efectivo_cup.config(text="")
                entry_efectivo_cup.config(state="disabled")
            else:
                entry_tasa.config(state="normal")
                tasa_var.set("")
                metodo_pago.set("Efectivo")
                radio_efectivo.config(state="normal")
                radio_transferencia.config(state="disabled")
                radio_mixto.config(state="disabled")
                entry_efectivo.config(state="normal")
                entry_efectivo_cup.config(state="normal")
                entry_transferencia.config(state="disabled")
                monto_efectivo.set("")
                monto_transferencia.set("")
                monto_efectivo_cup.set("")
                label_efectivo.config(text=f"Efectivo ({moneda}):")
                label_efectivo_cup.config(text="Efectivo (CUP):")
            label_moneda_efectivo.config(text=moneda if moneda != "CUP" else "CUP")
            label_moneda_transferencia.config(text=moneda if moneda != "CUP" else "CUP")
            label_vuelto_moneda.config(text=moneda if moneda != "CUP" else "CUP")
            label_vuelto_moneda_entry.config(text=moneda if moneda != "CUP" else "CUP")
            entry_vuelto_moneda.config(state="normal" if moneda != "CUP" else "disabled")
            calcular_vuelto()

        def actualizar_metodo():
            metodo = metodo_pago.get()
            moneda = moneda_pago.get()
            if moneda != "CUP":
                return
            if metodo == "Mixto":
                entry_efectivo.config(state="normal")
                entry_efectivo_cup.config(state="disabled")
                entry_transferencia.config(state="normal")
                monto_efectivo.set("")
                monto_transferencia.set("")
                monto_efectivo_cup.set("")
            elif metodo == "Efectivo":
                entry_efectivo.config(state="normal")
                entry_efectivo_cup.config(state="disabled")
                entry_transferencia.config(state="disabled")
                monto_transferencia.set("")
                monto_efectivo_cup.set("")
            else:
                entry_efectivo.config(state="disabled")
                entry_efectivo_cup.config(state="disabled")
                entry_transferencia.config(state="normal")
                monto_efectivo.set("")
                monto_efectivo_cup.set("")
            calcular_vuelto()

        def calcular_vuelto(event=None):
            nonlocal vuelto_total_cup, deuda_restante_cup
            try:
                moneda = moneda_pago.get()
                tasa = float(tasa_var.get()) if moneda != "CUP" else 1.0
                if moneda != "CUP" and tasa <= 0:
                    label_vuelto.config(text="Tasa inválida")
                    return
                
                efectivo_text = monto_efectivo.get().strip()
                transferencia_text = monto_transferencia.get().strip()
                efectivo_cup_text = monto_efectivo_cup.get().strip()
                
                efectivo = float(efectivo_text) if efectivo_text else 0.0
                transferencia = float(transferencia_text) if transferencia_text else 0.0
                efectivo_cup = float(efectivo_cup_text) if efectivo_cup_text else 0.0
                
                # Calcular pago total en CUP
                if moneda != "CUP":
                    # Para moneda extranjera: pago en USD/EUR + CUP adicional
                    total_pagado_cup = (efectivo * tasa) + efectivo_cup + transferencia
                    deuda_restante_cup = saldo_pendiente - (efectivo * tasa)
                    
                    # Auto-calcular el monto en CUP si es necesario
                    if efectivo > 0 and not efectivo_cup_text:
                        # Si el pago en USD no cubre toda la deuda, calcular automáticamente el resto en CUP
                        if deuda_restante_cup > 0:
                            monto_efectivo_cup.set(f"{deuda_restante_cup:.2f}")
                            # Recalcular con el nuevo valor
                            efectivo_cup = deuda_restante_cup
                            total_pagado_cup = (efectivo * tasa) + efectivo_cup + transferencia
                        else:
                            monto_efectivo_cup.set("0.00")
                            entry_efectivo_cup.config(state="disabled")
                    elif efectivo > 0 and efectivo_cup_text:
                        # Validar que el monto en CUP no exceda la deuda restante
                        if deuda_restante_cup > 0 and efectivo_cup > deuda_restante_cup:
                            self.mostrar_mensaje("error", "Error", 
                                f"El monto en CUP ({efectivo_cup:.2f}) excede la deuda restante ({deuda_restante_cup:.2f})")
                            monto_efectivo_cup.set(f"{deuda_restante_cup:.2f}")
                            efectivo_cup = deuda_restante_cup
                            total_pagado_cup = (efectivo * tasa) + efectivo_cup + transferencia
                else:
                    # Para CUP: efectivo + transferencia
                    total_pagado_cup = efectivo + transferencia
                    deuda_restante_cup = saldo_pendiente - total_pagado_cup
                
                if total_pagado_cup < saldo_pendiente:
                    vuelto_cup = 0.0
                    label_vuelto.config(text="Pago parcial, sin vuelto")
                    label_vuelto_moneda.config(text="")
                    entry_vuelto_moneda.config(state="disabled")
                    vuelto_moneda_var.set("")
                    vuelto_total_cup = 0.0
                    return

                vuelto_cup = total_pagado_cup - saldo_pendiente
                vuelto_total_cup = vuelto_cup
                
                if vuelto_cup > 0:
                    if moneda != "CUP":
                        vuelto_moneda_text = vuelto_moneda_var.get().strip()
                        vuelto_moneda = float(vuelto_moneda_text) if vuelto_moneda_text else 0.0
                        vuelto_moneda_cup = vuelto_moneda * tasa
                        
                        resto_cup = vuelto_total_cup - vuelto_moneda_cup
                        if vuelto_moneda > 0 and resto_cup > 0:
                            label_vuelto.config(text=f"{vuelto_moneda:.2f} {moneda} + {resto_cup:.2f} CUP")
                        elif vuelto_moneda > 0:
                            label_vuelto.config(text=f"{vuelto_moneda:.2f} {moneda}")
                        else:
                            label_vuelto.config(text=f"{vuelto_total_cup:.2f} CUP")
                        
                        label_vuelto_moneda.config(text=moneda)
                        entry_vuelto_moneda.config(state="normal")
                    else:
                        vuelto_moneda_var.set("")
                        label_vuelto.config(text=f"{vuelto_cup:.2f} CUP")
                        label_vuelto_moneda.config(text="CUP")
                        entry_vuelto_moneda.config(state="disabled")
                else:
                    label_vuelto.config(text="0.00 CUP")
                    label_vuelto_moneda.config(text="CUP")
                    entry_vuelto_moneda.config(state="disabled")
                    vuelto_moneda_var.set("")
            except ValueError:
                label_vuelto.config(text="Error en los montos")
                label_vuelto_moneda.config(text="")
                vuelto_total_cup = 0.0

        def agregar_denominacion(valor):
            if moneda_pago.get() == "CUP":
                return
            actual = vuelto_moneda_var.get().strip()
            try:
                nuevo = (float(actual) if actual else 0.0) + valor
            except ValueError:
                nuevo = valor

            moneda = moneda_pago.get()
            tasa = float(tasa_var.get() or "1.0")
            vuelto_moneda_cup = nuevo * tasa

            if vuelto_moneda_cup > vuelto_total_cup:
                self.mostrar_mensaje("error", "Error", "El vuelto en moneda no puede exceder el vuelto total.")
                return

            vuelto_moneda_var.set(f"{nuevo:.2f}")
            calcular_vuelto()

        def guardar_pago():
            try:
                moneda = moneda_pago.get()
                tasa = float(tasa_var.get()) if moneda != "CUP" else 1.0
                if moneda != "CUP" and tasa <= 0:
                    self.mostrar_mensaje("error", "Error", "Ingresa una tasa de cambio válida")
                    return

                efectivo_text = monto_efectivo.get().strip()
                transferencia_text = monto_transferencia.get().strip()
                efectivo_cup_text = monto_efectivo_cup.get().strip()
                
                efectivo = float(efectivo_text) if efectivo_text else 0.0
                transferencia = float(transferencia_text) if transferencia_text else 0.0
                efectivo_cup = float(efectivo_cup_text) if efectivo_cup_text else 0.0

                if efectivo < 0 or transferencia < 0 or efectivo_cup < 0:
                    self.mostrar_mensaje("error", "Error", "Los montos no pueden ser negativos")
                    return

                metodo = metodo_pago.get()
                
                # Validar método de pago
                if moneda != "CUP" and metodo != "Efectivo":
                    self.mostrar_mensaje("error", "Error", "Solo se permite Efectivo para pagos en divisa")
                    return
                if metodo == "Mixto" and moneda != "CUP":
                    self.mostrar_mensaje("error", "Error", "El pago mixto solo está disponible en CUP")
                    return
                if metodo == "Mixto" and (efectivo <= 0 or transferencia <= 0):
                    self.mostrar_mensaje("error", "Error", "Para pago mixto, ambos montos deben ser mayores que 0")
                    return
                
                # Calcular total pagado
                if moneda != "CUP":
                    total_pagado_moneda = efectivo  # Solo el monto en divisa
                    total_pagado_cup = (efectivo * tasa) + efectivo_cup
                    # Si se usó CUP adicional, considerarlo como efectivo
                    if efectivo_cup > 0:
                        metodo = "Efectivo"  # Se registra como efectivo en CUP
                else:
                    if metodo == "Mixto":
                        total_pagado_moneda = efectivo + transferencia
                    else:
                        total_pagado_moneda = efectivo if metodo == "Efectivo" else transferencia
                    total_pagado_cup = total_pagado_moneda

                if total_pagado_cup < saldo_pendiente:
                    nuevo_saldo = saldo_pendiente - total_pagado_cup
                    pagada = 0
                    fecha_pago = None
                    mensaje_exito = f"Pago parcial registrado.\nSaldo restante: {nuevo_saldo:.2f} CUP"
                    vuelto_cup = 0.0
                    vuelto_moneda = 0.0
                else:
                    nuevo_saldo = 0.0
                    pagada = 1
                    fecha_pago = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    vuelto_cup = total_pagado_cup - saldo_pendiente
                    if moneda != "CUP":
                        try:
                            vuelto_moneda = float(vuelto_moneda_var.get().strip() or "0")
                            vuelto_moneda_cup = vuelto_moneda * tasa
                            if vuelto_moneda_cup > vuelto_cup:
                                self.mostrar_mensaje("error", "Error", "El vuelto en moneda no puede exceder el vuelto total.")
                                return
                        except ValueError:
                            self.mostrar_mensaje("error", "Error", "Ingresa un número válido para el vuelto en moneda")
                            return
                    else:
                        vuelto_moneda = 0.0
                    mensaje_exito = f"Deuda pagada completamente.\nVuelto: {vuelto_cup:.2f} CUP" + (f" (en {moneda}: {vuelto_moneda:.2f})" if vuelto_moneda > 0 else "")

                # Validar vuelto en CUP
                if vuelto_cup > 0:
                    fecha_actual_corta = datetime.datetime.now().strftime("%Y-%m-%d")
                    efectivo_disponible = obtener_efectivo_disponible_cup(fecha_actual_corta)
                    vuelto_cup_restante = vuelto_cup - (vuelto_moneda * tasa) if vuelto_moneda > 0 else vuelto_cup
                    if vuelto_cup_restante > efectivo_disponible:
                        self.mostrar_mensaje("error", "Error", 
                            f"No hay suficiente efectivo en caja para el vuelto.\n"
                            f"Vuelto requerido: {vuelto_cup_restante:.2f} CUP\n"
                            f"Efectivo disponible: {efectivo_disponible:.2f} CUP")
                        return

                # Construir mensaje de confirmación
                mensaje_confirmacion = f"Confirmar pago de deuda:\nMonto total: {total_pagado_cup:.2f} CUP\n"
                if moneda != "CUP":
                    mensaje_confirmacion += f"  - {efectivo:.2f} {moneda} (tasa {tasa:.2f}) = {efectivo * tasa:.2f} CUP\n"
                    if efectivo_cup > 0:
                        mensaje_confirmacion += f"  - {efectivo_cup:.2f} CUP (efectivo adicional)\n"
                else:
                    mensaje_confirmacion += f"Método: {metodo}\n"
                    if metodo == "Mixto":
                        mensaje_confirmacion += f"  - Efectivo: {efectivo:.2f} CUP\n"
                        mensaje_confirmacion += f"  - Transferencia: {transferencia:.2f} CUP\n"
                    else:
                        mensaje_confirmacion += f"Monto: {total_pagado_moneda:.2f} CUP\n"
                
                mensaje_confirmacion += f"Saldo pendiente original: {saldo_pendiente:.2f} CUP\n"
                mensaje_confirmacion += f"{'Pago parcial' if pagada == 0 else 'Pago total'}\n"
                if vuelto_cup > 0:
                    mensaje_confirmacion += f"Vuelto: {vuelto_cup:.2f} CUP" + (f" (en {moneda}: {vuelto_moneda:.2f})" if vuelto_moneda > 0 else "")
                
                if not self.mostrar_mensaje("yesno", "Confirmar", mensaje_confirmacion):
                    return

                try:
                    # Actualizar observaciones de la venta
                    observaciones = obs_actual or ""
                    if pagada == 1:
                        observaciones += f" | Pagada totalmente (abonado {total_pagado_cup:.2f} CUP)"
                    else:
                        observaciones += f" | Pago parcial de {total_pagado_cup:.2f} CUP, saldo restante {nuevo_saldo:.2f} CUP"
                    
                    metodo_pago_real = metodo if metodo != "Mixto" else "Mixto"
                    if moneda != "CUP" and efectivo_cup > 0:
                        metodo_pago_real = "Mixto (USD+CUP)"

                    exito_cobro, msg_cobro = registrar_cobro_deuda_en_db(venta_id, {
                        "moneda": moneda,
                        "tasa": tasa,
                        "metodo": metodo,
                        "efectivo": efectivo,
                        "transferencia": transferencia,
                        "efectivo_cup": efectivo_cup,
                        "vuelto_cup": vuelto_cup,
                        "vuelto_moneda": vuelto_moneda,
                        "total_pagado_moneda": total_pagado_moneda,
                        "total_pagado_cup": total_pagado_cup,
                        "nuevo_saldo": nuevo_saldo,
                        "pagada": pagada,
                        "fecha_pago": fecha_pago,
                        "metodo_pago_real": metodo_pago_real,
                        "observaciones": observaciones.strip(),
                    })
                    if not exito_cobro:
                        raise Exception(msg_cobro)

                    self.mostrar_mensaje("info", "Éxito", mensaje_exito)
                    ventana.destroy()
                    self.cargar_ventas()
                    for item in self.tabla_detalle.get_children():
                        self.tabla_detalle.delete(item)
                    self.frame_detalle_venta.config(text="Detalle")
                    self.label_info.config(text="Selecciona un registro de la lista para ver detalle")
                    self.actualizar_saldo_cambio()
                    if self.panel_corte_visible:
                        self.cargar_resumen_corte()
                except Exception as e:
                    self.mostrar_mensaje("error", "Error", f"Error al procesar el pago: {str(e)}")
            except Exception as e:
                self.mostrar_mensaje("error", "Error", f"Error inesperado: {str(e)}")

        def cancelar_pago():
            ventana.destroy()

        # ============ INTERFAZ GRÁFICA ============
        main_frame = tk.Frame(ventana, padx=20, pady=20)
        main_frame.pack(fill="both", expand=True)

        tk.Label(main_frame, text=f"Deuda #{venta_id}", font=("Arial", 14, "bold")).pack(pady=5)
        tk.Label(main_frame, text=f"Total: {total:.2f} CUP", font=("Arial", 10)).pack(anchor="w", pady=2)
        tk.Label(main_frame, text=f"Saldo pendiente: {saldo_pendiente:.2f} CUP", font=("Arial", 10, "bold"), fg="blue").pack(anchor="w", pady=2)
        
        if es_deuda_del_dia:
            tk.Label(main_frame, text="Deuda del día actual", font=("Arial", 9), fg="green").pack(anchor="w", pady=2)
        else:
            tk.Label(main_frame, text="Deuda de días anteriores", font=("Arial", 9), fg="orange").pack(anchor="w", pady=2)
        
        tk.Frame(main_frame, height=2, bg="gray").pack(fill="x", pady=10)

        # Moneda y Tasa
        frame_moneda = tk.Frame(main_frame)
        frame_moneda.pack(fill="x", pady=5)
        tk.Label(frame_moneda, text="Moneda:", font=("Arial", 10, "bold")).pack(side="left", padx=5)
        combo_moneda = ttk.Combobox(frame_moneda, textvariable=moneda_pago, values=["CUP", "USD", "EUR"], state="readonly", width=8)
        combo_moneda.pack(side="left", padx=5)
        combo_moneda.bind("<<ComboboxSelected>>", actualizar_moneda)
        tk.Label(frame_moneda, text="Tasa (CUP):", font=("Arial", 10, "bold")).pack(side="left", padx=5)
        entry_tasa = tk.Entry(frame_moneda, textvariable=tasa_var, width=10)
        entry_tasa.pack(side="left", padx=5)
        entry_tasa.config(state="disabled")

        # Método de pago
        frame_metodo = tk.Frame(main_frame)
        frame_metodo.pack(fill="x", pady=5)
        tk.Label(frame_metodo, text="Método de pago:", font=("Arial", 10, "bold")).pack(side="left", padx=5)
        radio_efectivo = tk.Radiobutton(frame_metodo, text="Efectivo", variable=metodo_pago, value="Efectivo", command=actualizar_metodo)
        radio_efectivo.pack(side="left", padx=5)
        radio_transferencia = tk.Radiobutton(frame_metodo, text="Transferencia", variable=metodo_pago, value="Transferencia", command=actualizar_metodo)
        radio_transferencia.pack(side="left", padx=5)
        radio_mixto = tk.Radiobutton(frame_metodo, text="Mixto", variable=metodo_pago, value="Mixto", command=actualizar_metodo)
        radio_mixto.pack(side="left", padx=5)

        # Campos de montos
        frame_montos = tk.Frame(main_frame)
        frame_montos.pack(fill="x", pady=5)
        
        # Efectivo (USD/EUR o CUP)
        label_efectivo = tk.Label(frame_montos, text="Efectivo:", font=("Arial", 10))
        label_efectivo.pack(side="left", padx=5)
        entry_efectivo = tk.Entry(frame_montos, textvariable=monto_efectivo, width=12)
        entry_efectivo.pack(side="left", padx=5)
        entry_efectivo.bind("<KeyRelease>", calcular_vuelto)
        label_moneda_efectivo = tk.Label(frame_montos, text="CUP", font=("Arial", 10))
        label_moneda_efectivo.pack(side="left", padx=2)

        # Efectivo CUP (solo para pago en USD/EUR)
        label_efectivo_cup = tk.Label(frame_montos, text="", font=("Arial", 10))
        label_efectivo_cup.pack(side="left", padx=(20, 5))
        entry_efectivo_cup = tk.Entry(frame_montos, textvariable=monto_efectivo_cup, width=12, state="disabled")
        entry_efectivo_cup.pack(side="left", padx=5)
        entry_efectivo_cup.bind("<KeyRelease>", calcular_vuelto)
        label_moneda_efectivo_cup = tk.Label(frame_montos, text="CUP", font=("Arial", 10))
        label_moneda_efectivo_cup.pack(side="left", padx=2)

        # Transferencia
        tk.Label(frame_montos, text="Transferencia:", font=("Arial", 10)).pack(side="left", padx=(20, 5))
        entry_transferencia = tk.Entry(frame_montos, textvariable=monto_transferencia, width=12, state="disabled")
        entry_transferencia.pack(side="left", padx=5)
        entry_transferencia.bind("<KeyRelease>", calcular_vuelto)
        label_moneda_transferencia = tk.Label(frame_montos, text="CUP", font=("Arial", 10))
        label_moneda_transferencia.pack(side="left", padx=2)

        # Vuelto
        frame_vuelto = tk.Frame(main_frame)
        frame_vuelto.pack(fill="x", pady=10)
        tk.Label(frame_vuelto, text="Vuelto:", font=("Arial", 10, "bold")).pack(side="left", padx=5)
        label_vuelto = tk.Label(frame_vuelto, text="0.00 CUP", font=("Arial", 12, "bold"), fg="green")
        label_vuelto.pack(side="left", padx=5)
        label_vuelto_moneda = tk.Label(frame_vuelto, text="", font=("Arial", 10))
        label_vuelto_moneda.pack(side="left", padx=5)

        # Opciones de vuelto en moneda
        frame_vuelto_opciones = tk.Frame(main_frame)
        frame_vuelto_opciones.pack(fill="x", pady=5)
        tk.Label(frame_vuelto_opciones, text="Vuelto en moneda:", font=("Arial", 10)).pack(side="left", padx=5)
        entry_vuelto_moneda = tk.Entry(frame_vuelto_opciones, textvariable=vuelto_moneda_var, width=10, state="disabled")
        entry_vuelto_moneda.pack(side="left", padx=5)
        entry_vuelto_moneda.bind("<KeyRelease>", calcular_vuelto)
        label_vuelto_moneda_entry = tk.Label(frame_vuelto_opciones, text="", font=("Arial", 10))
        label_vuelto_moneda_entry.pack(side="left", padx=2)

        # Botones de denominaciones
        frame_denominaciones = tk.Frame(main_frame)
        frame_denominaciones.pack(fill="x", pady=5)
        for valor in [1, 5, 10, 20, 50]:
            tk.Button(frame_denominaciones, text=f"+{valor}", command=lambda v=valor: agregar_denominacion(v), 
                    bg="#E0E0E0", fg="black", font=("Arial", 8, "bold"), width=4, relief="raised", bd=2).pack(side="left", padx=1)

        # Botones de acción
        frame_botones = tk.Frame(main_frame)
        frame_botones.pack(pady=20)
        tk.Button(frame_botones, text="Guardar", command=guardar_pago, bg="#4CAF50", fg="white", width=12).pack(side="left", padx=10)
        tk.Button(frame_botones, text="Cancelar", command=cancelar_pago, bg="#f44336", fg="white", width=12).pack(side="left", padx=10)

        # Inicializar la interfaz
        actualizar_moneda()
        actualizar_metodo()
