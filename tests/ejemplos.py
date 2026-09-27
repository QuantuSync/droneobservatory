"""Documentos de ejemplo completos y válidos. Cada llamada devuelve una copia nueva."""

from datetime import UTC, datetime

from esquema import Documento

AHORA = datetime(2026, 1, 1, tzinfo=UTC)
VOCABULARIO_MODELOS = frozenset({"shahed_geran", "gerbera_senuelos", "otros"})


def instante(valor: str, precision: str = "minuto") -> Documento:
    return {"valor": valor, "precision": precision}


def fuente(
    id_: str = "F1",
    fiabilidad: str = "A",
    *,
    publica: bool = True,
    es_autoridad: bool = False,
    interna_fuera_de_ucrania: bool = False,
) -> Documento:
    return {
        "id": id_,
        "enlace": f"https://ejemplo.org/nota/{id_}",
        "medio": f"Medio {id_}",
        "fecha": instante("2025-10-02T06:00Z"),
        "idioma": "da",
        "fiabilidad": fiabilidad,
        "credibilidad": 2,
        "frase_origen": "Lufthavnen blev lukket efter observation af droner",
        "replicas": 3,
        "campos_respaldados": ["drones.numero", "consecuencias.cierre"],
        "es_autoridad": es_autoridad,
        "interna_fuera_de_ucrania": interna_fuera_de_ucrania,
        "publica": publica,
    }


def incidente_completo() -> Documento:
    """Incidente con todos los campos, públicos e internos, rellenos."""
    return {
        "id": "EODI-2025-00001",
        "tipo": "interrupcion_aeroportuaria",
        "estado": {
            "actual": "atribuido",
            "historial": [
                {"estado": "notificado", "fecha": instante("2025-10-01T21:00Z"), "fuente_id": "F1"},
                {"estado": "confirmado", "fecha": instante("2025-10-01T22:00Z"), "fuente_id": "F2"},
                {"estado": "atribuido", "fecha": instante("2025-10-03T10:00Z"), "fuente_id": "F2"},
            ],
        },
        "titulo": {"es": "Cierre de aeropuerto por drones", "en": "Airport closed by drones"},
        "episodio": "EODI-EP-2025-0001",
        "origen_demostrado_por": ["rastreo"],
        "tiempo": {
            "inicio": instante("2025-10-01T20:30Z"),
            "fin": instante("2025-10-01T23:30Z"),
            "duracion_min": 180,
        },
        "lugar": {
            "punto": {"lat": 55.61806, "lon": 12.65611},
            "radio_km": 5,
            "pais": "DK",
            "localidad": "Kastrup",
            "nuts2": "DK01",
        },
        "objetivo": {
            "categoria": "aeropuerto",
            "nombre": "Kastrup",
            "oaci": "EKCH",
            "uso": "civil",
        },
        "drones": {
            "numero": {"min": 3, "max": 6},
            "clase": "ala_fija",
            "modelo": "otros",
            "luces": "si",
            "altura_m": {"min": 100, "max": 300},
            "velocidad_ms": "desconocido",
            "trayectoria": {
                "entrada_grados": 90,
                "salida_grados": 270,
                "puntos": [{"lat": 55.6, "lon": 12.7}],
            },
            "patron": "merodeo",
        },
        "consecuencias": {
            "cierre": {"valor": "si", "minutos": {"min": 170, "max": 190}},
            "vuelos_desviados": {"min": 30, "max": 35},
            "vuelos_cancelados": {"min": 50, "max": 60},
            "vuelos_retrasados": "desconocido",
            "danos": {"nivel": "ninguno"},
            "heridos": {"min": 0, "max": 0},
            "fallecidos": {"min": 0, "max": 0},
        },
        "respuesta": {
            "medidas": ["cierre_espacio_aereo", "patrulla"],
            "deteccion": ["radar", "piloto"],
            "resultado_contramedidas": "desconocido",
        },
        "atribucion": {
            "actor": "Actor estatal",
            "autoridad": "Gobierno nacional",
            "fecha": instante("2025-10-03T10:00Z", "hora"),
        },
        "fuentes": [
            fuente("F1", "B"),
            fuente("F2", "A", es_autoridad=True),
            fuente("F3", "E", publica=False),
            fuente("F4", "C", publica=False, interna_fuera_de_ucrania=True),
        ],
        "afirmaciones": [
            {"campo": "drones.numero", "valor": 10, "fuente_id": "F1", "confianza_extraccion": 0.9},
            {
                "campo": "drones.numero",
                "valor": 20,
                "fuente_id": "F3",
                "confianza_extraccion": 0.7,
                "credibilidad": 4,
            },
        ],
        "control": {
            "alta": instante("2025-10-01T21:05Z"),
            "ultima_actualizacion": instante("2025-10-03T10:05Z"),
            "version_extractor": "nulo",
            "huella_fuentes": "0" * 64,
            "vocabulario_aegis": {"tipo": "airport_disruption"},
            "distancia_instalaciones_km": 12.5,
        },
    }


