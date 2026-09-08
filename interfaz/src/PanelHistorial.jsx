import { useCallback, useEffect, useState } from "react";
import { api, dinero, enviar } from "./api";
import DialogoDeuda from "./DialogoDeuda";

const TIPOS = [
  ["todos", "Todos"], ["ventas", "Ventas"], ["deudas", "Deudas"],
  ["cambio", "Cambio de Divisa"], ["entrada_efectivo", "Entrada de Efectivo"],
  ["salida_efectivo", "Salida de Efectivo"], ["salidas", "Salidas"],
  ["merma", "Merma"], ["entrada_producto", "Entrada de Producto"],
];

const METODOS = [
  ["todos", "Todos"], ["efectivo", "Efectivo"],
  ["transferencia", "Transferencia"], ["mixto", "Mixto"],
];

export default function PanelHistorial() {
  const [registros, setRegistros] = useState([]);
  const [fecha, setFecha] = useState("");
  const [tipo, setTipo] = useState("todos");
  const [metodo, setMetodo] = useState("todos");
  const [elegido, setElegido] = useState(null);
  const [aviso, setAviso] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [cobrando, setCobrando] = useState(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    setAviso(null);
    try {
      const parametros = new URLSearchParams({ tipo, metodo });
      if (fecha) parametros.set("fecha", fecha);
      setRegistros(await api(`/ventas?${parametros}`));
      setElegido(null);
    } catch (e) {
      setAviso({ tipo: "error", texto: e.message });
    } finally {
      setCargando(false);
    }
  }, [fecha, tipo, metodo]);

  useEffect(() => { cargar(); }, [cargar]);

  async function revertir() {
    if (!elegido) return;
    setAviso(null);
    try {
      const r = await enviar(
        `/historial/${elegido.id}?tipo=${encodeURIComponent(elegido.tipo)}`,
        null, "DELETE");
      setAviso({ tipo: "bien", texto: r.mensaje });
      cargar();
    } catch (e) {
      setAviso({ tipo: "error", texto: e.message });
    }
  }

  const esDeudaPendiente = (r) =>
    r?.tipo === "Deuda" && r?.detalle_extra?.pagada === 0;

  return (
    <div className="cuerpo una-columna">
      {cobrando && (
        <DialogoDeuda
          deuda={cobrando}
          alCerrar={() => setCobrando(null)}
          alCobrar={(mensaje) => {
            setCobrando(null);
            setAviso({ tipo: "bien", texto: mensaje });
            cargar();
          }}
        />
      )}
      <section className="tarjeta">
        <h2>Filtros</h2>
        <div className="fila" style={{ marginBottom: 10 }}>
          <label htmlFor="fecha">Fecha</label>
          <input id="fecha" type="date" value={fecha}
                 onChange={(e) => setFecha(e.target.value)} />
          <button className="boton fantasma" onClick={() => setFecha("")}>Todas</button>
          <button className="boton" onClick={cargar}>Refrescar</button>
          <button className="boton naranja" onClick={() => setCobrando(elegido)}
                  disabled={!elegido || !esDeudaPendiente(elegido)}>Pagar deuda</button>
          <button className="boton rojo" onClick={revertir}
                  disabled={!elegido}>Eliminar del historial</button>
        </div>

        <div className="fila" style={{ marginBottom: 8 }}>
          <label>Tipo</label>
          <select value={tipo} onChange={(e) => setTipo(e.target.value)}>
            {TIPOS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
          </select>
          <label style={{ marginLeft: 10 }}>Método de pago</label>
          <select value={metodo} onChange={(e) => setMetodo(e.target.value)}>
            {METODOS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
          </select>
        </div>

        {aviso && <div className={`aviso ${aviso.tipo}`}>{aviso.texto}</div>}
      </section>

      <section className="tarjeta">
        <h2>Registros</h2>
        <div className="desplazable alto">
          {cargando ? (
            <p className="vacio">Cargando…</p>
          ) : registros.length === 0 ? (
            <p className="vacio">No hay registros con esos filtros</p>
          ) : (
            <table className="tabla">
              <thead>
                <tr>
                  <th className="centro">ID</th><th>Fecha</th><th>Tipo</th>
                  <th>Producto</th><th className="derecha">Monto</th>
                  <th>Método</th><th>Observaciones</th>
                </tr>
              </thead>
              <tbody>
                {registros.map((r, i) => (
                  <tr key={`${r.tipo}-${r.id}-${i}`}
                      tabIndex={0}
                      aria-selected={elegido === r}
                      className={esDeudaPendiente(r) ? "deuda" : undefined}
                      onClick={() => setElegido(r)}
                      onFocus={() => setElegido(r)}>
                    <td className="centro">{r.id}</td>
                    <td>{r.fecha}</td>
                    <td>{r.tipo}</td>
                    <td>{r.producto}</td>
                    <td className="derecha">{dinero(r.monto)} {r.moneda}</td>
                    <td>{r.metodo_pago}</td>
                    <td className="recortado" title={r.observaciones}>{r.observaciones}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      <section className="tarjeta">
        <h2>Detalle</h2>
        {!elegido ? (
          <p className="vacio">Selecciona un registro de la lista para ver detalle</p>
        ) : (
          <table className="tabla">
            <tbody>
              {Object.entries(elegido.detalle_extra ?? {}).map(([campo, valor]) => (
                <tr key={campo}>
                  <td style={{ width: 260, color: "var(--suave)" }}>{campo}</td>
                  <td>{String(valor)}</td>
                </tr>
              ))}
              {!elegido.detalle_extra && (
                <tr><td className="vacio">Este registro no tiene detalle adicional</td></tr>
              )}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
