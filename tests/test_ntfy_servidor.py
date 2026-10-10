"""El servidor ntfy de los avisos (servidor/ntfy.sh, configuracion/ntfy/, docs/avisos.md): nadie
lee ni publica por defecto, caché de 24 horas, sin adjuntos, iPhone por ntfy.sh, tope de memoria
en sus servicios, solo 80 y 443 además de SSH, y el envío al final de la recogida que publica."""

import json
import re
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
SERVIDOR = RAIZ / "servidor"


def _texto(ruta: str) -> str:
    return (RAIZ / ruta).read_text(encoding="utf-8")


def _yaml_plano(texto: str) -> dict[str, Any]:
    """server.yml solo tiene claves de primer nivel con un valor escalar."""
    datos: dict[str, Any] = {}
    for linea in texto.splitlines():
        if not linea.strip() or linea.lstrip().startswith("#"):
            continue
        clave, _, valor = linea.partition(":")
        valor = valor.strip()
        datos[clave.strip()] = (
            json.loads(valor)
            if valor[:1] == '"' or valor in ("true", "false") or valor.isdigit()
            else valor
        )
    return datos


def test_configuracion_de_ntfy() -> None:
    config = _yaml_plano(_texto("configuracion/ntfy/server.yml"))
    assert config["base-url"] == "https://ntfy.droneobservatory.eu"
    assert config["auth-default-access"] == "deny-all"
    assert config["enable-signup"] is False
    assert config["cache-duration"] == "24h"
    assert config["upstream-base-url"] == "https://ntfy.sh"
    assert config["listen-http"].startswith("127.0.0.1:")
    assert config["behind-proxy"] is True
    # Sin adjuntos: sin carpeta de adjuntos, ntfy los rechaza.
    assert not any(clave.startswith("attachment") for clave in config)
    for limite in ("visitor-subscription-limit", "visitor-request-limit-burst"):
        assert isinstance(config[limite], int) and config[limite] > 0
    # Ningún secreto en el repositorio: las claves de Web Push van en el servidor.
    assert "web-push-private-key" not in config and "auth-users" not in config


def test_caddy_solo_lets_encrypt_y_al_ntfy_local() -> None:
    caddy = _texto("configuracion/ntfy/Caddyfile")
    assert "ntfy.droneobservatory.eu {" in caddy
    assert "cert_issuer acme" in caddy
    assert "reverse_proxy 127.0.0.1:2586" in caddy


def test_topes_de_memoria_y_puertos() -> None:
    ntfy = (SERVIDOR / "ntfy.sh").read_text(encoding="utf-8")
    configuracion = (SERVIDOR / "configuracion.sh").read_text(encoding="utf-8")
    for servicio, variable in (("ntfy", "NTFY_MEMORIA"), ("caddy", "CADDY_MEMORIA")):
        bloque = re.search(rf"{servicio}\.service\.d/eodi\.conf <<FIN\n(.*?)\nFIN", ntfy, re.S)
        assert bloque is not None and f"MemoryMax=${variable}" in bloque.group(1)
        assert re.search(rf'^{variable}="\d+M"', configuracion, re.M)
    endurecer = (SERVIDOR / "endurecer.sh").read_text(encoding="utf-8")
    assert "tcp dport { 80, 443 } ct state new accept" in endurecer
    reconstruir = (SERVIDOR / "reconstruir.sh").read_text(encoding="utf-8")
    assert "--port 80 " in reconstruir and "--port 443 " in reconstruir


def test_permisos_solo_lectura_para_todos_y_escritura_para_los_dos_usuarios() -> None:
    ntfy = (SERVIDOR / "ntfy.sh").read_text(encoding="utf-8")
    assert 'access everyone "$tema" read-only' in ntfy
    assert 'access observatorio "$tema" write-only' in ntfy
    assert 'access lucas "$tema" read-write' in ntfy
    assert "--role=admin" not in ntfy
    assert "everyone" not in ntfy.replace('access everyone "$tema" read-only', "")


def test_el_envio_va_tras_publicar_bien() -> None:
    recogida = (SERVIDOR / "recogida.sh").read_text(encoding="utf-8")
    publicar = recogida.index('if publicar_en_almacen "$modo_pub"; then')
    envio = recogida.index("-m recogida.avisos enviar")
    no_publicado = recogida.index('echo "aviso: los ficheros no se publicaron en el almacén"')
    assert publicar < envio < no_publicado
    ensayo = (SERVIDOR / "ensayo.sh").read_text(encoding="utf-8")
    assert "-m recogida.avisos ensayo" in ensayo and "recogida.avisos enviar" not in ensayo
