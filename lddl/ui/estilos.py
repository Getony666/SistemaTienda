"""Estilos ttk compartidos por toda la interfaz.

ttkbootstrap retematiza los widgets ttk estandar (Treeview, Combobox, Entry,
Scrollbar, etc.) automaticamente al crear la ventana con un tema. Los widgets
que dibujan su propio color por instancia en el codigo original (Button,
Checkbutton, Radiobutton) no aceptan `fg=`/`bg=` en ttk: aqui se registran
como estilos con nombre, uno por color semantico usado en la app, para
conservar el mismo lenguaje de colores por accion.

Paleta verde azulado (linea "Panel de control") aprobada sobre la maqueta del
panel de Ventas: lienzo muy claro con tarjetas blancas encima y barra de
navegacion solida en verde azulado oscuro con la pestana activa en blanco.
ttk no dibuja esquinas redondeadas ni sombras, asi que el lienzo va un punto
mas oscuro que en la maqueta para que la tarjeta blanca se despegue igual.

Regla de fondos: el fondo por defecto de TFrame/TLabel es el BLANCO de la
tarjeta, porque casi todo el contenido vive dentro de una. Los contenedores
que quedan por fuera (el armazon de la ventana y las columnas) se marcan
explicitamente con el estilo `Lienzo.TFrame`.
"""

FUENTE_BASE = ("Segoe UI", 9)
FUENTE_TITULO = ("Segoe UI", 11, "bold")
FUENTE_TARJETA = ("Segoe UI", 8, "bold")
FUENTE_CIFRA = ("Segoe UI", 14, "bold")

# ---- Lienzo y tarjetas ----
COLOR_LIENZO = "#EDF2EF"
COLOR_TARJETA = "#FFFFFF"
COLOR_BORDE = "#DDE7E1"
COLOR_TEXTO = "#233129"
COLOR_TEXTO_SUAVE = "#68796F"

# ---- Acentos ----
COLOR_TOTAL = "#1F5A4C"
COLOR_VUELTO_FONDO = "#EAF4EF"
COLOR_VUELTO_BORDE = "#C9D6CE"
COLOR_VUELTO_VALOR = "#1F7A4C"
COLOR_TABLA_CABECERA = "#8B968D"
COLOR_PASTILLA_ON = "#B87B1E"
COLOR_PASTILLA_OK = "#2E9E6B"
COLOR_SELECCION = "#2E7D6B"

# ---- Barra de navegacion ----
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
    "Neutro": ("#68796F", "#55655C", "white"),
    "Quick": ("#FFFFFF", "#EAF4EF", "#233129"),
}

# (nombre_estilo, color_texto)
PALETA_TEXTO_MARCADO = {
    "Success": "#23824F",
    "Purple": "#7B4FA3",
    "DeepOrange": "#D2691E",
    "Danger": "#C4432E",
}

# Pastillas de la seccion Pago: (nombre_estilo, color_cuando_esta_marcada)
PALETA_PASTILLAS = {
    "Pastilla": COLOR_PASTILLA_ON,
    "PastillaOk": COLOR_PASTILLA_OK,
}


def _borde(style, nombre, color):
    """clam dibuja el borde con tres colores; los tres iguales dan una linea de 1px."""
    style.configure(nombre, bordercolor=color, lightcolor=color, darkcolor=color)


