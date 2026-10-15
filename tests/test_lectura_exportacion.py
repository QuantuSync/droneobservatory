"""Credencial de solo lectura de la exportación para AEGIS (almacen/lectura_exportacion.py): la
política del bucket y la comprobación de su alcance, sin red."""

import hashlib
import json
import urllib.request

import pytest

from almacen import copias, exportaciones, lectura_exportacion

NS = "http://s3.amazonaws.com/doc/2006-03-01/"
CIFRADO = b"cifrado"
MANIFIESTO = json.dumps({"ficheros": [{"cifrado": {
    "nombre": "a.jsonl.gz.age", "bytes": len(CIFRADO),
    "sha256": hashlib.sha256(CIFRADO).hexdigest()}}]}).encode()  # fmt: skip


def test_la_politica_solo_da_lectura_y_conserva_las_demas_declaraciones() -> None:
    principal = lectura_exportacion.principal_de("123", "ABCDEF")
    assert principal == "arn:aws:iam:::user/p123:ABCDEF"
    actual = {"Statement": [{"Sid": "Otra"}, {"Sid": lectura_exportacion.SID, "Action": ["s3:*"]}]}
    datos = json.loads(lectura_exportacion.politica("b", "exportaciones/", principal, actual))
    assert [d["Sid"] for d in datos["Statement"]] == ["Otra", lectura_exportacion.SID]
    nueva = datos["Statement"][1]
    assert nueva["Action"] == ["s3:GetObject", "s3:ListBucket"]
    assert nueva["Principal"] == {"AWS": [principal]}
    assert nueva["Resource"] == ["arn:aws:s3:::b", "arn:aws:s3:::b/exportaciones/*"]


def test_un_principal_raro_no_se_acepta() -> None:
    with pytest.raises(ValueError):
        lectura_exportacion.principal_de("12a", "ABC")


def transporte(lee_otros: bool) -> copias.Enviar:
    """Un almacén que deja leer el bucket de la exportación y nada más (o, con `lee_otros`, como
    la credencial del proyecto, que lo puede todo)."""

    def enviar(peticion: urllib.request.Request) -> copias.Respuesta:
        url = peticion.full_url
        propio = "/prueba-exportaciones" in url
        if not propio and not lee_otros:
            return copias.Respuesta(403, {}, b"")
        if peticion.get_method() in ("PUT", "DELETE"):
            return copias.Respuesta(204 if lee_otros else 403, {}, b"")
        if "list-type" in url:
            clave = "exportaciones/2026.10.12/manifiesto.json"
            cuerpo = (f'<ListBucketResult xmlns="{NS}"><Contents><Key>{clave}</Key>'
                      "<Size>1</Size></Contents></ListBucketResult>")  # fmt: skip
            return copias.Respuesta(200, {}, cuerpo.encode())
        if url.endswith("manifiesto.json"):
            return copias.Respuesta(200, {}, MANIFIESTO)
        return copias.Respuesta(200, {}, CIFRADO)

    return enviar


def test_la_comprobacion_pasa_con_solo_lectura_y_falla_si_puede_escribir() -> None:
    credenciales = copias.Credenciales("id", "secreto")
    resultados = lectura_exportacion.comprobar(credenciales, transporte(lee_otros=False))
    assert resultados and all(bien for _, bien, _ in resultados), resultados
    destinos = {d.bucket for d in lectura_exportacion._otros_destinos()}
    assert exportaciones.destino().bucket not in destinos
    assert {"prueba-base", "prueba-archivo"} <= destinos
    todo = lectura_exportacion.comprobar(credenciales, transporte(lee_otros=True))
    assert not all(bien for _, bien, _ in todo)
