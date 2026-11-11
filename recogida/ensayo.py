"""La foto de una base y la comparación de dos fotos, para el ensayo de varias recogidas seguidas
sobre la misma copia (docs/ciclo_de_vida.md, «Cómo se prueba»).

Una recogida de ensayo sola no ve lo que cambia de una hora a la siguiente: el vaivén de
EODI-2026-00770 y 00773 (9 y 10 de noviembre de 2026) solo estaba en el historial. Con una foto
antes y otra después de cada recogida se ve qué fichas nacen, cuáles desaparecen, qué se une o se
separa, qué dato cambia en cada ficha y cuántas versiones nuevas quedan; la segunda recogida y las
siguientes, sin noticias nuevas, no tienen que cambiar nada.

Solo lee: la base, en modo de solo lectura.

Uso:
    python -m recogida.ensayo foto --base <eodi.sqlite> [--publicacion <carpeta>] --salida f.json
    python -m recogida.ensayo comparar antes.json despues.json [--salida informe.md]
        [--sin-cambios]      sale con 1 si alguna ficha cambia (la segunda recogida y siguientes)
"""

import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path
from typing import Any

from esquema import Documento

registro = logging.getLogger(__name__)

FICHEROS = {"incidentes.geojson": "features", "incidentes_sin_ubicacion.json": "incidentes"}
# Lo que se compara de cada ficha: lo grave (docs/ciclo_de_vida.md).
CAMPOS = (
    "inicio", "lugar", "drones", "presencia", "tipo", "estado", "titulo", "cierre", "fuentes",
    "fusionado_en", "retirado", "relacionados",
)  # fmt: skip
MAX_LISTA = 60


def _vista(documento: Documento) -> Documento:
    """Lo que se compara de una ficha."""
    lugar = documento.get("lugar") or {}
    tiempo = documento.get("tiempo") or {}
    cierre = (documento.get("consecuencias") or {}).get("cierre") or {}
    return {
        "inicio": (tiempo.get("inicio") or {}).get("valor"),
        "lugar": {
            "pais": lugar.get("pais"),
            "nivel": lugar.get("nivel"),
            "localidad": lugar.get("localidad"),
            "region": lugar.get("region"),
            "punto": lugar.get("punto"),
        },
        "drones": {
            "numero": (documento.get("drones") or {}).get("numero"),
            "modelo": (documento.get("drones") or {}).get("modelo"),
        },
        "presencia": documento.get("presencia_dron"),
        "tipo": documento.get("tipo"),
        "estado": (documento.get("estado") or {}).get("actual"),
        "titulo": documento.get("titulo"),
        "cierre": {"valor": cierre.get("valor"), "minutos": cierre.get("minutos")},
        "fuentes": len(documento.get("fuentes") or []),
        "fusionado_en": documento.get("fusionado_en"),
        "retirado": "retirado" in documento,
        "relacionados": sorted(str(r.get("id")) for r in documento.get("relacionados") or []),
    }


def _hay_tabla(conexion: sqlite3.Connection, tabla: str) -> bool:
    fila = conexion.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (tabla,)
    ).fetchone()
    return fila is not None


def _cuenta(conexion: sqlite3.Connection, sql: str) -> int:
    return int(conexion.execute(sql).fetchone()[0])


def _publicados(carpeta: Path | None) -> Documento:
    """Lo que hay en los ficheros publicados: las fichas, las unidas y las retiradas."""
    if carpeta is None:
        return {}
    fichas: dict[str, Documento] = {}
    unidos: dict[str, str] = {}
    retirados: list[str] = []
    for nombre, lista in FICHEROS.items():
        ruta = carpeta / nombre
        if not ruta.exists():
            continue
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        unidos.update(datos.get("unidos") or {})
        retirados += sorted(datos.get("retirados") or {})
        for entrada in datos.get(lista) or []:
            propio = entrada.get("properties", entrada)
            id_ = str(entrada.get("id") or propio.get("id"))
            fichas[id_] = _vista(propio)
    return {"fichas": fichas, "unidos": unidos, "retirados": sorted(set(retirados))}


