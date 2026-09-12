"""Las tablas de casos que caracterizan el cobro, el carrito y el registro
de venta: los números y textos que la ventana vieja de tkinter (`ventas.py`,
`mitienda/ui/`) daba antes de que esas cuentas se sacaran a `mitienda/calculo_cobro.py`
y `mitienda/carrito.py`. No se inventaron a mano: se tomaron ejecutando esa
ventana, y la constancia de que coinciden con ella vive en
`pruebas/acta_de_la_app_vieja.json`.

Viven aquí, sueltas de cualquier módulo de prueba, porque más de un fichero
las necesita: hoy las usan `test_equivalencia_con_la_app.py` y
`test_registro_de_venta.py`, y las mismas van a hacer falta para probar la
API cuando le llegue el turno, sin tener que volver a escribirlas.

    python -m unittest discover -s pruebas -v
"""

from mitienda.calculo_cobro import Pago, a_numero, cup_faltante

# ---------------------------------------------------------------------
# Vuelto y cobro (antes en test_equivalencia_con_la_app.py)
# ---------------------------------------------------------------------

# (descripcion, total, moneda, tasa, pagado, transferencia, cup_ef, cup_tr, vuelto_moneda)
CASOS = [
    ("CUP justo",                 2250, "CUP", "1.00", "2250", "",     "",     "",     ""),
    ("CUP de mas",                2250, "CUP", "1.00", "2300", "",     "",     "",     ""),
    ("CUP no alcanza",            2250, "CUP", "1.00", "2000", "",     "",     "",     ""),
    ("CUP nada",                  2250, "CUP", "1.00", "",     "",     "",     "",     ""),
    ("CUP mixto justo",           1000, "CUP", "1.00", "400",  "600",  "",     "",     ""),
    ("CUP mixto de mas",          1000, "CUP", "1.00", "400",  "700",  "",     "",     ""),
    ("CUP mixto no alcanza",      1000, "CUP", "1.00", "200",  "300",  "",     "",     ""),
    ("CUP solo transferencia",    1000, "CUP", "1.00", "",     "1000", "",     "",     ""),
    ("CUP centavos",             99.99, "CUP", "1.00", "100",  "",     "",     "",     ""),

    ("USD justo",                 4000, "USD", "400.00", "10", "",     "",     "",     ""),
    ("USD de mas",                5000, "USD", "400.00", "15", "",     "",     "",     ""),
    ("USD no alcanza sin CUP",    5000, "USD", "400.00", "10", "",     "",     "",     ""),
    ("USD con CUP efectivo",      5000, "USD", "400.00", "10", "",     "1000", "",     ""),
    ("USD con CUP de mas",        5000, "USD", "400.00", "10", "",     "1500", "",     ""),
    ("USD con CUP transferencia", 5000, "USD", "400.00", "10", "",     "",     "1000", ""),
    ("USD con los dos CUP",       5000, "USD", "400.00", "8",  "",     "1000", "1000", ""),
    ("USD vuelto repartido",      5000, "USD", "400.00", "15", "",     "",     "",     "2"),
    ("USD vuelto todo en divisa", 5000, "USD", "400.00", "15", "",     "",     "",     "2.5"),
    ("USD sin divisa solo CUP",    500, "USD", "400.00", "",   "",     "500",  "",     ""),
    ("EUR de mas",                3000, "EUR", "450.00", "8",  "",     "",     "",     ""),
]

# Vuelto en CUP que la aplicación daba antes de la extracción.
REFERENCIA = {
    "CUP justo": 0.0,
    "CUP de mas": 50.0,
    "CUP no alcanza": 0.0,
    "CUP nada": 0.0,
    "CUP mixto justo": 0.0,
    "CUP mixto de mas": 100.0,
    "CUP mixto no alcanza": 0.0,
    "CUP solo transferencia": 0.0,
    "CUP centavos": 0.01,
    "USD justo": 0.0,
    "USD de mas": 1000.0,
    "USD no alcanza sin CUP": 0.0,
    "USD con CUP efectivo": 0.0,
    "USD con CUP de mas": 500.0,
    "USD con CUP transferencia": 0.0,
    "USD con los dos CUP": 200.0,
    "USD vuelto repartido": 1000.0,
    "USD vuelto todo en divisa": 1000.0,
    "USD sin divisa solo CUP": 0.0,
    "EUR de mas": 600.0,
}


