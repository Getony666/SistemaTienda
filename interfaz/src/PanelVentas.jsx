import { useEffect, useMemo, useRef, useState } from "react";
import { dinero, cantidad as fmtCantidad, enviar } from "./api";
import PanelAcciones from "./PanelAcciones";

// Los billetes que se ven en la calle. Sirven para armar el vuelto en divisa
// sin teclear: la cajera va sumando los que tiene a mano.
const DENOMINACIONES = [1, 5, 10, 20, 50, 100];

// El carrito se llena igual siempre; lo que cambia es qué se hace con él.
const MODOS = {
  venta: {
    precio: (l) => l.precio,
    boton: "Finalizar venta",
    apunte: "",
  },
  salida: {
    precio: (l) => l.costo,
    boton: "Registrar salida",
    apunte: "a precio de costo",
    aviso: "Salida de inventario. Todo el carrito se valora a precio de costo y se " +
           "descuenta del almacén. Genera la deuda del trabajador. No se cobra al cliente.",
    motivoPorDefecto: "Salida a trabajador",
  },
  merma: {
    precio: () => 0,
    boton: "Registrar merma",
    apunte: "sin cobro",
    aviso: "Merma. El carrito se descuenta del almacén sin cobrar nada. " +
           "Ni caja, ni deuda, ni vuelto: sólo baja el inventario.",
    motivoPorDefecto: "Merma",
  },
};

