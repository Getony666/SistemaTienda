import { useEffect, useMemo, useRef, useState } from "react";
import { dinero, cantidad as fmtCantidad, enviar } from "./api";
import PanelAcciones from "./PanelAcciones";

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

export default function PanelVentas({ productos, recargarProductos }) {
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

  // El vuelto se lo pedimos a la misma función que usa la caja de tkinter.
  useEffect(() => {
    if (!esVenta || total <= 0) { setVuelto(null); return; }
    const id = setTimeout(async () => {
      try {
        setVuelto(await enviar("/cobro/vuelto", {
          total_cup: total,
          moneda,
          tasa: Number(tasa) || 0,
          efectivo: Number(efectivo) || 0,
          transferencia: Number(transferencia) || 0,
          solo_transferencia: soloTransferencia,
        }));
      } catch (e) {
        setAviso({ tipo: "error", texto: e.message });
      }
    }, 120);
    return () => clearTimeout(id);
  }, [esVenta, total, moneda, tasa, efectivo, transferencia, soloTransferencia]);

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

  const puedeConfirmar = carrito.length > 0 && !guardando &&
    (!esVenta || deuda || vuelto?.cubre);

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
            <button className="pastilla naranja" aria-pressed={modo === "salida"}
                    onClick={() => cambiarModo("salida")}>
              Salida
            </button>
            <button className="pastilla morada" aria-pressed={modo === "merma"}
                    onClick={() => cambiarModo("merma")}>
              Merma
            </button>
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
            </>
          )}

          {esVenta && !deuda && total > 0 && vuelto && (
            <div className="vuelto">
              <strong style={{ color: "var(--suave)", fontSize: 13 }}>Vuelto</strong>
              {vuelto.cubre
                ? <span className="cifra">{vuelto.texto}</span>
                : <span className="falta">Faltan {dinero(vuelto.falta_cup)} CUP</span>}
              {vuelto.resumen_pago && <span className="nota">{vuelto.resumen_pago}</span>}
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
        <PanelAcciones productos={productos} alCambiar={recargarProductos} />
      </div>
    </div>
  );
}
