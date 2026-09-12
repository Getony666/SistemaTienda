"""Las reglas de la licencia. Módulo puro: ni disco, ni red, ni reloj.

Recibe el texto de un `licencia.lic`, la llave pública, la huella de esta
computadora y qué día es hoy, y contesta qué se puede hacer. Nada más. Quien
lee el fichero es `almacen_licencia.py`; quien mira el reloj y decide qué
enseñar es `estado_licencia.py`.

Está partido así por la misma razón que `calculo_cobro` o `carrito`: se puede
probar un vencimiento pasándole una fecha inventada, sin tocar la hora de
Windows ni fabricar ficheros.

Formato del fichero, en texto plano UTF-8:

    MiTienda-Licencia-v2
    producto: MiTienda
    negocio: Bodega La Esquina
    maquina: A7K2-3M4P-XR7T
    desde: 2026-09-15
    hasta: 2027-09-15
    edicion: completa
    firma: MFRGGZDF MZTWQ2LK ...

Es legible a propósito: el cliente puede abrirlo y entender qué compró.
Cambiarle una letra invalida la firma.
"""

import base64
import dataclasses
import datetime

from .ed25519 import verificar as verificar_firma

CABECERA = "MiTienda-Licencia-v2"

# El orden importa: es el que se firma. Tocarlo -o añadir un campo- invalida
# de golpe todas las licencias emitidas hasta ese momento, así que va siempre
# con una cabecera nueva. La v2 añadió "producto", y se pudo hacer sin coste
# porque todavía no había ni un cliente en la calle.
CAMPOS = ("producto", "negocio", "maquina", "desde", "hasta", "edicion")
EDICIONES = ("completa", "tecnico")

# Estados
ACTIVA = "activa"
POR_VENCER = "por_vencer"
URGENTE = "urgente"
VENCIDA = "vencida"
SIN_LICENCIA = "sin_licencia"
RELOJ_ATRASADO = "reloj_atrasado"
# Este módulo nunca devuelve CORTESIA -no sabe cuándo se instaló el programa,
# que es un dato del disco-, pero el nombre vive aquí con los demás para que
# el vocabulario de estados esté en un solo sitio. Quien lo produce es
# estado_licencia.py.
CORTESIA = "cortesia"

# Los estados con los que se puede cobrar, dar de alta un producto o mover
# dinero. Los que faltan -vencida, sin licencia, reloj atrasado- dejan
# consultar y exportar, pero no escribir: los datos del cliente son suyos.
ESTADOS_QUE_ESCRIBEN = frozenset({ACTIVA, POR_VENCER, URGENTE, CORTESIA})

# Motivos del rechazo. Se guardan aparte del estado porque "esta licencia es
# de otra computadora" ahorra una llamada de soporte que "licencia no valida"
# no ahorra.
NO_HAY_ARCHIVO = "no_hay_archivo"
FORMATO = "formato"
FIRMA = "firma"
OTRA_MAQUINA = "otra_maquina"
OTRO_PRODUCTO = "otro_producto"

DIAS_DE_AVISO = 30
DIAS_DE_AVISO_SERIO = 7


@dataclasses.dataclass(frozen=True)
class Veredicto:
    estado: str
    motivo: str = ""
    negocio: str = ""
    producto: str = ""
    edicion: str = ""
    maquina: str = ""
    hasta: datetime.date | None = None
    dias_restantes: int | None = None


def normalizar_maquina(codigo):
    """El código de máquina sin guiones, sin espacios y en mayúsculas.

    La cajera lo va a dictar por teléfono y a teclear a mano, así que
    compararlo tal cual llega sería regalar una llamada de soporte por cada
    guion de más.
    """
    return "".join(c for c in str(codigo or "") if c.isalnum()).upper()


def normalizar_producto(nombre):
    """El nombre del producto sin espacios sobrantes y sin mayúsculas.

    Se teclea a mano al emitir la licencia, así que una mayúscula de más no
    puede dejar sin abrir a un cliente que ya pagó.
    """
    return str(nombre or "").strip().casefold()


def texto_canonico(datos):
    """Los octetos exactos que se firman y se verifican.

    No se firma el fichero tal cual, sino esta cadena reconstruida a partir de
    los campos ya leídos. Así el fichero sobrevive a que Windows le cambie los
    saltos de línea, a un espacio de más al copiar y pegar, o a que alguien lo
    abra con el Bloc de notas y le dé a guardar.
    """
    return "\n".join(f"{campo}: {datos[campo]}" for campo in CAMPOS).encode("utf-8")