# Lo que la cajera ve en pantalla. Tomado de la app antes de extraer, con una
# corrección deliberada: el monto del vuelto ya no lleva la moneda, porque la
# etiqueta de al lado ya la muestra y se leía "1000.00 CUP CUP".
# (vuelto, resumen del pago, resto en CUP, campo de CUP adicional).
TEXTOS = {
    "CUP justo": ('0.00', 'Efectivo: 2250.00', '', ''),
    "CUP de mas": ('50.00', 'Efectivo: 2300.00', '', ''),
    "CUP no alcanza": ('0.00', 'Faltan 250.00 CUP', '', ''),
    "CUP nada": ('0.00', '', '', ''),
    "CUP mixto justo": ('0.00', 'Efectivo: 400.00 | Transferencia: 600.00', '', ''),
    "CUP mixto de mas": ('100.00', 'Efectivo: 400.00 | Transferencia: 700.00', '', ''),
    "CUP mixto no alcanza": ('0.00', 'Faltan 500.00 CUP', '', ''),
    "CUP solo transferencia": ('0.00', 'Transferencia: 1000.00', '', ''),
    "CUP centavos": ('0.01', 'Efectivo: 100.00', '', ''),
    "USD justo": ('0.00', '10.00 USD (=4000.00 CUP)', '', ''),
    "USD de mas": ('1000.00', '15.00 USD (=6000.00 CUP)', 'Todo el vuelto en CUP', ''),
    "USD no alcanza sin CUP": ('0.00', '10.00 USD (=4000.00 CUP) + 1000.00 CUP (efectivo)', '', '1000.00'),
    "USD con CUP efectivo": ('0.00', '10.00 USD (=4000.00 CUP) + 1000.00 CUP (efectivo)', '', '1000'),
    "USD con CUP de mas": ('500.00', '10.00 USD (=4000.00 CUP) + 1500.00 CUP (efectivo)', 'Todo el vuelto en CUP', '1500'),
    "USD con CUP transferencia": ('0.00', '10.00 USD (=4000.00 CUP) + 1000.00 CUP (transferencia)', '', ''),
    "USD con los dos CUP": ('200.00', '8.00 USD (=3200.00 CUP) + 1000.00 CUP (efectivo) + 1000.00 CUP (transferencia)', 'Todo el vuelto en CUP', '1000'),
    "USD vuelto repartido": ('2.00 USD + 200.00 CUP', '15.00 USD (=6000.00 CUP)', 'Resto en CUP: 200.00', ''),
    "USD vuelto todo en divisa": ('2.50 USD', '15.00 USD (=6000.00 CUP)', 'Todo el vuelto en moneda de pago', ''),
    "USD sin divisa solo CUP": ('0.00', '500.00 CUP (efectivo)', '', '500'),
    "EUR de mas": ('600.00', '8.00 EUR (=3600.00 CUP)', 'Todo el vuelto en CUP', ''),
}


def pago_del_caso(total, moneda, tasa, pagado, transferencia, cup_ef, cup_tr, vuelto_moneda):
    """Traduce un caso de la tabla a un Pago, aplicando el autorrelleno de CUP.

    Cuando se paga en divisa y no alcanza, la interfaz rellena sola el CUP que
    falta y lo da por cobrado. Eso es comodidad de pantalla, no aritmética, así
    que vive fuera del módulo; aquí se reproduce para poder comparar.
    """
    pago = Pago(
        total_cup=float(total),
        moneda=moneda,
        tasa=a_numero(tasa),
        efectivo=a_numero(pagado),
        transferencia=a_numero(transferencia),
        cup_efectivo=a_numero(cup_ef),
        cup_transferencia=a_numero(cup_tr),
        vuelto_en_moneda=a_numero(vuelto_moneda),
    )
    if moneda != "CUP" and pago.efectivo > 0 and not cup_ef and not cup_tr:
        falta = cup_faltante(float(total), pago.efectivo, pago.tasa)
        if falta > 0:
            pago.cup_efectivo = falta
    return pago


# El otro camino de cálculo: teclear en "Pagado (Transferencia)".
# (descripcion, total, pagado, transferencia)
CASOS_MIXTO = [
    ("transferencia parcial",  "1000.00", "",     "400"),
    ("transferencia total",    "1000.00", "",     "1000"),
    ("transferencia de mas",   "1000.00", "",     "1500"),
    ("transferencia negativa", "1000.00", "",     "-5"),
    ("sin transferencia",      "1000.00", "1200", ""),
    ("efectivo insuficiente",  "1000.00", "500",  ""),
]

