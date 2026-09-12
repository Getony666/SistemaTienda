"""El código de máquina: qué computadora es ésta.

Es lo que ata una licencia a una caja concreta. Sin esto, el mismo
`licencia.lic` valdría en cualquier computadora del mundo y un cliente podría
revender el programa sin más trabajo que copiar una carpeta.

Se calcula con dos datos de Windows que no cambian solos:

1. `MachineGuid`, que Windows escribe al instalarse.
2. El número de serie del volumen del disco DEL SISTEMA -no el de donde esté
   la carpeta, para que mover el programa de sitio no invalide la licencia.

Sale un código de doce caracteres en base32, en tres grupos: `A7K2-3M4P-XR7T`.
Base32 no usa 0, 1, 8 ni 9, así que no hay forma de confundir O con 0 ni I
con 1 al dictarlo por teléfono, que es como va a viajar la mitad de las veces.

**Si le reinstalan Windows al cliente, el MachineGuid cambia y hay que
emitirle una licencia nueva.** Es correcto que sea así -es otra instalación-
pero va a pasar, y conviene saberlo de antemano.

Nada de aquí levanta excepciones: si el registro no se deja leer, el programa
tiene que llegar igual a la pantalla de licencia para poder explicarlo.
"""

import base64
import ctypes
import hashlib
import os

SAL = b"MiTienda-v1"


def _limpiar_guid(guid):
    """El GUID sin llaves y en minúsculas.

    Según la versión de Windows viene de una forma o de otra, y dos formas
    del mismo GUID no pueden dar dos códigos distintos.
    """
    if not guid:
        return None
    limpio = str(guid).strip().strip("{}").lower()
    return limpio or None


def huella_de(machine_guid, serie_volumen):
    """El código de máquina de una computadora con estos dos datos.

    Es la parte pura y probable: entran dos datos, sale un código. Quien los
    va a buscar de verdad es `codigo_de_esta_maquina()`.

    Cada combinación de datos disponibles lleva su propia sal, para que una
    máquina donde falle el registro no pueda dar por casualidad el mismo
    código que otra donde sí se lea.
    """
    guid = _limpiar_guid(machine_guid)
    serie = None if serie_volumen is None else str(serie_volumen).encode("ascii")

    if guid and serie:
        material = SAL + b"|" + guid.encode("ascii") + b"|" + serie
    elif serie:
        material = SAL + b"-sin-guid|" + serie
    elif guid:
        material = SAL + b"-sin-disco|" + guid.encode("ascii")
    else:
        # Sin ningún dato no hay computadora que identificar. Devolver un
        # código fijo aquí sería repartir una llave maestra: todas las
        # máquinas sin datos compartirían licencia.
        return ""

    digesto = hashlib.sha256(material).digest()
    codigo = base64.b32encode(digesto).decode("ascii")[:12]
    return f"{codigo[:4]}-{codigo[4:8]}-{codigo[8:12]}"


def _machine_guid():
    """El MachineGuid del registro, o None si no se puede leer.

    Se abre con KEY_WOW64_64KEY a propósito: sin eso, un Python de 32 bits
    acabaría leyendo la rama WOW6432Node, que es otra, y el código cambiaría
    según con qué se hubiera compilado el programa.
    """
    try:
        import winreg
    except ImportError:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\Cryptography", 0,
                            winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as clave:
            valor, _tipo = winreg.QueryValueEx(clave, "MachineGuid")
            return valor
    except OSError:
        return None


def _serie_del_volumen_del_sistema():
    """El número de serie del volumen donde está Windows, o None."""
    try:
        raiz = os.environ.get("SystemDrive", "C:") + "\\"
        serie = ctypes.c_ulong(0)
        ok = ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(raiz), None, 0, ctypes.byref(serie), None, None, None, 0)
        return serie.value if ok else None
    except (AttributeError, OSError, ValueError):
        return None


def codigo_de_esta_maquina():
    """El código de la computadora donde está corriendo esto.

    Cadena vacía si no se pudo averiguar nada, y entonces ninguna licencia va
    a casar: el programa se queda en la pantalla de licencia, que es donde
    tiene que quedarse si no sabe ni en qué máquina está.
    """
    return huella_de(_machine_guid(), _serie_del_volumen_del_sistema())