def foto(base: Path, publicacion: Path | None = None) -> Documento:
    """Lo que hay en la base (y, con `publicacion`, en los ficheros publicados) para compararlo
    después: cada ficha con sus datos graves y los recuentos de lo que nunca puede perderse."""
    conexion = sqlite3.connect(f"{base.resolve().as_uri()}?mode=ro", uri=True)
    try:
        fichas = {
            str(id_): _vista(json.loads(documento))
            for id_, documento in conexion.execute("SELECT id, documento FROM incidentes")
        }
        fusiones = [
            {"absorbido": a, "destino": d, "revertida": bool(r)}
            for a, d, r in conexion.execute(
                "SELECT absorbido, destino, revertida FROM fusiones ORDER BY id"
            )
        ]
        separaciones = sorted(
            str(f[0]).removeprefix("revisados:separar:")
            for f in conexion.execute(
                "SELECT fuente_id FROM cursores WHERE fuente_id LIKE 'revisados:separar:%'"
            )
        )
        publicado: dict[str, str] = {}
        if _hay_tabla(conexion, "publicado"):
            publicado = {
                str(i): str(e) for i, e in conexion.execute("SELECT id, estado FROM publicado")
            }
        resultado: Documento = {
            "fichas": fichas,
            "fusiones": fusiones,
            "separaciones": separaciones,
            "publicado": publicado,
            "recuentos": {
                "incidentes": len(fichas),
                "versiones": _cuenta(
                    conexion, "SELECT count(*) FROM historial WHERE tabla = 'incidentes'"
                ),
                "ultima_version": _cuenta(
                    conexion,
                    "SELECT coalesce(max(id), 0) FROM historial WHERE tabla = 'incidentes'",
                ),
                "decisiones": _cuenta(conexion, "SELECT count(*) FROM control_fichas"),
                "fusiones": len(fusiones),
                "afirmaciones": _cuenta(conexion, "SELECT count(*) FROM afirmaciones"),
                "llamadas": _cuenta(
                    conexion, "SELECT coalesce(max(id), 0) FROM llamadas_extractor"
                ),
            },
            "gasto": float(
                conexion.execute(
                    "SELECT coalesce(sum(coste), 0) FROM llamadas_extractor"
                ).fetchone()[0]
            ),
        }
    finally:
        conexion.close()
    resultado["publicacion"] = _publicados(publicacion)
    return resultado


def _activa(vista: Documento) -> bool:
    return not vista.get("fusionado_en") and not vista.get("retirado")


def _cambios(antes: dict[str, Documento], despues: dict[str, Documento]) -> dict[str, Documento]:
    """{ficha: {campo: [antes, después]}} de las fichas que están en las dos fotos."""
    resultado: dict[str, Documento] = {}
    for id_ in sorted(set(antes) & set(despues)):
        distintos = {
            campo: [antes[id_].get(campo), despues[id_].get(campo)]
            for campo in CAMPOS
            if antes[id_].get(campo) != despues[id_].get(campo)
        }
        if distintos:
            resultado[id_] = distintos
    return resultado


def comparar(antes: Documento, despues: Documento) -> Documento:
    """Lo que cambia entre dos fotos: fichas nuevas, desaparecidas, uniones, separaciones, cambios
    por campo, versiones nuevas y, si las fotos traen la publicación, lo mismo en lo publicado."""
    a, d = antes["fichas"], despues["fichas"]
    vivas_antes = {i for i, v in a.items() if _activa(v)}
    vivas_despues = {i for i, v in d.items() if _activa(v)}
    hechas = {(f["absorbido"], f["destino"]) for f in antes["fusiones"] if not f["revertida"]}
    ahora = {(f["absorbido"], f["destino"]) for f in despues["fusiones"] if not f["revertida"]}
    cambios = _cambios(a, d)
    por_campo: dict[str, list[str]] = {}
    for id_, distintos in cambios.items():
        for campo in distintos:
            por_campo.setdefault(campo, []).append(id_)
    pub_a = (antes.get("publicacion") or {}).get("fichas") or {}
    pub_d = (despues.get("publicacion") or {}).get("fichas") or {}
    unidos_d = (despues.get("publicacion") or {}).get("unidos") or {}
    retirados_d = set((despues.get("publicacion") or {}).get("retirados") or [])
    resultado: Documento = {
        "nuevas": sorted(set(d) - set(a)),
        "desaparecidas": sorted(vivas_antes - vivas_despues),
        "perdidas": sorted(set(a) - set(d)),
        "uniones": sorted(f"{x}→{y}" for x, y in ahora - hechas),
        "uniones_deshechas": sorted(f"{x}→{y}" for x, y in hechas - ahora),
        "separaciones": sorted(set(despues["separaciones"]) - set(antes["separaciones"])),
        "cambios": cambios,
        "por_campo": {c: ids for c, ids in sorted(por_campo.items())},
        "versiones_nuevas": despues["recuentos"]["versiones"] - antes["recuentos"]["versiones"],
        "recuentos": {
            clave: [antes["recuentos"].get(clave), despues["recuentos"].get(clave)]
            for clave in sorted(set(antes["recuentos"]) | set(despues["recuentos"]))
        },
        "gasto": round(float(despues.get("gasto", 0)) - float(antes.get("gasto", 0)), 4),
        "publicacion": {
            "nuevas": sorted(set(pub_d) - set(pub_a)),
            "fuera": sorted(set(pub_a) - set(pub_d)),
            # Las que salen de lo publicado sin que su dirección lleve a ningún sitio: nunca.
            "sin_direccion": sorted(
                i for i in set(pub_a) - set(pub_d) if i not in unidos_d and i not in retirados_d
            ),
            "cambios": _cambios(pub_a, pub_d),
        },
    }
    return resultado


