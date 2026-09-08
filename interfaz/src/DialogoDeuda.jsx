import { useEffect, useState } from "react";
import { dinero, enviar } from "./api";

const METODOS = ["Efectivo", "Transferencia", "Mixto"];

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
          {enDivisa && simulacion?.vuelto_cup > 0 && (
            <label className="campo"><span>Vuelto en {moneda}</span>
              <input className="numero" value={vueltoMoneda}
                     onChange={(e) => setVueltoMoneda(e.target.value)} /></label>
          )}
        </div>

        {simulacion && hayAlgoQueCobrar && (
          <div className="vuelto" style={{ marginTop: 14 }}>
            {simulacion.pagada === 1 ? (
              <>
                <strong style={{ color: "var(--suave)", fontSize: 13 }}>Queda pagada</strong>
                {simulacion.vuelto_cup > 0 && (
                  <span className="cifra">Vuelto {dinero(simulacion.vuelto_cup)} CUP</span>
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