def incidente_minimo() -> Documento:
    """Incidente recién notificado con lo imprescindible."""
    return {
        "id": "EODI-2025-00002",
        "tipo": "sobrevuelo",
        "estado": {
            "actual": "notificado",
            "historial": [
                {"estado": "notificado", "fecha": instante("2025-11-04T19:00Z"), "fuente_id": "F1"}
            ],
        },
        "titulo": {"es": "Drones sobre una base", "en": "Drones over a base"},
        "tiempo": {"inicio": instante("2025-11-04T18:00Z", "hora")},
        "lugar": {"punto": {"lat": 50.9, "lon": 5.4}, "radio_km": 10, "pais": "BE"},
        "fuentes": [fuente("F1", "B")],
        "control": {
            "alta": instante("2025-11-04T19:05Z"),
            "ultima_actualizacion": instante("2025-11-04T19:05Z"),
        },
    }


def region() -> Documento:
    return {
        "region": "UA-63",
        "impactos": {"min": 2, "max": 3},
        "caida_restos": {"min": 1, "max": 1},
        "categorias_objetivo": ["energia", "residencial"],
        "heridos": {"min": 4, "max": 4},
        "fallecidos": {"min": 0, "max": 0},
    }


def ataque_completo() -> Documento:
    return {
        "id": "EODI-UA-2025-0001",
        "tipo": "ataque_guerra",
        "periodo": {"inicio": instante("2025-10-05T15:00Z"), "fin": instante("2025-10-06T06:00Z")},
        "sentido": "RU_UA",
        "reivindicacion_de_parte": True,
        "estado": {
            "actual": "confirmado",
            "historial": [
                {"estado": "notificado", "fecha": instante("2025-10-06T06:30Z"), "fuente_id": "P1"},
                {"estado": "confirmado", "fecha": instante("2025-10-06T07:00Z"), "fuente_id": "P1"},
            ],
        },
        "lanzados": {
            "shahed_geran": {"min": 80, "max": 80},
            "gerbera_senuelos": {"min": 20, "max": 20},
            "otros": {"min": 0, "max": 0},
            "total": {"min": 100, "max": 100},
        },
        "zonas_lanzamiento": ["Kursk", "Oriol"],
        "tipos_dron": ["ala_fija"],
        "derribados": {"min": 70, "max": 70},
        "derribados_categoria": "derribados_o_neutralizados",
        "perdidos_guerra_electronica": {"min": 15, "max": 15},
        "localizaciones_impacto": {"min": 3, "max": 3},
        "localizaciones_restos": "desconocido",
        "lugares_impacto": ["Járkov"],
        "lugares_restos": ["Poltava"],
        "cruces": [{"pais": "PL", "numero": {"min": 1, "max": 2}}],
        "horas_llegada": [instante("2025-10-05T22:10Z")],
        "duracion_oleada_min": 420,
        "proporcion_senuelos": 0.2,
        "regiones": [region()],
        "fuentes": [
            fuente("P1", "B", es_autoridad=True),
            fuente("P2", "C", interna_fuera_de_ucrania=True),
        ],
        "afirmaciones": [
            {
                "campo": "derribados",
                "valor": 70,
                "fuente_id": "P1",
                "confianza_extraccion": 1,
                "credibilidad": 1,
            }
        ],
        "control": {
            "alta": instante("2025-10-06T06:35Z"),
            "ultima_actualizacion": instante("2025-10-06T07:05Z"),
            "version_extractor": "nulo",
            "huella_fuentes": "1" * 64,
        },
    }


def episodio() -> Documento:
    return {
        "id": "EODI-EP-2025-0001",
        "titulo": {"es": "Noche de drones", "en": "Night of drones"},
        "noche": "2025-10-01",
        "incidentes": ["EODI-2025-00001"],
    }
