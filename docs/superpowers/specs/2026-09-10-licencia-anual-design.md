# Sistema de licencias para MiTienda

Fecha: 2026-09-10
Estado: aprobado para plan de implementación

## El problema

MiTienda se vende como plantilla a negocios pequeños. Hoy, una vez entregada la
carpeta (`MiTienda.exe`, `tienda.db`, `config_caja.json`), el cliente tiene el
programa para siempre y no hay nada que le recuerde renovar ni que lo detenga si
decide no pagar. Tampoco hay nada que le impida pasarle la carpeta a otro
negocio.

Hace falta una licencia con fecha de caducidad —un año por defecto— que el
programa compruebe al arrancar y que sólo el vendedor pueda emitir.

## Decisiones tomadas

| Decisión | Elección | Consecuencia |
|---|---|---|
| Alcance de la licencia | **Una licencia = una computadora** | El `.lic` lleva un solo código de máquina. Un negocio con dos cajas necesita dos licencias. |
| Al vencer | **Bloquear escritura, permitir lectura** | No puede vender ni tocar inventario; sí consultar historial, deudas y exportar. |
| Entrega de la clave | **Archivo `licencia.lic`** | Se manda por WhatsApp o USB y se copia junto al `.exe`. |
| Conectividad | **Todo offline** | Sin servidor, sin llamadas a internet, sin coste recurrente. |
| Licencia de técnico | **Sí** | Edición corta (3 días) para dar soporte a un cliente vencido. |
| Cortesía al instalar | **Sí, 7 días** | Permite dejar instalado y mandar el `.lic` después, y hacer demostraciones. |

## Modelo de amenaza

Conviene ser explícito sobre qué para este sistema y qué no.

**Lo que sí para:**

- El cliente que deja de pagar y sigue vendiendo como si nada.
- El cliente que le pasa la carpeta completa a otro negocio.
- El que atrasa el reloj de Windows para estirar la licencia.
- El que borra `tienda.db` para que el programa "empiece de cero".

**Lo que no para:**

MiTienda es Python empaquetado con PyInstaller en modo `--onefile`. El paquete
se descomprime y el bytecode se descompila con herramientas públicas. Alguien
con conocimientos puede localizar la comprobación y parchearla. Ningún esquema
de licencias evita eso en un programa que se ejecuta en la máquina del cliente.

El objetivo no es ser infranqueable, sino que el cliente honesto tenga un motivo
claro y visible para renovar, y que copiar el programa a otra tienda deje de ser
trivial.

**Lo que no se hace, y por qué:**

- **Nada de ofuscación ni de trucos anti-depuración.** Complican la compilación,
  provocan falsos positivos de antivirus y no detienen a quien de verdad sabe.
- **Nada de bloquear el acceso a los datos del cliente.** Sus ventas, su
  inventario y sus deudas son suyos. Secuestrarlos es lo que empuja a un cliente
  molesto a buscarse una copia parcheada en lugar de pagar.
- **Nada sale de la PC del cliente.** No hay telemetría ni envío de datos.

## Arquitectura

### Piezas nuevas

| Módulo | Responsabilidad | ¿Va en el `.exe`? |
|---|---|---|
| `mitienda/ed25519.py` | Verificar firmas Ed25519. Python puro (RFC 8032). Sólo `verificar()`, no firma. | Sí |
| `mitienda/licencia.py` | **Módulo puro.** Analiza y valida el texto de una licencia. Sin disco, sin red, sin reloj propio. | Sí |
| `mitienda/maquina.py` | Calcula el código de máquina de esta computadora. | Sí |
| `mitienda/almacen_licencia.py` | Lee `licencia.lic`, lee y escribe la marca anti-reloj. | Sí |
| `mitienda/estado_licencia.py` | Guarda el veredicto del arranque, como `sesion.py` guarda el usuario. | Sí |
| `herramientas/generar_licencia.py` | Emite licencias con la llave privada. | **No.** Excluido del `.spec`. |

