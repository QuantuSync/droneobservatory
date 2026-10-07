"""Base de prueba para la exportación semanal: un ejemplo de cada campo del esquema, con los
valores que ponen las reglas de la recogida tal como los pone la recogida.

Una regla que pone un valor sin afirmación del extractor (el cierre de una pista, la presencia
por la actuación de la autoridad, el enlace de una incursión con su ataque) deja la exportación
sin origen para ese valor si nadie le ha dado una regla de origen en exportacion/procedencia.py.
Eso solo se ve sobre una base que haya pasado por esas reglas: aquí se guardan los ejemplos y se
pasan las mismas revisiones que hace la recogida horaria antes de exportar.

La usan los tests (tests/test_exportacion_completa.py) y la CI, que exporta en ensayo, sin subir
nada, con una clave age de usar y tirar:

    python -m tests.base_prueba --salida <carpeta>

Un campo nuevo del esquema tiene que estar aquí (lo comprueba
test_la_base_de_prueba_cubre_todo_el_esquema); si su valor no tiene regla de origen, la
exportación falla en la CI antes de fusionar.
"""

import argparse
import copy
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pyrage

from almacen.base import Almacen
from almacen.cifrado import VARIABLE_CLAVE, guardar_cifrada
from esquema import Documento
from proceso import cruces, luces, periodos, presencia, zona
from tests import ejemplos
from tests.ejemplos import AHORA, VOCABULARIO_MODELOS

# Hora de la exportación de ensayo (lunes, a la hora del temporizador).
EXPORTACION = datetime(2026, 1, 5, 3, 47, tzinfo=UTC)

# Lo que respalda la nota oficial F2 del incidente completo (como en
# tests/test_exportacion_semanal.py): sin fuente, un valor no tiene origen.
RESPALDA_F2 = [
    "consecuencias", "detalle_oficial", "drones", "estado", "lugar.localidad", "pruebas",
    "respuesta", "tiempo.fin",
]  # fmt: skip


def completo() -> Documento:
    """El incidente con todos los campos, con lo que una autoridad investiga."""
    documento = ejemplos.incidente_completo()
    del documento["procedencia"], documento["nivel_detalle"], documento["indicadores"]
    del documento["deduccion"], documento["tipo_dron"], documento["recorrido"]  # en su tabla
    for fuente in documento["fuentes"]:
        if fuente["id"] == "F2":
            fuente["campos_respaldados"] = RESPALDA_F2
    documento["investigacion"] = [{
        "autoridad": "Gobierno nacional",
        "cita": "El Gobierno investiga si los drones despegaron de un barco",
        "fuente_id": "F2",
        "fecha": ejemplos.instante("2025-10-02T12:00Z", "hora"),
    }]  # fmt: skip
    return documento


def con_fuente_e() -> Documento:
    """Un incidente que solo cuenta una fuente de fiabilidad E."""
    documento = ejemplos.incidente_minimo()
    documento["fuentes"].append(ejemplos.fuente("FE", "E", publica=False))
    documento["afirmaciones"] = [
        {"campo": "drones", "valor": {"min": 2, "max": 2}, "fuente_id": "FE",
         "confianza_extraccion": 0.6},
    ]  # fmt: skip
    return documento


def cierre_de_pista() -> Documento:
    """Schiphol (EODI-2025-00058): la fuente cuenta que se suspendió una pista por un dron y
    ninguna ficha registra el cierre. La revisión de presencia pone el cierre y confirma la
    presencia por la actuación de la autoridad del aeropuerto."""
    documento = ejemplos.incidente_minimo()
    documento.update(
        id="EODI-2025-00003", presencia_dron="no_confirmada",
        consecuencias={"cierre": {"valor": "desconocido"}},
        objetivo={"categoria": "aeropuerto", "nombre": "Luchthaven Schiphol", "oaci": "EHAM"},
        titulo={"es": "Posibles drones cierran una pista del aeropuerto de Ámsterdam Schiphol",
                "en": "Possible drones close runway at Amsterdam Schiphol Airport"},
        # Localidad corregida a mano, sin afirmación de la ficha (recogida/revisados.py).
        lugar={"punto": {"lat": 52.327, "lon": 4.758}, "radio_km": 5, "pais": "NL",
               "localidad": "Haarlemmermeer"},
    )  # fmt: skip
    documento["fuentes"][0]["frase_origen"] = (
        "Аэропорт Схипхол приостанавливал работу взлетно-посадочной полосы из-за дрона."
    )
    return documento


