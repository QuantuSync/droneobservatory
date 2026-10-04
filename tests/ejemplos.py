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


def foco_termico() -> Documento:
    """Foco térmico detectado con todos sus campos, públicos e internos."""
    return {
        "resultado": "detectado",
        "primer_foco": instante("2025-10-01T23:42Z"),
        "satelite": "NOAA-20",
        "instrumento": "VIIRS",
        "distancia_km": 1.4,
        "numero_focos": 3,
        "frp_max_mw": 48.2,
        "radio_km": 5,
        "ventana": {"inicio": instante("2025-10-01T20:30Z"), "fin": instante("2025-10-03T11:30Z")},
        "focos_en_ventana": 4,
        "linea_base": {
            "focos": 2,
            "dias": 2,
            "frp_max_mw": 3.1,
            "emplazamiento": {"focos": 40, "descartados": 1},
        },
        "fuentes_firms": ["VIIRS_NOAA20_SP", "MODIS_SP"],
        "evaluado": instante("2025-10-04T00:17Z"),
    }


def trafico_aereo() -> Documento:
    """Tráfico aéreo medido con cierre, respuesta militar e interferencia GNSS, con todos sus
    campos (Copenhague, 22 de septiembre de 2025)."""
    return {
        "cierre": {
            "resultado": "cierre_medido",
            "aeropuerto": "EKCH",
            "inicio": instante("2025-09-22T18:26Z"),
            "fin": instante("2025-09-22T22:38Z"),
            "duracion_min": 252,
            "vuelos_desviados": 31,
            "vuelos_en_espera": 6,
            "difiere_de_declarado": False,
            "aproximaciones_frustradas": 1,
            "llegadas_perdidas": 52,
            "salidas_perdidas": 48,
            "precision_bordes": "movimientos",
            "linea_base": {
                "semanas": 4,
                "llegadas": 54.0,
                "salidas": 50.0,
                "llegadas_vistas": 2,
                "salidas_vistas": 2,
                "esperas": 1.0,
                "frustradas": 0.0,
                "desvios": 0.0,
            },
            "cobertura": {
                "nivel": "alta",
                "vistos": 694,
                "referencia": 780.0,
                "origen_referencia": "eurocontrol",
                "indice": 0.89,
            },
            "motivos_meteorologicos": [],
            "declarado": {
                "minutos": {"min": 240, "max": 240},
                "vuelos_desviados": {"min": 35, "max": 35},
            },
            "diferencias": [],
            "otras_interrupciones": 0,
            "indicios": {
                "base_ventana": 3.0,
                "vistos_ventana": 0,
                "esperas_ventana": 2,
                "desvios_ventana": 1,
            },
        },
        "respuesta_militar": {
            "resultado": "vistas",
            "radio_km": 150.0,
            "ventana": {
                "inicio": instante("2025-09-22T16:30Z"),
                "fin": instante("2025-09-23T01:00Z"),
            },
            "aeronaves": 1,
            "por_clase": {"helicoptero": 1},
            "tipos": ["EH10"],
            "primera": instante("2025-09-22T19:02Z"),
            "distancia_min_km": 12.4,
            "detalle": [
                {
                    "icao": "45d001",
                    "tipo": "EH10",
                    "clase": "helicoptero",
                    "indicativos": ["DAF123"],
                    "primera": instante("2025-09-22T19:02Z"),
                    "distancia_min_km": 12.4,
                }
            ],
            "ausencia_no_concluyente": True,
        },
        "interferencia_gnss": {
            "resultado": "medida",
            "celda": "841f059ffffffff",
            "resolucion_h3": 4,
            "ventana": {
                "inicio": instante("2025-09-22T18:30Z"),
                "fin": instante("2025-09-22T23:00Z"),
            },
            "propia": {
                "aeronaves": 40,
                "degradadas": 1,
                "proporcion": 0.0,
                "nivel": "sin_interferencia",
            },
            "vecinas": {
                "aeronaves": 210,
                "degradadas": 3,
                "proporcion": 0.01,
                "nivel": "sin_interferencia",
            },
        },
        "datos": [
            "https://github.com/adsblol/globe_history_2025/releases/tag/v2025.09.22-planes-readsb-prod-0"
        ],
        "fuente_id": "adsblol-EKCH-2025-09-22-EODI-2025-00001",
        "ventana": {"inicio": instante("2025-09-22T18:30Z"), "fin": instante("2025-09-22T23:00Z")},
        "precision_incidente": "hora",
        "origen": "medido",
        "metodo": "regla",
        "regla": {"nombre": "trafico_aereo", "version": "1.0.0"},
        "huella": "a" * 64,
        "evaluado": instante("2025-09-23T09:17Z"),
    }


