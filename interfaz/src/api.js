// Único punto por el que la interfaz habla con Python.
// La API vive en el mismo servidor que sirve esta página.

export async function api(camino, opciones = {}) {
  const r = await fetch(camino, {
    headers: { "Content-Type": "application/json" },
    ...opciones,
  });
  const cuerpo = await r.json().catch(() => null);
  if (!r.ok) throw new Error(cuerpo?.detail ?? `Error ${r.status}`);
  return cuerpo;
}

// datos a null significa sin cuerpo, que es lo que espera un DELETE.
export const enviar = (camino, datos, metodo = "POST") =>
  api(camino, {
    method: metodo,
    ...(datos == null ? {} : { body: JSON.stringify(datos) }),
  });

export const dinero = (n) => Number(n ?? 0).toFixed(2);

export const cantidad = (c) =>
  Number.isInteger(Number(c)) ? Number(c) : Number(Number(c).toFixed(3));
