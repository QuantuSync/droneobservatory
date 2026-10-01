"""Exportación semanal para AEGIS: contenido, validación, determinismo, cifrado y subida."""

import gzip
import hashlib
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pyrage
import pytest

from almacen import remoto
from almacen.base import Almacen
from almacen.cifrado import VARIABLE_CLAVE, guardar_cifrada
from esquema import Documento
from exportacion import semanal
from proceso import mediciones
from recogida import estado, exportacion, salud
from tests import ejemplos
from tests.ejemplos import AHORA, VOCABULARIO_MODELOS


@pytest.fixture
def clave(monkeypatch: pytest.MonkeyPatch) -> pyrage.x25519.Identity:
    identidad = pyrage.x25519.Identity.generate()
    monkeypatch.setenv(VARIABLE_CLAVE, str(identidad))
    return identidad


def incidente_con_fuente_e() -> Documento:
    documento = ejemplos.incidente_minimo()
    documento["fuentes"].append(ejemplos.fuente("FE", "E", publica=False))
    documento["afirmaciones"] = [
        {"campo": "drones", "valor": {"min": 2, "max": 2}, "fuente_id": "FE",
         "confianza_extraccion": 0.6},
    ]  # fmt: skip
    return documento


# Lo que respalda la nota oficial F2 del ejemplo completo: todo lo que el ejemplo rellena y
# ninguna fuente dice (sin fuente, un valor no se exporta: no tendría origen).
RESPALDA_F2 = [
    "consecuencias",
    "detalle_oficial",
    "drones",
    "estado",
    "lugar.localidad",
    "pruebas",
    "respuesta",
    "tiempo.fin",
]


def completo_con_fuentes() -> Documento:
    documento = ejemplos.incidente_completo()
    # Como está en la base: procedencia y nivel los calcula la exportación.
    del documento["procedencia"], documento["nivel_detalle"]
    for fuente in documento["fuentes"]:
        if fuente["id"] == "F2":
            fuente["campos_respaldados"] = RESPALDA_F2
    return documento


def poblado() -> Almacen:
    almacen = Almacen.abrir()
    almacen.guardar_incidente(completo_con_fuentes(), AHORA, VOCABULARIO_MODELOS)
    almacen.guardar_incidente(incidente_con_fuente_e(), AHORA, VOCABULARIO_MODELOS)
    ataque = ejemplos.ataque_completo()
    # P2 hace de Ministerio de Defensa ruso: interna fuera de la capa de guerra.
    ataque["fuentes"][1]["campos_respaldados"] = ["derribados"]
    almacen.guardar_ataque_ucrania(ataque, AHORA)
    almacen.guardar_episodio(ejemplos.episodio(), AHORA)
    return almacen


def por_nombre(ficheros: list[semanal.Fichero]) -> dict[str, semanal.Fichero]:
    return {f.nombre: f for f in ficheros}


def lineas(fichero: semanal.Fichero) -> list[Any]:
    return [json.loads(linea) for linea in fichero.contenido.decode("utf-8").splitlines()]


def test_estan_todos_los_ficheros_con_su_esquema() -> None:
    ficheros = por_nombre(semanal.generar(poblado()))
    datos = {
        "incidentes.jsonl", "afirmaciones.jsonl", "episodios.jsonl", "ucrania_ataques.jsonl",
        "ucrania_regiones.jsonl", "frecuencias.json", "descartes.jsonl", "vocabulario.json",
    }  # fmt: skip
    assert datos <= set(ficheros)
    for nombre in datos:
        assert ficheros[ficheros[nombre].esquema].registros == 1, nombre
    assert "esquema/eodi/incidente.schema.json" in ficheros
    assert ficheros["incidentes.jsonl"].registros == 2


def test_los_incidentes_salen_enteros_con_los_campos_internos() -> None:
    almacen = poblado()
    exportados = lineas(por_nombre(semanal.generar(almacen))["incidentes.jsonl"])
    # Como están en la base, más su procedencia y su nivel de detalle: un campo interno nuevo
    # del esquema entra sin tocar código si sus fuentes dicen que lo respaldan.
    sin_anadidos = [
        {k: v for k, v in e.items() if k not in {"procedencia", "nivel_detalle"}}
        for e in exportados
    ]
    assert sin_anadidos == almacen.incidentes()
    assert "pruebas" in exportados[0] and "alta" in exportados[0]["control"]


