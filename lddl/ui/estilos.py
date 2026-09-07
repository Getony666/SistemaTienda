"""Estilos ttk compartidos por toda la interfaz.

ttkbootstrap retematiza los widgets ttk estandar (Treeview, Combobox, Entry,
Scrollbar, etc.) automaticamente al crear la ventana con un tema. Los widgets
que dibujan su propio color por instancia en el codigo original (Button,
Checkbutton, Radiobutton) no aceptan `fg=`/`bg=` en ttk: aqui se registran
como estilos con nombre, uno por color semantico usado en la app, para
conservar el mismo lenguaje de colores por accion.

Paleta verde azulado (linea "Panel de control") aprobada sobre la maqueta
del panel de Ventas: fondo de lienzo muy claro, barra de navegacion solida
en verde azulado oscuro con la pestana activa en blanco.
"""

FUENTE_BASE = ("Segoe UI", 10)
FUENTE_TITULO = ("Segoe UI", 12, "bold")

COLOR_LIENZO = "#F6F9F7"
COLOR_NAV_FONDO = "#1F5A4C"
COLOR_NAV_TEXTO_INACTIVO = "#CFE8DF"
COLOR_NAV_HOVER = "#28685A"

# (nombre_estilo, color_normal, color_hover, color_texto)
PALETA_BOTONES = {
    "Primary": ("#2E7D6B", "#1F5A4C", "white"),
    "PrimaryOscuro": ("#1F5A4C", "#16413A", "white"),
    "Success": ("#2E9E6B", "#23824F", "white"),
    "Danger": ("#C4432E", "#A8351F", "white"),
    "Warning": ("#B87B1E", "#96630F", "white"),
    "WarningOscuro": ("#96630F", "#744C0B", "white"),
    "Purple": ("#7B4FA3", "#63397F", "white"),
    "PurpleOscuro": ("#63397F", "#4C2B63", "white"),
    "Brown": ("#7A5C46", "#5C4433", "white"),
    "BrownOscuro": ("#5C4433", "#432F24", "white"),
    "DeepOrange": ("#D2691E", "#B85A18", "white"),
    "Quick": ("#FFFFFF", "#EAF4EF", "#233129"),
}

# (nombre_estilo, color_texto)
PALETA_TEXTO_MARCADO = {
    "Success": "#23824F",
    "Purple": "#7B4FA3",
    "DeepOrange": "#D2691E",
    "Danger": "#C4432E",
}


def configurar_estilos(style):
    """Registra las fuentes y estilos ttk con nombre usados en toda la app."""
    style.configure(".", font=FUENTE_BASE)
    style.configure("TFrame", background=COLOR_LIENZO)
    style.configure("TLabelframe", background=COLOR_LIENZO)
    style.configure("TLabelframe.Label", background=COLOR_LIENZO, font=("Segoe UI", 10, "bold"))
    style.configure("TLabel", background=COLOR_LIENZO)
    style.configure("TCheckbutton", background=COLOR_LIENZO)
    style.configure("TRadiobutton", background=COLOR_LIENZO)

    for nombre, (color, hover, texto) in PALETA_BOTONES.items():
        estilo = f"{nombre}.TButton"
        style.configure(estilo, background=color, foreground=texto,
                         borderwidth=0, focusthickness=0, padding=(12, 8))
        style.map(estilo,
                   background=[("active", hover), ("pressed", hover), ("disabled", "#B0BEC5")],
                   foreground=[("disabled", "#ECEFF1")])

        # Variante para botones de cuadricula con texto largo (ej. panel de Acciones)
        estilo_ajustado = f"{nombre}Ajustado.TButton"
        style.configure(estilo_ajustado, background=color, foreground=texto,
                         borderwidth=0, focusthickness=0, padding=(8, 8), wraplength=130)
        style.map(estilo_ajustado,
                   background=[("active", hover), ("pressed", hover), ("disabled", "#B0BEC5")],
                   foreground=[("disabled", "#ECEFF1")])

    for nombre, texto in PALETA_TEXTO_MARCADO.items():
        estilo_chk = f"{nombre}.TCheckbutton"
        style.configure(estilo_chk, foreground=texto, background=COLOR_LIENZO)
        estilo_rad = f"{nombre}.TRadiobutton"
        style.configure(estilo_rad, foreground=texto, background=COLOR_LIENZO)

    style.configure("DeudaBold.TCheckbutton", foreground="#C4432E", background=COLOR_LIENZO, font=("Segoe UI", 9, "bold"))
    style.configure("Titulo.TLabel", font=FUENTE_TITULO, background=COLOR_LIENZO)

    # Filas seleccionadas en las tablas (Treeview) en verde azulado, a tono con el resto
    style.map("Treeview", background=[("selected", "#2E7D6B")], foreground=[("selected", "white")])

    # ---- Barra de navegacion: franja solida con la pestana activa en blanco ----
    style.configure("NavBar.TFrame", background=COLOR_NAV_FONDO)
    style.configure("NavActivo.TButton", background="white", foreground=COLOR_NAV_FONDO,
                     borderwidth=0, focusthickness=0, padding=(16, 10), font=("Segoe UI", 10, "bold"))
    style.map("NavActivo.TButton", background=[("active", "white")])
    style.configure("NavInactivo.TButton", background=COLOR_NAV_FONDO, foreground=COLOR_NAV_TEXTO_INACTIVO,
                     borderwidth=0, focusthickness=0, padding=(16, 10), font=("Segoe UI", 10, "bold"))
    style.map("NavInactivo.TButton",
               background=[("active", COLOR_NAV_HOVER)],
               foreground=[("active", "white")])
