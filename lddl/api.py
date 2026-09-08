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

import datetime
import re

from fastapi import FastAPI, HTTPException, Path, Query
from pydantic import BaseModel, Field

from . import NOMBRE_APP
from . import calculo_cobro as cc
from .caja import (
    cargar_fondo_por_fecha,
    guardar_fondo_por_fecha,
    obtener_resumen_caja,
    obtener_saldo_divisas,
    registrar_entrada_efectivo,
    registrar_operacion_cambio,
    registrar_salida_efectivo,
)
from .historial import revertir_registro
from .inventario import registrar_merma, registrar_salida
from .productos import actualizar_producto, agregar_producto, buscar_productos, eliminar_producto
from .ventas_datos import (
    obtener_ventas,
    registrar_cobro_deuda_en_db,
    registrar_venta_en_db,
    utilidad_del_carrito,
)

FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")

app = FastAPI(
    title=NOMBRE_APP,
    description="Consulta del punto de venta. La caja sigue siendo la que manda.",
    version="1.0.0",
)


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


# ----------------------------------------------------------------- productos

class Producto(BaseModel):
    id: int
    nombre: str
    precio: float
    stock: float
    tipo: str
    unidad: str


@app.get("/productos", response_model=list[Producto], tags=["inventario"])
def listar_productos(buscar: str = Query("", description="Texto a buscar; vacío devuelve todo")):
    """Productos del inventario, opcionalmente filtrados por nombre."""
    return [
        Producto(id=p[0], nombre=p[1], precio=p[2], stock=p[3], tipo=p[4], unidad=p[5])
        for p in buscar_productos(buscar)
    ]


# -------------------------------------------------------------------- ventas

@app.get("/ventas", tags=["historial"])
def listar_ventas(
    fecha: str = Query(None, description="AAAA-MM-DD; sin ella, todas"),
    metodo: str = Query("todos", description="todos, efectivo, transferencia o mixto"),
    tipo: str = Query("todos", description="todos, ventas, deudas, cambio, merma..."),
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


@app.post("/ventas", tags=["ventas"], status_code=201)
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


@app.post("/deudas/{venta_id}/cobros", tags=["ventas"], status_code=201)
def cobrar_deuda(venta_id: int, datos: dict):
    """Registra el cobro -total o parcial- de una deuda pendiente.

    OJO: a diferencia de /ventas, aquí `datos` llega ya calculado. El cálculo
    del cobro de deudas sigue viviendo dentro de `lddl/ui/dialogo_deuda.py`, y
    hasta que se extraiga como se hizo con el de la venta, quien llame a este
    endpoint tiene que componer esos importes por su cuenta.
    """
    return _resultado(registrar_cobro_deuda_en_db(venta_id, datos))


# ---------------------------------------------------------------- productos

class ProductoEntrante(BaseModel):
    nombre: str
    categoria: str = ""
    precio_compra: float = Field(0.0, ge=0)
    precio_venta: float = Field(0.0, ge=0)
    stock: float = Field(0.0, ge=0)
    proveedor: str = ""
    tipo_producto: str = "unidad"
    unidad_medida: str = "unidad"
    fecha_vencimiento: str = ""


@app.post("/productos", tags=["inventario"], status_code=201)
def crear_producto(producto: ProductoEntrante):
    """Da de alta un producto."""
    return _resultado(agregar_producto(**producto.model_dump()))


@app.put("/productos/{producto_id}", tags=["inventario"])
def editar_producto(producto_id: int, producto: ProductoEntrante):
    """Cambia los datos de un producto. Los cambios quedan en el historial."""
    return _resultado(actualizar_producto(producto_id, **producto.model_dump()))


@app.delete("/productos/{producto_id}", tags=["inventario"])
def borrar_producto(producto_id: int):
    """Elimina un producto. No se puede si ya tiene ventas asociadas."""
    return _resultado(eliminar_producto(producto_id))


# ------------------------------------------------------- salidas y mermas

class SalidaEntrante(BaseModel):
    producto_id: int
    cantidad: float = Field(..., gt=0)
    precio_costo: float = Field(..., ge=0)
    motivo: str = "Salida a trabajador"


@app.post("/inventario/salidas", tags=["inventario"], status_code=201)
def crear_salida(salida: SalidaEntrante):
    """Saca producto del almacén y genera la deuda correspondiente."""
    return _resultado(registrar_salida(**salida.model_dump()))


class MermaEntrante(BaseModel):
    producto_id: int
    cantidad: float = Field(..., gt=0)
    motivo: str = "Merma"


@app.post("/inventario/mermas", tags=["inventario"], status_code=201)
def crear_merma(merma: MermaEntrante):
    """Da de baja producto perdido o dañado."""
    return _resultado(registrar_merma(**merma.model_dump()))


# ------------------------------------------------------------------- caja

class MovimientoEfectivo(BaseModel):
    moneda: str = "CUP"
    monto: float = Field(..., gt=0)
    descripcion: str = ""


@app.post("/caja/entradas", tags=["caja"], status_code=201)
def crear_entrada_efectivo(movimiento: MovimientoEfectivo):
    """Mete efectivo en la caja."""
    return _resultado(registrar_entrada_efectivo(**movimiento.model_dump()))


@app.post("/caja/salidas", tags=["caja"], status_code=201)
def crear_salida_efectivo(movimiento: MovimientoEfectivo):
    """Saca efectivo de la caja. Falla si no hay suficiente."""
    return _resultado(registrar_salida_efectivo(**movimiento.model_dump()))


class FondoEntrante(BaseModel):
    fondo: float = Field(..., ge=0)


@app.put("/caja/fondo/{fecha}", tags=["caja"])
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


@app.post("/cambio", tags=["caja"], status_code=201)
def crear_operacion_cambio(operacion: CambioEntrante):
    """Registra una compra o venta de divisa."""
    return _resultado(registrar_operacion_cambio(**operacion.model_dump()))


# -------------------------------------------------------------- historial

@app.delete("/historial/{registro_id}", tags=["historial"])
def revertir_del_historial(
    registro_id: int,
    tipo: str = Query(..., description="Tipo del registro, tal como lo devuelve /ventas"),
):
    """Deshace un registro del historial y todos sus efectos.

    No borra sin más: devuelve el stock, ajusta la caja y deshace las deudas
    que hubiera generado.
    """
    return _resultado(revertir_registro(registro_id, tipo))
