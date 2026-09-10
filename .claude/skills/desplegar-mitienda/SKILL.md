---
name: desplegar-mitienda
description: Compilar, probar y entregar MiTienda. Usar siempre que haya que recompilar el .exe, preparar la carpeta que va a una tienda, dejar la base virgen para un negocio nuevo, ensayar cambios sin tocar datos reales, o recuperar el acceso de Admin. También recoge las trampas de este proyecto (el bundle de React, los acentos, la base de las pruebas) que ya han mordido antes.
---

# Desplegar MiTienda

Punto de venta de una tienda cubana. Lógica en Python, interfaz en React
dentro de una ventana de escritorio (pywebview + WebView2), todo empaquetado
en un solo `.exe` con PyInstaller.

Raíz del proyecto: `C:\Users\Mirielys\Documents\Py\LDDL`

## Las tres trampas de este proyecto

Antes que nada, porque las tres ya han costado un rato:

1. **El bundle de React se empaqueta tal como esté.** PyInstaller mete
   `interfaz/dist` dentro del `.exe` sin mirar si está al día. Si cambias
   algo de React y compilas sin `npm run build`, el ejecutable sale con la
   interfaz vieja **y no avisa de nada**. Siempre los dos pasos, en orden.

2. **Nunca añadir texto a un archivo con PowerShell.** `Get-Content -Raw`
   lee UTF-8 como ANSI y `Add-Content -Encoding utf8` lo vuelve a codificar:
   cada acento queda doble (`automáticamente` → `automÃ¡ticamente`). Para
   añadir o editar, usar Python abriendo con `encoding="utf-8", newline=""`,
   o las herramientas de edición. Comprobar después:
   `python -c "import re; print(len(re.findall(rb'\xc3\x83|\xc3\x82', open(RUTA,'rb').read())))"` → tiene que dar 0.
   Y ojo: **la consola engaña**. Al imprimir texto roto lo reencodea y se ve
   bien. Hay que mirar los BYTES.

3. **Las pruebas no usan `tienda.db`.** Esa se entrega vacía a cada negocio.
   Las pruebas leen `pruebas/tienda_de_pruebas.db` a través de
   `pruebas/base.py`, que reparte copias temporales ya migradas. Si una
   prueba nueva necesita datos, que los pida ahí.

## Compilar

Dos pasos. El primero no se salta.

```
cd interfaz
npm run build
cd ..

python -m PyInstaller --noconfirm --onefile --windowed ^
    --name MiTienda ^
    --icon icono_pos.ico ^
    --add-data "interfaz/dist;interfaz/dist" ^
    --collect-all webview ^
    --collect-all uvicorn ^
    --exclude-module pandas --exclude-module matplotlib ^
    --exclude-module ttkbootstrap --exclude-module tkinter ^
    escritorio.py
```

Si `npm` no responde, es que el PATH de la sesión no lo tiene:
`$env:Path = "C:\Program Files\nodejs;" + $env:Path`

Sale en `dist\MiTienda.exe`, unos 21 MB.

### Por qué cada opción

- `--add-data "interfaz/dist;interfaz/dist"` — es la interfaz.
  `escritorio.py` la busca en `sys._MEIPASS`; sin ella se cierra avisando.
- `--collect-all webview` — pywebview usa WebView2 vía pythonnet y lleva
  archivos que PyInstaller no descubre solo.
- `--collect-all uvicorn` — carga sus protocolos por nombre en tiempo de
  ejecución. Sin esto compila bien y **falla al arrancar**.
- Las exclusiones — las usaba la ventana vieja de tkinter, que ya no está en
  el proyecto. Se dejan igual en el comando: son inofensivas y evitan que
  alguna dependencia nueva las arrastre de vuelta sin que nadie lo note.
  Quitarlas baja el ejecutable de 41 MB a 21 MB.

### Si el .exe no arranca

`--windowed` esconde los errores. Compilar igual pero con `--console` y otro
`--name`, lanzarlo y leer la traza. Así se encontró en su día que faltaban
los recursos de ttkbootstrap.

