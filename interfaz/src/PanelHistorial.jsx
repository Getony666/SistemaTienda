import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { api, enviar } from "./api";
import DialogoDeuda from "./DialogoDeuda";

const TIPOS = [
  ["todos", "Todos"], ["ventas", "Ventas"], ["deudas", "Deudas"],
  ["mensajeria", "Mensajería"],
  ["cambio", "Cambio de Divisa"], ["entrada_efectivo", "Entrada de Efectivo"],
  ["salida_efectivo", "Salida de Efectivo"], ["salidas", "Salidas"],
  ["merma", "Merma"], ["entrada_producto", "Entrada de Producto"],
];

const METODOS = [
  ["todos", "Todos"], ["efectivo", "Efectivo"],
  ["transferencia", "Transferencia"], ["mixto", "Mixto"],
];

// Cuántos registros se piden de golpe. El historial de una tienda con meses
// de trabajo son miles de líneas, y nadie mira más allá de las primeras.
const TANDA = 50;

const DIAS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
               "agosto", "septiembre", "octubre", "noviembre", "diciembre"];

// El dinero se lee en grupos de tres: 12 500.00, no 12500.00. El espacio fino
// no se confunde con un separador decimal, que aquí es el punto.
const plata = (n) =>
  Number(n ?? 0).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, " ");

// Cada tipo tiene su color, para reconocerlo de un vistazo sin leerlo.
const PASTILLA = {
  "Venta": ["t-venta", "Venta"],
  "Deuda": ["t-deuda", "Deuda"],
  "Entrada de efectivo": ["t-caja", "Entrada caja"],
  "Salida de efectivo": ["t-caja", "Salida caja"],
  "Cambio de Divisa": ["t-divisa", "Divisa"],
  "Merma": ["t-merma", "Merma"],
  "Salida de Producto": ["t-merma", "Salida"],
  "Entrada de Producto": ["t-ficha", "Alta"],
  "Actualización de Producto": ["t-ficha", "Ficha"],
  "Eliminación de Producto": ["t-ficha", "Baja"],
};

const pastillaDe = (tipo) => PASTILLA[tipo] || ["t-ficha", tipo];

const soloFecha = (f) => (f || "").slice(0, 10);
const soloHora = (f) => (f || "").slice(11, 16);

/** "Hoy — jueves 10 de septiembre". Los días recientes por su nombre, que es
 *  como los llama quien está detrás del mostrador. */
function tituloDelDia(iso) {
  if (!iso) return "Sin fecha";
  const [a, m, d] = iso.split("-").map(Number);
  const fecha = new Date(a, m - 1, d);
  const hoy = new Date();
  hoy.setHours(0, 0, 0, 0);
  const dias = Math.round((hoy - fecha) / 86400000);
  const largo = `${DIAS[fecha.getDay()]} ${d} de ${MESES[m - 1]}`;
  if (dias === 0) return `Hoy — ${largo}`;
  if (dias === 1) return `Ayer — ${largo}`;
  return largo.charAt(0).toUpperCase() + largo.slice(1);
}

/** Lo que entró y lo que salió ese día, contando sólo lo que hay cargado. */
function resumenDelDia(registros) {
  let entro = 0, salio = 0;
  for (const r of registros) {
    if (r.moneda !== "CUP" || r.tipo === "Deuda") continue;
    if (r.signo === "entra") entro += r.monto || 0;
    else if (r.signo === "sale") salio += r.monto || 0;
  }
  const partes = [`${registros.length} movimiento${registros.length === 1 ? "" : "s"}`];
  if (entro) partes.push(`entró ${plata(entro)}`);
  if (salio) partes.push(`salió ${plata(salio)}`);
  return partes.join(" · ");
}

const COLUMNAS = [
  ["fecha", "Hora"], ["tipo", "Tipo"], ["concepto", "Concepto"],
  ["monto", "Monto"], ["metodo_pago", "Método"], ["usuario", "Usuario"],
];

