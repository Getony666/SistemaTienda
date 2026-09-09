import { useEffect, useRef, useState } from "react";
import { enviar } from "./api";

/**
 * La puerta: o entras con tu usuario, o -si la tienda está estrenada- creas
 * el primer Admin.
 *
 * No se reparte ningún PIN de fábrica con el programa. Si viniera uno puesto,
 * sería el mismo en todos los negocios a los que se le venda esto, y en el
 * primero que alguien lo cuente deja de servir de nada.
 */
export default function Entrar({ hayUsuarios, alEntrar }) {
  const [nombre, setNombre] = useState("");
  const [pin, setPin] = useState("");
  const [error, setError] = useState(null);
  const [entrando, setEntrando] = useState(false);
  const campoNombre = useRef(null);

  const primeraVez = !hayUsuarios;

  useEffect(() => { campoNombre.current?.focus(); }, []);

  async function enviarFormulario(e) {
    e.preventDefault();
    setEntrando(true);
    setError(null);
    try {
      const camino = primeraVez ? "/sesion/primer-admin" : "/sesion";
      alEntrar(await enviar(camino, { nombre: nombre.trim(), pin }));
    } catch (problema) {
      setError(problema.message);
      setPin("");
    } finally {
      setEntrando(false);
    }
  }

  return (
    <div className="puerta">
      <form className="tarjeta acceso" onSubmit={enviarFormulario}>
        <h1 className="marca-grande">MiTienda</h1>

        {primeraVez ? (
          <p className="explicacion">
            Esta tienda está recién estrenada. Crea el usuario <b>Admin</b>,
            que es el único que podrá cambiar los permisos de los demás.
            Apunta el PIN: no hay forma de recuperarlo desde el programa.
          </p>
        ) : (
          <p className="explicacion">¿Quién va a usar la caja?</p>
        )}

        <label className="campo ancho">
          <span>Usuario</span>
          <input ref={campoNombre} value={nombre} autoComplete="off"
                 onChange={(e) => setNombre(e.target.value)} />
        </label>

        <label className="campo ancho">
          <span>PIN{primeraVez && " (mínimo 4 caracteres)"}</span>
          <input type="password" value={pin} autoComplete="off"
                 onChange={(e) => setPin(e.target.value)} />
        </label>

        {error && <div className="aviso error">{error}</div>}

        <button className="boton verde ancho" type="submit"
                disabled={entrando || !nombre.trim() || !pin}>
          {entrando ? "Comprobando…" : primeraVez ? "Crear Admin y entrar" : "Entrar"}
        </button>
      </form>
    </div>
  );
}
