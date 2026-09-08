"""Cálculo del cobro de una deuda, sin interfaz.

Es hermano de `calculo_cobro.py`, pero el problema es distinto: aquí no se
cobra una venta nueva, sino que se abona sobre un saldo que ya existe. Puede
quedar pagada del todo o sólo en parte.

Como el resto de módulos de este paquete, no sabe que existe una pantalla:
recibe números y devuelve números. La comprobación de si hay efectivo en caja
para dar el vuelto se queda fuera, porque necesita la base de datos; aquí se
dice cuánto vuelto hay que entregar y quien llame decide.
"""

from dataclasses import dataclass

CUP = "CUP"

EFECTIVO = "Efectivo"
TRANSFERENCIA = "Transferencia"
MIXTO = "Mixto"


@dataclass
class Abono:
    """Lo que la cajera ha tecleado en el diálogo de Pagar Deuda."""

    saldo_pendiente: float
    moneda: str = CUP
    tasa: float = 1.0
    metodo: str = EFECTIVO
    efectivo: float = 0.0
    transferencia: float = 0.0
    efectivo_cup: float = 0.0
    vuelto_en_moneda: float = 0.0

    @property
    def en_divisa(self):
        return self.moneda != CUP


@dataclass
class Cobro:
    """Resultado. `error` no es None cuando el abono no es válido."""

    moneda: str = CUP
    tasa: float = 1.0
    metodo: str = EFECTIVO
    metodo_pago_real: str = EFECTIVO
    efectivo: float = 0.0
    transferencia: float = 0.0
    efectivo_cup: float = 0.0
    total_pagado_moneda: float = 0.0
    total_pagado_cup: float = 0.0
    nuevo_saldo: float = 0.0
    pagada: int = 0
    vuelto_cup: float = 0.0
    vuelto_moneda: float = 0.0
    error: str = None


def _validar(abono):
    if abono.en_divisa and abono.tasa <= 0:
        return "tasa_invalida"
    if abono.efectivo < 0 or abono.transferencia < 0 or abono.efectivo_cup < 0:
        return "montos_negativos"
    if abono.en_divisa and abono.metodo != EFECTIVO:
        return "divisa_solo_efectivo"
    if abono.metodo == MIXTO and abono.en_divisa:
        return "mixto_solo_cup"
    if abono.metodo == MIXTO and (abono.efectivo <= 0 or abono.transferencia <= 0):
        return "mixto_necesita_ambos"
    if abono.vuelto_en_moneda < 0:
        return "vuelto_negativo"
    return None


def total_pagado(abono):
    """Lo entregado, en la moneda de pago y convertido a CUP."""
    if abono.en_divisa:
        # El CUP que se añade encima no cuenta como "moneda de pago".
        return abono.efectivo, (abono.efectivo * abono.tasa) + abono.efectivo_cup

    if abono.metodo == MIXTO:
        total = abono.efectivo + abono.transferencia
    elif abono.metodo == EFECTIVO:
        total = abono.efectivo
    else:
        total = abono.transferencia
    return total, total


def calcular_cobro(abono):
    """Cuánto queda por pagar, si la deuda se salda y cuánto vuelto sale.

    Devuelve siempre un `Cobro`. Cuando el abono no cubre el saldo, `pagada`
    es 0 y `nuevo_saldo` dice lo que falta; cuando lo cubre, `vuelto_cup` dice
    lo que hay que devolver.
    """
    error = _validar(abono)
    if error:
        return Cobro(error=error)

    tasa = abono.tasa if abono.en_divisa else 1.0
    en_moneda, en_cup = total_pagado(abono)

    if en_cup < abono.saldo_pendiente:
        cobro = Cobro(
            nuevo_saldo=abono.saldo_pendiente - en_cup,
            pagada=0,
            vuelto_cup=0.0,
            vuelto_moneda=0.0,
        )
    else:
        vuelto_cup = en_cup - abono.saldo_pendiente
        vuelto_moneda = abono.vuelto_en_moneda if abono.en_divisa else 0.0
        if vuelto_moneda * tasa > vuelto_cup:
            return Cobro(error="vuelto_moneda_excede", vuelto_cup=vuelto_cup)
        cobro = Cobro(
            nuevo_saldo=0.0,
            pagada=1,
            vuelto_cup=vuelto_cup,
            vuelto_moneda=vuelto_moneda,
        )

    # El método que se guarda: al mezclar divisa con CUP deja de ser sólo divisa.
    metodo_real = abono.metodo
    if abono.en_divisa and abono.efectivo_cup > 0:
        metodo_real = "Mixto (USD+CUP)"

    cobro.moneda = abono.moneda
    cobro.tasa = tasa
    cobro.metodo = abono.metodo
    cobro.metodo_pago_real = metodo_real
    cobro.efectivo = abono.efectivo
    cobro.transferencia = abono.transferencia
    cobro.efectivo_cup = abono.efectivo_cup
    cobro.total_pagado_moneda = en_moneda
    cobro.total_pagado_cup = en_cup
    return cobro


def vuelto_en_cup_a_entregar(cobro):
    """Parte del vuelto que sale de la caja en CUP.

    Lo que se devuelva en divisa no toca el efectivo en CUP, así que se
    descuenta. Quien llame compara esto con lo que hay en caja.
    """
    if cobro.vuelto_cup <= 0:
        return 0.0
    if cobro.vuelto_moneda > 0:
        return cobro.vuelto_cup - (cobro.vuelto_moneda * cobro.tasa)
    return cobro.vuelto_cup


def observaciones_del_cobro(observaciones_previas, cobro):
    """Añade al historial de la venta la línea que resume este abono."""
    texto = observaciones_previas or ""
    if cobro.pagada == 1:
        return texto + f" | Pagada totalmente (abonado {cobro.total_pagado_cup:.2f} CUP)"
    return (texto + f" | Pago parcial de {cobro.total_pagado_cup:.2f} CUP, "
                    f"saldo restante {cobro.nuevo_saldo:.2f} CUP")


def resumen_del_cobro(cobro):
    """Una línea con lo que ha pasado, para enseñarla al terminar."""
    if cobro.pagada == 1:
        texto = f"Deuda pagada completamente. Vuelto: {cobro.vuelto_cup:.2f} CUP"
        if cobro.vuelto_moneda > 0:
            texto += f" (en {cobro.moneda}: {cobro.vuelto_moneda:.2f})"
        return texto
    return f"Pago parcial registrado. Saldo restante: {cobro.nuevo_saldo:.2f} CUP"
