"""Base de datos SQLite. Nada se borra: los triggers impiden DELETE y registran cada cambio."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from esquema import Documento
from proceso.validaciones import (
    Error,
    validar_ataque_ucrania,
    validar_episodio,
    validar_incidente,
)

# Tablas de documentos con historial automático y sin DELETE.
TABLAS_CON_HISTORIAL = ("incidentes", "fuentes", "episodios", "ataques_ucrania", "regiones_ucrania")
# Campos de la fuente que dependen del incidente y no se guardan en la tabla común.
CAMPOS_FUENTE_POR_ENTIDAD = frozenset({"credibilidad", "campos_respaldados"})

_TABLAS = """
CREATE TABLE IF NOT EXISTS incidentes (
    id TEXT PRIMARY KEY,
    tipo TEXT NOT NULL,
    estado TEXT NOT NULL,
    documento TEXT NOT NULL CHECK (json_valid(documento))
);
CREATE TABLE IF NOT EXISTS fuentes (
    id TEXT PRIMARY KEY,
    fiabilidad TEXT NOT NULL,
    publica INTEGER NOT NULL,
    documento TEXT NOT NULL CHECK (json_valid(documento))
);
CREATE TABLE IF NOT EXISTS episodios (
    id TEXT PRIMARY KEY,
    documento TEXT NOT NULL CHECK (json_valid(documento))
);
CREATE TABLE IF NOT EXISTS ataques_ucrania (
    id TEXT PRIMARY KEY,
    sentido TEXT NOT NULL,
    estado TEXT NOT NULL,
    documento TEXT NOT NULL CHECK (json_valid(documento))
);
CREATE TABLE IF NOT EXISTS regiones_ucrania (
    id TEXT PRIMARY KEY,
    ataque_id TEXT NOT NULL REFERENCES ataques_ucrania (id),
    region TEXT NOT NULL,
    documento TEXT NOT NULL CHECK (json_valid(documento)),
    UNIQUE (ataque_id, region)
);
CREATE TABLE IF NOT EXISTS afirmaciones (
    id INTEGER PRIMARY KEY,
    entidad_id TEXT NOT NULL,
    campo TEXT NOT NULL,
    fuente_id TEXT NOT NULL REFERENCES fuentes (id),
    documento TEXT NOT NULL CHECK (json_valid(documento)),
    UNIQUE (entidad_id, documento)
);
CREATE TABLE IF NOT EXISTS historial (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tabla TEXT NOT NULL,
    entidad_id TEXT NOT NULL,
    operacion TEXT NOT NULL CHECK (operacion IN ('alta', 'cambio')),
    anterior TEXT,
    nuevo TEXT NOT NULL,
    fecha TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE TABLE IF NOT EXISTS cursores (
    fuente_id TEXT PRIMARY KEY,
    documento TEXT NOT NULL CHECK (json_valid(documento))
);
CREATE TABLE IF NOT EXISTS partes_fallidos (
    enlace TEXT PRIMARY KEY,
    fuente_id TEXT NOT NULL,
    motivo TEXT NOT NULL,
    fecha TEXT NOT NULL,
    resuelto INTEGER NOT NULL DEFAULT 0
);
-- Noticias: solo datos del artículo, nunca su texto. Tablas internas.
CREATE TABLE IF NOT EXISTS articulos (
    url TEXT PRIMARY KEY,
    medio TEXT NOT NULL,
    fecha TEXT NOT NULL,
    idioma TEXT,
    pais TEXT,
    titular TEXT NOT NULL,
    titular_normalizado TEXT NOT NULL,
    temas TEXT NOT NULL CHECK (json_valid(temas)),
    lugares TEXT NOT NULL CHECK (json_valid(lugares)),
    replicas INTEGER NOT NULL DEFAULT 0,
    candidato TEXT
);
CREATE INDEX IF NOT EXISTS articulos_fecha ON articulos (fecha);
CREATE TABLE IF NOT EXISTS candidatos (
    id TEXT PRIMARY KEY,
    documento TEXT NOT NULL CHECK (json_valid(documento))
);
-- Extractor: cada llamada con sus tokens y su coste, cada ficha (válida o no) y los
-- vocabularios que crecen con el uso. Tablas internas.
CREATE TABLE IF NOT EXISTS llamadas_extractor (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL,
    modo TEXT NOT NULL,
    candidato TEXT NOT NULL,
    lote INTEGER NOT NULL,
    entrada INTEGER NOT NULL,
    salida INTEGER NOT NULL,
    escritura_cache INTEGER NOT NULL,
    lectura_cache INTEGER NOT NULL,
    coste REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS extracciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidato TEXT NOT NULL,
    fecha TEXT NOT NULL,
    version TEXT NOT NULL,
    huella TEXT NOT NULL,
    valida INTEGER NOT NULL,
    documento TEXT NOT NULL CHECK (json_valid(documento))
);
CREATE INDEX IF NOT EXISTS extracciones_candidato ON extracciones (candidato);
CREATE TABLE IF NOT EXISTS vocabulario (
    tipo TEXT NOT NULL,
    clave TEXT NOT NULL,
    documento TEXT NOT NULL CHECK (json_valid(documento)),
    PRIMARY KEY (tipo, clave)
);
CREATE TABLE IF NOT EXISTS fusiones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL,
    absorbido TEXT NOT NULL,
    destino TEXT NOT NULL,
    motivo TEXT NOT NULL,
    fuentes TEXT NOT NULL CHECK (json_valid(fuentes)),
    revertida INTEGER NOT NULL DEFAULT 0
);
CREATE TRIGGER IF NOT EXISTS llamadas_extractor_sin_delete BEFORE DELETE ON llamadas_extractor
BEGIN SELECT RAISE(ABORT, 'llamadas_extractor: nada se borra'); END;
CREATE TRIGGER IF NOT EXISTS extracciones_sin_delete BEFORE DELETE ON extracciones
BEGIN SELECT RAISE(ABORT, 'extracciones: nada se borra'); END;
CREATE TRIGGER IF NOT EXISTS vocabulario_sin_delete BEFORE DELETE ON vocabulario
BEGIN SELECT RAISE(ABORT, 'vocabulario: nada se borra'); END;
CREATE TRIGGER IF NOT EXISTS fusiones_sin_delete BEFORE DELETE ON fusiones
BEGIN SELECT RAISE(ABORT, 'fusiones: nada se borra'); END;
CREATE TRIGGER IF NOT EXISTS articulos_sin_delete BEFORE DELETE ON articulos
BEGIN SELECT RAISE(ABORT, 'articulos: nada se borra'); END;
CREATE TRIGGER IF NOT EXISTS candidatos_sin_delete BEFORE DELETE ON candidatos
BEGIN SELECT RAISE(ABORT, 'candidatos: nada se borra'); END;
CREATE TRIGGER IF NOT EXISTS cursores_sin_delete BEFORE DELETE ON cursores
BEGIN SELECT RAISE(ABORT, 'cursores: nada se borra'); END;
CREATE TRIGGER IF NOT EXISTS partes_fallidos_sin_delete BEFORE DELETE ON partes_fallidos
BEGIN SELECT RAISE(ABORT, 'partes_fallidos: nada se borra'); END;
CREATE TRIGGER IF NOT EXISTS historial_sin_update BEFORE UPDATE ON historial
BEGIN SELECT RAISE(ABORT, 'historial: solo admite inserciones'); END;
CREATE TRIGGER IF NOT EXISTS historial_sin_delete BEFORE DELETE ON historial
BEGIN SELECT RAISE(ABORT, 'historial: solo admite inserciones'); END;
CREATE TRIGGER IF NOT EXISTS afirmaciones_sin_update BEFORE UPDATE ON afirmaciones
BEGIN SELECT RAISE(ABORT, 'afirmaciones: una afirmación nueva es una fila nueva'); END;
CREATE TRIGGER IF NOT EXISTS afirmaciones_sin_delete BEFORE DELETE ON afirmaciones
BEGIN SELECT RAISE(ABORT, 'afirmaciones: nada se borra'); END;
"""

_TRIGGERS_POR_TABLA = """
CREATE TRIGGER IF NOT EXISTS {t}_sin_delete BEFORE DELETE ON {t}
BEGIN SELECT RAISE(ABORT, '{t}: nada se borra'); END;
CREATE TRIGGER IF NOT EXISTS {t}_alta AFTER INSERT ON {t}
BEGIN
    INSERT INTO historial (tabla, entidad_id, operacion, anterior, nuevo)
    VALUES ('{t}', NEW.id, 'alta', NULL, NEW.documento);
