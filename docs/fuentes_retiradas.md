# Fuentes oficiales retiradas de la recogida

Fuentes de `configuracion/fuentes_oficiales.json` que se quitaron porque ya no se pueden leer y
solo sumaban fallos. Si vuelven a responder, se añaden otra vez con su entrada de siempre. Si
solo bloquean la dirección del servidor, se añaden como delegadas (`"delegada": true`) y se leen a
través del lector delegado de la web ([lector_delegado.md](lector_delegado.md)).

| Fuente | Retirada | Por qué |
|---|---|---|
| (ninguna ahora) | | |

## Fuentes que volvieron

| Fuente | Retirada | Vuelta | Cómo |
|---|---|---|---|
| `mod_lv` (Ministerio de Defensa de Letonia, página de noticias, `https://www.mod.gov.lv/lv/zinas`) | 26 de octubre de 2026 | 28 de octubre de 2026 | Con su entrada de siempre. Por qué se retiró: Desde el 21 de octubre de 2026 a las 16:20 UTC se cortaba en cada recogida al agotar su tope de 45 s (22 recogidas seguidas el 26 de octubre, con pausas de 6 horas entre medias). No es lentitud ni un cambio de dirección: mod.gov.lv no acepta la conexión en el puerto 443 desde la dirección del servidor (centro de datos de Hetzner), y el nombre resuelve a la misma dirección de siempre. Se ha visto cargar con normalidad desde alguna red de fuera de Hetzner y de Letonia, así que no es un corte del sitio. Pero el 27 de octubre de 2026, de 00:00 a 00:30 UTC, tampoco aceptó la conexión en el 443 (tiempo agotado, sin respuesta) desde el lector delegado de Vercel (Estocolmo), desde un runner de GitHub Actions (Azure, Estados Unidos) ni desde una conexión doméstica en España; solo el puerto 80 respondió, con una redirección al 443. Por eso no se puede delegar con los proveedores del observatorio (Hetzner, Vercel y GitHub) y sigue retirada; si su 443 vuelve a responder desde Vercel, se añade como delegada (basta con su entrada en la configuración y en la lista del lector). **Sustitutas probadas el 27 de octubre de 2026 (19:30-19:40 UTC), sin ninguna dada de alta:** las Fuerzas Armadas (`https://www.mil.lv/lv/zinas`, de donde salió la declaración de EODI-2026-00140) resuelven a la misma dirección que mod.gov.lv y tampoco aceptan la conexión en el 443 (tiempo agotado a los 25 s, también su robots.txt), así que no se puede ver si tienen canal RSS; el canal `https://www.mod.gov.lv/lv/rss.xml` (el de `configuracion/barrido_catalogo.json`), igual; `http://www.mod.gov.lv/` responde 302 al 443; y el portal del Ministerio `https://www.sargs.lv` responde 200 al momento, pero en todas sus direcciones (portada, robots.txt, `/lv/rss.xml`) con la misma página de mantenimiento («Pašreiz tiek veikti tīmekļa vietnes modernizācijas darbi»: obras de modernización de la web), sin notas ni canal. Lo mismo desde el servidor, desde un runner de GitHub Actions y desde una conexión doméstica en España; Vercel no se probó porque solo tendría sentido si GitHub respondiera. Toda la web de Defensa letona está en obras: ninguna de las cuatro sustituye a `mod_lv`, y de Letonia siguen `lgs`, `riga_airport` y la prensa letona por las búsquedas. Se reintentan mod.gov.lv, mil.lv y sargs.lv a mano una vez al mes (sin automatizar). Otros portales del Estado letón (Policía Estatal, Guardia de Fronteras, Agencia de Aviación Civil en `*.gov.lv/lv/jaunumi`) sí respondían 200 desde el servidor ese día; no se han evaluado como fuente. Desde la mañana del 28 de octubre de 2026 vuelve a responder desde el servidor: 200 en menos de 0,25 s en tres pruebas separadas al menos 10 minutos (13:09, 13:19 y 13:30 UTC; también a las 12:59 y a las 13:26), con robots.txt que deja leer `/lv/zinas` y la lista con sus notas fechadas. Publica las mismas notas que mil.lv (abajo) con otra dirección. |
| `mil_lv` (Fuerzas Armadas Nacionales de Letonia, NBS, página de noticias, `https://www.mil.lv/lv/zinas`) | — | 28 de octubre de 2026 (alta nueva) | No estaba en la recogida. Responde desde el servidor desde la mañana del 28 de octubre de 2026 (200 en menos de 0,25 s, robots.txt que deja leer `/lv/zinas`) y lista sus notas con fecha dd.mm.aaaa; tenía tres de drones o espacio aéreo del 22 y el 24 de octubre de 2026 (prueba `tests/test_mil_lv.py` con ellas). |
| `csn_sucesos` (Consejo de Seguridad Nuclear, RSS de sucesos notificados, `https://www.csn.es/sucesos-notificados/-/asset_publisher/AhgtIexAjt0q/rss`) | 25 de octubre de 2026 | 27 de octubre de 2026 | Del 23 de octubre de 2026 a las 13:21 UTC hasta el 26, csn.es respondía 403 a todas las peticiones de la recogida (también a su portada y con cualquier identificación), mientras desde otra red respondía 200 con el canal: un bloqueo de la dirección del servidor. Vuelve como fuente delegada: se lee a través del lector delegado de la web, que lo descarga con código 200. El 27 de octubre de 2026 csn.es respondía 200 también desde el servidor; la delegación evita que un bloqueo nuevo lo vuelva a dejar fuera. |

