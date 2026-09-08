"""Panel de ventas: búsqueda de productos, carrito y formularios auxiliares."""

import tkinter as tk
from tkinter import messagebox, ttk

from ..caja import registrar_entrada_efectivo, registrar_salida_efectivo
from ..inventario import registrar_merma, registrar_salida
from ..productos import actualizar_producto, agregar_producto, buscar_productos, eliminar_producto
from ..rutas import consulta
from .. import carrito as ca
from ..calculo_cobro import redondear_subtotal_peso
from .estilos import COLOR_TARJETA, COLOR_SELECCION, COLOR_TEXTO_SUAVE, COLOR_TOTAL


class PanelVentasMixin:
    """Búsqueda de productos, carrito y formularios de la pantalla de ventas."""

    def crear_panel_ventas(self):
        self.frame_contenido_ventas = ttk.Frame(self.scrollable_frame, style="Lienzo.TFrame")

        self.frame_dos_columnas = ttk.Frame(self.frame_contenido_ventas, style="Lienzo.TFrame")
        self.frame_dos_columnas.pack(fill="both", expand=True, padx=8, pady=3)
        # Reparto 60/40: el carrito se lleva algo mas de la mitad y a Acciones le
        # queda ancho de sobra para sus tres columnas de botones. El minimo de la
        # derecha evita que esas tres columnas se aplasten en pantallas pequenas.
        self.frame_dos_columnas.grid_columnconfigure(0, weight=3)
        self.frame_dos_columnas.grid_columnconfigure(1, weight=2, minsize=560)
        self.frame_dos_columnas.grid_rowconfigure(0, weight=1)

        self.columna_izquierda = ttk.Frame(self.frame_dos_columnas, style="Lienzo.TFrame")
        self.columna_izquierda.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.columna_derecha = ttk.Frame(self.frame_dos_columnas, style="Lienzo.TFrame")
        self.columna_derecha.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        self.crear_seccion_busqueda_y_resultados()
        self.crear_botones_modulos()
        self.frame_contenedor_dinamico = ttk.Frame(self.columna_derecha, style="Lienzo.TFrame")
        self.frame_contenedor_dinamico.pack(fill="both", expand=True, padx=0, pady=3)
        self.crear_hueco_acciones()
        self.crear_seccion_nuevo_producto()
        self.crear_seccion_carrito()
        self.frame_nuevo_producto.pack_forget()

    def crear_botones_modulos(self):
        frame_modulos = ttk.LabelFrame(self.columna_derecha, text="⚡ ACCIONES", padding=7)
        frame_modulos.pack(fill="x", padx=0, pady=3)
        for col in range(3):
            frame_modulos.grid_columnconfigure(col, weight=1, uniform="acciones")

        acciones = [
            ("📦 Nuevo Producto", self.mostrar_formulario_nuevo_producto, "Primary", 0, 0),
            ("💵 Entrada de Efectivo", self.mostrar_formulario_entrada_efectivo, "Success", 0, 1),
            ("📤 Salida de Inventario", self.mostrar_formulario_salida, "DeepOrange", 0, 2),
            ("✏️ Actualizar Producto", self.cargar_para_actualizar, "Warning", 1, 0),
            ("💸 Salida de Efectivo", self.mostrar_formulario_salida_efectivo, "Danger", 1, 1),
            ("⚠️ Merma", self.mostrar_formulario_merma, "Purple", 1, 2),
            ("🗑️ Eliminar Producto", self.eliminar_productos_seleccionados, "Danger", 2, 0),
        ]
        for texto, comando, estilo, fila, col in acciones:
            ttk.Button(frame_modulos, text=texto, command=comando,
                       style=f"{estilo}Ajustado.TButton").grid(row=fila, column=col, padx=3, pady=3, sticky="nsew")

    def crear_hueco_acciones(self):
        """Recuadro que ocupa el sitio de los formularios de Acciones mientras no hay ninguno abierto."""
        self.hueco_acciones = ttk.Frame(self.frame_contenedor_dinamico, style="Placeholder.TFrame", padding=18)
        ttk.Label(self.hueco_acciones, style="Placeholder.TLabel", justify="center",
                  text="Al tocar un botón de arriba,\nsu formulario aparece aquí debajo.").pack()
        self.hueco_acciones.pack(fill="x")
        # Los formularios se muestran y ocultan desde muchos sitios: en vez de tocar
        # cada uno, el hueco reacciona a que el contenedor cambie de tamaño.
        self.frame_contenedor_dinamico.bind("<Configure>", self.sincronizar_hueco_acciones)

    def sincronizar_hueco_acciones(self, event=None):
        hay_formulario = any(
            hijo is not self.hueco_acciones and hijo.winfo_ismapped()
            for hijo in self.frame_contenedor_dinamico.winfo_children()
        )
        visible = bool(self.hueco_acciones.winfo_manager())
        if hay_formulario and visible:
            self.hueco_acciones.pack_forget()
        elif not hay_formulario and not visible:
            self.hueco_acciones.pack(fill="x")

    def crear_seccion_busqueda_y_resultados(self):
            self.frame_busqueda_resultados = ttk.Frame(self.columna_izquierda, style="Lienzo.TFrame")
            frame_busqueda = ttk.LabelFrame(self.frame_busqueda_resultados, text="BUSCAR PRODUCTOS", padding=7)
            frame_busqueda.pack(fill="x", padx=0, pady=3)
            frame_interno = ttk.Frame(frame_busqueda)
            frame_interno.pack(fill="x")
            frame_interno.grid_columnconfigure(0, weight=1)

            frame_linea_busqueda = ttk.Frame(frame_interno)
            frame_linea_busqueda.grid(row=0, column=0, pady=3, sticky="ew")
            frame_linea_busqueda.grid_columnconfigure(1, weight=1)

            ttk.Label(frame_linea_busqueda, text="Producto:").grid(row=0, column=0, padx=(0, 8), sticky="w")
            self.busqueda_var = tk.StringVar()
            self.entry_busqueda = ttk.Entry(frame_linea_busqueda, textvariable=self.busqueda_var)
            self.entry_busqueda.grid(row=0, column=1, sticky="ew", padx=(0, 10))
            ttk.Button(frame_linea_busqueda, text="🔍 Buscar", command=self.buscar,
                       style="Primary.TButton").grid(row=0, column=2, padx=(0, 6))
            ttk.Button(frame_linea_busqueda, text="Mostrar Todos", command=self.cargar_productos,
                       style="Warning.TButton").grid(row=0, column=3, padx=(0, 30))
            ttk.Button(frame_linea_busqueda, text="➕ Agregar al Carrito", command=self.agregar_desde_resultados,
                       style="Success.TButton").grid(row=0, column=4, sticky="e")

            self.frame_sugerencias = tk.Frame(frame_busqueda, bg="white", relief="solid", bd=1)
            self.frame_sugerencias.pack(fill="x", pady=2)
            self.frame_sugerencias.pack_forget()
            self.lista_sugerencias = tk.Listbox(self.frame_sugerencias, height=6, width=40, font=("Segoe UI", 10),
                                                 bg="white", relief="flat", highlightthickness=0,
                                                 selectbackground=COLOR_SELECCION, selectmode=tk.SINGLE)
            self.lista_sugerencias.pack(fill="x")
            self.lista_sugerencias.bind("<ButtonRelease-1>", self.on_sugerencia_seleccionada)
            self.entry_busqueda.bind("<KeyRelease>", self.on_key_release)
            self.entry_busqueda.bind("<Key-Return>", lambda event: self.buscar())
            self.entry_busqueda.bind("<Escape>", lambda event: self.ocultar_sugerencias())
            self.entry_busqueda.bind("<Down>", self.on_flecha_abajo)
            self.entry_busqueda.bind("<Up>", self.on_flecha_arriba)

            frame_resultados = ttk.LabelFrame(self.frame_busqueda_resultados, text="PRODUCTOS DISPONIBLES", padding=7)
            frame_resultados.pack(fill="x", padx=0, pady=3)
            contenedor = ttk.Frame(frame_resultados)
            contenedor.pack(fill="both", expand=True)
            contenedor.grid_columnconfigure(0, weight=1)
            contenedor.grid_rowconfigure(0, weight=1)
            columnas_tabla = ("ID", "Nombre", "Precio", "Stock", "Tipo", "Unidad")
            self.tabla_resultados = ttk.Treeview(contenedor, columns=columnas_tabla, show="headings", height=4)
            self.tabla_resultados.heading("ID", text="ID", anchor='center')
            self.tabla_resultados.heading("Nombre", text="Nombre", anchor='center')
            self.tabla_resultados.heading("Precio", text="Precio (CUP)", anchor='center')
            self.tabla_resultados.heading("Stock", text="Stock", anchor='center')
            self.tabla_resultados.heading("Tipo", text="Tipo", anchor='center')
            self.tabla_resultados.heading("Unidad", text="Unidad", anchor='center')
            self.tabla_resultados.column("ID", width=40, minwidth=35, anchor='center')
            self.tabla_resultados.column("Nombre", width=170, minwidth=100, anchor='center')
            self.tabla_resultados.column("Precio", width=75, minwidth=60, anchor='center')
            self.tabla_resultados.column("Stock", width=60, minwidth=50, anchor='center')
            self.tabla_resultados.column("Tipo", width=60, minwidth=50, anchor='center')
            self.tabla_resultados.column("Unidad", width=60, minwidth=50, anchor='center')
            scrollbar = ttk.Scrollbar(contenedor, orient="vertical", command=self.tabla_resultados.yview)
            self.tabla_resultados.configure(yscrollcommand=scrollbar.set)
            self.tabla_resultados.grid(row=0, column=0, sticky="nsew")
            scrollbar.grid(row=0, column=1, sticky="ns")
            self.tabla_resultados.bind("<Double-1>", lambda event: self.agregar_desde_resultados())

            self.frame_busqueda_resultados.pack(fill="x", padx=0, pady=0)

    def crear_seccion_nuevo_producto(self):
        self.frame_nuevo_producto = ttk.LabelFrame(self.frame_contenedor_dinamico, text="NUEVO PRODUCTO", padding=7)
        ttk.Label(self.frame_nuevo_producto, text="Nombre:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.entry_nombre = ttk.Entry(self.frame_nuevo_producto, textvariable=self.nombre, width=30)
        self.entry_nombre.grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(self.frame_nuevo_producto, text="Proveedor:").grid(row=0, column=2, sticky="e", padx=5, pady=5)
        ttk.Entry(self.frame_nuevo_producto, textvariable=self.proveedor, width=20).grid(row=0, column=3, padx=5, pady=5)
        ttk.Label(self.frame_nuevo_producto, text="Precio Compra (CUP):").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        ttk.Entry(self.frame_nuevo_producto, textvariable=self.precio_compra, width=15).grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(self.frame_nuevo_producto, text="Precio Venta (CUP):").grid(row=1, column=2, sticky="e", padx=5, pady=5)
        ttk.Entry(self.frame_nuevo_producto, textvariable=self.precio_venta, width=15).grid(row=1, column=3, padx=5, pady=5)
        ttk.Label(self.frame_nuevo_producto, text="Stock:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        ttk.Entry(self.frame_nuevo_producto, textvariable=self.stock, width=15).grid(row=2, column=1, padx=5, pady=5)
        ttk.Label(self.frame_nuevo_producto, text="Tipo:").grid(row=2, column=2, sticky="e", padx=5, pady=5)
        self.tipo_combobox = ttk.Combobox(self.frame_nuevo_producto, textvariable=self.tipo_producto, values=["unidad", "peso"], state="readonly", width=12)
        self.tipo_combobox.grid(row=2, column=3, padx=5, pady=5)
        self.tipo_combobox.set("unidad")
        ttk.Label(self.frame_nuevo_producto, text="Unidad:").grid(row=3, column=0, sticky="e", padx=5, pady=5)
        ttk.Entry(self.frame_nuevo_producto, textvariable=self.unidad_medida, width=15).grid(row=3, column=1, padx=5, pady=5)
        ttk.Label(self.frame_nuevo_producto, text="Fecha Venc.:").grid(row=3, column=2, sticky="e", padx=5, pady=5)
        ttk.Entry(self.frame_nuevo_producto, textvariable=self.fecha_vencimiento, width=15).grid(row=3, column=3, padx=5, pady=5)
        ttk.Label(self.frame_nuevo_producto, text="(YYYY-MM-DD)", font=("Segoe UI", 8)).grid(row=3, column=4, padx=2, pady=5)
        ttk.Label(self.frame_nuevo_producto, text="ID:").grid(row=4, column=0, sticky="e", padx=5, pady=5)
        ttk.Entry(self.frame_nuevo_producto, textvariable=self.id_producto, width=10, state="readonly").grid(row=4, column=1, padx=5, pady=5)
        frame_botones_form = ttk.Frame(self.frame_nuevo_producto)
        frame_botones_form.grid(row=5, column=0, columnspan=5, pady=10)
        ttk.Button(frame_botones_form, text="Guardar", command=self.guardar_nuevo_producto, style="Success.TButton", width=12).pack(side="left", padx=5)
        ttk.Button(frame_botones_form, text="Cancelar", command=self.ocultar_formulario_nuevo_producto, style="Danger.TButton", width=12).pack(side="left", padx=5)

    def limpiar_formulario_nuevo_producto(self):
        self.id_producto.set("")
        self.nombre.set("")
        self.precio_compra.set("")
        self.precio_venta.set("")
        self.stock.set("")
        self.tipo_producto.set("unidad")
        self.unidad_medida.set("unidad")
        self.proveedor.set("")
        self.fecha_vencimiento.set("")
    def guardar_nuevo_producto(self):
        if not self.nombre.get():
            self.mostrar_mensaje("error", "Error", "El nombre del producto es obligatorio")
            return
        nombre = self.nombre.get()
        categoria = ""
        precio_compra = self.precio_compra.get().strip() or "0"
        precio_venta = self.precio_venta.get().strip() or "0"
        stock = self.stock.get().strip() or "0"
        proveedor = self.proveedor.get().strip()
        tipo = self.tipo_producto.get()
        unidad = self.unidad_medida.get()
        fecha = self.fecha_vencimiento.get().strip()
        id_actual = self.id_producto.get()
        try:
            if id_actual:
                exito, mensaje = actualizar_producto(int(id_actual), nombre, categoria, float(precio_compra), float(precio_venta), float(stock), proveedor, tipo, unidad, fecha)
            else:
                exito, mensaje = agregar_producto(nombre, categoria, float(precio_compra), float(precio_venta), float(stock), proveedor, tipo, unidad, fecha)
        except ValueError:
            self.mostrar_mensaje("error", "Error", "Asegúrate de que los valores numéricos sean válidos")
            return
        if exito:
            self.mostrar_mensaje("info", "Éxito", mensaje)
            self.ocultar_formulario_nuevo_producto()
            if self.panel_historial_visible:
                self.cargar_ventas()
        else:
            self.mostrar_mensaje("error", "Error", mensaje)
    def cargar_para_actualizar(self):
        seleccion = self.tabla_resultados.selection()
        if not seleccion:
            self.mostrar_mensaje("warning", "Advertencia", "Selecciona un producto de la lista")
            return
        valores = self.tabla_resultados.item(seleccion[0])['values']
        producto_id = int(valores[0])
        with consulta() as (conn, cursor):
            cursor.execute('''
                SELECT nombre, categoria, precio_compra, precio_venta, stock, proveedor, tipo_producto, unidad_medida, fecha_vencimiento
                FROM productos WHERE id=?
            ''', (producto_id,))
            producto = cursor.fetchone()
        if not producto:
            self.mostrar_mensaje("error", "Error", "Producto no encontrado")
            return
        self.id_producto.set(str(producto_id))
        self.nombre.set(producto[0] or "")
        self.categoria.set(producto[1] or "")
        self.precio_compra.set(str(producto[2]) if producto[2] is not None else "")
        self.precio_venta.set(str(producto[3]) if producto[3] is not None else "")
        self.stock.set(str(producto[4]) if producto[4] is not None else "")
        self.proveedor.set(producto[5] or "")
        self.tipo_producto.set(producto[6] or "unidad")
        self.unidad_medida.set(producto[7] or "unidad")
        self.fecha_vencimiento.set(producto[8] or "")
        self.ocultar_modulos_dinamicos()
        if not self.frame_nuevo_producto.winfo_ismapped():
            self.frame_nuevo_producto.pack(fill="x", padx=0, pady=5)
            self.entry_nombre.focus_set()

    def eliminar_productos_seleccionados(self):
        seleccion = self.tabla_resultados.selection()
        if not seleccion:
            self.mostrar_mensaje("warning", "Advertencia", "Selecciona al menos un producto de la lista")
            return
        productos_a_eliminar = []
        for item in seleccion:
            valores = self.tabla_resultados.item(item)['values']
            productos_a_eliminar.append((int(valores[0]), valores[1]))
        if len(productos_a_eliminar) == 1:
            mensaje = f"Eliminar el producto '{productos_a_eliminar[0][1]}'?"
        else:
            nombres = ", ".join([p[1] for p in productos_a_eliminar])
            mensaje = f"Eliminar los siguientes {len(productos_a_eliminar)} productos?\n\n{nombres}"
        if not self.mostrar_mensaje("yesno", "Confirmar Eliminación", mensaje):
            return
        eliminados = []
        errores = []
        for pid, pnombre in productos_a_eliminar:
            exito, msg = eliminar_producto(pid)
            if exito:
                eliminados.append(pnombre)
            else:
                errores.append(f"{pnombre}: {msg}")
        if eliminados:
            if len(eliminados) == 1:
                self.mostrar_mensaje("info", "Éxito", f"Producto '{eliminados[0]}' eliminado correctamente")
            else:
                self.mostrar_mensaje("info", "Éxito", f"{len(eliminados)} productos eliminados correctamente")
        if errores:
            self.mostrar_mensaje("error", "Errores", "\n".join(errores))
        self.cargar_productos()
        if self.panel_historial_visible:
            self.cargar_ventas()

    def on_key_release(self, event):
        if event.keysym in ("Up", "Down", "Left", "Right", "Shift_L", "Shift_R", "Control_L", "Control_R", "Return", "Escape"):
            return
        texto = self.busqueda_var.get().strip()
        if len(texto) < 2:
            self.ocultar_sugerencias()
            return
        productos = buscar_productos(texto)
        self.lista_sugerencias.delete(0, tk.END)
        if productos:
            for p in productos:
                self.lista_sugerencias.insert(tk.END, f"{p[1]} - {p[2]:.2f} CUP ({p[4]}: {p[5]})")
            self.frame_sugerencias.pack(fill="x", pady=2)
            self.menu_visible = True
            self.indice_seleccionado = -1
            self.lista_sugerencias.selection_clear(0, tk.END)
        else:
            self.ocultar_sugerencias()
    def ocultar_sugerencias(self):
        self.frame_sugerencias.pack_forget()
        self.menu_visible = False
        self.indice_seleccionado = -1
    def on_flecha_abajo(self, event):
        if not self.menu_visible or self.lista_sugerencias.size() == 0:
            return
        self.lista_sugerencias.focus_set()
        self.lista_sugerencias.selection_clear(0, tk.END)
        self.lista_sugerencias.selection_set(0)
        self.lista_sugerencias.activate(0)
        self.indice_seleccionado = 0
        return "break"
    def on_flecha_arriba(self, event):
        if not self.menu_visible or self.lista_sugerencias.size() == 0:
            return
        ultimo = self.lista_sugerencias.size() - 1
        self.lista_sugerencias.focus_set()
        self.lista_sugerencias.selection_clear(0, tk.END)
        self.lista_sugerencias.selection_set(ultimo)
        self.lista_sugerencias.activate(ultimo)
        self.indice_seleccionado = ultimo
        return "break"
    def on_tecla_global(self, event):
        if not self.menu_visible:
            return
        total = self.lista_sugerencias.size()
        if total == 0:
            return
        if event.keysym == "Down":
            self.indice_seleccionado = (self.indice_seleccionado + 1) % total
            self.actualizar_seleccion()
            return "break"
        elif event.keysym == "Up":
            self.indice_seleccionado = (self.indice_seleccionado - 1) % total
            self.actualizar_seleccion()
            return "break"
        elif event.keysym == "Return":
            if self.indice_seleccionado >= 0:
                self.seleccionar_producto_actual()
                return "break"
    def actualizar_seleccion(self):
        self.lista_sugerencias.selection_clear(0, tk.END)
        self.lista_sugerencias.selection_set(self.indice_seleccionado)
        self.lista_sugerencias.activate(self.indice_seleccionado)
        self.lista_sugerencias.see(self.indice_seleccionado)
    def seleccionar_producto_actual(self):
        if self.indice_seleccionado < 0:
            return
        texto = self.lista_sugerencias.get(self.indice_seleccionado)
        nombre = texto.split(" - ")[0]
        self.busqueda_var.set(nombre)
        self.ocultar_sugerencias()
        self.buscar()
    def on_sugerencia_seleccionada(self, event):
        seleccion = self.lista_sugerencias.curselection()
        if not seleccion:
            return
        self.indice_seleccionado = seleccion[0]
        self.seleccionar_producto_actual()

    def buscar(self):
        texto = self.busqueda_var.get().strip()
        self.ocultar_sugerencias()
        for item in self.tabla_resultados.get_children():
            self.tabla_resultados.delete(item)
        productos = buscar_productos(texto)
        for p in productos:
            self.tabla_resultados.insert("", "end", values=(p[0], p[1], p[2], p[3], p[4], p[5]))
        if not productos and texto:
            self.mostrar_mensaje("info", "Sin resultados", f"No se encontraron productos con '{texto}'")
    def cargar_productos(self):
        for item in self.tabla_resultados.get_children():
            self.tabla_resultados.delete(item)
        productos = buscar_productos("")
        for p in productos:
            self.tabla_resultados.insert("", "end", values=(p[0], p[1], p[2], p[3], p[4], p[5]))

    def crear_seccion_carrito(self):
        self.frame_carrito = ttk.LabelFrame(self.columna_izquierda, text="CARRITO DE COMPRAS", padding=7)
        self.frame_carrito.pack(fill="both", expand=True, padx=0, pady=3)
        self.frame_carrito.grid_columnconfigure(0, weight=1)
        self.frame_carrito.grid_rowconfigure(0, weight=1)

        contenedor = ttk.Frame(self.frame_carrito)
        contenedor.grid(row=0, column=0, sticky="nsew")
        contenedor.grid_columnconfigure(0, weight=1)
        contenedor.grid_rowconfigure(0, weight=0)

        columnas = ("Producto", "Cantidad", "Precio", "Subtotal", "")
        self.tabla_carrito = ttk.Treeview(contenedor, columns=columnas, show="headings", height=5)
        self.tabla_carrito.heading("Producto", text="Producto", anchor='center')
        self.tabla_carrito.heading("Cantidad", text="Cantidad", anchor='center')
        self.tabla_carrito.heading("Precio", text="Precio (CUP)", anchor='center')
        self.tabla_carrito.heading("Subtotal", text="Subtotal (CUP)", anchor='center')
        self.tabla_carrito.heading("", text="", anchor='center')
        self.tabla_carrito.column("Producto", width=180, minwidth=120, anchor='center')
        self.tabla_carrito.column("Cantidad", width=75, minwidth=60, anchor='center')
        self.tabla_carrito.column("Precio", width=85, minwidth=70, anchor='center')
        self.tabla_carrito.column("Subtotal", width=95, minwidth=80, anchor='center')
        self.tabla_carrito.column("", width=30, minwidth=30, anchor='center')
        scrollbar = ttk.Scrollbar(contenedor, orient="vertical", command=self.tabla_carrito.yview)
        self.tabla_carrito.configure(yscrollcommand=scrollbar.set)
        self.tabla_carrito.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tabla_carrito.bind("<ButtonRelease-1>", self.on_carrito_click)
        self.tabla_carrito.bind("<Double-1>", self.editar_cantidad_carrito)

        ttk.Separator(self.frame_carrito, orient="horizontal").grid(row=1, column=0, sticky="ew", pady=(10, 6))
        frame_total_carrito = ttk.Frame(self.frame_carrito)
        frame_total_carrito.grid(row=2, column=0, sticky="e")
        ttk.Label(frame_total_carrito, text="TOTAL", style="TotalEtiqueta.TLabel").pack(side="left", padx=(0, 8))
        ttk.Label(frame_total_carrito, textvariable=self.total_var, style="TotalValor.TLabel").pack(side="left")
        ttk.Label(frame_total_carrito, text=" CUP", style="TotalMoneda.TLabel").pack(side="left")

        self.frame_modulo_pago = ttk.LabelFrame(self.columna_izquierda, text="PAGO", padding=7)
        self.frame_modulo_pago.pack(fill="x", padx=0, pady=3)

        frame_acciones = ttk.Frame(self.frame_modulo_pago)
        frame_acciones.pack(fill="x")
        frame_acciones.grid_columnconfigure(0, weight=1)

        frame_botones = ttk.Frame(frame_acciones)
        frame_botones.grid(row=0, column=0, sticky="w")
        self.check_transferencia = ttk.Checkbutton(frame_botones, text="Transferencia", variable=self.transferencia_var, style="Pastilla.Toolbutton", command=self.actualizar_por_transferencia)
        self.check_transferencia.pack(side="left", padx=(0, 8))
        self.check_mensajeria = ttk.Checkbutton(frame_botones, text="Mensajería", variable=self.mensajeria_var, style="Pastilla.Toolbutton")
        self.check_mensajeria.pack(side="left", padx=8)
        self.check_deuda = ttk.Checkbutton(frame_botones, text="Deuda", variable=self.deuda_var, style="Pastilla.Toolbutton", command=self.toggle_observaciones_deuda)
        self.check_deuda.pack(side="left", padx=8)

        self.frame_obs_deuda = ttk.Frame(frame_acciones)
        self.frame_obs_deuda.grid(row=1, column=0, pady=1, sticky="w")
        ttk.Label(self.frame_obs_deuda, text="Observaciones (deuda):").pack(side="left", padx=5)
        self.entry_obs_deuda = ttk.Entry(self.frame_obs_deuda, textvariable=self.observaciones_deuda_var, width=40)
        self.entry_obs_deuda.pack(side="left", padx=5)
        self.entry_obs_deuda.config(state="disabled")
        self.frame_obs_deuda.grid_remove()

        frame_pago = ttk.Frame(frame_acciones)
        frame_pago.grid(row=2, column=0, sticky="ew", pady=3)
        frame_pago.grid_columnconfigure(0, weight=0)
        frame_pago.grid_columnconfigure(1, weight=0)
        frame_pago.grid_columnconfigure(2, weight=0)
        frame_pago.grid_columnconfigure(3, weight=1)

        ttk.Label(frame_pago, text="Pago en:").grid(row=0, column=0, padx=5, sticky="e")
        self.combo_moneda = ttk.Combobox(frame_pago, textvariable=self.moneda_pago, values=["CUP", "USD", "EUR"], state="readonly", width=6)
        self.combo_moneda.grid(row=0, column=1, padx=5, sticky="w")
        self.combo_moneda.bind("<<ComboboxSelected>>", self.actualizar_moneda_pago)
        ttk.Label(frame_pago, text="Tasa (CUP):").grid(row=0, column=2, padx=5, sticky="e")
        self.entry_tasa = ttk.Entry(frame_pago, textvariable=self.tasa_cambio, width=10)
        self.entry_tasa.grid(row=0, column=3, padx=5, sticky="w")
        self.entry_tasa.bind("<KeyRelease>", self.actualizar_pago)
        self.entry_tasa.config(state="disabled")

        self.label_pagado = ttk.Label(frame_pago, text="Pagado (efectivo):")
        self.label_pagado.grid(row=2, column=0, padx=5, sticky="e")
        self.entry_pagado = ttk.Entry(frame_pago, textvariable=self.pagado_var, width=12)
        self.entry_pagado.grid(row=2, column=1, padx=5, sticky="w")
        self.entry_pagado.bind("<FocusOut>", self.calcular_vuelto_silencioso)
        self.entry_pagado.bind("<KeyRelease>", self.calcular_vuelto)
        self.label_moneda_pago = ttk.Label(frame_pago, text="CUP", foreground=COLOR_TEXTO_SUAVE)
        self.label_moneda_pago.grid(row=2, column=2, padx=5, sticky="w")

        self.frame_pago_extra = ttk.Frame(frame_pago)
        self.frame_pago_extra.grid(row=3, column=0, columnspan=4, sticky="w", padx=5)

        self.frame_transferencia = ttk.Frame(self.frame_pago_extra)
        fila_pago_transferencia = ttk.Frame(self.frame_transferencia)
        fila_pago_transferencia.pack(side="top", anchor="w")
        ttk.Label(fila_pago_transferencia, text="Pagado (Transferencia):").pack(side="left", padx=5)
        self.entry_pago_transferencia = ttk.Entry(fila_pago_transferencia, textvariable=self.pago_transferencia_var, width=10)
        self.entry_pago_transferencia.pack(side="left", padx=5)
        self.entry_pago_transferencia.bind("<KeyRelease>", self.calcular_vuelto_con_pago_mixto)
        self.label_pago_efectivo_resto = ttk.Label(self.frame_transferencia, text="", foreground=COLOR_TEXTO_SUAVE)
        self.label_pago_efectivo_resto.pack(side="top", anchor="w", padx=5, pady=(2, 0))

        self.frame_adicional_divisa = ttk.Frame(self.frame_pago_extra)

        subframe_efectivo = ttk.Frame(self.frame_adicional_divisa)
        ttk.Label(subframe_efectivo, text="CUP adicional (efectivo):").pack(side="left", padx=5)
        self.entry_pago_cup_adicional = ttk.Entry(subframe_efectivo, textvariable=self.pago_cup_adicional_var, width=10)
        self.entry_pago_cup_adicional.pack(side="left", padx=5)
        self.entry_pago_cup_adicional.bind("<KeyRelease>", self.calcular_vuelto)
        self.entry_pago_cup_adicional.config(state="disabled")
        subframe_efectivo.pack(side="top", anchor="w", padx=5, pady=1)

        subframe_transferencia = ttk.Frame(self.frame_adicional_divisa)
        ttk.Label(subframe_transferencia, text="CUP adicional (transferencia):").pack(side="left", padx=5)
        self.entry_pago_transferencia_adicional = ttk.Entry(subframe_transferencia, textvariable=self.pago_transferencia_adicional_var, width=10)
        self.entry_pago_transferencia_adicional.pack(side="left", padx=5)
        self.entry_pago_transferencia_adicional.bind("<KeyRelease>", self.calcular_vuelto)
        self.entry_pago_transferencia_adicional.config(state="disabled")
        subframe_transferencia.pack(side="top", anchor="w", padx=5, pady=1)

        self.frame_adicional_divisa.pack_forget()

        # El vuelto vive dentro de una banda verde clara, como en la maqueta.
        frame_vuelto = ttk.Frame(frame_pago, style="Vuelto.TFrame", padding=(12, 8))
        frame_vuelto.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(10, 0))

        bloque_vuelto = ttk.Frame(frame_vuelto, style="Vuelto.TFrame")
        bloque_vuelto.pack(side="top", anchor="w")
        ttk.Button(bloque_vuelto, text="Vuelto", command=self.calcular_vuelto, style="Purple.TButton").pack(side="left", padx=(0, 12))
        self.label_vuelto_valor = ttk.Label(bloque_vuelto, textvariable=self.vuelto_var, style="VueltoValor.TLabel")
        self.label_vuelto_valor.pack(side="left", padx=5)
        self.label_vuelto_moneda = ttk.Label(bloque_vuelto, text="CUP", style="VueltoMoneda.TLabel")
        self.label_vuelto_moneda.pack(side="left", padx=5)

        self.frame_vuelto_divisa = ttk.Frame(frame_vuelto, style="Vuelto.TFrame")
        self.label_vuelto_divisa_texto = ttk.Label(self.frame_vuelto_divisa, text="Vuelto en moneda de pago:", style="Vuelto.TLabel")
        self.label_vuelto_divisa_texto.pack(side="left", padx=(0, 8))
        self.entry_vuelto_moneda = ttk.Entry(self.frame_vuelto_divisa, textvariable=self.vuelto_moneda_var, width=10)
        self.entry_vuelto_moneda.bind("<KeyRelease>", self.calcular_vuelto_mixto)

        frame_botones_rapidos = ttk.Frame(self.frame_vuelto_divisa, style="Vuelto.TFrame")
        frame_botones_rapidos.pack(side="left")
        def agregar_vuelto_rapido(cantidad):
            actual = self.vuelto_moneda_var.get().strip()
            if actual:
                try:
                    nuevo = float(actual) + cantidad
                except ValueError:
                    nuevo = cantidad
            else:
                nuevo = cantidad
            self.vuelto_moneda_var.set(f"{nuevo:.2f}")
            self.calcular_vuelto_mixto()
        for valor in [1, 5, 10, 20, 50]:
            ttk.Button(frame_botones_rapidos, text=f"+{valor}", command=lambda v=valor: agregar_vuelto_rapido(v), style="Quick.TButton", width=4).pack(side="left", padx=1)
        self.frame_vuelto_divisa.pack(side="top", anchor="w", pady=(6, 0))
        self.frame_vuelto_divisa.pack_forget()

        self.label_resto_cup = ttk.Label(frame_vuelto, text="", style="VueltoResto.TLabel")
        self.label_resto_cup.pack(side="top", anchor="w", pady=(4, 0))

        frame_finales = ttk.Frame(frame_acciones)
        frame_finales.grid(row=3, column=0, pady=(10, 2), sticky="ew")
        frame_finales.grid_columnconfigure(0, weight=1)
        frame_finales.grid_columnconfigure(1, weight=1)
        ttk.Button(frame_finales, text="Finalizar Venta", command=self.finalizar_venta,
                   style="Success.TButton").grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ttk.Button(frame_finales, text="Cancelar Venta", command=self.cancelar_venta,
                   style="Danger.TButton").grid(row=0, column=1, sticky="ew", padx=(5, 0))

        self.frame_transferencia.pack(fill="x")
        self.frame_adicional_divisa.pack_forget()

    def toggle_observaciones_deuda(self):
        if self.deuda_var.get() == 1:
            self.frame_obs_deuda.grid()
            self.entry_obs_deuda.config(state="normal")
        else:
            self.frame_obs_deuda.grid_remove()
            self.entry_obs_deuda.config(state="disabled")
            self.observaciones_deuda_var.set("")

    def on_carrito_click(self, event):
        region = self.tabla_carrito.identify_region(event.x, event.y)
        if region != "cell":
            return
        col = self.tabla_carrito.identify_column(event.x)
        if col != "#5":
            return
        item = self.tabla_carrito.identify_row(event.y)
        if not item:
            return
        indice = int(item)
        if indice < len(self.carrito):
            nombre = self.carrito[indice]["nombre"]
            if self.mostrar_mensaje("yesno", "Confirmar", f"Eliminar '{nombre}' del carrito?"):
                self.carrito, _ = ca.quitar(self.carrito, indice)
                self.actualizar_carrito()

    def editar_cantidad_carrito(self, event):
        item = self.tabla_carrito.identify_row(event.y)
        if not item:
            return
        indice = int(item)
        if indice >= len(self.carrito):
            return
        producto = self.carrito[indice]
        with consulta() as (conn, cursor):
            cursor.execute("SELECT stock FROM productos WHERE id = ?", (producto["id"],))
            fila = cursor.fetchone()
        if not fila:
            self.mostrar_mensaje("error", "Error", "No se pudo obtener el stock del producto")
            return
        stock_actual = fila[0]
        self.pedir_cantidad_universal(producto["id"], producto["nombre"], producto["precio"], stock_actual, producto.get("unidad", "unidad"), producto["tipo"], indice)

    def pedir_cantidad_universal(self, producto_id, nombre, precio, stock, unidad, tipo, indice_carrito=None):
        ventana = tk.Toplevel(self.root)
        ventana.configure(background=COLOR_TARJETA)
        ventana.title("Ingresar Cantidad" if tipo == "peso" else "Ingresar Cantidad")
        ventana.geometry("420x340")
        ventana.resizable(False, False)
        ventana.transient(self.root)
        ventana.grab_set()

        ttk.Label(ventana, text="Ingresar Cantidad", style="Titulo.TLabel").pack(pady=10)
        ttk.Label(ventana, text=f"Producto: {nombre}").pack(pady=2)
        ttk.Label(ventana, text=f"Tipo: {'Peso' if tipo=='peso' else 'Unidad'} - Unidad: {unidad}").pack(pady=2)
        ttk.Label(ventana, text=f"Stock disponible: {stock:.2f} {unidad}", foreground=COLOR_TEXTO_SUAVE).pack(pady=2)
        ttk.Label(ventana, text=f"Precio: {precio:.2f} CUP por {unidad}", foreground=COLOR_TOTAL).pack(pady=2)
        if indice_carrito is not None:
            actual = self.carrito[indice_carrito]["cantidad"]
            ttk.Label(ventana, text=f"Cantidad actual: {actual:.2f} {unidad}", foreground="#7B4FA3").pack(pady=2)
        ttk.Separator(ventana, orient="horizontal").pack(fill="x", pady=10, padx=20)

        frame_cantidad = ttk.Frame(ventana)
        frame_cantidad.pack(pady=10)
        ttk.Label(frame_cantidad, text=f"Cantidad ({unidad}):").pack(side="left", padx=5)
        cantidad_var = tk.StringVar(value="1.0")
        entry_cantidad = ttk.Entry(frame_cantidad, textvariable=cantidad_var, width=15, font=("Segoe UI", 12))
        entry_cantidad.pack(side="left", padx=5)
        entry_cantidad.focus_set()
        entry_cantidad.select_range(0, tk.END)

        subtotal_label = ttk.Label(ventana, text="Subtotal: 0.00 CUP", style="Titulo.TLabel", foreground=COLOR_TOTAL)
        subtotal_label.pack(pady=5)

        def actualizar_subtotal(*args):
            try:
                cant = float(cantidad_var.get().strip() or "0")
                if tipo == "peso":
                    subtotal_redondeado = redondear_subtotal_peso(cant, precio)
                    subtotal_label.config(text=f"Subtotal: {subtotal_redondeado:.2f} CUP")
                else:
                    subtotal_label.config(text=f"Subtotal: {cant * precio:.2f} CUP")
            except ValueError:
                subtotal_label.config(text="Subtotal: 0.00 CUP")
        cantidad_var.trace_add("write", actualizar_subtotal)

        def aceptar_cantidad():
            try:
                cant = float(cantidad_var.get().strip() or "0")
            except ValueError:
                self.mostrar_mensaje("error", "Error", "Ingresa un número válido")
                return

            if indice_carrito is not None:
                nuevo, motivo = ca.fijar_cantidad(self.carrito, indice_carrito, cant, stock)
            else:
                nuevo, motivo = ca.agregar_cantidad(self.carrito, producto_id, nombre,
                                                    cant, precio, stock, tipo, unidad)

            if motivo == "cantidad_invalida":
                self.mostrar_mensaje("error", "Error", "La cantidad debe ser mayor que 0")
                return
            if motivo == "stock_insuficiente":
                self.mostrar_mensaje("error", "Error",
                                     f"No hay suficiente stock. Disponible: {stock:.2f} {unidad}")
                return
            if motivo:
                self.mostrar_mensaje("error", "Error", ca.MOTIVOS.get(motivo, motivo))
                return

            self.carrito = nuevo
            self.actualizar_carrito()
            ventana.destroy()

        frame_botones = ttk.Frame(ventana)
        frame_botones.pack(pady=15)
        btn_aceptar = ttk.Button(frame_botones, text="Aceptar", command=aceptar_cantidad, style="Success.TButton")
        btn_aceptar.pack(side="left", padx=10)
        btn_cancelar = ttk.Button(frame_botones, text="Cancelar", command=ventana.destroy, style="Danger.TButton")
        btn_cancelar.pack(side="left", padx=10)
        entry_cantidad.bind("<Key-Return>", lambda event: aceptar_cantidad())

    def agregar_desde_resultados(self):
        seleccion = self.tabla_resultados.selection()
        if not seleccion:
            self.mostrar_mensaje("warning", "Advertencia", "Selecciona un producto de la lista")
            return
        try:
            valores = self.tabla_resultados.item(seleccion[0])['values']
            producto_id = int(valores[0])
            nombre = valores[1]
            precio = float(valores[2])
            stock = float(valores[3])
            tipo = valores[4]
            unidad = valores[5]
            nuevo, motivo = ca.agregar_unidad(self.carrito, producto_id, nombre,
                                              precio, stock, tipo, unidad)
            if motivo == "sin_stock":
                self.mostrar_mensaje("error", "Error", f"El producto '{nombre}' no tiene stock")
                return
            if motivo == "stock_insuficiente":
                self.mostrar_mensaje("error", "Error", f"No hay suficiente stock de '{nombre}'")
                return
            self.carrito = nuevo
            self.actualizar_carrito()
        except Exception as e:
            self.mostrar_mensaje("error", "Error", f"Error: {str(e)}")

    def actualizar_carrito(self):
        for item in self.tabla_carrito.get_children():
            self.tabla_carrito.delete(item)
        for i, fila in enumerate(ca.filas_para_tabla(self.carrito)):
            self.tabla_carrito.insert("", "end", i, values=(
                fila["nombre"], fila["cantidad"], fila["precio"], fila["subtotal"], "✖"))
        total = ca.total(self.carrito)
        self.total_var.set(f"{total:.2f}")
        if self.transferencia_var.get() == 1:
            self.pagado_var.set(f"{total:.2f}")
            self.vuelto_var.set("0.00")
            self.vuelto_total_cup = 0.0
        else:
            self.vuelto_var.set("0.00")

    def crear_formulario_salida(self):
        self.frame_formulario_salida = ttk.LabelFrame(self.frame_contenedor_dinamico, text="REGISTRAR SALIDA", padding=7)
        ttk.Label(self.frame_formulario_salida, text="Producto:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.label_salida_producto = ttk.Label(self.frame_formulario_salida, text="(Ninguno seleccionado)", foreground=COLOR_TEXTO_SUAVE)
        self.label_salida_producto.grid(row=0, column=1, columnspan=3, padx=5, pady=5, sticky="w")
        ttk.Label(self.frame_formulario_salida, text="Precio Costo (CUP):", font=("Segoe UI", 10, "bold")).grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.label_salida_precio = ttk.Label(self.frame_formulario_salida, text="0.00", foreground=COLOR_TOTAL)
        self.label_salida_precio.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(self.frame_formulario_salida, text="Cantidad:", font=("Segoe UI", 10, "bold")).grid(row=1, column=2, padx=5, pady=5, sticky="w")
        self.entry_salida_cantidad = ttk.Entry(self.frame_formulario_salida, textvariable=self.salida_cantidad, width=12)
        self.entry_salida_cantidad.grid(row=1, column=3, padx=5, pady=5, sticky="w")
        ttk.Label(self.frame_formulario_salida, text="Motivo:", font=("Segoe UI", 10, "bold")).grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.entry_salida_motivo = ttk.Entry(self.frame_formulario_salida, textvariable=self.salida_motivo, width=40)
        self.entry_salida_motivo.grid(row=2, column=1, columnspan=3, padx=5, pady=5, sticky="w")
        frame_botones_salida = ttk.Frame(self.frame_formulario_salida)
        frame_botones_salida.grid(row=3, column=0, columnspan=4, pady=10)
        ttk.Button(frame_botones_salida, text="Guardar Salida", command=self.guardar_salida, style="Success.TButton", width=15).pack(side="left", padx=5)
        ttk.Button(frame_botones_salida, text="Cancelar", command=self.ocultar_formulario_salida, style="Danger.TButton", width=15).pack(side="left", padx=5)
    def mostrar_formulario_salida(self):
        seleccion = self.tabla_resultados.selection()
        if not seleccion:
            self.mostrar_mensaje("warning", "Advertencia", "Selecciona un producto de la lista")
            return
        valores = self.tabla_resultados.item(seleccion[0])['values']
        producto_id = int(valores[0])
        nombre = valores[1]
        stock = float(valores[3])
        try:
            with consulta() as (conn, cursor):
                cursor.execute("SELECT precio_compra FROM productos WHERE id=?", (producto_id,))
                precio_costo = cursor.fetchone()[0]
        except Exception as e:
            self.mostrar_mensaje("error", "Error", f"Error al obtener precio: {e}")
            return
        self.salida_producto_id.set(str(producto_id))
        self.label_salida_producto.config(text=f"{nombre} (Stock: {stock:.2f})", fg="black")
        self.label_salida_precio.config(text=f"{precio_costo:.2f} CUP")
        self.salida_precio_costo.set(str(precio_costo))
        self.salida_cantidad.set("1.0")
        self.salida_motivo.set("Salida a trabajador")
        self.ocultar_modulos_dinamicos()
        if not self.frame_formulario_salida.winfo_ismapped():
            self.frame_formulario_salida.pack(fill="x", padx=0, pady=5)
            self.entry_salida_cantidad.focus_set()
    def ocultar_formulario_salida(self):
        if self.frame_formulario_salida.winfo_ismapped():
            self.frame_formulario_salida.pack_forget()
            self.salida_producto_id.set("")
            self.salida_cantidad.set("1.0")
            self.salida_motivo.set("Salida a trabajador")
            self.label_salida_producto.config(text="(Ninguno seleccionado)", foreground=COLOR_TEXTO_SUAVE)
            self.label_salida_precio.config(text="0.00 CUP")
            if self.panel_ventas_visible:
                self.cargar_productos()
    def guardar_salida(self):
        try:
            if not self.salida_producto_id.get():
                self.mostrar_mensaje("error", "Error", "No hay producto seleccionado")
                return
            try:
                cantidad = float(self.salida_cantidad.get().strip())
                if cantidad <= 0:
                    self.mostrar_mensaje("error", "Error", "La cantidad debe ser mayor que 0")
                    return
            except ValueError:
                self.mostrar_mensaje("error", "Error", "Ingresa un número válido para la cantidad")
                return
            producto_id = int(self.salida_producto_id.get())
            precio_costo = float(self.salida_precio_costo.get())
            motivo = self.salida_motivo.get().strip() or "Salida a trabajador"
            if not messagebox.askyesno("Confirmar Salida", f"Registrar salida de:\n\nProducto: {self.label_salida_producto.cget('text')}\nCantidad: {cantidad}\nPrecio Costo: {precio_costo:.2f} CUP\nMotivo: {motivo}\n\nEsto generará una DEUDA automáticamente."):
                return
            exito, mensaje = registrar_salida(producto_id, cantidad, precio_costo, motivo)
            if exito:
                messagebox.showinfo("Éxito", mensaje)
                if self.frame_formulario_salida.winfo_ismapped():
                    self.frame_formulario_salida.pack_forget()
                self.salida_producto_id.set("")
                self.salida_cantidad.set("1.0")
                self.salida_motivo.set("Salida a trabajador")
                self.label_salida_producto.config(text="(Ninguno seleccionado)", foreground=COLOR_TEXTO_SUAVE)
                self.label_salida_precio.config(text="0.00 CUP")
                if self.panel_ventas_visible:
                    self.cargar_productos()
                    self.busqueda_var.set("")
                    self.entry_busqueda.focus_set()
                if self.panel_historial_visible:
                    self.cargar_ventas()
                if self.panel_corte_visible:
                    self.cargar_resumen_corte()
                self.root.update_idletasks()
            else:
                self.mostrar_mensaje("error", "Error", mensaje)
        except Exception as e:
            self.mostrar_mensaje("error", "Error", f"Error inesperado: {str(e)}")

    def crear_formulario_entrada_efectivo(self):
        self.frame_formulario_entrada_efectivo = ttk.LabelFrame(self.frame_contenedor_dinamico, text="ENTRADA DE EFECTIVO A CAJA", padding=7)
        ttk.Label(self.frame_formulario_entrada_efectivo, text="Moneda:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        frame_moneda = ttk.Frame(self.frame_formulario_entrada_efectivo)
        frame_moneda.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Radiobutton(frame_moneda, text="USD", variable=self.efectivo_moneda, value="USD").pack(side="left", padx=5)
        ttk.Radiobutton(frame_moneda, text="EUR", variable=self.efectivo_moneda, value="EUR").pack(side="left", padx=5)
        ttk.Radiobutton(frame_moneda, text="CUP", variable=self.efectivo_moneda, value="CUP").pack(side="left", padx=5)
        ttk.Label(self.frame_formulario_entrada_efectivo, text="Monto:", font=("Segoe UI", 10, "bold")).grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.entry_efectivo_monto = ttk.Entry(self.frame_formulario_entrada_efectivo, textvariable=self.efectivo_monto, width=15, font=("Segoe UI", 12))
        self.entry_efectivo_monto.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(self.frame_formulario_entrada_efectivo, text="Descripción:", font=("Segoe UI", 10, "bold")).grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.entry_efectivo_desc = ttk.Entry(self.frame_formulario_entrada_efectivo, textvariable=self.efectivo_descripcion, width=40)
        self.entry_efectivo_desc.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        frame_botones_entrada = ttk.Frame(self.frame_formulario_entrada_efectivo)
        frame_botones_entrada.grid(row=3, column=0, columnspan=2, pady=10)
        ttk.Button(frame_botones_entrada, text="Guardar", command=self.guardar_entrada_efectivo, style="Success.TButton", width=12).pack(side="left", padx=5)
        ttk.Button(frame_botones_entrada, text="Cancelar", command=self.ocultar_formulario_entrada_efectivo, style="Danger.TButton", width=12).pack(side="left", padx=5)
        self.frame_formulario_entrada_efectivo.pack_forget()
    def mostrar_formulario_entrada_efectivo(self):
        self.ocultar_modulos_dinamicos()
        if not self.frame_formulario_entrada_efectivo.winfo_ismapped():
            self.frame_formulario_entrada_efectivo.pack(fill="x", padx=0, pady=5)
            self.efectivo_monto.set("")
            self.efectivo_descripcion.set("")
            self.entry_efectivo_monto.focus_set()
    def ocultar_formulario_entrada_efectivo(self):
        if self.frame_formulario_entrada_efectivo.winfo_ismapped():
            self.frame_formulario_entrada_efectivo.pack_forget()
            self.efectivo_monto.set("")
            self.efectivo_descripcion.set("")
            if self.panel_ventas_visible:
                self.cargar_productos()
    def guardar_entrada_efectivo(self):
        try:
            monto = float(self.efectivo_monto.get().strip())
            if monto <= 0:
                self.mostrar_mensaje("error", "Error", "El monto debe ser mayor que 0")
                return
        except ValueError:
            self.mostrar_mensaje("error", "Error", "Ingresa un monto válido")
            return
        moneda = self.efectivo_moneda.get()
        descripcion = self.efectivo_descripcion.get().strip()
        if not self.mostrar_mensaje("yesno", "Confirmar", f"Registrar entrada de efectivo?\nMoneda: {moneda}\nMonto: {monto:.2f}\nDescripción: {descripcion or '(ninguna)'}"):
            return
        exito, mensaje = registrar_entrada_efectivo(moneda, monto, descripcion)
        if exito:
            self.mostrar_mensaje("info", "Éxito", mensaje)
            self.ocultar_formulario_entrada_efectivo()
            if self.panel_historial_visible:
                self.cargar_ventas()
            if self.panel_corte_visible:
                self.cargar_resumen_corte()
            self.actualizar_saldo_cambio()
        else:
            self.mostrar_mensaje("error", "Error", mensaje)

    def crear_formulario_salida_efectivo(self):
        self.frame_formulario_salida_efectivo = ttk.LabelFrame(self.frame_contenedor_dinamico, text="SALIDA DE EFECTIVO DE CAJA", padding=7)
        ttk.Label(self.frame_formulario_salida_efectivo, text="Moneda:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        frame_moneda = ttk.Frame(self.frame_formulario_salida_efectivo)
        frame_moneda.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Radiobutton(frame_moneda, text="USD", variable=self.salida_efectivo_moneda, value="USD").pack(side="left", padx=5)
        ttk.Radiobutton(frame_moneda, text="EUR", variable=self.salida_efectivo_moneda, value="EUR").pack(side="left", padx=5)
        ttk.Radiobutton(frame_moneda, text="CUP", variable=self.salida_efectivo_moneda, value="CUP").pack(side="left", padx=5)
        ttk.Label(self.frame_formulario_salida_efectivo, text="Monto:", font=("Segoe UI", 10, "bold")).grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.entry_salida_efectivo_monto = ttk.Entry(self.frame_formulario_salida_efectivo, textvariable=self.salida_efectivo_monto, width=15, font=("Segoe UI", 12))
        self.entry_salida_efectivo_monto.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(self.frame_formulario_salida_efectivo, text="Descripción:", font=("Segoe UI", 10, "bold")).grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.entry_salida_efectivo_desc = ttk.Entry(self.frame_formulario_salida_efectivo, textvariable=self.salida_efectivo_descripcion, width=40)
        self.entry_salida_efectivo_desc.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        frame_botones_salida_efectivo = ttk.Frame(self.frame_formulario_salida_efectivo)
        frame_botones_salida_efectivo.grid(row=3, column=0, columnspan=2, pady=10)
        ttk.Button(frame_botones_salida_efectivo, text="Guardar", command=self.guardar_salida_efectivo, style="Success.TButton", width=12).pack(side="left", padx=5)
        ttk.Button(frame_botones_salida_efectivo, text="Cancelar", command=self.ocultar_formulario_salida_efectivo, style="Danger.TButton", width=12).pack(side="left", padx=5)
        self.frame_formulario_salida_efectivo.pack_forget()
    def mostrar_formulario_salida_efectivo(self):
        self.ocultar_modulos_dinamicos()
        if not self.frame_formulario_salida_efectivo.winfo_ismapped():
            self.frame_formulario_salida_efectivo.pack(fill="x", padx=0, pady=5)
            self.salida_efectivo_monto.set("")
            self.salida_efectivo_descripcion.set("")
            self.entry_salida_efectivo_monto.focus_set()
    def ocultar_formulario_salida_efectivo(self):
        if self.frame_formulario_salida_efectivo.winfo_ismapped():
            self.frame_formulario_salida_efectivo.pack_forget()
            self.salida_efectivo_monto.set("")
            self.salida_efectivo_descripcion.set("")
            if self.panel_ventas_visible:
                self.cargar_productos()
    def guardar_salida_efectivo(self):
        try:
            monto = float(self.salida_efectivo_monto.get().strip())
            if monto <= 0:
                self.mostrar_mensaje("error", "Error", "El monto debe ser mayor que 0")
                return
        except ValueError:
            self.mostrar_mensaje("error", "Error", "Ingresa un monto válido")
            return
        moneda = self.salida_efectivo_moneda.get()
        descripcion = self.salida_efectivo_descripcion.get().strip()
        if not self.mostrar_mensaje("yesno", "Confirmar", f"Registrar salida de efectivo?\nMoneda: {moneda}\nMonto: {monto:.2f}\nDescripción: {descripcion or '(ninguna)'}"):
            return
        exito, mensaje = registrar_salida_efectivo(moneda, monto, descripcion)
        if exito:
            self.mostrar_mensaje("info", "Éxito", mensaje)
            self.ocultar_formulario_salida_efectivo()
            if self.panel_historial_visible:
                self.cargar_ventas()
            if self.panel_corte_visible:
                self.cargar_resumen_corte()
            self.actualizar_saldo_cambio()
        else:
            self.mostrar_mensaje("error", "Error", mensaje)

    def crear_formulario_merma(self):
        self.frame_formulario_merma = ttk.LabelFrame(self.frame_contenedor_dinamico, text="REGISTRAR MERMA", padding=7)
        ttk.Label(self.frame_formulario_merma, text="Producto:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.label_merma_producto = ttk.Label(self.frame_formulario_merma, text="(Ninguno seleccionado)", foreground=COLOR_TEXTO_SUAVE)
        self.label_merma_producto.grid(row=0, column=1, columnspan=3, padx=5, pady=5, sticky="w")
        ttk.Label(self.frame_formulario_merma, text="Stock actual:", font=("Segoe UI", 10, "bold")).grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.label_merma_stock = ttk.Label(self.frame_formulario_merma, text="0", foreground=COLOR_TOTAL)
        self.label_merma_stock.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(self.frame_formulario_merma, text="Cantidad a mermar:", font=("Segoe UI", 10, "bold")).grid(row=1, column=2, padx=5, pady=5, sticky="w")
        self.entry_merma_cantidad = ttk.Entry(self.frame_formulario_merma, textvariable=self.merma_cantidad, width=12)
        self.entry_merma_cantidad.grid(row=1, column=3, padx=5, pady=5, sticky="w")
        ttk.Label(self.frame_formulario_merma, text="Motivo:", font=("Segoe UI", 10, "bold")).grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.entry_merma_motivo = ttk.Entry(self.frame_formulario_merma, textvariable=self.merma_motivo, width=40)
        self.entry_merma_motivo.grid(row=2, column=1, columnspan=3, padx=5, pady=5, sticky="w")
        frame_botones_merma = ttk.Frame(self.frame_formulario_merma)
        frame_botones_merma.grid(row=3, column=0, columnspan=4, pady=10)
        ttk.Button(frame_botones_merma, text="Guardar Merma", command=self.guardar_merma, style="Success.TButton", width=15).pack(side="left", padx=5)
        ttk.Button(frame_botones_merma, text="Cancelar", command=self.ocultar_formulario_merma, style="Danger.TButton", width=15).pack(side="left", padx=5)
        self.frame_formulario_merma.pack_forget()
    def mostrar_formulario_merma(self):
        seleccion = self.tabla_resultados.selection()
        if not seleccion:
            self.mostrar_mensaje("warning", "Advertencia", "Selecciona un producto de la lista")
            return
        valores = self.tabla_resultados.item(seleccion[0])['values']
        producto_id = int(valores[0])
        nombre = valores[1]
        stock = float(valores[3])
        self.merma_producto_id.set(str(producto_id))
        self.label_merma_producto.config(text=f"{nombre} (Stock: {stock:.2f})", fg="black")
        self.label_merma_stock.config(text=f"{stock:.2f}")
        self.merma_cantidad.set("1.0")
        self.merma_motivo.set("Merma")
        self.ocultar_modulos_dinamicos()
        if not self.frame_formulario_merma.winfo_ismapped():
            self.frame_formulario_merma.pack(fill="x", padx=0, pady=5)
            self.entry_merma_cantidad.focus_set()
    def ocultar_formulario_merma(self):
        if self.frame_formulario_merma.winfo_ismapped():
            self.frame_formulario_merma.pack_forget()
            self.merma_producto_id.set("")
            self.merma_cantidad.set("1.0")
            self.merma_motivo.set("Merma")
            self.label_merma_producto.config(text="(Ninguno seleccionado)", foreground=COLOR_TEXTO_SUAVE)
            self.label_merma_stock.config(text="0")
            if self.panel_ventas_visible:
                self.cargar_productos()
    def guardar_merma(self):
        try:
            if not self.merma_producto_id.get():
                self.mostrar_mensaje("error", "Error", "No hay producto seleccionado")
                return
            try:
                cantidad = float(self.merma_cantidad.get().strip())
                if cantidad <= 0:
                    self.mostrar_mensaje("error", "Error", "La cantidad debe ser mayor que 0")
                    return
            except ValueError:
                self.mostrar_mensaje("error", "Error", "Ingresa un número válido para la cantidad")
                return
            producto_id = int(self.merma_producto_id.get())
            motivo = self.merma_motivo.get().strip() or "Merma"
            if not messagebox.askyesno("Confirmar Merma", f"Registrar merma de:\n\nProducto: {self.label_merma_producto.cget('text')}\nCantidad: {cantidad}\nMotivo: {motivo}\n\nEl stock se reducirá sin generar venta."):
                return
            exito, mensaje = registrar_merma(producto_id, cantidad, motivo)
            if exito:
                messagebox.showinfo("Éxito", mensaje)
                if self.frame_formulario_merma.winfo_ismapped():
                    self.frame_formulario_merma.pack_forget()
                self.merma_producto_id.set("")
                self.merma_cantidad.set("1.0")
                self.merma_motivo.set("Merma")
                self.label_merma_producto.config(text="(Ninguno seleccionado)", foreground=COLOR_TEXTO_SUAVE)
                self.label_merma_stock.config(text="0")
                if self.panel_ventas_visible:
                    self.cargar_productos()
                    self.busqueda_var.set("")
                    self.entry_busqueda.focus_set()
                if self.panel_historial_visible:
                    self.cargar_ventas()
                if self.panel_corte_visible:
                    self.cargar_resumen_corte()
                self.root.update_idletasks()
            else:
                self.mostrar_mensaje("error", "Error", mensaje)
        except Exception as e:
            self.mostrar_mensaje("error", "Error", f"Error inesperado: {str(e)}")

    def ocultar_modulos_dinamicos(self):
        if self.frame_nuevo_producto.winfo_ismapped():
            self.frame_nuevo_producto.pack_forget()
        if self.frame_formulario_salida.winfo_ismapped():
            self.frame_formulario_salida.pack_forget()
        if self.frame_formulario_entrada_efectivo.winfo_ismapped():
            self.frame_formulario_entrada_efectivo.pack_forget()
        if self.frame_formulario_merma.winfo_ismapped():
            self.frame_formulario_merma.pack_forget()
        if self.frame_formulario_salida_efectivo.winfo_ismapped():
            self.frame_formulario_salida_efectivo.pack_forget()
    def mostrar_formulario_nuevo_producto(self):
        self.ocultar_modulos_dinamicos()
        self.limpiar_formulario_nuevo_producto()
        if not self.frame_nuevo_producto.winfo_ismapped():
            self.frame_nuevo_producto.pack(fill="x", padx=0, pady=5)
            self.entry_nombre.focus_set()
    def ocultar_formulario_nuevo_producto(self):
        if self.frame_nuevo_producto.winfo_ismapped():
            self.frame_nuevo_producto.pack_forget()
            self.limpiar_formulario_nuevo_producto()
