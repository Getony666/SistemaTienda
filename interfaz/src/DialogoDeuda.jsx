import { useEffect, useState } from "react";
import { dinero, enviar } from "./api";

const METODOS = ["Efectivo", "Transferencia", "Mixto"];

// Los mismos billetes que en el panel de Ventas: el vuelto se arma sumando.
const DENOMINACIONES = [1, 5, 10, 20, 50, 100];

export default function DialogoDeuda({ deuda, alCerrar, alCobrar }) {
  const [moneda, setMoneda] = useState("CUP");
  const [tasa, setTasa] = useState("");
  const [metodo, setMetodo] = useState("Efectivo");
  const [efectivo, setEfectivo] = useState("");
  const [efectivoCup, setEfectivoCup] = useState("");
  const [transferencia, setTransferencia] = useState("");
  const [vueltoMoneda, setVueltoMoneda] = useState("");

  const [simulacion, setSimulacion] = useState(null);
  const [error, setError] = useState(null);
  const [guardando, setGuardando] = useState(false);

  const enDivisa = moneda !== "CUP";
  const saldo = deuda.detalle_extra?.saldo_pendiente ?? 0;

  // Al pasar a divisa sólo se admite efectivo, igual que en la ventana.
  useEffect(() => {
    if (enDivisa) { setMetodo("Efectivo"); setTransferencia(""); }
    else { setTasa(""); setEfectivoCup(""); setVueltoMoneda(""); }
  }, [enDivisa]);

  const abono = () => ({
    moneda,
    tasa: enDivisa ? Number(tasa) || 0 : 1,
    metodo,
    efectivo: Number(efectivo) || 0,
    transferencia: Number(transferencia) || 0,
    efectivo_cup: Number(efectivoCup) || 0,
    vuelto_en_moneda: Number(vueltoMoneda) || 0,
  });

  // El resultado se lo pedimos a la API mientras se teclea: mismo cálculo
  // que usa el diálogo de tkinter.
  useEffect(() => {
    const id = setTimeout(async () => {
      try {
        setSimulacion(await enviar(`/deudas/${deuda.id}/simular`, abono()));
        setError(null);
      } catch (e) {
        setSimulacion(null);
        setError(e.message);
      }
    }, 150);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [moneda, tasa, metodo, efectivo, efectivoCup, transferencia, vueltoMoneda]);

  async function cobrar() {
    setGuardando(true);
    try {
      const r = await enviar(`/deudas/${deuda.id}/cobros`, abono());
      alCobrar(r.mensaje);
    } catch (e) {
      setError(e.message);
    } finally {
      setGuardando(false);
    }
  }

  const hayAlgoQueCobrar =
    (Number(efectivo) || 0) + (Number(transferencia) || 0) + (Number(efectivoCup) || 0) > 0;

  // ---------------------------------------------------------- vuelto mixto
  const tasaNumero = Number(tasa) || 0;
  const vueltoCup = simulacion?.vuelto_cup ?? 0;
  const topeEnMoneda = tasaNumero > 0 ? vueltoCup / tasaNumero : 0;

  const cabeOtroBillete = (valor) =>
    ((Number(vueltoMoneda) || 0) + valor) * tasaNumero <= vueltoCup + 1e-9;

  const sumarBillete = (valor) => {
    const nuevo = (Number(vueltoMoneda) || 0) + valor;
    if (nuevo * tasaNumero > vueltoCup + 1e-9) return;
    setVueltoMoneda(nuevo.toFixed(2));
  };

  // El reparto real del cambio. `vuelto_en_cup_a_entregar` es lo que sale de
  // la caja en CUP; lo demás se devuelve en billetes de la divisa.
  const textoDelVuelto = () => {
    if (!simulacion || vueltoCup <= 0) return "0.00 CUP";
    const enCup = simulacion.vuelto_en_cup_a_entregar ?? vueltoCup;
    const enMoneda = simulacion.vuelto_moneda ?? 0;
    if (enMoneda > 0 && enCup > 0.005) {
      return `${dinero(enMoneda)} ${moneda} + ${dinero(enCup)} CUP`;
    }
    if (enMoneda > 0) return `${dinero(enMoneda)} ${moneda}`;
    return `${dinero(enCup)} CUP`;
  };

  return (
    <div className="velo" onClick={(e) => e.target === e.currentTarget && alCerrar()}>
      <div className="modal" role="dialog" aria-label="Pagar deuda">
        <h2>Deuda #{deuda.id}</h2>

        <div className="resumen-deuda">
          <span>Total: <strong>{dinero(deuda.detalle_extra?.total)} CUP</strong></span>
          <span className="saldo">Saldo pendiente: <strong>{dinero(saldo)} CUP</strong></span>
        </div>

        <div className="fila" style={{ marginBottom: 12 }}>
          <label>Moneda</label>
          <select value={moneda} onChange={(e) => setMoneda(e.target.value)}>
            <option>CUP</option><option>USD</option><option>EUR</option>
          </select>
          {enDivisa && (
            <>
              <label style={{ marginLeft: 10 }}>Tasa (CUP)</label>
              <input className="numero" style={{ width: 100 }}
                     value={tasa} onChange={(e) => setTasa(e.target.value)} />
            </>
          )}
        </div>

        <div className="pastillas">
          {METODOS.map((m) => (
            <button key={m} className="pastilla" aria-pressed={metodo === m}
                    disabled={enDivisa && m !== "Efectivo"}
                    onClick={() => setMetodo(m)}>{m}</button>
          ))}
        </div>

        <div className="campos">
          {(metodo === "Efectivo" || metodo === "Mixto") && (
            <label className="campo">
              <span>{enDivisa ? `Efectivo (${moneda})` : "Efectivo (CUP)"}</span>
              <input className="numero" value={efectivo} autoFocus
                     onChange={(e) => setEfectivo(e.target.value)} />
            </label>
          )}
          {enDivisa && (
            <label className="campo"><span>Efectivo (CUP)</span>
              <input className="numero" value={efectivoCup}
                     onChange={(e) => setEfectivoCup(e.target.value)} /></label>
          )}
          {!enDivisa && (metodo === "Transferencia" || metodo === "Mixto") && (
            <label className="campo"><span>Transferencia (CUP)</span>
              <input className="numero" value={transferencia}
                     onChange={(e) => setTransferencia(e.target.value)} /></label>
          )}
        </div>

        {/* Vuelto mixto: parte en divisa, el resto en CUP. Sin esto sólo se
            podía teclear el número, y el reparto no se veía por ninguna parte. */}
        {enDivisa && vueltoCup > 0 && (
          <div className="adicional">
            <span className="titulo-bloque">
              Vuelto en {moneda} <em>(el resto se devuelve en CUP)</em>
            </span>
            <div className="fila">
              <input className="numero" style={{ width: 110 }} value={vueltoMoneda}
                     onChange={(e) => setVueltoMoneda(e.target.value)} />
              <div className="denominaciones">
                {DENOMINACIONES.map((v) => (
                  <button key={v} type="button" className="billete"
                          disabled={!cabeOtroBillete(v)}
                          title={`Añadir ${v} ${moneda} al vuelto`}
                          onClick={() => sumarBillete(v)}>+{v}</button>
                ))}
                <button type="button" className="billete limpiar"
                        disabled={!vueltoMoneda}
                        onClick={() => setVueltoMoneda("")}>Limpiar</button>
              </div>
            </div>
            <span className="nota">
              Como mucho {dinero(topeEnMoneda)} {moneda} a esta tasa
            </span>
          </div>
        )}

        {simulacion && hayAlgoQueCobrar && (
          <div className="vuelto" style={{ marginTop: 14 }}>
            {simulacion.pagada === 1 ? (
              <>
                <strong style={{ color: "var(--suave)", fontSize: 13 }}>Queda pagada</strong>
                {vueltoCup > 0 && (
                  <span className="cifra">Vuelto {textoDelVuelto()}</span>
                )}
              </>
            ) : (
              <>
                <strong style={{ color: "var(--suave)", fontSize: 13 }}>Pago parcial</strong>
                <span className="cifra">Resta {dinero(simulacion.nuevo_saldo)} CUP</span>
              </>
            )}
            <span className="nota">Abonado: {dinero(simulacion.total_pagado_cup)} CUP</span>
          </div>
        )}

        {error && <div className="aviso error" style={{ marginTop: 12 }}>{error}</div>}

        <div className="finales">
          <button className="boton verde" onClick={cobrar}
                  disabled={guardando || !simulacion || !hayAlgoQueCobrar}>
            {guardando ? "Guardando…" : "Cobrar"}
          </button>
          <button className="boton fantasma" onClick={alCerrar}>Cancelar</button>
        </div>
      </div>
    </div>
  );
}
