import { useState } from "react";
import { enviar } from "./api";

// Salida de Inventario y Merma ya no están aquí: se marcan como etiquetas en
// la sección de Pago, sobre el carrito entero. Quedan cinco, en dos filas.
const ACCIONES = [
  { id: "nuevo", texto: "Nuevo Producto", color: "teal" },
  { id: "actualizar", texto: "Actualizar Producto", color: "ocre" },
  { id: "eliminar", texto: "Eliminar Producto", color: "rojo" },
  { id: "entrada", texto: "Entrada de Efectivo", color: "verde" },
  { id: "salida_efe", texto: "Salida de Efectivo", color: "rojo" },
];

const vacio = {
  nombre: "", categoria: "", precio_compra: "", precio_venta: "",
  stock: "", proveedor: "", tipo_producto: "unidad", unidad_medida: "unidad",
  fecha_vencimiento: "",
  moneda: "CUP", monto: "", descripcion: "",
  producto_id: "",
};

export default function PanelAcciones({ productos, alCambiar }) {
  const [abierta, setAbierta] = useState(null);
  const [campos, setCampos] = useState(vacio);
  const [aviso, setAviso] = useState(null);
  const [guardando, setGuardando] = useState(false);

  const abrir = (id) => {
    setAbierta((actual) => (actual === id ? null : id));
    setCampos(vacio);
    setAviso(null);
  };

  const cerrar = () => { setAbierta(null); setCampos(vacio); setAviso(null); };

  const set = (campo) => (e) =>
    setCampos((c) => ({ ...c, [campo]: e.target.value }));

  const numero = (v) => Number(v) || 0;

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
        const p = productos.find((x) => String(x.id) === String(campos.producto_id));
        if (!p) throw new Error("Elige un producto de la lista");
        respuesta = await enviar(`/productos/${p.id}`, {
          nombre: campos.nombre || p.nombre,
          categoria: campos.categoria,
          precio_compra: numero(campos.precio_compra),
          precio_venta: numero(campos.precio_venta || p.precio),
          stock: numero(campos.stock || p.stock),
          proveedor: campos.proveedor,
          tipo_producto: campos.tipo_producto,
          unidad_medida: campos.unidad_medida,
          fecha_vencimiento: campos.fecha_vencimiento,
        }, "PUT");
      } else if (abierta === "eliminar") {
        if (!campos.producto_id) throw new Error("Elige un producto de la lista");
        respuesta = await enviar(`/productos/${campos.producto_id}`, null, "DELETE");
      } else if (abierta === "entrada") {
        respuesta = await enviar("/caja/entradas", {
          moneda: campos.moneda, monto: numero(campos.monto),
          descripcion: campos.descripcion,
        });
      } else if (abierta === "salida_efe") {
        respuesta = await enviar("/caja/salidas", {
          moneda: campos.moneda, monto: numero(campos.monto),
          descripcion: campos.descripcion,
        });
      }
      setAviso({ tipo: "bien", texto: respuesta?.mensaje ?? "Hecho" });
      setCampos(vacio);
      alCambiar?.();
    } catch (e) {
      setAviso({ tipo: "error", texto: e.message });
    } finally {
      setGuardando(false);
    }
  }

  const listaProductos = (
    <label className="campo">
      <span>Producto</span>
      <select value={campos.producto_id} onChange={set("producto_id")}>
        <option value="">— elige uno —</option>
        {productos.map((p) => (
          <option key={p.id} value={p.id}>{p.nombre}</option>
        ))}
      </select>
    </label>
  );

  const montoYMoneda = (
    <>
      <label className="campo">
        <span>Moneda</span>
        <select value={campos.moneda} onChange={set("moneda")}>
          <option>CUP</option><option>USD</option><option>EUR</option>
        </select>
      </label>
      <label className="campo">
        <span>Monto</span>
        <input className="numero" value={campos.monto} onChange={set("monto")} />
      </label>
      <label className="campo ancho">
        <span>Descripción</span>
        <input value={campos.descripcion} onChange={set("descripcion")} />
      </label>
    </>
  );

  const formularios = {
    nuevo: (
      <>
        <label className="campo ancho"><span>Nombre</span>
          <input value={campos.nombre} onChange={set("nombre")} autoFocus /></label>
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
      </>
    ),
    actualizar: (
      <>
        {listaProductos}
        <label className="campo"><span>Precio venta</span>
          <input className="numero" value={campos.precio_venta} onChange={set("precio_venta")} /></label>
        <label className="campo"><span>Precio compra</span>
          <input className="numero" value={campos.precio_compra} onChange={set("precio_compra")} /></label>
        <label className="campo"><span>Stock</span>
          <input className="numero" value={campos.stock} onChange={set("stock")} /></label>
      </>
    ),
    eliminar: (
      <>
        {listaProductos}
        <p className="nota-form">
          No se puede eliminar un producto que ya tenga ventas asociadas.
        </p>
      </>
    ),
    entrada: montoYMoneda,
    salida_efe: montoYMoneda,
  };

  const titulo = ACCIONES.find((a) => a.id === abierta)?.texto;

  return (
    <section className="tarjeta">
      <h2>⚡ Acciones</h2>

      <div className="acciones">
        {ACCIONES.map((a) => (
          <button
            key={a.id}
            className={`boton ${a.color} ${abierta === a.id ? "activo" : ""}`}
            onClick={() => abrir(a.id)}
          >
            {a.texto}
          </button>
        ))}
      </div>

      {abierta ? (
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
      ) : (
        <div className="pendiente">
          Al tocar un botón de arriba,<br />su formulario aparece aquí debajo.
        </div>
      )}
    </section>
  );
}
