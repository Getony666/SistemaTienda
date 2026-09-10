import { useRef, useState } from "react";
import { enviar } from "./api";

// Sin licencia puesta. La cortesía entra aquí aunque deje trabajar: durante
// esos siete días no hay ningún fichero, así que lo que hace falta enseñar
// es el código para pedirla, no una ficha de algo que no existe.
const SIN_FICHERO = ["cortesia", "sin_licencia"];

/**
 * La pantalla de licencia. Sirve para dos momentos distintos:
 *
 * - `pantallaCompleta`, cuando el programa no se puede usar todavía: no hay
 *   licencia, o el reloj está atrasado. Sale antes de pedir el usuario,
 *   porque no tiene sentido preguntar quién va a usar la caja si la caja no
 *   va a abrir -y porque en una tienda recién estrenada puede que ni haya
 *   usuarios creados.
 * - Como panel normal el resto del tiempo, para consultar o renovar.
 *
 * Cuando hay algo que pedir, lo único grande de la pantalla es el código de
 * la computadora: es el dato que se dicta por teléfono o se pega en WhatsApp,
 * y todo lo demás está para acompañarlo. Con la licencia al día el código
 * baja al tamaño de todo lo demás, porque ya no hay nada que pedir.
 */
export default function PanelLicencia({ licencia, alCambiar, pantallaCompleta = false }) {
  const [copiado, setCopiado] = useState(false);
  const [error, setError] = useState(null);
  const [encima, setEncima] = useState(false);
  const [poniendo, setPoniendo] = useState(false);
  const selector = useRef(null);

  const relojMal = licencia.estado === "reloj_atrasado";
  const sinLicencia = SIN_FICHERO.includes(licencia.estado);
  const vencida = licencia.estado === "vencida";
  const hayQuePedirla = sinLicencia || vencida;

  // Hay un fichero y no sirve: es de otra computadora, está alterado o no se
  // entiende. Hay que decirlo con esas palabras. Si no, el cliente ve la
  // pantalla de activar, cree que el archivo no llegó, y lo vuelve a pegar
  // diez veces antes de llamar.
  const noSirve = Boolean(licencia.motivo) && licencia.motivo !== "no_hay_archivo";

  async function copiar() {
    try {
      await navigator.clipboard.writeText(licencia.maquina);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 2000);
    } catch {
      // WebView2 puede negar el portapapeles. Seleccionarlo deja copiar a mano.
      const codigo = document.getElementById("codigo-maquina");
      if (codigo) window.getSelection()?.selectAllChildren(codigo);
    }
  }

  async function poner(texto) {
    setPoniendo(true);
    setError(null);
    try {
      alCambiar(await enviar("/licencia", { texto }));
    } catch (problema) {
      setError(problema.message);
    } finally {
      setPoniendo(false);
    }
  }

  function leerFichero(fichero) {
    if (!fichero) return;
    const lector = new FileReader();
    lector.onload = () => poner(String(lector.result));
    lector.onerror = () => setError("No se pudo leer el archivo. Prueba a copiarlo otra vez.");
    lector.readAsText(fichero, "utf-8");
  }

  const cuerpo = (
    <div className="tarjeta panel-licencia">
      {sinLicencia ? (
        <>
          <p className="titulo-licencia">Activa MiTienda</p>
          {!noSirve && (
            <p className="explica-licencia">
              {licencia.estado === "cortesia"
                ? `Puedes trabajar ${diasDeCortesia(licencia.dias_restantes)} más
                   mientras llega la licencia. Se activa una sola vez, en esta
                   computadora.`
                : "Este programa todavía no tiene licencia. Se activa una sola vez, en esta computadora."}
            </p>
          )}
        </>
      ) : (
        vencida ? <p className="titulo-licencia">Renueva la licencia</p>
                : <h2>Licencia</h2>
      )}

      {(vencida || relojMal || noSirve) && (
        <div className="bloqueo">
          {/* Vencida no repite la frase de la banda, que ya está arriba en la
              misma pantalla: dice la fecha y pasa a lo que sí se puede hacer. */}
          <span className="fuerte">
            {vencida ? `Venció el ${enCastellano(licencia.hasta)}.`
                     : licencia.explicacion}
          </span>
          {vencida && (
            <span className="resto">
              Mientras tanto puedes consultar tu historial, tus deudas y el
              almacén. Lo que no se puede es cobrar, tocar el inventario ni
              mover dinero.
            </span>
          )}
        </div>
      )}

      {hayQuePedirla && (
        <div className="placa">
          <div className="rotulo">El código de esta computadora</div>
          <div className="fila-codigo">
            <div className="codigo" id="codigo-maquina">
              {licencia.maquina || "sin código"}
            </div>
            <button className="copiar" type="button" onClick={copiar}>
              {copiado ? "Copiado" : "Copiar"}
            </button>
          </div>
        </div>
      )}

      {sinLicencia && (
        <>
          <div className="paso">
            <span className="marca-paso">1</span>
            <span className="texto">Mándale este código a quien te vendió MiTienda.</span>
          </div>
          <div className="paso">
            <span className="marca-paso">2</span>
            <span className="texto">Te devolverá un archivo <b>licencia.lic</b>.</span>
          </div>
          <div className="paso">
            <span className="marca-paso">3</span>
            <span className="texto">Suéltalo aquí abajo, o ponlo en la carpeta del programa.</span>
          </div>
        </>
      )}

      {!hayQuePedirla && !relojMal && <DatosDeLaLicencia licencia={licencia} />}

      {!relojMal && (
        <>
          <div
            className={`soltar${encima ? " encima" : ""}`}
            onDragOver={(e) => { e.preventDefault(); setEncima(true); }}
            onDragLeave={() => setEncima(false)}
            onDrop={(e) => {
              e.preventDefault();
              setEncima(false);
              leerFichero(e.dataTransfer.files?.[0]);
            }}
            onClick={() => selector.current?.click()}
          >
            <div className="principal">
              {poniendo ? "Comprobando…"
                        : hayQuePedirla ? "Suelta aquí el licencia.lic"
                                        : "Suelta aquí una licencia nueva"}
            </div>
            <div className="secundario">o <u>busca el archivo</u></div>
          </div>
          <input ref={selector} type="file" accept=".lic,text/plain" hidden
                 onChange={(e) => leerFichero(e.target.files?.[0])} />
        </>
      )}

      {error && <div className="aviso error">{error}</div>}
    </div>
  );

  return pantallaCompleta ? <div className="puerta">{cuerpo}</div>
                          : <div className="cuerpo-licencia">{cuerpo}</div>;
}