def incursion() -> Documento:
    """Dron ruso en Rumanía la noche del ataque EODI-UA-2025-0001: la revisión de cruces lo
    enlaza con el ataque, en los dos sentidos."""
    documento = ejemplos.incidente_minimo()
    documento.update(
        id="EODI-2025-00004",
        titulo={"es": "Dron ruso interceptado en Rumanía", "en": "Russian drone over Romania"},
        tiempo={"inicio": ejemplos.instante("2025-10-05T23:00Z", "hora")},
        lugar={"punto": {"lat": 45.17, "lon": 28.8}, "radio_km": 10, "pais": "RO"},
    )  # fmt: skip
    # El lugar que da la autoridad, con los demás lugares que nombra (recogida/revisados.py).
    documento["lugar"].update(
        geocodificacion="oficial", fuente_punto=documento["fuentes"][0]["id"], localidad="Isaccea",
        otros_lugares=[{"nombre": "Galați", "punto": {"lat": 45.43, "lon": 28.05}},
                       {"nombre": "Smârdan", "fuente": documento["fuentes"][0]["id"]}],
        # El punto anterior, cambiado por una corrección revisada con su motivo.
        historial=[{"fecha": ejemplos.instante("2025-10-07T12:00Z", "minuto"),
                    "anterior": {"localidad": "Smârdan", "punto": {"lat": 45.29, "lon": 28.35},
                                 "radio_km": 3, "fuente_punto": documento["fuentes"][0]["id"]},
                    "motivo": {"es": "Daño de la defensa, no del dron.",
                               "en": "Damage from the defence, not the drone."}}],
    )  # fmt: skip
    return documento


def ataques() -> list[Documento]:
    """El ataque completo, un parte de resumen de la semana y un tramo de la misma noche."""
    principal = ejemplos.ataque_completo()
    principal["fuentes"][1]["campos_respaldados"] = ["derribados"]
    del principal["deduccion"], principal["procedencia"]
    resumen = copy.deepcopy(principal)
    resumen.update(
        id="EODI-UA-2025-0002",
        periodo={"inicio": ejemplos.instante("2025-09-29T00:00Z"),
                 "fin": ejemplos.instante("2025-10-06T06:00Z")},
        cruces=[], resumen=True,
    )  # fmt: skip
    for campo in ("cruces_parte", "restricciones_aeropuertos", "regiones", "condiciones"):
        resumen.pop(campo, None)
    tramo = copy.deepcopy(principal)
    tramo.update(
        id="EODI-UA-2025-0003",
        periodo={"inicio": ejemplos.instante("2025-10-05T18:00Z"),
                 "fin": ejemplos.instante("2025-10-06T03:00Z")},
        cruces=[], regiones_misiles=["UA-63"], incluido_en="EODI-UA-2025-0001",
        solapado_con="EODI-UA-2025-0002",
    )  # fmt: skip
    for campo in ("cruces_parte", "restricciones_aeropuertos", "condiciones"):
        tramo.pop(campo, None)
    return [principal, resumen, tramo]


def impactos() -> list[Documento]:
    """Un impacto en una localidad con víctimas por fuente y otro en una instalación que solo da
    un parte en guerra, en el parte diario."""
    localidad = ejemplos.impacto_guerra()
    localidad.update(
        heridos={"min": 3, "max": 3}, fallecidos={"min": 1, "max": 1}, dia="2025-05-31",
    )  # fmt: skip
    localidad["lugar"]["nivel"] = "comunidad"
    localidad["lecturas"][0]["victimas"] = {"heridos": 3, "fallecidos": 1}
    instalacion = ejemplos.impacto_guerra()
    instalacion.update(
        id="EODI-IG-2025-00002", reivindicacion_de_parte=True, parte_diario=True,
    )  # fmt: skip
    instalacion.pop("ataque")
    instalacion.pop("enlace_ataque")
    instalacion["lugar"].update(
        nivel="instalacion", categoria="subestacion", localidad="Харків",
    )  # fmt: skip
    return [localidad, instalacion]


