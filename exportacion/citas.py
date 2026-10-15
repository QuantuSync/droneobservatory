"""Las citas de las fuentes en lo publicado: su traducción y la que respalda cada dato.

- Cada cita que enseña la web (la frase de cada fuente, la de «Qué dice la fuente», la de la
  investigación, la del tipo de dron y la del recorrido; también las de la capa de Ucrania) lleva
  su traducción al español y al inglés (`traduccion` junto a `frase_origen`, `cita_traduccion`
  junto a `cita`), hecha una sola vez por el control de las fichas (tabla traducciones). La web
  enseña la del idioma de la página y el original debajo, plegado; si no hay traducción, el
  original.
- Cada dato que verificó el control (recogida/control_fichas.py) lleva en «Qué dice la fuente»
  la frase literal que lo respalda, de la fuente que lo dice, si coincide con lo publicado.
- Las citas que se publican sin traducción quedan anotadas (`Pendientes`): el control las
  traduce en su siguiente pasada.
- Las autoridades que no están en configuracion/autoridades.json se traducen igual y van en
  `autoridades` (nombre -> {es, en}); la web no escribe nunca una sin traducir.

Se añade al publicar, sobre lo ya proyectado: la base no cambia.
"""

import hashlib
from dataclasses import dataclass, field
from typing import Any

from esquema import Documento
from proceso import autoridades

# Dato de la verificación -> campo público de «Qué dice la fuente».
CAMPO_PUBLICO = {
    "presencia": "presencia_dron",
    "drones": "drones.numero",
    "cierre": "consecuencias.cierre.valor",
    "duracion_min": "consecuencias.cierre.minutos",
    "dia": "tiempo.inicio",
    "hora": "tiempo.inicio",
}
# Lo que dice la fuente de la presencia y los valores publicados con que casa.
PRESENCIA_CASA = {
    "confirmada": {"confirmada"},
    "posible": {"no_confirmada", "no_acreditada"},
    "no_hallado": {"no_confirmada", "no_acreditada", "descartada"},
    "desmentido": {"no_confirmada", "no_acreditada", "descartada"},
}
MAX_LETRAS_CITA = 600


def huella_texto(texto: str) -> str:
    return hashlib.sha256(" ".join(texto.split()).encode("utf-8")).hexdigest()


@dataclass
class Pendientes:
    """Las citas publicadas que aún no tienen traducción: huella -> (idioma, texto)."""

    europa: dict[str, tuple[str, str]] = field(default_factory=dict)
    ucrania: dict[str, tuple[str, str]] = field(default_factory=dict)

    def documento(self) -> Documento:
        return {
            "europa": {h: list(v) for h, v in self.europa.items()},
            "ucrania": {h: list(v) for h, v in self.ucrania.items()},
        }


def traduccion(texto: str, traducciones: dict[str, Documento]) -> Documento | None:
    entrada = traducciones.get(huella_texto(texto)) if texto else None
    if not entrada or not entrada.get("es") or not entrada.get("en"):
        return None
    return {"es": entrada["es"], "en": entrada["en"]}


def _traducir(
    objeto: Documento, texto_en: str, destino: str, idioma: str,
    traducciones: dict[str, Documento], faltan: dict[str, tuple[str, str]],
) -> None:  # fmt: skip
    texto = str(objeto.get(texto_en) or "").strip()
    if not texto:
        return
    hecha = traduccion(texto, traducciones)
    if hecha is not None:
        objeto[destino] = hecha
    else:
        faltan.setdefault(huella_texto(texto), (idioma, texto[:MAX_LETRAS_CITA]))


def _valor_publicado(publico: Documento, dato: str) -> Any:
    if dato == "presencia":
        return publico.get("presencia_dron")
    if dato == "drones":
        return (publico.get("drones") or {}).get("numero")
    cierre = (publico.get("consecuencias") or {}).get("cierre") or {}
    if dato == "cierre":
        return cierre.get("valor")
    if dato == "duracion_min":
        return cierre.get("minutos")
    return (publico.get("tiempo") or {}).get("inicio")


def _casa(dato: str, verificado: Any, publicado: Any) -> bool:
    if publicado in (None, "desconocido"):
        return False
    if dato == "presencia":
        return publicado in PRESENCIA_CASA.get(str(verificado), set())
    if dato in {"drones", "duracion_min", "cierre"}:
        return bool(verificado == publicado)
    if dato == "dia":
        return bool(str(publicado.get("valor", ""))[:10] == verificado)
    if dato == "hora":
        return bool(publicado.get("precision") in {"hora", "minuto"})
    return False