El diseño respeta el patrón que ya sigue el proyecto: la aritmética y las reglas
viven en módulos puros con pruebas propias (`calculo_cobro`, `calculo_deuda`,
`carrito`), y la interfaz sólo pinta. `licencia.py` recibe la fecha como
parámetro y nunca llama a `datetime.now()`; eso es lo que permite probar el
vencimiento sin tocar el reloj del sistema.

### Las llaves

Se genera **una sola vez** un par Ed25519:

- **Privada** (32 bytes) → `C:\Users\Mirielys\Documents\Py\!Salva\llaves\mitienda_privada.key`.
  Fuera del repositorio. **Si se pierde, no se le puede renovar a ningún cliente
  nunca más.** Requiere un segundo respaldo en soporte físico distinto.
- **Pública** (32 bytes) → constante en `mitienda/licencia.py`. Que la vean los
  clientes es irrelevante: con ella se comprueba una firma, no se crea.

Se usa Ed25519 y no RSA porque la firma ocupa 64 bytes en lugar de 256, y la
verificación en Python puro cabe en unas 80 líneas sin dependencias externas.
Verificar tarda del orden de 15 ms, una sola vez por arranque.

**Esto es deliberado: cero dependencias nuevas y cero aumento del tamaño del
`.exe`.** El `.exe` se queda en sus 21 MB actuales. La herramienta que firma sí
puede usar `cryptography`, porque corre en la máquina del vendedor y no se
compila.

### Formato del archivo de licencia

`licencia.lic`, texto plano UTF-8:

```
MiTienda-Licencia-v2
producto: MiTienda
negocio: Bodega La Esquina
maquina: A7K2-3M4P-XR7T
desde: 2026-09-15
hasta: 2027-09-15
edicion: completa
firma: MFRGGZDF MZTWQ2LK NNWG23TP OBYGC4TU ...
```

- `edicion` es `completa` o `tecnico`.
- `firma` son 64 bytes en base32 (104 caracteres), partidos en grupos de 8 para
  que se lea. Los espacios se ignoran al verificar.
- `producto` es el nombre del programa al que pertenece la licencia
  (`NOMBRE_APP`). Se compara sin distinguir mayúsculas, porque se teclea a
  mano al emitir. **Es lo único que separa las licencias de dos productos
  distintos** cuando ambos se firman con la misma llave: sin este campo, una
  licencia barata de un producto abriría el otro sin quejarse. Se añadió el
  mismo día, antes de vender la primera copia, que es el único momento en que
  cambiar el formato no le cuesta nada a nadie.
- Es legible a propósito: el cliente puede abrirlo y entender qué compró.

**Canonicalización.** La firma no se calcula sobre el texto crudo del archivo,
sino sobre una cadena reconstruida a partir de los campos ya analizados, en
orden fijo y unidos por `\n`:

```
producto: MiTienda
negocio: Bodega La Esquina
maquina: A7K2-3M4P-XR7T
desde: 2026-09-15
hasta: 2027-09-15
edicion: completa
```

codificada en UTF-8. Así el archivo sobrevive a que Windows le cambie los
saltos de línea a CRLF, a espacios de más al final, o a que alguien lo abra y lo
guarde con el Bloc de notas.

**Acentos.** Los nombres de negocio llevan tildes y eñes. El archivo se lee y se
escribe siempre con `encoding="utf-8"` explícito, y la cadena canónica se
codifica en UTF-8 antes de firmar y de verificar. Es una trampa conocida de este
proyecto y hay que dejarla cerrada desde el primer día. Las pruebas incluyen un
nombre con tilde y otro con eñe.

### Código de máquina

`mitienda/maquina.py` combina dos datos estables de Windows:

1. `MachineGuid`, del registro:
   `HKLM\SOFTWARE\Microsoft\Cryptography`, valor `MachineGuid`.
   Se abre con `winreg.KEY_READ | winreg.KEY_WOW64_64KEY` para que un Python de
   32 bits no acabe leyendo `WOW6432Node`.