def base_prueba() -> Almacen:
    """La base de prueba, ya pasada por las revisiones de la recogida horaria."""
    almacen = Almacen.abrir()
    for documento in (completo(), con_fuente_e(), cierre_de_pista(), incursion()):
        almacen.guardar_incidente(documento, AHORA, VOCABULARIO_MODELOS)
    for ataque in ataques():
        almacen.guardar_ataque_ucrania(ataque, AHORA)
    almacen.guardar_luces_nocturnas(
        "EODI-UA-2025-0001", {"version": luces.VERSION, "perdidas": [ejemplos.perdida_luz()]}
    )
    for impacto in impactos():
        almacen.guardar_impacto_guerra(impacto)
    almacen.guardar_foco_termico("EODI-IG-2025-00001", ejemplos.foco_termico())
    almacen.guardar_foco_termico("EODI-2025-00002", {
        "resultado": "no_detectado", "motivo": "sin_focos", "radio_km": 10,
        "focos_en_ventana": 0, "linea_base": {"focos": 0, "dias": 0},
        "evaluado": ejemplos.instante("2025-11-06T00:17Z"),
    })  # fmt: skip
    almacen.guardar_foco_termico("EODI-UA-2025-0001/UA-63", ejemplos.foco_termico())
    almacen.guardar_deduccion("EODI-2025-00001", "incidente", ejemplos.deduccion_completa())
    almacen.guardar_deduccion("EODI-IG-2025-00001", "impacto", ejemplos.deduccion_completa())
    almacen.guardar_tipo_dron("EODI-2025-00001", ejemplos.tipo_dron_completo())
    almacen.guardar_condiciones("EODI-2025-00001", ejemplos.condiciones())
    almacen.guardar_restriccion(ejemplos.restriccion())
    almacen.guardar_episodio(ejemplos.episodio(), AHORA)
    almacen.guardar_encuentro(ejemplos.encuentro(), AHORA)
    almacen.guardar_documento_oficial(ejemplos.documento_oficial(), AHORA)
    estadistica = ejemplos.estadistica_oficial()
    estadistica["ambito"] = {"pais": "DK", "categoria": "aeropuerto"}
    estadistica["periodo"] = {"inicio": "2025-10-01", "fin": "2025-10-31"}
    almacen.guardar_estadistica_oficial(estadistica, AHORA)
    # Las revisiones de la recogida horaria que ponen valores por regla.
    periodos.revisar(almacen, AHORA)
    presencia.revisar(almacen, AHORA, VOCABULARIO_MODELOS)
    cruces.enlazar(almacen, AHORA, VOCABULARIO_MODELOS)
    zona.clasificar_todos(almacen, AHORA, VOCABULARIO_MODELOS)
    almacen.registrar_previsiones(ejemplos.previsiones())
    return almacen


def ensayo(salida: Path) -> int:
    """Exporta la base de prueba en `salida`, en ensayo y sin subir nada, como la orden del
    servidor (recogida/exportacion.py). Devuelve su código de salida."""
    from recogida import exportacion

    identidad = pyrage.x25519.Identity.generate()
    anterior = os.environ.get(VARIABLE_CLAVE)
    os.environ[VARIABLE_CLAVE] = str(identidad)
    try:
        with TemporaryDirectory() as temporal:
            base = Path(temporal) / "db.age"
            almacen = base_prueba()
            guardar_cifrada(almacen.conexion, base)
            almacen.cerrar()
            argumentos = ["--base", str(base), "--sin-subir", "--salida", str(salida)]
            return exportacion.principal(argumentos, EXPORTACION)
    finally:
        if anterior is None:
            os.environ.pop(VARIABLE_CLAVE, None)
        else:
            os.environ[VARIABLE_CLAVE] = anterior


if __name__ == "__main__":
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--salida", type=Path, required=True, help="carpeta de la versión")
    sys.exit(ensayo(opciones.parse_args().salida))
