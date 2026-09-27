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
