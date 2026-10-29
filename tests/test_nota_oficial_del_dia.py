"""La alerta de Letonia del 22 de octubre de 2026 (EODI-2026-00704) nació de cuatro notas
oficiales que solo dan el día: entraron como artículos a las 00:00 UTC y la hora del suceso de su
texto («no plkst. 12.39», las 09:39 UTC) se descartaba por posterior a la nota. La ficha publicaba
la fecha de publicación."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from proceso import extraccion
from proceso.fechas import hora_en_utc
from proceso.textos_dron import hora_local
from proceso.validacion_ficha import fecha_valida

FRASE = (
    "Nacionālie bruņotie spēki informē, ka no plkst. 12.39 iespējams apdraudējums Latvijas "
    "gaisa telpā pašlaik ir izsludināts Krāslavas un Rēzeknes novadā."
)
NOTA = {
    "url": "https://www.mil.lv/lv/zinas/iespejams-apdraudejums-latvijas-gaisa-telpa-kraslavas-uz-rezeknes-novada",
    "medio": "Nacionālie bruņotie spēki",
    "fecha": "2026-10-22T00:00:00Z",
}
AHORA = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)


def test_la_nota_del_dia_cuenta_el_dia_entero() -> None:
    (publicada,) = extraccion.publicaciones([NOTA], [NOTA["url"]])
    assert publicada == datetime(2026, 10, 23, tzinfo=UTC)
    inicio = "2026-10-22T09:39"
    assert fecha_valida("inicio", inicio, FRASE, publicada, AHORA) is None


def test_un_articulo_de_prensa_a_medianoche_no_cambia() -> None:
    articulo = {**NOTA, "medio": "LSM", "url": "https://lsm.lv/x"}
    (publicada,) = extraccion.publicaciones([articulo], [articulo["url"]])
    assert publicada == datetime(2026, 10, 22, tzinfo=UTC)
    assert fecha_valida("inicio", "2026-10-22T09:39", FRASE, publicada, AHORA) is not None


def test_una_nota_con_hora_no_cambia() -> None:
    nota = {**NOTA, "fecha": "2026-10-22T10:05:00Z"}
    (publicada,) = extraccion.publicaciones([nota], [nota["url"]])
    assert publicada == datetime(2026, 10, 22, 10, 5, tzinfo=UTC)


def test_plkst_es_la_hora_local_letona() -> None:
    assert hora_local(FRASE, con_dron=False) == (12, 39)
    cierre = "ir noslēdzies plkst. 13.16."
    assert hora_local(cierre, con_dron=False) == (13, 16)
    riga = ZoneInfo("Europe/Riga")
    tomada = datetime(2026, 10, 22, 12, 39, tzinfo=UTC)
    assert hora_en_utc(tomada, "minuto", FRASE, riga) == datetime(2026, 10, 22, 9, 39, tzinfo=UTC)