def test_el_foco_termico_va_completo_con_lo_interno() -> None:
    """El cruce con FIRMS vive en su tabla: AEGIS recibe el bloque entero, también un no
    detectado con su motivo, que la web nunca ve."""
    almacen = poblado()
    no_detectado = {
        "resultado": "no_detectado", "motivo": "sin_focos", "radio_km": 10,
        "focos_en_ventana": 0, "linea_base": {"focos": 0, "dias": 0},
        "evaluado": ejemplos.instante("2025-11-06T00:17Z"),
    }  # fmt: skip
    almacen.guardar_foco_termico("EODI-2025-00002", no_detectado)
    almacen.guardar_foco_termico("EODI-UA-2025-0001/UA-63", ejemplos.foco_termico())
    ficheros = por_nombre(semanal.generar(almacen))
    incidentes = {i["id"]: i for i in lineas(ficheros["incidentes.jsonl"])}
    assert incidentes["EODI-2025-00002"]["foco_termico"] == no_detectado
    (ataque,) = lineas(ficheros["ucrania_ataques.jsonl"])
    assert ataque["regiones"][0]["foco_termico"] == ejemplos.foco_termico()
    (region,) = lineas(ficheros["ucrania_regiones.jsonl"])
    assert region["region"]["foco_termico"]["frp_max_mw"] == 48.2


def test_el_trafico_aereo_y_las_condiciones_van_completos_con_su_origen_medido() -> None:
    """Las mediciones viven en sus tablas: AEGIS recibe los bloques enteros (también la
    respuesta militar y la interferencia GNSS, que la web nunca ve), su procedencia medida y
    las afirmaciones de la fuente medida, vigentes, junto a lo declarado."""
    almacen = poblado()
    bloque = ejemplos.trafico_aereo()
    cierre = bloque["cierre"]
    fuente = mediciones.fuente_trafico("EODI-2025-00002", cierre, bloque["datos"], 2)
    bloque["fuente_id"] = fuente["id"]
    almacen.guardar_fuente(fuente)
    almacen.guardar_afirmaciones(
        "EODI-2025-00002", mediciones.afirmaciones_trafico(fuente, cierre, 2)
    )
    almacen.guardar_trafico_aereo("EODI-2025-00002", bloque)
    almacen.guardar_condiciones("EODI-2025-00002", ejemplos.condiciones())
    ficheros = por_nombre(semanal.generar(almacen))
    incidentes = {i["id"]: i for i in lineas(ficheros["incidentes.jsonl"])}
    exportado = incidentes["EODI-2025-00002"]
    assert exportado["trafico_aereo"] == bloque
    assert exportado["condiciones"] == ejemplos.condiciones()
    assert exportado["procedencia"]["trafico_aereo"] == {
        "origen": "medido",
        "metodo": "regla",
        "fuentes": [fuente["id"]],
    }
    medidas = [a for a in lineas(ficheros["afirmaciones.jsonl"]) if a["fuente_id"] == fuente["id"]]
    assert {(a["campo"], a["origen"], a["metodo"], a["vigente"]) for a in medidas} == {
        ("cierre", "medido", "regla", True),
        ("cierre_minutos", "medido", "regla", True),
        ("vuelos_desviados", "medido", "regla", True),
    }
    assert {a["fuente"]["medio"] for a in medidas} == {"Tráfico aéreo medido (adsb.lol)"}


def test_las_afirmaciones_llevan_todas_las_fuentes_tambien_las_internas() -> None:
    afirmaciones = lineas(por_nombre(semanal.generar(poblado()))["afirmaciones.jsonl"])
    de_e = [a for a in afirmaciones if a["fuente_id"] == "FE"]
    assert de_e[0]["fuente"]["fiabilidad"] == "E" and de_e[0]["metodo"] == "extractor"
    assert de_e[0]["confianza_extraccion"] == 0.6 and de_e[0]["origen"] == "prensa"
    assert not de_e[0]["fuente"]["publica"]
    [interna] = [a for a in afirmaciones if a["fuente_id"] == "P2"]
    assert interna["fuente"]["interna_fuera_de_ucrania"] and interna["capa"] == "ucrania"
    assert (interna["campo"], interna["valor"]) == ("derribados", {"min": 70, "max": 70})
    assert interna["metodo"] == "parser" and interna["confianza_extraccion"] is None
    assert interna["origen"] == "parte"
    estados = [a for a in afirmaciones if a["campo"] == "estado"]
    assert {(a["entidad_id"], a["valor"]) for a in estados if a["fuente_id"] == "F2"} == {
        ("EODI-2025-00001", "confirmado"), ("EODI-2025-00001", "atribuido"),
    }  # fmt: skip


