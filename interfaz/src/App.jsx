import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "./estilos.css";

// La API vive en el mismo servidor que sirve esta página.
const api = async (camino, opciones = {}) => {
  const r = await fetch(camino, {
    headers: { "Content-Type": "application/json" },
    ...opciones,
  });
  const cuerpo = await r.json().catch(() => null);
  if (!r.ok) throw new Error(cuerpo?.detail ?? `Error ${r.status}`);
  return cuerpo;
};

const dinero = (n) => Number(n ?? 0).toFixed(2);
const cantidadTexto = (c) => (Number.isInteger(c) ? c : Number(c.toFixed(3)));

export default function App() {
  const [busqueda, setBusqueda] = useState("");
  const [resultados, setResultados] = useState([]);
  const [marcado, setMarcado] = useState(0);
  const [carrito, setCarrito] = useState([]);

  const [soloTransferencia, setSoloTransferencia] = useState(false);
  const [mensajeria, setMensajeria] = useState(false);
  const [deuda, setDeuda] = useState(false);
  const [observaciones, setObservaciones] = useState("");

  const [moneda, setMoneda] = useState("CUP");
  const [tasa, setTasa] = useState("1.00");
  const [efectivo, setEfectivo] = useState("");
  const [transferencia, setTransferencia] = useState("");

  const [vuelto, setVuelto] = useState(null);
  const [aviso, setAviso] = useState(null);
  const [guardando, setGuardando] = useState(false);

  const campoBusqueda = useRef(null);
  const filasRef = useRef([]);

  const total = useMemo(
    () => carrito.reduce((suma, l) => suma + l.cantidad * l.precio, 0),
    [carrito]
  );

  useEffect(() => { campoBusqueda.current?.focus(); }, []);

  const buscar = useCallback(async (texto) => {
    try {
      const datos = await api(`/productos?buscar=${encodeURIComponent(texto)}`);
      setResultados(datos.slice(0, 60));
      setMarcado(0);
    } catch (e) {
      setAviso({ tipo: "error", texto: e.message });
    }
  }, []);

  useEffect(() => { buscar(""); }, [buscar]);

  // --- el vuelto se recalcula solo, pidiéndoselo a la misma función que usa la caja
  useEffect(() => {
    if (total <= 0) { setVuelto(null); return; }
    const id = setTimeout(async () => {
      try {
        setVuelto(await api("/cobro/vuelto", {
          method: "POST",
          body: JSON.stringify({
            total_cup: total,
            moneda,
            tasa: Number(tasa) || 0,
            efectivo: Number(efectivo) || 0,
            transferencia: Number(transferencia) || 0,
            solo_transferencia: soloTransferencia,
          }),
        }));
      } catch (e) {
        setAviso({ tipo: "error", texto: e.message });
      }
    }, 120);
    return () => clearTimeout(id);
  }, [total, moneda, tasa, efectivo, transferencia, soloTransferencia]);

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
        id: p.id, nombre: p.nombre, cantidad: 1, precio: p.precio,
        tipo: p.tipo, unidad: p.unidad, stock: p.stock,
      }];
    });
    setAviso(null);
  };

  const cambiarCantidad = (id, valor) => {
    setCarrito((actual) => actual.map((l) => {
      if (l.id !== id) return l;
      const cantidad = Number(valor);
      if (!(cantidad > 0)) return l;
      if (cantidad > l.stock) {
        setAviso({ tipo: "error", texto: `Sólo quedan ${l.stock} de ${l.nombre}` });
        return l;
      }
      return { ...l, cantidad };
    }));
  };

  const quitar = (id) => setCarrito((a) => a.filter((l) => l.id !== id));

  const limpiar = () => {
    setCarrito([]); setEfectivo(""); setTransferencia("");
    setSoloTransferencia(false); setMensajeria(false); setDeuda(false);
    setObservaciones(""); setMoneda("CUP"); setTasa("1.00");
    setVuelto(null); campoBusqueda.current?.focus();
  };

  const finalizar = async () => {
    setGuardando(true);
    try {
      const r = await api("/ventas", {
        method: "POST",
        body: JSON.stringify({
          carrito: carrito.map(({ id, nombre, cantidad, precio, tipo, unidad }) =>
            ({ id, nombre, cantidad, precio, tipo, unidad })),
          pago: {
            total_cup: total,
            moneda,
            tasa: Number(tasa) || 1,
            efectivo: Number(efectivo) || 0,
            transferencia: Number(transferencia) || 0,
            solo_transferencia: soloTransferencia,
          },
          es_deuda: deuda,
          es_mensajeria: mensajeria,
          observaciones,
        }),
      });
      setAviso({ tipo: "bien", texto: `Venta ${r.venta_id} guardada. Vuelto: ${r.vuelto_texto}` });
      limpiar();
      buscar(busqueda);
    } catch (e) {
      setAviso({ tipo: "error", texto: e.message });
    } finally {
      setGuardando(false);
    }
  };

  // ------------------------------------------------------------- teclado
  const teclasBusqueda = (e) => {
    if (e.key === "Enter") { buscar(busqueda); }
    else if (e.key === "ArrowDown" && resultados.length) {
      e.preventDefault();
      filasRef.current[0]?.focus();
    } else if (e.key === "Escape") {
      setBusqueda(""); buscar("");
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

  const puedeFinalizar =
    carrito.length > 0 && !guardando && (deuda || vuelto?.cubre);

  return (
    <>
      <nav className="nav">
        <button aria-current="page">Ventas</button>
        <button disabled title="Todavía en tkinter">Historial</button>
        <button disabled title="Todavía en tkinter">Cambio de Divisa</button>
        <button disabled title="Todavía en tkinter">Corte de Caja</button>
        <span className="marca">MiTienda · panel de Ventas en React</span>
      </nav>

      <div className="cuerpo">
        <div className="columna">
          <section className="tarjeta">
            <h2>Buscar productos</h2>
            <div className="fila">
              <input
                ref={campoBusqueda}
                style={{ flex: 1 }}
                placeholder="Escribe y pulsa Enter…"
                value={busqueda}
                onChange={(e) => setBusqueda(e.target.value)}
                onKeyDown={teclasBusqueda}
              />
              <button className="boton" onClick={() => buscar(busqueda)}>Buscar</button>
              <button className="boton fantasma" onClick={() => { setBusqueda(""); buscar(""); }}>
                Todos
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
                      <tr
                        key={p.id}
                        tabIndex={0}
                        ref={(el) => (filasRef.current[i] = el)}
                        aria-selected={i === marcado}
                        onFocus={() => setMarcado(i)}
                        onKeyDown={(e) => teclasResultado(e, i)}
                        onDoubleClick={() => agregar(p)}
                      >
                        <td>{p.nombre}</td>
                        <td className="derecha">{dinero(p.precio)}</td>
                        <td className="centro">{cantidadTexto(p.stock)}</td>
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
            <h2>Carrito</h2>
            {carrito.length === 0 ? (
              <p className="vacio">El carrito está vacío</p>
            ) : (
              <table className="tabla">
                <thead>
                  <tr>
                    <th>Producto</th>
                    <th className="centro">Cantidad</th>
                    <th className="derecha">Precio</th>
                    <th className="derecha">Subtotal</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {carrito.map((l) => (
                    <tr key={l.id}>
                      <td>{l.nombre}</td>
                      <td className="centro">
                        <input
                          className="numero"
                          style={{ width: 78 }}
                          type="number" min="0" step={l.tipo === "peso" ? "0.1" : "1"}
                          value={l.cantidad}
                          onChange={(e) => cambiarCantidad(l.id, e.target.value)}
                        />
                      </td>
                      <td className="derecha">{dinero(l.precio)}</td>
                      <td className="derecha">{dinero(l.cantidad * l.precio)}</td>
                      <td className="derecha">
                        <button className="quitar" title="Quitar" onClick={() => quitar(l.id)}>✕</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <div className="total">
              <span className="etiqueta">TOTAL</span>
              <span className="cifra">{dinero(total)}</span>
              <span className="moneda">CUP</span>
            </div>
          </section>

          <section className="tarjeta">
            <h2>Pago</h2>

            <div className="pastillas">
              <button className="pastilla" aria-pressed={soloTransferencia}
                      onClick={() => setSoloTransferencia((v) => !v)}>Transferencia</button>
              <button className="pastilla" aria-pressed={mensajeria}
                      onClick={() => setMensajeria((v) => !v)}>Mensajería</button>
              <button className="pastilla" aria-pressed={deuda}
                      onClick={() => setDeuda((v) => !v)}>Deuda</button>
            </div>

            {deuda && (
              <div className="fila" style={{ marginBottom: 12 }}>
                <label htmlFor="obs">Observaciones</label>
                <input id="obs" style={{ flex: 1 }} value={observaciones}
                       onChange={(e) => setObservaciones(e.target.value)} />
              </div>
            )}

            {!deuda && !soloTransferencia && (
              <>
                <div className="fila" style={{ marginBottom: 10 }}>
                  <label htmlFor="moneda">Pago en</label>
                  <select id="moneda" value={moneda} onChange={(e) => setMoneda(e.target.value)}>
                    <option>CUP</option><option>USD</option><option>EUR</option>
                  </select>
                  {moneda !== "CUP" && (
                    <>
                      <label htmlFor="tasa">Tasa</label>
                      <input id="tasa" className="numero" style={{ width: 96 }}
                             value={tasa} onChange={(e) => setTasa(e.target.value)} />
                    </>
                  )}
                </div>

                <div className="fila">
                  <label htmlFor="efectivo">{moneda === "CUP" ? "Efectivo" : `Pago en ${moneda}`}</label>
                  <input id="efectivo" className="numero" style={{ width: 120 }}
                         value={efectivo} onChange={(e) => setEfectivo(e.target.value)} />
                  {moneda === "CUP" && (
                    <>
                      <label htmlFor="transf" style={{ marginLeft: 10 }}>Transferencia</label>
                      <input id="transf" className="numero" style={{ width: 120 }}
                             value={transferencia} onChange={(e) => setTransferencia(e.target.value)} />
                    </>
                  )}
                </div>
              </>
            )}

            {!deuda && total > 0 && vuelto && (
              <div className="vuelto">
                <strong style={{ color: "var(--suave)", fontSize: 13 }}>Vuelto</strong>
                {vuelto.cubre ? (
                  <span className="cifra">{vuelto.texto}</span>
                ) : (
                  <span className="falta">Faltan {dinero(vuelto.falta_cup)} CUP</span>
                )}
                {vuelto.resumen_pago && <span className="nota">{vuelto.resumen_pago}</span>}
              </div>
            )}

            {aviso && (
              <div className={`aviso ${aviso.tipo}`} style={{ marginTop: 12 }}>{aviso.texto}</div>
            )}

            <div className="finales">
              <button className="boton verde" disabled={!puedeFinalizar} onClick={finalizar}>
                {guardando ? "Guardando…" : "Finalizar venta"}
              </button>
              <button className="boton rojo" disabled={!carrito.length} onClick={limpiar}>
                Cancelar venta
              </button>
            </div>
          </section>
        </div>

        <div className="columna">
          <section className="tarjeta">
            <h2>Atajos de teclado</h2>
            <div className="atajos">
              <kbd>Enter</kbd> en el buscador — buscar<br />
              <kbd>↓</kbd> — bajar a la lista<br />
              <kbd>↑</kbd> <kbd>↓</kbd> — moverse por los resultados<br />
              <kbd>Enter</kbd> — añadir al carrito<br />
              <kbd>Esc</kbd> — volver al buscador
            </div>
          </section>

          <section className="tarjeta">
            <h2>Acciones</h2>
            <div className="pendiente">
              Nuevo producto, entradas y salidas de efectivo,<br />
              inventario y mermas siguen en la ventana de tkinter.<br />
              Esta vista sólo prueba el panel de Ventas.
            </div>
          </section>
        </div>
      </div>
    </>
  );
}

// build: interfaz de Ventas en React sobre la API local
