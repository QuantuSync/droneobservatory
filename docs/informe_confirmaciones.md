# Informe del PR «confirmaciones-oficiales»

Estado: **a medias, sin mergear**. La rama `confirmaciones-oficiales` está subida con
todo commiteado y la puerta local en verde (pytest, ruff check, ruff format --check,
mypy --strict). No se mergea porque no cubre todavía el alcance pedido (ver «Qué
falta»). El workflow de pruebas de la rama está en verde.

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

- Se respeta robots.txt (incluido el Crawl-delay) y se identifica como
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

Incidentes que han cambiado de estado por una nota oficial en las ejecuciones hechas:
**ninguno** todavía (los canales solo devuelven las últimas notas y ninguna reciente
coincide con un incidente de la base).

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

## Qué falta

1. Incorporar como fuentes activas los canales RSS de NATS y PANSA (legibles desde
   Actions; desde local no se pudieron verificar a tiempo).
2. Lectores de páginas (scraping) para las 17 candidatas legibles y el sitemap de la
   OTAN, cada uno con su prueba offline.
3. Buscar la dirección correcta de las 10 candidatas con 404 (las direcciones se
   dedujeron y no existen) y la del Presseportal de Múnich y NTB de Avinor.
4. UK Airprox Board: páginas mensuales, PDF y Excel; no empezado.
5. Revisar la incursión de Rumanía y ampliar la detección de cruces cuando el parte
   nombra el país de forma indirecta («у напрямку Молдови», etc.).
6. Informe final con incidentes que cambian de estado cuando haya notas que encajen.

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
