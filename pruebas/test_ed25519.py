"""Ed25519 en Python puro, contra los vectores oficiales del RFC 8032.

Esto es lo primero que hay que probar de todo el sistema de licencias, y es
innegociable: una implementación de curva escrita a mano y no comparada con
vectores conocidos puede aceptar firmas falsas sin que nadie se entere. Si
este fichero no está en verde, nada de lo demás significa nada.

Los vectores salen de la sección 7.1 del RFC 8032 (§ "Test Vectors for
Ed25519"). No se tocan: son el patrón, no un dato del proyecto.

No abre la base de datos: `mitienda/ed25519.py` no toca disco ni red.

    python -m unittest discover -s pruebas -v
"""

import binascii
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mitienda.ed25519 import verificar  # noqa: E402


def octetos(hexadecimal):
    return binascii.unhexlify(hexadecimal.replace(" ", "").replace("\n", ""))


# RFC 8032, sección 7.1. Cada entrada: (llave privada, llave pública, mensaje, firma).
VECTORES_RFC_8032 = (
    (
        "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
        "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
        "",
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8"
        "821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b",
    ),
    (
        "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
        "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
        "72",
        "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085a"
        "c1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00",
    ),
    (
        "c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
        "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025",
        "af82",
        "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac18ff"
        "9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a",
    ),
    (
        "833fe62409237b9d62ec77587520911e9a759cec1d19755b7da901b96dca3d42",
        "ec172b93ad5e563bf4932c70e1245034c35467ef2efd4d64ebf819683467e2bf",
        "ddaf35a193617abacc417349ae20413112e6fa4e89a97ea20a9eeee64b55d39a2192"
        "992a274fc1a836ba3c23a3feebbd454d4423643ce80e2a9ac94fa54ca49f",
        "dc2a4459e7369633a52b1bf277839a00201009a3efbf3ecb69bea2186c26b5890935"
        "1fc9ac90b3ecfdfbc7c66431e0303dca179c138ac17ad9bef1177331a704",
    ),
)


class LosVectoresDelRFC(unittest.TestCase):
    """La prueba que decide si esta implementación sirve o no sirve."""

    def test_las_cuatro_firmas_oficiales_se_aceptan(self):
        for i, (_privada, publica, mensaje, firma) in enumerate(VECTORES_RFC_8032, 1):
            with self.subTest(vector=i):
                self.assertTrue(
                    verificar(octetos(publica), octetos(mensaje), octetos(firma)),
                    f"el vector {i} del RFC 8032 tendria que valer")


class LoQueNoDebeAceptarse(unittest.TestCase):
    """Aceptar una firma mala es peor que rechazar una buena: sería regalar
    el generador de licencias a cualquiera que sepa editar un fichero."""

    def setUp(self):
        _privada, publica, mensaje, firma = VECTORES_RFC_8032[2]
        self.publica = octetos(publica)
        self.mensaje = octetos(mensaje)
        self.firma = octetos(firma)

    def test_una_firma_con_un_bit_cambiado_no_vale(self):
        alterada = bytearray(self.firma)
        alterada[0] ^= 0x01
        self.assertFalse(verificar(self.publica, self.mensaje, bytes(alterada)))

    def test_un_bit_cambiado_al_final_de_la_firma_tampoco(self):
        """El último byte es parte del escalar; un fallo aquí es fácil de
        pasar por alto si sólo se prueba tocando el principio."""
        alterada = bytearray(self.firma)
        alterada[-1] ^= 0x01
        self.assertFalse(verificar(self.publica, self.mensaje, bytes(alterada)))

    def test_un_mensaje_cambiado_no_vale(self):
        self.assertFalse(verificar(self.publica, b"otra cosa", self.firma))

    def test_otra_llave_publica_no_vale(self):
        otra = octetos(VECTORES_RFC_8032[1][1])
        self.assertFalse(verificar(otra, self.mensaje, self.firma))

    def test_una_firma_que_no_mide_64_octetos_no_vale(self):
        self.assertFalse(verificar(self.publica, self.mensaje, self.firma[:63]))
        self.assertFalse(verificar(self.publica, self.mensaje, self.firma + b"\x00"))

    def test_una_llave_que_no_mide_32_octetos_no_vale(self):
        self.assertFalse(verificar(self.publica[:31], self.mensaje, self.firma))

    def test_una_llave_publica_que_no_es_un_punto_de_la_curva_no_vale(self):
        """Verificar tiene que decir "no" y no reventar: el fichero de
        licencia lo puede haber tocado cualquiera, y una excepción sin
        recoger dejaría el programa sin arrancar."""
        basura = b"\xff" * 32
        self.assertFalse(verificar(basura, self.mensaje, self.firma))

    def test_nada_de_esto_levanta_excepciones(self):
        for llave, mensaje, firma in (
            (b"", b"", b""),
            (b"\x00" * 32, b"hola", b"\x00" * 64),
            (self.publica, self.mensaje, b"\xff" * 64),
        ):
            with self.subTest(firma=firma[:4]):
                self.assertFalse(verificar(llave, mensaje, firma))


if __name__ == "__main__":
    unittest.main()