function DatosDeLaLicencia({ licencia }) {
  return (
    <dl className="datos-licencia">
      <dt>Negocio</dt>
      <dd>{licencia.negocio}</dd>

      <dt>Estado</dt>
      <dd>
        {licencia.edicion === "tecnico" ? (
          <span className="pastilla-licencia tecnico">Licencia de técnico</span>
        ) : (
          <span className="pastilla-licencia activa">Al día</span>
        )}
      </dd>

      <dt>Vence</dt>
      <dd>
        {enCastellano(licencia.hasta)}
        {licencia.dias_restantes != null && (
          <span className="restantes"> · {quedan(licencia.dias_restantes)}</span>
        )}
      </dd>

      <dt>Computadora</dt>
      <dd>{licencia.maquina}</dd>
    </dl>
  );
}

function diasDeCortesia(dias) {
  if (dias == null) return "unos días";
  if (dias === 0) return "hasta el final del día";
  return dias === 1 ? "un día" : `${dias} días`;
}

export function enCastellano(iso) {
  if (!iso) return "";
  const fecha = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(fecha.getTime())) return iso;
  return fecha.toLocaleDateString("es-ES",
    { day: "numeric", month: "long", year: "numeric" });
}

export function quedan(dias) {
  if (dias < 0) return "vencida";
  if (dias === 0) return "hoy es el último día";
  return dias === 1 ? "queda 1 día" : `quedan ${dias} días`;
}
