"""Panel de historial: listado, detalle, edición de observaciones y borrado."""

import datetime
import json
try:
    import pandas as pd
except ImportError:  # sólo hace falta para exportar a Excel
    pd = None
import tkinter as tk
from tkinter import filedialog, ttk

from ..historial import revertir_registro
from ..rutas import consulta
from ..ventas_datos import _obtener_total_cobros, obtener_ventas


class PanelHistorialMixin:
    """Listado del historial, detalle, observaciones y borrado de registros."""

    def crear_panel_historial(self):
        self.frame_contenido_historial = tk.Frame(self.scrollable_frame)
        frame_filtros = tk.LabelFrame(self.frame_contenido_historial, text="Filtros", padx=10, pady=10)
        frame_filtros.pack(fill="x", padx=10, pady=5)

        frame_botones_accion = tk.Frame(frame_filtros)
        frame_botones_accion.pack(fill="x", pady=2)
        tk.Button(frame_botones_accion, text="Pagar Deuda", command=self.pagar_deuda, bg="#FF5722", fg="white", font=("Arial", 10, "bold")).pack(side="left", padx=2)
        tk.Button(frame_botones_accion, text="Editar", command=self.editar_observacion, bg="#4CAF50", fg="white", font=("Arial", 10, "bold")).pack(side="left", padx=2)
        tk.Button(frame_botones_accion, text="Eliminar del historial", command=self.eliminar_del_historial, bg="#f44336", fg="white", font=("Arial", 10, "bold")).pack(side="left", padx=2)
        tk.Button(frame_botones_accion, text="Exportar a Excel", command=self.exportar_a_excel, bg="#4CAF50", fg="white", font=("Arial", 10, "bold")).pack(side="left", padx=2)

        frame_fecha = tk.Frame(frame_filtros)
        frame_fecha.pack(fill="x", pady=2)
        tk.Label(frame_fecha, text="Fecha (YYYY-MM-DD):").pack(side="left", padx=5)
        self.entry_fecha = tk.Entry(frame_fecha, textvariable=self.filtro_fecha, width=12)
        self.entry_fecha.pack(side="left", padx=5)
        tk.Button(frame_fecha, text="Filtrar", command=self.cargar_ventas, bg="#2196F3", fg="white").pack(side="left", padx=5)
        tk.Button(frame_fecha, text="Refrescar", command=self.cargar_ventas, bg="#2196F3", fg="white").pack(side="left", padx=2)
        tk.Button(frame_fecha, text="Limpiar", command=self.limpiar_filtros, bg="#607D8B", fg="white", font=("Arial", 10, "bold")).pack(side="left", padx=2)

        frame_producto = tk.Frame(frame_filtros)
        frame_producto.pack(fill="x", pady=3)
        tk.Label(frame_producto, text="Producto:").pack(side="left", padx=5)
        self.producto_filtro_var = tk.StringVar()
        self.combo_producto_filtro = ttk.Combobox(frame_producto, textvariable=self.producto_filtro_var, state="readonly", width=40)
        self.combo_producto_filtro.pack(side="left", padx=5)
        self.combo_producto_filtro.bind("<<ComboboxSelected>>", self.cargar_ventas)
        self.cargar_productos_filtro()

        frame_tipo = tk.Frame(frame_filtros)
        frame_tipo.pack(fill="x", pady=3)
        tk.Label(frame_tipo, text="Tipo:", font=("Arial", 10, "bold")).pack(side="left", padx=5)
        tk.Radiobutton(frame_tipo, text="Todos", variable=self.filtro_tipo, value="todos", command=self.cargar_ventas).pack(side="left", padx=5)
        tk.Radiobutton(frame_tipo, text="Ventas", variable=self.filtro_tipo, value="ventas", command=self.cargar_ventas).pack(side="left", padx=5)
        tk.Radiobutton(frame_tipo, text="Cambio de Divisa", variable=self.filtro_tipo, value="cambio", command=self.cargar_ventas).pack(side="left", padx=5)
        tk.Radiobutton(frame_tipo, text="Entrada de Efectivo", variable=self.filtro_tipo, value="entrada_efectivo", command=self.cargar_ventas).pack(side="left", padx=5)
        tk.Radiobutton(frame_tipo, text="Salidas", variable=self.filtro_tipo, value="salidas", command=self.cargar_ventas).pack(side="left", padx=5)
        tk.Radiobutton(frame_tipo, text="Deudas", variable=self.filtro_tipo, value="deudas", command=self.cargar_ventas).pack(side="left", padx=5)
        tk.Radiobutton(frame_tipo, text="Salida de Efectivo", variable=self.filtro_tipo, value="salida_efectivo", command=self.cargar_ventas).pack(side="left", padx=5)
        tk.Radiobutton(frame_tipo, text="Merma", variable=self.filtro_tipo, value="merma", command=self.cargar_ventas).pack(side="left", padx=5)
        tk.Radiobutton(frame_tipo, text="Entrada de Producto", variable=self.filtro_tipo, value="entrada_producto", command=self.cargar_ventas).pack(side="left", padx=5)

        frame_metodo = tk.Frame(frame_filtros)
        frame_metodo.pack(fill="x", pady=3)
        tk.Label(frame_metodo, text="Método de pago:", font=("Arial", 10, "bold")).pack(side="left", padx=5)
        tk.Radiobutton(frame_metodo, text="Todos", variable=self.filtro_metodo, value="todos", command=self.cargar_ventas).pack(side="left", padx=5)
        tk.Radiobutton(frame_metodo, text="Efectivo", variable=self.filtro_metodo, value="efectivo", command=self.cargar_ventas).pack(side="left", padx=5)
        tk.Radiobutton(frame_metodo, text="Transferencia", variable=self.filtro_metodo, value="transferencia", command=self.cargar_ventas).pack(side="left", padx=5)
        tk.Radiobutton(frame_metodo, text="Mixto", variable=self.filtro_metodo, value="mixto", command=self.cargar_ventas).pack(side="left", padx=5)

        self.frame_tabla_ventas = tk.LabelFrame(self.frame_contenido_historial, text="Registros", padx=10, pady=10)
        self.frame_tabla_ventas.pack(fill="both", expand=True, padx=10, pady=5)
        columnas = ("ID", "Fecha", "Tipo", "Producto", "Monto", "Método Pago", "Observaciones")
        self.tabla_ventas = ttk.Treeview(self.frame_tabla_ventas, columns=columnas, show="headings")
        self.tabla_ventas.heading("ID", text="ID", anchor='center')
        self.tabla_ventas.heading("Fecha", text="Fecha", anchor='center')
        self.tabla_ventas.heading("Tipo", text="Tipo", anchor='center')
        self.tabla_ventas.heading("Producto", text="Producto", anchor='w')
        self.tabla_ventas.heading("Monto", text="Monto", anchor='center')
        self.tabla_ventas.heading("Método Pago", text="Método Pago", anchor='center')
        self.tabla_ventas.heading("Observaciones", text="Observaciones", anchor='w')
        self.tabla_ventas.column("ID", width=60, anchor='center')
        self.tabla_ventas.column("Fecha", width=150, anchor='center')
        self.tabla_ventas.column("Tipo", width=100, anchor='center')
        self.tabla_ventas.column("Producto", width=220, anchor='w')
        self.tabla_ventas.column("Monto", width=110, anchor='center')
        self.tabla_ventas.column("Método Pago", width=110, anchor='center')
        self.tabla_ventas.column("Observaciones", width=200, anchor='w')
        scrollbar = ttk.Scrollbar(self.frame_tabla_ventas, orient="vertical", command=self.tabla_ventas.yview)
        self.tabla_ventas.configure(yscrollcommand=scrollbar.set)
        self.tabla_ventas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tabla_ventas.bind("<<TreeviewSelect>>", self.mostrar_detalle)

        self.tabla_ventas.tag_configure('deuda_pendiente', foreground='red')

        self.frame_detalle_venta = tk.LabelFrame(self.frame_contenido_historial, text="Detalle", padx=10, pady=10)
        self.frame_detalle_venta.pack(fill="both", expand=True, padx=10, pady=5)
        columnas_detalle = ("Campo", "Valor")
        self.tabla_detalle = ttk.Treeview(self.frame_detalle_venta, columns=columnas_detalle, show="headings")
        self.tabla_detalle.heading("Campo", text="Campo", anchor='center')
        self.tabla_detalle.heading("Valor", text="Valor", anchor='center')
        self.tabla_detalle.column("Campo", width=150, anchor='center')
        self.tabla_detalle.column("Valor", width=300, anchor='center')
        scrollbar_detalle = ttk.Scrollbar(self.frame_detalle_venta, orient="vertical", command=self.tabla_detalle.yview)
        self.tabla_detalle.configure(yscrollcommand=scrollbar_detalle.set)
        self.tabla_detalle.pack(side="left", fill="both", expand=True)
        scrollbar_detalle.pack(side="right", fill="y")
        self.label_info = tk.Label(self.frame_detalle_venta, text="Selecciona un registro de la lista para ver detalle", fg="gray")
        self.label_info.pack(fill="x", pady=5)

    def limpiar_filtros(self):
        self.filtro_fecha.set("")
        self.filtro_tipo.set("todos")
        self.filtro_metodo.set("todos")
        self.producto_filtro_var.set("")
        self.producto_filtro_id = None
        self.cargar_ventas()

    def cargar_productos_filtro(self):
        # Todos los productos, no sólo los que quedan en stock: el historial
        # habla del pasado y casi todo está a cero.
        with consulta() as (conn, cursor):
            cursor.execute("SELECT id, nombre FROM productos ORDER BY nombre COLLATE NOCASE")
            productos = cursor.fetchall()
        self.combo_producto_filtro['values'] = [f"{p[0]} - {p[1]}" for p in productos]
        self.producto_filtro_var.set("")
        self.producto_filtro_id = None

    def cargar_ventas(self, event=None):
        for item in self.tabla_ventas.get_children():
            self.tabla_ventas.delete(item)
        for item in self.tabla_detalle.get_children():
            self.tabla_detalle.delete(item)
        filtro_fecha = self.filtro_fecha.get().strip()
        if not filtro_fecha:
            filtro_fecha = None
        filtro_metodo = self.filtro_metodo.get()
        filtro_tipo = self.filtro_tipo.get()
        seleccion = self.combo_producto_filtro.get()
        producto_id = None
        if seleccion:
            try:
                producto_id = int(seleccion.split(' - ')[0])
            except ValueError:
                pass
        self.producto_filtro_id = producto_id

        registros = obtener_ventas(filtro_fecha, filtro_metodo, filtro_tipo, producto_id)

        for reg in registros:
            tipo = reg["tipo"]
            id_reg = reg["id"]
            fecha = reg["fecha"]
            monto = reg["monto"]
            moneda = reg["moneda"]
            metodo_pago = reg["metodo_pago"]
            producto = reg.get("producto", "")
            observaciones = reg["observaciones"]

            if reg["detalle_extra"].get("es_mensajeria"):
                observaciones = (observaciones + " - Mensajería") if observaciones else "Mensajería"

            if tipo == "Venta" and reg["detalle_extra"].get("metodo_pago_real") == "Mixto" and reg["detalle_extra"].get("moneda_pago") in ("USD", "EUR"):
                pago_texto = reg["detalle_extra"].get("pago_texto", "")
                if pago_texto:
                    monto_formateado = pago_texto
                else:
                    monto_formateado = f"{monto:.2f} {moneda}" if moneda else f"{monto:.2f}"
            else:
                monto_formateado = f"{monto:.2f} {moneda}" if moneda else f"{monto:.2f}"

            # En rojo lo que sigue pendiente de cobro.
            if tipo == "Deuda" or (tipo == "Salida de Producto" and not reg["detalle_extra"].get("pagada", 0)):
                etiquetas = ('deuda_pendiente',)
            else:
                etiquetas = ()

            # El ID va siempre numérico: es lo que usan Editar y Eliminar para
            # localizar el registro. El producto tiene su propia columna.
            self.tabla_ventas.insert("", "end", tags=etiquetas, values=(
                id_reg, fecha, tipo, producto, monto_formateado, metodo_pago, observaciones))

    def mostrar_detalle(self, event):
        for item in self.tabla_detalle.get_children():
            self.tabla_detalle.delete(item)
        seleccion = self.tabla_ventas.selection()
        if not seleccion:
            return
        valores = self.tabla_ventas.item(seleccion[0])['values']
        
        try:
            id_reg = int(valores[0])
        except (ValueError, TypeError):
            self.mostrar_mensaje("warning", "Aviso", "No se puede mostrar el detalle porque el ID no está disponible.")
            return

        tipo_reg = valores[2]

        if tipo_reg in ("Venta", "Deuda"):
            with consulta() as (conn, cursor):
                cursor.execute('''
                    SELECT fecha, total, metodo_pago, moneda_pago, tasa_cambio, es_mensajeria, es_deuda, pagada, saldo_pendiente, metodo_pago_real, observaciones, pago_texto, vuelto_texto
                    FROM ventas WHERE id = ?
                ''', (id_reg,))
                fila = cursor.fetchone()
                if fila:
                    fecha, total, metodo_pago, moneda_pago, tasa_cambio, es_mensajeria, es_deuda, pagada, saldo_pendiente, metodo_pago_real, observaciones, pago_texto, vuelto_texto = fila
                    self.tabla_detalle.insert("", "end", values=("Fecha", fecha))
                    self.tabla_detalle.insert("", "end", values=("Total (CUP)", f"{total:.2f}"))
                    self.tabla_detalle.insert("", "end", values=("Método de pago original", metodo_pago))
                    self.tabla_detalle.insert("", "end", values=("Moneda de pago", moneda_pago))
                    self.tabla_detalle.insert("", "end", values=("Tasa de cambio", f"{tasa_cambio:.2f}"))
                    self.tabla_detalle.insert("", "end", values=("Mensajería", "Sí" if es_mensajeria else "No"))
                    self.tabla_detalle.insert("", "end", values=("Deuda", "Sí" if es_deuda else "No"))
                    self.tabla_detalle.insert("", "end", values=("Pagada", "Sí" if pagada else "No"))
                    if es_deuda:
                        self.tabla_detalle.insert("", "end", values=("Saldo pendiente", f"{saldo_pendiente:.2f} CUP"))
                    if metodo_pago_real:
                        self.tabla_detalle.insert("", "end", values=("Método real de pago", metodo_pago_real))
                    if observaciones:
                        self.tabla_detalle.insert("", "end", values=("Observaciones", observaciones))

                    if pago_texto:
                        self.tabla_detalle.insert("", "end", values=("Monto pagado", pago_texto))
                    else:
                        if es_deuda:
                            if pagada:
                                total_cobrado = total
                            else:
                                total_cobrado = _obtener_total_cobros(id_reg)
                            self.tabla_detalle.insert("", "end", values=("Monto pagado", f"{total_cobrado:.2f} CUP"))
                        else:
                            if pagada:
                                if metodo_pago == "Efectivo" and moneda_pago != "CUP" and tasa_cambio > 0:
                                    pagado_moneda = total / tasa_cambio
                                    self.tabla_detalle.insert("", "end", values=("Monto pagado", f"{pagado_moneda:.2f} {moneda_pago}"))
                                else:
                                    self.tabla_detalle.insert("", "end", values=("Monto pagado", f"{total:.2f} CUP"))
                            else:
                                self.tabla_detalle.insert("", "end", values=("Monto pagado", "0.00 CUP"))

                    if vuelto_texto:
                        self.tabla_detalle.insert("", "end", values=("Vuelto", vuelto_texto))
                    else:
                        if not es_deuda and pagada:
                            self.tabla_detalle.insert("", "end", values=("Vuelto", "0.00 CUP (no registrado)"))
                        else:
                            self.tabla_detalle.insert("", "end", values=("Vuelto", "No aplica"))

                    with consulta() as (_conn2, cursor2):
                        cursor2.execute('''
                            SELECT p.nombre, dv.cantidad, dv.precio_unitario, (dv.cantidad * dv.precio_unitario) as subtotal
                            FROM detalles_venta dv
                            JOIN productos p ON dv.producto_id = p.id
                            WHERE dv.venta_id = ?
                        ''', (id_reg,))
                        detalles = cursor2.fetchall()
                    if detalles:
                        self.tabla_detalle.insert("", "end", values=("--- Productos ---", ""))
                        for d in detalles:
                            self.tabla_detalle.insert("", "end", values=(d[0], f"{d[1]} x {d[2]:.2f} = {d[3]:.2f} CUP"))
                    self.frame_detalle_venta.config(text="Detalle de Venta")

        elif tipo_reg == "Cambio de Divisa":
            with consulta() as (conn, cursor):
                cursor.execute('''
                    SELECT fecha, tipo, moneda, cantidad, tasa, monto_cup, observaciones
                    FROM operaciones_cambio WHERE id = ?
                ''', (id_reg,))
                fila = cursor.fetchone()
            if fila:
                fecha, tipo_op, moneda, cantidad, tasa, monto_cup, obs = fila
                self.tabla_detalle.insert("", "end", values=("Fecha", fecha))
                self.tabla_detalle.insert("", "end", values=("Tipo", "Compra" if tipo_op == "compra" else "Venta"))
                self.tabla_detalle.insert("", "end", values=("Moneda", moneda))
                self.tabla_detalle.insert("", "end", values=("Cantidad", f"{cantidad:.2f}"))
                self.tabla_detalle.insert("", "end", values=("Tasa (CUP)", f"{tasa:.2f}"))
                self.tabla_detalle.insert("", "end", values=("Monto en CUP", f"{monto_cup:.2f}"))
                self.tabla_detalle.insert("", "end", values=("Observaciones", obs or ""))
                self.frame_detalle_venta.config(text="Detalle de Operación de Cambio")

        elif tipo_reg in ("Entrada de efectivo", "Salida de efectivo"):
            with consulta() as (conn, cursor):
                if tipo_reg == "Entrada de efectivo":
                    cursor.execute('''
                        SELECT fecha, moneda, monto, descripcion
                        FROM entradas_efectivo WHERE id = ?
                    ''', (id_reg,))
                else:
                    cursor.execute('''
                        SELECT fecha, moneda, monto, descripcion
                        FROM salidas_efectivo WHERE id = ?
                    ''', (id_reg,))
                fila = cursor.fetchone()
            if fila:
                fecha, moneda, monto, desc = fila
                self.tabla_detalle.insert("", "end", values=("Fecha", fecha))
                self.tabla_detalle.insert("", "end", values=("Moneda", moneda))
                self.tabla_detalle.insert("", "end", values=("Monto", f"{monto:.2f}"))
                self.tabla_detalle.insert("", "end", values=("Descripción", desc or ""))
                self.frame_detalle_venta.config(text=f"Detalle de {tipo_reg}")

        elif tipo_reg == "Merma":
            # El ID de una merma viene de salidas_inventario, no del historial:
            # buscarla por ese ID en historial no encontraba nunca nada.
            with consulta() as (conn, cursor):
                cursor.execute('''
                    SELECT s.fecha, p.nombre, s.cantidad, s.precio_costo, s.motivo
                    FROM salidas_inventario s
                    JOIN productos p ON s.producto_id = p.id
                    WHERE s.id = ?
                ''', (id_reg,))
                fila = cursor.fetchone()
            if fila:
                fecha, nombre, cantidad, precio_costo, motivo = fila
                self.tabla_detalle.insert("", "end", values=("Fecha", fecha))
                self.tabla_detalle.insert("", "end", values=("Producto", nombre))
                self.tabla_detalle.insert("", "end", values=("Cantidad", cantidad))
                self.tabla_detalle.insert("", "end", values=("Precio costo", f"{precio_costo:.2f} CUP"))
                self.tabla_detalle.insert("", "end", values=("Costo total", f"{cantidad * precio_costo:.2f} CUP"))
                self.tabla_detalle.insert("", "end", values=("Motivo", motivo or ""))
                self.frame_detalle_venta.config(text="Detalle de Merma")

        elif tipo_reg in ("Salida de Producto", "Entrada de Producto", "Actualización de Producto", "Eliminación de Producto"):
            with consulta() as (conn, cursor):
                cursor.execute('''
                    SELECT fecha, tipo_accion, descripcion, detalles
                    FROM historial WHERE id = ?
                ''', (id_reg,))
                fila = cursor.fetchone()
            if fila:
                fecha, tipo_accion, desc, detalles_json = fila
                self.tabla_detalle.insert("", "end", values=("Fecha", fecha))
                self.tabla_detalle.insert("", "end", values=("Acción", tipo_accion))
                if tipo_accion == "Salida de Producto":
                    try:
                        detalles = json.loads(detalles_json)
                        motivo = detalles.get("motivo", "")
                        self.tabla_detalle.insert("", "end", values=("Motivo", motivo))
                        venta_id = detalles.get("venta_id")
                        if venta_id:
                            with consulta() as (conn2, cursor2):
                                cursor2.execute("SELECT pagada, saldo_pendiente, observaciones FROM ventas WHERE id = ?", (venta_id,))
                                fila2 = cursor2.fetchone()
                            if fila2:
                                pagada2 = fila2[0]
                                saldo2 = fila2[1]
                                obs2 = fila2[2]
                                if pagada2:
                                    self.tabla_detalle.insert("", "end", values=("Estado", "Pagada"))
                                else:
                                    self.tabla_detalle.insert("", "end", values=("Saldo pendiente", f"{saldo2:.2f} CUP"))
                                if obs2:
                                    self.tabla_detalle.insert("", "end", values=("Observaciones", obs2))
                    except:
                        self.tabla_detalle.insert("", "end", values=("Descripción", desc))
                elif tipo_accion == "Merma":
                    try:
                        detalles = json.loads(detalles_json)
                        cantidad = detalles.get("cantidad", 0)
                        precio = detalles.get("precio_costo", 0)
                        self.tabla_detalle.insert("", "end", values=("Cantidad", cantidad))
                        self.tabla_detalle.insert("", "end", values=("Precio costo", f"{precio:.2f} CUP"))
                        motivo = detalles.get("motivo", "")
                        if motivo:
                            self.tabla_detalle.insert("", "end", values=("Motivo", motivo))
                    except:
                        pass
                elif tipo_accion == "Entrada de Producto":
                    try:
                        detalles = json.loads(detalles_json)
                        nombre = detalles.get("nombre", "")
                        if nombre:
                            self.tabla_detalle.insert("", "end", values=("Nombre", nombre))
                        precio_compra = detalles.get("precio_compra", 0)
                        self.tabla_detalle.insert("", "end", values=("Precio compra", f"{precio_compra} CUP"))
                        stock = detalles.get("stock", 0)
                        self.tabla_detalle.insert("", "end", values=("Stock inicial", stock))
                    except:
                        pass
                else:
                    self.tabla_detalle.insert("", "end", values=("Descripción", desc))
                if detalles_json:
                    try:
                        detalles = json.loads(detalles_json)
                        if isinstance(detalles, dict):
                            for k, v in detalles.items():
                                if k not in ("motivo", "venta_id", "cantidad", "precio_costo", "nombre", "stock", "precio_compra"):
                                    self.tabla_detalle.insert("", "end", values=(k.capitalize(), str(v)))
                    except:
                        pass
                self.frame_detalle_venta.config(text=f"Detalle de {tipo_accion}")

    def eliminar_del_historial(self):
        selecciones = self.tabla_ventas.selection()
        if not selecciones:
            self.mostrar_mensaje("warning", "Advertencia", "Selecciona al menos un registro de la lista")
            return

        items_a_eliminar = []
        for item in selecciones:
            valores = self.tabla_ventas.item(item)['values']
            id_reg = valores[0] if str(valores[0]).isdigit() else None
            if id_reg is None:
                self.mostrar_mensaje("warning", "Aviso", f"El registro con ID {valores[0]} no es válido para eliminar. Se omitirá.")
                continue
            tipo = valores[2]
            items_a_eliminar.append((id_reg, tipo, item))

        if not items_a_eliminar:
            return

        if len(items_a_eliminar) == 1:
            msg = f"Eliminar permanentemente el registro '{items_a_eliminar[0][1]}' con ID {items_a_eliminar[0][0]}? Se revertirán todos los efectos asociados."
        else:
            tipos = ", ".join([f"{t} (ID {i})" for i, t, _ in items_a_eliminar])
            msg = f"Eliminar permanentemente los siguientes {len(items_a_eliminar)} registros?\n\n{tipos}\n\nSe revertirán todos los efectos asociados."

        if not self.mostrar_mensaje("yesno", "Confirmar Eliminación", msg):
            return

        errores = []
        exitos = 0
        for id_reg, tipo, item in items_a_eliminar:
            exito, mensaje = revertir_registro(id_reg, tipo)
            if exito:
                exitos += 1
            else:
                errores.append(f"ID {id_reg} ({tipo}): {mensaje}")

        if exitos > 0:
            self.mostrar_mensaje("info", "Éxito", f"{exitos} registro(s) eliminado(s) correctamente.")
            self.cargar_ventas()
            self.actualizar_saldo_cambio()
            if self.panel_corte_visible:
                self.cargar_resumen_corte()
        if errores:
            self.mostrar_mensaje("error", "Errores", "Se produjeron errores:\n" + "\n".join(errores))

    def editar_observacion(self):
        seleccion = self.tabla_ventas.selection()
        if not seleccion:
            self.mostrar_mensaje("warning", "Advertencia", "Selecciona un registro de la lista")
            return

        valores = self.tabla_ventas.item(seleccion[0])['values']
        id_reg = valores[0] if str(valores[0]).isdigit() else None
        if id_reg is None:
            self.mostrar_mensaje("warning", "Aviso", "El ID del registro no es válido para editar.")
            return
        tipo = valores[2]
        observacion_actual = valores[6] if len(valores) > 6 else ""

        tipos_permitidos = ["Venta", "Deuda", "Salida de Producto"]
        if tipo not in tipos_permitidos:
            self.mostrar_mensaje("warning", "No permitido", "Solo se puede editar la observación de Ventas, Deudas o Salidas de Producto.")
            return

        venta_id = None
        if tipo == "Salida de Producto":
            with consulta() as (conn, cursor):
                cursor.execute("SELECT detalles FROM historial WHERE id = ?", (id_reg,))
                fila = cursor.fetchone()
            if fila:
                try:
                    detalles = json.loads(fila[0])
                    venta_id = detalles.get("venta_id")
                except:
                    pass
            if not venta_id:
                self.mostrar_mensaje("error", "Error", "No se pudo obtener la venta asociada a esta salida.")
                return
        else:
            venta_id = id_reg

        with consulta() as (conn, cursor):
            cursor.execute("SELECT observaciones FROM ventas WHERE id = ?", (venta_id,))
            fila = cursor.fetchone()
        if not fila:
            self.mostrar_mensaje("error", "Error", "No se encontró la venta asociada.")
            return

        observacion_actual_db = fila[0] or ""

        ventana_editar = tk.Toplevel(self.root)
        ventana_editar.title("Editar Observación")
        ventana_editar.geometry("500x250")
        ventana_editar.resizable(False, False)
        ventana_editar.transient(self.root)
        ventana_editar.grab_set()

        tk.Label(ventana_editar, text=f"Editar observación para {tipo} (ID {id_reg})", font=("Arial", 12, "bold")).pack(pady=5)
        tk.Label(ventana_editar, text="Observaciones:", font=("Arial", 10)).pack(anchor="w", padx=20, pady=5)
        texto_var = tk.StringVar(value=observacion_actual_db)
        entry_obs = tk.Entry(ventana_editar, textvariable=texto_var, width=60, font=("Arial", 10))
        entry_obs.pack(padx=20, pady=5)
        entry_obs.focus_set()
        entry_obs.select_range(0, tk.END)

        def guardar_observacion():
            nueva_obs = texto_var.get().strip()
            with consulta() as (conn, cursor):
                cursor.execute("UPDATE ventas SET observaciones = ? WHERE id = ?", (nueva_obs, venta_id))
                conn.commit()
            ventana_editar.destroy()
            self.mostrar_mensaje("info", "Éxito", "Observación actualizada correctamente.")
            self.cargar_ventas()

        def cancelar_edicion():
            ventana_editar.destroy()

        frame_botones_editar = tk.Frame(ventana_editar)
        frame_botones_editar.pack(pady=20)
        tk.Button(frame_botones_editar, text="Guardar", command=guardar_observacion, bg="#4CAF50", fg="white", width=12).pack(side="left", padx=10)
        tk.Button(frame_botones_editar, text="Cancelar", command=cancelar_edicion, bg="#f44336", fg="white", width=12).pack(side="left", padx=10)

    def exportar_a_excel(self):
        if pd is None:
            self.mostrar_mensaje("error", "Falta un componente",
                                 "Para exportar a Excel hace falta pandas.\nInstálalo con: pip install pandas openpyxl")
            return
        try:
            datos = []
            for item in self.tabla_ventas.get_children():
                valores = self.tabla_ventas.item(item)['values']
                datos.append({
                    "ID": valores[0],
                    "Fecha": valores[1],
                    "Tipo": valores[2],
                    "Producto": valores[3],
                    "Monto": valores[4],
                    "Método Pago": valores[5],
                    "Observaciones": valores[6]
                })
            if not datos:
                self.mostrar_mensaje('warning', "Sin datos", "No hay registros para exportar.")
                return
            df = pd.DataFrame(datos)
            fecha_actual = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
            nombre_por_defecto = f"historial_{fecha_actual}.xlsx"
            ruta_archivo = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Archivos Excel", "*.xlsx")],
                initialfile=nombre_por_defecto,
                title="Guardar archivo Excel"
            )
            if not ruta_archivo:
                return
            df.to_excel(ruta_archivo, index=False, sheet_name="Registros")
            self.mostrar_mensaje('info', "Éxito", f"Datos exportados correctamente.\n\n{len(datos)} registros exportados.")
        except Exception as e:
            self.mostrar_mensaje('error', "Error", f"Error al exportar: {str(e)}")
