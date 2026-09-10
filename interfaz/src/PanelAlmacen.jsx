import { useCallback, useEffect, useMemo, useState } from "react";
import { api, cantidad as fmtCantidad, dinero, enviar } from "./api";

const ACCIONES = [
  { id: "nuevo", texto: "Nuevo producto", color: "teal", permiso: "crear_producto" },
  { id: "actualizar", texto: "Actualizar producto", color: "ocre", permiso: "actualizar_producto" },
  { id: "eliminar", texto: "Eliminar producto", color: "rojo", permiso: "eliminar_producto" },
];

const vacio = {
  producto_id: "", nombre: "", categoria: "Otros",
  precio_compra: "", precio_venta: "", stock: "",
  tipo_producto: "unidad", unidad_medida: "unidad",
  proveedor: "", fecha_vencimiento: "",
};

// El backend calcula vendidos y margen; aquí sólo se pide, se ordena y se
// muestra. Filtrar en el navegador engañaría al "Mostrando N de M" en
// cuanto la lista pasara de un puñado de productos.
export default function PanelAlmacen({ puede, recargarProductosGlobal }) {
  const [buscarTexto, setBuscarTexto] = useState("");
  const [buscar, setBuscar] = useState("");
  const [proveedor, setProveedor] = useState("");
  const [categoria, setCategoria] = useState("");
  const [orden, setOrden] = useState("nombre");
  const [dias, setDias] = useState(30);

  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [avisoCarga, setAvisoCarga] = useState(null);

  const [abierta, setAbierta] = useState(null);
  const [campos, setCampos] = useState(vacio);
  const [aviso, setAviso] = useState(null);
  const [guardando, setGuardando] = useState(false);

  // Un cuarto de segundo de gracia: que la cajera termine de teclear antes
  // de disparar la petición, o cada letra pediría de nuevo.
  useEffect(() => {
    const id = setTimeout(() => setBuscar(buscarTexto), 250);
    return () => clearTimeout(id);
  }, [buscarTexto]);

  const cargar = useCallback(async () => {
    setCargando(true);
    setAvisoCarga(null);
    try {
      const parametros = new URLSearchParams({ orden, dias: String(dias) });
      if (buscar) parametros.set("buscar", buscar);
      if (proveedor) parametros.set("proveedor", proveedor);
      if (categoria) parametros.set("categoria", categoria);
      setDatos(await api(`/almacen?${parametros}`));
    } catch (e) {
      setDatos(null);
      setAvisoCarga({ tipo: "error", texto: e.message });
    } finally {
      setCargando(false);
    }
  }, [buscar, proveedor, categoria, orden, dias]);

  useEffect(() => { cargar(); }, [cargar]);

  const productos = datos?.productos ?? [];
  const resumen = datos?.resumen ?? { total: 0, valor_costo: 0, sin_existencia: 0 };
  const proveedores = datos?.proveedores ?? [];
  const categorias = datos?.categorias ?? [];

  const maxVendidos = useMemo(
    () => productos.reduce((m, p) => Math.max(m, p.vendidos ?? 0), 0),
    [productos]
  );

  const permitidas = ACCIONES.filter((a) => puede(a.permiso));

  const abrir = (id) => {
    setAbierta((actual) => (actual === id ? null : id));
    setCampos(vacio);
    setAviso(null);
  };

  const cerrar = () => { setAbierta(null); setCampos(vacio); setAviso(null); };

  const set = (campo) => (e) =>
    setCampos((c) => ({ ...c, [campo]: e.target.value }));

  const numero = (v) => Number(v) || 0;

  // Al elegir un producto para actualizar se rellena todo lo que ya tiene:
  // mandar campos vacíos borraba el proveedor de un producto que sí lo tenía.
  const elegirParaActualizar = (id) => {
    const p = productos.find((x) => String(x.id) === String(id));
    if (!p) { setCampos({ ...vacio, producto_id: id }); return; }
    setCampos({
      producto_id: id,
      nombre: p.nombre,
      categoria: p.categoria,
      precio_compra: String(p.precio_compra),
      precio_venta: String(p.precio_venta),
      stock: String(p.stock),
      tipo_producto: p.tipo_producto,
      unidad_medida: p.unidad_medida,
      proveedor: p.proveedor,
      fecha_vencimiento: p.fecha_vencimiento || "",
    });
  };

  async function guardar() {
    setGuardando(true);
    setAviso(null);
    try {
      let respuesta;
      if (abierta === "nuevo") {
        respuesta = await enviar("/productos", {
          nombre: campos.nombre,
          categoria: campos.categoria,
          precio_compra: numero(campos.precio_compra),
          precio_venta: numero(campos.precio_venta),
          stock: numero(campos.stock),
          proveedor: campos.proveedor,
          tipo_producto: campos.tipo_producto,
          unidad_medida: campos.unidad_medida,
          fecha_vencimiento: campos.fecha_vencimiento,
        });
      } else if (abierta === "actualizar") {
        if (!campos.producto_id) throw new Error("Elige un producto de la lista");
        respuesta = await enviar(`/productos/${campos.producto_id}`, {
          nombre: campos.nombre,
          categoria: campos.categoria,
          precio_compra: numero(campos.precio_compra),
          precio_venta: numero(campos.precio_venta),
          stock: numero(campos.stock),
          proveedor: campos.proveedor,
          tipo_producto: campos.tipo_producto,
          unidad_medida: campos.unidad_medida,
          fecha_vencimiento: campos.fecha_vencimiento,
        }, "PUT");
      } else if (abierta === "eliminar") {
        if (!campos.producto_id) throw new Error("Elige un producto de la lista");
        respuesta = await enviar(`/productos/${campos.producto_id}`, null, "DELETE");
      }
      setAviso({ tipo: "bien", texto: respuesta?.mensaje ?? "Hecho" });
      setCampos(abierta === "nuevo" ? vacio : { ...vacio });
      await cargar();
      recargarProductosGlobal?.();
    } catch (e) {
      setAviso({ tipo: "error", texto: e.message });
    } finally {
      setGuardando(false);
    }
  }

  const listaProductos = (onSeleccionar) => (
    <label className="campo">
      <span>Producto</span>
      <select value={campos.producto_id} onChange={(e) => onSeleccionar(e.target.value)}>
        <option value="">— elige uno —</option>
        {productos.map((p) => (
          <option key={p.id} value={p.id}>{p.nombre}</option>
        ))}
      </select>
    </label>
  );

  const formularios = {
    nuevo: (
      <>
        <label className="campo ancho"><span>Nombre</span>
          <input value={campos.nombre} onChange={set("nombre")} autoFocus /></label>
        <label className="campo"><span>Categoría</span>
          <select value={campos.categoria} onChange={set("categoria")}>
            {categorias.map((c) => <option key={c} value={c}>{c}</option>)}
          </select></label>
        <label className="campo"><span>Precio compra</span>
          <input className="numero" value={campos.precio_compra} onChange={set("precio_compra")} /></label>
        <label className="campo"><span>Precio venta</span>
          <input className="numero" value={campos.precio_venta} onChange={set("precio_venta")} /></label>
        <label className="campo"><span>Stock</span>
          <input className="numero" value={campos.stock} onChange={set("stock")} /></label>
        <label className="campo"><span>Tipo</span>
          <select value={campos.tipo_producto} onChange={set("tipo_producto")}>
            <option value="unidad">unidad</option><option value="peso">peso</option>
          </select></label>
        <label className="campo"><span>Unidad</span>
          <input value={campos.unidad_medida} onChange={set("unidad_medida")} /></label>
        <label className="campo"><span>Proveedor</span>
          <input value={campos.proveedor} onChange={set("proveedor")} /></label>
        <label className="campo"><span>Fecha de vencimiento</span>
          <input type="date" value={campos.fecha_vencimiento} onChange={set("fecha_vencimiento")} /></label>
      </>
    ),
    actualizar: (
      <>
        {listaProductos(elegirParaActualizar)}
        <label className="campo"><span>Nombre</span>
          <input value={campos.nombre} onChange={set("nombre")} /></label>
        <label className="campo"><span>Categoría</span>
          <select value={campos.categoria} onChange={set("categoria")}>
            {categorias.map((c) => <option key={c} value={c}>{c}</option>)}
          </select></label>
        <label className="campo"><span>Precio compra</span>
          <input className="numero" value={campos.precio_compra} onChange={set("precio_compra")} /></label>
        <label className="campo"><span>Precio venta</span>
          <input className="numero" value={campos.precio_venta} onChange={set("precio_venta")} /></label>
        <label className="campo"><span>Stock</span>
          <input className="numero" value={campos.stock} onChange={set("stock")} /></label>
        <label className="campo"><span>Tipo</span>
          <select value={campos.tipo_producto} onChange={set("tipo_producto")}>
            <option value="unidad">unidad</option><option value="peso">peso</option>
          </select></label>
        <label className="campo"><span>Unidad</span>
          <input value={campos.unidad_medida} onChange={set("unidad_medida")} /></label>
        <label className="campo"><span>Proveedor</span>
          <input value={campos.proveedor} onChange={set("proveedor")} /></label>
        <label className="campo"><span>Fecha de vencimiento</span>
          <input type="date" value={campos.fecha_vencimiento} onChange={set("fecha_vencimiento")} /></label>
      </>
    ),
    eliminar: (
      <>
        {listaProductos((id) => setCampos((c) => ({ ...c, producto_id: id })))}
        <p className="nota-form">
          No se puede eliminar un producto que ya tenga ventas asociadas.
        </p>
      </>
    ),
  };

  const titulo = ACCIONES.find((a) => a.id === abierta)?.texto;

  return (
    <div className="cuerpo una-columna">
      <section className="tarjeta">
        <h2>Filtros</h2>
        <div className="fila">
          <input
            style={{ flex: 1 }}
            placeholder="Buscar productos…"
            value={buscarTexto}
            onChange={(e) => setBuscarTexto(e.target.value)}
          />
          <label>Proveedor</label>
          <select value={proveedor} onChange={(e) => setProveedor(e.target.value)}>
            <option value="">Todos</option>
            {proveedores.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
          <label>Categoría</label>
          <select value={categoria} onChange={(e) => setCategoria(e.target.value)}>
            <option value="">Todas</option>
            {categorias.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <label>Orden</label>
          <div className="segmentado" role="group" aria-label="Orden">
            <button type="button" className={orden === "nombre" ? "activo" : ""}
                    onClick={() => setOrden("nombre")}>A – Z</button>
            <button type="button" className={orden === "vendidos" ? "activo" : ""}
                    onClick={() => setOrden("vendidos")}>Más vendidos</button>
          </div>
          <label>Período</label>
          <select value={dias} onChange={(e) => setDias(Number(e.target.value))}>
            <option value={30}>30 días</option>
            <option value={90}>90 días</option>
            <option value={0}>Todo</option>
          </select>
        </div>

        <div className="resumen-almacen">
          <div className="bloque">
            <span className="etiqueta">Productos</span>
            <span className="cifra">{resumen.total}</span>
          </div>
          <div className="bloque">
            <span className="etiqueta">Valor a costo</span>
            <span className="cifra">{dinero(resumen.valor_costo)}</span>
          </div>
          <div className="bloque">
            <span className="etiqueta">Sin existencia</span>
            <span className="cifra rojo">{resumen.sin_existencia}</span>
          </div>
        </div>

        {avisoCarga && <div className={`aviso ${avisoCarga.tipo}`} style={{ marginTop: 10 }}>{avisoCarga.texto}</div>}
      </section>

      <section className="tarjeta">
        <div className="cabecera-tarjeta">
          <h2>Productos · {resumen.total}</h2>
          <div className="fila">
            {permitidas.map((a) => (
              <button
                key={a.id}
                className={`boton ${a.color} ${abierta === a.id ? "activo" : ""}`}
                onClick={() => abrir(a.id)}
              >
                {a.texto}
              </button>
            ))}
          </div>
        </div>

        <div className="desplazable alto">
          {productos.length === 0 ? (
            <p className="vacio">{cargando ? "Cargando…" : "Sin productos con esos filtros"}</p>
          ) : (
            <table className="tabla almacen">
              <thead>
                <tr>
                  <th>Producto</th><th>Categoría</th><th>Proveedor</th>
                  <th className="derecha">Compra</th><th className="derecha">Venta</th>
                  <th className="derecha">Margen</th><th className="derecha">Existencia</th>
                  <th>Vence</th><th>Vendidos</th>
                </tr>
              </thead>
              <tbody>
                {productos.map((p) => (
                  <tr key={p.id}>
                    <td>{p.nombre}</td>
                    <td>{p.categoria}</td>
                    <td>{p.proveedor}</td>
                    <td className="derecha">{dinero(p.precio_compra)}</td>
                    <td className="derecha">{dinero(p.precio_venta)}</td>
                    <td className="derecha margen">{fmtCantidad(p.margen)}%</td>
                    <td className={`derecha ${p.stock <= 0 ? "sin-existencia" : ""}`}>
                      {fmtCantidad(p.stock)}{p.tipo_producto === "peso" ? ` ${p.unidad_medida}` : ""}
                    </td>
                    <td>{p.fecha_vencimiento || "—"}</td>
                    <td>
                      <div className="vendidos-celda">
                        <span className="barra-vendidos">
                          <span style={{ width: `${maxVendidos > 0 ? (p.vendidos / maxVendidos) * 100 : 0}%` }} />
                        </span>
                        {fmtCantidad(p.vendidos)}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <p className="nota-filtro" style={{ marginTop: 8, marginBottom: 0 }}>
          Mostrando {productos.length} de {resumen.total}
        </p>

        {abierta && (
          <div className="formulario">
            <h3>{titulo}</h3>
            <div className="campos">{formularios[abierta]}</div>

            {aviso && <div className={`aviso ${aviso.tipo}`}>{aviso.texto}</div>}

            <div className="fila" style={{ marginTop: 12 }}>
              <button className="boton verde" onClick={guardar} disabled={guardando}>
                {guardando ? "Guardando…" : "Guardar"}
              </button>
              <button className="boton fantasma" onClick={cerrar}>Cancelar</button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
