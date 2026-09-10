import { useCallback, useEffect, useState } from "react";
import "./estilos.css";
import { api, enviar } from "./api";
import Entrar from "./Entrar";
import BandaLicencia from "./BandaLicencia";
import PanelLicencia from "./PanelLicencia";
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

// Con estos dos el programa no da para nada, así que la pantalla de licencia
// sale ANTES de preguntar quién va a usar la caja: no tiene sentido pedir un
// PIN si la caja no va a abrir, y en una tienda recién estrenada puede que
// todavía no haya ni usuarios que nombrar.
const CERRADO = ["sin_licencia", "reloj_atrasado"];

export default function App() {
  const [acceso, setAcceso] = useState(null);   // null mientras se pregunta
  const [licencia, setLicencia] = useState(null);
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

  const preguntarLicencia = useCallback(async () => {
    try {
      setLicencia(await api("/licencia"));
    } catch {
      // Si la propia comprobación falla, se deja pasar. Un fallo nuestro no
      // puede dejar a una tienda sin poder cobrar: el candado de verdad está
      // en la API, y ésa contestará 402 si de verdad hay que parar.
      setLicencia({ estado: "activa", puede_escribir: true, maquina: "" });
    }
  }, []);

  useEffect(() => { preguntarQuienSoy(); }, [preguntarQuienSoy]);
  useEffect(() => { preguntarLicencia(); }, [preguntarLicencia]);
  useEffect(() => { if (acceso?.sesion) recargarProductos(); },
            [acceso?.sesion, recargarProductos]);

  if (acceso === null || licencia === null) {
    return <div className="puerta"><p className="vacio">Abriendo…</p></div>;
  }

  if (CERRADO.includes(licencia.estado)) {
    return <PanelLicencia licencia={licencia} alCambiar={setLicencia} pantallaCompleta />;
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
  // estaba desaparece: se le devuelve a Ventas en vez de dejar el hueco. La
  // licencia no está en la barra pero es un destino válido.
  const actual = panel === "licencia" || visibles.some((p) => p.id === panel)
    ? panel : "ventas";

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
        <button className="salir" onClick={() => setPanel("licencia")}
                aria-current={actual === "licencia" ? "page" : undefined}
                title="Ver o cambiar la licencia de este programa">
          Licencia
        </button>
        <button className="salir" onClick={salir} title="Que entre otra persona">
          Cambiar de usuario
        </button>
      </nav>

      <BandaLicencia licencia={licencia} alPulsar={() => setPanel("licencia")} />

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
      {actual === "licencia" && (
        <PanelLicencia licencia={licencia} alCambiar={setLicencia} />
      )}
    </>
  );
}