def componer(datos, firma):
    """El contenido completo de un licencia.lic. Lo usa el generador."""
    agrupada = base64.b32encode(firma).decode("ascii")
    trozos = [agrupada[i:i + 8] for i in range(0, len(agrupada), 8)]
    lineas = [CABECERA]
    lineas += [f"{campo}: {datos[campo]}" for campo in CAMPOS]
    lineas.append("firma: " + " ".join(trozos))
    return "\n".join(lineas) + "\n"


def analizar(texto):
    """El texto vuelve a ser (datos, firma), o (None, None) si no cuadra.

    Los campos que no conoce se ignoran en lugar de rechazarse: si algún día
    se añade uno, una versión vieja del programa seguirá abriendo las
    licencias nuevas mientras los cinco de siempre estén. Ignorarlos no abre
    ninguna puerta, porque la firma sólo cubre esos cinco.
    """
    lineas = [l.strip() for l in str(texto).splitlines()]
    lineas = [l for l in lineas if l]
    if not lineas or lineas[0] != CABECERA:
        return None, None

    leidos = {}
    for linea in lineas[1:]:
        if ":" not in linea:
            continue
        clave, _, valor = linea.partition(":")
        leidos[clave.strip()] = valor.strip()

    if not all(campo in leidos for campo in CAMPOS) or "firma" not in leidos:
        return None, None
    if leidos["edicion"] not in EDICIONES:
        return None, None

    try:
        for campo in ("desde", "hasta"):
            datetime.date.fromisoformat(leidos[campo])
        firma = base64.b32decode(leidos["firma"].replace(" ", ""))
    except (ValueError, TypeError):
        return None, None
    if len(firma) != 64:
        return None, None

    return {campo: leidos[campo] for campo in CAMPOS}, firma


def verificar(texto, llave_publica, huella_maquina, hoy, producto):
    """Qué se puede hacer hoy, en esta máquina, con esta licencia.

    `producto` es el nombre del programa que está preguntando -`NOMBRE_APP`-.
    Va como parámetro y no leído de dentro por lo mismo que la llave pública:
    este módulo no tiene por qué saber a qué producto sirve.

    El orden de las comprobaciones no es casual: hasta que la firma no vale,
    nada de lo que dice el fichero se puede repetir en pantalla, porque lo
    habría escrito quien quisiera. Por eso el nombre del negocio sólo aparece
    en el veredicto a partir de que la firma pasa.
    """
    if not str(texto or "").strip():
        return Veredicto(SIN_LICENCIA, NO_HAY_ARCHIVO)

    datos, firma = analizar(texto)
    if datos is None:
        return Veredicto(SIN_LICENCIA, FORMATO)

    if not verificar_firma(llave_publica, texto_canonico(datos), firma):
        return Veredicto(SIN_LICENCIA, FIRMA)

    hasta = datetime.date.fromisoformat(datos["hasta"])
    desde = datetime.date.fromisoformat(datos["desde"])
    dias = (hasta - hoy).days
    conocido = {"negocio": datos["negocio"], "edicion": datos["edicion"],
                "producto": datos["producto"], "maquina": datos["maquina"],
                "hasta": hasta, "dias_restantes": dias}

    # El producto antes que la máquina: si alguien mete aquí la licencia de
    # otro programa, "esta licencia es de otro programa" explica mejor lo que
    # pasa que "es de otra computadora", aunque las dos cosas fallen.
    if normalizar_producto(datos["producto"]) != normalizar_producto(producto):
        return Veredicto(SIN_LICENCIA, OTRO_PRODUCTO, **conocido)

    if normalizar_maquina(datos["maquina"]) != normalizar_maquina(huella_maquina):
        return Veredicto(SIN_LICENCIA, OTRA_MAQUINA, **conocido)

    # Nadie tiene una licencia emitida el mes que viene: o el reloj está
    # atrasado, o alguien lo ha atrasado. Se mira antes que el vencimiento
    # porque con el reloj mal, "vencida" tampoco significaría nada.
    if hoy < desde:
        return Veredicto(RELOJ_ATRASADO, **conocido)

    if dias < 0:
        return Veredicto(VENCIDA, **conocido)

    # La de técnico dura tres días: si entrara en el aviso de los siete,
    # sacaría el cartel de renovar cada vez que se abre, y no es una
    # renovación, es un técnico trabajando.
    if datos["edicion"] == "tecnico":
        return Veredicto(ACTIVA, **conocido)

    if dias <= DIAS_DE_AVISO_SERIO:
        return Veredicto(URGENTE, **conocido)
    if dias <= DIAS_DE_AVISO:
        return Veredicto(POR_VENCER, **conocido)
    return Veredicto(ACTIVA, **conocido)
