"""Ventana de cobro de una deuda pendiente."""

import datetime
import json
import tkinter as tk
from tkinter import ttk

from .. import calculo_cobro as cc
from .. import calculo_deuda as cd
from ..caja import obtener_efectivo_disponible_cup
from ..rutas import consulta
from ..ventas_datos import registrar_cobro_deuda_en_db
from .estilos import COLOR_PASTILLA_ON, COLOR_TARJETA, COLOR_TOTAL


MOTIVOS_DEUDA = {
    "tasa_invalida": "Ingresa una tasa de cambio válida",
    "montos_negativos": "Los montos no pueden ser negativos",
    "divisa_solo_efectivo": "Solo se permite Efectivo para pagos en divisa",
    "mixto_solo_cup": "El pago mixto solo está disponible en CUP",
    "mixto_necesita_ambos": "Para pago mixto, ambos montos deben ser mayores que 0",
    "vuelto_negativo": "El vuelto no puede ser negativo",
    "vuelto_moneda_excede": "El vuelto en moneda no puede exceder el vuelto total.",
}


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
        ventana.configure(background=COLOR_TARJETA)

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
            """Recoge lo tecleado, pide el cálculo y guarda el abono.

            La aritmética vive en `lddl/calculo_deuda.py`. Aquí sólo quedan
            los campos, los mensajes y la comprobación de que hay efectivo en
            caja para el vuelto, que necesita la base.
            """
            try:
                abono = cd.Abono(
                    saldo_pendiente=saldo_pendiente,
                    moneda=moneda_pago.get(),
                    tasa=cc.a_numero(tasa_var.get(), 1.0)
                        if moneda_pago.get() != cd.CUP else 1.0,
                    metodo=metodo_pago.get(),
                    efectivo=cc.a_numero(monto_efectivo.get()),
                    transferencia=cc.a_numero(monto_transferencia.get()),
                    efectivo_cup=cc.a_numero(monto_efectivo_cup.get()),
                    vuelto_en_moneda=cc.a_numero(vuelto_moneda_var.get()),
                )

                cobro = cd.calcular_cobro(abono)
                if cobro.error:
                    self.mostrar_mensaje("error", "Error", MOTIVOS_DEUDA.get(
                        cobro.error, "Revisa los montos del pago"))
                    return

                # Lo único que no puede decidir el módulo: si la caja tiene
                # ese dinero para devolverlo.
                falta_en_caja = cd.vuelto_en_cup_a_entregar(cobro)
                if falta_en_caja > 0:
                    hoy = datetime.datetime.now().strftime("%Y-%m-%d")
                    disponible = obtener_efectivo_disponible_cup(hoy)
                    if falta_en_caja > disponible:
                        self.mostrar_mensaje(
                            "error", "Error",
                            f"No hay suficiente efectivo en caja para el vuelto.\n"
                            f"Vuelto requerido: {falta_en_caja:.2f} CUP\n"
                            f"Efectivo disponible: {disponible:.2f} CUP")
                        return

                mensaje_confirmacion = (
                    f"Confirmar pago de deuda:\n"
                    f"Monto total: {cobro.total_pagado_cup:.2f} CUP\n")
                if abono.en_divisa:
                    mensaje_confirmacion += (
                        f"  - {cobro.efectivo:.2f} {cobro.moneda} "
                        f"(tasa {cobro.tasa:.2f}) = {cobro.efectivo * cobro.tasa:.2f} CUP\n")
                    if cobro.efectivo_cup > 0:
                        mensaje_confirmacion += (
                            f"  - {cobro.efectivo_cup:.2f} CUP (efectivo adicional)\n")
                else:
                    mensaje_confirmacion += f"Método: {cobro.metodo}\n"
                    if cobro.metodo == cd.MIXTO:
                        mensaje_confirmacion += f"  - Efectivo: {cobro.efectivo:.2f} CUP\n"
                        mensaje_confirmacion += f"  - Transferencia: {cobro.transferencia:.2f} CUP\n"
                    else:
                        mensaje_confirmacion += f"Monto: {cobro.total_pagado_moneda:.2f} CUP\n"
                mensaje_confirmacion += f"Saldo pendiente original: {saldo_pendiente:.2f} CUP\n"
                mensaje_confirmacion += f"{'Pago parcial' if cobro.pagada == 0 else 'Pago total'}\n"
                if cobro.vuelto_cup > 0:
                    mensaje_confirmacion += f"Vuelto: {cobro.vuelto_cup:.2f} CUP"
                    if cobro.vuelto_moneda > 0:
                        mensaje_confirmacion += f" (en {cobro.moneda}: {cobro.vuelto_moneda:.2f})"

                if not self.mostrar_mensaje("yesno", "Confirmar", mensaje_confirmacion):
                    return

                try:
                    fecha_pago = (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                  if cobro.pagada == 1 else None)

                    exito_cobro, msg_cobro = registrar_cobro_deuda_en_db(venta_id, {
                        "moneda": cobro.moneda,
                        "tasa": cobro.tasa,
                        "metodo": cobro.metodo,
                        "efectivo": cobro.efectivo,
                        "transferencia": cobro.transferencia,
                        "efectivo_cup": cobro.efectivo_cup,
                        "vuelto_cup": cobro.vuelto_cup,
                        "vuelto_moneda": cobro.vuelto_moneda,
                        "total_pagado_moneda": cobro.total_pagado_moneda,
                        "total_pagado_cup": cobro.total_pagado_cup,
                        "nuevo_saldo": cobro.nuevo_saldo,
                        "pagada": cobro.pagada,
                        "fecha_pago": fecha_pago,
                        "metodo_pago_real": cobro.metodo_pago_real,
                        "observaciones": cd.observaciones_del_cobro(obs_actual, cobro).strip(),
                    })
                    if not exito_cobro:
                        raise Exception(msg_cobro)

                    self.mostrar_mensaje("info", "Éxito", cd.resumen_del_cobro(cobro))
                    ventana.destroy()
                    self.cargar_ventas()
                    for item in self.tabla_detalle.get_children():
                        self.tabla_detalle.delete(item)
                    self.frame_detalle_venta.config(text="DETALLE")
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
        main_frame = ttk.Frame(ventana, padding=18)
        main_frame.pack(fill="both", expand=True)

        ttk.Label(main_frame, text=f"Deuda #{venta_id}", style="Titulo.TLabel").pack(pady=(0, 8))
        ttk.Label(main_frame, text=f"Total: {total:.2f} CUP").pack(anchor="w", pady=2)
        ttk.Label(main_frame, text=f"Saldo pendiente: {saldo_pendiente:.2f} CUP", font=("Segoe UI", 9, "bold"), foreground=COLOR_TOTAL).pack(anchor="w", pady=2)
        
        if es_deuda_del_dia:
            ttk.Label(main_frame, text="Deuda del día actual", foreground="#2E9E6B").pack(anchor="w", pady=2)
        else:
            ttk.Label(main_frame, text="Deuda de días anteriores", foreground=COLOR_PASTILLA_ON).pack(anchor="w", pady=2)
        
        ttk.Separator(main_frame, orient="horizontal").pack(fill="x", pady=10)

        # Moneda y Tasa
        frame_moneda = ttk.Frame(main_frame)
        frame_moneda.pack(fill="x", pady=5)
        ttk.Label(frame_moneda, text="Moneda:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
        combo_moneda = ttk.Combobox(frame_moneda, textvariable=moneda_pago, values=["CUP", "USD", "EUR"], state="readonly", width=8)
        combo_moneda.pack(side="left", padx=5)
        combo_moneda.bind("<<ComboboxSelected>>", actualizar_moneda)
        ttk.Label(frame_moneda, text="Tasa (CUP):", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(14, 6))
        entry_tasa = ttk.Entry(frame_moneda, textvariable=tasa_var, width=10)
        entry_tasa.pack(side="left", padx=5)
        entry_tasa.config(state="disabled")

        # Método de pago
        frame_metodo = ttk.Frame(main_frame)
        frame_metodo.pack(fill="x", pady=5)
        ttk.Label(frame_metodo, text="Método de pago:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
        radio_efectivo = ttk.Radiobutton(frame_metodo, text="Efectivo", variable=metodo_pago, value="Efectivo", command=actualizar_metodo)
        radio_efectivo.pack(side="left", padx=5)
        radio_transferencia = ttk.Radiobutton(frame_metodo, text="Transferencia", variable=metodo_pago, value="Transferencia", command=actualizar_metodo)
        radio_transferencia.pack(side="left", padx=5)
        radio_mixto = ttk.Radiobutton(frame_metodo, text="Mixto", variable=metodo_pago, value="Mixto", command=actualizar_metodo)
        radio_mixto.pack(side="left", padx=5)

        # Campos de montos
        frame_montos = ttk.Frame(main_frame)
        frame_montos.pack(fill="x", pady=5)
        
        # Efectivo (USD/EUR o CUP)
        label_efectivo = ttk.Label(frame_montos, text="Efectivo:")
        label_efectivo.pack(side="left", padx=5)
        entry_efectivo = ttk.Entry(frame_montos, textvariable=monto_efectivo, width=12)
        entry_efectivo.pack(side="left", padx=5)
        entry_efectivo.bind("<KeyRelease>", calcular_vuelto)
        label_moneda_efectivo = ttk.Label(frame_montos, text="CUP")
        label_moneda_efectivo.pack(side="left", padx=2)

        # Efectivo CUP (solo para pago en USD/EUR)
        label_efectivo_cup = ttk.Label(frame_montos, text="")
        label_efectivo_cup.pack(side="left", padx=(20, 5))
        entry_efectivo_cup = ttk.Entry(frame_montos, textvariable=monto_efectivo_cup, width=12, state="disabled")
        entry_efectivo_cup.pack(side="left", padx=5)
        entry_efectivo_cup.bind("<KeyRelease>", calcular_vuelto)
        label_moneda_efectivo_cup = ttk.Label(frame_montos, text="CUP")
        label_moneda_efectivo_cup.pack(side="left", padx=2)

        # Transferencia
        ttk.Label(frame_montos, text="Transferencia:").pack(side="left", padx=(20, 5))
        entry_transferencia = ttk.Entry(frame_montos, textvariable=monto_transferencia, width=12, state="disabled")
        entry_transferencia.pack(side="left", padx=5)
        entry_transferencia.bind("<KeyRelease>", calcular_vuelto)
        label_moneda_transferencia = ttk.Label(frame_montos, text="CUP")
        label_moneda_transferencia.pack(side="left", padx=2)

        # Vuelto
        frame_vuelto = ttk.Frame(main_frame)
        frame_vuelto.pack(fill="x", pady=10)
        ttk.Label(frame_vuelto, text="Vuelto:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
        label_vuelto = ttk.Label(frame_vuelto, text="0.00 CUP", style="CifraVerde.TLabel")
        label_vuelto.pack(side="left", padx=5)
        label_vuelto_moneda = ttk.Label(frame_vuelto, text="")
        label_vuelto_moneda.pack(side="left", padx=5)

        # Opciones de vuelto en moneda
        frame_vuelto_opciones = ttk.Frame(main_frame)
        frame_vuelto_opciones.pack(fill="x", pady=5)
        ttk.Label(frame_vuelto_opciones, text="Vuelto en moneda:").pack(side="left", padx=(0, 6))
        entry_vuelto_moneda = ttk.Entry(frame_vuelto_opciones, textvariable=vuelto_moneda_var, width=10, state="disabled")
        entry_vuelto_moneda.pack(side="left", padx=5)
        entry_vuelto_moneda.bind("<KeyRelease>", calcular_vuelto)
        label_vuelto_moneda_entry = ttk.Label(frame_vuelto_opciones, text="")
        label_vuelto_moneda_entry.pack(side="left", padx=2)

        # Botones de denominaciones
        frame_denominaciones = ttk.Frame(main_frame)
        frame_denominaciones.pack(fill="x", pady=5)
        for valor in [1, 5, 10, 20, 50]:
            ttk.Button(frame_denominaciones, text=f"+{valor}", command=lambda v=valor: agregar_denominacion(v),
                       style="Quick.TButton", width=4).pack(side="left", padx=2)

        # Botones de acción
        frame_botones = ttk.Frame(main_frame)
        frame_botones.pack(pady=20)
        ttk.Button(frame_botones, text="Guardar", command=guardar_pago, style="Success.TButton", width=12).pack(side="left", padx=10)
        ttk.Button(frame_botones, text="Cancelar", command=cancelar_pago, style="Danger.TButton", width=12).pack(side="left", padx=10)

        # Inicializar la interfaz
        actualizar_moneda()
        actualizar_metodo()
