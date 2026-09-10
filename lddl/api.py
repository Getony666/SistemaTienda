"""API HTTP sobre el núcleo de la aplicación.

Expone por HTTP lo que hasta ahora sólo sabía la ventana de tkinter, usando
exactamente las mismas funciones: ni una cuenta se repite aquí.

Sirve para dos cosas:

- El panel del dueño en el navegador, que sólo consulta.
- Cualquier interfaz futura -React en el escritorio, móvil- que quiera pedir
  el cálculo del vuelto sin reimplementarlo.

⚠️ **Esta API escribe en la base: no puede salir a internet tal cual.**

Está pensada para correr en `127.0.0.1`, dentro de la máquina de la tienda,
donde el único cliente es la propia caja. Cuando llegue el momento de publicar
el panel del dueño habrá que separar dos modos -uno que lee y escribe para la
caja, otro de sólo lectura para el navegador- y desplegar fuera sólo el
segundo. Mientras tanto, no la expongas a la red.

Los endpoints de /cobro no tocan la base: son aritmética.

Para levantarla:

    python -m uvicorn lddl.api:app --reload

y la documentación interactiva queda en http://127.0.0.1:8000/docs
"""

import contextlib
import datetime
import re

from fastapi import Depends, FastAPI, HTTPException, Path, Query
from pydantic import BaseModel, Field

from . import NOMBRE_APP
from . import calculo_cobro as cc
from . import calculo_deuda as cd
from . import estado_licencia, sesion, usuarios
from .esquema import preparar_base
from .caja import (
    cargar_fondo_por_fecha,
    guardar_fondo_por_fecha,
    obtener_efectivo_disponible_cup,
    obtener_resumen_caja,
    obtener_saldo_divisas,
    registrar_entrada_efectivo,
    registrar_operacion_cambio,
    registrar_salida_efectivo,
)
from .rutas import consulta
from .historial import revertir_registro
from .inventario import (
    registrar_merma,
    registrar_merma_de_carrito,
    registrar_salida,
    registrar_salida_de_carrito,
)
from .almacen import obtener_almacen
from .productos import actualizar_producto, agregar_producto, buscar_productos, eliminar_producto
from .ventas_datos import (
    obtener_ventas,
    registrar_cobro_deuda_en_db,
    registrar_venta_en_db,
    utilidad_del_carrito,
)

FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@contextlib.asynccontextmanager
async def arrancar(_app):
    """Se ejecuta al levantar el servidor, no al importar el módulo.

    Importar no puede tocar la base: las pruebas importan `app` antes de
    apuntar a su copia, y crear tablas ahí escribiría en la de verdad.
    """
    preparar_base()
    # Después de preparar la base, porque la marca contra el reloj atrasado
    # vive en una tabla que puede que todavía no exista.
    estado_licencia.comprobar()
    yield


app = FastAPI(
    title=NOMBRE_APP,
    description="Consulta del punto de venta. La caja sigue siendo la que manda.",
    version="1.0.0",
    lifespan=arrancar,
)


# =========================================================================
#  PERMISOS
#
#  Esconder un botón en la interfaz es una comodidad, no una barrera: quien
#  sepa la dirección puede llamar a la ruta directamente. Lo que impide de
#  verdad es esto: la ruta contesta 403 y no toca la base.
# =========================================================================

def exige(permiso):
    """Dependencia que corta la ruta si el usuario de ahora no puede."""
    def guardian():
        try:
            sesion.exigir(permiso)
        except sesion.SinPermiso as sin_permiso:
            codigo = 401 if not sesion.hay_sesion() else 403
            raise HTTPException(status_code=codigo, detail=str(sin_permiso))
    return Depends(guardian)


# =========================================================================
#  LICENCIA
#
#  El mismo razonamiento que los permisos, una vuelta más arriba: el candado
#  va aquí y no en la pantalla, porque quien sepa la dirección puede llamar a
#  la ruta desde la consola del navegador.
#
#  Vencida la licencia se bloquea LO QUE ESCRIBE: cobrar, tocar inventario,
#  mover dinero. Lo que lee sigue funcionando -historial, deudas, almacén,
#  exportaciones- porque los datos del negocio son del negocio. Quitarle a un
#  cliente el acceso a sus propias cuentas es lo que le empuja a buscarse una
#  copia parcheada en vez de pagar.
#
#  402 y no 403: 403 es "tú no puedes", y esto no es cosa del usuario que
#  entró, sino del programa entero.
# =========================================================================

