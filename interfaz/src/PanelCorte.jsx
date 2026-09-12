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

const DIAS = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];
const MESES = ["ene", "feb", "mar", "abr", "may", "jun",
               "jul", "ago", "sep", "oct", "nov", "dic"];

// "2026-09-11" -> "jue 11 sep". Se parte la cadena en vez de pasarla por
// new Date(), que la leería como UTC y devolvería el día de antes.
const comoDiaCorto = (f) => {
  const [a, m, d] = (f || "").split("-").map(Number);
  if (!a) return f;
  const fecha = new Date(a, m - 1, d);
  return `${DIAS[fecha.getDay()]} ${String(d).padStart(2, "0")} ${MESES[m - 1]}`;
};

// Las cifras del cuadre son las más grandes de la pantalla y las que se leen
// de un vistazo; con miles de CUP, sin separador cuesta ver el orden de
// magnitud. El punto decimal se queda como en el resto del programa.
const conMiles = (n) => {
  const texto = dinero(n);
  const negativo = texto.startsWith("-");
  const [entero, decimales] = (negativo ? texto.slice(1) : texto).split(".");
  const agrupado = entero.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  return `${negativo ? "−" : ""}${agrupado}.${decimales}`;
};

const MONEDAS = ["CUP", "USD", "EUR"];
const CONTADO_VACIO = { CUP: "", USD: "", EUR: "" };

const vacioEfectivo = { moneda: "CUP", monto: "", descripcion: "" };

// El día en cifras: lo que NO es dinero en la gaveta. Va aparte del cuadre a
// propósito -antes estaba mezclado con el efectivo, en la misma lista y con
// la misma pinta, y se leía como si sumara-.
const CIFRAS_DEL_DIA = [
  { clave: "ventas", color: "verde", titulo: "Ventas del día",
    total: (r) => r.total_ventas_dia,
    cuenta: (r) => `${r.ventas_efectivo.cantidad + r.ventas_transferencia.cantidad}` },
  { clave: "ganancia", color: "naranja", titulo: "Ganancia del día",
    total: (r) => r.utilidad_total },
  { clave: "transferencia", color: "morado", titulo: "Cobrado por transferencia",
    total: (r) => r.ventas_transferencia.total,
    cuenta: (r) => `${r.ventas_transferencia.cantidad}` },
  // Deudas y salidas de inventario van separadas: hasta ahora se sumaban en
  // una sola fila llamada "Deudas Pendientes del Día", y una salida de
  // mercancía no es dinero que nadie deba.
  { clave: "deudas", color: "ocre", titulo: "Deudas nuevas sin cobrar",
    total: (r) => r.deudas_pendientes_netas.total,
    cuenta: (r) => `${r.deudas_pendientes_netas.cantidad}` },
  { clave: "salidas", color: "suave", titulo: "Salidas de inventario pendientes",
    total: (r) => r.salidas_pendientes.total,
    cuenta: (r) => `${r.salidas_pendientes.cantidad}` },
];