export default function PanelVentas({ productos, recargarProductos, puede }) {
  const [busqueda, setBusqueda] = useState("");
  const [marcado, setMarcado] = useState(0);
  const [carrito, setCarrito] = useState([]);

  const [modo, setModo] = useState("venta");
  const [motivo, setMotivo] = useState("");

  const [soloTransferencia, setSoloTransferencia] = useState(false);
  const [mensajeria, setMensajeria] = useState(false);
  const [deuda, setDeuda] = useState(false);
  const [observaciones, setObservaciones] = useState("");

  const [moneda, setMoneda] = useState("CUP");
  const [tasa, setTasa] = useState("1.00");
  const [efectivo, setEfectivo] = useState("");
  const [transferencia, setTransferencia] = useState("");

  // Pagando en divisa, el CUP que se pone encima para llegar al total, y la
  // parte del cambio que se devuelve en la propia divisa.
  const [cupEfectivo, setCupEfectivo] = useState("");
  const [cupTransferencia, setCupTransferencia] = useState("");
  const [vueltoMoneda, setVueltoMoneda] = useState("");

  const [vuelto, setVuelto] = useState(null);
  const [aviso, setAviso] = useState(null);
  const [guardando, setGuardando] = useState(false);

  const campoBusqueda = useRef(null);
  const filasRef = useRef([]);

  const esVenta = modo === "venta";
  const reglas = MODOS[modo];

  const precioDe = (linea) => reglas.precio(linea);
  const total = useMemo(
    () => carrito.reduce((s, l) => s + l.cantidad * precioDe(l), 0),
    [carrito, modo]
  );

  const resultados = useMemo(() => {
    const texto = busqueda.trim().toLowerCase();
    const lista = texto
      ? productos.filter((p) => p.nombre.toLowerCase().includes(texto))
      : productos;
    return lista.slice(0, 60);
  }, [productos, busqueda]);

  useEffect(() => { campoBusqueda.current?.focus(); }, []);
  useEffect(() => { setMarcado(0); }, [busqueda]);

  // Salida y merma no se cobran: al marcarlas se apaga todo lo del pago.
  const cambiarModo = (nuevo) => {
    const destino = modo === nuevo ? "venta" : nuevo;
    setModo(destino);
    setMotivo(destino === "venta" ? "" : MODOS[destino].motivoPorDefecto);
    if (destino !== "venta") {
      setSoloTransferencia(false); setMensajeria(false); setDeuda(false);
      setEfectivo(""); setTransferencia(""); setMoneda("CUP"); setTasa("1.00");
      setVuelto(null);
    }
    setAviso(null);
  };

  const marcarPago = (poner) => {
    if (!esVenta) return;
    poner();
  };

  // Lo que se manda a cobrar. Un solo sitio, para que la simulación del
  // vuelto y la venta que se guarda no puedan discrepar.
  const datosDelPago = () => ({
    total_cup: total,
    moneda,
    tasa: Number(tasa) || 0,
    efectivo: Number(efectivo) || 0,
    transferencia: Number(transferencia) || 0,
    cup_efectivo: Number(cupEfectivo) || 0,
    cup_transferencia: Number(cupTransferencia) || 0,
    vuelto_en_moneda: Number(vueltoMoneda) || 0,
    solo_transferencia: soloTransferencia,
  });

  // El vuelto se lo pedimos a la misma función que usa la caja de tkinter.
  useEffect(() => {
    if (!esVenta || total <= 0) { setVuelto(null); return; }
    const id = setTimeout(async () => {
      try {
        setVuelto(await enviar("/cobro/vuelto", datosDelPago()));
      } catch (e) {
        setAviso({ tipo: "error", texto: e.message });
      }
    }, 120);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [esVenta, total, moneda, tasa, efectivo, transferencia,
      cupEfectivo, cupTransferencia, vueltoMoneda, soloTransferencia]);

  // Al cambiar de moneda no puede quedar arrastrado lo tecleado en la otra:
  // un "vuelto en USD" con la venta ya en CUP descuadraba la caja.
  useEffect(() => {
    setEfectivo(""); setTransferencia("");
    setCupEfectivo(""); setCupTransferencia(""); setVueltoMoneda("");
  }, [moneda]);

  const agregar = (p) => {
    if (p.stock <= 0) {
      setAviso({ tipo: "error", texto: `${p.nombre} no tiene stock` });
      return;
    }
    setCarrito((actual) => {
      const i = actual.findIndex((l) => l.id === p.id);
      if (i >= 0) {
        if (actual[i].cantidad + 1 > p.stock) {
          setAviso({ tipo: "error", texto: `Sólo quedan ${p.stock} de ${p.nombre}` });
          return actual;
        }
        const copia = [...actual];
        copia[i] = { ...copia[i], cantidad: copia[i].cantidad + 1 };
        return copia;
      }
      return [...actual, {
        id: p.id, nombre: p.nombre, cantidad: 1,
        precio: p.precio, costo: p.costo,
        tipo: p.tipo, unidad: p.unidad, stock: p.stock,
      }];
    });
    setAviso(null);
  };

  const cambiarCantidad = (id, valor) =>
    setCarrito((actual) => actual.map((l) => {
      if (l.id !== id) return l;
      const c = Number(valor);
      if (!(c > 0)) return l;
      if (c > l.stock) {
        setAviso({ tipo: "error", texto: `Sólo quedan ${l.stock} de ${l.nombre}` });
        return l;
      }
      return { ...l, cantidad: c };
    }));

  const quitar = (id) => setCarrito((a) => a.filter((l) => l.id !== id));

  const limpiar = () => {
    setCarrito([]); setEfectivo(""); setTransferencia("");
    setCupEfectivo(""); setCupTransferencia(""); setVueltoMoneda("");
    setSoloTransferencia(false); setMensajeria(false); setDeuda(false);
    setObservaciones(""); setMoneda("CUP"); setTasa("1.00");
    setModo("venta"); setMotivo(""); setVuelto(null);
    campoBusqueda.current?.focus();
  };

  const lineasParaInventario = () =>
    carrito.map(({ id, cantidad }) => ({ producto_id: id, cantidad }));

  async function confirmar() {
    setGuardando(true);
    try {
      let r;
      if (modo === "salida") {
        r = await enviar("/inventario/salidas/carrito",
                         { lineas: lineasParaInventario(), motivo });
      } else if (modo === "merma") {
        r = await enviar("/inventario/mermas/carrito",
                         { lineas: lineasParaInventario(), motivo });
      } else {
        r = await enviar("/ventas", {
          carrito: carrito.map(({ id, nombre, cantidad, precio, tipo, unidad }) =>
            ({ id, nombre, cantidad, precio, tipo, unidad })),
          pago: { ...datosDelPago(), tasa: Number(tasa) || 1 },
          es_deuda: deuda,
          es_mensajeria: mensajeria,
          observaciones,
        });
      }
      setAviso({
        tipo: "bien",
        texto: r.mensaje ?? `Venta ${r.venta_id} guardada. Vuelto: ${r.vuelto_texto}`,
      });
      limpiar();
      recargarProductos();
    } catch (e) {
      setAviso({ tipo: "error", texto: e.message });
    } finally {
      setGuardando(false);
    }
  }

  // ------------------------------------------------------------- teclado
  const teclasBusqueda = (e) => {
    if (e.key === "ArrowDown" && resultados.length) {
      e.preventDefault(); filasRef.current[0]?.focus();
    } else if (e.key === "Enter" && resultados.length) {
      e.preventDefault(); agregar(resultados[0]);
    } else if (e.key === "Escape") {
      setBusqueda("");
    }
  };

  const teclasResultado = (e, i) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      const s = Math.min(i + 1, resultados.length - 1);
      setMarcado(s); filasRef.current[s]?.focus();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (i === 0) { campoBusqueda.current?.focus(); return; }
      setMarcado(i - 1); filasRef.current[i - 1]?.focus();
    } else if (e.key === "Enter") {
      e.preventDefault(); agregar(resultados[i]);
    } else if (e.key === "Escape") {
      campoBusqueda.current?.focus();
    }
  };

  // ---------------------------------------------------------- vuelto mixto
  const enDivisa = esVenta && !deuda && !soloTransferencia && moneda !== "CUP";
  const tasaNumero = Number(tasa) || 0;
  const vueltoCup = vuelto?.vuelto_cup ?? 0;

  // Cuánta divisa cabe en el vuelto a esta tasa. El resto va en CUP.
  const topeEnMoneda = tasaNumero > 0 ? vueltoCup / tasaNumero : 0;

  const cabeOtroBillete = (valor) =>
    ((Number(vueltoMoneda) || 0) + valor) * tasaNumero <= vueltoCup + 1e-9;

  const sumarBillete = (valor) => {
    const nuevo = (Number(vueltoMoneda) || 0) + valor;
    if (nuevo * tasaNumero > vueltoCup + 1e-9) return;
    setVueltoMoneda(nuevo.toFixed(2));
  };

  // Un vuelto en divisa que se pasa deja la venta sin poder cerrarse: el
  // cálculo devuelve error y no hay reparto que guardar.
  const puedeConfirmar = carrito.length > 0 && !guardando &&
    (!esVenta || deuda || (vuelto?.cubre && !vuelto?.error));

  return (
    <div className="cuerpo">
      <div className="columna">
        <section className="tarjeta">
          <h2>Buscar productos</h2>
          <div className="fila">
            <input
              ref={campoBusqueda}
              style={{ flex: 1 }}
              placeholder="Escribe para filtrar; Enter añade el primero…"
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
              onKeyDown={teclasBusqueda}
            />
            <button className="boton fantasma" onClick={() => setBusqueda("")}>
              Mostrar todos
            </button>
          </div>

          <div className="desplazable" style={{ marginTop: 12 }}>
            {resultados.length === 0 ? (
              <p className="vacio">Sin resultados</p>
            ) : (
              <table className="tabla">
                <thead>
                  <tr>
                    <th>Producto</th>
                    <th className="derecha">Precio</th>
                    <th className="centro">Stock</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {resultados.map((p, i) => (
                    <tr key={p.id} tabIndex={0}
                        ref={(el) => (filasRef.current[i] = el)}
                        aria-selected={i === marcado}
                        onFocus={() => setMarcado(i)}
                        onKeyDown={(e) => teclasResultado(e, i)}
                        onDoubleClick={() => agregar(p)}>
                      <td>{p.nombre}</td>
                      <td className="derecha">{dinero(esVenta ? p.precio : p.costo)}</td>
                      <td className="centro">{fmtCantidad(p.stock)}</td>
                      <td className="derecha">
                        <button className="boton verde" onClick={() => agregar(p)}>Añadir</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>

        <section className="tarjeta">
          <h2>Carrito de compras</h2>
          {carrito.length === 0 ? (
            <p className="vacio">El carrito está vacío</p>
          ) : (
            <table className="tabla">
              <thead>
                <tr>
                  <th>Producto</th><th className="centro">Cantidad</th>
                  <th className="derecha">Precio</th><th className="derecha">Subtotal</th><th></th>
                </tr>
              </thead>
              <tbody>
                {carrito.map((l) => (
                  <tr key={l.id}>
                    <td>{l.nombre}</td>
                    <td className="centro">
                      <input className="numero" style={{ width: 74 }} type="number"
                             min="0" step={l.tipo === "peso" ? "0.1" : "1"}
                             value={l.cantidad}
                             onChange={(e) => cambiarCantidad(l.id, e.target.value)} />
                    </td>
                    <td className="derecha">
                      {modo === "merma" ? "—" : dinero(precioDe(l))}
                    </td>
                    <td className="derecha">{dinero(l.cantidad * precioDe(l))}</td>
                    <td className="derecha">
                      <button className="quitar" title="Quitar" onClick={() => quitar(l.id)}>✕</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div className="total">
            {reglas.apunte && <span className="apunte">{reglas.apunte}</span>}
            <span className="etiqueta">TOTAL</span>
            <span className="cifra">{dinero(total)}</span>
            <span className="moneda">CUP</span>
          </div>
        </section>

        <section className="tarjeta">
          <h2>Pago</h2>

          <div className="pastillas">
            <button className="pastilla" aria-pressed={soloTransferencia} disabled={!esVenta}
                    onClick={() => marcarPago(() => setSoloTransferencia((v) => !v))}>
              Transferencia
            </button>
            <button className="pastilla" aria-pressed={mensajeria} disabled={!esVenta}
                    onClick={() => marcarPago(() => setMensajeria((v) => !v))}>
              Mensajería
            </button>
            <button className="pastilla" aria-pressed={deuda} disabled={!esVenta}
                    onClick={() => marcarPago(() => setDeuda((v) => !v))}>
              Deuda
            </button>
            {puede("salida_inventario") && (
              <button className="pastilla naranja" aria-pressed={modo === "salida"}
                      onClick={() => cambiarModo("salida")}>
                Salida
              </button>
            )}
            {puede("merma") && (
              <button className="pastilla morada" aria-pressed={modo === "merma"}
                      onClick={() => cambiarModo("merma")}>
                Merma
              </button>
            )}
          </div>

          {!esVenta && (
            <>
              <div className={`aviso-modo ${modo}`}>{reglas.aviso}</div>
              <div className="fila" style={{ marginTop: 12 }}>
                <label htmlFor="motivo">Motivo</label>
                <input id="motivo" style={{ flex: 1 }} value={motivo}
                       onChange={(e) => setMotivo(e.target.value)} />
              </div>
            </>
          )}

          {esVenta && deuda && (
            <div className="fila" style={{ marginBottom: 12 }}>
              <label htmlFor="obs">Observaciones</label>
              <input id="obs" style={{ flex: 1 }} value={observaciones}
                     onChange={(e) => setObservaciones(e.target.value)} />
            </div>
          )}

          {esVenta && !deuda && !soloTransferencia && (
            <>
              <div className="fila" style={{ marginBottom: 10 }}>
                <label htmlFor="moneda">Pago en</label>
                <select id="moneda" value={moneda} onChange={(e) => setMoneda(e.target.value)}>
                  <option>CUP</option><option>USD</option><option>EUR</option>
                </select>
                {moneda !== "CUP" && (
                  <>
                    <label htmlFor="tasa">Tasa (CUP)</label>
                    <input id="tasa" className="numero" style={{ width: 96 }}
                           value={tasa} onChange={(e) => setTasa(e.target.value)} />
                  </>
                )}
              </div>
              <div className="fila">
                <label htmlFor="efectivo">
                  {moneda === "CUP" ? "Pagado (efectivo)" : `Pago en ${moneda}`}
                </label>
                <input id="efectivo" className="numero" style={{ width: 120 }}
                       value={efectivo} onChange={(e) => setEfectivo(e.target.value)} />
                {moneda === "CUP" && (
                  <>
                    <label htmlFor="transf" style={{ marginLeft: 10 }}>Pagado (transferencia)</label>
                    <input id="transf" className="numero" style={{ width: 120 }}
                           value={transferencia} onChange={(e) => setTransferencia(e.target.value)} />
                  </>
                )}
              </div>

              {/* La divisa rara vez cuadra justa: lo que falta se completa en
                  CUP, y esos CUP entran en caja como efectivo o transferencia. */}
              {enDivisa && (
                <div className="adicional">
                  <span className="titulo-bloque">Pago adicional en CUP</span>
                  <div className="fila">
                    <label htmlFor="cupef">Efectivo</label>
                    <input id="cupef" className="numero" style={{ width: 120 }}
                           value={cupEfectivo}
                           onChange={(e) => setCupEfectivo(e.target.value)} />
                    <label htmlFor="cuptr" style={{ marginLeft: 10 }}>Transferencia</label>
                    <input id="cuptr" className="numero" style={{ width: 120 }}
                           value={cupTransferencia}
                           onChange={(e) => setCupTransferencia(e.target.value)} />
                  </div>
                </div>
              )}

              {/* Vuelto mixto: la cajera reparte el cambio entre divisa y CUP.
                  Los botones sólo dejan llegar hasta donde alcanza el vuelto. */}
              {enDivisa && vueltoCup > 0 && (
                <div className="adicional">
                  <span className="titulo-bloque">
                    Vuelto en {moneda} <em>(el resto se devuelve en CUP)</em>
                  </span>
                  <div className="fila">
                    <input className="numero" style={{ width: 120 }}
                           value={vueltoMoneda}
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
                    Como mucho {fmtCantidad(topeEnMoneda)} {moneda} a esta tasa
                  </span>
                </div>
              )}
            </>
          )}

          {esVenta && !deuda && total > 0 && vuelto && (
            <div className="cobro">
              {/* Primera línea: la sugerencia. Dice con qué se ha pagado ya y
                  cuánto falta, para que la cajera lo teclee arriba. */}
              {(!vuelto.cubre || vuelto.resumen_pago) && (
                <div className="sugerencia">
                  {!vuelto.cubre && (
                    <span className="falta">
                      Faltan {dinero(vuelto.falta_cup)} CUP
                      {enDivisa ? " (ponlos en el pago adicional)" : " en efectivo"}
                    </span>
                  )}
                  {vuelto.resumen_pago && <span className="nota">{vuelto.resumen_pago}</span>}
                </div>
              )}

              {/* Segunda línea: sólo el vuelto. Nada más puede salir aquí. */}
              <div className="vuelto">
                <strong style={{ color: "var(--suave)", fontSize: 13 }}>Vuelto</strong>
                <span className="cifra">
                  {vuelto.cubre ? vuelto.texto : "0.00 CUP"}
                </span>
              </div>

              {vuelto.error === "vuelto_moneda_excede" && (
                <div className="aviso error">
                  El vuelto en {moneda} no puede pasar del vuelto total.
                </div>
              )}
            </div>
          )}

          {aviso && <div className={`aviso ${aviso.tipo}`} style={{ marginTop: 12 }}>{aviso.texto}</div>}

          <div className="finales">
            <button className="boton verde" disabled={!puedeConfirmar} onClick={confirmar}>
              {guardando ? "Guardando…" : reglas.boton}
            </button>
            <button className="boton rojo" disabled={!carrito.length} onClick={limpiar}>
              Cancelar
            </button>
          </div>
        </section>
      </div>

      <div className="columna">
        <PanelAcciones productos={productos} alCambiar={recargarProductos}
                       puede={puede} />
      </div>
    </div>
  );
}
