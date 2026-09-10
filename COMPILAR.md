# Compilar el ejecutable

La interfaz del programa es la de React. Se compila en dos pasos, y el
primero no se puede saltar: PyInstaller mete dentro del `.exe` la carpeta
`interfaz/dist` **tal como esté en ese momento**, así que si no se
reconstruye antes, el ejecutable sale con la interfaz vieja.

```
cd interfaz
npm install
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

El resultado queda en `dist\MiTienda.exe`. Cópialo a la carpeta donde estén
`tienda.db` y `config_caja.json`: el programa los busca **junto al ejecutable**
(ver `obtener_ruta_base()` en `lddl/rutas.py`). La interfaz viaja dentro del
`.exe` y se descomprime en una carpeta temporal; la base de datos no, y así
debe seguir siendo, o cada actualización del programa se llevaría por delante
las ventas.

## Por qué cada opción

- **`--add-data "interfaz/dist;interfaz/dist"`** — imprescindible. Es la
  interfaz. `escritorio.py` la busca en `sys._MEIPASS` cuando está
  empaquetado, y si no la encuentra se cierra avisando.

- **`--collect-all webview`** — pywebview abre la ventana nativa apoyándose en
  WebView2 a través de pythonnet. Lleva archivos de datos y ensamblados que
  PyInstaller no descubre solo.

- **`--collect-all uvicorn`** — uvicorn carga sus protocolos y bucles por
  nombre, en tiempo de ejecución. Sin esto compila bien y falla al arrancar.

- **`--exclude-module`** de pandas, matplotlib, tkinter y ttkbootstrap — los
  usaba la ventana vieja de tkinter, que ya no está en el proyecto. Se dejan
  igual en el comando: son inofensivas y evitan que alguna dependencia nueva
  los arrastre de vuelta sin que nadie lo note. Quitarlos baja el ejecutable
  de unos 43 MB a unos 18 MB.

- **`--windowed`** — sin consola detrás. El precio es que los errores de
  arranque no se ven: para diagnosticarlos, compila igual pero con
  `--console` y otro `--name`, lánzalo y lee la traza. Es como se encontró en
  su día que faltaban los recursos de ttkbootstrap.

- **`--onefile`** — un solo fichero, más cómodo de repartir. Arranca algo más
  lento porque se descomprime en una carpeta temporal en cada ejecución.

## Los tipos MIME, que ya dieron guerra

Windows guarda los tipos MIME en el registro y en muchas máquinas `.js` está
apuntado a `text/plain`. Python lee de ahí, el WebView2 rechazaba el módulo de
React —*"Expected a JavaScript module, got text/plain"*— y la ventana salía en
blanco. `escritorio.py` los declara a mano antes de servir nada. Si algún día
vuelve a salir la ventana vacía, es lo primero que hay que mirar.

## La ventana de tkinter

`ventas.py` y `lddl/ui/` ya no están en el repositorio: se retiraron una vez
que la interfaz de React quedó terminada. De ellos colgaban las pruebas de
caracterización que demuestran que las cuentas del cobro, del carrito y de
las deudas no cambiaron al mudarse a React; para no perder esa red, antes de
borrar el código se hizo repasar a la ventana esos mismos casos una última
vez y se grabó lo que contestó en `pruebas/acta_de_la_app_vieja.json`. Las
pruebas comparan hoy contra ese acta en vez de abrir una ventana de verdad.

## Usuarios y permisos

La primera vez que se abre el programa en una tienda, pide crear el usuario
**Admin**. No se reparte ningún PIN de fábrica: si viniera uno puesto, sería
el mismo en todos los negocios a los que se venda esto, y en el primero que
alguien lo cuente deja de servir. Cada tienda pone el suyo.

Los permisos de Boss y Empleado se cambian desde el propio programa, en la
pestaña **Usuarios**, que sólo ve Admin.

**Si en una tienda olvidan el PIN de Admin**, no quedan encerrados:

```
python restablecer_admin.py
```

Se ejecuta en la máquina de la tienda, sobre la `tienda.db` que tenga al
lado, y deja constancia en el historial. No abre ninguna puerta que no
estuviera abierta: quien tiene el fichero de la base delante siempre pudo
hacer lo mismo a mano.

### Hasta dónde protege esto

El PIN se guarda cifrado con pbkdf2, así que **no se puede leer** de la base.
Lo que impide que un Empleado haga de más es la API, que contesta 403 y no
toca la base: esconder botones en la pantalla es sólo comodidad.

Lo que **no** protege: la base es un fichero al lado del ejecutable, y quien
pueda editarlo puede saltárselo todo. Para una tienda es suficiente. Para el
día que el panel del dueño salga a internet, no: entonces la sesión, que hoy
vive en memoria dentro del proceso, tiene que pasar a ser un identificador
por cada cliente.

## Cambiar el nombre para otro negocio

El nombre vive en un solo sitio, `lddl/__init__.py`:

```python
NOMBRE_APP = "MiTienda"
```

Cámbialo ahí y ajusta el `--name` y el `--icon` al compilar. Con eso cambian
el título de la ventana, el de la API y el del ejecutable.

## Antes de entregar

```
python -m unittest discover -s pruebas
```

Y arranca el ejecutable una vez, desde una carpeta con su `tienda.db` al lado:
que abra la ventana **y que se vean los productos** es la única forma de saber
que no le falta ningún recurso empaquetado. Una ventana en blanco significa
que la interfaz llegó pero no cargó; una ventana que no abre, que falta algo
del lado de Python.
