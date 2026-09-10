import { useCallback, useEffect, useState } from "react";
import "./estilos.css";
import { api, enviar } from "./api";
import Entrar from "./Entrar";
import PanelVentas from "./PanelVentas";
import PanelAlmacen from "./PanelAlmacen";
import PanelHistorial from "./PanelHistorial";
import PanelCambio from "./PanelCambio";
import PanelCorte from "./PanelCorte";
import PanelUsuarios from "./PanelUsuarios";

// `permiso` deja fuera de la barra lo que ese usuario no puede usar. Es una
// comodidad, no una barrera: lo que impide de verdad es la API, que contesta
// 403 aunque alguien llame a la ruta por su cuenta.
const PANELES = [
  { id: "ventas", icono: "🛒", texto: "Ventas" },
  { id: "almacen", icono: "📦", texto: "Almacén", permiso: "ver_almacen" },
  { id: "historial", icono: "🕒", texto: "Historial", permiso: "ver_historial" },
  { id: "cambio", icono: "💱", texto: "Cambio de Divisa", permiso: "cambio_divisa" },
  { id: "corte", icono: "🧮", texto: "Corte de Caja", permiso: "ver_corte" },
  { id: "usuarios", icono: "🔑", texto: "Usuarios", permiso: "gestionar_usuarios" },
];

export default function App() {
  const [acceso, setAcceso] = useState(null);   // null mientras se pregunta
  const [panel, setPanel] = useState("ventas");
  const [productos, setProductos] = useState([]);

  const recargarProductos = useCallback(async () => {
    try {
      setProductos(await api("/productos"));
    } catch {
      setProductos([]);
    }
  }, []);

  const preguntarQuienSoy = useCallback(async () => {
    try {
      setAcceso(await api("/sesion"));
    } catch {
      setAcceso({ sesion: null, permisos: [], hay_usuarios: true });
    }
  }, []);

  useEffect(() => { preguntarQuienSoy(); }, [preguntarQuienSoy]);
  useEffect(() => { if (acceso?.sesion) recargarProductos(); },
            [acceso?.sesion, recargarProductos]);

  if (acceso === null) {
    return <div className="puerta"><p className="vacio">Abriendo…</p></div>;
  }

  if (!acceso.sesion) {
    return (
      <Entrar
        hayUsuarios={acceso.hay_usuarios}
        alEntrar={(respuesta) => { setAcceso(respuesta); setPanel("ventas"); }}
      />
    );
  }

  const puede = (clave) => acceso.permisos.includes(clave);
  const visibles = PANELES.filter((p) => !p.permiso || puede(p.permiso));

  // Si a alguien le quitan un permiso mientras está dentro, la pestaña donde
  // estaba desaparece: se le devuelve a Ventas en vez de dejar el hueco.
  const actual = visibles.some((p) => p.id === panel) ? panel : "ventas";

  async function salir() {
    try {
      setAcceso(await enviar("/sesion", null, "DELETE"));
    } catch {
      await preguntarQuienSoy();
    }
  }

  return (
    <>
      <nav className="nav">
        {visibles.map((p) => (
          <button
            key={p.id}
            aria-current={actual === p.id ? "page" : undefined}
            onClick={() => setPanel(p.id)}
          >
            <span className="ico" aria-hidden="true">{p.icono}</span>{p.texto}
          </button>
        ))}

        <span className="quien">
          <b>{acceso.sesion.nombre}</b>
          <span className="rol">{acceso.sesion.rol}</span>
        </span>
        <button className="salir" onClick={salir} title="Que entre otra persona">
          Cambiar de usuario
        </button>
      </nav>

      {actual === "ventas" && (
        <PanelVentas productos={productos} recargarProductos={recargarProductos}
                     puede={puede} />
      )}
      {actual === "almacen" && (
        <PanelAlmacen puede={puede} recargarProductosGlobal={recargarProductos} />
      )}
      {actual === "historial" && <PanelHistorial puede={puede} />}
      {actual === "cambio" && <PanelCambio />}
      {actual === "corte" && <PanelCorte puede={puede} />}
      {actual === "usuarios" && (
        <PanelUsuarios alCambiarPermisos={preguntarQuienSoy} />
      )}
    </>
  );
}
