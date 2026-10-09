"""Copia pública de reserva del almacén de la web (almacen/reserva.py), con almacenes S3 en
memoria."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from almacen import copias, reserva
from tests.s3_falso import S3Falso

AHORA = datetime(2026, 10, 9, 14, 2, tzinfo=UTC)
CREDENCIALES = copias.Credenciales("id", "secreto")


def cliente(destino: copias.Destino) -> tuple[copias.Copias, S3Falso]:
    s3 = S3Falso(destino.bucket)
    s3.existe_bucket = True
    return copias.Copias(destino, CREDENCIALES, s3, lambda _s: None), s3


@pytest.fixture
def almacenes() -> tuple[copias.Copias, S3Falso, copias.Copias, S3Falso]:
    principal, s3p = cliente(reserva.destinos()[0])
    copia, s3r = cliente(reserva.destinos()[1])
    return principal, s3p, copia, s3r


def publicar(principal: copias.Copias, clave: str, cuerpo: bytes) -> None:
    principal.subir(
        clave,
        cuerpo,
        {
            "Content-Type": "application/json",
            "Cache-Control": "public, max-age=60",
            "Content-Encoding": "gzip",
            "x-amz-meta-licencia": "CC BY 4.0",
        },
    )


def test_la_reserva_es_publica_y_esta_en_otra_ubicacion() -> None:
    datos = json.loads(reserva.CONFIGURACION.read_text(encoding="utf-8"))
    principal, copia = reserva.destinos()
    assert principal.ubicacion != copia.ubicacion
    assert principal.bucket != copia.bucket
    assert (
        datos["reserva"]["publico"]
        == f"https://{copia.bucket}.{copia.ubicacion}.your-objectstorage.com"
    )
    assert datos["en_la_web"] == "/almacen"


def test_copia_lo_nuevo_con_sus_cabeceras_y_el_manifiesto_el_ultimo(
    almacenes: tuple[copias.Copias, S3Falso, copias.Copias, S3Falso],
) -> None:
    principal, _, copia, s3r = almacenes
    publicar(principal, reserva.MANIFIESTO, b"manifiesto")
    publicar(principal, "publicacion/ucrania.json", b"ucrania")
    publicar(principal, "estado.json", b"estado")
    pasada = reserva.sincronizar(principal, copia)
    assert pasada.al_dia
    assert pasada.copiados[-1] == reserva.MANIFIESTO
    assert s3r.objetos["publicacion/ucrania.json"][0] == b"ucrania"
    assert s3r.objetos["publicacion/ucrania.json"][1]["x-amz-meta-licencia"] == "CC BY 4.0"
    assert s3r.cabeceras["publicacion/ucrania.json"] == {
        "content-type": "application/json",
        "cache-control": "public, max-age=60",
        "content-encoding": "gzip",
    }
    # Otra pasada sin cambios no sube nada; un cambio se copia.
    puts = sum(1 for m, _ in s3r.peticiones if m == "PUT")
    assert reserva.sincronizar(principal, copia).copiados == []
    assert sum(1 for m, _ in s3r.peticiones if m == "PUT") == puts
    publicar(principal, "estado.json", b"estado nuevo")
    assert reserva.sincronizar(principal, copia).copiados == ["estado.json"]


def test_borra_lo_retirado_pero_nunca_si_el_principal_viene_vacio(
    almacenes: tuple[copias.Copias, S3Falso, copias.Copias, S3Falso],
) -> None:
    principal, s3p, copia, s3r = almacenes
    for clave in (reserva.MANIFIESTO, "satelite/a.webp", "versiones/2026-10/metadatos.json",
                  "publicacion/historial/2026-10-09/ucrania.json.gz"):  # fmt: skip
        publicar(principal, clave, clave.encode())
    reserva.sincronizar(principal, copia)
    for clave in ("satelite/a.webp", "versiones/2026-10/metadatos.json",
                  "publicacion/historial/2026-10-09/ucrania.json.gz"):  # fmt: skip
        principal.borrar(clave)
    assert reserva.sincronizar(principal, copia).borrados == ["satelite/a.webp"]
    assert "versiones/2026-10/metadatos.json" in s3r.objetos
    # Un principal vacío (o sin manifiesto) no vacía la reserva.
    s3p.objetos.clear()
    assert reserva.sincronizar(principal, copia).borrados == []
    assert reserva.MANIFIESTO in s3r.objetos


def test_el_mapa_de_fondo_no_se_copia_aqui_pero_se_comprueba(
    almacenes: tuple[copias.Copias, S3Falso, copias.Copias, S3Falso],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    principal, _, copia, s3r = almacenes
    monkeypatch.setattr(reserva, "TOPE_COPIA", 10)
    publicar(principal, "europa-z14.pmtiles", b"teselas grandes")
    pasada = reserva.sincronizar(principal, copia)
    assert pasada.grandes_pendientes == ["europa-z14.pmtiles"] and not pasada.al_dia
    assert "europa-z14.pmtiles" not in s3r.objetos
    copia.subir("europa-z14.pmtiles", b"teselas grandes")
    assert reserva.sincronizar(principal, copia).al_dia


def test_un_fallo_al_copiar_queda_pendiente(
    almacenes: tuple[copias.Copias, S3Falso, copias.Copias, S3Falso],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    principal, _, copia, _ = almacenes
    publicar(principal, "estado.json", b"estado")

    def falla(*_argumentos: object) -> None:
        raise OSError("estado.json: PUT 503")

    monkeypatch.setattr(copia, "subir", falla)
    pasada = reserva.sincronizar(principal, copia)
    assert pasada.pendientes == ["estado.json"] and not pasada.al_dia


def test_comprobar_no_escribe(
    almacenes: tuple[copias.Copias, S3Falso, copias.Copias, S3Falso],
) -> None:
    principal, _, copia, s3r = almacenes
    publicar(principal, "estado.json", b"estado")
    pasada = reserva.sincronizar(principal, copia, escribir=False)
    assert pasada.pendientes == ["estado.json"]
    assert s3r.objetos == {}


def test_estado_y_aviso_de_la_vigilancia(tmp_path: Path) -> None:
    ruta = tmp_path / reserva.ESTADO
    assert reserva.problema_para_vigilancia({}, AHORA) is None
    reserva.anotar(ruta, reserva.Pasada(), AHORA)
    estado = json.loads(ruta.read_text(encoding="utf-8"))
    assert estado["ultima_al_dia"] == "2026-10-09T14:02:00Z"
    assert reserva.problema_para_vigilancia(estado, AHORA + timedelta(minutes=29)) is None
    # Pasadas que fallan: se conserva la última vez al día, y a los 30 minutos avisa.
    reserva.anotar(ruta, None, AHORA + timedelta(minutes=40), "HTTP 503")
    estado = json.loads(ruta.read_text(encoding="utf-8"))
    assert estado["ultima_al_dia"] == "2026-10-09T14:02:00Z"
    frase = reserva.problema_para_vigilancia(estado, AHORA + timedelta(minutes=40))
    assert frase is not None and "2026-10-09 14:02" in frase and "HTTP 503" in frase


def test_principal_anota_la_pasada(
    almacenes: tuple[copias.Copias, S3Falso, copias.Copias, S3Falso],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    principal, _, copia, _ = almacenes
    publicar(principal, "estado.json", b"estado")
    monkeypatch.setenv("EODI_SECRETOS", str(tmp_path))
    por_bucket = {principal.destino.bucket: principal, copia.destino.bucket: copia}
    codigo = reserva.principal([], cliente=lambda d: por_bucket[d.bucket], ahora=lambda: AHORA)
    assert codigo == 0
    estado = json.loads((tmp_path / reserva.ESTADO).read_text(encoding="utf-8"))
    assert estado["copiados"] == 1 and estado["ultima_al_dia"] == "2026-10-09T14:02:00Z"