def test_la_salida_en_claro_es_determinista() -> None:
    primera = semanal.generar(poblado())
    segunda = semanal.generar(poblado())
    assert [(f.nombre, f.contenido) for f in primera] == [(f.nombre, f.contenido) for f in segunda]


def test_una_version_que_no_valida_no_se_genera(monkeypatch: pytest.MonkeyPatch) -> None:
    almacen = poblado()
    roto = {**ejemplos.incidente_minimo(), "tipo": "otro"}
    monkeypatch.setattr(almacen, "incidentes", lambda: [roto])
    with pytest.raises(semanal.ExportacionInvalida, match=r"^incidentes\.jsonl, registro 1"):
        semanal.generar(almacen)


def test_frecuencias_por_categoria_pais_y_mes_con_el_sesgo_declarado() -> None:
    datos = json.loads(por_nombre(semanal.generar(poblado()))["frecuencias.json"].contenido)
    claves = {(f["categoria"], f["pais"], f["mes"]) for f in datos["filas"]}
    assert ("aeropuerto", "DK", "2025-10") in claves
    assert ("sin_objetivo", "BE", "2025-11") in claves
    assert datos["totales"]["incidentes"] == 2
    assert datos["sesgo_cobertura"]["correccion"] == "ninguna"
    paises = {p["pais"]: p for p in datos["sesgo_cobertura"]["por_pais"]}
    assert paises["DK"]["fuentes_oficiales"]


def incidente_en(id_: str, inicio: str, lat: float) -> Documento:
    documento = ejemplos.incidente_minimo()
    documento["id"] = id_
    documento["tiempo"] = {"inicio": ejemplos.instante(inicio, "hora")}
    documento["lugar"]["punto"] = {"lat": lat, "lon": 5.4}
    return documento


def test_la_fusion_dudosa_queda_entre_los_descartes() -> None:
    incidentes = [
        incidente_en("EODI-2025-00010", "2025-11-04T18:00Z", 50.80),
        incidente_en("EODI-2025-00011", "2025-11-04T19:00Z", 51.00),
        incidente_en("EODI-2025-00012", "2025-11-04T20:00Z", 50.90),
    ]
    assert semanal.fusiones_dudosas(incidentes) == [
        ("EODI-2025-00012", ["EODI-2025-00010", "EODI-2025-00011"])
    ]


def test_descartes_con_su_motivo() -> None:
    almacen = poblado()
    desmentido = ejemplos.incidente_minimo()
    desmentido["id"] = "EODI-2025-00003"
    desmentido["fuentes"].append(ejemplos.fuente("F9", "A", es_autoridad=True))
    desmentido["estado"]["actual"] = "desmentido"
    desmentido["estado"]["historial"].append(
        {"estado": "desmentido", "fecha": ejemplos.instante("2025-11-05T10:00Z"), "fuente_id": "F9"}
    )
    desmentido["control"]["motivo_desmentido"] = "Forsvaret: «no hubo drones»"
    almacen.guardar_incidente(desmentido, AHORA, VOCABULARIO_MODELOS)
    almacen.registrar_fusion("2025-11-05T10:00Z", "EODI-2025-00003", "EODI-2025-00002", "x", [])
    descartes = lineas(por_nombre(semanal.generar(almacen))["descartes.jsonl"])
    assert {(d["tipo"], d["id"]) for d in descartes} == {
        ("duplicado", "EODI-2025-00003"), ("desmentido", "EODI-2025-00003"),
    }  # fmt: skip
    [desmentido_exportado] = [d for d in descartes if d["tipo"] == "desmentido"]
    assert desmentido_exportado["motivo"] == "Forsvaret: «no hubo drones»"


def descifrar(identidad: pyrage.x25519.Identity, datos: bytes) -> bytes:
    return gzip.decompress(pyrage.decrypt(datos, [identidad]))


