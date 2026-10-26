# Fuentes oficiales retiradas de la recogida

Fuentes de `configuracion/fuentes_oficiales.json` que se quitaron porque ya no se pueden leer y
solo sumaban fallos. Si vuelven a responder, se añaden otra vez con su entrada de siempre.

| Fuente | Retirada | Por qué |
|---|---|---|
| `csn_sucesos` (Consejo de Seguridad Nuclear, RSS de sucesos notificados, `https://www.csn.es/sucesos-notificados/-/asset_publisher/AhgtIexAjt0q/rss`) | 25 de octubre de 2026 | Desde el 23 de octubre de 2026 a las 13:21 UTC, csn.es responde 403 a todas las peticiones de la recogida, también a su portada y con cualquier identificación (la del observatorio o la de un navegador); desde otra red la misma dirección responde 200 con el canal. Es un bloqueo de la red de la recogida, no un cambio de dirección del canal, y la pausa de 6 horas tras tres fallos no lo arregla. |
| `mod_lv` (Ministerio de Defensa de Letonia, página de noticias, `https://www.mod.gov.lv/lv/zinas`) | 26 de octubre de 2026 | Desde el 21 de octubre de 2026 a las 16:20 UTC se cortaba en cada recogida al agotar su tope de 45 s (22 recogidas seguidas el 26 de octubre, con pausas de 6 horas entre medias). No es lentitud ni un cambio de dirección: mod.gov.lv no acepta la conexión (ni en el puerto 443 ni en el 80; el nombre resuelve a la misma dirección de siempre) desde la red de la recogida ni desde una conexión doméstica de otro país, mientras otras webs letonas (sargs.lv) responden al momento. Es un bloqueo de red de fuera de Letonia, y un tope mayor no lo arreglaría. Su aviso oficial sigue llegando por la prensa y por `riga_airport`. |
