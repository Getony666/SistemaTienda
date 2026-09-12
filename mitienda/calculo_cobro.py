"""Cálculo del pago y del vuelto, sin interfaz.

Aquí vive la aritmética que antes estaba repartida por `mitienda/ui/cobro.py`:
cuánto se ha pagado, si cubre la venta, cuánto se devuelve y cómo se reparte
ese dinero entre efectivo y transferencia a la hora de guardar la venta.

Ninguna función de este módulo sabe que existe una pantalla: recibe números y
devuelve números. Eso permite probarlas sin abrir la aplicación, y reutilizar
exactamente el mismo cálculo desde cualquier interfaz.

Vocabulario, que en el código original se mezclaba:

- En CUP, `efectivo` y `transferencia` son las dos formas de pagar.
- En divisa, `efectivo` es la cantidad en la moneda extranjera, y el CUP que
  se añade encima va en `cup_efectivo` y `cup_transferencia`.
- `vuelto_en_moneda` es la parte del cambio que la cajera decide devolver en
  la moneda extranjera; el resto se devuelve en CUP.
"""

from dataclasses import dataclass

CUP = "CUP"


def a_numero(texto, por_defecto=0.0):
    """Convierte a float lo tecleado, sin reventar con vacíos ni basura."""
    if texto is None:
        return por_defecto
    if isinstance(texto, (int, float)):
        return float(texto)
    texto = texto.strip()
    if not texto:
        return por_defecto
    try:
        return float(texto)
    except ValueError:
        return por_defecto


@dataclass
class Pago:
    """Lo que la cajera ha tecleado en la sección de Pago."""

    total_cup: float
    moneda: str = CUP
    tasa: float = 1.0
    efectivo: float = 0.0
    transferencia: float = 0.0
    cup_efectivo: float = 0.0
    cup_transferencia: float = 0.0
    vuelto_en_moneda: float = 0.0
    solo_transferencia: bool = False

    @property
    def en_divisa(self):
        return self.moneda != CUP and not self.solo_transferencia


@dataclass
class Vuelto:
    """Resultado del cálculo. `error` no es None cuando el pago no es válido."""

    total_pagado_cup: float = 0.0
    cubre: bool = False
    falta_cup: float = 0.0
    vuelto_cup: float = 0.0
    vuelto_moneda: float = 0.0
    vuelto_cup_restante: float = 0.0
    error: str = None


@dataclass
class Desglose:
    """Cómo se reparte el dinero cobrado, para guardarlo en la base."""

    metodo_pago: str = "Efectivo"
    metodo_pago_real: str = "Efectivo"
    moneda_pago: str = CUP
    tasa_cambio: float = 1.0
    total_pagado: float = 0.0
    monto_efectivo_cup: float = 0.0
    monto_transferencia_cup: float = 0.0
    salida_efectivo_extra: float = 0.0
    pago_divisa: float = 0.0
    vuelto_moneda: float = 0.0
    pago_texto: str = ""
    vuelto_texto: str = "0.00 CUP"
    saldo_pendiente: float = 0.0
    pagada: int = 1
    error: str = None


# ----------------------------------------------------------------- cantidades

def pagado_en_cup(pago):
    """Todo lo entregado por la clienta, convertido a CUP."""
    if pago.solo_transferencia:
        return pago.total_cup
    if pago.moneda == CUP:
        return pago.efectivo + pago.transferencia
    divisa_en_cup = pago.efectivo * pago.tasa if pago.efectivo > 0 else 0.0
    return divisa_en_cup + pago.cup_efectivo + pago.cup_transferencia


def cup_faltante(total_cup, pago_divisa, tasa):
    """Cuánto CUP hay que añadir para completar la venta. Nunca negativo."""
    if pago_divisa <= 0 or tasa <= 0:
        return 0.0
    falta = total_cup - (pago_divisa * tasa)
    return falta if falta > 0 else 0.0


def maximo_vuelto_en_moneda(vuelto_cup, tasa):
    """Tope de cambio que se puede devolver en la moneda extranjera."""
    if tasa <= 0:
        return 0.0
    return vuelto_cup / tasa


# -------------------------------------------------------------------- vuelto

