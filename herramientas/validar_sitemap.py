"""Valida el sitemap de la web contra el esquema oficial de sitemaps.org (docs/posicionamiento.md).

    python herramientas/validar_sitemap.py [dirección o fichero del sitemap]

Necesita lxml (`pip install lxml`). El esquema de sitemaps.org admite elementos de otros espacios de
nombres solo si están declarados (processContents="strict"): para los enlaces a la otra versión
(`xhtml:link`) se declara aquí su forma mínima (rel, hreflang y href), la que documenta Google.
Además comprueba que no hay direcciones repetidas, que todas son del dominio y que cada una trae su
versión en español, en inglés y la de por defecto (x-default). Sale con 0 si todo está bien.
"""

from __future__ import annotations

import sys
import tempfile
import urllib.request
from pathlib import Path

from lxml import etree

ESQUEMA = "https://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd"
SITEMAP = "https://droneobservatory.eu/sitemap.xml"
DOMINIO = "https://droneobservatory.eu/"
XHTML = """<?xml version="1.0" encoding="UTF-8"?>
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
  targetNamespace="http://www.w3.org/1999/xhtml" elementFormDefault="qualified">
  <xsd:element name="link">
    <xsd:complexType>
      <xsd:attribute name="rel" type="xsd:string" use="required"/>
      <xsd:attribute name="hreflang" type="xsd:string" use="required"/>
      <xsd:attribute name="href" type="xsd:anyURI" use="required"/>
    </xsd:complexType>
  </xsd:element>
</xsd:schema>
"""
ENVOLTORIO = """<?xml version="1.0" encoding="UTF-8"?>
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <xsd:import namespace="http://www.sitemaps.org/schemas/sitemap/0.9" schemaLocation="sitemap.xsd"/>
  <xsd:import namespace="http://www.w3.org/1999/xhtml" schemaLocation="xhtml.xsd"/>
</xsd:schema>
"""
AGENTE = {"User-Agent": "EODI-bot/1.0 (+https://droneobservatory.eu)"}


def leer(origen: str) -> bytes:
    if origen.startswith("http"):
        peticion = urllib.request.Request(origen, headers=AGENTE)
        with urllib.request.urlopen(peticion, timeout=60) as r:
            datos: bytes = r.read()
            return datos
    return Path(origen).read_bytes()


def principal(argumentos: list[str]) -> int:
    origen = argumentos[0] if argumentos else SITEMAP
    documento = etree.fromstring(leer(origen))
    with tempfile.TemporaryDirectory() as carpeta:
        raiz = Path(carpeta)
        (raiz / "sitemap.xsd").write_bytes(leer(ESQUEMA))
        (raiz / "xhtml.xsd").write_text(XHTML, encoding="utf-8")
        (raiz / "todo.xsd").write_text(ENVOLTORIO, encoding="utf-8")
        esquema = etree.XMLSchema(etree.parse(str(raiz / "todo.xsd")))
    errores: list[str] = []
    if not esquema.validate(documento):
        errores += [f"esquema, línea {e.line}: {e.message}" for e in esquema.error_log][:20]
    espacios = {
        "s": "http://www.sitemaps.org/schemas/sitemap/0.9",
        "x": "http://www.w3.org/1999/xhtml",
    }
    locs = [str(t) for t in documento.xpath("//s:url/s:loc/text()", namespaces=espacios)]
    if len(locs) != len(set(locs)):
        errores.append("hay direcciones repetidas")
    errores += [f"fuera del dominio: {u}" for u in locs if not u.startswith(DOMINIO)][:5]
    for url in documento.xpath("//s:url", namespaces=espacios):
        idiomas = {str(i) for i in url.xpath("x:link/@hreflang", namespaces=espacios)}
        if idiomas != {"es", "en", "x-default"}:
            errores.append(f"sin sus tres versiones: {url.findtext('s:loc', namespaces=espacios)}")
            break
    print(f"{len(locs)} direcciones; {'sin errores' if not errores else f'{len(errores)} errores'}")
    for error in errores:
        print(" -", error)
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))
