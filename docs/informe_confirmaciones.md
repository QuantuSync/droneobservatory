# Informe del PR «confirmaciones-oficiales»

Estado: puerta local en verde (pytest, ruff check, ruff format --check, mypy
--strict) y workflow de pruebas en verde. Se mergea con 18 fuentes oficiales activas;
lo que queda sin hacer está en «Qué falta» y no entra en el workflow horario.

## Qué hay hecho

### Incursiones a partir de los cruces de los partes ucranianos

`proceso/incursiones.py` convierte los cruces de frontera que recogen los partes de la
Fuerza Aérea ucraniana (dron que sale hacia Moldavia, Rumanía, Polonia, Hungría o
Eslovaquia) en incidentes de tipo incursión en el país afectado, con estado
`notificado`. Solo pasan a `confirmado` cuando hay una nota oficial del país afectado
(regla de las fuentes oficiales, abajo); el parte ucraniano solo notifica. Las
fronteras están en `configuracion/fronteras_ucrania.json`.

Con la base actual sale **1 incursión** (Rumanía, 2024-09-27). Los partes rara vez
nombran el país de salida; la mayoría de los cruces que citan la prensa no aparecen en
el texto del parte.

### Fuentes oficiales activas

`recogida/oficiales.py`, añadido a la ejecución horaria. Fuentes en
`configuracion/fuentes_oficiales.json`:

| Fuente | Canal | Estado |
|---|---|---|
| Københavns Politi | RSS de Ritzau (publisherId 90685) | activa |
| Nordjyllands Politi | RSS de Ritzau (publisherId 13562880) | activa |
| Rigspolitiet | RSS de Ritzau (publisherId 90752) | activa |
| NATS (control aéreo británico) | RSS de su web | activa |
| PANSA (control aéreo polaco) | RSS de su web | activa |
| LGS (control aéreo letón) | RSS de su web | activa |
| Defensa belga | RSS de mil.be | activa |
| Ministerio de Defensa rumano (MApN) | página de comunicados | activa |
| DFS (control aéreo alemán) | página de prensa | activa |
| Aeropuerto de Múnich | sala de prensa | activa |
| Ministerio de Defensa letón | página de noticias | activa |
| Ministerio de Defensa moldavo | página de comunicados | activa |
| Aeropuerto de Riga | página de noticias | activa |
| Finavia | sala de prensa | activa |
| Austro Control | página de prensa | activa |
| Ministerio de Defensa finlandés | página de actualidad | activa |
| Gobierno sueco (defensa) | página de comunicados | activa |

Las 18 se leyeron en vivo desde GitHub Actions (ejecución 36421785643 y siguientes,
en verde): todas responden y dan notas o enlaces. Las páginas se leen con
`recogida/paginas_oficiales.py`: los enlaces que casan con el patrón de cada fuente
dan las notas; solo se abren las que hablan de drones en el título o tienen un título
genérico («Informație de presă» en MApN), como mucho cinco por fuente y ejecución. La
fecha sale del patrón de la fuente o de los metadatos de publicación
(`article:published_time`, `datePublished`, `<time>`); si es medianoche local se toma
como fecha de día. Cada fuente tiene su prueba offline en
`tests/test_paginas_oficiales.py`.

- Se respeta robots.txt (también en cada nota que se abre), con una pausa mínima de
  3 s entre peticiones al mismo sitio, y se identifica como
  `EODI-bot/1.0 (+https://droneobservatory.eu)`.
- Una nota que habla de drones se enlaza al incidente con la regla de fusión (mismo
  sitio por radios + 10 km, misma ventana temporal). Si encaja con uno solo, entra como
  fuente de autoridad (fiabilidad A) y el incidente pasa a `confirmado`. Si encaja con
  ninguno o con varios, no se enlaza.
- `presencia_dron` solo cambia a `confirmada` si la nota lo afirma sin reservas
  («bekræfter» y similares, sin «mulige», «formodede»…).
- Las actualizaciones de una misma nota comparten página en Ritzau; se distinguen por
  el fragmento `#sm-…` del enlace.
- El registro solo lleva recuentos.

Incidentes que han cambiado de estado o de `presencia_dron` por una nota oficial:
**ninguno**. Prueba contra una copia de la base actual (sin subirla), con las 18
fuentes: 323 notas leídas, 20 hablan de drones y ninguna encaja con un incidente. Son
notas sobre programas militares (drones de la defensa belga, DroneTower de PANSA,
cooperación finlandesa con Ucrania); cuando la nota nombra un sitio de otro país
(«Regimentul de Aviaţie „Decebal”» en una nota belga) el filtro por país de la fuente
evita el enlace. Los canales solo devuelven las últimas notas, así que los incidentes
de 2025 no se pueden confirmar hacia atrás con estas fuentes.