def condiciones() -> Documento:
    """Condiciones medidas con todos sus campos: el lugar de un incidente y, como en un ataque
    de la capa de guerra, una zona de lanzamiento y una de impacto."""
    lugar = _lugar_condiciones()
    return {
        "lugar": lugar,
        "lanzamiento": [{**lugar, "nombre": "Primorsko-Ajtarsk", "lat": 46.05, "lon": 38.17}],
        "impacto": [{**lugar, "nombre": "Járkov", "lat": 49.99, "lon": 36.23}],
        "origen_lugar": "punto",
        "niveles_desde": "2022-11-24",
        "fuentes": [
            "https://open-meteo.com/",
            "https://mesonet.agron.iastate.edu/request/download.phtml",
        ],
        "fuente_id": "condiciones-EODI-2025-00001",
        "origen": "medido",
        "metodo": "regla",
        "regla": {"nombre": "condiciones", "version": "1.0.0"},
        "huella": "b" * 64,
        "evaluado": instante("2025-09-23T09:17Z"),
    }


def _lugar_condiciones() -> Documento:
    return {
        "lat": 55.618,
        "lon": 12.656,
        "momento": {"valor": "2025-09-22T18:00Z", "precision": "hora"},
        "rango_dia": False,
        "superficie": {
            "temperatura_c": 12.4,
            "viento_10m_ms": 6.1,
            "direccion_10m": 280.0,
            "racha_10m_ms": 11.2,
            "precipitacion_mm": 0.0,
        },
        "niveles": {"850": {"viento_ms": 16.3, "direccion": 299.0, "temperatura_c": 3.0}},
        "metar": {
            "estacion": "EKCH",
            "distancia_km": 0.0,
            "hora": {"valor": "2025-09-22T18:20Z", "precision": "minuto"},
            "texto": "EKCH 221820Z AUTO 28012KT 9999 NCD 12/07 Q1014 NOSIG",
            "visibilidad_m": 10000,
            "techo_ft": None,
            "fenomenos": [],
            "viento_kt": 12.0,
            "racha_kt": None,
            "viento_dir": 280,
        },
        "astronomia": {
            "elevacion_sol": -12.2,
            "luz": "noche",
            "altura_luna": -12.3,
            "luna_iluminada": 0.01,
            "horas_de_luz": 12.0,
        },
        "nombre": "Kastrup",
    }