def sin_cambios(diferencias: Documento) -> bool:
    """Entre las dos fotos no cambió ninguna ficha, ni en la base ni en lo publicado, ni quedó
    ninguna versión nueva: lo que tiene que pasar en una recogida sin noticias nuevas."""
    publicacion = diferencias["publicacion"]
    return not (
        diferencias["nuevas"]
        or diferencias["desaparecidas"]
        or diferencias["perdidas"]
        or diferencias["uniones"]
        or diferencias["uniones_deshechas"]
        or diferencias["separaciones"]
        or diferencias["cambios"]
        or diferencias["versiones_nuevas"]
        or publicacion["nuevas"]
        or publicacion["fuera"]
        or publicacion["cambios"]
    )


def _corto(valor: Any) -> str:
    texto = json.dumps(valor, ensure_ascii=False, sort_keys=True)
    return texto if len(texto) <= 110 else texto[:109] + "…"


def _lista(ids: list[str]) -> str:
    if not ids:
        return "ninguna"
    resto = f" y {len(ids) - MAX_LISTA} más" if len(ids) > MAX_LISTA else ""
    return ", ".join(ids[:MAX_LISTA]) + resto


def informe(diferencias: Documento, titulo: str = "Diferencias") -> str:
    """El informe en texto (Markdown) de una comparación."""
    d = diferencias
    lineas = [
        f"## {titulo}",
        "",
        f"- Fichas nuevas ({len(d['nuevas'])}): {_lista(d['nuevas'])}",
        f"- Fichas que dejan de estar activas ({len(d['desaparecidas'])}): "
        f"{_lista(d['desaparecidas'])}",
        f"- Fichas perdidas de la base ({len(d['perdidas'])}): {_lista(d['perdidas'])}",
        f"- Uniones ({len(d['uniones'])}): {_lista(d['uniones'])}",
        f"- Uniones deshechas ({len(d['uniones_deshechas'])}): {_lista(d['uniones_deshechas'])}",
        f"- Separaciones ({len(d['separaciones'])}): {_lista(d['separaciones'])}",
        f"- Fichas con algún dato cambiado: {len(d['cambios'])}",
        f"- Versiones nuevas en el historial de las fichas: {d['versiones_nuevas']}",
        f"- Gasto del modelo: {d['gasto']} USD",
        "",
        "### Cambios por campo",
        "",
    ]
    lineas += [f"- {campo} ({len(ids)}): {_lista(ids)}" for campo, ids in d["por_campo"].items()]
    if not d["por_campo"]:
        lineas.append("Ninguno.")
    lineas += ["", "### Detalle", ""]
    for id_, distintos in list(d["cambios"].items())[:MAX_LISTA]:
        for campo, (antes, despues) in distintos.items():
            lineas.append(f"- {id_} · {campo}: {_corto(antes)} → {_corto(despues)}")
    if not d["cambios"]:
        lineas.append("Ninguno.")
    p = d["publicacion"]
    lineas += [
        "",
        "### En lo publicado",
        "",
        f"- Fichas que entran ({len(p['nuevas'])}): {_lista(p['nuevas'])}",
        f"- Fichas que salen ({len(p['fuera'])}): {_lista(p['fuera'])}",
        f"- De ellas, sin dirección (ni unidas ni retiradas) ({len(p['sin_direccion'])}): "
        f"{_lista(p['sin_direccion'])}",
        f"- Fichas publicadas con algún dato cambiado: {len(p['cambios'])}",
    ]
    for id_, distintos in list(p["cambios"].items())[:MAX_LISTA]:
        for campo, (antes, despues) in distintos.items():
            lineas.append(f"  - {id_} · {campo}: {_corto(antes)} → {_corto(despues)}")
    lineas += ["", "### Recuentos (antes → después)", ""]
    lineas += [f"- {clave}: {a} → {b}" for clave, (a, b) in d["recuentos"].items()]
    return "\n".join(lineas) + "\n"


def principal(argumentos: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    analizador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = analizador.add_subparsers(dest="orden", required=True)
    f = sub.add_parser("foto")
    f.add_argument("--base", type=Path, required=True)
    f.add_argument("--publicacion", type=Path)
    f.add_argument("--salida", type=Path, required=True)
    c = sub.add_parser("comparar")
    c.add_argument("antes", type=Path)
    c.add_argument("despues", type=Path)
    c.add_argument("--salida", type=Path)
    c.add_argument("--titulo", default="Diferencias")
    c.add_argument("--sin-cambios", action="store_true")
    args = analizador.parse_args(argumentos)
    if args.orden == "foto":
        datos = foto(args.base, args.publicacion)
        args.salida.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
        registro.info("foto de %d fichas en %s", len(datos["fichas"]), args.salida)
        return 0
    antes = json.loads(args.antes.read_text(encoding="utf-8"))
    despues = json.loads(args.despues.read_text(encoding="utf-8"))
    diferencias = comparar(antes, despues)
    texto = informe(diferencias, args.titulo)
    if args.salida is not None:
        args.salida.write_text(texto, encoding="utf-8")
    else:
        sys.stdout.write(texto)
    iguales = sin_cambios(diferencias)
    registro.info("%s: %s", args.titulo, "sin cambios" if iguales else "con cambios")
    return 1 if args.sin_cambios and not iguales else 0


if __name__ == "__main__":
    sys.exit(principal())