export default function PanelCorte({ puede }) {
  const [fecha, setFecha] = useState(hoy());
  const [resumen, setResumen] = useState(null);
  const [movimientos, setMovimientos] = useState([]);
  const [cierres, setCierres] = useState([]);
  const [fondo, setFondo] = useState("");
  const [aviso, setAviso] = useState(null);

  const [contado, setContado] = useState(CONTADO_VACIO);
  const [moneda, setMoneda] = useState("CUP");
  const [cerrando, setCerrando] = useState(false);

  // Entrada y Salida de Efectivo viven aquí: son movimientos de caja, y el
  // corte es lo primero que cambia cuando se registra uno.
  const [abiertoEfectivo, setAbiertoEfectivo] = useState(null);
  const [camposEfectivo, setCamposEfectivo] = useState(vacioEfectivo);
  const [avisoEfectivo, setAvisoEfectivo] = useState(null);
  const [guardandoEfectivo, setGuardandoEfectivo] = useState(false);

  const cargarCierres = useCallback(async () => {
    try {
      setCierres(await api("/caja/cierres?limite=8"));
    } catch {
      setCierres([]);
    }
  }, []);

  const cargar = useCallback(async (f) => {
    setAviso(null);
    try {
      const r = await api(`/corte/${f}`);
      setResumen(r);
      setFondo(String(r.fondo_registrado ?? 0));
      // Si el día ya está cerrado, lo contado es lo que quedó guardado esa
      // noche; si no, los tres campos salen en blanco para que nadie tome
      // por contado un número que no ha contado nadie.
      setContado(r.cierre
        ? Object.fromEntries(MONEDAS.map((m) => [m, dinero(r.cierre.contado[m])]))
        : CONTADO_VACIO);
    } catch (e) {
      setResumen(null);
      setContado(CONTADO_VACIO);
      setAviso({ tipo: "error", texto: e.message });
    }
    try {
      setMovimientos(await api(`/caja/movimientos/${f}`));
    } catch {
      setMovimientos([]);
    }
  }, []);

  useEffect(() => { cargar(fecha); }, [cargar, fecha]);
  useEffect(() => { cargarCierres(); }, [cargarCierres]);

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

  const cuadre = resumen?.cuadre ?? {};
  const cierre = resumen?.cierre ?? null;

  const esperadoDe = (m) => Number(cuadre[m]?.esperado ?? 0);
  const contadoDe = (m) => (contado[m].trim() === "" ? null : Number(contado[m]) || 0);
  const diferenciaDe = (m) => {
    const c = contadoDe(m);
    return c === null ? null : Number((c - esperadoDe(m)).toFixed(2));
  };

  // Una moneda que no se movió en todo el día y nadie contó no es un
  // descuadre: sencillamente no había nada que contar. Las que sí tuvieron
  // movimiento hay que contarlas antes de poder cerrar.
  const sinContar = MONEDAS.filter(
    (m) => contadoDe(m) === null && esperadoDe(m) !== 0);

  async function cerrarElDia() {
    setAviso(null);
    if (sinContar.length) {
      setAviso({ tipo: "error",
                 texto: `Falta contar: ${sinContar.join(", ")}` });
      return;
    }
    setCerrando(true);
    try {
      const r = await enviar(`/caja/cierres/${fecha}`, {
        CUP: contadoDe("CUP") ?? 0,
        USD: contadoDe("USD") ?? 0,
        EUR: contadoDe("EUR") ?? 0,
      });
      setAviso({ tipo: "bien", texto: r?.mensaje ?? "Caja cerrada" });
      cargar(fecha);
      cargarCierres();
    } catch (e) {
      setAviso({ tipo: "error", texto: e.message });
    } finally {
      setCerrando(false);
    }
  }

  async function reabrirElDia() {
    setAviso(null);
    try {
      const r = await enviar(`/caja/cierres/${fecha}`, null, "DELETE");
      setAviso({ tipo: "bien", texto: r?.mensaje ?? "Caja reabierta" });
      cargar(fecha);
      cargarCierres();
    } catch (e) {
      setAviso({ tipo: "error", texto: e.message });
    }
  }

  const cadena = cuadre[moneda]?.cadena ?? [];
  const esNuevoElFondo = fecha === hoy() && !Number(resumen?.fondo_registrado);

  return (
    <div className="cuerpo corte">
      <div className="columna">

        {/* ------------------------------------------------ el cuadre */}
        <section className="tarjeta">
          <div className="cabecera-tarjeta">
            <h2>Corte del día</h2>
            <div className="fila no-imprimir">
              {cierre
                ? <span className="estado-caja cerrada">
                    Cerrada {cierre.hora}{cierre.usuario ? ` · ${cierre.usuario}` : ""}
                  </span>
                : <span className="estado-caja abierta">● Caja abierta</span>}
              <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
              <button className="boton fantasma" onClick={() => setFecha(ayer())}>Ayer</button>
              <button className="boton fantasma" onClick={() => setFecha(hoy())}>Hoy</button>
              <button className="boton" onClick={() => cargar(fecha)}>Actualizar</button>
            </div>
          </div>

          {/* Sólo se ve al imprimir: en papel no hay pestaña que diga de qué
              día es la hoja. */}
          <p className="solo-imprimir">
            Corte de caja del {comoDiaCorto(fecha)} ({fecha})
            {cierre ? ` · cerrado a las ${cierre.hora} por ${cierre.usuario}` : ""}
          </p>

          {/* El aviso vive aquí, fuera del bloque del fondo: si estuviera
              dentro, quien no pueda fijar el fondo no vería los errores de
              carga, que no tienen nada que ver con el permiso. */}
          {aviso && <div className={`aviso ${aviso.tipo}`}>{aviso.texto}</div>}

          {!resumen ? (
            <p className="vacio">Sin datos para esa fecha</p>
          ) : (
            <>
              <div className="cuadre">
                <div className="cuadre-cab">
                  <span>Moneda</span>
                  <span className="n">Debería haber</span>
                  <span className="n">Contado</span>
                  <span className="n">Diferencia</span>
                </div>

                {MONEDAS.map((m) => {
                  const dif = diferenciaDe(m);
                  const estado = dif === null ? "sincontar"
                    : Math.abs(dif) < 0.005 ? "cuadra"
                    : dif < 0 ? "falta" : "sobra";
                  return (
                    <div key={m}
                         className={`cuadre-fila ${m === "CUP" ? "" : "chica"} ${estado === "falta" ? "en-rojo" : ""}`}>
                      <button type="button"
                              className={`cuadre-moneda ${moneda === m ? "activa" : ""}`}
                              onClick={() => setMoneda(m)}
                              title={`Ver de dónde sale el ${m}`}>
                        {m}
                      </button>
                      <div className="cel esperado">
                        <span className="cifra">{conMiles(esperadoDe(m))}</span>
                      </div>
                      <div className="cel">
                        <input className="contado numero" inputMode="decimal"
                               placeholder="—" value={contado[m]}
                               aria-label={`Contado en ${m}`}
                               onChange={(e) =>
                                 setContado((c) => ({ ...c, [m]: e.target.value }))} />
                      </div>
                      <div className="cel">
                        {dif === null ? (
                          <span className="diferencia sincontar">sin contar todavía</span>
                        ) : (
                          <>
                            <span className={`diferencia ${estado}`}>
                              {dif > 0 ? "+" : ""}{conMiles(dif)}
                            </span>
                            <span className="pie-diferencia">
                              {estado === "cuadra" ? "cuadra"
                                : estado === "falta" ? "falta dinero" : "sobra dinero"}
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Cerrar no traba nada: si después de contar entra un cliente,
                  el apunte se registra igual y aquí sale el aviso. */}
              {cierre && cierre.movimientos_despues > 0 && (
                <div className="aviso ojo">
                  La caja se cerró a las {cierre.hora} y después hubo{" "}
                  {cierre.movimientos_despues}{" "}
                  {cierre.movimientos_despues === 1 ? "movimiento" : "movimientos"}.
                  Conviene reabrir y volver a contar.
                </div>
              )}

              <div className="acciones-corte no-imprimir">
                {puede("cerrar_caja") && (cierre ? (
                  <button className="boton grande ocre" onClick={reabrirElDia}>
                    Reabrir y volver a contar
                  </button>
                ) : (
                  <button className="boton grande morado" onClick={cerrarElDia}
                          disabled={cerrando}>
                    {cerrando ? "Cerrando…" : "Cerrar la caja del día"}
                  </button>
                ))}
                <button className="boton fantasma" onClick={() => window.print()}>
                  Imprimir el corte
                </button>
                <span className="apunte">
                  {cierre
                    ? "Reabrir borra la foto de esa noche para poder contar otra vez."
                    : "Al cerrar se guardan las tres monedas, la diferencia, quién cerró y a qué hora. Mañana todo arranca en cero."}
                </span>
              </div>
            </>
          )}
        </section>

        {/* ------------------------------------------------- la cadena */}
        <section className="tarjeta">
          <div className="cabecera-tarjeta">
            <h2>De dónde sale esa cifra</h2>
            <div className="pastillas no-imprimir">
              {MONEDAS.map((m) => (
                <button key={m} className="pastilla moneda"
                        aria-pressed={moneda === m}
                        onClick={() => setMoneda(m)}>
                  {m}
                </button>
              ))}
            </div>
          </div>

          {!cadena.length ? (
            <p className="vacio">Ese día no hubo movimiento en {moneda}</p>
          ) : (
            <div className="cadena">
              {cadena.map((linea) => (
                <div key={linea.clave}
                     className={`cadena-linea ${linea.signo === "+" ? "mas"
                                 : linea.signo === "-" ? "menos" : "base"}`}>
                  <span className="signo">{linea.signo || " "}</span>
                  <span className="titulo">{linea.titulo}</span>
                  {linea.cuenta && <span className="cuenta">· {linea.cuenta}</span>}
                  <span className="importe">{conMiles(linea.monto)}</span>
                </div>
              ))}
              <div className="cadena-linea suma">
                <span className="signo">=</span>
                <span className="titulo">Debería haber en {moneda}</span>
                <span className="importe">{conMiles(esperadoDe(moneda))}</span>
              </div>
            </div>
          )}
        </section>

        {/* -------------------------------------------- movimientos */}
        <section className="tarjeta">
          <div className="cabecera-tarjeta">
            <h2>Movimientos de efectivo del día</h2>
            <div className="fila no-imprimir">
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
            <div className="formulario verde-tenue no-imprimir">
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

          {!movimientos.length ? (
            <p className="vacio">Ningún movimiento de efectivo ese día</p>
          ) : (
            <table className="tabla movimientos">
              <thead>
                <tr>
                  <th>Hora</th><th>Tipo</th><th>Concepto</th>
                  <th className="derecha">Monto</th><th>Quién</th>
                </tr>
              </thead>
              <tbody>
                {movimientos.map((m) => (
                  <tr key={`${m.tipo}-${m.id}`}>
                    <td>{(m.fecha || "").slice(11, 16)}</td>
                    <td>
                      <span className={`etiqueta-tipo ${claseDeTipo(m.tipo)}`}
                            title={m.tipo}>
                        {etiquetaCorta(m.tipo)}
                      </span>
                    </td>
                    <td title={m.concepto}>{m.concepto}</td>
                    <td className="derecha">
                      <span className={m.monto < 0 ? "sale" : "entra"}>
                        {m.monto > 0 ? "+" : ""}{conMiles(m.monto)} {m.moneda}
                      </span>
                      {/* Un cambio de divisa mueve dos monedas a la vez: las
                          dos van en la misma línea, no en dos apuntes. */}
                      {m.moneda_2 && (
                        <span className={`segunda ${m.monto_2 < 0 ? "sale" : "entra"}`}>
                          {m.monto_2 > 0 ? "+" : ""}{conMiles(m.monto_2)} {m.moneda_2}
                        </span>
                      )}
                    </td>
                    <td>{m.usuario}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>

      {/* ================================================== derecha */}
      <div className="columna">

        {/* El fondo es dinero que se declara: quien no pueda fijarlo no ve
            ni el formulario. La API lo impide igual, esto es por comodidad. */}
        {puede("fondo_caja") && (
        <section className="tarjeta no-imprimir">
          <h2>Fondo de caja de {fecha === hoy() ? "hoy" : comoDiaCorto(fecha)}</h2>
          {esNuevoElFondo && (
            <div className="aviso ojo">Todavía no se ha puesto el fondo de hoy.</div>
          )}
          <div className="fila">
            <input id="fondo" className="numero" style={{ width: 130 }}
                   value={fondo} onChange={(e) => setFondo(e.target.value)} />
            <span className="unidad">CUP</span>
            <button className="boton morado" onClick={guardarFondo}>Guardar</button>
            <button className="boton fantasma" onClick={() => setFondo("0")}>Limpiar</button>
          </div>
          <p className="nota-form">
            Se teclea cada mañana. No se arrastra del día anterior: la gaveta
            se vacía todas las noches.
          </p>
        </section>
        )}

        <section className="tarjeta">
          <h2>El día en cifras <span className="acotacion">— no es dinero en la gaveta</span></h2>
          {!resumen ? (
            <p className="vacio">Sin datos para esa fecha</p>
          ) : (
            <div className="cifras-dia">
              {CIFRAS_DEL_DIA.map((c) => (
                <div key={c.clave} className={`cifra-fila ${c.color}`}>
                  <span className="punta" />
                  <span className="titulo">{c.titulo}</span>
                  {c.cuenta && <span className="cuenta">· {c.cuenta(resumen)}</span>}
                  <span className="importe">{conMiles(c.total(resumen))}</span>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* En papel no pinta nada la lista de otros días: la hoja es del día
            que se está cerrando. */}
        <section className="tarjeta no-imprimir">
          <h2>Últimos cierres</h2>
          {!cierres.length ? (
            <p className="vacio">Todavía no se ha cerrado ningún día</p>
          ) : (
            <div className="lista-cierres">
              {cierres.map((c) => {
                const dif = c.diferencia.CUP;
                const cuadro = Math.abs(dif) < 0.005;
                return (
                  <button key={c.fecha} className="cierre"
                          onClick={() => setFecha(c.fecha)}
                          aria-current={c.fecha === fecha ? "true" : undefined}>
                    <span className="dia">{comoDiaCorto(c.fecha)}</span>
                    <span className="quien">
                      cerró {c.usuario || "alguien"} · {c.hora}
                    </span>
                    <span className={`dif ${cuadro ? "cuadra" : dif < 0 ? "falta" : "sobra"}`}>
                      {cuadro ? "cuadró" : `${dif > 0 ? "+" : ""}${conMiles(dif)}`}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
          <p className="nota-form">
            Cada día queda guardado entero. Al pulsar uno, el corte de arriba
            muestra ese día.
          </p>
        </section>
      </div>
    </div>
  );
}

function claseDeTipo(tipo) {
  if (tipo === "Entrada") return "entrada";
  if (tipo === "Salida") return "salida";
  return "cambio";
}

// En la pastilla no cabe "Compra de divisa" sin recortarse, y el concepto de
// al lado ya dice de qué divisa se trata. El texto entero queda en el título.
function etiquetaCorta(tipo) {
  return tipo.replace(" de divisa", "");
}
