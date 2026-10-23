"""El titular lo decide un solo sitio (proceso/decidir.decidir_titulo): una prueba por causa de los
titulares que oscilaban o se publicaban mal el 22-23 de octubre de 2026, con la ficha real."""

import copy
import json

from esquema import Documento
from proceso import atribucion, decidir, referencia, titulares

GENTILICIO_EN = ("Russian", "Ukrainian", "Turkish")


def _copia(id_: str) -> Documento:
    ruta = referencia.DIRECTORIO / "fichas" / f"{id_}.json"
    documento: Documento = json.loads(ruta.read_text(encoding="utf-8"))
    return documento


def _ficha(id_: str, titulo: dict[str, str], enlace: str, pais: str) -> Documento:
    """Lo que el titular necesita de una ficha: su fuente, su país, su estado y su presencia."""
    return {
        "id": id_,
        "titulo": titulo,
        "fuentes": [{"id": "f1", "enlace": enlace, "frase_origen": ""}],
        "lugar": {"pais": pais, "nivel": "region"},
        "estado": {"actual": "notificado", "historial": []},
        "presencia_dron": "no_confirmada",
    }


def _sin_atribucion(es: str, en: str) -> dict[str, str]:
    return atribucion.titulo_sin_atribucion({"titulo": {"es": es, "en": en}, "fuentes": []})


def test_la_revision_a_mano_pasa_por_la_presencia_y_la_atribucion() -> None:
    # Tulcea (2025-00378): la revisión a mano del titular entraba tal cual al guardar y ganaba a
    # la atribución y a la presencia; cada hora se publicaba «Drones rusos…» sin atribución.
    tulcea = _copia("EODI-2025-00378")
    tulcea["titulo"] = {
        "es": "Drones rusos cerca de la frontera en Tulcea: dos F-16 despegan de la base de Borcea",
        "en": "Russian drones near the border in Tulcea: two F-16s take off from Borcea air base",
    }
    decidido = decidir.aplicar(tulcea)
    assert decidido["presencia_dron"] == "no_confirmada"
    assert decidido["titulo"] == {
        "es": "Posibles drones cerca de la frontera en Tulcea: dos F-16 despegan de la base de "
        "Borcea",
        "en": "Possible drones near the border in Tulcea: two F-16s take off from Borcea air base",
    }


def test_el_titular_decidido_no_cambia_con_las_demas_reglas() -> None:
    # Sin vaivén: guardar otra vez, ajustar a la presencia o quitar la atribución dejan el mismo.
    decidido = decidir.aplicar(_copia("EODI-2025-00378"))
    assert decidir.aplicar(copy.deepcopy(decidido))["titulo"] == decidido["titulo"]
    assert titulares.ajustar_incidente(decidido)["titulo"] == decidido["titulo"]
    assert atribucion.titulo_segun_atribucion(decidido) == decidido["titulo"]


def test_la_nacionalidad_del_espacio_aereo_se_queda() -> None:
    # 2026-00650: «Ukrainian airspace» perdía «Ukrainian» y el titular sugería espacio rumano.
    assert _sin_atribucion(
        "Alerta RO-Alert en Tulcea por posibles drones detectados en el espacio aéreo ucraniano",
        "RO-Alert issued in Tulcea over possible drones detected in Ukrainian airspace",
    ) == {
        "es": "Alerta RO-Alert en Tulcea por posibles drones detectados en el espacio aéreo "
        "ucraniano",
        "en": "RO-Alert issued in Tulcea over possible drones detected in Ukrainian airspace",
    }


def test_la_nacionalidad_de_una_persona_se_queda() -> None:
    # 2026-00222 (Vilna): «Ukrainian citizen» pasó a «Citizen»; la persona no es el autor del dron.
    titulo = _sin_atribucion(
        "Un ciudadano ucraniano detenido por volar un dron cerca del aeropuerto de Vilna",
        "Ukrainian citizen detained for flying a drone near Vilnius airport",
    )
    assert titulo["es"].startswith("Un ciudadano ucraniano")
    assert titulo["en"].startswith("Ukrainian citizen")