def test_el_manifiesto_da_las_huellas_en_claro_y_cifradas(
    clave: pyrage.x25519.Identity,
) -> None:
    ficheros = semanal.generar(poblado())
    contenido = semanal.empaquetar(
        ficheros, "2026.01.05", "2026-01-01T00:00:00Z", AHORA, str(clave.to_public())
    )
    manifiesto = json.loads(contenido[semanal.MANIFIESTO])
    assert manifiesto["version"] == "2026.01.05"
    assert manifiesto["cifrado"]["destinatario"] == str(clave.to_public())
    assert len(manifiesto["ficheros"]) == len(ficheros)
    for entrada in manifiesto["ficheros"]:
        cifrado = contenido[entrada["cifrado"]["nombre"]]
        assert hashlib.sha256(cifrado).hexdigest() == entrada["cifrado"]["sha256"]
        claro = descifrar(clave, cifrado)
        assert hashlib.sha256(claro).hexdigest() == entrada["sha256"]
        assert len(claro) == entrada["bytes"]
    # Todo cifrado salvo el manifiesto.
    assert all(n.endswith(".gz.age") for n in contenido if n != semanal.MANIFIESTO)


def git(*argumentos: str, directorio: Path) -> str:
    return subprocess.run(
        ["git", *argumentos], cwd=directorio, capture_output=True, encoding="utf-8", check=True
    ).stdout


@pytest.fixture
def datos(tmp_path: Path) -> str:
    """Repositorio de datos local con main y la rama estado, como el de verdad."""
    desnudo = tmp_path / "datos.git"
    git("init", "--quiet", "--bare", "--initial-branch", "main", str(desnudo),
        directorio=tmp_path)  # fmt: skip
    trabajo = tmp_path / "trabajo"
    git("init", "--quiet", "--initial-branch", "main", str(trabajo), directorio=tmp_path)
    (trabajo / "README.md").write_text("datos\n", encoding="utf-8")
    git("add", ".", directorio=trabajo)
    git("-c", "user.name=P", "-c", "user.email=p@e.invalid", "commit", "--quiet", "-m", "x",
        directorio=trabajo)  # fmt: skip
    git("push", "--quiet", str(desnudo), "main", directorio=trabajo)
    return desnudo.as_uri()


def test_sube_la_version_con_su_etiqueta_y_nunca_la_sobrescribe(datos: str, tmp_path: Path) -> None:
    origen = tmp_path / "version"
    (origen / "esquema").mkdir(parents=True)
    (origen / "manifiesto.json").write_text("{}", encoding="utf-8")
    (origen / "esquema" / "a.json.gz.age").write_bytes(b"x")
    remoto.subir_exportacion(origen, "2026.01.05", "autor@ejemplo.org", datos)
    clon = tmp_path / "comprobar"
    git("clone", "--quiet", datos, str(clon), directorio=tmp_path)
    assert (clon / "exportaciones" / "2026.01.05" / "esquema" / "a.json.gz.age").exists()
    assert (clon / "README.md").exists()
    assert git("tag", "--list", directorio=clon).split() == ["eodi-2026.01.05"]
    autor = git("log", "-1", "--format=%an <%ae>|%s", directorio=clon).strip()
    assert autor == "QuantuSync <autor@ejemplo.org>|Exportación 2026.01.05"
    (origen / "manifiesto.json").write_text('{"otra": 1}', encoding="utf-8")
    with pytest.raises(remoto.ExportacionExistente):
        remoto.subir_exportacion(origen, "2026.01.05", "autor@ejemplo.org", datos)
    git("pull", "--quiet", directorio=clon)
    assert (clon / "exportaciones" / "2026.01.05" / "manifiesto.json").read_text() == "{}"


@pytest.mark.usefixtures("clave")
def test_la_orden_exporta_sube_y_deja_el_registro(datos: str, tmp_path: Path) -> None:
    base = tmp_path / "db.age"
    guardar_cifrada(poblado().conexion, base)
    registro = tmp_path / "exportacion.json"
    argumentos = ["--correo", "a@e.invalid", "--repositorio", datos, "--base", str(base),
                  "--registro", str(registro)]  # fmt: skip
    ahora = datetime(2026, 1, 5, 3, 47, tzinfo=UTC)
    assert exportacion.principal(argumentos, ahora) == 0
    anotado = json.loads(registro.read_text(encoding="utf-8"))
    assert anotado["version"] == "2026.01.05"
    # Otra vez el mismo día: no se sobrescribe, no es un fallo y el registro no cambia.
    registro.write_text("{}", encoding="utf-8")
    assert exportacion.principal(argumentos, ahora) == 0
    assert registro.read_text(encoding="utf-8") == "{}"