def guardian_de_licencia():
    """La comprobación en sí. Suelta para que las pruebas la reconozcan."""
    try:
        estado_licencia.exigir_escritura()
    except estado_licencia.LicenciaVencida as vencida:
        raise HTTPException(status_code=402, detail=str(vencida))


def exige_licencia():
    """Dependencia que corta la ruta si no se puede escribir hoy."""
    return Depends(guardian_de_licencia)


def _validar_fecha(fecha):
    if not FECHA.match(fecha):
        raise HTTPException(status_code=422, detail="La fecha debe ser AAAA-MM-DD")
    try:
        datetime.date.fromisoformat(fecha)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{fecha} no es una fecha real")
    return fecha


# --------------------------------------------------------------------- salud

@app.get("/salud", tags=["estado"])
def salud():
    """Comprueba que la API responde y que la base contesta."""
    try:
        buscar_productos("")
        base = "ok"
    except Exception as e:
        base = f"error: {e}"
    return {"estado": "ok", "base_de_datos": base,
            "momento": datetime.datetime.now().isoformat(timespec="seconds")}


# ------------------------------------------------------------------ licencia

class LicenciaEntrante(BaseModel):
    texto: str = Field(..., description="Contenido completo del licencia.lic")


@app.get("/licencia", tags=["estado"])
def ver_licencia():
    """Cómo está la licencia y el código de esta computadora.

    Sin guardián de ninguna clase, y a propósito: es lo que pinta la pantalla
    de licencia. Si se bloqueara a sí misma, un cliente con la licencia
    vencida no tendría ni de dónde copiar su código de máquina para pedir la
    renovación.
    """
    return estado_licencia.para_la_pantalla()


@app.post("/licencia", tags=["estado"])
def poner_licencia(entrante: LicenciaEntrante):
    """Guarda una licencia nueva: la que el cliente pega o suelta en la ventana.

    Se comprueba antes de escribir. Si se guardara primero, una licencia de
    otra computadora pisaría la buena que hubiera y dejaría al cliente sin
    poder vender justo por intentar renovar.
    """
    bien, veredicto = estado_licencia.activar(entrante.texto)
    if not bien:
        raise HTTPException(status_code=400,
                            detail=estado_licencia.explicar(veredicto))
    return estado_licencia.para_la_pantalla()


# ----------------------------------------------------------------- productos

class Producto(BaseModel):
    id: int
    nombre: str
    precio: float = Field(..., description="Precio de venta")
    costo: float = Field(..., description="Precio de compra; con él se valoran las salidas")
    stock: float
    tipo: str
    unidad: str


@app.get("/productos", response_model=list[Producto], tags=["inventario"])
def listar_productos(buscar: str = Query("", description="Texto a buscar; vacío devuelve todo")):
    """Productos del inventario, opcionalmente filtrados por nombre."""
    return [
        Producto(id=p[0], nombre=p[1], precio=p[2], stock=p[3], tipo=p[4],
                 unidad=p[5], costo=p[6])
        for p in buscar_productos(buscar)
    ]


@app.get("/almacen", tags=["inventario"], dependencies=[exige("ver_almacen")])
def ver_almacen(
    buscar: str = Query("", description="Subcadena del nombre; vacío no filtra"),
    proveedor: str = Query("", description="Proveedor exacto; vacío no filtra"),
    categoria: str = Query("", description="Categoría exacta; vacía no filtra"),
    orden: str = Query("nombre", description="'nombre' o 'vendidos'"),
    dias: int = Query(30, description="Período de 'vendidos': 30, 90 o 0 (todo)"),
):
    """Catálogo completo con costo, margen y unidades vendidas por producto.

    Es de sólo lectura pero lleva su propio permiso -a diferencia de
    /productos, que usa la caja para buscar- porque enseña el precio de
    compra y el valor del inventario: eso no es para cualquiera."""
    return obtener_almacen(buscar=buscar, proveedor=proveedor, categoria=categoria,
                           orden=orden, dias=dias)