def configurar_estilos(style):
    """Registra las fuentes y estilos ttk con nombre usados en toda la app."""
    style.configure(".", font=FUENTE_BASE)

    # ---- Fondos: blanco de tarjeta por defecto, lienzo solo donde se pide ----
    style.configure("TFrame", background=COLOR_TARJETA)
    style.configure("TLabel", background=COLOR_TARJETA, foreground=COLOR_TEXTO)
    style.configure("TCheckbutton", background=COLOR_TARJETA)
    style.configure("TRadiobutton", background=COLOR_TARJETA)
    style.configure("Lienzo.TFrame", background=COLOR_LIENZO)
    style.configure("Lienzo.TLabel", background=COLOR_LIENZO, foreground=COLOR_TEXTO_SUAVE)

    # ---- Tarjetas: panel blanco con borde fino y titulo en versalitas ----
    style.configure("TLabelframe", background=COLOR_TARJETA, relief="solid", borderwidth=1)
    _borde(style, "TLabelframe", COLOR_BORDE)
    style.configure("TLabelframe.Label", background=COLOR_TARJETA,
                    foreground=COLOR_TEXTO_SUAVE, font=FUENTE_TARJETA)

    # ---- Botones de accion ----
    for nombre, (color, hover, texto) in PALETA_BOTONES.items():
        estilo = f"{nombre}.TButton"
        style.configure(estilo, background=color, foreground=texto,
                        borderwidth=0, focusthickness=0, padding=(11, 6))
        style.map(estilo,
                  background=[("active", hover), ("pressed", hover), ("disabled", "#B0BEC5")],
                  foreground=[("disabled", "#ECEFF1")])

        # Variante para botones de cuadricula con texto largo (ej. panel de Acciones)
        estilo_ajustado = f"{nombre}Ajustado.TButton"
        style.configure(estilo_ajustado, background=color, foreground=texto,
                        borderwidth=0, focusthickness=0, padding=(8, 7), wraplength=130)
        style.map(estilo_ajustado,
                  background=[("active", hover), ("pressed", hover), ("disabled", "#B0BEC5")],
                  foreground=[("disabled", "#ECEFF1")])

    for nombre, texto in PALETA_TEXTO_MARCADO.items():
        estilo_chk = f"{nombre}.TCheckbutton"
        style.configure(estilo_chk, foreground=texto, background=COLOR_TARJETA)
        estilo_rad = f"{nombre}.TRadiobutton"
        style.configure(estilo_rad, foreground=texto, background=COLOR_TARJETA)

    # Los botones de denominacion son blancos: sin borde desaparecen cuando el
    # fondo tambien es blanco (dialogo de Pagar Deuda), asi que llevan linea fina.
    style.configure("Quick.TButton", relief="solid", borderwidth=1)
    _borde(style, "Quick.TButton", COLOR_VUELTO_BORDE)

    style.configure("DeudaBold.TCheckbutton", foreground="#C4432E",
                    background=COLOR_TARJETA, font=("Segoe UI", 8, "bold"))
    style.configure("Titulo.TLabel", font=FUENTE_TITULO, background=COLOR_TARJETA)

    # ---- Pastillas de la seccion Pago (Checkbutton dibujado como boton) ----
    for nombre, color_on in PALETA_PASTILLAS.items():
        estilo = f"{nombre}.Toolbutton"
        style.configure(estilo, background=COLOR_TARJETA, foreground=COLOR_TEXTO_SUAVE,
                        relief="solid", borderwidth=1, focusthickness=0,
                        padding=(12, 5), font=FUENTE_TARJETA, anchor="center")
        _borde(style, estilo, COLOR_BORDE)
        style.map(estilo,
                  background=[("selected", color_on), ("active", COLOR_VUELTO_FONDO)],
                  foreground=[("selected", "white"), ("active", COLOR_TEXTO)],
                  bordercolor=[("selected", color_on)],
                  lightcolor=[("selected", color_on)],
                  darkcolor=[("selected", color_on)])

    # ---- Cifras destacadas ----
    style.configure("TotalEtiqueta.TLabel", background=COLOR_TARJETA,
                    foreground=COLOR_TEXTO_SUAVE, font=("Segoe UI", 9, "bold"))
    style.configure("TotalValor.TLabel", background=COLOR_TARJETA,
                    foreground=COLOR_TOTAL, font=FUENTE_CIFRA)
    style.configure("TotalMoneda.TLabel", background=COLOR_TARJETA,
                    foreground=COLOR_TOTAL, font=("Segoe UI", 9, "bold"))
    # Cifra verde sobre tarjeta blanca (el vuelto en los dialogos, sin banda detras)
    style.configure("CifraVerde.TLabel", background=COLOR_TARJETA,
                    foreground=COLOR_VUELTO_VALOR, font=FUENTE_CIFRA)

    # ---- Banda del Vuelto ----
    style.configure("Vuelto.TFrame", background=COLOR_VUELTO_FONDO)
    style.configure("Vuelto.TLabel", background=COLOR_VUELTO_FONDO,
                    foreground=COLOR_TEXTO_SUAVE)
    style.configure("VueltoValor.TLabel", background=COLOR_VUELTO_FONDO,
                    foreground=COLOR_VUELTO_VALOR, font=FUENTE_CIFRA)
    style.configure("VueltoMoneda.TLabel", background=COLOR_VUELTO_FONDO,
                    foreground=COLOR_TEXTO_SUAVE, font=("Segoe UI", 9, "bold"))
    style.configure("VueltoResto.TLabel", background=COLOR_VUELTO_FONDO,
                    foreground=COLOR_TEXTO_SUAVE, font=("Segoe UI", 8, "italic"))

    # ---- Hueco donde aparecen los formularios de Acciones ----
    style.configure("Placeholder.TFrame", background=COLOR_TARJETA,
                    relief="solid", borderwidth=1)
    _borde(style, "Placeholder.TFrame", COLOR_VUELTO_BORDE)
    style.configure("Placeholder.TLabel", background=COLOR_TARJETA,
                    foreground=COLOR_TABLA_CABECERA, font=("Segoe UI", 8, "italic"))

    # ---- Tablas: cabecera gris en versalitas y filas mas aireadas ----
    style.configure("Treeview", background=COLOR_TARJETA, fieldbackground=COLOR_TARJETA,
                    foreground=COLOR_TEXTO, rowheight=22, borderwidth=0)
    style.configure("Treeview.Heading", background=COLOR_TARJETA,
                    foreground=COLOR_TABLA_CABECERA, font=FUENTE_TARJETA,
                    relief="flat", padding=(6, 4))
    style.map("Treeview.Heading", background=[("active", COLOR_VUELTO_FONDO)])
    style.map("Treeview", background=[("selected", COLOR_SELECCION)],
              foreground=[("selected", "white")])

    # ---- Barra de navegacion: franja solida con la pestana activa en blanco ----
    style.configure("NavBar.TFrame", background=COLOR_NAV_FONDO)
    style.configure("NavActivo.TButton", background="white", foreground=COLOR_NAV_FONDO,
                    borderwidth=0, focusthickness=0, padding=(12, 6), font=("Segoe UI", 10, "bold"))
    style.map("NavActivo.TButton", background=[("active", "white")])
    style.configure("NavInactivo.TButton", background=COLOR_NAV_FONDO, foreground=COLOR_NAV_TEXTO_INACTIVO,
                    borderwidth=0, focusthickness=0, padding=(12, 6), font=("Segoe UI", 10, "bold"))
    style.map("NavInactivo.TButton",
              background=[("active", COLOR_NAV_HOVER)],
              foreground=[("active", "white")])