def test_estado_json_lleva_la_ultima_exportacion(tmp_path: Path) -> None:
    fin = datetime(2026, 1, 5, 4, 20, tzinfo=UTC)
    sin = estado.componer(fin, fin, 0, None, None, 17)
    assert "ultima_exportacion" not in sin
    nunca = estado.componer(fin, fin, 0, None, None, 17, None, True)
    assert nunca["ultima_exportacion"] is None
    hecha = estado.componer(fin, fin, 0, None, None, 17, {"fin": "2026-01-05T03:49Z"}, True)
    assert hecha["ultima_exportacion"] == "2026-01-05T03:49Z"


@pytest.mark.parametrize(
    ("datos_estado", "al_dia"),
    [
        (None, True),
        ({"resultado": "correcta"}, True),
        ({"ultima_exportacion": None}, False),
        ({"ultima_exportacion": "2026-01-05T03:49Z"}, True),
        ({"ultima_exportacion": "2025-12-28T03:49Z"}, False),
    ],
)
def test_la_salud_avisa_con_mas_de_8_dias_sin_exportacion(
    datos_estado: dict[str, Any] | None, al_dia: bool
) -> None:
    ahora = datetime(2026, 1, 5, 12, tzinfo=UTC)
    assert salud.diagnostico_exportacion(datos_estado, ahora)[0] is al_dia
    assert timedelta(days=8) == salud.MAX_SIN_EXPORTACION


def test_la_salud_escribe_las_dos_salidas(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    salida = tmp_path / "salida"
    monkeypatch.setenv(salud.VARIABLE_SALIDA, str(salida))
    publicado = {"resultado": "correcta", "fin": "2026-01-05T11:20Z",
                 "ultima_correcta": "2026-01-05T11:20Z", "ultima_exportacion": None}  # fmt: skip
    salud.principal([], datetime(2026, 1, 5, 12, tzinfo=UTC),
                    leer=lambda _url: json.dumps(publicado).encode())  # fmt: skip
    texto = salida.read_text(encoding="utf-8")
    assert "problema=false" in texto
    assert "problema_exportacion=true" in texto


def con_registros_de_detalle() -> Almacen:
    almacen = poblado()
    almacen.guardar_encuentro(ejemplos.encuentro(), AHORA)
    estadistica = ejemplos.estadistica_oficial()
    estadistica["ambito"] = {"pais": "DK", "categoria": "aeropuerto"}
    estadistica["periodo"] = {"inicio": "2025-10-01", "fin": "2025-10-31"}
    almacen.guardar_estadistica_oficial(estadistica, AHORA)
    almacen.guardar_documento_oficial(ejemplos.documento_oficial(), AHORA)
    return almacen


def test_los_registros_de_detalle_salen_en_sus_ficheros_con_su_esquema() -> None:
    ficheros = por_nombre(semanal.generar(con_registros_de_detalle()))
    for nombre, esquema in (
        ("encuentros.jsonl", "esquema/eodi/encuentro.schema.json"),
        ("estadisticas_oficiales.jsonl", "esquema/eodi/estadistica_oficial.schema.json"),
        ("documentos_oficiales.jsonl", "esquema/eodi/documento_oficial.schema.json"),
    ):
        assert ficheros[nombre].esquema == esquema and ficheros[nombre].registros == 1
        assert esquema in ficheros
    (encuentro,) = lineas(ficheros["encuentros.jsonl"])
    assert encuentro == ejemplos.encuentro()


def test_las_frecuencias_ponen_cada_cifra_oficial_junto_a_lo_que_recoge_el_observatorio() -> None:
    datos = json.loads(
        por_nombre(semanal.generar(con_registros_de_detalle()))["frecuencias.json"].contenido
    )
    (referencia,) = datos["sesgo_cobertura"]["referencias_oficiales"]
    assert referencia["cifra"] == {"min": 536, "max": 536}
    # El incidente de aeropuerto en Dinamarca de octubre de 2025.
    assert referencia["incidentes_observatorio"] == 1
    assert datos["sesgo_cobertura"]["correccion"] == "ninguna"


def test_el_vocabulario_lleva_las_metricas_de_las_estadisticas() -> None:
    vocabulario = json.loads(por_nombre(semanal.generar(poblado()))["vocabulario.json"].contenido)
    assert set(vocabulario["metricas_estadistica"]) >= {
        "avistamientos",
        "sobrevuelos",
        "encuentros",
    }
