import { useCallback, useEffect, useState } from "react";
import { api, enviar } from "./api";

const ROLES = ["Admin", "Boss", "Empleado"];

const vacio = { nombre: "", rol: "Empleado", pin: "" };

/**
 * Sólo lo ve Admin. Dos cosas: quién puede entrar, y qué puede hacer cada rol.
 *
 * Marcar aquí una casilla no es un adorno: cambia la tabla `permisos_rol`, y
 * es esa tabla la que consulta la API antes de dejar pasar cada petición.
 */
export default function PanelUsuarios({ alCambiarPermisos }) {
  const [usuarios, setUsuarios] = useState([]);
  const [permisos, setPermisos] = useState(null);
  const [nuevo, setNuevo] = useState(vacio);
  const [creando, setCreando] = useState(false);
  const [pinNuevo, setPinNuevo] = useState({});
  const [aviso, setAviso] = useState(null);

  const cargar = useCallback(async () => {
    try {
      const [lista, tabla] = await Promise.all([
        api("/usuarios?incluir_inactivos=true"),
        api("/permisos"),
      ]);
      setUsuarios(lista);
      setPermisos(tabla);
    } catch (e) {
      setAviso({ tipo: "error", texto: e.message });
    }
  }, []);

  useEffect(() => { cargar(); }, [cargar]);

  const hacer = async (accion, exito) => {
    setAviso(null);
    try {
      const r = await accion();
      setAviso({ tipo: "bien", texto: exito ?? r?.mensaje ?? "Hecho" });
      await cargar();
      alCambiarPermisos?.();
      return true;
    } catch (e) {
      setAviso({ tipo: "error", texto: e.message });
      return false;
    }
  };

  async function crear() {
    setCreando(true);
    const bien = await hacer(() => enviar("/usuarios", {
      nombre: nuevo.nombre.trim(), rol: nuevo.rol, pin: nuevo.pin,
    }));
    if (bien) setNuevo(vacio);
    setCreando(false);
  }

  const tienePermiso = (rol, clave) =>
    (permisos?.concedidos?.[rol] ?? []).includes(clave);

  return (
    <div className="cuerpo una-columna">
      <section className="tarjeta">
        <h2>👤 Usuarios</h2>

        <table className="tabla">
          <thead>
            <tr>
              <th>Nombre</th><th>Rol</th><th className="centro">Activo</th>
              <th>PIN nuevo</th><th></th>
            </tr>
          </thead>
          <tbody>
            {usuarios.map((u) => (
              <tr key={u.id} className={u.activo ? undefined : "apagado"}>
                <td>{u.nombre}</td>
                <td>
                  <select value={u.rol}
                          onChange={(e) => hacer(
                            () => enviar(`/usuarios/${u.id}/rol`,
                                         { rol: e.target.value }, "PUT"))}>
                    {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                </td>
                <td className="centro">{u.activo ? "Sí" : "No"}</td>
                <td>
                  <div className="fila">
                    <input type="password" style={{ width: 110 }}
                           value={pinNuevo[u.id] ?? ""}
                           placeholder="mínimo 4"
                           onChange={(e) => setPinNuevo(
                             (p) => ({ ...p, [u.id]: e.target.value }))} />
                    <button className="boton fantasma"
                            disabled={!(pinNuevo[u.id] ?? "").trim()}
                            onClick={async () => {
                              const bien = await hacer(() => enviar(
                                `/usuarios/${u.id}/pin`,
                                { pin: pinNuevo[u.id] }, "PUT"));
                              if (bien) setPinNuevo((p) => ({ ...p, [u.id]: "" }));
                            }}>
                      Restablecer
                    </button>
                  </div>
                </td>
                <td className="derecha">
                  {u.activo && (
                    <button className="boton rojo"
                            onClick={() => hacer(
                              () => enviar(`/usuarios/${u.id}`, null, "DELETE"))}>
                      Desactivar
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <p className="nota-filtro">
          Los usuarios no se borran, se desactivan: lo que hicieron tiene que
          seguir teniendo nombre en el historial.
        </p>

        <div className="formulario">
          <h3>Usuario nuevo</h3>
          <div className="campos">
            <label className="campo"><span>Nombre</span>
              <input value={nuevo.nombre}
                     onChange={(e) => setNuevo({ ...nuevo, nombre: e.target.value })} /></label>
            <label className="campo"><span>Rol</span>
              <select value={nuevo.rol}
                      onChange={(e) => setNuevo({ ...nuevo, rol: e.target.value })}>
                {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
              </select></label>
            <label className="campo"><span>PIN</span>
              <input type="password" value={nuevo.pin}
                     onChange={(e) => setNuevo({ ...nuevo, pin: e.target.value })} /></label>
          </div>
          <div className="fila" style={{ marginTop: 12 }}>
            <button className="boton verde" onClick={crear}
                    disabled={creando || !nuevo.nombre.trim() || !nuevo.pin}>
              {creando ? "Creando…" : "Crear usuario"}
            </button>
          </div>
        </div>

        {aviso && <div className={`aviso ${aviso.tipo}`}>{aviso.texto}</div>}
      </section>

      <section className="tarjeta">
        <h2>🔑 Permisos por rol</h2>

        {!permisos ? (
          <p className="vacio">Cargando…</p>
        ) : (
          <>
            <div className="desplazable alto">
              <table className="tabla permisos">
                <thead>
                  <tr>
                    <th>Permiso</th>
                    {permisos.roles.map((r) => <th key={r} className="centro">{r}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {permisos.catalogo.map(({ clave, texto }) => (
                    <tr key={clave}>
                      <td>{texto}</td>
                      {permisos.roles.map((rol) => {
                        const fijo = clave === permisos.permiso_fijo;
                        const bloqueado = fijo || rol === "Admin";
                        return (
                          <td key={rol} className="centro">
                            <input
                              type="checkbox"
                              checked={rol === "Admin" ? true : tienePermiso(rol, clave)}
                              disabled={bloqueado}
                              title={
                                fijo
                                  ? "Sólo de Admin: no se puede dar ni quitar"
                                  : rol === "Admin"
                                    ? "Admin lo puede todo, siempre"
                                    : undefined
                              }
                              onChange={(e) => hacer(() => enviar("/permisos", {
                                rol, permiso: clave, concedido: e.target.checked,
                              }, "PUT"))}
                            />
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <p className="nota-filtro">
              Admin lo puede todo y no se le quita nada: si se pudiera, un
              descuido dejaría la tienda sin nadie capaz de administrarla.
              Por el mismo motivo, <b>gestionar usuarios y permisos</b> no se
              le puede dar a Boss.
            </p>
          </>
        )}
      </section>
    </div>
  );
}