# -------------------------------------------------------------------- ventas

@app.get("/ventas", tags=["historial"])
def listar_ventas(
    fecha: str = Query(None, description="AAAA-MM-DD; sin ella, todas"),
    metodo: str = Query("todos", description="todos, efectivo, transferencia o mixto"),
    tipo: str = Query("todos", description="todos, ventas, deudas, mensajeria, cambio, merma..."),
    producto_id: int = Query(None, description="Sólo los registros de este producto"),
):
    """Historial de ventas y movimientos, con los mismos filtros que la app."""
    if fecha is not None:
        _validar_fecha(fecha)
    return obtener_ventas(filtro_fecha=fecha, filtro_metodo=metodo,
                          filtro_tipo=tipo, producto_id=producto_id)


# ---------------------------------------------------------------- corte
@app.get("/corte/{fecha}", tags=["caja"])
def corte_de_caja(fecha: str = Path(..., description="AAAA-MM-DD")):
    """Resumen del día: lo mismo que muestra la pestaña de Corte de Caja."""
    _validar_fecha(fecha)
    resumen = obtener_resumen_caja(fecha)
    resumen["fecha"] = fecha
    resumen["fondo_registrado"] = cargar_fondo_por_fecha(fecha)
    resumen["saldo_divisas"] = obtener_saldo_divisas(fecha)
    return resumen


# --------------------------------------------------------------------- cobro

class PagoEntrante(BaseModel):
    """Lo que la cajera ha tecleado. No toca la base de datos."""

    total_cup: float = Field(..., ge=0, description="Total de la venta en CUP")
    moneda: str = Field("CUP", description="CUP, USD o EUR")
    tasa: float = Field(1.0, description="CUP por unidad de la moneda de pago")
    efectivo: float = Field(0.0, description="En CUP, o en la divisa si moneda != CUP")
    transferencia: float = Field(0.0, description="Sólo cuando se paga en CUP")
    cup_efectivo: float = Field(0.0, description="CUP añadido al pago en divisa")
    cup_transferencia: float = Field(0.0, description="CUP por transferencia sobre la divisa")
    vuelto_en_moneda: float = Field(0.0, description="Parte del cambio a devolver en divisa")
    solo_transferencia: bool = Field(False, description="La venta se cobra entera por transferencia")

    def a_pago(self):
        return cc.Pago(**self.model_dump())


class VueltoSaliente(BaseModel):
    cubre: bool
    total_pagado_cup: float
    falta_cup: float
    vuelto_cup: float
    vuelto_moneda: float
    vuelto_cup_restante: float
    texto: str
    resumen_pago: str
    error: str | None = None


@app.post("/cobro/vuelto", response_model=VueltoSaliente, tags=["cobro"])
def calcular_vuelto(pago_entrante: PagoEntrante):
    """Cuánto hay que devolver. Misma función que usa la caja."""
    pago = pago_entrante.a_pago()
    v = cc.calcular_vuelto(pago)
    return VueltoSaliente(
        cubre=v.cubre,
        total_pagado_cup=v.total_pagado_cup,
        falta_cup=v.falta_cup,
        vuelto_cup=v.vuelto_cup,
        vuelto_moneda=v.vuelto_moneda,
        vuelto_cup_restante=v.vuelto_cup_restante,
        texto=cc.texto_vuelto(v, pago.moneda),
        resumen_pago=cc.texto_resumen_pago(pago),
        error=v.error,
    )


@app.post("/cobro/desglose", tags=["cobro"])
def calcular_desglose(pago_entrante: PagoEntrante, es_deuda: bool = Query(False)):
    """Cómo se repartiría el dinero al guardar la venta. No guarda nada."""
    desglose = cc.desglosar_para_registro(pago_entrante.a_pago(), es_deuda=es_deuda)
    if desglose.error:
        raise HTTPException(status_code=422, detail=desglose.error)
    return desglose.__dict__


@app.get("/cobro/faltante", tags=["cobro"])
def cup_que_falta(
    total_cup: float = Query(..., ge=0),
    pago_divisa: float = Query(..., ge=0),
    tasa: float = Query(..., gt=0),
):
    """CUP que hay que añadir para completar un pago en divisa."""
    return {"falta_cup": cc.cup_faltante(total_cup, pago_divisa, tasa)}


