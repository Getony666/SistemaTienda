"""Salida de emergencia: devolver el acceso cuando se olvida el PIN de Admin.

Si en una tienda pierden el PIN del Admin y no queda otro, no hay forma de
entrar a administrar el programa. Esto lo arregla desde la propia máquina.

    python restablecer_admin.py                    # sobre tienda.db de al lado
    python restablecer_admin.py C:\\ruta\\tienda.db  # sobre otra

No debilita nada que no estuviera ya abierto: quien puede ejecutar esto es
quien tiene el fichero de la base delante, y con el fichero delante siempre
se pudo hacer lo mismo a mano. El PIN se guarda cifrado; esto no lo lee, lo
sustituye por otro.

Deja constancia en el historial, para que el cambio no pase inadvertido.
"""

import getpass
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

from lddl import rutas, usuarios  # noqa: E402
from lddl.esquema import preparar_base  # noqa: E402
from lddl.historial import registrar_historial  # noqa: E402


def main():
    ruta_db = sys.argv[1] if len(sys.argv) > 1 else os.path.join(AQUI, "tienda.db")
    ruta_db = os.path.abspath(ruta_db)
    if not os.path.exists(ruta_db):
        sys.exit(f"No existe: {ruta_db}")

    rutas.fijar_directorio_base(os.path.dirname(ruta_db))
    preparar_base()

    print(f"Base: {ruta_db}\n")
    admins = [u for u in usuarios.listar_usuarios(incluir_inactivos=True)
              if u["rol"] == usuarios.ADMIN]

    if admins:
        print("Administradores:")
        for i, u in enumerate(admins, 1):
            estado = "" if u["activo"] else "  (desactivado)"
            print(f"  {i}. {u['nombre']}{estado}")
        elegido = input("\n¿A cuál le pones PIN nuevo? (número, o Enter para salir): ").strip()
        if not elegido:
            sys.exit("Cancelado.")
        try:
            usuario = admins[int(elegido) - 1]
        except (ValueError, IndexError):
            sys.exit("Ese número no está en la lista.")
        nombre = usuario["nombre"]
    else:
        print("No hay ningún Admin. Se va a crear uno.")
        nombre = input("Nombre del Admin nuevo: ").strip()
        if not nombre:
            sys.exit("Cancelado.")
        usuario = None

    pin = getpass.getpass("PIN nuevo (mínimo 4): ")
    if pin != getpass.getpass("Repítelo: "):
        sys.exit("Los dos PIN no coinciden. No se ha cambiado nada.")

    if usuario:
        exito, mensaje = usuarios.restablecer_pin(usuario["id"], pin)
        if exito and not usuario["activo"]:
            # De poco sirve el PIN si el usuario está apagado.
            with rutas.transaccion() as (_conexion, cursor):
                cursor.execute("UPDATE usuarios SET activo = 1 WHERE id = ?",
                               (usuario["id"],))
            mensaje += " (y se ha reactivado)"
    else:
        exito, mensaje = usuarios.crear_usuario(nombre, usuarios.ADMIN, pin)

    if not exito:
        sys.exit(mensaje)

    registrar_historial(
        "Restablecimiento de acceso",
        f"PIN de Admin restablecido para {nombre} desde restablecer_admin.py")
    print(f"\n{mensaje}")
    print("Ya puedes entrar en el programa con ese PIN.")


if __name__ == "__main__":
    main()
