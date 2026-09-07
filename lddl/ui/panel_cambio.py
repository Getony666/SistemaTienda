"""Panel de cambio de divisa."""

import tkinter as tk

from ..caja import obtener_fondo_hoy, obtener_resumen_caja, registrar_operacion_cambio


class PanelCambioMixin:
    """Compra y venta de divisa."""

    def crear_panel_cambio_divisa(self):
        self.frame_contenido_cambio = tk.Frame(self.scrollable_frame)
        frame_saldo = tk.LabelFrame(self.frame_contenido_cambio, text="Efectivo en Caja (hoy)", padx=10, pady=10)
        frame_saldo.pack(fill="x", padx=10, pady=5)
        self.label_saldo = tk.Label(frame_saldo, text="", font=("Arial", 12))
        self.label_saldo.pack()
        self.actualizar_saldo_cambio()
        frame_form = tk.LabelFrame(self.frame_contenido_cambio, text="Registrar Operación", padx=15, pady=15)
        frame_form.pack(fill="x", padx=10, pady=10)
        tk.Label(frame_form, text="Tipo de operación:", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        frame_tipo = tk.Frame(frame_form)
        frame_tipo.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        tk.Radiobutton(frame_tipo, text="Compra", variable=self.cambio_tipo, value="compra", fg="green", command=self.actualizar_monto_cup).pack(side="left", padx=10)
        tk.Radiobutton(frame_tipo, text="Venta", variable=self.cambio_tipo, value="venta", fg="red", command=self.actualizar_monto_cup).pack(side="left", padx=10)
        tk.Label(frame_form, text="Moneda:", font=("Arial", 10, "bold")).grid(row=1, column=0, sticky="w", padx=5, pady=5)
        frame_moneda = tk.Frame(frame_form)
        frame_moneda.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        tk.Radiobutton(frame_moneda, text="USD", variable=self.cambio_moneda, value="USD", command=self.actualizar_saldo_cambio).pack(side="left", padx=10)
        tk.Radiobutton(frame_moneda, text="EUR", variable=self.cambio_moneda, value="EUR", command=self.actualizar_saldo_cambio).pack(side="left", padx=10)
        tk.Label(frame_form, text="Cantidad:", font=("Arial", 10, "bold")).grid(row=2, column=0, sticky="w", padx=5, pady=5)
        self.entry_cantidad = tk.Entry(frame_form, textvariable=self.cambio_cantidad, width=15, font=("Arial", 12))
        self.entry_cantidad.grid(row=2, column=1, sticky="w", padx=5, pady=5)
        self.entry_cantidad.bind("<KeyRelease>", self.actualizar_monto_cup)
        tk.Label(frame_form, text="Tasa (CUP):", font=("Arial", 10, "bold")).grid(row=3, column=0, sticky="w", padx=5, pady=5)
        self.entry_tasa_cambio = tk.Entry(frame_form, textvariable=self.cambio_tasa, width=15, font=("Arial", 12))
        self.entry_tasa_cambio.grid(row=3, column=1, sticky="w", padx=5, pady=5)
        self.entry_tasa_cambio.bind("<KeyRelease>", self.actualizar_monto_cup)
        tk.Label(frame_form, text="Monto en CUP:", font=("Arial", 10, "bold")).grid(row=4, column=0, sticky="w", padx=5, pady=5)
        self.label_monto_cup = tk.Label(frame_form, textvariable=self.cambio_monto_cup, font=("Arial", 12, "bold"), fg="purple")
        self.label_monto_cup.grid(row=4, column=1, sticky="w", padx=5, pady=5)
        tk.Label(frame_form, text="Observaciones:", font=("Arial", 10, "bold")).grid(row=5, column=0, sticky="w", padx=5, pady=5)
        self.entry_obs = tk.Entry(frame_form, textvariable=self.cambio_observaciones, width=40)
        self.entry_obs.grid(row=5, column=1, sticky="w", padx=5, pady=5)
        frame_botones_cambio = tk.Frame(frame_form)
        frame_botones_cambio.grid(row=6, column=0, columnspan=2, pady=15)
        tk.Button(frame_botones_cambio, text="Registrar Operación", command=self.guardar_operacion_cambio, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), width=20, height=2).pack(side="left", padx=10)
        tk.Button(frame_botones_cambio, text="Limpiar", command=self.limpiar_formulario_cambio, bg="#FF9800", fg="white", font=("Arial", 10, "bold"), width=15).pack(side="left", padx=10)

    def actualizar_saldo_cambio(self):
        try:
            fecha_actual = self.corte_fecha_var.get().strip()
            usd = obtener_fondo_hoy("USD")
            eur = obtener_fondo_hoy("EUR")
            resumen = obtener_resumen_caja(fecha_actual)
            total_cup = resumen["total_esperado"]
            self.label_saldo.config(text=f"USD: {usd:.2f}  |  EUR: {eur:.2f}  |  CUP: {total_cup:.2f}")
        except Exception as e:
            self.label_saldo.config(text="Error al cargar saldo")
            print(f"Error en actualizar_saldo_cambio: {e}")

    def actualizar_monto_cup(self, event=None):
        try:
            cantidad = float(self.cambio_cantidad.get().strip() or "0")
            tasa = float(self.cambio_tasa.get().strip() or "0")
            monto = cantidad * tasa
            self.cambio_monto_cup.set(f"{monto:.2f}")
        except ValueError:
            self.cambio_monto_cup.set("0.00")
    def limpiar_formulario_cambio(self):
        self.cambio_cantidad.set("")
        self.cambio_tasa.set("")
        self.cambio_observaciones.set("")
        self.cambio_monto_cup.set("0.00")
        self.entry_cantidad.focus_set()
    def guardar_operacion_cambio(self):
        try:
            cantidad = float(self.cambio_cantidad.get().strip())
            if cantidad <= 0:
                self.mostrar_mensaje("error", "Error", "La cantidad debe ser mayor que 0")
                return
        except ValueError:
            self.mostrar_mensaje("error", "Error", "Ingresa una cantidad válida")
            return
        try:
            tasa = float(self.cambio_tasa.get().strip())
            if tasa <= 0:
                self.mostrar_mensaje("error", "Error", "La tasa debe ser mayor que 0")
                return
        except ValueError:
            self.mostrar_mensaje("error", "Error", "Ingresa una tasa válida")
            return
        tipo = self.cambio_tipo.get()
        moneda = self.cambio_moneda.get()
        observaciones = self.cambio_observaciones.get().strip()
        monto_cup = cantidad * tasa
        tipo_texto = "Compra" if tipo == "compra" else "Venta"
        mensaje = (f"Confirmar operación:\n\n"
                   f"Tipo: {tipo_texto}\n"
                   f"Moneda: {moneda}\n"
                   f"Cantidad: {cantidad:.2f}\n"
                   f"Tasa: {tasa:.2f} CUP\n"
                   f"Monto en CUP: {monto_cup:.2f}\n"
                   f"Observaciones: {observaciones or '(ninguna)'}")
        if not self.mostrar_mensaje("yesno", "Confirmar", mensaje):
            return
        exito, mensaje = registrar_operacion_cambio(tipo, moneda, cantidad, tasa, observaciones)
        if exito:
            self.mostrar_mensaje("info", "Éxito", mensaje)
            self.limpiar_formulario_cambio()
            self.actualizar_saldo_cambio()
            if self.panel_historial_visible:
                self.cargar_ventas()
        else:
            self.mostrar_mensaje("error", "Error", mensaje)