def calcular_vuelto(pago):
    """Cuánto hay que devolver, y en qué monedas.

    Devuelve siempre un `Vuelto`. Cuando el pago no alcanza, `cubre` es False
    y `falta_cup` dice cuánto queda por cobrar. Cuando la cajera pide devolver
    más divisa de la que corresponde, `error` explica el motivo y el resto de
    campos quedan a cero.
    """
    if pago.solo_transferencia:
        return Vuelto(total_pagado_cup=pago.total_cup, cubre=True)

    if pago.moneda != CUP and pago.tasa <= 0:
        return Vuelto(error="tasa_invalida")

    if pago.cup_efectivo < 0:
        return Vuelto(error="cup_efectivo_negativo")
    if pago.cup_transferencia < 0:
        return Vuelto(error="cup_transferencia_negativo")
    if pago.vuelto_en_moneda < 0:
        return Vuelto(error="vuelto_moneda_negativo")

    total_pagado = pagado_en_cup(pago)

    if total_pagado < pago.total_cup:
        return Vuelto(
            total_pagado_cup=total_pagado,
            cubre=False,
            falta_cup=pago.total_cup - total_pagado,
        )

    vuelto_cup = total_pagado - pago.total_cup

    # En CUP no hay nada que repartir: todo el cambio va en CUP.
    if pago.moneda == CUP or vuelto_cup <= 0 or pago.vuelto_en_moneda <= 0:
        return Vuelto(
            total_pagado_cup=total_pagado,
            cubre=True,
            vuelto_cup=vuelto_cup,
            vuelto_cup_restante=vuelto_cup,
        )

    vuelto_moneda_cup = pago.vuelto_en_moneda * pago.tasa
    if vuelto_moneda_cup > vuelto_cup:
        return Vuelto(
            total_pagado_cup=total_pagado,
            cubre=True,
            vuelto_cup=vuelto_cup,
            error="vuelto_moneda_excede",
        )

    return Vuelto(
        total_pagado_cup=total_pagado,
        cubre=True,
        vuelto_cup=vuelto_cup,
        vuelto_moneda=pago.vuelto_en_moneda,
        vuelto_cup_restante=vuelto_cup - vuelto_moneda_cup,
    )


# --------------------------------------------------------------------- textos

def texto_resumen_pago(pago):
    """La línea que resume con qué se pagó, tal como la muestra la app."""
    if pago.moneda == CUP:
        efectivo, transferencia = pago.efectivo, pago.transferencia
        if efectivo > 0 and transferencia > 0:
            return f"Efectivo: {efectivo:.2f} | Transferencia: {transferencia:.2f}"
        if transferencia > 0:
            return f"Transferencia: {transferencia:.2f}"
        if efectivo > 0:
            return f"Efectivo: {efectivo:.2f}"
        return ""

    partes = []
    if pago.efectivo > 0:
        partes.append(f"{pago.efectivo:.2f} {pago.moneda} (={pago.efectivo * pago.tasa:.2f} CUP)")
    if pago.cup_efectivo > 0:
        partes.append(f"{pago.cup_efectivo:.2f} CUP (efectivo)")
    if pago.cup_transferencia > 0:
        partes.append(f"{pago.cup_transferencia:.2f} CUP (transferencia)")
    return " + ".join(partes)


def texto_pago_para_registro(pago):
    """La descripción del pago que se guarda con la venta."""
    if pago.solo_transferencia:
        return f"Transferencia: {pago.total_cup:.2f} CUP"

    if pago.moneda == CUP:
        efectivo, transferencia = pago.efectivo, pago.transferencia
        if efectivo > 0 and transferencia > 0:
            return f"Efectivo: {efectivo:.2f} CUP + Transferencia: {transferencia:.2f} CUP"
        if transferencia > 0:
            return f"Transferencia: {transferencia:.2f} CUP"
        return f"Efectivo: {efectivo:.2f} CUP"

    partes = []
    if pago.efectivo > 0:
        partes.append(f"{pago.efectivo:.2f} {pago.moneda}")
    if pago.cup_efectivo > 0:
        partes.append(f"{pago.cup_efectivo:.2f} CUP (efectivo)")
    if pago.cup_transferencia > 0:
        partes.append(f"{pago.cup_transferencia:.2f} CUP (transferencia)")
    return " + ".join(partes) if partes else "0.00 CUP"


def texto_vuelto(vuelto, moneda):
    """El vuelto en palabras, tal como se guarda con la venta."""
    if vuelto.vuelto_cup <= 0:
        return "0.00 CUP"
    if vuelto.vuelto_moneda > 0 and vuelto.vuelto_cup_restante > 0:
        return f"{vuelto.vuelto_moneda:.2f} {moneda} + {vuelto.vuelto_cup_restante:.2f} CUP"
    if vuelto.vuelto_moneda > 0:
        return f"{vuelto.vuelto_moneda:.2f} {moneda}"
    return f"{vuelto.vuelto_cup:.2f} CUP"


# ------------------------------------------------------------------ desglose