**Ventana en blanco** = la interfaz llegó pero no cargó. Casi siempre son los
tipos MIME: Windows guarda `.js` como `text/plain` en el registro y WebView2
rechaza el módulo. `escritorio.py` los declara a mano; es lo primero a mirar.

## Comprobar antes de entregar

```
python -m unittest discover -s pruebas
```

Y arrancar el `.exe` desde una carpeta con su `tienda.db` al lado. Que abra
la ventana no basta: hay que ver que **carga datos**. Comprobaciones útiles
sobre el proceso ya lanzado:

- ¿Qué puerto abrió? `Get-NetTCPConnection -State Listen | Where-Object { $pids -contains $_.OwningProcess }`
- `/salud`, `/productos`, `/corte/<fecha>` tienen que responder 200.
- El `.js` tiene que servirse como `application/javascript`, no `text/plain`.

## Ensayar sin tocar nada

```
python servir.py 8140            # con los datos de prueba
python servir.py 8140 virgen     # base vacía, como una tienda estrenada
```

Levanta la aplicación contra una **copia** en el temporal. Nunca toca
`tienda.db`. Útil para probar cambios en el navegador antes de empaquetar.

## Entregar a un negocio

La tienda no se lleva la carpeta del proyecto: se lleva **tres archivos**.

```
MiTienda-Tienda\
    MiTienda.exe        el programa entero
    tienda.db           la base
    config_caja.json    los fondos de caja
```

**Nunca copiar LDDL a una tienda**: `.git/config` lleva el token de GitHub en
texto plano, y además les entregaría el código fuente completo.

Para dejar la base virgen:

```
python vaciar_tablas.py                          # la de al lado
python vaciar_tablas.py "ruta\a\tienda.db" --si  # otra, sin preguntar
```

Borra todo -productos incluidos-, reinicia los contadores y vacía
`config_caja.json`. Guarda copia con la fecha antes de tocar nada; esas
copias **no** deben viajar a la tienda, hay que quitarlas de la carpeta.

La computadora de la tienda necesita **WebView2**. En Windows 11 viene de
fábrica.

## Usuarios y permisos

La primera vez que se abre, el programa pide crear el Admin. No se reparte
ningún PIN de fábrica: cada tienda pone el suyo.

Si olvidan el PIN de Admin:

```
python restablecer_admin.py
```

Los permisos se comprueban **en la API**, no en la pantalla: cada ruta que
escribe lleva `dependencies=[exige("...")]` y contesta 403 sin tocar la base.
Esconder botones en React es sólo comodidad. Si añades una ruta que escriba,
ponle su permiso: hay una prueba que falla si se te olvida.

## Cambiar el nombre para otro negocio

Vive en un solo sitio, `lddl/__init__.py`:

```python
NOMBRE_APP = "MiTienda"
```

Cámbialo ahí y ajusta `--name` e `--icon` al compilar.

## Mapa rápido

| Dónde | Qué |
|---|---|
| `lddl/calculo_cobro.py` | vuelto y desglose del pago, sin interfaz |
| `lddl/calculo_deuda.py` | cobro de deudas |
| `lddl/carrito.py` | el carrito, funciones puras |
| `lddl/api.py` | la API; aquí viven los permisos de cada ruta |
| `lddl/sesion.py` | quién está dentro ahora |
| `lddl/usuarios.py` | usuarios, roles, permisos, PIN cifrado |
| `lddl/esquema.py` | crea y migra tablas; `preparar_base()` al arrancar |
| `interfaz/src/` | React |
| `pruebas/acta_de_la_app_vieja.json` | testimonio de la ventana de tkinter que hubo antes de React |

## Detalles que se olvidan

- La base se busca **junto al ejecutable** (`obtener_ruta_base()` en
  `lddl/rutas.py`), no dentro del `.exe`.
- Las fechas de la interfaz se arman campo a campo, nunca con
  `toISOString()`: eso da UTC y Cuba va 4-5 horas por detrás. Con UTC, toda
  venta hecha después de las 8 de la noche caía en el día siguiente y el
  corte de caja salía vacío.
- No dejar el `.exe` corriendo en dos carpetas a la vez: son dos bases
  distintas y las ventas se reparten entre ellas.