## Estados bálticos y Polonia: lo probado el 11 de noviembre de 2026

La noche del 10 al 11 de noviembre de 2026 hubo alertas aéreas en media Lituania y el
observatorio no tenía ninguna fuente lituana. Lo que se probó desde el servidor, con la
identificación del observatorio y una sola petición por dirección, y lo que queda:

| País | Organismo | Dirección probada | Resultado | Qué se hace |
|---|---|---|---|---|
| Lituania | Centro Nacional de Gestión de Crisis (NKVC) | `lrv.lt`, `lt72.lt` | 403, también su robots.txt (comprobación de Cloudflare); `nkvc.lrv.lt` no existe | No se da de alta. No se intenta saltar la comprobación |
| Lituania | Fuerzas Armadas | `www.kariuomene.lt/naujienos` | 403 (comprobación de Cloudflare) | No se da de alta |
| Lituania | Ministerio de Defensa | `kam.lt/naujienos/`, `kam.lt/feed/` | 403 (comprobación de Cloudflare) | No se da de alta |
| Lituania | Aeropuertos de Lituania | `www.ltou.lt/lt/naujienos`, `www.vilnius-airport.lt/lt/naujienos` | 403 (comprobación de Cloudflare) | No se da de alta |
| Lituania | LRT, la radiotelevisión pública | `www.lrt.lt/en/news-in-english`, `www.lrt.lt/naujienos/lietuvoje` | 200; su robots.txt deja leerlas | Alta como **medio público**, no como fuente oficial (`configuracion/medios_publicos.json`, `recogida/medios_publicos.py`): cuenta las alertas con las citas del NKVC, de las Fuerzas Armadas y de los Aeropuertos |
| Estonia | Fuerzas de Defensa (Kaitsevägi) | `mil.ee/feed/` | 200, canal RSS con 10 notas | Alta como fuente oficial `mil_ee` |
| Estonia | Ministerio de Defensa | `kaitseministeerium.ee/rss-feeds/rss.xml` | 200, canal RSS (notas de política de defensa, no de sucesos) | No se da de alta: no publica alertas |
| Polonia | Mando Operativo (DORSZ) | `www.wojsko-polskie.pl/dorsz/articles/aktualnosci-w/` | corta la conexión sin responder (dos pruebas), también su robots.txt; la portada sí responde | No se da de alta. Publica sus comunicados del espacio aéreo sobre todo en redes sociales |
| Polonia | Centro Gubernamental de Seguridad (RCB) | `www.gov.pl/web/rcb/komunikaty` | 200 | No se da de alta: sus «Alert RCB - zagrożenie z powietrza» avisan de ataques rusos contra Ucrania y de la disposición de la defensa aérea, no cuentan un dron en Polonia |

De Polonia siguen `pansa` y `port_gdansk`; de Estonia, `eans`, `tallinna_sadam` y ahora
`mil_ee`. Ninguna fuente oficial lituana se puede leer hoy: si alguna deja de pedir la
comprobación, se añade con su entrada en `configuracion/fuentes_oficiales.json`.

Las notas de las Fuerzas Armadas de Letonia (`mil_lv`) cambiaron ese día la forma de sus títulos
(«Izsludināts gaisa telpas apdraudējums…», «Atcelts Latvijas gaisa telpas apdraudējums…»): cinco
de las siete notas de la noche no se abrieron. `titulos_genericos` recoge ahora las que avisan
de una alerta (las que la anulan, «Atcelts…», no se abren: no cuentan nada nuevo del suceso y con
ellas la fuente rozaba su tope de 45 s), y sus alertas van por zonas (`alertas_por_zona`,
`proceso/alertas_zona.py`).