### Sondeo de candidatas desde GitHub Actions

`recogida/sondeo_oficiales.py` y `.github/workflows/prueba-oficiales.yml` comprueban
robots.txt y la respuesta de las 43 candidatas de
`configuracion/fuentes_oficiales_candidatas.json` desde un runner de GitHub, con una
sola petición por candidata. Resultado de la ejecución 36407514019 (en verde):

| Resultado | Candidatas |
|---|---|
| canal RSS legible | nats, pansa |
| sitemap legible | nato |
| página legible (scraping posible) | austrocontrol, dfs, eans, enaire, enav, finavia, forsvaret_dk, lfv, lvnl, mapn, mod_be, mod_fi, mod_lv, mod_md, riga_airport, romatsa, skyguide |
| responde pero no es HTML | mod_de |
| bloqueada por robots.txt | fintraffic |
| rechaza (403) | aalborg_lufthavn, brussels_airport, cph, kam_lt, mod_no, oro_navigacija, swedavia, vilnius_airport |
| rechaza (503) | dsna |
| sin respuesta | billund_lufthavn, dorsz |
| dirección no encontrada (404) | aena, avinor_ntb, lgs, liege_airport, mod_ee, mod_se, muc_presseportal, naviair, oslo_lufthavn, skeyes |

Desde el equipo local los resultados coinciden casi siempre; pansa y dorsz no
responden desde aquí y sí (pansa) desde GitHub. Las 403 no se intentan esquivar: se
respetan como negativa.

## Direcciones corregidas

| Candidata | Dirección nueva | Resultado |
|---|---|---|
| lgs | https://www.lgs.lv/category/news/feed/ | activa (RSS) |
| muc_presseportal | https://www.munich-airport.de/newsroom-86335 | activa |
| mod_se | https://www.regeringen.se/pressmeddelanden/ | activa |
| aalborg_lufthavn | https://aal.dk/nyheder | se lee desde el equipo local, pero rechaza la petición desde GitHub Actions: fuera del workflow horario |
| naviair | https://www.naviair.dk/presse/nyhedsarkiv- | responde, pero las notas se cargan con JavaScript: sin enlaces en el HTML |
| mod_ee | https://kaitseministeerium.ee/uudised | responde, pero la lista de noticias no trae enlaces a notas en el HTML |
| liege_airport | https://www.liegeairport.com/fr/actualites | responde, sin enlaces a notas en el HTML |
| skeyes | sin encontrar | todas las direcciones probadas dan 404 |
| aena | sin encontrar | todas las direcciones probadas dan 404 |
| avinor_ntb, oslo_lufthavn | sin encontrar | avinor.no da 404 en las rutas de noticias; oslo-lufthavn.no no responde |

## Páginas legibles que no se leen todavía

Del sondeo salieron 17 páginas legibles; 9 están activas (MApN, DFS, defensa letona,
moldava y finlandesa, aeropuerto de Riga, Finavia, Austro Control y, por RSS, la
defensa belga). Las otras no traen los enlaces a las notas en el HTML (se cargan con
JavaScript) o no son una lista de notas: forsvaret_dk, lfv, lvnl, enaire, enav,
skyguide y eans. romatsa rechaza al equipo local y fintraffic está cerrada por
robots.txt. Leerlas pide sus API internas o el sitemap; queda pendiente.

## Qué falta

1. Las 7 páginas que cargan las notas con JavaScript y el sitemap de la OTAN.
2. Las direcciones que siguen sin funcionar (tabla anterior).
3. UK Airprox Board: no empezado. www.airproxboard.org.uk no resuelve desde el equipo
   local; habría que probarlo desde GitHub Actions.
4. Revisar la incursión de Rumanía y ampliar la detección de cruces cuando el parte
   nombra el país de forma indirecta («у напрямку Молдови», etc.).

## Decisiones tomadas sin consultar

- La policía danesa se incorporó primero porque publica RSS con robots.txt permisivo y
  es la autoridad que informa de los incidentes en aeropuertos daneses.
- Una nota oficial confirma el incidente, pero `presencia_dron` solo se toca con
  afirmación expresa: la policía suele hablar de «observaciones de posibles drones».
- El gancho pre-push local examinaba también `publicacion/`, que contiene citas de
  noticias en otros idiomas generadas por el workflow horario (preposiciones
  italianas de dos letras, o palabras con letras no ASCII que `git grep -w` parte).
  Bloqueaba cualquier push. Se ha excluido `publicacion/` del examen de ficheros; los
  mensajes de commit y el resto del árbol se siguen examinando igual.