2. Número de serie del volumen del **disco del sistema**
   (`os.environ["SystemDrive"]`), vía
   `ctypes.windll.kernel32.GetVolumeInformationW`.
   Se usa el disco del sistema, y no aquel donde esté la carpeta, para que mover
   la carpeta de sitio no invalide la licencia.

```
huella  = sha256(b"MiTienda-v1|" + machine_guid + b"|" + serie_volumen)
codigo  = base32(huella)[:12]  ->  "A7K23M4PXR7T"  ->  "A7K2-3M4P-XR7T"
```

Base32 estándar (RFC 4648) usa el alfabeto `A-Z2-7`, que ya excluye `0`, `1`,
`8` y `9`; no hay confusión posible entre O/0 ni entre I/1 al dictarlo por
teléfono. Doce caracteres son 60 bits, de sobra.

**Consecuencia que hay que asumir:** si al cliente le reinstalan Windows, el
`MachineGuid` cambia y hace falta emitirle un `.lic` nuevo. Es correcto que sea
así —es otra instalación— pero va a pasar y conviene tenerlo previsto.

**Si el registro no se puede leer** (permisos, Windows atípico), la huella se
calcula sólo con el número de serie del volumen y se registra el hecho en el
propio código, con un prefijo distinto. Nunca se lanza una excepción que impida
arrancar: un fallo al calcular la huella deja el programa en estado
*sin licencia*, con su pantalla, no en un error sin salida.

### Verificación en el arranque

En `mitienda/api.py`, dentro del `lifespan` que ya existe (`arrancar`), justo
después de `verificar_y_crear_columnas()`:

1. Calcular la huella de esta computadora.
2. Leer `licencia.lic` desde `rutas.obtener_ruta_licencia()`.
3. `licencia.verificar(texto, LLAVE_PUBLICA, huella, hoy)`.
4. Comprobar el reloj contra la marca de agua.
5. Guardar el veredicto en `estado_licencia`.

`rutas.py` gana una función nueva, gemela de `obtener_ruta_config()`:

```python
def obtener_ruta_licencia():
    return os.path.join(obtener_ruta_base(), "licencia.lic")
```

Esto hace que las pruebas y los ensayos hereden el comportamiento gratis: ya
usan `fijar_directorio_base()` para trabajar sobre una copia.

### Los estados posibles

| Estado | Cuándo | Qué hace la aplicación |
|---|---|---|
| `activa` | Firma válida, dentro de fecha, máquina correcta | Todo normal |
| `por_vencer` | Faltan 30 días o menos | Banda fija arriba con los días restantes |
| `urgente` | Faltan 7 días o menos | Además, modal al abrir con el código de máquina y botón de copiar |
| `cortesia` | Sin licencia, dentro de los 7 días del primer arranque | Todo normal, con banda que dice cuántos días de cortesía quedan |
| `vencida` | Pasó `hasta` | Escritura bloqueada, lectura permitida |
| `sin_licencia` | No hay archivo, firma inválida, máquina distinta, o se acabó la cortesía | Sólo la pantalla de licencia |
| `reloj_atrasado` | El reloj va por detrás de la marca de agua | Sólo la pantalla de licencia, con el mensaje de corregir la fecha del sistema |

En `vencida` y en `sin_licencia` el motivo concreto se muestra al usuario en
lenguaje llano: *"esta licencia es de otra computadora"* dice mucho más que
*"licencia no válida"*, y ahorra una llamada de soporte.

### El bloqueo, en concreto

Aquí el proyecto ya tiene la mitad del trabajo hecho: los permisos se comprueban
en la API, no en la pantalla (`sesion.exigir(permiso)` levantando `SinPermiso`).
El bloqueo por licencia entra por el mismo camino.

- Se añade `estado_licencia.exigir_escritura()`, que levanta `LicenciaVencida`.
- Todos los endpoints que **escriben** —cobrar, alta y baja de producto, entrada
  y salida de efectivo, merma, salida de inventario, cobro de deuda, cierre de
  caja, alta de usuarios— la llaman.