# =========================================================================
#  ESCRITURAS
#
#  A partir de aquí todo toca la base de datos. Este bloque es el que hace
#  que la API no pueda salir a internet tal cual: ver la nota de arriba.
# =========================================================================

def _resultado(par):
    """Traduce el (exito, mensaje) del núcleo a una respuesta HTTP."""
    exito, mensaje = par
    if not exito:
        raise HTTPException(status_code=422, detail=mensaje)
    return {"ok": True, "mensaje": mensaje}


class LineaCarrito(BaseModel):
    id: int
    nombre: str
    cantidad: float = Field(..., gt=0)
    precio: float = Field(..., ge=0)
    tipo: str = "unidad"
    unidad: str = "unidad"


class VentaEntrante(BaseModel):
    """Una venta tal como la teclea la cajera.

    El reparto entre efectivo y transferencia no se pide: lo calcula la propia
    API con `calculo_cobro`, el mismo módulo que usa la ventana. Así ninguna
    interfaz tiene que reimplementar esas reglas.
    """

    carrito: list[LineaCarrito] = Field(..., min_length=1)
    pago: PagoEntrante
    es_deuda: bool = False
    es_mensajeria: bool = False
    observaciones: str = ""


@app.post("/ventas", tags=["ventas"], status_code=201, dependencies=[exige("vender"), exige_licencia()])
def registrar_venta(venta: VentaEntrante):
    """Cierra una venta y la guarda con todos sus efectos en caja e inventario."""
    carrito = [linea.model_dump() for linea in venta.carrito]
    pago = venta.pago.a_pago()

    desglose = cc.desglosar_para_registro(pago, es_deuda=venta.es_deuda)
    if desglose.error:
        raise HTTPException(status_code=422, detail=desglose.error)

    if not venta.es_deuda and desglose.total_pagado < pago.total_cup:
        raise HTTPException(
            status_code=422,
            detail=f"El total pagado ({desglose.total_pagado:.2f}) es menor que "
                   f"el total de la venta ({pago.total_cup:.2f})")

    exito, resultado = registrar_venta_en_db(carrito, {
        "total_cup": pago.total_cup,
        "metodo_pago": desglose.metodo_pago,
        "moneda_pago": desglose.moneda_pago,
        "tasa_cambio": desglose.tasa_cambio,
        "es_mensajeria": int(venta.es_mensajeria),
        "es_deuda": int(venta.es_deuda),
        "pagada": desglose.pagada,
        "fecha_pago": (None if venta.es_deuda
                       else datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        "saldo_pendiente": desglose.saldo_pendiente,
        "metodo_pago_real": desglose.metodo_pago_real,
        "observaciones": venta.observaciones,
        "pago_texto": desglose.pago_texto,
        "vuelto_texto": desglose.vuelto_texto,
        "monto_efectivo_cup": desglose.monto_efectivo_cup,
        "monto_transferencia_cup": desglose.monto_transferencia_cup,
        "utilidad_total": utilidad_del_carrito(carrito),
        "pago_divisa": desglose.pago_divisa,
        "vuelto_moneda": desglose.vuelto_moneda,
        "salida_efectivo_extra": desglose.salida_efectivo_extra,
    })
    if not exito:
        raise HTTPException(status_code=422, detail=str(resultado))
    return {"ok": True, "venta_id": resultado, "vuelto_texto": desglose.vuelto_texto}


class AbonoEntrante(BaseModel):
    """Lo que la cajera teclea para abonar una deuda."""

    moneda: str = Field("CUP", description="CUP, USD o EUR")
    tasa: float = Field(1.0, description="CUP por unidad de la moneda de pago")
    metodo: str = Field("Efectivo", description="Efectivo, Transferencia o Mixto")
    efectivo: float = Field(0.0, ge=0, description="En CUP, o en la divisa si moneda != CUP")
    transferencia: float = Field(0.0, ge=0, description="Sólo cuando se paga en CUP")
    efectivo_cup: float = Field(0.0, ge=0, description="CUP añadido al pago en divisa")
    vuelto_en_moneda: float = Field(0.0, ge=0, description="Parte del cambio a devolver en divisa")


def _deuda_pendiente(venta_id):
    """Saldo y observaciones de una deuda, o un error si no se puede cobrar."""
    with consulta() as (_conexion, cursor):
        cursor.execute(
            "SELECT es_deuda, pagada, saldo_pendiente, observaciones "
            "FROM ventas WHERE id = ?", (venta_id,))
        fila = cursor.fetchone()

    if not fila:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    es_deuda, pagada, saldo, observaciones = fila
    if es_deuda != 1:
        raise HTTPException(status_code=422, detail="Esa venta no es una deuda")
    if pagada == 1:
        raise HTTPException(status_code=422, detail="Esa deuda ya está pagada")
    return saldo, observaciones


def _cobro_de(venta_id, abono_entrante):
    saldo, observaciones = _deuda_pendiente(venta_id)
    abono = cd.Abono(saldo_pendiente=saldo, **abono_entrante.model_dump())
    cobro = cd.calcular_cobro(abono)
    if cobro.error:
        raise HTTPException(status_code=422, detail=cobro.error)
    return saldo, observaciones, cobro


@app.post("/deudas/{venta_id}/simular", tags=["ventas"])
def simular_cobro_deuda(venta_id: int, abono: AbonoEntrante):
    """Qué pasaría con ese abono. No guarda nada.

    Sirve para que la interfaz enseñe el vuelto y el saldo restante mientras
    la cajera teclea, sin reimplementar el cálculo.
    """
    saldo, _observaciones, cobro = _cobro_de(venta_id, abono)
    return {
        "saldo_pendiente": saldo,
        "total_pagado_cup": cobro.total_pagado_cup,
        "nuevo_saldo": cobro.nuevo_saldo,
        "pagada": cobro.pagada,
        "vuelto_cup": cobro.vuelto_cup,
        "vuelto_moneda": cobro.vuelto_moneda,
        "vuelto_en_cup_a_entregar": cd.vuelto_en_cup_a_entregar(cobro),
        "metodo_pago_real": cobro.metodo_pago_real,
        "resumen": cd.resumen_del_cobro(cobro),
    }


@app.post("/deudas/{venta_id}/cobros", tags=["ventas"], status_code=201, dependencies=[exige("cobrar_deudas"), exige_licencia()])
def cobrar_deuda(venta_id: int, abono: AbonoEntrante):
    """Registra el cobro, total o parcial, de una deuda pendiente.

    El desglose lo calcula la API con `calculo_deuda`, el mismo módulo que usa
    el diálogo de tkinter: quien llame no tiene que componer los importes.
    """
    _saldo, observaciones, cobro = _cobro_de(venta_id, abono)

    # Lo único que no decide el cálculo: si la caja tiene ese dinero.
    falta = cd.vuelto_en_cup_a_entregar(cobro)
    if falta > 0:
        disponible = obtener_efectivo_disponible_cup(
            datetime.datetime.now().strftime("%Y-%m-%d"))
        if falta > disponible:
            raise HTTPException(
                status_code=422,
                detail=f"No hay suficiente efectivo en caja para el vuelto. "
                       f"Requerido: {falta:.2f} CUP, disponible: {disponible:.2f} CUP")

    exito, mensaje = registrar_cobro_deuda_en_db(venta_id, {
        "moneda": cobro.moneda,
        "tasa": cobro.tasa,
        "metodo": cobro.metodo,
        "efectivo": cobro.efectivo,
        "transferencia": cobro.transferencia,
        "efectivo_cup": cobro.efectivo_cup,
        "vuelto_cup": cobro.vuelto_cup,
        "vuelto_moneda": cobro.vuelto_moneda,
        "total_pagado_moneda": cobro.total_pagado_moneda,
        "total_pagado_cup": cobro.total_pagado_cup,
        "nuevo_saldo": cobro.nuevo_saldo,
        "pagada": cobro.pagada,
        "fecha_pago": (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                       if cobro.pagada == 1 else None),
        "metodo_pago_real": cobro.metodo_pago_real,
        "observaciones": cd.observaciones_del_cobro(observaciones, cobro).strip(),
    })
    if not exito:
        raise HTTPException(status_code=422, detail=mensaje)
    return {"ok": True, "mensaje": cd.resumen_del_cobro(cobro),
            "pagada": cobro.pagada, "nuevo_saldo": cobro.nuevo_saldo,
            "vuelto_cup": cobro.vuelto_cup}


# ---------------------------------------------------------------- productos

class ProductoEntrante(BaseModel):
    """Lo que manda la pantalla para dar de alta o editar un producto.

    Salvo el nombre, todos los campos son opcionales y por defecto llegan en
    None. Al crear, None se rellena con un valor neutro (ver `agregar_producto`).
    Al actualizar, None significa "no cambiar" y conserva lo que ya había en
    la base (ver `actualizar_producto`) -así una pantalla que no conoce cierto
    campo no lo pisa con vacío sólo por no mandarlo.
    """

    nombre: str
    categoria: str | None = None
    precio_compra: float | None = Field(None, ge=0)
    precio_venta: float | None = Field(None, ge=0)
    stock: float | None = Field(None, ge=0)
    proveedor: str | None = None
    tipo_producto: str | None = None
    unidad_medida: str | None = None
    fecha_vencimiento: str | None = None


@app.post("/productos", tags=["inventario"], status_code=201, dependencies=[exige("crear_producto"), exige_licencia()])
def crear_producto(producto: ProductoEntrante):
    """Da de alta un producto."""
    return _resultado(agregar_producto(**producto.model_dump()))


@app.put("/productos/{producto_id}", tags=["inventario"], dependencies=[exige("actualizar_producto"), exige_licencia()])
def editar_producto(producto_id: int, producto: ProductoEntrante):
    """Cambia los datos de un producto. Los cambios quedan en el historial."""
    return _resultado(actualizar_producto(producto_id, **producto.model_dump()))


@app.delete("/productos/{producto_id}", tags=["inventario"], dependencies=[exige("eliminar_producto"), exige_licencia()])
def borrar_producto(producto_id: int):
    """Elimina un producto. No se puede si ya tiene ventas asociadas."""
    return _resultado(eliminar_producto(producto_id))


# ------------------------------------------------------- salidas y mermas

class SalidaEntrante(BaseModel):
    producto_id: int
    cantidad: float = Field(..., gt=0)
    precio_costo: float = Field(..., ge=0)
    motivo: str = "Salida a trabajador"


@app.post("/inventario/salidas", tags=["inventario"], status_code=201, dependencies=[exige("salida_inventario"), exige_licencia()])
def crear_salida(salida: SalidaEntrante):
    """Saca producto del almacén y genera la deuda correspondiente."""
    return _resultado(registrar_salida(**salida.model_dump()))


class MermaEntrante(BaseModel):
    producto_id: int
    cantidad: float = Field(..., gt=0)
    motivo: str = "Merma"


@app.post("/inventario/mermas", tags=["inventario"], status_code=201, dependencies=[exige("merma"), exige_licencia()])
def crear_merma(merma: MermaEntrante):
    """Da de baja producto perdido o dañado."""
    return _resultado(registrar_merma(**merma.model_dump()))


class LineaDeCarrito(BaseModel):
    producto_id: int
    cantidad: float = Field(..., gt=0)


class CarritoDeInventario(BaseModel):
    """Varios productos que salen del almacén de una vez.

    El precio de costo no viaja: lo pone el almacén al registrarlo, para que
    nadie pueda valorar una salida por debajo de lo que costó.
    """

    lineas: list[LineaDeCarrito] = Field(..., min_length=1)
    motivo: str = ""


@app.post("/inventario/salidas/carrito", tags=["inventario"], status_code=201, dependencies=[exige("salida_inventario"), exige_licencia()])
def crear_salida_de_carrito(carrito: CarritoDeInventario):
    """Saca un carrito entero del almacén, a precio de costo.

    Genera una sola deuda por el total, no una por producto. O entran todas
    las líneas o no entra ninguna.
    """
    lineas = [linea.model_dump() for linea in carrito.lineas]
    return _resultado(registrar_salida_de_carrito(
        lineas, carrito.motivo or "Salida a trabajador"))


@app.post("/inventario/mermas/carrito", tags=["inventario"], status_code=201, dependencies=[exige("merma"), exige_licencia()])
def crear_merma_de_carrito(carrito: CarritoDeInventario):
    """Da de baja un carrito entero sin cobrar nada.

    Cada línea queda como su propia merma, para que se vean y se reviertan por
    separado, pero se guardan todas juntas o ninguna.
    """
    lineas = [linea.model_dump() for linea in carrito.lineas]
    return _resultado(registrar_merma_de_carrito(lineas, carrito.motivo or "Merma"))


# ------------------------------------------------------------------- caja

class MovimientoEfectivo(BaseModel):
    moneda: str = "CUP"
    monto: float = Field(..., gt=0)
    descripcion: str = ""


@app.post("/caja/entradas", tags=["caja"], status_code=201, dependencies=[exige("entrada_efectivo"), exige_licencia()])
def crear_entrada_efectivo(movimiento: MovimientoEfectivo):
    """Mete efectivo en la caja."""
    return _resultado(registrar_entrada_efectivo(**movimiento.model_dump()))


@app.post("/caja/salidas", tags=["caja"], status_code=201, dependencies=[exige("salida_efectivo"), exige_licencia()])
def crear_salida_efectivo(movimiento: MovimientoEfectivo):
    """Saca efectivo de la caja. Falla si no hay suficiente."""
    return _resultado(registrar_salida_efectivo(**movimiento.model_dump()))


class FondoEntrante(BaseModel):
    fondo: float = Field(..., ge=0)


@app.put("/caja/fondo/{fecha}", tags=["caja"], dependencies=[exige("fondo_caja"), exige_licencia()])
def fijar_fondo(fecha: str, cuerpo: FondoEntrante):
    """Fija el fondo de caja de un día. Sustituye, no suma."""
    _validar_fecha(fecha)
    if not guardar_fondo_por_fecha(fecha, cuerpo.fondo):
        raise HTTPException(status_code=422, detail="No se pudo guardar el fondo")
    return {"ok": True, "fecha": fecha, "fondo": cuerpo.fondo}


class CambioEntrante(BaseModel):
    tipo: str = Field(..., description="compra o venta")
    moneda: str = Field(..., description="USD o EUR")
    cantidad: float = Field(..., gt=0)
    tasa: float = Field(..., gt=0)
    observaciones: str = ""


@app.post("/cambio", tags=["caja"], status_code=201, dependencies=[exige("cambio_divisa"), exige_licencia()])
def crear_operacion_cambio(operacion: CambioEntrante):
    """Registra una compra o venta de divisa."""
    return _resultado(registrar_operacion_cambio(**operacion.model_dump()))


# -------------------------------------------------------------- historial

@app.delete("/historial/{registro_id}", tags=["historial"], dependencies=[exige("eliminar_historial"), exige_licencia()])
def revertir_del_historial(
    registro_id: int,
    tipo: str = Query(..., description="Tipo del registro, tal como lo devuelve /ventas"),
):
    """Deshace un registro del historial y todos sus efectos.

    No borra sin más: devuelve el stock, ajusta la caja y deshace las deudas
    que hubiera generado.
    """
    return _resultado(revertir_registro(registro_id, tipo))


# =========================================================================
#  SESIÓN, USUARIOS Y PERMISOS
# =========================================================================

class Credenciales(BaseModel):
    nombre: str
    pin: str


class UsuarioEntrante(BaseModel):
    nombre: str
    rol: str
    pin: str


class RolEntrante(BaseModel):
    rol: str


class PinEntrante(BaseModel):
    pin: str


class PermisoEntrante(BaseModel):
    rol: str
    permiso: str
    concedido: bool


def _quien_soy():
    """Lo que la interfaz necesita para saber qué enseñar y qué esconder."""
    return {
        "sesion": sesion.sesion_actual(),
        "permisos": sorted(sesion.permisos_actuales()),
        "hay_usuarios": usuarios.hay_usuarios(),
        "roles": list(usuarios.ROLES),
        "catalogo_permisos": [{"clave": c, "texto": t} for c, t in usuarios.PERMISOS],
        "permiso_fijo": usuarios.PERMISO_FIJO,
    }


@app.get("/sesion", tags=["sesion"])
def quien_soy():
    """Quién está dentro y qué puede hacer. Sin nadie dentro, sesion va nula."""
    return _quien_soy()


@app.post("/sesion", tags=["sesion"])
def abrir_sesion(credenciales: Credenciales):
    """Entrar. El error no distingue usuario de PIN, y eso es a propósito:
    decir cuál de los dos ha fallado es regalar media contraseña."""
    exito, mensaje = sesion.entrar(credenciales.nombre, credenciales.pin)
    if not exito:
        raise HTTPException(status_code=401, detail=mensaje)
    return {"ok": True, "mensaje": mensaje, **_quien_soy()}


@app.delete("/sesion", tags=["sesion"])
def cerrar_sesion():
    """Salir, para que entre otra persona sin cerrar el programa."""
    sesion.salir()
    return {"ok": True, **_quien_soy()}


@app.post("/sesion/primer-admin", tags=["sesion"], status_code=201)
def crear_primer_admin(nuevo: Credenciales):
    """Crea el Admin de una tienda estrenada, y sólo entonces.

    No se reparte un PIN de fábrica con el programa: cada negocio pone el
    suyo la primera vez que abre. Si ya hay usuarios, esta ruta se cierra.
    """
    if usuarios.hay_usuarios():
        raise HTTPException(status_code=409,
                            detail="Ya hay usuarios: entra con el tuyo")
    exito, mensaje = usuarios.crear_usuario(nuevo.nombre, usuarios.ADMIN, nuevo.pin)
    if not exito:
        raise HTTPException(status_code=422, detail=mensaje)
    sesion.entrar(nuevo.nombre, nuevo.pin)
    return {"ok": True, "mensaje": mensaje, **_quien_soy()}


@app.get("/usuarios", tags=["usuarios"], dependencies=[exige("gestionar_usuarios")])
def listar_los_usuarios(incluir_inactivos: bool = Query(False)):
    return usuarios.listar_usuarios(incluir_inactivos=incluir_inactivos)


@app.post("/usuarios", tags=["usuarios"], status_code=201,
          dependencies=[exige("gestionar_usuarios"), exige_licencia()])
def crear_el_usuario(nuevo: UsuarioEntrante):
    return _resultado(usuarios.crear_usuario(nuevo.nombre, nuevo.rol, nuevo.pin))


@app.put("/usuarios/{usuario_id}/rol", tags=["usuarios"],
         dependencies=[exige("gestionar_usuarios"), exige_licencia()])
def cambiar_el_rol(usuario_id: int, cambio: RolEntrante):
    return _resultado(usuarios.cambiar_rol(usuario_id, cambio.rol))


@app.put("/usuarios/{usuario_id}/pin", tags=["usuarios"],
         dependencies=[exige("gestionar_usuarios"), exige_licencia()])
def restablecer_el_pin(usuario_id: int, nuevo: PinEntrante):
    """El Admin le pone PIN nuevo a cualquiera, sin necesitar el viejo."""
    return _resultado(usuarios.restablecer_pin(usuario_id, nuevo.pin))


@app.delete("/usuarios/{usuario_id}", tags=["usuarios"],
            dependencies=[exige("gestionar_usuarios"), exige_licencia()])
def desactivar_el_usuario(usuario_id: int):
    """Lo apaga, no lo borra: lo que hizo tiene que seguir teniendo nombre."""
    return _resultado(usuarios.desactivar_usuario(usuario_id))


@app.get("/permisos", tags=["usuarios"], dependencies=[exige("gestionar_usuarios")])
def ver_permisos():
    return {
        "roles": list(usuarios.ROLES),
        "catalogo": [{"clave": c, "texto": t} for c, t in usuarios.PERMISOS],
        "concedidos": usuarios.mapa_de_permisos(),
        "permiso_fijo": usuarios.PERMISO_FIJO,
    }


@app.put("/permisos", tags=["usuarios"], dependencies=[exige("gestionar_usuarios"), exige_licencia()])
def cambiar_permiso(cambio: PermisoEntrante):
    return _resultado(
        usuarios.fijar_permiso(cambio.rol, cambio.permiso, cambio.concedido))
