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
| `historico_gdelt.py` | Histórico de noticias desde GKG en trabajos paralelos, con parciales cifrados |
| `extractor.py` | Extractor en la ejecución horaria; estimación y lote del histórico |
| `paises_osm.py` | Generador de las cajas de coordenadas de los países desde Nominatim |
| `comparacion.py` | Cobertura frente a la lista de referencia de 2025 |
| `lugares_osm.py` | Generador del nomenclátor de lugares desde OpenStreetMap |
| `auditoria.py` | Cobertura por días: días sin parte y su explicación |
| `horaria.py` | Ejecución horaria, que lanza el servidor de recogida (`servidor/`) |
| `plazo.py` | Tope de tiempo de cada paso de la ejecución horaria |
| `oficiales.py` | Fuentes oficiales que confirman incidentes (`configuracion/fuentes_oficiales.json`), con tope por fuente y pausa automática |
| `salud.py` | Aviso en el workflow de tests si la rama `estado` lleva más de dos horas sin actualizarse |
| `historico.py` | Histórico de una fuente de partes desde octubre de 2022 |

## Fuentes oficiales: una fuente caída no frena a las demás

`oficiales.py` lee en cada ejecución horaria las fuentes de
`configuracion/fuentes_oficiales.json` (canales RSS y páginas de noticias de autoridades).

- **Tope de todas**: 300 s (`TOPE_S`). Leer las 32 fuentes y enlazar sus notas tarda de 170 a
  190 s. Si se agota, las fuentes que faltan quedan sin leer, la ejecución termina con aviso
  (código 2) y la siguiente las lee: las notas se leen enteras cada vez.
- **Tope de cada fuente**: 45 s (`TOPE_FUENTE_S`) dentro del de todas; las más lentas tardan
  18 s. Una fuente que lo agota (o que falla al descargarse) se corta y se pasa a la siguiente.
  El registro lleva una línea por fuente fallida con su id y el motivo:
  `oficiales: fuente <id> falló: <motivo>`. Una petición tampoco pasa del tope.
- **Pausa automática**: una fuente que falla en 3 ejecuciones seguidas se salta durante 6 horas
  y después se vuelve a probar; si falla otra vez, otras 6 horas. Cuando responde, sale de la
  pausa y empieza de cero. El estado se guarda entre ejecuciones en la base, en el cursor
  `oficiales_pausas`, como el de los demás pasos.
- **Una fuente en pausa no es un fallo**: no cuenta como sin leer ni como aviso de la ejecución.
  Sale en el registro (`oficiales: fuente <id> en pausa hasta …`) y en el resumen diario privado.
- **Aviso al responsable**: solo si una fuente lleva 7 días seguidos en pausa, una vez por
  fuente, por el canal privado del resumen diario. Nunca desde un ensayo.

Una fuente que falla de forma duradera se arregla en `configuracion/fuentes_oficiales.json`
(dirección nueva o canal cambiado) o se quita de allí.
