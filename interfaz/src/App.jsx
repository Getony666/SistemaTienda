import { useCallback, useEffect, useState } from "react";
import "./estilos.css";
import { api } from "./api";
import PanelVentas from "./PanelVentas";
import PanelHistorial from "./PanelHistorial";
import PanelCambio from "./PanelCambio";
import PanelCorte from "./PanelCorte";

const PANELES = [
  { id: "ventas", icono: "🛒", texto: "Ventas" },
  { id: "historial", icono: "🕒", texto: "Historial" },
  { id: "cambio", icono: "💱", texto: "Cambio de Divisa" },
  { id: "corte", icono: "🧮", texto: "Corte de Caja" },
];

export default function App() {
  const [panel, setPanel] = useState("ventas");
  const [productos, setProductos] = useState([]);

  const recargarProductos = useCallback(async () => {
    try {
      setProductos(await api("/productos"));
    } catch {
      setProductos([]);
    }
  }, []);

  useEffect(() => { recargarProductos(); }, [recargarProductos]);

  return (
    <>
      <nav className="nav">
        {PANELES.map((p) => (
          <button
            key={p.id}
            aria-current={panel === p.id ? "page" : undefined}
            onClick={() => setPanel(p.id)}
          >
            <span className="ico" aria-hidden="true">{p.icono}</span>{p.texto}
          </button>
        ))}
        <span className="marca">MiTienda</span>
      </nav>

      {panel === "ventas" && (
        <PanelVentas productos={productos} recargarProductos={recargarProductos} />
      )}
      {panel === "historial" && <PanelHistorial />}
      {panel === "cambio" && <PanelCambio />}
      {panel === "corte" && <PanelCorte />}
    </>
  );
}
