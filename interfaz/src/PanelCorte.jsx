import { useCallback, useEffect, useState } from "react";
import { api, dinero, enviar } from "./api";

// La fecha se arma a mano, campo a campo. `toISOString()` da la fecha en
// UTC, y Cuba va cuatro o cinco horas por detrás: con él, toda venta hecha
// pasadas las ocho de la noche caía en el día siguiente, y la caja se
// cuadraba contra un día vacío. El programa guarda con la hora local
// (datetime.now()), así que aquí hay que preguntar por la local también.
const comoFecha = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

const hoy = () => comoFecha(new Date());
const ayer = () => {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return comoFecha(d);
};

// Mismo código de color por concepto que en la ventana de tkinter.
const FILAS = [
  { clave: "efectivo", color: "verde", titulo: "Ventas en Efectivo (CUP)",
    total: (r) => r.ventas_efectivo.total + r.cobros_efectivo.total,
    cuenta: (r) => `${r.ventas_efectivo.cantidad + r.cobros_efectivo.cantidad} transacciones` },
  { clave: "transferencia", color: "morado", titulo: "Transferencias",
    total: (r) => r.ventas_transferencia.total + r.cobros_transferencia.total,
    cuenta: (r) => `${r.ventas_transferencia.cantidad + r.cobros_transferencia.cantidad} transacciones` },
  { clave: "deudas", color: "ocre", titulo: "Deudas Pendientes del Día",
    total: (r) => r.deudas_pendientes_dia.total,
    cuenta: (r) => `${r.deudas_pendientes_dia.cantidad} deudas` },
  { clave: "utilidad", color: "naranja", titulo: "Utilidad Total",
    total: (r) => r.utilidad_total },
  { clave: "esperado", color: "teal", titulo: "TOTAL ESPERADO EN CAJA", grande: true,
    total: (r) => r.total_esperado },
  { clave: "ventas", color: "neutro", titulo: "Total de Ventas",
    total: (r) => r.total_ventas_dia },
];

const vacioEfectivo = { moneda: "CUP", monto: "", descripcion: "" };