- Los endpoints que **leen** no la llaman: historial, deudas, almacén, corte de
  caja en modo consulta, exportaciones.
- La dependencia `guardian_de_licencia()` traduce `LicenciaVencida` a
  `402 Payment Required` con el motivo ya redactado en castellano. Va en la
  dependencia y no en un manejador global de FastAPI para que sea la misma
  pieza que `exige(...)`, y para que la prueba guardiana pueda comprobar ruta
  por ruta que está puesta.
- **402 y no 403.** 403 es «tú no puedes», cosa del usuario que entró; esto es
  del programa entero, y la diferencia importa cuando la cajera llama.

**Lo que la interfaz NO hace, a propósito.** Con la licencia vencida los
botones de vender siguen encendidos: al pulsarlos, la API contesta 402 y el
mensaje sale en el mismo sitio donde ya salen los errores de cobro. Apagarlos
uno por uno obligaría a pasar la licencia por los cinco paneles, y no compra
seguridad ninguna -la barrera está en la API-. Si algún día molesta, se hace
entonces.

Dos ventajas de hacerlo aquí y no en la interfaz: no hay que revisar botón por
botón, y no se puede saltar el candado desde el navegador, porque la puerta no
está en la pantalla.

`GET /salud` y el endpoint nuevo `GET /licencia` quedan siempre abiertos: son
los que la pantalla de licencia necesita para funcionar.

### Marca anti-reloj

El programa recuerda la fecha más alta que ha visto, y la compara al arrancar.
La marca vive en **tres sitios**, y se toma el máximo de los tres:

1. Tabla nueva `marcas_licencia (clave TEXT PRIMARY KEY, valor TEXT)` en
   `tienda.db`. Se crea en `esquema.py`, junto a las demás.
2. Registro de Windows, `HKCU\Software\MiTienda`, valor `um`. Sobrevive a que
   borren `tienda.db`. Va en `HKCU` para no necesitar permisos de
   administrador.
3. `MAX(fecha)` de la tabla `historial`, que ya registra cada operación con
   formato `"%Y-%m-%d %H:%M:%S"` en hora local.

Si el reloj del sistema va por detrás del máximo de las tres, menos un margen de
**48 horas** (por husos horarios, cambios de hora y relojes de placa base con la
pila gastada), el estado pasa a `reloj_atrasado`.

Al cerrar bien la aplicación, y también cada vez que se registra una operación,
la marca se actualiza en 1 y 2.

El campo `desde` de la licencia sirve de suelo adicional: una licencia emitida
el 2026-09-15 no puede considerarse válida si el reloj dice que es 2025.

### El periodo de cortesía

Cuando el programa arranca por primera vez y no encuentra `licencia.lic`, anota
la fecha de ese primer arranque en la marca (clave `primer_arranque`), en la
base y en el registro. Durante 7 días funciona con normalidad, con una banda
visible que dice cuántos quedan. Al octavo, pasa a `sin_licencia`.

Un cliente podría borrar la base y el registro para conseguir otros siete días,
pero al hacerlo perdería todas sus ventas, su inventario y sus deudas. El coste
para él es mucho mayor que el beneficio, así que es un agujero aceptable.

### La licencia de técnico

`edicion: tecnico` es una licencia igual a las demás —atada a la misma máquina,
firmada igual— pero de 3 días por defecto y con una banda de color distinto que
dice **"Licencia de técnico"**, para que nadie la confunda con una renovación de
verdad. Sirve para abrirle la aplicación a un cliente vencido mientras se le
resuelve algo.

No es una llave maestra: sigue atada a la máquina concreta. Emitirla requiere el
código de máquina del cliente y la llave privada.

**Riesgo importante:** eso implica no llevar nunca la llave privada a casa de un
cliente. La llave se queda en una sola computadora; el `.lic` de técnico se
genera desde allí y se manda por WhatsApp. Llevar la llave en una USB por ahí es
el mayor riesgo de todo el sistema, porque quien la consiga puede emitir
licencias infinitas y no hay forma de revocarla sin recompilar y reinstalar a
todos los clientes.

