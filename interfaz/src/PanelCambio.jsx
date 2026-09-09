import { useCallback, useEffect, useMemo, useState } from "react";
import { api, dinero, enviar } from "./api";

// Fecha local, no UTC: ver el comentario largo en PanelCorte.jsx. Con
// toISOString() el efectivo en caja se vaciaba solo cada noche.
const hoy = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

export default function PanelCambio() {
  const [tipo, setTipo] = useState("compra");
  const [moneda, setMoneda] = useState("USD");
  const [cantidad, setCantidad] = useState("");
  const [tasa, setTasa] = useState("");
  const [observaciones, setObservaciones] = useState("");
  const [saldo, setSaldo] = useState(null);
  const [aviso, setAviso] = useState(null);
  const [guardando, setGuardando] = useState(false);

  const cargarSaldo = useCallback(async () => {
    try {
      setSaldo(await api(`/corte/${hoy()}`));
    } catch {
      setSaldo(null);
    }
  }, []);

  useEffect(() => { cargarSaldo(); }, [cargarSaldo]);

  const montoCup = useMemo(
    () => (Number(cantidad) || 0) * (Number(tasa) || 0),
    [cantidad, tasa]
  );

  async function guardar() {
    setGuardando(true);
    setAviso(null);
    try {
      const r = await enviar("/cambio", {
        tipo, moneda,
        cantidad: Number(cantidad) || 0,
        tasa: Number(tasa) || 0,
        observaciones,
      });
      setAviso({ tipo: "bien", texto: r.mensaje });
      setCantidad(""); setTasa(""); setObservaciones("");
      cargarSaldo();
    } catch (e) {
      setAviso({ tipo: "error", texto: e.message });
    } finally {
      setGuardando(false);
    }
  }

  const divisas = saldo?.saldo_divisas ?? {};

  return (
    <div className="cuerpo una-columna">
      <section className="tarjeta">
        <h2>Efectivo en caja (hoy)</h2>
        <p className="cifra-linea">
          USD: {dinero(divisas.USD)} &nbsp;|&nbsp; EUR: {dinero(divisas.EUR)}
          &nbsp;|&nbsp; CUP: {dinero(saldo?.total_esperado)}
        </p>
      </section>

      <section className="tarjeta">
        <h2>Registrar operación</h2>

        <div className="fila" style={{ marginBottom: 12 }}>
          <label>Tipo de operación</label>
          <button className={`pastilla ${tipo === "compra" ? "" : ""}`}
                  aria-pressed={tipo === "compra"}
                  onClick={() => setTipo("compra")}>Compra</button>
          <button className="pastilla" aria-pressed={tipo === "venta"}
                  onClick={() => setTipo("venta")}>Venta</button>

          <label style={{ marginLeft: 14 }}>Moneda</label>
          <select value={moneda} onChange={(e) => setMoneda(e.target.value)}>
            <option>USD</option><option>EUR</option>
          </select>
        </div>

        <div className="campos" style={{ maxWidth: 620 }}>
          <label className="campo"><span>Cantidad</span>
            <input className="numero" value={cantidad}
                   onChange={(e) => setCantidad(e.target.value)} /></label>
          <label className="campo"><span>Tasa (CUP)</span>
            <input className="numero" value={tasa}
                   onChange={(e) => setTasa(e.target.value)} /></label>
          <label className="campo ancho"><span>Observaciones</span>
            <input value={observaciones}
                   onChange={(e) => setObservaciones(e.target.value)} /></label>
        </div>

        <div className="total" style={{ justifyContent: "flex-start" }}>
          <span className="etiqueta">MONTO EN CUP</span>
          <span className="cifra">{dinero(montoCup)}</span>
        </div>

        {aviso && <div className={`aviso ${aviso.tipo}`}>{aviso.texto}</div>}

        <div className="fila" style={{ marginTop: 14 }}>
          <button className="boton verde" onClick={guardar}
                  disabled={guardando || !(Number(cantidad) > 0 && Number(tasa) > 0)}>
            {guardando ? "Guardando…" : "Registrar operación"}
          </button>
          <button className="boton fantasma"
                  onClick={() => { setCantidad(""); setTasa(""); setObservaciones(""); setAviso(null); }}>
            Limpiar
          </button>
        </div>
      </section>
    </div>
  );
}