# (vuelto, resumen, vuelto en CUP, efectivo que la app rellena sola)
MIXTO = {
    "transferencia parcial": ('0.00', 'Efectivo: 600.00 | Transferencia: 400.00', 0.0, '600.00'),
    "transferencia total": ('0.00', 'Transferencia: 1000.00', 0.0, '0.00'),
    "transferencia de mas": ('0.00', '', 0.0, ''),
    "transferencia negativa": ('0.00', '', 0.0, ''),
    "sin transferencia": ('200.00', 'Efectivo: 1200.00', 200.0, '1200'),
    "efectivo insuficiente": ('0.00', 'Efectivo: 500.00', 0.0, '500'),
}


# ---------------------------------------------------------------------
# Desglose para registro de venta (antes en test_registro_de_venta.py)
# ---------------------------------------------------------------------

TOTAL = 1000.0

# (nombre, solo_transferencia, es_deuda, moneda, tasa, pagado, transf_cup, cup_ef, cup_tr, vuelto_moneda)
ESCENARIOS = [
    ("CUP justo",             0, 0, "CUP", "1.00",   "1000", "",     "",    "", ""),
    ("CUP de mas",            0, 0, "CUP", "1.00",   "1200", "",     "",    "", ""),
    ("CUP mixto",             0, 0, "CUP", "1.00",   "200",  "900",  "",    "", ""),
    ("CUP mixto vuelto alto", 0, 0, "CUP", "1.00",   "50",   "1200", "",    "", ""),
    ("Pastilla transferencia",1, 0, "CUP", "1.00",   "",     "",     "",    "", ""),
    ("Deuda",                 0, 1, "CUP", "1.00",   "",     "",     "",    "", ""),
    ("USD justo",             0, 0, "USD", "200.00", "5",    "",     "",    "", ""),
    ("USD de mas",            0, 0, "USD", "400.00", "5",    "",     "",    "", ""),
    ("USD con CUP",           0, 0, "USD", "100.00", "5",    "",     "600", "", ""),
    ("USD vuelto en divisa",  0, 0, "USD", "400.00", "5",    "",     "",    "", "1"),
]

