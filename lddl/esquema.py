"""Creación y migración del esquema de la base de datos.

Cada arranque comprueba que existan las tablas y columnas que el programa
necesita, y añade las que falten sin tocar los datos ya guardados."""

from .rutas import conectar_db


def preparar_base():
    """Deja la base lista para trabajar: tablas al día y permisos sembrados.

    Lo llaman la ventana de tkinter y el arranque de la API. Antes sólo lo
    hacía tkinter, así que la aplicación de React se abría sin comprobar el
    esquema: las tablas nuevas no llegaban a crearse.
    """
    verificar_y_crear_columnas()
    from .usuarios import sembrar_permisos_si_hace_falta
    sembrar_permisos_si_hace_falta()


def verificar_y_crear_columnas():
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(ventas)")
        columnas_ventas = [col[1] for col in cursor.fetchall()]
        if "cancelada" not in columnas_ventas:
            cursor.execute("ALTER TABLE ventas ADD COLUMN cancelada INTEGER DEFAULT 0")
            conn.commit()
        if "saldo_pendiente" not in columnas_ventas:
            cursor.execute("ALTER TABLE ventas ADD COLUMN saldo_pendiente REAL DEFAULT 0")
            conn.commit()
        if "metodo_pago_real" not in columnas_ventas:
            cursor.execute("ALTER TABLE ventas ADD COLUMN metodo_pago_real TEXT DEFAULT ''")
            conn.commit()
        if "observaciones" not in columnas_ventas:
            cursor.execute("ALTER TABLE ventas ADD COLUMN observaciones TEXT DEFAULT ''")
            conn.commit()
        if "pago_texto" not in columnas_ventas:
            cursor.execute("ALTER TABLE ventas ADD COLUMN pago_texto TEXT DEFAULT ''")
            conn.commit()
        if "vuelto_texto" not in columnas_ventas:
            cursor.execute("ALTER TABLE ventas ADD COLUMN vuelto_texto TEXT DEFAULT ''")
            conn.commit()
        if "monto_efectivo" not in columnas_ventas:
            cursor.execute("ALTER TABLE ventas ADD COLUMN monto_efectivo REAL DEFAULT 0")
            conn.commit()
        if "monto_transferencia" not in columnas_ventas:
            cursor.execute("ALTER TABLE ventas ADD COLUMN monto_transferencia REAL DEFAULT 0")
            conn.commit()

        # Divisa neta que entró al fondo por esta venta (pago menos vuelto en divisa).
        # Sin este dato la reversión tendría que adivinarla a partir del total.
        if "monto_divisa_neto" not in columnas_ventas:
            cursor.execute("ALTER TABLE ventas ADD COLUMN monto_divisa_neto REAL DEFAULT 0")
            conn.commit()


        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cobros_deudas'")
        if not cursor.fetchone():
            cursor.execute('''
                CREATE TABLE cobros_deudas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha TEXT NOT NULL,
                    venta_id INTEGER NOT NULL,
                    monto REAL NOT NULL,
                    metodo_pago TEXT NOT NULL,
                    moneda TEXT DEFAULT 'CUP',
                    tasa REAL DEFAULT 1.0,
                    monto_cup REAL DEFAULT 0,
                    monto_divisa_neto REAL DEFAULT 0
                )
            ''')
            conn.commit()
        else:
            cursor.execute("PRAGMA table_info(cobros_deudas)")
            columnas_cobros = [col[1] for col in cursor.fetchall()]
            if "metodo_pago" not in columnas_cobros:
                cursor.execute("ALTER TABLE cobros_deudas ADD COLUMN metodo_pago TEXT DEFAULT 'Efectivo'")
                conn.commit()
            if "moneda" not in columnas_cobros:
                cursor.execute("ALTER TABLE cobros_deudas ADD COLUMN moneda TEXT DEFAULT 'CUP'")
                conn.commit()
            if "tasa" not in columnas_cobros:
                cursor.execute("ALTER TABLE cobros_deudas ADD COLUMN tasa REAL DEFAULT 1.0")
                conn.commit()
            if "monto_cup" not in columnas_cobros:
                cursor.execute("ALTER TABLE cobros_deudas ADD COLUMN monto_cup REAL DEFAULT 0")
                conn.commit()
            if "monto_divisa_neto" not in columnas_cobros:
                cursor.execute("ALTER TABLE cobros_deudas ADD COLUMN monto_divisa_neto REAL DEFAULT 0")
                conn.commit()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='salidas_inventario'")
        if not cursor.fetchone():
            cursor.execute('''
                CREATE TABLE salidas_inventario (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha TEXT NOT NULL,
                    producto_id INTEGER NOT NULL,
                    cantidad REAL NOT NULL,
                    precio_costo REAL NOT NULL,
                    motivo TEXT,
                    FOREIGN KEY (producto_id) REFERENCES productos(id)
                )
            ''')
            conn.commit()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='operaciones_cambio'")
        if not cursor.fetchone():
            cursor.execute('''
                CREATE TABLE operaciones_cambio (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha TEXT NOT NULL,
                    tipo TEXT NOT NULL,
                    moneda TEXT NOT NULL,
                    cantidad REAL NOT NULL,
                    tasa REAL NOT NULL,
                    monto_cup REAL NOT NULL,
                    observaciones TEXT
                )
            ''')
            conn.commit()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fondo_divisas'")
        if not cursor.fetchone():
            cursor.execute('''
                CREATE TABLE fondo_divisas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha TEXT NOT NULL,
                    moneda TEXT NOT NULL,
                    cantidad REAL NOT NULL,
                    UNIQUE(fecha, moneda)
                )
            ''')
            conn.commit()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='entradas_efectivo'")
        if not cursor.fetchone():
            cursor.execute('''
                CREATE TABLE entradas_efectivo (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha TEXT NOT NULL,
                    moneda TEXT NOT NULL,
                    monto REAL NOT NULL,
                    descripcion TEXT
                )
            ''')
            conn.commit()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='salidas_efectivo'")
        if not cursor.fetchone():
            cursor.execute('''
                CREATE TABLE salidas_efectivo (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha TEXT NOT NULL,
                    moneda TEXT NOT NULL,
                    monto REAL NOT NULL,
                    descripcion TEXT
                )
            ''')
            conn.commit()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='historial'")
        if not cursor.fetchone():
            cursor.execute('''
                CREATE TABLE historial (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha TEXT NOT NULL,
                    tipo_accion TEXT NOT NULL,
                    descripcion TEXT,
                    detalles TEXT
                )
            ''')
            conn.commit()

        # venta_id enlaza los movimientos de caja con la venta o deuda que los generó,
        # para poder revertirlos con exactitud al eliminar el registro del historial.
        # Va al final, cuando ya se sabe que ambas tablas existen.
        for tabla in ("entradas_efectivo", "salidas_efectivo"):
            cursor.execute(f"PRAGMA table_info({tabla})")
            columnas_mov = [col[1] for col in cursor.fetchall()]
            if columnas_mov and "venta_id" not in columnas_mov:
                cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN venta_id INTEGER")
                conn.commit()

        # La categoría no es obligatoria y antes se guardaba vacía sin más.
        # Los productos de siempre (categoria NULL o en blanco) pasan a
        # "Otros" para que el filtro del almacén no los deje fuera. Vuelto a
        # correr no cambia nada: ya no queda ninguno vacío que tocar.
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='productos'")
        if cursor.fetchone():
            cursor.execute('''
                UPDATE productos SET categoria = 'Otros'
                WHERE categoria IS NULL OR TRIM(categoria) = ''
            ''')
            conn.commit()

        # ------------------------------------------------------ usuarios
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='usuarios'")
        if not cursor.fetchone():
            cursor.execute('''
                CREATE TABLE usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL UNIQUE,
                    rol TEXT NOT NULL,
                    pin TEXT NOT NULL,
                    activo INTEGER DEFAULT 1,
                    creado TEXT
                )
            ''')
            conn.commit()

        # Los permisos son datos: el Admin los cambia desde el programa. La
        # clave doble deja usar ON CONFLICT al concederlos o quitarlos.
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='permisos_rol'")
        if not cursor.fetchone():
            cursor.execute('''
                CREATE TABLE permisos_rol (
                    rol TEXT NOT NULL,
                    permiso TEXT NOT NULL,
                    concedido INTEGER DEFAULT 0,
                    PRIMARY KEY (rol, permiso)
                )
            ''')
            conn.commit()

        # Quién hizo cada cosa. Va en las seis tablas que el historial enseña,
        # para que ninguna linea salga sin nombre.
        for tabla in ("ventas", "historial", "entradas_efectivo", "salidas_efectivo",
                      "operaciones_cambio", "salidas_inventario"):
            cursor.execute(f"PRAGMA table_info({tabla})")
            columnas_tabla = [col[1] for col in cursor.fetchall()]
            if columnas_tabla and "usuario" not in columnas_tabla:
                cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN usuario TEXT DEFAULT ''")
                conn.commit()

        conn.close()
    except Exception as e:
        print(f"Error al verificar/crear columnas: {e}")
