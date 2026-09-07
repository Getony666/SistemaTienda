"""Panel de corte de caja y exportación del resumen."""

import datetime
try:
    import pandas as pd
except ImportError:  # sólo hace falta para exportar a Excel
    pd = None
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ..caja import cargar_fondo_por_fecha, guardar_fondo_por_fecha, obtener_resumen_caja
from .estilos import COLOR_TARJETA, COLOR_TEXTO, COLOR_TEXTO_SUAVE, COLORES_CORTE


class PanelCorteMixin:
    """Corte de caja del día y exportación del resumen."""

    def crear_panel_corte_caja(self):
        self.frame_contenido_corte = ttk.Frame(self.scrollable_frame, style="Lienzo.TFrame")
        frame_fecha = ttk.LabelFrame(self.frame_contenido_corte, text="SELECCIONAR FECHA", padding=7)
        frame_fecha.pack(fill="x", padx=8, pady=3)
        frame_fecha_interno = ttk.Frame(frame_fecha)
        frame_fecha_interno.pack(fill="x")
        ttk.Label(frame_fecha_interno, text="Fecha:").pack(side="left", padx=(0, 6))
        self.entry_corte_fecha = ttk.Entry(frame_fecha_interno, textvariable=self.corte_fecha_var, width=15)
        self.entry_corte_fecha.pack(side="left", padx=5)
        self.entry_corte_fecha.bind("<Key-Return>", lambda event: self.cambiar_fecha_corte())
        ttk.Button(frame_fecha_interno, text="Hoy", command=self.ir_a_hoy_corte, style="Primary.TButton", width=10).pack(side="left", padx=4)
        ttk.Button(frame_fecha_interno, text="Ayer", command=self.ir_a_ayer_corte, style="Neutro.TButton", width=10).pack(side="left", padx=4)
        ttk.Button(frame_fecha_interno, text="Actualizar", command=self.cargar_resumen_corte, style="Success.TButton", width=12).pack(side="left", padx=4)

        frame_fondo = ttk.LabelFrame(self.frame_contenido_corte, text="FONDO DE CAJA DEL DÍA", padding=7)
        frame_fondo.pack(fill="x", padx=8, pady=3)
        frame_fondo_interno = ttk.Frame(frame_fondo)
        frame_fondo_interno.pack(fill="x")
        ttk.Label(frame_fondo_interno, text="Fondo (CUP):").pack(side="left", padx=(0, 6))
        self.entry_corte_fondo = ttk.Entry(frame_fondo_interno, textvariable=self.corte_fondo_var, width=15)
        self.entry_corte_fondo.pack(side="left", padx=5)
        self.entry_corte_fondo.bind("<Key-Return>", lambda event: self.guardar_fondo_corte())
        ttk.Button(frame_fondo_interno, text="Añadir / Guardar", command=self.guardar_fondo_corte, style="Purple.TButton", width=16).pack(side="left", padx=4)
        ttk.Button(frame_fondo_interno, text="Limpiar", command=self.limpiar_fondo_corte, style="Danger.TButton", width=10).pack(side="left", padx=4)
        self.label_corte_fondo_status = ttk.Label(frame_fondo_interno, text="", foreground=COLOR_TEXTO_SUAVE, font=("Segoe UI", 8))
        self.label_corte_fondo_status.pack(side="left", padx=10)
        ttk.Label(frame_fondo, text="Si ya hay fondo para esta fecha, el nuevo monto se SUMARÁ al existente.",
                  foreground=COLOR_TEXTO_SUAVE, font=("Segoe UI", 8, "italic")).pack(anchor="w", pady=(6, 0))

        self.frame_corte_resumen = ttk.LabelFrame(self.frame_contenido_corte, text="RESUMEN DEL DÍA", padding=10)
        self.frame_corte_resumen.pack(fill="both", expand=True, padx=8, pady=3)

        self.frame_corte_efectivo = self._crear_fila_resumen("Ventas en Efectivo (CUP)", COLORES_CORTE["efectivo"])
        self.label_corte_efectivo_cantidad = ttk.Label(self.frame_corte_efectivo, text="0 ventas", foreground=COLOR_TEXTO_SUAVE)
        self.label_corte_efectivo_cantidad.pack(side="left", padx=12)
        self.label_corte_efectivo_total = ttk.Label(self.frame_corte_efectivo, text="0.00 CUP", font=("Segoe UI", 15, "bold"), foreground=COLORES_CORTE["efectivo"])
        self.label_corte_efectivo_total.pack(side="right")

        self.frame_corte_transferencia = self._crear_fila_resumen("Transferencias", COLORES_CORTE["transferencia"])
        self.label_corte_transferencia_cantidad = ttk.Label(self.frame_corte_transferencia, text="0 transacciones", foreground=COLOR_TEXTO_SUAVE)
        self.label_corte_transferencia_cantidad.pack(side="left", padx=12)
        self.label_corte_transferencia_total = ttk.Label(self.frame_corte_transferencia, text="0.00 CUP", font=("Segoe UI", 15, "bold"), foreground=COLORES_CORTE["transferencia"])
        self.label_corte_transferencia_total.pack(side="right")

        self.frame_corte_deudas_pend = self._crear_fila_resumen("Deudas Pendientes del Día", COLORES_CORTE["deudas"])
        self.label_corte_deudas_pend_cantidad = ttk.Label(self.frame_corte_deudas_pend, text="0 deudas", foreground=COLOR_TEXTO_SUAVE)
        self.label_corte_deudas_pend_cantidad.pack(side="left", padx=12)
        self.label_corte_deudas_pend_total = ttk.Label(self.frame_corte_deudas_pend, text="0.00 CUP", font=("Segoe UI", 14, "bold"), foreground=COLORES_CORTE["deudas"])
        self.label_corte_deudas_pend_total.pack(side="right")

        self.frame_corte_divisas = self._crear_fila_resumen("Divisas en Caja", COLORES_CORTE["divisas"])
        self.label_corte_divisas = ttk.Label(self.frame_corte_divisas, text="USD: 0.00 | EUR: 0.00", font=("Segoe UI", 11, "bold"), foreground=COLORES_CORTE["divisas"])
        self.label_corte_divisas.pack(side="right")

        self.frame_corte_utilidad = self._crear_fila_resumen("Utilidad Total", COLORES_CORTE["utilidad"])
        self.label_corte_utilidad = ttk.Label(self.frame_corte_utilidad, text="0.00 CUP", font=("Segoe UI", 15, "bold"), foreground=COLORES_CORTE["utilidad"])
        self.label_corte_utilidad.pack(side="right")

        # La cifra que cierra el dia: franja mas ancha y numero mas grande.
        self.frame_corte_total_esperado = self._crear_fila_resumen("TOTAL ESPERADO EN CAJA", COLORES_CORTE["esperado"], ancho_franja=9)
        self.label_corte_total_esperado = ttk.Label(self.frame_corte_total_esperado, text="0.00 CUP", font=("Segoe UI", 19, "bold"), foreground=COLORES_CORTE["esperado"])
        self.label_corte_total_esperado.pack(side="right")

        self.frame_corte_total_general = self._crear_fila_resumen("Total de Ventas", COLORES_CORTE["ventas"])
        self.label_corte_total_general = ttk.Label(self.frame_corte_total_general, text="0.00 CUP", font=("Segoe UI", 14, "bold"), foreground=COLORES_CORTE["ventas"])
        self.label_corte_total_general.pack(side="right")

        frame_botones_corte = ttk.Frame(self.frame_contenido_corte, style="Lienzo.TFrame")
        frame_botones_corte.pack(fill="x", padx=8, pady=(6, 10))
        ttk.Button(frame_botones_corte, text="Resumen en Texto", command=self.generar_resumen_texto_corte, style="Purple.TButton", width=20).pack(side="left", padx=(0, 8))
        ttk.Button(frame_botones_corte, text="Exportar a Excel", command=self.exportar_a_excel_corte, style="Success.TButton", width=20).pack(side="left", padx=8)
        self.frame_contenido_corte.pack_forget()

    def _crear_fila_resumen(self, texto, color_acento, ancho_franja=5):
        """Fila del resumen: tarjeta blanca con una franja de color a la izquierda.

        Devuelve el cuerpo de la fila, que es donde el llamante mete la cantidad
        (a la izquierda) y la cifra (a la derecha).
        """
        fila = ttk.Frame(self.frame_corte_resumen, style="FilaResumen.TFrame")
        fila.pack(fill="x", pady=2)
        # La franja es un tk.Frame porque solo tiene que pintar un color solido.
        tk.Frame(fila, background=color_acento, width=ancho_franja).pack(side="left", fill="y")
        cuerpo = ttk.Frame(fila, padding=(12, 9))
        cuerpo.pack(side="left", fill="both", expand=True)
        ttk.Label(cuerpo, text=texto, font=("Segoe UI", 10, "bold"), foreground=color_acento).pack(side="left")
        return cuerpo

    def ir_a_hoy_corte(self):
        hoy = datetime.datetime.now().strftime("%Y-%m-%d")
        self.corte_fecha_var.set(hoy)
        self.cambiar_fecha_corte()
    def ir_a_ayer_corte(self):
        ayer = datetime.datetime.now() - datetime.timedelta(days=1)
        ayer_str = ayer.strftime("%Y-%m-%d")
        self.corte_fecha_var.set(ayer_str)
        self.cambiar_fecha_corte()
    def cambiar_fecha_corte(self):
        fecha = self.corte_fecha_var.get().strip()
        try:
            datetime.datetime.strptime(fecha, "%Y-%m-%d")
        except ValueError:
            self.mostrar_mensaje('showerror', "Error", "Formato de fecha inválido. Usa YYYY-MM-DD")
            return
        self.corte_fondo_actual = cargar_fondo_por_fecha(fecha)
        self.corte_fondo_var.set(f"{self.corte_fondo_actual:.2f}" if self.corte_fondo_actual > 0 else "")
        if self.corte_fondo_actual > 0:
            self.label_corte_fondo_status.config(text="Fondo guardado", foreground=COLORES_CORTE["efectivo"])
        else:
            self.label_corte_fondo_status.config(text="Sin fondo registrado", foreground=COLORES_CORTE["deudas"])
        self.cargar_resumen_corte()

    def limpiar_fondo_corte(self):
        fecha = self.corte_fecha_var.get().strip()
        confirmacion = messagebox.askyesno(
            "Confirmar limpieza", 
            f"Estás seguro de que quieres establecer el fondo de caja para {fecha} a 0.00 CUP?\n\nEsto eliminará cualquier fondo registrado para esta fecha."
        )
        if not confirmacion:
            return
        if guardar_fondo_por_fecha(fecha, 0.0):
            self.corte_fondo_actual = 0.0
            self.corte_fondo_var.set("0.00")
            self.label_corte_fondo_status.config(text="Fondo limpiado (0.00 CUP)", foreground="#C4432E")
            self.cargar_resumen_corte()
            self.actualizar_saldo_cambio()
            self.root.update_idletasks()
        else:
            messagebox.showerror("Error", "No se pudo limpiar el fondo.")

    def guardar_fondo_corte(self):
        fecha = self.corte_fecha_var.get().strip()
        try:
            fondo_nuevo = float(self.corte_fondo_var.get().strip())
            if fondo_nuevo < 0:
                self.mostrar_mensaje('showerror', "Error", "El fondo no puede ser negativo")
                return
            fondo_actual = cargar_fondo_por_fecha(fecha)
            if fondo_actual > 0:
                fondo_total = fondo_actual + fondo_nuevo
                if guardar_fondo_por_fecha(fecha, fondo_total):
                    self.corte_fondo_actual = fondo_total
                    self.corte_fondo_var.set(f"{fondo_total:.2f}")
                    self.label_corte_fondo_status.config(text="Fondo actualizado (sumado)", foreground=COLORES_CORTE["efectivo"])
                    self.mostrar_mensaje('showinfo', "Éxito", f"Fondo actualizado:\n\nFondo anterior: {fondo_actual:.2f} CUP\nAñadido: {fondo_nuevo:.2f} CUP\nNuevo fondo: {fondo_total:.2f} CUP")
                    self.cargar_resumen_corte()
                else:
                    self.mostrar_mensaje('showerror', "Error", "No se pudo guardar la configuración")
            else:
                if guardar_fondo_por_fecha(fecha, fondo_nuevo):
                    self.corte_fondo_actual = fondo_nuevo
                    self.corte_fondo_var.set(f"{fondo_nuevo:.2f}")
                    self.label_corte_fondo_status.config(text="Fondo guardado", foreground=COLORES_CORTE["efectivo"])
                    self.mostrar_mensaje('showinfo', "Éxito", f"Fondo de caja guardado para {fecha}: {fondo_nuevo:.2f} CUP")
                    self.cargar_resumen_corte()
                else:
                    self.mostrar_mensaje('showerror', "Error", "No se pudo guardar la configuración")
        except ValueError:
            self.mostrar_mensaje('showerror', "Error", "Ingresa un número válido")

    def cargar_resumen_corte(self):
        fecha = self.corte_fecha_var.get().strip()
        try:
            datetime.datetime.strptime(fecha, "%Y-%m-%d")
        except ValueError:
            return
        self.corte_fondo_actual = cargar_fondo_por_fecha(fecha)
        self.corte_fondo_var.set(f"{self.corte_fondo_actual:.2f}" if self.corte_fondo_actual > 0 else "0.00")
        resumen = obtener_resumen_caja(fecha)

        total_efectivo = resumen["ventas_efectivo"]["total"]
        cant_efectivo = resumen["ventas_efectivo"]["cantidad"]
        self.label_corte_efectivo_cantidad.config(text=f"{cant_efectivo} transacciones")
        self.label_corte_efectivo_total.config(text=f"{total_efectivo:.2f} CUP")

        total_transferencia = resumen["ventas_transferencia"]["total"]
        cant_transferencia = resumen["ventas_transferencia"]["cantidad"]
        self.label_corte_transferencia_cantidad.config(text=f"{cant_transferencia} transacciones")
        self.label_corte_transferencia_total.config(text=f"{total_transferencia:.2f} CUP")

        self.label_corte_deudas_pend_cantidad.config(text=f"{resumen['deudas_pendientes_dia']['cantidad']} deudas")
        self.label_corte_deudas_pend_total.config(text=f"{resumen['deudas_pendientes_dia']['total']:.2f} CUP")

        saldo = resumen["saldo_divisas"]
        self.label_corte_divisas.config(text=f"USD: {saldo.get('USD', 0.0):.2f} | EUR: {saldo.get('EUR', 0.0):.2f}")

        utilidad_total = resumen.get("utilidad_total", 0.0)
        self.label_corte_utilidad.config(text=f"{utilidad_total:.2f} CUP")

        total_esperado = resumen["total_esperado"]
        self.label_corte_total_esperado.config(text=f"{total_esperado:.2f} CUP")

        self.label_corte_total_general.config(text=f"{resumen['total_ventas_dia']:.2f} CUP")
        self.root.title(f"La Despensa de Leslia - Sistema Integrado")

    def generar_resumen_texto_corte(self):
        fecha = self.corte_fecha_var.get().strip()
        fecha_formateada = datetime.datetime.strptime(fecha, "%Y-%m-%d").strftime("%d/%m/%Y")
        resumen = obtener_resumen_caja(fecha)
        total_efectivo = resumen["ventas_efectivo"]["total"] + resumen["cobros_efectivo"]["total"]
        total_transferencia = resumen["ventas_transferencia"]["total"] + resumen["cobros_transferencia"]["total"]
        total_esperado = resumen["total_esperado"]
        saldo = resumen["saldo_divisas"]
        texto_divisas = f"USD: {saldo.get('USD', 0.0):.2f} | EUR: {saldo.get('EUR', 0.0):.2f}"
        texto = "=" * 50 + "\n"
        texto += f"CORTE DE CAJA\n"
        texto += f"Fecha: {fecha_formateada}\n"
        texto += "=" * 50 + "\n\n"
        texto += f"VENTAS EN EFECTIVO (incluye cobros de deudas):\n   Transacciones: {resumen['ventas_efectivo']['cantidad'] + resumen['cobros_efectivo']['cantidad']}\n   Total:  {total_efectivo:.2f} CUP\n\n"
        texto += f"TRANSFERENCIAS (incluye cobros de deudas):\n   Transacciones: {resumen['ventas_transferencia']['cantidad'] + resumen['cobros_transferencia']['cantidad']}\n   Total:  {total_transferencia:.2f} CUP\n\n"
        texto += f"DEUDAS PENDIENTES DEL DÍA:\n   Cantidad: {resumen['deudas_pendientes_dia']['cantidad']}\n   Total:  {resumen['deudas_pendientes_dia']['total']:.2f} CUP\n\n"
        texto += f"DIVISAS EN CAJA:\n   {texto_divisas}\n\n"
        texto += f"TOTAL DE VENTAS (Efectivo + Transferencia + Deudas pendientes):\n   {resumen['total_ventas_dia']:.2f} CUP\n\n"
        texto += "-" * 50 + "\n"
        texto += f"TOTAL ESPERADO EN CAJA:\n   {total_esperado:.2f} CUP\n"
        texto += "=" * 50 + "\n"
        ventana_texto = tk.Toplevel(self.root)
        ventana_texto.title("Resumen de Caja")
        ventana_texto.geometry("500x600")
        ventana_texto.resizable(False, False)
        ventana_texto.configure(background=COLOR_TARJETA)
        frame_texto = ttk.Frame(ventana_texto, padding=10)
        frame_texto.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(frame_texto)
        scrollbar.pack(side="right", fill="y")
        text_widget = tk.Text(frame_texto, wrap="word", yscrollcommand=scrollbar.set, font=("Consolas", 10),
                              background=COLOR_TARJETA, foreground=COLOR_TEXTO, relief="flat", highlightthickness=0)
        text_widget.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=text_widget.yview)
        text_widget.insert("1.0", texto)
        text_widget.config(state="disabled")
        def copiar_texto():
            self.root.clipboard_clear()
            self.root.clipboard_append(texto)
            self.mostrar_mensaje('showinfo', "Éxito", "Texto copiado al portapapeles")
        ttk.Button(ventana_texto, text="Copiar al portapapeles", command=copiar_texto, style="Primary.TButton").pack(pady=(0, 12))

    def exportar_a_excel_corte(self):
        if pd is None:
            self.mostrar_mensaje("error", "Falta un componente",
                                 "Para exportar a Excel hace falta pandas.\nInstálalo con: pip install pandas openpyxl")
            return
        try:
            fecha = self.corte_fecha_var.get().strip()
            resumen = obtener_resumen_caja(fecha)
            total_efectivo = resumen["ventas_efectivo"]["total"] + resumen["cobros_efectivo"]["total"]
            total_transferencia = resumen["ventas_transferencia"]["total"] + resumen["cobros_transferencia"]["total"]
            total_esperado = resumen["total_esperado"]
            saldo = resumen["saldo_divisas"]
            texto_divisas = f"USD: {saldo.get('USD', 0.0):.2f} | EUR: {saldo.get('EUR', 0.0):.2f}"
            datos = {
                "Concepto": [
                    "Ventas en Efectivo (incluye cobros)",
                    "Transferencias (incluye cobros)",
                    "Deudas Pendientes del Día",
                    "Divisas en Caja",
                    "TOTAL ESPERADO EN CAJA",
                    "Total de Ventas (Efectivo + Transferencia + Deudas pendientes)"
                ],
                "Cantidad": [
                    resumen["ventas_efectivo"]["cantidad"] + resumen["cobros_efectivo"]["cantidad"],
                    resumen["ventas_transferencia"]["cantidad"] + resumen["cobros_transferencia"]["cantidad"],
                    resumen["deudas_pendientes_dia"]["cantidad"],
                    "-",
                    "-",
                    "-"
                ],
                "Total (CUP)": [
                    total_efectivo,
                    total_transferencia,
                    resumen["deudas_pendientes_dia"]["total"],
                    texto_divisas,
                    total_esperado,
                    resumen["total_ventas_dia"]
                ]
            }
            df = pd.DataFrame(datos)
            nombre_por_defecto = f"corte_caja_{fecha}.xlsx"
            ruta_archivo = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Archivos Excel", "*.xlsx")], initialfile=nombre_por_defecto, title="Guardar archivo Excel")
            if not ruta_archivo:
                return
            df.to_excel(ruta_archivo, index=False, sheet_name=f"Corte_{fecha}")
            self.mostrar_mensaje('showinfo', "Éxito", f"Resumen exportado correctamente.\nArchivo guardado en:\n{ruta_archivo}")
        except Exception as e:
            self.mostrar_mensaje('showerror', "Error", f"Error al exportar: {str(e)}")