def con_respaldos(publico: Documento, verificacion: Documento | None) -> None:
    """Las frases de la verificación en «Qué dice la fuente», junto al dato que respaldan."""
    if not verificacion:
        return
    fuentes = {f["id"]: f for f in publico.get("fuentes", [])}
    afirmaciones: list[Documento] = list(publico.get("afirmaciones_publicas", []))
    for dato, (valor, fuente_id, frase) in sorted(verificacion.get("datos", {}).items()):
        campo = CAMPO_PUBLICO.get(dato)
        fuente = fuentes.get(fuente_id)
        publicado = _valor_publicado(publico, dato)
        if campo is None or fuente is None or not _casa(dato, valor, publicado):
            continue
        existente = next(
            (a for a in afirmaciones if a["campo"] == campo and a["fuente_id"] == fuente_id), None
        )
        if existente is not None:
            existente["cita"] = frase
            continue
        afirmaciones.append({
            "campo": campo, "fuente_id": fuente_id, "medio": fuente["medio"],
            "fiabilidad": fuente["fiabilidad"], "credibilidad": fuente["credibilidad"],
            "fecha": fuente["fecha"], "valor": publicado, "cita": frase,
        })  # fmt: skip
    if afirmaciones:
        publico["afirmaciones_publicas"] = sorted(
            afirmaciones, key=lambda a: (a["campo"], a["fecha"]["valor"], a["fuente_id"])
        )


def con_traducciones(
    publico: Documento, traducciones: dict[str, Documento],
    faltan: dict[str, tuple[str, str]] | None = None,
) -> None:  # fmt: skip
    """La traducción de cada cita del incidente, del ataque o del impacto, si la hay; las que
    faltan, en `faltan`."""
    faltan = {} if faltan is None else faltan
    idiomas = {f["id"]: str(f.get("idioma") or "") for f in publico.get("fuentes", [])}
    for fuente in publico.get("fuentes", []):
        _traducir(fuente, "frase_origen", "traduccion", idiomas[fuente["id"]], traducciones, faltan)
    for afirmacion in publico.get("afirmaciones_publicas", []):
        idioma = idiomas.get(str(afirmacion.get("fuente_id")), "")
        _traducir(afirmacion, "cita", "cita_traduccion", idioma, traducciones, faltan)
    for entrada in publico.get("investigacion", []) or []:
        idioma = idiomas.get(str(entrada.get("fuente_id")), "")
        _traducir(entrada, "cita", "cita_traduccion", idioma, traducciones, faltan)
    tipo = publico.get("tipo_dron") or {}
    if tipo.get("identificado"):
        identificado = tipo["identificado"]
        idioma = idiomas.get(str(identificado.get("fuente")), "")
        _traducir(identificado, "cita", "cita_traduccion", idioma, traducciones, faltan)
    for razon in tipo.get("razones", []) or []:
        datos = razon.get("datos") or {}
        if datos.get("cita"):
            idioma = idiomas.get(str(datos.get("fuente")), "")
            _traducir(datos, "cita", "cita_traduccion", idioma, traducciones, faltan)
    recorrido = publico.get("recorrido")
    if recorrido and recorrido.get("cita"):
        idioma = idiomas.get(str(recorrido.get("fuente")), "")
        _traducir(recorrido, "cita", "cita_traduccion", idioma, traducciones, faltan)
    con_autoridades(publico, traducciones, faltan)


def con_autoridades(
    publico: Documento, traducciones: dict[str, Documento], faltan: dict[str, tuple[str, str]]
) -> None:
    """Las autoridades que no están en configuracion/autoridades.json, en español y en inglés
    (`autoridades`: nombre -> {es, en}), para que la web nunca las escriba en otro idioma; las que
    aún no tienen traducción, en `faltan` (con la marca de nombre)."""
    escritas: dict[str, Documento] = {}
    for nombre, idioma in autoridades.por_traducir(publico):
        hecha = traduccion(nombre, traducciones)
        if hecha is not None:
            escritas[nombre] = hecha
        else:
            faltan.setdefault(huella_texto(nombre), (idioma, autoridades.MARCA + nombre))
    if escritas:
        publico["autoridades"] = escritas


def enriquecer_incidentes(
    publicados: list[Documento],
    verificaciones: dict[str, Documento],
    traducciones: dict[str, Documento],
    faltan: dict[str, tuple[str, str]] | None = None,
) -> None:
    """Sobre las propiedades publicadas de cada incidente (in situ)."""
    for publico in publicados:
        con_respaldos(publico, verificaciones.get(str(publico.get("id"))))
        con_traducciones(publico, traducciones, faltan)
