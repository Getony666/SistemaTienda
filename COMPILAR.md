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
    --icon logo_despensa.ico ^
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

- **`--exclude-module`** de pandas, matplotlib, tkinter y ttkbootstrap — sólo
  los usaba la ventana vieja. Quitarlos baja el ejecutable de unos 43 MB a
  unos 18 MB.

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

`ventas.py` y `lddl/ui/` siguen en el repositorio, pero **ya no se compilan**.
Se quedan porque de ellos cuelgan las pruebas de caracterización, que son las
que demuestran que las cuentas del cobro, del carrito y de las deudas no
cambiaron al mudarse a React. Si algún día se borran, se borran esas pruebas
con ellos, y se pierde esa red.

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
