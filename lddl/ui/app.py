"""Ventana principal: navegación entre paneles y armazón común.

La ventana se compone con un mixin por panel (ventas, cobro, historial, cambio,
corte). Cada mixin vive en su propio fichero y aporta sus métodos; aquí sólo
queda lo que comparten todos: el lienzo con barras de desplazamiento, los
botones de navegación y el diálogo de mensajes.
"""

import datetime
import tkinter as tk
from tkinter import messagebox, ttk

from .. import TITULO_VENTANA
from ..caja import cargar_fondo_por_fecha
from ..esquema import verificar_y_crear_columnas
from .cobro import CobroMixin
from .dialogo_deuda import DialogoDeudaMixin
from .estilos import configurar_estilos
from .panel_cambio import PanelCambioMixin
from .panel_corte import PanelCorteMixin
from .panel_historial import PanelHistorialMixin
from .panel_ventas import PanelVentasMixin


class VentanaVentas(PanelVentasMixin, CobroMixin, PanelHistorialMixin,
                    DialogoDeudaMixin, PanelCambioMixin, PanelCorteMixin):
    """La ventana del programa. Cada mixin aporta los métodos de su panel."""

    def __init__(self, master):
        self.root = master
        self.root.title(TITULO_VENTANA)
        self.style = ttk.Style(self.root)
        configurar_estilos(self.style)
        self.color_fondo = self.style.lookup("Lienzo.TFrame", "background")
        try:
            self.root.state('zoomed')
        except:
            try:
                self.root.attributes('-zoomed', True)
            except:
                self.root.geometry("1100x780")
        self.root.minsize(800, 600)
        verificar_y_crear_columnas()
        self.carrito = []
        self.total_var = tk.StringVar(value="0.00")
        self.vuelto_var = tk.StringVar(value="0.00")
        self.pagado_var = tk.StringVar()
        self.menu_visible = False
        self.indice_seleccionado = -1
        self.transferencia_var = tk.IntVar(value=0)
        self.mensajeria_var = tk.IntVar(value=0)
        self.deuda_var = tk.IntVar(value=0)
        self.moneda_pago = tk.StringVar(value="CUP")
        self.tasa_cambio = tk.StringVar(value="1.00")
        self.vuelto_moneda_var = tk.StringVar()
        self.pago_transferencia_var = tk.StringVar()
        self.pago_cup_adicional_var = tk.StringVar()
        self.pago_transferencia_adicional_var = tk.StringVar()
        self.vuelto_total_cup = 0.0
        self.actualizando = False

        self.observaciones_deuda_var = tk.StringVar()

        self.id_producto = tk.StringVar()
        self.nombre = tk.StringVar()
        self.categoria = tk.StringVar()
        self.precio_compra = tk.StringVar()
        self.precio_venta = tk.StringVar()
        self.stock = tk.StringVar()
        self.proveedor = tk.StringVar()
        self.tipo_producto = tk.StringVar(value="unidad")
        self.unidad_medida = tk.StringVar(value="unidad")
        self.fecha_vencimiento = tk.StringVar()
        
        self.salida_producto_id = tk.StringVar()
        self.salida_precio_costo = tk.StringVar()
        self.salida_cantidad = tk.StringVar(value="1.0")
        self.salida_motivo = tk.StringVar(value="Salida a trabajador")
        
        self.merma_producto_id = tk.StringVar()
        self.merma_cantidad = tk.StringVar(value="1.0")
        self.merma_motivo = tk.StringVar(value="Merma")

        self.salida_efectivo_moneda = tk.StringVar(value="CUP")
        self.salida_efectivo_monto = tk.StringVar()
        self.salida_efectivo_descripcion = tk.StringVar()

        self.filtro_fecha = tk.StringVar(value="")
        self.filtro_metodo = tk.StringVar(value="todos")
        self.filtro_tipo = tk.StringVar(value="todos")
        self.producto_filtro_id = None
        
        self.cambio_tipo = tk.StringVar(value="compra")
        self.cambio_moneda = tk.StringVar(value="USD")
        self.cambio_cantidad = tk.StringVar()
        self.cambio_tasa = tk.StringVar()
        self.cambio_observaciones = tk.StringVar()
        self.cambio_monto_cup = tk.StringVar(value="0.00")
        
        self.efectivo_moneda = tk.StringVar(value="CUP")
        self.efectivo_monto = tk.StringVar()
        self.efectivo_descripcion = tk.StringVar()
        
        hoy = datetime.datetime.now().strftime("%Y-%m-%d")
        self.corte_fecha_var = tk.StringVar(value=hoy)
        self.corte_fondo_var = tk.StringVar()
        self.corte_fondo_actual = cargar_fondo_por_fecha(hoy)
        if self.corte_fondo_actual > 0:
            self.corte_fondo_var.set(f"{self.corte_fondo_actual:.2f}")
        
        self.crear_scrollable()
        self.crear_botones_principales()
        self.crear_panel_ventas()
        self.crear_panel_historial()
        self.crear_panel_cambio_divisa()
        self.crear_formulario_salida()
        self.crear_formulario_entrada_efectivo()
        self.crear_formulario_merma()
        self.crear_formulario_salida_efectivo()
        self.crear_panel_corte_caja()
        
        self.panel_ventas_visible = False
        self.panel_historial_visible = False
        self.panel_cambio_visible = False
        self.panel_corte_visible = False
        self.mostrar_panel_ventas()

    def mostrar_mensaje(self, tipo, titulo, mensaje, **kwargs):
        self.root.lift()
        self.root.focus_force()
        self.root.attributes('-topmost', True)
        kwargs['parent'] = self.root
        if tipo == 'info':
            res = messagebox.showinfo(titulo, mensaje, **kwargs)
        elif tipo == 'error':
            res = messagebox.showerror(titulo, mensaje, **kwargs)
        elif tipo == 'warning':
            res = messagebox.showwarning(titulo, mensaje, **kwargs)
        elif tipo == 'yesno':
            res = messagebox.askyesno(titulo, mensaje, **kwargs)
        elif tipo == 'askokcancel':
            res = messagebox.askokcancel(titulo, mensaje, **kwargs)
        else:
            res = None
        self.root.attributes('-topmost', False)
        self.root.lift()
        self.root.focus_force()
        return res

    def crear_scrollable(self):
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=0)
        self.root.grid_rowconfigure(1, weight=0)
        self.canvas = tk.Canvas(self.root, background=self.color_fondo, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar_y = ttk.Scrollbar(self.root, orient="vertical", command=self.canvas.yview)
        self.scrollbar_y.grid(row=0, column=1, sticky="ns")
        self.scrollbar_x = ttk.Scrollbar(self.root, orient="horizontal", command=self.canvas.xview)
        self.scrollbar_x.grid(row=1, column=0, sticky="ew")
        self.canvas.configure(yscrollcommand=self.scrollbar_y.set, xscrollcommand=self.scrollbar_x.set)
        self.scrollable_frame = ttk.Frame(self.canvas, style="Lienzo.TFrame")
        self.scrollable_frame.grid_columnconfigure(0, weight=1)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        def _configure_canvas(event):
            self.canvas.itemconfig(self.canvas_window, width=event.width)
            self.scrollable_frame.update_idletasks()
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.canvas.bind('<Configure>', _configure_canvas)

        # El contenido tambien crece por su cuenta (al pagar en divisa aparecen
        # filas nuevas). Sin esto el area desplazable se queda con la medida
        # vieja y lo que sobresale por abajo -Finalizar y Cancelar Venta- queda
        # fuera de alcance de la barra.
        def _configure_interior(event):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.scrollable_frame.bind('<Configure>', _configure_interior)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Shift-MouseWheel>", self._on_shift_mousewheel)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    def _on_shift_mousewheel(self, event):
        self.canvas.xview_scroll(int(-1*(event.delta/120)), "units")

    def crear_botones_principales(self):
        self.frame_botones_principales = ttk.Frame(self.scrollable_frame, padding=(14, 8), style="NavBar.TFrame")
        self.frame_botones_principales.pack(fill="x")
        self.btn_ventas = ttk.Button(self.frame_botones_principales, text="🛒 Ventas", command=self.toggle_panel_ventas, style="NavActivo.TButton")
        self.btn_ventas.pack(side="left", padx=(0, 8))
        self.btn_historial = ttk.Button(self.frame_botones_principales, text="🕒 Historial", command=self.toggle_panel_historial, style="NavInactivo.TButton")
        self.btn_historial.pack(side="left", padx=8)
        self.btn_cambio = ttk.Button(self.frame_botones_principales, text="💱 Cambio de Divisa", command=self.toggle_panel_cambio, style="NavInactivo.TButton")
        self.btn_cambio.pack(side="left", padx=8)
        self.btn_corte = ttk.Button(self.frame_botones_principales, text="🧮 Corte de Caja", command=self.toggle_panel_corte, style="NavInactivo.TButton")
        self.btn_corte.pack(side="left", padx=8)

    def toggle_panel_ventas(self):
        if self.panel_ventas_visible:
            self.ocultar_panel_ventas()
        else:
            self.mostrar_panel_ventas()
    def mostrar_panel_ventas(self):
        if self.panel_historial_visible:
            self.ocultar_panel_historial()
        if self.panel_cambio_visible:
            self.ocultar_panel_cambio()
        if self.panel_corte_visible:
            self.ocultar_panel_corte()
        if not self.panel_ventas_visible:
            self.frame_contenido_ventas.pack(fill="both", expand=True, padx=0, pady=0)
            self.ocultar_modulos_dinamicos()
            self.busqueda_var.set("")
            self.cargar_productos()
            self.actualizar_moneda_pago()
            self.panel_ventas_visible = True
            self.btn_ventas.configure(style="NavActivo.TButton")
            self.btn_historial.configure(style="NavInactivo.TButton")
            self.btn_cambio.configure(style="NavInactivo.TButton")
            self.btn_corte.configure(style="NavInactivo.TButton")
    def ocultar_panel_ventas(self):
        if self.panel_ventas_visible:
            self.frame_contenido_ventas.pack_forget()
            self.ocultar_sugerencias()
            self.ocultar_modulos_dinamicos()
            self.panel_ventas_visible = False
            self.btn_ventas.configure(style="NavInactivo.TButton")

    def toggle_panel_historial(self):
        if self.panel_historial_visible:
            self.ocultar_panel_historial()
        else:
            self.mostrar_panel_historial()
    def mostrar_panel_historial(self):
        if self.panel_ventas_visible:
            self.ocultar_panel_ventas()
        if self.panel_cambio_visible:
            self.ocultar_panel_cambio()
        if self.panel_corte_visible:
            self.ocultar_panel_corte()
        if not self.panel_historial_visible:
            self.frame_contenido_historial.pack(fill="both", expand=True, padx=0, pady=0)
            self.cargar_ventas()
            self.panel_historial_visible = True
            self.btn_historial.configure(style="NavActivo.TButton")
            self.btn_ventas.configure(style="NavInactivo.TButton")
            self.btn_cambio.configure(style="NavInactivo.TButton")
            self.btn_corte.configure(style="NavInactivo.TButton")
    def ocultar_panel_historial(self):
        if self.panel_historial_visible:
            self.frame_contenido_historial.pack_forget()
            self.panel_historial_visible = False
            self.btn_historial.configure(style="NavInactivo.TButton")

    def toggle_panel_cambio(self):
        if self.panel_cambio_visible:
            self.ocultar_panel_cambio()
        else:
            self.mostrar_panel_cambio()
    def mostrar_panel_cambio(self):
        if self.panel_ventas_visible:
            self.ocultar_panel_ventas()
        if self.panel_historial_visible:
            self.ocultar_panel_historial()
        if self.panel_corte_visible:
            self.ocultar_panel_corte()
        if not self.panel_cambio_visible:
            self.frame_contenido_cambio.pack(fill="both", expand=True, padx=0, pady=0)
            self.actualizar_saldo_cambio()
            self.panel_cambio_visible = True
            self.btn_cambio.configure(style="NavActivo.TButton")
            self.btn_ventas.configure(style="NavInactivo.TButton")
            self.btn_historial.configure(style="NavInactivo.TButton")
            self.btn_corte.configure(style="NavInactivo.TButton")
    def ocultar_panel_cambio(self):
        if self.panel_cambio_visible:
            self.frame_contenido_cambio.pack_forget()
            self.panel_cambio_visible = False
            self.btn_cambio.configure(style="NavInactivo.TButton")

    def toggle_panel_corte(self):
        if self.panel_corte_visible:
            self.ocultar_panel_corte()
        else:
            self.mostrar_panel_corte()
    def mostrar_panel_corte(self):
        if self.panel_ventas_visible:
            self.ocultar_panel_ventas()
        if self.panel_historial_visible:
            self.ocultar_panel_historial()
        if self.panel_cambio_visible:
            self.ocultar_panel_cambio()
        if not self.panel_corte_visible:
            self.frame_contenido_corte.pack(fill="both", expand=True, padx=0, pady=0)
            self.cargar_resumen_corte()
            self.panel_corte_visible = True
            self.btn_corte.configure(style="NavActivo.TButton")
            self.btn_ventas.configure(style="NavInactivo.TButton")
            self.btn_historial.configure(style="NavInactivo.TButton")
            self.btn_cambio.configure(style="NavInactivo.TButton")
    def ocultar_panel_corte(self):
        if self.panel_corte_visible:
            self.frame_contenido_corte.pack_forget()
            self.panel_corte_visible = False
            self.btn_corte.configure(style="NavInactivo.TButton")