END;
CREATE TRIGGER IF NOT EXISTS {t}_cambio AFTER UPDATE ON {t}
BEGIN
    INSERT INTO historial (tabla, entidad_id, operacion, anterior, nuevo)
    VALUES ('{t}', NEW.id, 'cambio', OLD.documento, NEW.documento);
END;
"""

ESQUEMA_SQL = _TABLAS + "".join(_TRIGGERS_POR_TABLA.format(t=t) for t in TABLAS_CON_HISTORIAL)


class DocumentoInvalido(ValueError):
    def __init__(self, errores: list[Error]) -> None:
        super().__init__("; ".join(f"{e.ruta}: {e.mensaje}" for e in errores))
        self.errores = errores


def _json(documento: Any) -> str:
    # Serialización canónica: el mismo documento produce siempre el mismo texto.
    return json.dumps(documento, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class Almacen:
    def __init__(self, conexion: sqlite3.Connection) -> None:
        self._conexion = conexion
        # recursive_triggers hace que INSERT OR REPLACE dispare los triggers de DELETE.
        conexion.execute("PRAGMA recursive_triggers = ON")
        conexion.execute("PRAGMA foreign_keys = ON")
        conexion.executescript(ESQUEMA_SQL)

    @classmethod
    def abrir(cls, ruta: Path | str = ":memory:") -> "Almacen":
        return cls(sqlite3.connect(ruta))

    @property
    def conexion(self) -> sqlite3.Connection:
        return self._conexion

    def cerrar(self) -> None:
        self._conexion.close()

    # --- Escritura ----------------------------------------------------------

    def _upsert(self, tabla: str, columnas: dict[str, Any]) -> None:
        nombres = ", ".join(columnas)
        huecos = ", ".join("?" for _ in columnas)
        cambios = ", ".join(f"{c} = excluded.{c}" for c in columnas if c != "id")
        self._conexion.execute(
            f"INSERT INTO {tabla} ({nombres}) VALUES ({huecos}) "
            f"ON CONFLICT (id) DO UPDATE SET {cambios} "
            f"WHERE {tabla}.documento IS NOT excluded.documento",
            tuple(columnas.values()),
        )

    def _guardar_fuentes(self, fuentes: list[Documento]) -> None:
        for fuente in fuentes:
            comun = {k: v for k, v in fuente.items() if k not in CAMPOS_FUENTE_POR_ENTIDAD}
            self._upsert(
                "fuentes",
                {
                    "id": fuente["id"],
                    "fiabilidad": fuente["fiabilidad"],
                    "publica": int(fuente["publica"]),
                    "documento": _json(comun),
                },
            )

    def _guardar_afirmaciones(self, entidad_id: str, afirmaciones: list[Documento]) -> None:
        for afirmacion in afirmaciones:
            self._conexion.execute(
                "INSERT INTO afirmaciones (entidad_id, campo, fuente_id, documento) "
                "VALUES (?, ?, ?, ?) ON CONFLICT (entidad_id, documento) DO NOTHING",
                (entidad_id, afirmacion["campo"], afirmacion["fuente_id"], _json(afirmacion)),
            )

    def guardar_incidente(
        self, documento: Documento, ahora: datetime, vocabulario_modelos: frozenset[str]
    ) -> None:
        errores = validar_incidente(documento, ahora, vocabulario_modelos)
        if errores:
            raise DocumentoInvalido(errores)
        with self._conexion:
            self._guardar_fuentes(documento["fuentes"])
            self._upsert(
                "incidentes",
                {
                    "id": documento["id"],
                    "tipo": documento["tipo"],
                    "estado": documento["estado"]["actual"],
                    "documento": _json(documento),
                },
            )
            self._guardar_afirmaciones(documento["id"], documento.get("afirmaciones", []))

    def guardar_ataque_ucrania(self, documento: Documento, ahora: datetime) -> None:
        errores = validar_ataque_ucrania(documento, ahora)
        if errores:
            raise DocumentoInvalido(errores)
        with self._conexion:
            self._guardar_fuentes(documento["fuentes"])
            self._upsert(
                "ataques_ucrania",
                {
                    "id": documento["id"],
                    "sentido": documento["sentido"],
                    "estado": documento["estado"]["actual"],
                    "documento": _json(documento),
                },
            )
            for region in documento.get("regiones", []):
                self._upsert(
                    "regiones_ucrania",
                    {
                        "id": f"{documento['id']}/{region['region']}",
                        "ataque_id": documento["id"],
                        "region": region["region"],
                        "documento": _json(region),
                    },
                )
            self._guardar_afirmaciones(documento["id"], documento.get("afirmaciones", []))

    def guardar_episodio(self, documento: Documento, ahora: datetime) -> None:
        errores = validar_episodio(documento, ahora)
        if errores:
            raise DocumentoInvalido(errores)
        with self._conexion:
            self._upsert("episodios", {"id": documento["id"], "documento": _json(documento)})

    # --- Recogida ----------------------------------------------------------

    def cursor(self, fuente_id: str) -> Documento | None:
        """Hasta dónde leyó la fuente en la última ejecución."""
        encontrados = self._documentos(
            "SELECT documento FROM cursores WHERE fuente_id = ?", (fuente_id,)
        )
        return encontrados[0] if encontrados else None

    def guardar_cursor(self, fuente_id: str, documento: Documento) -> None:
        with self._conexion:
            self._conexion.execute(
                "INSERT INTO cursores (fuente_id, documento) VALUES (?, ?) "
                "ON CONFLICT (fuente_id) DO UPDATE SET documento = excluded.documento "
                "WHERE cursores.documento IS NOT excluded.documento",
                (fuente_id, _json(documento)),
            )

    def registrar_fallido(self, enlace: str, fuente_id: str, motivo: str, fecha: str) -> None:
        """Parte que el parser no entiende: no se publica, queda aquí con su enlace."""
        with self._conexion:
            self._conexion.execute(
                "INSERT INTO partes_fallidos (enlace, fuente_id, motivo, fecha) "
                "VALUES (?, ?, ?, ?) ON CONFLICT (enlace) DO UPDATE SET "
                "motivo = excluded.motivo, fecha = excluded.fecha, resuelto = 0 "
                "WHERE partes_fallidos.motivo IS NOT excluded.motivo "
                "OR partes_fallidos.fecha IS NOT excluded.fecha OR partes_fallidos.resuelto = 1",
                (enlace, fuente_id, motivo, fecha),
            )

    def resolver_fallido(self, enlace: str) -> None:
        with self._conexion:
            self._conexion.execute(
                "UPDATE partes_fallidos SET resuelto = 1 WHERE enlace = ? AND resuelto = 0",
                (enlace,),
            )

    def fallidos(self, fuente_id: str) -> list[Documento]:
        filas = self._conexion.execute(
            "SELECT enlace, motivo, fecha FROM partes_fallidos "
            "WHERE fuente_id = ? AND resuelto = 0 ORDER BY fecha, enlace",
            (fuente_id,),
        ).fetchall()
        return [{"enlace": e, "motivo": m, "fecha": f} for e, m, f in filas]

    def ataque_con_fuente(self, fuente_id: str) -> Documento | None:
        encontrados = self._documentos(
            "SELECT documento FROM ataques_ucrania WHERE EXISTS ("
            "SELECT 1 FROM json_each(documento, '$.fuentes') "
            "WHERE json_extract(value, '$.id') = ?) ORDER BY id",
            (fuente_id,),
        )
        return encontrados[0] if encontrados else None

    def ataque_con_periodo(self, sentido: str, inicio: str) -> Documento | None:
        """Ataque del mismo sentido cuyo periodo declarado empieza en el mismo instante."""
        encontrados = self._documentos(
            "SELECT documento FROM ataques_ucrania WHERE sentido = ? "
            "AND json_extract(documento, '$.periodo.inicio.valor') = ? ORDER BY id",
            (sentido, inicio),
        )
        return encontrados[0] if encontrados else None

    def siguiente_id_ataque(self, anio: int) -> str:
        prefijo = f"EODI-UA-{anio:04d}-"
        fila = self._conexion.execute(
            "SELECT max(id) FROM ataques_ucrania WHERE id LIKE ?", (prefijo + "%",)
        ).fetchone()
        ultimo = int(fila[0][len(prefijo) :]) if fila and fila[0] else 0
        return f"{prefijo}{ultimo + 1:04d}"

    # --- Noticias ------------------------------------------------------------

    def guardar_articulo(self, articulo: Documento) -> bool:
        """Guarda el artículo si su URL canónica es nueva. True si lo ha guardado."""
        with self._conexion:
            cursor = self._conexion.execute(
                "INSERT INTO articulos (url, medio, fecha, idioma, pais, titular, "
                "titular_normalizado, temas, lugares) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (url) DO NOTHING",
                (
                    articulo["url"],
                    articulo["medio"],
                    articulo["fecha"],
                    articulo.get("idioma"),
                    articulo.get("pais"),
                    articulo["titular"],
                    articulo["titular_normalizado"],
                    _json(articulo.get("temas", [])),
                    _json(articulo.get("lugares", [])),
                ),
            )
        return cursor.rowcount > 0

    def existe_articulo(self, url: str) -> bool:
        fila = self._conexion.execute("SELECT 1 FROM articulos WHERE url = ?", (url,)).fetchone()
        return fila is not None

    def sumar_replica(self, url: str) -> None:
        with self._conexion:
            self._conexion.execute(
                "UPDATE articulos SET replicas = replicas + 1 WHERE url = ?", (url,)
            )

    def titulares_desde(self, fecha: str) -> list[tuple[str, str, str]]:
        """(URL, titular normalizado, fecha) de los artículos publicados desde `fecha`."""
        filas = self._conexion.execute(
            "SELECT url, titular_normalizado, fecha FROM articulos WHERE fecha >= ? "
            "ORDER BY fecha, url",
            (fecha,),
        ).fetchall()
        return [(u, t, f) for u, t, f in filas]

    def asignar_candidato(self, url: str, candidato: str) -> None:
        with self._conexion:
            self._conexion.execute(
                "UPDATE articulos SET candidato = ? WHERE url = ? AND candidato IS NOT ?",
                (candidato, url, candidato),
            )

    def guardar_candidato(self, documento: Documento) -> None:
        with self._conexion:
            self._upsert("candidatos", {"id": documento["id"], "documento": _json(documento)})

    def candidatos_desde(self, fecha: str) -> list[Documento]:
        """Candidatos con actividad desde `fecha`: los que aún pueden crecer."""
        return self._documentos(
            "SELECT documento FROM candidatos "
            "WHERE json_extract(documento, '$.ultimo') >= ? ORDER BY id",
            (fecha,),
        )

    def candidatos(self) -> list[Documento]:
        return self._documentos("SELECT documento FROM candidatos ORDER BY id")

    def articulos(self) -> list[Documento]:
        return self._articulos("")

    def articulos_de(self, urls: list[str]) -> list[Documento]:
        """Los artículos con esas URL, en orden de fecha."""
        return self._articulos(
            "WHERE url IN (SELECT value FROM json_each(?))", (_json(sorted(set(urls))),)
        )

    def _articulos(self, donde: str, parametros: tuple[Any, ...] = ()) -> list[Documento]:
        filas = self._conexion.execute(
            "SELECT url, medio, fecha, idioma, pais, titular, temas, lugares, replicas, candidato "
            f"FROM articulos {donde} ORDER BY fecha, url",
            parametros,
        ).fetchall()
        claves = ("url", "medio", "fecha", "idioma", "pais", "titular", "temas", "lugares")
        return [
            {
                **dict(zip(claves, fila[:6], strict=False)),
                "temas": json.loads(fila[6]),
                "lugares": json.loads(fila[7]),
                "replicas": fila[8],
                "candidato": fila[9],
            }
            for fila in filas
        ]

    # --- Extractor ------------------------------------------------------------

    def registrar_llamada(self, llamada: Documento) -> None:
        with self._conexion:
            self._conexion.execute(
                "INSERT INTO llamadas_extractor (fecha, modo, candidato, lote, entrada, salida, "
                "escritura_cache, lectura_cache, coste) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    llamada["fecha"], llamada["modo"], llamada["candidato"],
                    int(llamada["lote"]), llamada["entrada"], llamada["salida"],
                    llamada["escritura_cache"], llamada["lectura_cache"], llamada["coste"],
                ),
            )  # fmt: skip

    def gastado(self, modo: str, dia: str | None = None) -> float:
        """Dólares gastados en un modo; con `dia` (AAAA-MM-DD), solo ese día UTC."""
        sql = "SELECT coalesce(sum(coste), 0) FROM llamadas_extractor WHERE modo = ?"
        parametros: tuple[Any, ...] = (modo,)
        if dia is not None:
            sql += " AND substr(fecha, 1, 10) = ?"
            parametros += (dia,)
        return float(self._conexion.execute(sql, parametros).fetchone()[0])

    def llamadas(self) -> list[Documento]:
        filas = self._conexion.execute(
            "SELECT fecha, modo, candidato, lote, entrada, salida, escritura_cache, "
            "lectura_cache, coste FROM llamadas_extractor ORDER BY id"
        ).fetchall()
        claves = ("fecha", "modo", "candidato", "lote", "entrada", "salida",
                  "escritura_cache", "lectura_cache", "coste")  # fmt: skip
        return [dict(zip(claves, fila, strict=True)) for fila in filas]

    def guardar_extraccion(
        self, candidato: str, fecha: str, version: str, huella: str, valida: bool,
        documento: Documento,
    ) -> None:  # fmt: skip
        with self._conexion:
            self._conexion.execute(
                "INSERT INTO extracciones (candidato, fecha, version, huella, valida, documento) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (candidato, fecha, version, huella, int(valida), _json(documento)),
            )

    def extracciones(self, candidato: str) -> list[Documento]:
        filas = self._conexion.execute(
            "SELECT fecha, version, huella, valida, documento FROM extracciones "
            "WHERE candidato = ? ORDER BY id",
            (candidato,),
        ).fetchall()
        return [
            {"fecha": f, "version": v, "huella": h, "valida": bool(ok), **json.loads(d)}
            for f, v, h, ok, d in filas
        ]

    def vocabulario(self, tipo: str) -> dict[str, Documento]:
        filas = self._conexion.execute(
            "SELECT clave, documento FROM vocabulario WHERE tipo = ? ORDER BY clave", (tipo,)
        ).fetchall()
        return {clave: json.loads(documento) for clave, documento in filas}

    def ampliar_vocabulario(self, tipo: str, clave: str, documento: Documento) -> bool:
        """Añade la entrada si la clave es nueva. True si la ha añadido."""
        with self._conexion:
            cursor = self._conexion.execute(
                "INSERT INTO vocabulario (tipo, clave, documento) VALUES (?, ?, ?) "
                "ON CONFLICT (tipo, clave) DO NOTHING",
                (tipo, clave, _json(documento)),
            )
        return cursor.rowcount > 0

    def registrar_fusion(
        self, fecha: str, absorbido: str, destino: str, motivo: str, fuentes: list[str]
    ) -> None:
        """Anota una fusión con las fuentes que el absorbido aportó al destino."""
        with self._conexion:
            self._conexion.execute(
                "INSERT INTO fusiones (fecha, absorbido, destino, motivo, fuentes) "
                "VALUES (?, ?, ?, ?, ?)",
                (fecha, absorbido, destino, motivo, _json(fuentes)),
            )

    def revertir_fusion(self, absorbido: str) -> None:
        with self._conexion:
            self._conexion.execute(
                "UPDATE fusiones SET revertida = 1 WHERE absorbido = ? AND revertida = 0",
                (absorbido,),
            )

    def fusiones(self) -> list[Documento]:
        filas = self._conexion.execute(
            "SELECT fecha, absorbido, destino, motivo, fuentes, revertida FROM fusiones ORDER BY id"
        ).fetchall()
        return [
            {"fecha": f, "absorbido": a, "destino": d, "motivo": m,
             "fuentes": json.loads(fu), "revertida": bool(r)}
            for f, a, d, m, fu, r in filas
        ]  # fmt: skip

    def siguiente_id_incidente(self, anio: int) -> str:
        prefijo = f"EODI-{anio:04d}-"
        fila = self._conexion.execute(
            "SELECT max(id) FROM incidentes WHERE id LIKE ?", (prefijo + "%",)
        ).fetchone()
        ultimo = int(fila[0][len(prefijo) :]) if fila and fila[0] else 0
        return f"{prefijo}{ultimo + 1:05d}"

    def siguiente_id_episodio(self, anio: int) -> str:
        prefijo = f"EODI-EP-{anio:04d}-"
        fila = self._conexion.execute(
            "SELECT max(id) FROM episodios WHERE id LIKE ?", (prefijo + "%",)
        ).fetchone()
        ultimo = int(fila[0][len(prefijo) :]) if fila and fila[0] else 0
        return f"{prefijo}{ultimo + 1:04d}"

    # --- Lectura ------------------------------------------------------------

    def _documentos(self, sql: str, parametros: tuple[Any, ...] = ()) -> list[Documento]:
        filas = self._conexion.execute(sql, parametros).fetchall()
        return [json.loads(fila[0]) for fila in filas]

    def incidente(self, id_: str) -> Documento | None:
        encontrados = self._documentos("SELECT documento FROM incidentes WHERE id = ?", (id_,))
        return encontrados[0] if encontrados else None

    def incidentes(self) -> list[Documento]:
        return self._documentos("SELECT documento FROM incidentes ORDER BY id")

    def ataques_ucrania(self) -> list[Documento]:
        return self._documentos("SELECT documento FROM ataques_ucrania ORDER BY id")

    def regiones_ucrania(self, ataque_id: str) -> list[Documento]:
        return self._documentos(
            "SELECT documento FROM regiones_ucrania WHERE ataque_id = ? ORDER BY region",
            (ataque_id,),
        )

    def episodios(self) -> list[Documento]:
        return self._documentos("SELECT documento FROM episodios ORDER BY id")

    def fuentes(self) -> dict[str, Documento]:
        return {f["id"]: f for f in self._documentos("SELECT documento FROM fuentes ORDER BY id")}

    def afirmaciones(self, entidad_id: str) -> list[Documento]:
        return self._documentos(
            "SELECT documento FROM afirmaciones WHERE entidad_id = ? ORDER BY id", (entidad_id,)
        )

    def historial(self, entidad_id: str) -> list[Documento]:
        filas = self._conexion.execute(
            "SELECT tabla, operacion, anterior, nuevo, fecha FROM historial "
            "WHERE entidad_id = ? ORDER BY id",
            (entidad_id,),
        ).fetchall()
        return [
            {
                "tabla": tabla,
                "operacion": operacion,
                "anterior": json.loads(anterior) if anterior is not None else None,
                "nuevo": json.loads(nuevo),
                "fecha": fecha,
            }
            for tabla, operacion, anterior, nuevo, fecha in filas
        ]
