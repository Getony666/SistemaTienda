# Compilar el ejecutable

```
python -m PyInstaller --noconfirm --onefile --windowed ^
    --name MiTienda ^
    --icon logo_despensa.ico ^
    --collect-data ttkbootstrap ^
    --exclude-module fastapi --exclude-module uvicorn --exclude-module httpx ^
    ventas.py
```

El resultado queda en `dist\MiTienda.exe`. Cópialo a la carpeta donde estén
`tienda.db` y `config_caja.json`: el programa los busca **junto al ejecutable**
(ver `obtener_ruta_base()` en `lddl/rutas.py`).

## Por qué cada opción

- **`--collect-data ttkbootstrap`** — imprescindible. ttkbootstrap 2.x lleva
  fuentes e iconos en `ttkbootstrap/assets/`, y PyInstaller no los detecta
  solo. Sin esto el ejecutable compila bien pero **revienta al arrancar**, con
  una ventana que sólo dice "Unhandled exception in script":

      FileNotFoundError: ...\ttkbootstrap\assets\icons\bootstrap.ttf

- **`--windowed`** — sin consola detrás. El precio es que los errores de
  arranque no se ven: para diagnosticarlos, compila igual pero con
  `--console` y otro `--name`, y lee la traza.

- **`--exclude-module fastapi/uvicorn/httpx`** — la API no va dentro del
  ejecutable de la tienda. La caja funciona sin conexión y sin servidor.

- **`--onefile`** — un solo fichero, más cómodo de repartir. Arranca algo más
  lento porque se descomprime en una carpeta temporal en cada ejecución.

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

Y arranca el ejecutable una vez: que abra la ventana es la única forma de
saber que no le falta ningún recurso empaquetado.
