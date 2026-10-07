"""Lo que se publica del tipo de dron de un incidente (web y páginas de texto).

Solo lo identificado por la autoridad y lo deducido que se publica (calculo.publicable), con las
razones que han pesado. Una cita sale solo si su fuente es una de las fuentes públicas del
incidente (la ficha la enlaza); si no, la razón sale sin cita y lo identificado no sale.
"""

from typing import Any

from esquema import Documento

DATOS_PUBLICOS = ("rasgo", "valor", "cita", "fuente", "distancia_km", "mas_de_600_km",
                  "costa_km", "entrada_exterior", "kmh", "metros", "minutos")  # fmt: skip


def _datos(datos: dict[str, Any], fuentes: set[str]) -> dict[str, Any]:
    publicos = {k: v for k, v in datos.items() if k in DATOS_PUBLICOS and v is not None}
    if publicos.get("fuente") not in fuentes:
        publicos.pop("cita", None)
        publicos.pop("fuente", None)
    return publicos


def presentado(publicado: Documento) -> Documento:
    """Lo deducido tal como se enseña: con «compatible_guerra», los grupos sin porcentajes (las
    probabilidades se quedan en la base y en la exportación, con su regla de origen)."""
    if publicado.get("presentacion") != "compatible_guerra":
        return dict(publicado)
    salida: Documento = {
        "presentacion": "compatible_guerra",
        "compatible": [{"grupo": c["grupo"]} for c in publicado["compatible"]],
    }
    if "casos_referencia" in publicado:
        salida["casos_referencia"] = publicado["casos_referencia"]
    return salida


def bloque(tipo: Documento | None, incidente: Documento) -> Documento | None:
    if not tipo or (tipo.get("retirado") and "publicado" not in tipo):
        return None
    from exportacion.proyeccion import fuente_publica
    from proceso.estados import Capa

    fuentes = {f["id"] for f in incidente.get("fuentes", []) if fuente_publica(f, Capa.GENERAL)}
    salida: Documento = {"version": tipo["version"]}
    identificado = tipo.get("identificado")
    if identificado and identificado.get("fuente") in fuentes:
        salida["identificado"] = {k: identificado[k] for k in ("modelo", "grupo", "cita", "fuente")}
    elif "publicado" in tipo:
        salida["publicado"] = presentado(tipo["publicado"])
        salida["razones"] = [
            {
                "tipo": r["tipo"],
                "clave": r["clave"],
                **({"datos": _datos(r["datos"], fuentes)} if r.get("datos") else {}),
            }
            for r in tipo.get("razones", [])
        ]
    else:
        return None
    return salida


def recorrido_publico(tipo: Documento | None, incidente: Documento) -> Documento | None:
    """El recorrido de la incursión según la autoridad, si su fuente es pública."""
    if not tipo or "recorrido" not in tipo:
        return None
    from exportacion.proyeccion import fuente_publica
    from proceso.estados import Capa

    recorrido = tipo["recorrido"]
    publicas = {f["id"] for f in incidente.get("fuentes", []) if fuente_publica(f, Capa.GENERAL)}
    if recorrido["fuente"] not in publicas:
        return None
    return {k: v for k, v in recorrido.items() if k != "velocidad"}
