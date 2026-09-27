# recogida

Recogida automática de fuentes.

| Módulo | Contenido |
| --- | --- |
| `descarga.py` | Descarga educada: pausa por sitio, navegador real, reintentos y detección de bloqueos |
| `cache.py` | Páginas en bruto comprimidas en `data/cache/`, fuera de git |
| `telegram.py` | Lectura de la vista pública web de un canal (`t.me/s/<canal>`) |
| `recorrido.py` | Recorrido hacia atrás con `?before=` y avance reanudable |
| `fuente.py` | Descripción común de una fuente de partes, lectura desde el cursor y relectura de 48 horas |
| `fuentes.py` | Fuentes de partes que se recogen |
| `fuerza_aerea.py` | Fuente: Fuerza Aérea de Ucrania (RU_UA), verificación del canal oficial |
| `parte.py` | Parser por código de los partes de la Fuerza Aérea (solo drones) |
| `mindef.py` | Fuente y parser: Ministerio de Defensa ruso (UA_RU), reivindicación de parte |
| `ejecucion.py` | Procesado de publicaciones y recuentos |
| `gdelt.py` | Noticias europeas sobre drones en los ficheros GKG 2.0 de GDELT, por franjas de 15 minutos |
| `medios_gdelt.py` | Generador de la tabla de medios europeos desde la lista de dominios de GDELT |
| `informe_gdelt.py` | Informe interno de artículos y candidatos por mes con una muestra |
| `lugares_osm.py` | Generador del nomenclátor de lugares desde OpenStreetMap |
| `auditoria.py` | Cobertura por días: días sin parte y su explicación |
| `horaria.py` | Ejecución horaria del workflow |
| `historico.py` | Histórico de una fuente de partes desde octubre de 2022 |