## El generador

`herramientas/generar_licencia.py`, que **nunca** se compila en el `.exe`:

```
python herramientas/generar_licencia.py "Bodega La Esquina" A7K2-3M4P-XR7T --meses 12
python herramientas/generar_licencia.py "Bodega La Esquina" A7K2-3M4P-XR7T --dias 3 --tecnico
```

- Lee la llave privada de `!Salva\llaves\mitienda_privada.key`.
- Valida el formato del código de máquina antes de firmar, para no emitir una
  licencia inútil por una errata al copiar.
- Escribe `licencia.lic` en la carpeta actual e imprime un resumen legible
  (negocio, máquina, hasta cuándo) para confirmar antes de mandarlo.

Junto a él, `herramientas/generar_llaves.py`, que se ejecuta una sola vez y se
niega a sobrescribir una llave ya existente.

## Interfaz

Pantalla nueva `interfaz/src/PanelLicencia.jsx`, y una banda de aviso en
`App.jsx`. La pantalla muestra:

- El código de máquina, grande, con botón de copiar.
- El estado en lenguaje llano y el motivo si algo falla.
- Zona para arrastrar el `licencia.lic`, con alternativa de "buscar archivo".
- Cuando hay licencia activa: negocio, edición y fecha de vencimiento.

El nombre del negocio pasa también al título de la ventana, junto a `NOMBRE_APP`
de `mitienda/__init__.py`. Es un detalle que personaliza el producto y que además
recuerda a diario de quién es la licencia.

**Antes de escribir una línea de esta interfaz hay que mandarle al usuario un
mockup de cómo va a quedar.** Es una condición suya, sin excepciones.

## Pruebas

`pruebas/test_licencia.py` y `pruebas/test_maquina.py`, en `unittest` como el
resto:

- Los vectores oficiales del RFC 8032 → confirma que el Ed25519 propio es
  correcto. Esto es innegociable: una implementación de curva escrita a mano y
  no verificada contra vectores conocidos no sirve.
- Licencia válida dentro de fecha → `activa`.
- Un solo byte alterado en cualquier campo → rechazada.
- Firma de otra llave → rechazada.
- Código de máquina distinto → rechazada, con ese motivo concreto.
- Un día después de `hasta` → `vencida`.
- 30 y 7 días antes → `por_vencer` y `urgente`.
- Nombre de negocio con tilde y con eñe → firma y verifica bien.
- Archivo con saltos de línea CRLF y espacios al final → verifica bien.
- Reloj por detrás de la marca → `reloj_atrasado`; dentro del margen de 48 h →
  no salta.
- Cortesía: día 1 funciona, día 8 no.
- Por la API: endpoint de escritura con licencia vencida → 402; endpoint de
  lectura → 200.

Las 229 pruebas actuales no deben romperse. Como usan `fijar_directorio_base()`
sobre una copia temporal, `pruebas/base.py` gana la emisión de una licencia de
pruebas —con un par de llaves de pruebas, no el real— dentro de esa carpeta.
Son unas pocas líneas y evita tener que tocar cada archivo de pruebas.

## Empaquetado y entrega

- `MiTienda.spec`: PyInstaller sigue los `import`, y nada de `escritorio.py`
  importa `herramientas/`, así que no se empaqueta por sí solo. Aun así se
  añade a `excludes` para que un import descuidado en el futuro no meta el
  generador dentro del `.exe`. El `.spec` está en `.gitignore` como `*.spec`,
  o sea que no viaja en el repositorio: el cambio se hace en la copia local y
  se deja anotado en `COMPILAR.md`.
