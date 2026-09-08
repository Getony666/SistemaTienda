"""Cálculo del pago y del vuelto, y cierre de la venta.

Es la parte más delicada del programa: combina pagos en CUP, en divisa,
por transferencia y mixtos, con vuelto en cualquiera de ellos."""

import datetime

from .. import calculo_cobro as cc
from ..rutas import consulta
from ..ventas_datos import registrar_venta_en_db


class CobroMixin:
    """Cobro de la venta: forma de pago, cálculo del vuelto y cierre."""

    def actualizar_moneda_pago(self, event=None):
        if self.actualizando:
            return

        if not hasattr(self, "_pago_cup_adicional_auto_valor"):
            self._pago_cup_adicional_auto_valor = None

        self.actualizando = True
        try:
            moneda = self.moneda_pago.get()
            if moneda == "CUP":
                self.entry_tasa.config(state="disabled")
                self.tasa_cambio.set("1.00")
                self.entry_vuelto_moneda.config(state="disabled")
                self.vuelto_moneda_var.set("")
                self.frame_vuelto_divisa.pack_forget()
                self.label_resto_cup.config(text="")
                self.label_moneda_pago.config(text="CUP")
                self.label_vuelto_moneda.config(text="CUP")
                self.label_pagado.config(text="Pagado (efectivo):")
                self.pagado_var.set("")
                self.vuelto_var.set("0.00")
                self.vuelto_total_cup = 0.0

                self.frame_transferencia.pack(fill="x")
                self.frame_adicional_divisa.pack_forget()
                self.check_transferencia.config(state="normal")
                self.entry_pago_cup_adicional.config(state="disabled")
                self.entry_pago_transferencia_adicional.config(state="disabled")
                self.pago_cup_adicional_var.set("")
                self.pago_transferencia_adicional_var.set("")
                self._pago_cup_adicional_auto_valor = None
                if self.transferencia_var.get() == 0:
                    self.entry_pago_transferencia.config(state="normal")
                else:
                    self.entry_pago_transferencia.config(state="disabled")
                self.pago_transferencia_var.set("")
                self.label_pago_efectivo_resto.config(text="")
            else:
                self.entry_tasa.config(state="normal")
                self.tasa_cambio.set("")
                self.entry_vuelto_moneda.config(state="normal")
                self.frame_vuelto_divisa.pack(side="top", anchor="w", pady=(6, 0), before=self.label_resto_cup)
                self.label_vuelto_divisa_texto.config(text=f"Vuelto en {moneda}:")
                self.label_moneda_pago.config(text=moneda)
                self.label_vuelto_moneda.config(text=moneda)
                self.label_pagado.config(text="Pago en divisa:")
                self.pagado_var.set("")
                self.vuelto_var.set("0.00")
                self.vuelto_total_cup = 0.0

                self.frame_transferencia.pack_forget()
                self.frame_adicional_divisa.pack(fill="x")
                self.check_transferencia.config(state="disabled")
                self.transferencia_var.set(0)
                self.entry_pago_transferencia.config(state="disabled")
                self.pago_transferencia_var.set("")
                self.label_pago_efectivo_resto.config(text="")
                # AHORA ESTOS CAMPOS SON EDITABLES
                self.entry_pago_cup_adicional.config(state="normal")
                self.entry_pago_transferencia_adicional.config(state="normal")
                self.pago_cup_adicional_var.set("")
                self.pago_transferencia_adicional_var.set("")
        finally:
            self.actualizando = False

    def actualizar_pago(self, event=None):
        if self.actualizando:
            return
        self.actualizando = True
        try:
            if self.transferencia_var.get() == 1:
                self.moneda_pago.set("CUP")
                self.combo_moneda.config(state="disabled")
                self.entry_tasa.config(state="disabled")
                self.entry_vuelto_moneda.config(state="disabled")
                self.vuelto_moneda_var.set("")
                self.frame_vuelto_divisa.pack_forget()
                self.label_resto_cup.config(text="")
                self.label_moneda_pago.config(text="CUP")
                self.label_vuelto_moneda.config(text="CUP")
                self.entry_pago_transferencia.config(state="disabled")
                self.pago_transferencia_var.set("")
                self.label_pago_efectivo_resto.config(text="")
                self.entry_pago_cup_adicional.config(state="disabled")
                self.pago_cup_adicional_var.set("")
                self.entry_pago_transferencia_adicional.config(state="disabled")
                self.pago_transferencia_adicional_var.set("")
                self.frame_adicional_divisa.pack_forget()
                self.frame_transferencia.pack_forget()
                try:
                    total = float(self.total_var.get())
                    self.pagado_var.set(f"{total:.2f}")
                    self.vuelto_var.set("0.00")
                    self.vuelto_total_cup = 0.0
                    self.entry_pagado.config(state="disabled")
                    self.check_transferencia.configure(style="PastillaOk.Toolbutton")
                except:
                    self.pagado_var.set("0.00")
            else:
                self.combo_moneda.config(state="readonly")
                self.entry_pagado.config(state="normal")
                self.check_transferencia.configure(style="Pastilla.Toolbutton")
                self.actualizar_moneda_pago()
        finally:
            self.actualizando = False

    def actualizar_por_transferencia(self):
        self.actualizar_pago()

    def calcular_vuelto_silencioso(self, event=None):
        if self.transferencia_var.get() == 1:
            return
        if not self.pagado_var.get():
            return
        try:
            float(self.pagado_var.get())
        except ValueError:
            return
        self._calcular_vuelto_interno(silencioso=True)
    
    def _actualizar_efectivo_desde_transferencia(self):
        try:
            total = float(self.total_var.get())
            transferencia_text = self.pago_transferencia_var.get().strip()
            if not transferencia_text:
                return
            transferencia = float(transferencia_text)
            if transferencia < 0:
                self.mostrar_mensaje("error", "Error", "La transferencia no puede ser negativa")
                self.pago_transferencia_var.set("")
                return
            if transferencia > total:
                self.mostrar_mensaje("error", "Error", f"La transferencia ({transferencia:.2f}) supera el total ({total:.2f})")
                self.pago_transferencia_var.set("")
                return
            resto = total - transferencia
            self.pagado_var.set(f"{resto:.2f}")
            self.label_pago_efectivo_resto.config(text=f"Efectivo: {resto:.2f} CUP")
        except ValueError:
            pass

    def calcular_vuelto_con_pago_mixto(self, event=None):
        moneda = self.moneda_pago.get()
        if moneda != "CUP" or self.transferencia_var.get() == 1:
            return
        self._actualizar_efectivo_desde_transferencia()
        try:
            total_venta = float(self.total_var.get())
            pago_efectivo = float(self.pagado_var.get().strip() or "0")
            pago_transferencia = float(self.pago_transferencia_var.get().strip() or "0")
            if pago_transferencia < 0:
                self.mostrar_mensaje("error", "Error", "El pago por transferencia no puede ser negativo")
                self.pago_transferencia_var.set("")
                return
            total_pagado = pago_efectivo + pago_transferencia
            if total_pagado < 0:
                return
            if pago_efectivo > 0 and pago_transferencia > 0:
                self.label_pago_efectivo_resto.config(text=f"Efectivo: {pago_efectivo:.2f}  |  Transferencia: {pago_transferencia:.2f}")
            elif pago_transferencia > 0:
                self.label_pago_efectivo_resto.config(text=f"Transferencia: {pago_transferencia:.2f}")
            elif pago_efectivo > 0:
                self.label_pago_efectivo_resto.config(text=f"Efectivo: {pago_efectivo:.2f}")
            else:
                self.label_pago_efectivo_resto.config(text="")
            if total_pagado >= total_venta:
                vuelto_cup = total_pagado - total_venta
                self.vuelto_total_cup = vuelto_cup
                self.vuelto_var.set(f"{vuelto_cup:.2f} CUP")
                self.label_vuelto_moneda.config(text="CUP")
                if vuelto_cup > 0:
                    self.entry_vuelto_moneda.config(state="disabled")
                    self.vuelto_moneda_var.set("")
                    self.label_resto_cup.config(text="")
                else:
                    self.vuelto_var.set("0.00 CUP")
            else:
                self.vuelto_var.set("0.00 CUP")
                self.vuelto_total_cup = 0.0
                self.label_vuelto_moneda.config(text="CUP")
        except ValueError:
            self.pago_transferencia_var.set("")
            self.label_pago_efectivo_resto.config(text="")
            self.vuelto_var.set("0.00 CUP")
            self.vuelto_total_cup = 0.0

    def _limpiar_zona_vuelto(self):
        """Deja el bloque del vuelto a cero."""
        self.vuelto_var.set("0.00")
        self.label_vuelto_valor.config(text="0.00")
        self.label_vuelto_moneda.config(text="CUP")
        self.entry_vuelto_moneda.config(state="disabled")
        self.vuelto_moneda_var.set("")
        self.label_resto_cup.config(text="")
        self.vuelto_total_cup = 0.0

    def _calcular_vuelto_interno(self, silencioso=False):
        """Recoge lo tecleado, pide el cálculo y pinta el resultado.

        La aritmética vive en `lddl/calculo_cobro.py`. Aquí sólo queda leer
        campos, decidir qué mostrar y el autorrelleno del CUP que falta, que
        es comodidad de pantalla y no parte del cálculo.
        """
        if self.transferencia_var.get() == 1:
            if not silencioso:
                self._limpiar_zona_vuelto()
            return

        try:
            total_cup = float(self.total_var.get())
            if self.moneda_pago.get() == cc.CUP:
                self._vuelto_en_cup(total_cup)
            else:
                self._vuelto_en_divisa(total_cup, self.moneda_pago.get(), silencioso)
        except ValueError:
            pass

    def _vuelto_en_cup(self, total_cup):
        pago = cc.Pago(
            total_cup=total_cup,
            efectivo=float(self.pagado_var.get()) if self.pagado_var.get() else 0.0,
            transferencia=float(self.pago_transferencia_var.get().strip() or "0"),
        )
        vuelto = cc.calcular_vuelto(pago)

        if not vuelto.cubre:
            self._limpiar_zona_vuelto()
            if pago.efectivo > 0 or pago.transferencia > 0:
                self.label_pago_efectivo_resto.config(
                    text=f"Faltan {vuelto.falta_cup:.2f} CUP")
            else:
                self.label_pago_efectivo_resto.config(text="")
            return

        self.vuelto_total_cup = vuelto.vuelto_cup
        self.vuelto_var.set(f"{vuelto.vuelto_cup:.2f}")
        self.label_vuelto_valor.config(text=f"{vuelto.vuelto_cup:.2f}")
        self.label_vuelto_moneda.config(text="CUP")
        self.entry_vuelto_moneda.config(state="disabled")
        self.vuelto_moneda_var.set("")
        self.label_resto_cup.config(text="")
        self.label_pago_efectivo_resto.config(text=cc.texto_resumen_pago(pago))

    def _leer_cup_adicional(self, variable, mensaje_error, silencioso, limpiar_auto=False):
        """Lee uno de los campos de CUP adicional. Devuelve (valor, texto, seguir)."""
        texto = variable.get().strip()
        try:
            return (float(texto) if texto else 0.0), texto, True
        except ValueError:
            if texto and not silencioso:
                self.mostrar_mensaje("error", "Error", mensaje_error)
                variable.set("")
                if limpiar_auto:
                    self._pago_cup_adicional_auto_valor = None
                return 0.0, texto, False
            return 0.0, texto, True

    def _vuelto_en_divisa(self, total_cup, moneda, silencioso):
        tasa = float(self.tasa_cambio.get().strip() or "0")
        if tasa <= 0:
            if not silencioso:
                self._limpiar_zona_vuelto()
            return

        pago_divisa = cc.a_numero(self.pagado_var.get())

        cup_efectivo, cup_efectivo_texto, seguir = self._leer_cup_adicional(
            self.pago_cup_adicional_var,
            "Ingresa un número válido para el pago en CUP efectivo",
            silencioso, limpiar_auto=True)
        if not seguir:
            return

        cup_transferencia, cup_transferencia_texto, seguir = self._leer_cup_adicional(
            self.pago_transferencia_adicional_var,
            "Ingresa un número válido para el pago en CUP transferencia",
            silencioso)
        if not seguir:
            return

        if cup_efectivo < 0:
            if not silencioso:
                self.mostrar_mensaje("error", "Error",
                                     "El pago en CUP efectivo no puede ser negativo")
                self.pago_cup_adicional_var.set("0.00")
            self._pago_cup_adicional_auto_valor = None
            return

        if cup_transferencia < 0:
            if not silencioso:
                self.mostrar_mensaje("error", "Error",
                                     "El pago en CUP transferencia no puede ser negativo")
                self.pago_transferencia_adicional_var.set("0.00")
            return

        # ---- Autorrelleno del CUP que falta -------------------------------
        #
        # Mientras el campo conserve exactamente el valor que pusimos nosotros,
        # sigue siendo una sugerencia. En cuanto la dependienta lo cambia, deja
        # de coincidir y pasa a ser un pago manual.
        auto_valor = getattr(self, "_pago_cup_adicional_auto_valor", None)
        es_sugerencia = auto_valor is not None and cup_efectivo_texto == auto_valor
        divisa_en_cup = pago_divisa * tasa if pago_divisa > 0 else 0.0

        if pago_divisa > 0 and divisa_en_cup >= total_cup:
            # La divisa ya cubre la venta: sobra la sugerencia en CUP.
            if es_sugerencia:
                self.pago_cup_adicional_var.set("")
                cup_efectivo = 0.0
                self._pago_cup_adicional_auto_valor = None
                if not cup_transferencia_texto:
                    cup_transferencia = 0.0

        elif pago_divisa > 0 and not cup_efectivo_texto and not cup_transferencia_texto:
            # No alcanza y no hay CUP puesto: sugerimos lo que falta.
            falta = cc.cup_faltante(total_cup, pago_divisa, tasa)
            if falta > 0:
                valor_auto = f"{falta:.2f}"
                self.pago_cup_adicional_var.set(valor_auto)
                self._pago_cup_adicional_auto_valor = valor_auto
                cup_efectivo = falta

        elif auto_valor is not None and cup_efectivo_texto != auto_valor:
            # Lo tocó a mano: deja de ser sugerencia nuestra.
            self._pago_cup_adicional_auto_valor = None

        # ---- Cálculo ------------------------------------------------------
        pago = cc.Pago(
            total_cup=total_cup,
            moneda=moneda,
            tasa=tasa,
            efectivo=pago_divisa,
            cup_efectivo=cup_efectivo,
            cup_transferencia=cup_transferencia,
            vuelto_en_moneda=cc.a_numero(self.vuelto_moneda_var.get()),
        )
        vuelto = cc.calcular_vuelto(pago)

        if not vuelto.cubre:
            self._limpiar_zona_vuelto()
            self.label_pago_efectivo_resto.config(text=f"Faltan {vuelto.falta_cup:.2f} CUP")
            return

        self.vuelto_total_cup = vuelto.vuelto_cup
        self.label_pago_efectivo_resto.config(text=cc.texto_resumen_pago(pago))

        if vuelto.error == "vuelto_moneda_excede":
            if not silencioso:
                maximo = cc.maximo_vuelto_en_moneda(vuelto.vuelto_cup, tasa)
                vuelto_moneda_cup = pago.vuelto_en_moneda * tasa
                self.mostrar_mensaje(
                    "error", "Error",
                    f"El vuelto en {moneda} ({pago.vuelto_en_moneda:.2f}) equivale a "
                    f"{vuelto_moneda_cup:.2f} CUP,\n"
                    f"que excede el vuelto total de {vuelto.vuelto_cup:.2f} CUP.\n"
                    f"Máximo permitido: {maximo:.2f} {moneda}")
                self.vuelto_moneda_var.set("")
            return

        self._pintar_vuelto_en_divisa(vuelto, moneda)

    def _pintar_vuelto_en_divisa(self, vuelto, moneda):
        """Muestra el vuelto repartido entre la moneda de pago y el CUP."""
        if vuelto.vuelto_cup <= 0:
            self.vuelto_var.set(f"{vuelto.vuelto_cup:.2f}")
            self.label_vuelto_valor.config(text=f"{vuelto.vuelto_cup:.2f}")
            self.label_vuelto_moneda.config(text="CUP")
            self.entry_vuelto_moneda.config(state="disabled")
            self.vuelto_moneda_var.set("")
            self.label_resto_cup.config(text="")
            return

        if vuelto.vuelto_moneda > 0 and vuelto.vuelto_cup_restante > 0:
            texto = (f"{vuelto.vuelto_moneda:.2f} {moneda} + "
                     f"{vuelto.vuelto_cup_restante:.2f} CUP")
            resto = f"Resto en CUP: {vuelto.vuelto_cup_restante:.2f}"
            moneda_label = ""
        elif vuelto.vuelto_moneda > 0:
            texto = f"{vuelto.vuelto_moneda:.2f} {moneda}"
            resto = "Todo el vuelto en moneda de pago"
            moneda_label = ""
        else:
            texto = f"{vuelto.vuelto_cup:.2f} CUP"
            resto = "Todo el vuelto en CUP"
            moneda_label = "CUP"

        self.vuelto_var.set(texto)
        self.label_vuelto_valor.config(text=texto)
        self.label_vuelto_moneda.config(text=moneda_label)
        self.label_resto_cup.config(text=resto)
        self.entry_vuelto_moneda.config(state="normal")

    def calcular_vuelto(self, event=None):
        self._calcular_vuelto_interno(silencioso=False)

    def calcular_vuelto_mixto(self, event=None):
        moneda = self.moneda_pago.get()
        if moneda == "CUP" or self.transferencia_var.get() == 1:
            return
        vuelto_total_cup = self.vuelto_total_cup
        if vuelto_total_cup <= 0:
            return
        tasa = float(self.tasa_cambio.get().strip() or "0")
        if tasa <= 0:
            return
        vuelto_moneda_text = self.vuelto_moneda_var.get().strip()
        if not vuelto_moneda_text:
            vuelto_moneda = 0.0
        else:
            try:
                vuelto_moneda = float(vuelto_moneda_text)
            except ValueError:
                vuelto_moneda = 0.0
        if vuelto_moneda < 0:
            self.mostrar_mensaje("error", "Error", "El vuelto en moneda extranjera no puede ser negativo")
            self.vuelto_moneda_var.set("")
            return
        vuelto_moneda_cup = vuelto_moneda * tasa
        if vuelto_moneda_cup > vuelto_total_cup and vuelto_moneda > 0:
            maximo_moneda = vuelto_total_cup / tasa
            self.mostrar_mensaje("error", "Error", f"El vuelto en {moneda} ({vuelto_moneda:.2f}) equivale a {vuelto_moneda_cup:.2f} CUP,\nque excede el vuelto total ({vuelto_total_cup:.2f} CUP).\nMáximo permitido en {moneda}: {maximo_moneda:.2f}")
            self.vuelto_moneda_var.set("")
            return
        resto_cup = vuelto_total_cup - vuelto_moneda_cup
        if resto_cup > 0 and vuelto_moneda > 0:
            self.label_resto_cup.config(text=f"Resto en CUP: {resto_cup:.2f}")
            self.vuelto_var.set(f"{vuelto_moneda:.2f} {moneda} + {resto_cup:.2f} CUP")
            self.label_vuelto_moneda.config(text="")
        elif vuelto_moneda > 0:
            self.label_resto_cup.config(text="Todo el vuelto en moneda de pago")
            self.vuelto_var.set(f"{vuelto_moneda:.2f} {moneda}")
            self.label_vuelto_moneda.config(text="")
        else:
            self.label_resto_cup.config(text="Todo el vuelto en CUP")
            self.vuelto_var.set(f"{vuelto_total_cup:.2f} CUP")
            self.label_vuelto_moneda.config(text="")

    def finalizar_venta(self):
        if not self.carrito:
            self.mostrar_mensaje("warning", "Advertencia", "El carrito está vacío")
            return

        es_deuda = self.deuda_var.get()
        es_mensajeria = self.mensajeria_var.get()
        observaciones = self.observaciones_deuda_var.get().strip() if es_deuda else ""

        pago_texto = ""
        vuelto_texto = ""
        monto_efectivo_cup = 0.0
        monto_transferencia_cup = 0.0
        pago_divisa = 0.0
        pago_efectivo = 0.0
        pago_transferencia = 0.0
        pago_cup_efectivo = 0.0
        pago_cup_transferencia = 0.0
        vuelto_cup_total = 0.0
        vuelto_moneda = 0.0
        salida_efectivo_extra = 0.0
        utilidad_total = 0.0

        saldo_pendiente = 0.0
        pagada = 0
        fecha_pago = None
        total_cup = 0.0
        metodo_pago = "Efectivo"
        moneda_pago = "CUP"
        tasa_cambio = 1.0
        metodo_pago_real = ""

        with consulta() as (conn_util, cursor_util):
            for item in self.carrito:
                cursor_util.execute("SELECT precio_compra FROM productos WHERE id = ?", (item["id"],))
                fila_util = cursor_util.fetchone()
                if fila_util:
                    precio_compra = fila_util[0]
                    utilidad_item = (item["precio"] - precio_compra) * item["cantidad"]
                    utilidad_total += utilidad_item

        if self.transferencia_var.get() == 1:
            metodo_pago = "Transferencia"
            moneda_pago = "CUP"
            tasa_cambio = 1.0
            pago_transferencia = float(self.total_var.get())
            total_pagado = pago_transferencia
            pago_texto = f"Transferencia: {total_pagado:.2f} CUP"
            vuelto_texto = "0.00 CUP"
            monto_efectivo_cup = 0.0
            monto_transferencia_cup = total_pagado
            metodo_pago_real = "Transferencia"
            mensaje_confirmacion = self._construir_mensaje_confirmacion(
                total_cup=float(self.total_var.get()),
                pago_texto=pago_texto,
                vuelto_texto=vuelto_texto,
                es_deuda=es_deuda,
                es_mensajeria=es_mensajeria,
                observaciones=observaciones
            )
        else:
            metodo_pago = "Efectivo"
            moneda_pago = self.moneda_pago.get()
            if moneda_pago == "CUP":
                tasa_cambio = 1.0
                pago_efectivo = float(self.pagado_var.get()) if self.pagado_var.get() else 0.0
                try:
                    pago_transferencia = float(self.pago_transferencia_var.get().strip() or "0")
                except ValueError:
                    pago_transferencia = 0.0
                total_pagado = pago_efectivo + pago_transferencia

                if pago_efectivo > 0 and pago_transferencia > 0:
                    metodo_pago_real = "Mixto"
                    pago_texto = f"Efectivo: {pago_efectivo:.2f} CUP + Transferencia: {pago_transferencia:.2f} CUP"
                elif pago_transferencia > 0:
                    metodo_pago_real = "Transferencia"
                    pago_texto = f"Transferencia: {pago_transferencia:.2f} CUP"
                else:
                    metodo_pago_real = "Efectivo"
                    pago_texto = f"Efectivo: {pago_efectivo:.2f} CUP"

                total_cup = float(self.total_var.get())
                vuelto_cup = total_pagado - total_cup
                if vuelto_cup > 0:
                    vuelto_texto = f"{vuelto_cup:.2f} CUP"
                    monto_efectivo_cup = pago_efectivo - vuelto_cup
                    if monto_efectivo_cup < 0:
                        monto_transferencia_cup = pago_transferencia - (vuelto_cup - pago_efectivo)
                        monto_efectivo_cup = 0.0
                    else:
                        monto_transferencia_cup = pago_transferencia
                else:
                    monto_efectivo_cup = pago_efectivo
                    monto_transferencia_cup = pago_transferencia
                    vuelto_texto = "0.00 CUP"

                mensaje_confirmacion = self._construir_mensaje_confirmacion(
                    total_cup=total_cup,
                    pago_texto=pago_texto,
                    vuelto_texto=vuelto_texto,
                    es_deuda=es_deuda,
                    es_mensajeria=es_mensajeria,
                    observaciones=observaciones
                )
            else:
                try:
                    tasa_cambio = float(self.tasa_cambio.get().strip())
                    if tasa_cambio <= 0:
                        self.mostrar_mensaje("error", "Error", "La tasa de cambio debe ser mayor que 0")
                        return
                except ValueError:
                    self.mostrar_mensaje("error", "Error", "Ingresa una tasa de cambio válida")
                    return

                pago_divisa = float(self.pagado_var.get()) if self.pagado_var.get() else 0.0
                
                # Obtener los montos en CUP (que ahora son editables)
                pago_cup_efectivo_text = self.pago_cup_adicional_var.get().strip()
                pago_cup_transferencia_text = self.pago_transferencia_adicional_var.get().strip()
                
                try:
                    pago_cup_efectivo = float(pago_cup_efectivo_text) if pago_cup_efectivo_text else 0.0
                except ValueError:
                    self.mostrar_mensaje("error", "Error", "Ingresa un número válido para el pago en CUP efectivo")
                    return
                
                try:
                    pago_cup_transferencia = float(pago_cup_transferencia_text) if pago_cup_transferencia_text else 0.0
                except ValueError:
                    self.mostrar_mensaje("error", "Error", "Ingresa un número válido para el pago en CUP transferencia")
                    return

                # Validar que los montos no sean negativos
                if pago_cup_efectivo < 0:
                    self.mostrar_mensaje("error", "Error", "El pago en CUP efectivo no puede ser negativo")
                    return
                
                if pago_cup_transferencia < 0:
                    self.mostrar_mensaje("error", "Error", "El pago en CUP transferencia no puede ser negativo")
                    return

                total_pagado = (pago_divisa * tasa_cambio) + pago_cup_efectivo + pago_cup_transferencia

                # Determinar método de pago real
                if pago_divisa > 0 and (pago_cup_efectivo > 0 or pago_cup_transferencia > 0):
                    metodo_pago_real = "Mixto"
                elif pago_divisa > 0:
                    metodo_pago_real = "Efectivo"
                else:
                    metodo_pago_real = "Efectivo"
                    moneda_pago = "CUP"
                    tasa_cambio = 1.0
                    total_pagado = pago_cup_efectivo + pago_cup_transferencia

                # Construir texto de pago
                partes_pago = []
                if pago_divisa > 0:
                    partes_pago.append(f"{pago_divisa:.2f} {moneda_pago}")
                if pago_cup_efectivo > 0:
                    partes_pago.append(f"{pago_cup_efectivo:.2f} CUP (efectivo)")
                if pago_cup_transferencia > 0:
                    partes_pago.append(f"{pago_cup_transferencia:.2f} CUP (transferencia)")
                
                pago_texto = " + ".join(partes_pago) if partes_pago else "0.00 CUP"
                
                total_cup = float(self.total_var.get())
                vuelto_cup_total = total_pagado - total_cup

                vuelto_moneda = 0.0
                vuelto_moneda_text = self.vuelto_moneda_var.get().strip()
                if vuelto_moneda_text:
                    try:
                        vuelto_moneda = float(vuelto_moneda_text)
                    except ValueError:
                        vuelto_moneda = 0.0

                if vuelto_moneda > 0 and moneda_pago != "CUP":
                    vuelto_moneda_cup = vuelto_moneda * tasa_cambio
                    if vuelto_moneda_cup > vuelto_cup_total:
                        self.mostrar_mensaje("error", "Error", 
                            f"El vuelto en {moneda_pago} ({vuelto_moneda:.2f}) equivale a {vuelto_moneda_cup:.2f} CUP, "
                            f"que excede el vuelto total de {vuelto_cup_total:.2f} CUP.\n"
                            f"Máximo permitido: {vuelto_cup_total / tasa_cambio:.2f} {moneda_pago}")
                        return

                vuelto_cup_restante = vuelto_cup_total - (vuelto_moneda * tasa_cambio) if vuelto_moneda > 0 else vuelto_cup_total

                if vuelto_cup_total > 0:
                    if vuelto_moneda > 0 and vuelto_cup_restante > 0:
                        vuelto_texto = f"{vuelto_moneda:.2f} {moneda_pago} + {vuelto_cup_restante:.2f} CUP"
                    elif vuelto_moneda > 0:
                        vuelto_texto = f"{vuelto_moneda:.2f} {moneda_pago}"
                    else:
                        vuelto_texto = f"{vuelto_cup_total:.2f} CUP"
                else:
                    vuelto_texto = "0.00 CUP"

                monto_efectivo_cup = pago_cup_efectivo
                monto_transferencia_cup = pago_cup_transferencia
                salida_efectivo_extra = 0.0

                if vuelto_cup_restante > 0:
                    pago_cup_total = pago_cup_efectivo + pago_cup_transferencia
                    if pago_cup_total >= vuelto_cup_restante:
                        # El vuelto se descuenta del pago en CUP
                        if monto_efectivo_cup >= vuelto_cup_restante:
                            monto_efectivo_cup -= vuelto_cup_restante
                        else:
                            resto = vuelto_cup_restante - monto_efectivo_cup
                            monto_efectivo_cup = 0.0
                            monto_transferencia_cup -= resto
                            if monto_transferencia_cup < 0:
                                monto_transferencia_cup = 0.0
                    else:
                        salida_efectivo_extra = vuelto_cup_restante - pago_cup_total
                        monto_efectivo_cup = 0.0
                        monto_transferencia_cup = 0.0

                mensaje_confirmacion = self._construir_mensaje_confirmacion(
                    total_cup=total_cup,
                    pago_texto=pago_texto,
                    vuelto_texto=vuelto_texto,
                    es_deuda=es_deuda,
                    es_mensajeria=es_mensajeria,
                    observaciones=observaciones,
                    tasa=tasa_cambio if moneda_pago != "CUP" else None
                )

        total_cup = float(self.total_var.get())

        if es_deuda:
            monto_efectivo_cup = 0.0
            monto_transferencia_cup = 0.0
            metodo_pago_real = ""
            pago_texto = "Deuda registrada"
            vuelto_texto = "0.00 CUP"
            saldo_pendiente = total_cup
            pagada = 0
            fecha_pago = None
            mensaje_confirmacion = self._construir_mensaje_confirmacion(
                total_cup=total_cup,
                pago_texto=pago_texto,
                vuelto_texto=vuelto_texto,
                es_deuda=es_deuda,
                es_mensajeria=es_mensajeria,
                observaciones=observaciones
            )
        else:
            saldo_pendiente = 0.0
            pagada = 1
            fecha_pago = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if not es_deuda and total_pagado < total_cup:
            self.mostrar_mensaje("error", "Error", f"El total pagado ({total_pagado:.2f}) es menor que el total de la venta ({total_cup:.2f})")
            return

        if not self.mostrar_mensaje("yesno", "Confirmar", mensaje_confirmacion):
            return

        try:
            exito_venta, resultado = registrar_venta_en_db(self.carrito, {
                "total_cup": total_cup,
                "metodo_pago": metodo_pago,
                "moneda_pago": moneda_pago,
                "tasa_cambio": tasa_cambio,
                "es_mensajeria": es_mensajeria,
                "es_deuda": es_deuda,
                "pagada": pagada,
                "fecha_pago": fecha_pago,
                "saldo_pendiente": saldo_pendiente,
                "metodo_pago_real": metodo_pago_real,
                "observaciones": observaciones,
                "pago_texto": pago_texto,
                "vuelto_texto": vuelto_texto,
                "monto_efectivo_cup": monto_efectivo_cup,
                "monto_transferencia_cup": monto_transferencia_cup,
                "utilidad_total": utilidad_total,
                "pago_divisa": pago_divisa,
                "vuelto_moneda": vuelto_moneda,
                "salida_efectivo_extra": salida_efectivo_extra,
            })
            if not exito_venta:
                self.mostrar_mensaje("error", "Error", resultado)
                return

            self.mostrar_mensaje("info", "Éxito", f"Venta realizada por {total_cup:.2f} CUP\n{'Deuda registrada' if es_deuda else ''}")
            self.carrito = []
            self.actualizar_carrito()
            self.vuelto_var.set("0.00")
            self.pagado_var.set("")
            self.transferencia_var.set(0)
            self.mensajeria_var.set(0)
            self.deuda_var.set(0)
            self.moneda_pago.set("CUP")
            self.tasa_cambio.set("1.00")
            self.vuelto_moneda_var.set("")
            self.pago_transferencia_var.set("")
            self.pago_cup_adicional_var.set("")
            self.pago_transferencia_adicional_var.set("")
            self._pago_cup_adicional_auto_valor = None
            self.label_resto_cup.config(text="")
            self.vuelto_total_cup = 0.0
            self.observaciones_deuda_var.set("")
            self.entry_obs_deuda.config(state="disabled")
            self.frame_obs_deuda.grid_remove()
            self.combo_moneda.config(state="readonly")
            self.entry_tasa.config(state="disabled")
            self.entry_vuelto_moneda.config(state="disabled")
            self.frame_vuelto_divisa.pack_forget()
            self.entry_pago_transferencia.config(state="normal")
            self.entry_pago_cup_adicional.config(state="disabled")
            self.entry_pago_transferencia_adicional.config(state="disabled")
            self.label_pago_efectivo_resto.config(text="")
            self.entry_pagado.config(state="normal")
            self.check_transferencia.config(state="normal")
            self.check_transferencia.configure(style="Pastilla.Toolbutton")
            self.label_vuelto_moneda.config(text="CUP")
            self.label_moneda_pago.config(text="CUP")
            self.label_pagado.config(text="Pagado (efectivo):")
            self.frame_transferencia.pack(fill="x")
            self.frame_adicional_divisa.pack_forget()
            if self.panel_ventas_visible:
                self.cargar_productos()
            if self.panel_historial_visible:
                self.cargar_ventas()
            self.actualizar_saldo_cambio()
            if self.panel_corte_visible:
                self.cargar_resumen_corte()
        except Exception as e:
            self.mostrar_mensaje("error", "Error", f"Error al guardar: {str(e)}")
        self.root.lift()
        self.root.focus_force()

    def _construir_mensaje_confirmacion(self, total_cup, pago_texto, vuelto_texto, es_deuda=False, es_mensajeria=False, observaciones="", tasa=None):
        mensaje = f"Finalizar venta por {total_cup:.2f} CUP?\n"
        if es_deuda:
            mensaje = f"Finalizar venta por {total_cup:.2f} CUP como DEUDA?\n"
            mensaje += "El saldo se registrará como pendiente.\n"
        else:
            mensaje += f"Pago: {pago_texto}\n"
            if vuelto_texto:
                mensaje += f"Vuelto: {vuelto_texto}\n"
            if tasa is not None and tasa != 1.0:
                mensaje += f"Tasa: {tasa:.2f}\n"
        if es_mensajeria:
            mensaje += "Mensajería activada\n"
        if observaciones:
            mensaje += f"Observaciones: {observaciones}\n"
        return mensaje

    def cancelar_venta(self):
        if not self.carrito:
            return
        if self.mostrar_mensaje("yesno", "Confirmar", "Cancelar la venta actual?"):
            self.carrito = []
            self.actualizar_carrito()
            self.vuelto_var.set("0.00")
            self.pagado_var.set("")
            self.transferencia_var.set(0)
            self.mensajeria_var.set(0)
            self.deuda_var.set(0)
            self.moneda_pago.set("CUP")
            self.tasa_cambio.set("1.00")
            self.vuelto_moneda_var.set("")
            self.pago_transferencia_var.set("")
            self.pago_cup_adicional_var.set("")
            self.pago_transferencia_adicional_var.set("")
            self._pago_cup_adicional_auto_valor = None
            self.label_resto_cup.config(text="")
            self.vuelto_total_cup = 0.0
            self.observaciones_deuda_var.set("")
            self.entry_obs_deuda.config(state="disabled")
            self.frame_obs_deuda.grid_remove()
            self.combo_moneda.config(state="readonly")
            self.entry_tasa.config(state="disabled")
            self.entry_vuelto_moneda.config(state="disabled")
            self.frame_vuelto_divisa.pack_forget()
            self.entry_pago_transferencia.config(state="normal")
            self.entry_pago_cup_adicional.config(state="disabled")
            self.entry_pago_transferencia_adicional.config(state="disabled")
            self.label_pago_efectivo_resto.config(text="")
            self.entry_pagado.config(state="normal")
            self.check_transferencia.config(state="normal")
            self.check_transferencia.configure(style="Pastilla.Toolbutton")
            self.label_vuelto_moneda.config(text="CUP")
            self.label_moneda_pago.config(text="CUP")
            self.label_pagado.config(text="Pagado (efectivo):")
            self.frame_transferencia.pack(fill="x")
            self.frame_adicional_divisa.pack_forget()
            if self.panel_ventas_visible:
                self.cargar_productos()
        self.root.lift()
        self.root.focus_force()
