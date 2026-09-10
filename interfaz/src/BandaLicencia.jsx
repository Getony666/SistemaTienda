import { enCastellano } from "./PanelLicencia";

/**
 * La banda que avisa de la licencia, encima de la pantalla de siempre.
 *
 * Es una sola banda que cambia de color según lo que quede: ocre a treinta
 * días, roja a siete o cuando ya venció, verde durante la cortesía. Cuando la
 * licencia está al día no sale nada: avisar cada mañana de algo que falta un
 * año es la forma más rápida de que dejen de leerla.
 */
export default function BandaLicencia({ licencia, alPulsar }) {
  const aviso = redactar(licencia);
  if (!aviso) return null;

  return (
    <div className={`banda-licencia ${aviso.color}`}>
      <span className="punto" aria-hidden="true" />
      {aviso.texto}
      <button type="button" className="enlace" onClick={alPulsar}>
        {aviso.accion}
      </button>
    </div>
  );
}

function redactar({ estado, dias_restantes: dias, hasta }) {
  const cuando = enCastellano(hasta);

  if (estado === "vencida") {
    return {
      color: "roja",
      texto: `La licencia venció el ${cuando}. No se puede vender hasta renovarla.`,
      accion: "Renovar",
    };
  }
  if (estado === "urgente") {
    return {
      color: "roja",
      texto: dias === 0
        ? "Hoy es el último día de licencia. Pide la renovación antes de que se pare la caja."
        : `Quedan ${dias} ${dias === 1 ? "día" : "días"} de licencia. Pide la renovación antes de que se pare la caja.`,
      accion: "Ver licencia",
    };
  }
  if (estado === "por_vencer") {
    return {
      color: "ocre",
      texto: `La licencia vence en ${dias} días, el ${cuando}.`,
      accion: "Ver licencia",
    };
  }
  if (estado === "cortesia") {
    return {
      color: "verde",
      texto: dias === 0
        ? "Hoy se acaba la cortesía. Pon la licencia para poder seguir vendiendo mañana."
        : `Te ${dias === 1 ? "queda 1 día" : `quedan ${dias} días`} de cortesía para poner la licencia.`,
      accion: "Poner licencia",
    };
  }
  return null;
}
