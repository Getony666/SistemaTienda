"""API HTTP sobre el núcleo de la aplicación.

Expone por HTTP lo que hasta ahora sólo sabía la ventana de tkinter, usando
exactamente las mismas funciones: ni una cuenta se repite aquí.

Sirve para dos cosas:

- El panel del dueño en el navegador, que sólo consulta.
- Cualquier interfaz futura -React en el escritorio, móvil- que quiera pedir
  el cálculo del vuelto sin reimplementarlo.

**Todos los endpoints de datos son de sólo lectura.** Vender, cobrar deudas y
mover inventario se siguen haciendo desde la caja, que es la que manda y la
que funciona sin conexión. Los de /cobro no tocan la base: son aritmética.

Para levantarla:

    python -m uvicorn lddl.api:app --reload

y la documentación interactiva queda en http://127.0.0.1:8000/docs
"""

import datetime
import re

from fastapi import FastAPI, HTTPException, Path, Query
from pydantic import BaseModel, Field

from . import calculo_cobro as cc
from .caja import cargar_fondo_por_fecha, obtener_resumen_caja, obtener_saldo_divisas
from .productos import buscar_productos
from .ventas_datos import obtener_ventas

FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")

app = FastAPI(
    title="La Despensa de Leslia",
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