# Valores que la aplicación guardaba antes de la extracción.
FINALIZAR = {
    "CUP justo": {"metodo_pago": "Efectivo", "moneda_pago": "CUP", "tasa_cambio": 1.0,
                  "metodo_pago_real": "Efectivo", "monto_efectivo_cup": 1000.0,
                  "monto_transferencia_cup": 0.0, "salida_efectivo_extra": 0.0,
                  "pago_divisa": 0.0, "vuelto_moneda": 0.0,
                  "pago_texto": "Efectivo: 1000.00 CUP", "vuelto_texto": "0.00 CUP",
                  "saldo_pendiente": 0.0, "pagada": 1},
    "CUP de mas": {"metodo_pago": "Efectivo", "moneda_pago": "CUP", "tasa_cambio": 1.0,
                   "metodo_pago_real": "Efectivo", "monto_efectivo_cup": 1000.0,
                   "monto_transferencia_cup": 0.0, "salida_efectivo_extra": 0.0,
                   "pago_divisa": 0.0, "vuelto_moneda": 0.0,
                   "pago_texto": "Efectivo: 1200.00 CUP", "vuelto_texto": "200.00 CUP",
                   "saldo_pendiente": 0.0, "pagada": 1},
    "CUP mixto": {"metodo_pago": "Efectivo", "moneda_pago": "CUP", "tasa_cambio": 1.0,
                  "metodo_pago_real": "Mixto", "monto_efectivo_cup": 100.0,
                  "monto_transferencia_cup": 900.0, "salida_efectivo_extra": 0.0,
                  "pago_divisa": 0.0, "vuelto_moneda": 0.0,
                  "pago_texto": "Efectivo: 200.00 CUP + Transferencia: 900.00 CUP",
                  "vuelto_texto": "100.00 CUP", "saldo_pendiente": 0.0, "pagada": 1},
    "CUP mixto vuelto alto": {"metodo_pago": "Efectivo", "moneda_pago": "CUP", "tasa_cambio": 1.0,
                              "metodo_pago_real": "Mixto", "monto_efectivo_cup": 0.0,
                              "monto_transferencia_cup": 1000.0, "salida_efectivo_extra": 0.0,
                              "pago_divisa": 0.0, "vuelto_moneda": 0.0,
                              "pago_texto": "Efectivo: 50.00 CUP + Transferencia: 1200.00 CUP",
                              "vuelto_texto": "250.00 CUP", "saldo_pendiente": 0.0, "pagada": 1},
    "Pastilla transferencia": {"metodo_pago": "Transferencia", "moneda_pago": "CUP", "tasa_cambio": 1.0,
                               "metodo_pago_real": "Transferencia", "monto_efectivo_cup": 0.0,
                               "monto_transferencia_cup": 1000.0, "salida_efectivo_extra": 0.0,
                               "pago_divisa": 0.0, "vuelto_moneda": 0.0,
                               "pago_texto": "Transferencia: 1000.00 CUP", "vuelto_texto": "0.00 CUP",
                               "saldo_pendiente": 0.0, "pagada": 1},
    "Deuda": {"metodo_pago": "Efectivo", "moneda_pago": "CUP", "tasa_cambio": 1.0,
              "metodo_pago_real": "", "monto_efectivo_cup": 0.0,
              "monto_transferencia_cup": 0.0, "salida_efectivo_extra": 0.0,
              "pago_divisa": 0.0, "vuelto_moneda": 0.0,
              "pago_texto": "Deuda registrada", "vuelto_texto": "0.00 CUP",
              "saldo_pendiente": 1000.0, "pagada": 0},
    "USD justo": {"metodo_pago": "Efectivo", "moneda_pago": "USD", "tasa_cambio": 200.0,
                  "metodo_pago_real": "Efectivo", "monto_efectivo_cup": 0.0,
                  "monto_transferencia_cup": 0.0, "salida_efectivo_extra": 0.0,
                  "pago_divisa": 5.0, "vuelto_moneda": 0.0,
                  "pago_texto": "5.00 USD", "vuelto_texto": "0.00 CUP",
                  "saldo_pendiente": 0.0, "pagada": 1},
    "USD de mas": {"metodo_pago": "Efectivo", "moneda_pago": "USD", "tasa_cambio": 400.0,
                   "metodo_pago_real": "Efectivo", "monto_efectivo_cup": 0.0,
                   "monto_transferencia_cup": 0.0, "salida_efectivo_extra": 1000.0,
                   "pago_divisa": 5.0, "vuelto_moneda": 0.0,
                   "pago_texto": "5.00 USD", "vuelto_texto": "1000.00 CUP",
                   "saldo_pendiente": 0.0, "pagada": 1},
    "USD con CUP": {"metodo_pago": "Efectivo", "moneda_pago": "USD", "tasa_cambio": 100.0,
                    "metodo_pago_real": "Mixto", "monto_efectivo_cup": 500.0,
                    "monto_transferencia_cup": 0.0, "salida_efectivo_extra": 0.0,
                    "pago_divisa": 5.0, "vuelto_moneda": 0.0,
                    "pago_texto": "5.00 USD + 600.00 CUP (efectivo)", "vuelto_texto": "100.00 CUP",
                    "saldo_pendiente": 0.0, "pagada": 1},
    "USD vuelto en divisa": {"metodo_pago": "Efectivo", "moneda_pago": "USD", "tasa_cambio": 400.0,
                             "metodo_pago_real": "Efectivo", "monto_efectivo_cup": 0.0,
                             "monto_transferencia_cup": 0.0, "salida_efectivo_extra": 600.0,
                             "pago_divisa": 5.0, "vuelto_moneda": 1.0,
                             "pago_texto": "5.00 USD", "vuelto_texto": "1.00 USD + 600.00 CUP",
                             "saldo_pendiente": 0.0, "pagada": 1},
}


def pago_del_escenario(solo_transferencia, es_deuda, moneda, tasa, pagado,
                       transf_cup, cup_ef, cup_tr, vuelto_moneda):
    return Pago(
        total_cup=TOTAL,
        moneda=moneda,
        tasa=a_numero(tasa, 1.0),
        efectivo=a_numero(pagado),
        transferencia=a_numero(transf_cup),
        cup_efectivo=a_numero(cup_ef),
        cup_transferencia=a_numero(cup_tr),
        vuelto_en_moneda=a_numero(vuelto_moneda),
        solo_transferencia=bool(solo_transferencia),
    )
