# Fuentes oficiales retiradas de la recogida

Fuentes de `configuracion/fuentes_oficiales.json` que se quitaron porque ya no se pueden leer y
solo sumaban fallos. Si vuelven a responder, se añaden otra vez con su entrada de siempre. Si
solo bloquean la dirección del servidor, se añaden como delegadas (`"delegada": true`) y se leen a
través del lector delegado de la web ([lector_delegado.md](lector_delegado.md)).

| Fuente | Retirada | Por qué |
|---|---|---|
| `mod_lv` (Ministerio de Defensa de Letonia, página de noticias, `https://www.mod.gov.lv/lv/zinas`) | 26 de octubre de 2026 | Desde el 21 de octubre de 2026 a las 16:20 UTC se cortaba en cada recogida al agotar su tope de 45 s (22 recogidas seguidas el 26 de octubre, con pausas de 6 horas entre medias). No es lentitud ni un cambio de dirección: mod.gov.lv no acepta la conexión en el puerto 443 desde la dirección del servidor (centro de datos de Hetzner), y el nombre resuelve a la misma dirección de siempre. Se ha visto cargar con normalidad desde alguna red de fuera de Hetzner y de Letonia, así que no es un corte del sitio. Pero el 27 de octubre de 2026, de 00:00 a 00:30 UTC, tampoco aceptó la conexión en el 443 (tiempo agotado, sin respuesta) desde el lector delegado de Vercel (Estocolmo), desde un runner de GitHub Actions (Azure, Estados Unidos) ni desde una conexión doméstica en España; solo el puerto 80 respondió, con una redirección al 443. Otras webs letonas (sargs.lv) respondían al momento desde todas. Por eso no se puede delegar con los proveedores del observatorio (Hetzner, Vercel y GitHub) y sigue retirada; si su 443 vuelve a responder desde Vercel, se añade como delegada (basta con su entrada en la configuración y en la lista del lector). Su aviso oficial sigue llegando por la prensa y por `riga_airport`. |

## Fuentes que volvieron

| Fuente | Retirada | Vuelta | Cómo |
|---|---|---|---|
| `csn_sucesos` (Consejo de Seguridad Nuclear, RSS de sucesos notificados, `https://www.csn.es/sucesos-notificados/-/asset_publisher/AhgtIexAjt0q/rss`) | 25 de octubre de 2026 | 27 de octubre de 2026 | Del 23 de octubre de 2026 a las 13:21 UTC hasta el 26, csn.es respondía 403 a todas las peticiones de la recogida (también a su portada y con cualquier identificación), mientras desde otra red respondía 200 con el canal: un bloqueo de la dirección del servidor. Vuelve como fuente delegada: se lee a través del lector delegado de la web, que lo descarga con código 200. El 27 de octubre de 2026 csn.es respondía 200 también desde el servidor; la delegación evita que un bloqueo nuevo lo vuelva a dejar fuera. |