def anomalia() -> Documento:
    return {
        "oaci": "EKCH",
        "inicio": "2025-09-22T18:26Z",
        "fin": "2025-09-22T22:38Z",
        "duracion_min": 252,
        "estado": "casada",
        "incidentes": ["EODI-2025-00001"],
        "precision": "movimientos",
        "llegadas_perdidas": 52,
        "salidas_perdidas": 48,
        "llegadas_vistas": 2,
        "salidas_vistas": 2,
        "llegadas_base": 54.0,
        "salidas_base": 50.0,
        "esperas": 6,
        "esperas_base": 1.0,
        "frustradas": 1,
        "frustradas_base": 0.0,
        "desvios": 31,
        "desvios_base": 0.0,
        "semanas_base": 4,
        "motivos_meteorologicos": [],
        "cobertura": {"nivel": "alta", "vistos": 694},
        "datos": "https://github.com/adsblol/globe_history_2025/releases/tag/v2025.09.22-planes-readsb-prod-0",
        "regla": {"nombre": "trafico_aereo", "version": "1.0.0"},
        "evaluado": instante("2025-09-23T09:17Z"),
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
        "presencia_dron": "confirmada",
        "origen_demostrado_por": ["rastreo"],
        "pruebas": {"dron_estatal": False, "entrada_exterior": True, "evidencia": ["rastreo"]},
        "tiempo": {
            "inicio": instante("2025-10-01T20:30Z"),
            "fin": instante("2025-10-01T23:30Z"),
            "duracion_min": 180,
            "origen_inicio": {
                "tipo": "relativa",
                "fuente_id": "F1",
                "motivo": "«mandag» en una nota publicada el 2025-10-02 07:10",
                "corregido": True,
            },
        },
        "lugar": {
            "punto": {"lat": 55.61806, "lon": 12.65611},
            "radio_km": 5,
            "pais": "DK",
            "localidad": "Kastrup",
            "region": "Hovedstaden",
            "nivel": "instalacion",
            "suceso": "Københavns Lufthavn",
            "geocodificacion": "nomenclator",
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
        "foco_termico": foco_termico(),
        "detalle_oficial": {
            "inicio": instante("2025-10-01T20:25Z"),
            "punto": {"lat": 55.61, "lon": 12.64},
            "radio_km": 2.0,
            "numero": {"min": 4, "max": 4},
            "medidas": ["cierre_espacio_aereo"],
        },
        "encuentros": ["UKAB-2025022"],
        "trafico_aereo": trafico_aereo(),
        "condiciones": condiciones(),
        "respuesta": {
            "medidas": ["cierre_espacio_aereo", "patrulla"],
            "deteccion": ["radar", "piloto"],
            "resultado_contramedidas": "desconocido",
        },
        "ataque": {
            "id": "EODI-UA-2025-0244",
            "jornada": {"tipo": "noche", "desde": "2025-10-01", "hasta": "2025-10-02"},
            "por": "fecha",
        },
        "atribucion": {
            "actor": "Rusia",
            "autoridad": "Gobierno nacional",
            "fecha": instante("2025-10-03T10:00Z", "hora"),
            "tipo": "estado",
            "pais": "RU",
        },
        "fuentes": [
            fuente("F1", "B"),
            {
                **fuente("F2", "A", es_autoridad=True),
                "frase_origen": "El Gobierno atribuye a Rusia el cierre del aeropuerto por drones",
                "metodo": "parser",
                "documento_oficial": "UKAB-2025022",
                "campos_respaldados": ["detalle_oficial", "estado"],
            },
            fuente("F3", "E", publica=False),
            fuente("F4", "C", publica=False, interna_fuera_de_ucrania=True),
        ],
        "afirmaciones": [
            {
                "campo": "drones.numero",
                "valor": 10,
                "fuente_id": "F1",
                "confianza_extraccion": 0.9,
                "origen": "prensa",
                "metodo": "extractor",
            },
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
            "candidato": "CAND-20251001T2030-EKCH-aeropuerto",
            "vocabulario_aegis": {"tipo": "airport_disruption"},
            "distancia_instalaciones_km": 12.5,
        },
        "deduccion": deduccion_completa(),
        # Lo añade la exportación semanal; la base no lo guarda.
        "procedencia": {
            "drones.numero": {
                "origen": "oficial",
                "metodo": "parser",
                "fuentes": ["F1", "F2"],
                "confianza": 0.9,
            },
        },
        "nivel_detalle": "C",
        "indicadores": {
            "tiene_cierre_medido": False,
            "tiene_condiciones_medidas": False,
            "tiene_respuesta_militar_observada": False,
            "tiene_interferencia_gnss_medida": False,
            "tiene_foco_termico": False,
            "tiene_confirmacion_oficial_directa": True,
            "fecha_del_suceso_verificada": True,
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
        "zonas_lanzamiento_citadas": ["Kursk", "Oriol"],
        "tipos_dron": ["ala_fija"],
        "derribados": {"min": 70, "max": 70},
        "derribados_categoria": "derribados_o_neutralizados",
        "perdidos_guerra_electronica": {"min": 15, "max": 15},
        "localizaciones_impacto": {"min": 3, "max": 3},
        "localizaciones_restos": "desconocido",
        "lugares_impacto": ["Járkov"],
        "lugares_restos": ["Poltava"],
        "cruces": [
            {"pais": "PL", "numero": {"min": 1, "max": 2}, "incidentes": ["EODI-2025-00001"]},
            {
                "pais": "BY",
                "numero": {"min": 1, "max": 1},
                "frase": "Один БпЛА полетів у бік Білорусі.",
            },
        ],
        "cruces_parte": [
            {"pais": "PL", "numero": {"min": 1, "max": 2}, "frase": "Два БпЛА полетіли до Польщі."}
        ],
        "horas_llegada": [instante("2025-10-05T22:10Z")],
        "duracion_oleada_min": 420,
        "proporcion_senuelos": 0.2,
        "regiones": [{**region(), "foco_termico": foco_termico()}],
        "condiciones": condiciones(),
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
                "origen": "oficial",
                "metodo": "parser",
            }
        ],
        "restricciones_aeropuertos": {"aeropuertos": 2, "horas": 10.9},
        "deduccion": deduccion_completa(),
        "procedencia": {"derribados": {"origen": "oficial", "metodo": "parser", "fuentes": ["P1"]}},
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


def encuentro() -> Documento:
    """Un encuentro con aeronave de la UK Airprox Board, con los datos del informe 2025022."""
    return {
        "id": "UKAB-2025022",
        "autoridad": "UK Airprox Board",
        "numero": "2025022",
        "enlace": "https://www.airproxboard.org.uk/Documents/Download/2501/x/3600",
        "catalogo": "https://www.airproxboard.org.uk/Documents/Download/2501/x/4178",
        "reunion": "2025-04-23",
        "instante": instante("2025-03-03T12:15Z"),
        "luz": "Daylight",
        "pais": "GB",
        "posicion": {"punto": {"lat": 52.08333, "lon": -1.21667}, "descripcion": "5NM E Banbury"},
        "altitud": {"pies": 375, "texto": "375ft", "referencia": "sin_referencia"},
        "espacio_aereo": {"clase": "G", "nombre": "London FIR"},
        "aeronave": {
            "tipo": "OTHER - Military - Atlas A400M",
            "categoria": "Fixed Wing - Aeroplane",
        },
        "objeto": {
            "clasificacion": "Drone",
            "categoria_catalogo": "RPAS/UAS",
            "tipo_catalogo": "OTHER - UAS/RPAS",
            "descripcion": (
                "a grey quadcopter type UAS was observed to pass over the top of the aircraft"
            ),
            "clase": "multirrotor_pequeno",
            "altura_m": {"min": 99.06, "max": 129.54},
        },
        "separacion": {
            "texto": "50ft V/0m H",
            "vertical_m": {"min": 15.24, "max": 15.24},
            "horizontal_m": {"min": 0, "max": 0},
        },
        "riesgo_notificado": "Medium",
        "categoria_riesgo": "A",
        "fuente": {
            "medio": "UK Airprox Board",
            "fiabilidad": "A",
            "credibilidad": 2,
            "licencia": "Open Government Licence v3.0",
        },
        "procedencia": {
            "instante": {"origen": "oficial", "metodo": "parser", "fuentes": ["UKAB-2025022"]},
        },
        "control": {"alta": instante("2025-12-01T10:00Z"), "lector": "airprox/1"},
    }


def documento_oficial() -> Documento:
    return {
        "id": "bundestag_dip:21/1234",
        "fuente_detalle": "bundestag_dip",
        "tipo": "respuesta_parlamentaria",
        "autoridad": "Bundesregierung",
        "pais": "DE",
        "idioma": "de",
        "titulo": "Drohnenüberflüge über Liegenschaften der Bundeswehr",
        "enlace": "https://dserver.bundestag.de/btd/21/012/2101234.pdf",
        "fecha": "2025-11-20",
        "fiabilidad": "A",
        "credibilidad": 1,
        "estado": "extraido",
        "pasajes": {"numero": 2, "letras": 1800},
        "sucesos": [],
        "estadisticas": ["EST-0123456789abcdef"],
        "control": {"alta": instante("2025-12-01T10:00Z"), "metodo": "extractor"},
    }


def estadistica_oficial() -> Documento:
    return {
        "id": "EST-0123456789abcdef",
        "autoridad": "Bundesregierung",
        "pais_autoridad": "DE",
        "documento": {
            "id": "bundestag_dip:21/1234",
            "tipo": "respuesta_parlamentaria",
            "enlace": "https://dserver.bundestag.de/btd/21/012/2101234.pdf",
            "fecha": "2025-11-20",
        },
        "periodo": {"inicio": "2025-01-01", "fin": "2025-09-30"},
        "ambito": {"pais": "DE", "categoria": "base_militar"},
        "metrica": "sobrevuelos",
        "cifra": {"min": 536, "max": 536},
        "frase": (
            "Im Jahr 2025 wurden bislang 536 Drohnenüberflüge über Liegenschaften der "
            "Bundeswehr gemeldet."
        ),
        "confianza": 0.95,
        "fuente": {"medio": "Bundesregierung", "fiabilidad": "A", "credibilidad": 1},
        "procedencia": {
            "cifra": {
                "origen": "oficial",
                "metodo": "extractor",
                "fuentes": ["bundestag_dip:21/1234"],
            }
        },
        "control": {"alta": instante("2025-12-01T10:00Z")},
    }


def impacto_guerra() -> Documento:
    """Impacto con lugar de la capa de guerra: el de t.me/kharkivoda/31198, enlazado al ataque."""
    return {
        "id": "EODI-IG-2025-00001",
        "tipo": "impacto_guerra",
        "sentido": "RU_UA",
        "ataque": "EODI-UA-2025-0001",
        "enlace_ataque": "periodo",
        "region": "UA-63",
        "lugar": {
            "id": "katotth:UA63120270010096107", "nombre": "Харків", "nombre_latino": "Kharkiv",
            "nivel": "localidad", "punto": {"lat": 49.99, "lon": 36.23}, "radio_km": 15.0,
        },
        "impacto": "impacto",
        "categorias_objetivo": ["residencial"],
        "fecha": instante("2025-06-01T06:45Z"),
        "credibilidad": 2,
        "fuentes": [{
            "id": "kharkivoda-31198", "enlace": "https://t.me/kharkivoda/31198",
            "medio": "Харківська ОВА", "fecha": instante("2025-06-01T06:45Z"), "idioma": "uk",
            "fiabilidad": "B", "credibilidad": 2,
            "frase_origen": "Окупанти вдарили дроном по Київському району Харкова.",
            "replicas": 0, "campos_respaldados": ["lugar", "impacto", "categorias_objetivo"],
            "es_autoridad": False, "interna_fuera_de_ucrania": False, "publica": True,
        }],
        "lecturas": [{"fuente_id": "kharkivoda-31198", "metodo": "parser",
                      "version": "mensajes-guerra/1"}],
        "control": {"alta": instante("2025-06-01T07:17Z"),
                    "ultima_actualizacion": instante("2025-06-01T07:17Z")},
    }  # fmt: skip


def restriccion() -> Documento:
    """Restricción de Rosaviatsia (t.me/favt_info/8287 y 8289)."""
    return {
        "id": "favt_info-8287",
        "aeropuerto": {"nombre": "КАЛУГА (Грабцево)", "oaci": "UUBC"},
        "inicio": instante("2025-09-30T16:47Z"),
        "fin": instante("2025-10-01T03:42Z"),
        "horas": 10.92,
        "fuente_inicio": "https://t.me/favt_info/8287",
        "fuente_fin": "https://t.me/favt_info/8289",
        "emparejado": "respuesta",
    }


def deduccion() -> Documento:
    """Lo que deja el motor de deducción para un incidente (origen deducido, interno)."""
    return {
        "origen": "deducido",
        "metodo": "regla",
        "version_motor": "1.0.0",
        "version_catalogo": "1.0.0",
        "version_zonas": "1.0.0",
        "reglas": [{"nombre": "distancia", "version": "1.0.0"}],
        "compatibles": [{"clase": "multirrotor_consumo", "reglas": ["meteorologia"]}],
        "descartadas": [
            {
                "clase": "multirrotor_consumo_sub250",
                "por": [
                    {
                        "regla": "meteorologia",
                        "version": "1.0.0",
                        "efecto": "descarta",
                        "motivo": "viento por encima de su límite",
                        "datos": {"viento_banda_ms": 18.0},
                    }
                ],
            }
        ],
        "indeterminadas": [{"clase": "fpv", "motivo": "sin_datos"}],
        "conflictos": [],
        "conclusiones": [],
        "huella": "a" * 64,
        "evaluado": {"precision": "minuto", "valor": "2025-09-23T10:00Z"},
    }


def _evidencia(efecto: str) -> Documento:
    return {
        "regla": "distancia",
        "version": "1.0.0",
        "efecto": efecto,
        "motivo": "prueba",
        "datos": {"distancia_km": 12.0},
    }


def deduccion_completa() -> Documento:
    """Bloque del motor de deducción con todos sus campos (internos) rellenos."""
    return {
        **deduccion(),
        "compatibles": [
            {
                "clase": "multirrotor_consumo",
                "reglas": ["distancia"],
                "impactos": 2,
                "condiciones": [_evidencia("condicion")],
                "indicios": [_evidencia("a_favor")],
                "anotaciones": [_evidencia("anotacion")],
            }
        ],
        "indeterminadas": [
            {
                "clase": "fpv",
                "motivo": "conflicto",
                "indicios": [_evidencia("a_favor")],
                "anotaciones": [_evidencia("anotacion")],
            }
        ],
        "conflictos": [
            {
                "clase": "fpv",
                "motivo": "conflicto",
                "descartan": [_evidencia("descarta")],
                "apoyan": [_evidencia("a_favor")],
            }
        ],
        "conclusiones": [
            {
                "regla": "distancia",
                "version": "1.0.0",
                "conclusion": "despegue_cercano_o_largo_alcance",
                "datos": {"exterior_km": 40.0},
            }
        ],
        "exterior": {
            "tierra_extranjera_km": 16.1,
            "pais_extranjero": "SE",
            "costa_km": 0.0,
            "aguas_internacionales_km": 22.2,
        },
        "gnss": "media",
        "origenes": [{"zona": "kursk_khalino", "distancia_km": 120.5}],
        "alcance_exigido_km": 120.5,
        "zona_despegue": {
            "regla": "zona_despegue",
            "version": "1.0.0",
            "clases": [{"clase": "multirrotor_consumo", "radio_km": 41.0}],
        },
        "deriva": {
            "regla": "deriva",
            "version": "1.0.0",
            "resultado": "indeterminado",
            "motivo": "prueba",
            "datos": {"viento_ms": 1.0},
        },
        "horizonte_radar": {"regla": "horizonte_radar", "version": "1.0.0", "sectores": []},
        "direccion_entrada": {
            "regla": "direccion_entrada",
            "version": "1.0.0",
            "tipo": "declarada",
            "desde_grados": 75.0,
            "pais": "BY",
            "distancia_km": 32.5,
            "origen": "oficial_citado",
            "fuente": "F1-declaracion-1",
            "frase": "the drone entered from Belarus",
            "sectores": [0.0, 0.0, 0.5, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "concentracion": 0.9,
            "clases": ["multirrotor_consumo"],
        },
    }


def perdida_luz(zona: str = "ciudad") -> Documento:
    """Pérdida de luz nocturna de Járkov tras el ataque del 22 de marzo de 2024
    (proceso/luces.py)."""
    documento: Documento = {
        "zona": zona,
        "region": "UA-63",
        "perdida_pct": 87,
        "noche": "2024-03-22",
        "noches": ["2024-03-22", "2024-03-23"],
        "referencia": {"desde": "2024-02-29", "hasta": "2024-03-20", "noches": 6, "brillo": 5.1},
        "brillo": 0.66,
        "origen": "medido",
    }
    if zona == "ciudad":
        documento["ciudad"] = {
            "id": "katotth:UA63120270010096107",
            "nombre": "Харків",
            "punto": {"lat": 49.99232, "lon": 36.23101},
        }
    return documento
