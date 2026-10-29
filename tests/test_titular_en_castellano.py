"""El titular en español dice «dron», no «drone» (EODI-2026-00056 y EODI-2025-00057), y con ello
lleva el «posible» de su presencia, como el inglés."""

from proceso import titulares


def test_drone_pasa_a_dron_y_lleva_el_posible() -> None:
    assert (
        titulares.ajustar("Drone interrumpe el tráfico en el aeropuerto de Larnaca",
                          titulares.NO_CONFIRMADA, "es")
        == "Posible dron interrumpe el tráfico en el aeropuerto de Larnaca"
    )  # fmt: skip
    assert (
        titulares.ajustar("Un drone sobrevuela la base", titulares.CONFIRMADA, "es")
        == "Un dron sobrevuela la base"
    )


def test_drones_y_el_ingles_no_cambian() -> None:
    assert titulares.en_castellano("Drones sobre el aeropuerto de Lieja", "es") == (
        "Drones sobre el aeropuerto de Lieja"
    )
    assert titulares.en_castellano("Drone blocks Cuneo-Levaldigi airport", "en") == (
        "Drone blocks Cuneo-Levaldigi airport"
    )
    assert titulares.concuerda("Dron agrícola bloquea el aeropuerto de Cuneo-Levaldigi", "es")