export default function PanelCorte({ puede }) {
  const [fecha, setFecha] = useState(hoy());
  const [resumen, setResumen] = useState(null);
  const [fondo, setFondo] = useState("");
  const [aviso, setAviso] = useState(null);

  // Entrada y Salida de Efectivo viven aquí: son movimientos de caja, y el
  // corte es lo primero que cambia cuando se registra uno.
  const [abiertoEfectivo, setAbiertoEfectivo] = useState(null);
  const [camposEfectivo, setCamposEfectivo] = useState(vacioEfectivo);
  const [avisoEfectivo, setAvisoEfectivo] = useState(null);
  const [guardandoEfectivo, setGuardandoEfectivo] = useState(false);

  const cargar = useCallback(async (f) => {
    setAviso(null);
    try {
      const r = await api(`/corte/${f}`);
      setResumen(r);
      setFondo(String(r.fondo_registrado ?? 0));
    } catch (e) {
      setResumen(null);
      setAviso({ tipo: "error", texto: e.message });
    }
  }, []);

  useEffect(() => { cargar(fecha); }, [cargar, fecha]);

  async function guardarFondo() {
    setAviso(null);
    try {
      await enviar(`/caja/fondo/${fecha}`, { fondo: Number(fondo) || 0 }, "PUT");
      setAviso({ tipo: "bien", texto: "Fondo guardado" });
      cargar(fecha);
    } catch (e) {
      setAviso({ tipo: "error", texto: e.message });
    }
  }

  const abrirEfectivo = (tipo) => {
    setAbiertoEfectivo((actual) => (actual === tipo ? null : tipo));
    setCamposEfectivo(vacioEfectivo);
    setAvisoEfectivo(null);
  };

  const setCampoEfectivo = (campo) => (e) =>
    setCamposEfectivo((c) => ({ ...c, [campo]: e.target.value }));

  // El movimiento cambia el total esperado en caja: tras guardar hay que
  // recargar el resumen del día, no basta con cerrar el formulario.
  async function guardarEfectivo() {
    setGuardandoEfectivo(true);
    setAvisoEfectivo(null);
    try {
      const ruta = abiertoEfectivo === "entrada" ? "/caja/entradas" : "/caja/salidas";
      const r = await enviar(ruta, {
        moneda: camposEfectivo.moneda,
        monto: Number(camposEfectivo.monto) || 0,
        descripcion: camposEfectivo.descripcion,
      });
      setAvisoEfectivo({ tipo: "bien", texto: r?.mensaje ?? "Hecho" });
      setCamposEfectivo(vacioEfectivo);
      cargar(fecha);
    } catch (e) {
      setAvisoEfectivo({ tipo: "error", texto: e.message });
    } finally {
      setGuardandoEfectivo(false);
    }
  }

  const divisas = resumen?.saldo_divisas ?? {};

  return (
    <div className="cuerpo una-columna">
      <section className="tarjeta">
        <h2>Seleccionar fecha</h2>
        <div className="fila">
          <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
          <button className="boton" onClick={() => setFecha(hoy())}>Hoy</button>
          <button className="boton fantasma" onClick={() => setFecha(ayer())}>Ayer</button>
          <button className="boton verde" onClick={() => cargar(fecha)}>Actualizar</button>
        </div>
        {/* El aviso vive aquí, fuera del bloque del fondo: si estuviera
            dentro, quien no pueda fijar el fondo no vería los errores de
            carga, que no tienen nada que ver con el permiso. */}
        {aviso && <div className={`aviso ${aviso.tipo}`}>{aviso.texto}</div>}
      </section>

      {/* El fondo es dinero que se declara: quien no pueda fijarlo no ve
          ni el formulario. La API lo impide igual, esto es por comodidad. */}
      {puede("fondo_caja") && (
      <section className="tarjeta">
        <h2>Fondo de caja del día</h2>
        <div className="fila">
          <label htmlFor="fondo">Fondo (CUP)</label>
          <input id="fondo" className="numero" style={{ width: 140 }}
                 value={fondo} onChange={(e) => setFondo(e.target.value)} />
          <button className="boton morado" onClick={guardarFondo}>Guardar</button>
          <button className="boton rojo" onClick={() => setFondo("0")}>Limpiar</button>
        </div>
        <p className="nota-form">
          El fondo sustituye al que hubiera para esa fecha, no se suma.
        </p>
      </section>
      )}

      {/* Sin ninguno de los dos permisos, la tarjeta entera no se muestra:
          no hay nada que hacer aquí, y menos aún que ver. */}
      {(puede("entrada_efectivo") || puede("salida_efectivo")) && (
      <section className="tarjeta">
        <div className="cabecera-tarjeta">
          <h2>Movimientos de efectivo</h2>
          <div className="fila">
            {puede("entrada_efectivo") && (
              <button className={`boton verde ${abiertoEfectivo === "entrada" ? "activo" : ""}`}
                      onClick={() => abrirEfectivo("entrada")}>
                Entrada de Efectivo
              </button>
            )}
            {puede("salida_efectivo") && (
              <button className={`boton rojo ${abiertoEfectivo === "salida" ? "activo" : ""}`}
                      onClick={() => abrirEfectivo("salida")}>
                Salida de Efectivo
              </button>
            )}
          </div>
        </div>

        {abiertoEfectivo && (
          <div className="formulario verde-tenue">
            <div className="campos">
              <label className="campo"><span>Moneda</span>
                <select value={camposEfectivo.moneda} onChange={setCampoEfectivo("moneda")}>
                  <option>CUP</option><option>USD</option><option>EUR</option>
                </select></label>
              <label className="campo"><span>Monto</span>
                <input className="numero" value={camposEfectivo.monto}
                       onChange={setCampoEfectivo("monto")} /></label>
              <label className="campo ancho"><span>Descripción</span>
                <input value={camposEfectivo.descripcion}
                       onChange={setCampoEfectivo("descripcion")} /></label>
            </div>

            {avisoEfectivo && <div className={`aviso ${avisoEfectivo.tipo}`}>{avisoEfectivo.texto}</div>}

            <div className="fila" style={{ marginTop: 12 }}>
              <button className="boton verde" onClick={guardarEfectivo} disabled={guardandoEfectivo}>
                {guardandoEfectivo ? "Guardando…" : "Guardar"}
              </button>
              <button className="boton fantasma" onClick={() => setAbiertoEfectivo(null)}>Cancelar</button>
            </div>
          </div>
        )}
      </section>
      )}

      <section className="tarjeta">
        <h2>Resumen del día</h2>
        {!resumen ? (
          <p className="vacio">Sin datos para esa fecha</p>
        ) : (
          <div className="resumen">
            {FILAS.map((f) => (
              <div key={f.clave} className={`resumen-fila ${f.color} ${f.grande ? "grande" : ""}`}>
                <span className="franja" />
                <span className="titulo">{f.titulo}</span>
                {f.cuenta && <span className="cuenta">{f.cuenta(resumen)}</span>}
                <span className="importe">{dinero(f.total(resumen))} CUP</span>
              </div>
            ))}
            <div className="resumen-fila divisas">
              <span className="franja" />
              <span className="titulo">Divisas en Caja</span>
              <span className="importe">
                USD: {dinero(divisas.USD)} | EUR: {dinero(divisas.EUR)}
              </span>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