def test_la_nacionalidad_del_dron_se_quita_en_los_dos_idiomas() -> None:
    # 2026-00668 (Egeo): «Turkish» se quitaba del inglés y «turcos» se quedaba en español.
    titulo = _sin_atribucion(
        "Posibles drones y aviones turcos entran sin autorización en el FIR de Atenas",
        "Possible Turkish drones and aircraft enter Athens FIR without authorization",
    )
    assert titulo == {
        "es": "Posibles drones y aviones entran sin autorización en el FIR de Atenas",
        "en": "Possible drones and aircraft enter Athens FIR without authorization",
    }
    rusos = _sin_atribucion(
        "Drones militares rusos sobre Tulcea", "Russian Shahed drones over Tulcea"
    )
    assert rusos == {"es": "Drones militares sobre Tulcea", "en": "Shahed drones over Tulcea"}


def test_un_titular_solo_afirma_drones_que_nombra_una_cita() -> None:
    # 2026-00668: la cita guardada hablaba de ocho aeronaves; el titular se rehace con la cita
    # que nombra los drones (cinco UAV según el Estado Mayor), sin su país y con la presencia.
    enlace = (
        "https://inewsgr.com/441/synechizoun-oi-tourkikes-voltes-sto-aigaio-machitika-"
        "kataskopeftiko-kai-drones-ston-elliniko-enaerio-choro.htm"
    )
    egeo = _ficha(
        "EODI-2026-00668",
        {
            "es": "Posibles drones y aviones turcos entran sin autorización en el FIR de Atenas "
            "sobre el Egeo",
            "en": "Possible drones and aircraft enter Athens FIR over the Aegean without "
            "authorization",
        },
        enlace,
        "GR",
    )
    titulo = decidir.decidir_titulo(egeo)
    assert titulo == {
        "es": "Cinco posibles drones y tres aviones entran sin autorización en el FIR de Atenas "
        "sobre el mar Egeo",
        "en": "Five possible drones and three aircraft enter the Athens FIR over the Aegean Sea "
        "without authorization",
    }
    revision = decidir.revision_de(egeo, "titulo")
    assert revision is not None and "UAV" in revision["cita"]
    assert not any(g in titulo["en"] for g in GENTILICIO_EN)
    assert "turc" not in titulo["es"]


def test_ningun_otro_paso_escribe_el_titular() -> None:
    # Los pasos que antes rehacían el titular (el control, la revisión a mano, la barrera, las
    # declaraciones oficiales) lo piden a decidir.py o lo dejan para el guardado.
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent
    for fichero in ("recogida/control_fichas.py", "recogida/revisados.py", "recogida/barrera.py",
                    "recogida/declaraciones_oficiales.py"):  # fmt: skip
        texto = (raiz / fichero).read_text(encoding="utf-8")
        assert "titulo_segun_atribucion(" not in texto, fichero
        assert "titulares.ajustar_incidente(" not in texto, fichero


def test_k_cuenta_el_dato_que_cambia_y_vuelve_cada_hora() -> None:
    # Tulcea (2025-00378): cada recogida, la atribución quitaba «rusos» y se quedaba el titular
    # viejo; el inicio de Aalborg (2025-00238) iba y volvía entre dos pasos. Un arreglo deshecho
    # una sola vez (la zona de 2026-00019) no cuenta.
    from proceso import auditoria_fichas

    viejo, sin = {"es": "Drones rusos"}, {"es": "Drones"}
    cambios = [
        {"entidad_id": "EODI-2025-00378", "tabla": "incidentes_motivos",
         "anterior": {"titulo": viejo}, "nuevo": {"titulo": sin, "motivo": "atribución"}}
        for _ in range(4)
    ] + [
        {"entidad_id": "EODI-2025-00238", "tabla": "incidentes",
         "anterior": {"tiempo": a, "control": 1}, "nuevo": {"tiempo": b, "control": 2}}
        for a, b in [(55, 95), (95, 55)] * 2
    ] + [
        {"entidad_id": "EODI-2026-00019", "tabla": "incidentes",
         "anterior": {"zona": a}, "nuevo": {"zona": b}}
        for a, b in [("frontera", None), (None, "frontera")]
    ]  # fmt: skip
    assert auditoria_fichas.oscilan(cambios) == {
        "EODI-2025-00238": ["tiempo"],
        "EODI-2025-00378": ["titulo"],
    }
    resultado = auditoria_fichas.auditar([], cambios)
    assert resultado["K"] == []  # ninguna vigente entre los documentos