- La llave privada **nunca** vive dentro de `MiTienda-Dev\`. Su sitio es `!Salva`, que
  está fuera del repositorio.
- `.gitignore`: añadir `*.key`, `licencia.lic` y `herramientas/llaves/`.
- La carpeta que va a una tienda pasa de **3 archivos a 4**:
  `MiTienda.exe`, `tienda.db`, `config_caja.json`, `licencia.lic`.
- La skill `desplegar-mitienda` (`.claude/skills/`) y `COMPILAR.md` hay que
  actualizarlos con el paso nuevo de emitir la licencia.

**Momento oportuno:** hoy no hay ninguna tienda real funcionando, así que no hay
que migrar a nadie. Todo cliente futuro nace ya con licencia. Si esto se hiciera
después de repartir cinco copias, habría que ir una por una.

## Lo que se descubrió al construirlo

**Los códigos de máquina de este documento estaban mal.** Los ejemplos decían
`A7K2-9M4P-XR31`, y base32 no tiene `0`, `1`, `8` ni `9`. Lo cazó la prueba que
valida el formato en el generador, no una lectura. Corregidos a
`A7K2-3M4P-XR7T`.

**`preparar_base()` no sabe crear la base desde cero.** Empieza por
`PRAGMA table_info(ventas)` y abandona si esa tabla no existe, así que un
cliente que borre `tienda.db` no se queda con una base nueva: se queda sin
programa. Es anterior a este trabajo y no se tocó, pero cambia cuál es el
ataque real contra la marca anti-reloj: nadie borra la base, la sustituye por
la virgen de la entrega. Es eso lo que prueba
`pruebas/test_almacen_licencia.py`.

**Las pruebas necesitaban su propia licencia.** Desde que la API comprueba una
al arrancar, cualquier prueba que la levante se encontraba sin licencia: le
escribía la marca al registro de Windows de verdad, y la suite habría empezado
a fallar sola al acabarse los siete días de cortesía. `pruebas/base.py` reparte
ahora una licencia de pruebas, con llave de mentira y su propia clave de
registro, igual que ya repartía su propia base.

## La rutina de venta y de renovación

**Vender:**

1. Copiar los archivos a la PC del cliente y abrir.
2. La aplicación muestra la pantalla de licencia con el código de máquina.
3. Copiar el código (o fotografiarlo).
4. `python herramientas/generar_licencia.py "Nombre del negocio" CODIGO --meses 12`
5. Poner `licencia.lic` junto al `.exe`. Ya está.

Si no se puede hacer en el momento, la cortesía de 7 días cubre el hueco.

**Renovar:** pasos 3 a 5. El cliente no pierde nada: sus ventas, su inventario y
sus deudas siguen intactos en `tienda.db`, que no se toca.

## Riesgos

| Riesgo | Gravedad | Mitigación |
|---|---|---|
| Se pierde la llave privada | **Crítico.** Ningún cliente puede renovar jamás. | Dos respaldos en soportes distintos, uno fuera de la PC de trabajo. |
| Se filtra la llave privada | **Crítico.** Cualquiera emite licencias y no hay revocación sin recompilar y reinstalar a todos. | No sacarla nunca de una sola computadora. No llevarla a casa de clientes. |
| Ed25519 escrito a mano tiene un fallo | Alto: aceptaría firmas falsas o rechazaría las buenas. | Vectores del RFC 8032 en las pruebas, obligatorios. |
| Reinstalan Windows al cliente | Medio, y va a pasar. | Emitir `.lic` nuevo. Documentarlo en el manual del cliente. |
| Antivirus marca el `.exe` | Bajo, pero existe con PyInstaller. | Otra razón más para no ofuscar nada. |
| Falso positivo de reloj atrasado | Medio: bloquea a un cliente inocente. | Margen de 48 h, y mensaje que explica que hay que corregir la fecha de Windows, no llamar al soporte. |

## Fuera de alcance

- Servidor de activación, renovación automática y apagado remoto. Requieren
  internet estable, que no hay.
- Revocar una licencia ya emitida. Sin conexión no hay forma de avisar al
  programa. Se maneja con licencias más cortas si hace falta.
- Ofuscación del ejecutable.
- Contar usos, ventas o cualquier otra métrica del cliente.