def desglosar_para_registro(pago, es_deuda=False):
    """Reparte lo cobrado entre efectivo y transferencia para guardarlo.

    El vuelto se descuenta de lo que entró: primero del efectivo, y si no
    alcanza, de la transferencia. Lo que aún falte sale de la caja, y eso es
    `salida_efectivo_extra`.
    """
    if es_deuda:
        return Desglose(
            metodo_pago="Efectivo",
            metodo_pago_real="",
            moneda_pago=CUP,
            tasa_cambio=1.0,
            pago_texto="Deuda registrada",
            vuelto_texto="0.00 CUP",
            saldo_pendiente=pago.total_cup,
            pagada=0,
        )

    if pago.solo_transferencia:
        return Desglose(
            metodo_pago="Transferencia",
            metodo_pago_real="Transferencia",
            moneda_pago=CUP,
            tasa_cambio=1.0,
            total_pagado=pago.total_cup,
            monto_transferencia_cup=pago.total_cup,
            pago_texto=f"Transferencia: {pago.total_cup:.2f} CUP",
            vuelto_texto="0.00 CUP",
        )

    vuelto = calcular_vuelto(pago)
    if vuelto.error:
        return Desglose(error=vuelto.error)

    if pago.moneda == CUP:
        efectivo, transferencia = pago.efectivo, pago.transferencia
        if efectivo > 0 and transferencia > 0:
            metodo_real = "Mixto"
        elif transferencia > 0:
            metodo_real = "Transferencia"
        else:
            metodo_real = "Efectivo"

        vuelto_cup = vuelto.vuelto_cup
        if vuelto_cup > 0:
            monto_efectivo = efectivo - vuelto_cup
            if monto_efectivo < 0:
                monto_transferencia = transferencia - (vuelto_cup - efectivo)
                monto_efectivo = 0.0
            else:
                monto_transferencia = transferencia
        else:
            monto_efectivo, monto_transferencia = efectivo, transferencia

        return Desglose(
            metodo_pago="Efectivo",
            metodo_pago_real=metodo_real,
            moneda_pago=CUP,
            tasa_cambio=1.0,
            total_pagado=vuelto.total_pagado_cup,
            monto_efectivo_cup=monto_efectivo,
            monto_transferencia_cup=monto_transferencia,
            pago_texto=texto_pago_para_registro(pago),
            vuelto_texto=f"{vuelto_cup:.2f} CUP" if vuelto_cup > 0 else "0.00 CUP",
        )

    # ---- pago en divisa ----
    moneda_pago, tasa = pago.moneda, pago.tasa
    if pago.efectivo > 0 and (pago.cup_efectivo > 0 or pago.cup_transferencia > 0):
        metodo_real = "Mixto"
    elif pago.efectivo > 0:
        metodo_real = "Efectivo"
    else:
        # Sin divisa de por medio, la venta es en CUP aunque el desplegable
        # dijera otra cosa.
        metodo_real = "Efectivo"
        moneda_pago, tasa = CUP, 1.0

    monto_efectivo = pago.cup_efectivo
    monto_transferencia = pago.cup_transferencia
    salida_extra = 0.0
    restante = vuelto.vuelto_cup_restante

    if restante > 0:
        pago_cup_total = pago.cup_efectivo + pago.cup_transferencia
        if pago_cup_total >= restante:
            if monto_efectivo >= restante:
                monto_efectivo -= restante
            else:
                resto = restante - monto_efectivo
                monto_efectivo = 0.0
                monto_transferencia -= resto
                if monto_transferencia < 0:
                    monto_transferencia = 0.0
        else:
            salida_extra = restante - pago_cup_total
            monto_efectivo = 0.0
            monto_transferencia = 0.0

    return Desglose(
        metodo_pago="Efectivo",
        metodo_pago_real=metodo_real,
        moneda_pago=moneda_pago,
        tasa_cambio=tasa,
        total_pagado=vuelto.total_pagado_cup,
        monto_efectivo_cup=monto_efectivo,
        monto_transferencia_cup=monto_transferencia,
        salida_efectivo_extra=salida_extra,
        pago_divisa=pago.efectivo,
        vuelto_moneda=vuelto.vuelto_moneda,
        pago_texto=texto_pago_para_registro(pago),
        vuelto_texto=texto_vuelto(vuelto, pago.moneda),
    )


# ------------------------------------------------------------------- precios

def redondear_subtotal_peso(cantidad, precio):
    """Los productos por peso se cobran redondeando al múltiplo de 5 CUP.

    Regla de la tienda, no de la interfaz: vivía dentro del diálogo de
    cantidad del panel de Ventas.
    """
    return round((cantidad * precio) / 5) * 5
