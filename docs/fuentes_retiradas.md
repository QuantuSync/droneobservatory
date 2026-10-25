# Fuentes oficiales retiradas de la recogida

Fuentes de `configuracion/fuentes_oficiales.json` que se quitaron porque ya no se pueden leer y
solo sumaban fallos. Si vuelven a responder, se añaden otra vez con su entrada de siempre.

| Fuente | Retirada | Por qué |
|---|---|---|
| `csn_sucesos` (Consejo de Seguridad Nuclear, RSS de sucesos notificados, `https://www.csn.es/sucesos-notificados/-/asset_publisher/AhgtIexAjt0q/rss`) | 25 de octubre de 2026 | Desde el 23 de octubre de 2026 a las 13:21 UTC, csn.es responde 403 a todas las peticiones de la recogida, también a su portada y con cualquier identificación (la del observatorio o la de un navegador); desde otra red la misma dirección responde 200 con el canal. Es un bloqueo de la red de la recogida, no un cambio de dirección del canal, y la pausa de 6 horas tras tres fallos no lo arregla. |