export default function PanelHistorial({ puede }) {
  const [registros, setRegistros] = useState([]);
  const [resumen, setResumen] = useState(null);
  const [fecha, setFecha] = useState("");
  const [tipo, setTipo] = useState("todos");
  const [metodo, setMetodo] = useState("todos");
  const [producto, setProducto] = useState("");
  const [productos, setProductos] = useState([]);
  const [quien, setQuien] = useState("");
  const [tecleado, setTecleado] = useState("");
  const [buscado, setBuscado] = useState("");
  const [cuantos, setCuantos] = useState(TANDA);
  const [hayMas, setHayMas] = useState(false);
  const [orden, setOrden] = useState({ columna: "fecha", ascendente: false });
  const [elegido, setElegido] = useState(null);
  const [detalle, setDetalle] = useState(null);
  const [aviso, setAviso] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [cobrando, setCobrando] = useState(null);

  // Se espera a que deje de teclear: si no, cada letra dispara una consulta.
  useEffect(() => {
    const reloj = setTimeout(() => setBuscado(tecleado.trim()), 300);
    return () => clearTimeout(reloj);
  }, [tecleado]);

  const parametros = useCallback((extra = {}) => {
    const p = new URLSearchParams({ tipo, metodo, ...extra });
    if (fecha) p.set("fecha", fecha);
    if (producto) p.set("producto_id", producto);
    if (buscado) p.set("buscar", buscado);
    if (quien) p.set("usuario", quien);
    return p;
  }, [fecha, tipo, metodo, producto, buscado, quien]);

  const cargar = useCallback(async () => {
    setCargando(true);
    setAviso(null);
    try {
      // Se pide uno de más que los que se van a enseñar: si viene, es que
      // queda historial por detrás y hay que ofrecer el botón.
      const lista = await api(`/ventas?${parametros({ limite: cuantos + 1 })}`);
      setHayMas(lista.length > cuantos);
      setRegistros(lista.slice(0, cuantos));
      setElegido(null);
      setDetalle(null);
      setResumen(await api(`/historial/resumen?${parametros()}`));
    } catch (e) {
      setAviso({ tipo: "error", texto: e.message });
    } finally {
      setCargando(false);
    }
  }, [parametros, cuantos]);

  useEffect(() => { cargar(); }, [cargar]);

  // Cambiar un filtro devuelve la lista al principio: seguir en la página
  // cuatro de una búsqueda que ya no existe no le sirve a nadie.
  useEffect(() => { setCuantos(TANDA); },
            [fecha, tipo, metodo, producto, buscado, quien]);

  // La lista del desplegable de productos se pide una sola vez.
  useEffect(() => {
    api("/productos").then(setProductos).catch(() => setProductos([]));
  }, []);

  // El detalle se pide de uno en uno, al seleccionar: así la lista no carga
  // con las líneas de todas las ventas que nadie va a abrir.
  useEffect(() => {
    if (!elegido) { setDetalle(null); return; }
    let vigente = true;
    api(`/historial/detalle?tipo=${encodeURIComponent(elegido.tipo)}&id=${elegido.id}`)
      .then((d) => { if (vigente) setDetalle(d); })
      .catch(() => { if (vigente) setDetalle(null); });
    return () => { vigente = false; };
  }, [elegido]);

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

  function ordenarPor(columna) {
    setOrden((antes) => antes.columna === columna
      ? { columna, ascendente: !antes.ascendente }
      : { columna, ascendente: columna !== "fecha" && columna !== "monto" });
  }

  // Se ordena lo que hay cargado. Para la fecha da igual -el servidor ya lo
  // manda de lo nuevo a lo viejo-, pero ordenar por monto o por usuario sólo
  // alcanza a la tanda que se está viendo, y eso es lo honesto: no se puede
  // ordenar por monto lo que todavía no se ha pedido.
  const ordenados = useMemo(() => {
    const lista = [...registros];
    const { columna, ascendente } = orden;
    lista.sort((a, b) => {
      const x = a[columna] ?? "", y = b[columna] ?? "";
      const cmp = typeof x === "number" && typeof y === "number"
        ? x - y
        : String(x).localeCompare(String(y), "es");
      return ascendente ? cmp : -cmp;
    });
    return lista;
  }, [registros, orden]);

  // Los separadores de día sólo tienen sentido con la lista en orden de
  // fecha; ordenada por monto, agrupar por día no diría nada.
  const porDias = useMemo(() => {
    if (orden.columna !== "fecha") return [{ dia: null, filas: ordenados }];
    const grupos = [];
    for (const r of ordenados) {
      const dia = soloFecha(r.fecha);
      if (!grupos.length || grupos[grupos.length - 1].dia !== dia) {
        grupos.push({ dia, filas: [] });
      }
      grupos[grupos.length - 1].filas.push(r);
    }
    return grupos;
  }, [ordenados, orden.columna]);

  function pintarMonto(r) {
    if (r.tipo === "Deuda") {
      return <span className="plata deuda-monto">{plata(r.monto)}
        <span className="mon">{r.moneda}</span></span>;
    }
    if (r.signo === "neutro" || !r.monto) {
      return <span className="neutro">—</span>;
    }
    const sale = r.signo === "sale";
    return (
      <span className={`plata ${sale ? "sale" : "entra"}`}>
        {sale ? "−" : "+"}{plata(r.monto)}
        <span className="mon">{r.moneda}</span>
      </span>
    );
  }

  function pintarFila(r, i) {
    const [clase, texto] = pastillaDe(r.tipo);
    const avance = r.total_deuda ? (r.abonado || 0) / r.total_deuda * 100 : 0;
    return (
      <tr key={`${r.tipo}-${r.id}-${i}`}
          tabIndex={0}
          aria-selected={elegido === r}
          className={esDeudaPendiente(r) ? "deuda" : undefined}
          onClick={() => setElegido(r)}
          onFocus={() => setElegido(r)}>
        <td className="hora">{soloHora(r.fecha)}</td>
        <td>
          <span className={`tag ${clase}`}>{texto}</span>
          {r.es_mensajeria === 1 && <span className="moto" title="Mensajería">🛵</span>}
        </td>
        <td className="concepto">
          <span className="concepto-t" title={r.concepto}>{r.concepto || "—"}</span>
          {r.subconcepto && <small title={r.subconcepto}>{r.subconcepto}</small>}
          {r.tipo === "Deuda" && r.total_deuda > 0 && (
            <div className="barra" title={`Abonado ${plata(r.abonado || 0)} de ${plata(r.total_deuda)}`}>
              <i style={{ width: `${Math.min(100, avance)}%` }} />
            </div>
          )}
        </td>
        <td className="derecha">{pintarMonto(r)}</td>
        <td>{r.metodo_pago || <span className="neutro">—</span>}</td>
        {/* Lo anterior a los usuarios no lleva nombre: raya, no vacío. */}
        <td className="quien">{r.usuario || "—"}</td>
      </tr>
    );
  }

  return (
    <div className="cuerpo una-columna historial">
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
        <div className="fila" style={{ marginBottom: 9 }}>
          <input className="buscador" type="search"
                 placeholder="Buscar cliente, producto u observación…"
                 value={tecleado} onChange={(e) => setTecleado(e.target.value)} />
          <label htmlFor="fecha">Fecha</label>
          <input id="fecha" type="date" value={fecha}
                 onChange={(e) => setFecha(e.target.value)} />
          <button className="boton fantasma" onClick={() => setFecha("")}>Todas</button>
          <button className="boton" onClick={cargar}>Refrescar</button>
          {puede("cobrar_deudas") && (
            <button className="boton naranja" onClick={() => setCobrando(elegido)}
                    disabled={!elegido || !esDeudaPendiente(elegido)}>Pagar deuda</button>
          )}
          {puede("eliminar_historial") && (
            <button className="boton rojo" onClick={revertir}
                    disabled={!elegido}>Eliminar del historial</button>
          )}
        </div>

        <div className="fila">
          <label>Tipo</label>
          <select value={tipo} onChange={(e) => setTipo(e.target.value)}>
            {TIPOS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
          </select>
          <label style={{ marginLeft: 10 }}>Método de pago</label>
          <select value={metodo} onChange={(e) => setMetodo(e.target.value)}>
            {METODOS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
          </select>
          <label style={{ marginLeft: 10 }}>Producto</label>
          <select value={producto} onChange={(e) => setProducto(e.target.value)}
                  style={{ maxWidth: 200 }}>
            <option value="">Todos</option>
            {productos.map((p) => (
              <option key={p.id} value={p.id}>{p.nombre}</option>
            ))}
          </select>
          <label style={{ marginLeft: 10 }}>Usuario</label>
          <select value={quien} onChange={(e) => setQuien(e.target.value)}>
            <option value="">Todos</option>
            {(resumen?.usuarios ?? []).map((nombre) => (
              <option key={nombre} value={nombre}>{nombre}</option>
            ))}
          </select>
          {producto && (
            <button className="boton fantasma" onClick={() => setProducto("")}>
              Quitar producto
            </button>
          )}
        </div>

        {producto && (
          <p className="nota-filtro">
            Filtrando por producto: se muestran sus ventas, deudas, mermas,
            salidas y altas o cambios de ficha. Los movimientos de caja y los
            cambios de divisa no salen, porque no llevan producto.
          </p>
        )}

        {aviso && <div className={`aviso ${aviso.tipo}`}>{aviso.texto}</div>}
      </section>

      {resumen && (
        <div className="resumen-historial">
          <div><div className="et">Registros</div><div className="ci">{resumen.registros}</div></div>
          <div><div className="et">Entró</div>
               <div className="ci entra">{plata(resumen.entro)}<span className="mon">CUP</span></div></div>
          <div><div className="et">Salió</div>
               <div className="ci sale">{plata(resumen.salio)}<span className="mon">CUP</span></div></div>
          <div><div className="et">Por cobrar</div>
               <div className="ci debe">{plata(resumen.por_cobrar)}<span className="mon">CUP</span></div></div>
          <div><div className="et">Ganancia</div>
               <div className="ci">{plata(resumen.ganancia)}<span className="mon">CUP</span></div></div>
          {Object.entries(resumen.divisas || {}).map(([moneda, cantidad]) => (
            <div key={moneda}><div className="et">{moneda}</div>
              <div className="ci">{plata(cantidad)}<span className="mon">{moneda}</span></div></div>
          ))}
        </div>
      )}

      <div className="panel-historial">
        <section className="tarjeta lista">
          <h2>Registros</h2>
          <div className="desplazable alto">
            {cargando ? (
              <p className="vacio">Cargando…</p>
            ) : registros.length === 0 ? (
              <p className="vacio">No hay registros con esos filtros</p>
            ) : (
              <table className="tabla historial">
                <thead>
                  <tr>
                    {COLUMNAS.map(([clave, titulo]) => (
                      <th key={clave} className={`col-${clave}`}
                          onClick={() => ordenarPor(clave)}
                          title="Pulsa para ordenar">
                        {titulo}
                        {orden.columna === clave && (
                          <span className="flecha">{orden.ascendente ? "▲" : "▼"}</span>
                        )}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {porDias.map((grupo) => (
                    <Fragment key={grupo.dia ?? "todo"}>
                      {grupo.dia && (
                        <tr className="dia">
                          <td colSpan={COLUMNAS.length}>
                            <span className="dia-t">{tituloDelDia(grupo.dia)}</span>
                            <span className="dia-s">{resumenDelDia(grupo.filas)}</span>
                          </td>
                        </tr>
                      )}
                      {grupo.filas.map(pintarFila)}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          {registros.length > 0 && (
            <div className="pie-historial">
              <span>
                Mostrando {registros.length}
                {resumen ? ` de ${resumen.registros}` : ""}
                {orden.columna === "fecha" && !orden.ascendente
                  ? " · las más recientes primero" : ""}
              </span>
              {hayMas && (
                <button className="boton fantasma"
                        onClick={() => setCuantos((n) => n + TANDA)}>
                  Ver {TANDA} más
                </button>
              )}
            </div>
          )}
        </section>

        <section className="tarjeta detalle">
          <h2>Detalle</h2>
          {!elegido ? (
            <p className="vacio">Selecciona un registro para ver su detalle</p>
          ) : !detalle ? (
            <p className="vacio">Cargando…</p>
          ) : (
            <>
              <h3>{detalle.titulo}</h3>
              <p className="sub">{detalle.subtitulo}</p>
              {detalle.secciones.map((seccion) => (
                <div key={seccion.nombre}>
                  <h4>{seccion.nombre}</h4>
                  {seccion.tipo === "lineas" ? (
                    <table className="tabla lineas">
                      <tbody>
                        {seccion.filas.map((f, i) => (
                          <tr key={i} className={f.fuerte ? "fuerte" : undefined}>
                            <td>{f.texto}</td>
                            <td className="derecha">{f.medio}</td>
                            <td className="derecha">{f.derecha}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    seccion.filas.map((f, i) => (
                      <div className="par" key={i}>
                        <span>{f.texto}</span>
                        <span className={f.color ? `v-${f.color}` : undefined}>{f.derecha}</span>
                      </div>
                    ))
                  )}
                </div>
              ))}
            </>
          )}
        </section>
      </div>
    </div>
  );
}
