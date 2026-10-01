# Fuentes oficiales de detalle: informe de cierre

European Observatory of Drone Incidents, 1 de octubre de 2026. Cambios: PR #35 (fuentes,
extracción, cruce, esquema y exportación), PR #36 (la orden de recogida encuentra los lectores
de todos los módulos) y PR #42 (una fecha sin día escrito en su frase no es un día; retira el
alta que dependía de eso). En AEGIS, PR #43 (importador, vocabulario y documentación).

## 1. Resultado

Las cifras salen de una exportación semanal generada en local con la base del servidor
después de incorporar todo el histórico (versión 2026.10.01, sin publicar), comparada con la
exportación de la misma fecha anterior a estos cambios.

### Nivel de detalle

| Nivel | Antes | Después |
| --- | ---: | ---: |
| A | 0 (0,0 %) | 0 (0,0 %) |
| B | 0 (0,0 %) | 3 (0,8 %) |
| C | 141 (37,5 %) | 143 (37,5 %) |
| D | 235 (62,5 %) | 235 (61,7 %) |
| Activos | 376 | 381 |

Los tres incidentes que pasan a B son Copenhague (EODI-2025-00154), Aalborg (EODI-2025-00238)
y Køge (EODI-2025-00267): las notas de la policía danesa dan hora, punto y radio y la
autoridad confirma el estado directamente. Ninguno llega a A: A exige un dato del
comportamiento del dron medido o de origen oficial (trayectoria, altura o velocidad) y
ninguna fuente oficial accesible lo da para un incidente del observatorio. Los C nuevos son las dos altas de respuestas parlamentarias. De
los 5 activos más, 2 son esas altas y 3 vienen de la recogida normal de noticias del día.

### Incidentes enriquecidos y creados

| Incidente | Qué aporta la fuente oficial |
| --- | --- |
| EODI-2025-00154 Copenhague | Policía Nacional y cierre de la investigación de la policía de Copenhague (no se pudo demostrar que fueran drones): presencia y estado según la autoridad, hora, punto y radio |
| EODI-2025-00238 Aalborg | Policía de Jutlandia del Norte y Policía Nacional: hora al minuto, punto, radio, patrulla como medida |
| EODI-2025-00267 Køge | Policía de Zelanda Central y del Oeste: hora, punto y radio |
| EODI-2024-00003 Vught (nuevo) | Respuesta de la Tweede Kamer (2025D05422): día, lugar, centro penitenciario, detección visual |
| EODI-2026-00268 RAF Akrotiri (nuevo) | Respuestas escritas del Parlamento británico 117491, 117492 y 117499: día y base |

Un tercer alta (Ramstein, EODI-2024-00002) se retiró sin borrarse: su fecha salía de «aus dem
Jahr 2024», que no da un día (PR #42). El suceso queda como no válido con su motivo.

Cruce de los 175 sucesos citados en documentos: 108 sin incidente que encaje y sin poder darse
de alta (informes, cierres y sentencias no dan de alta), 44 sin fecha, 12 sin lugar, 7 con un
incidente existente, 2 nuevos, 1 no válido y 1 con varios candidatos (se deja sin enlazar).

### Registros guardados

| Registro | Número | Detalle |
| --- | ---: | --- |
| Encuentros con aeronave (UK Airprox Board) | 967 | Drone 737, Unknown 197, Model Aircraft 33; 0 enlazados con un incidente |
| Estadísticas oficiales | 202 | Tabla mensual de la UKAB 160, publicaciones 33, Parlamento británico 4, Bundestag 2, AAIB 2, policía danesa 1 |
| Documentos oficiales leídos | 578 | Tabla siguiente |

| Fuente | Con datos | Sin datos | Sin drones | Pendiente |
| --- | ---: | ---: | ---: | ---: |
| AAIB | 84 | 7 | 0 | 0 |
| Bundestag (DIP) | 3 | 77 | 46 | 4 |
| Havarikommissionen | 3 | 0 | 0 | 0 |
| NSIA | 2 | 0 | 1 | 0 |
| Onderzoeksraad voor Veiligheid | 16 | 2 | 1 | 0 |
| PKBWL | 8 | 1 | 0 | 0 |
| Policía danesa | 12 | 7 | 0 | 0 |
| Publicaciones estadísticas | 18 | 4 | 0 | 0 |
| rechtspraak.nl | 2 | 3 | 0 | 0 |
| Tweede Kamer | 5 | 20 | 0 | 0 |
| Parlamento británico | 17 | 154 | 80 | 0 |
| UKAB (tabla mensual) | 1 | 0 | 0 | 0 |

«Sin datos» es un documento que habla de drones sin dar ningún dato de un suceso o una cifra
que pase la validación; «pendiente», los últimos que esperan a la siguiente recogida horaria.
Domsdatabasen y las webs con JavaScript se leen sin que hasta ahora hayan dado un documento
nuevo de drones.

Ningún encuentro de Airprox encaja con un incidente británico: la prensa sitúa los incidentes
el día en que se publica la noticia, y los informes de la UKAB llegan meses después con la
fecha real del encuentro. Quedan como registros propios, contados en `frecuencias.json`.

### Gasto del extractor

| Partida | Peticiones | USD |
| --- | ---: | ---: |
| Histórico por lotes (modo `detalle`, límite 3 USD) | 431 | 1,0514 |
| Documentos nuevos en la recogida horaria (límite diario) | 14 | 0,0538 |
| Pruebas en local | | 0,061 |
| **Total** | | **1,17** |

### Consumo en el servidor

| Medida | Valor |
| --- | --- |
| Recogida de cada 3 horas | 4 min 46 s, 11,5 s de CPU, 378 MB de pico, 15 fuentes leídas, ninguna fallida |
| Histórico completo | 51 min la primera vez; 1 h 26 min al repetirlo entero; 736 MB de pico |
| Lote del histórico | 817 MB de pico |
| Página con navegador | 2 a 6 s y unos 165 MB por página |
| Disco | 14 MB de datos (`datos/detalle`), 656 MB del navegador; el disco está al 13 % |
| Memoria del servidor | 3,8 GB; las recogidas no coinciden (minuto 52 frente al 17 y el 40) |

## 2. Fuentes: acceso, condiciones y licencia

Verificado el 1 de octubre de 2026. Todas se piden con la identificación «EODI-bot/1.0
(+https://droneobservatory.eu)», respetando robots.txt, con pausas de 3 s por sitio y
comprobando que lo descargado es contenido real (firma del PDF o del Excel, JSON que se lee,
marcas de la página). Tabla de fuentes en
[`configuracion/fuentes_detalle.json`](../configuracion/fuentes_detalle.json).

| Fuente | Acceso | Condiciones y licencia | Histórico | Fiabilidad |
| --- | --- | --- | --- | --- |
| UK Airprox Board | Excel histórico de drones y objetos («UA and Other Airprox Count»), página de cada año con catálogo en Excel e informes en PDF; todo por código | Sin robots.txt. **No es Open Government Licence**: la página de copyright dice que los derechos son de la CAA y la MAA a través de la UKAB y permite el uso para seguridad aérea, investigación, uso personal o educativo, **no comercial sin acuerdo previo con la UKAB**, citando a la UKAB | 2010 a hoy | A2 |
| Bundestag (DIP) | API de DIP con la clave pública que publica el Bundestag en su ayuda; se lee de su API de contenidos en cada ejecución y no se guarda | Condiciones de DIP (27-02-2023): uso libre citando «Deutscher Bundestag/Bundesrat – DIP» y el número del documento | Desde 2024 | A1 |
| Tweede Kamer | OData del Gegevensmagazijn, sin clave; PDF de cada respuesta | CC0 1.0 | Desde 2024 | A1 |
| Parlamento británico | API de Written Questions, sin clave | Open Parliament Licence v3.0 | Desde 2024 | A1 |
| AAIB (Reino Unido) | API de búsqueda y de contenido de GOV.UK (categoría «unmanned aircraft systems») y PDF | Open Government Licence v3.0 | Completo (95) | A1 |
| Havarikommissionen | sitemap y páginas de cada caso | Reproducción con cita de la fuente | Completo | A1 |
| Onderzoeksraad voor Veiligheid | búsqueda del sitio | robots.txt lo permite; su señal de contenido prohíbe usarlo para entrenar modelos (aquí solo se leen pasajes y se cita con enlace) | Completo | A1 |
| NSIA (Noruega) | lista paginada | Pública, con cita | Completo | A1 |
| PKBWL (Polonia) | API JSON pública del registro | Pública, con cita | Completo | A1 |
| Policía danesa (politi.dk) | listas de noticias por distrito | Sin robots.txt; notas públicas citadas con enlace | Desde 2024 | A1 |
| rechtspraak.nl | datos abiertos (resúmenes) | CC0; máximo 10 peticiones por segundo (aquí una cada 3 s) | Desde 2024 | A1 |
| Domsdatabasen | API JSON pública | Sentencias públicas citadas con enlace | Completo | A1 |
| Publicaciones estadísticas | 22 publicaciones de DFS, BAZL, CAA letona, ULC, ANSV, Traficom, ILT, CAA británica, Transpordiamet, Naviair, IAA y dos respuestas parlamentarias antiguas (AT, FR) ([`configuracion/publicaciones_oficiales.json`](../configuracion/publicaciones_oficiales.json)) | Públicas de cada organismo; robots.txt comprobado en cada una | Lo que publican | A2 |
| Webs con JavaScript | forsvaret_dk, lvnl y skyguide con navegador sin interfaz; lfv, enav, eans y enaire con el HTML | robots.txt de cada sitio | Lo que muestra la portada | A1 |

### Descartadas

| Fuente | Motivo |
| --- | --- |
| Folketing | La API (oda.ft.dk) da metadatos, pero los textos de las respuestas están en www.ft.dk tras una comprobación anti-robots de Cloudflare (403), también robots.txt y la página de condiciones |
| BFU (Alemania) | robots.txt prohíbe todos los formularios de búsqueda |
| CIAIAC (España) | Responde 403 («Página web bloqueada»), también a robots.txt |
| Organismo lituano | Comprobación de Cloudflare |
| BEA (Francia) | El uso gratuito es solo no comercial; además, ningún informe de drones desde 2024 |
| SHK (Suecia), Letonia, Estonia | Accesibles, sin informes de drones |
| UK Find Case Law | Su licencia excluye el análisis computacional sin una licencia aparte |
| Tribunales alemanes, Lovdata | robots.txt, JavaScript o captcha |
| Judilibre (Francia) | Exige registro y una clave |
| CENDOJ (España) | Solo uso personal; prohíbe la descarga masiva |
| Tribunales suecos | Sin búsqueda de texto |
| Policías de Múnich y Oslo | robots.txt |
| DFS (estadísticas por aeropuerto) | Solo en gráficos de los informes de movilidad (2019-2023), sin texto que leer; los totales nacionales sí entran |
| BAZL ASR 2025, skeyes | La página no dice cuándo se publicó: no se inventa la fecha |
| EASA, EUROCONTROL | Cifras de ámbito europeo sin país |
| Transportstyrelsen, Luftfartstilsynet | Cifra solo en una imagen, o solo una proporción |

## 3. Cómo funciona

- **Recogida, sin tocar la base.** `eodi-detalle.timer` cada 3 horas (minuto 52) con su propio
  cerrojo descarga lo nuevo a `datos/detalle/` en el servidor. El histórico se lanza una vez.
- **Incorporación, en la recogida horaria.** Guarda encuentros, documentos y estadísticas,
  extrae lo de los últimos 30 días con el límite diario (después del extractor de noticias) y
  cruza todo con los incidentes. Un fallo deja aviso en sus fuentes de `estado.json` y no
  cambia el resultado de la recogida.
- **Por código** (método `parser`): todos los campos de la UKAB, la tabla mensual de la UKAB.
  **Con el extractor** (método `extractor`): solo los párrafos y tablas localizados por
  palabras de dron en todos los idiomas, con el siguiente; nunca el documento entero. Salida
  obligada por esquema ([`modelo/ficha_oficial.py`](../modelo/ficha_oficial.py)) con frase y
  confianza por campo; validación por código
  ([`proceso/validacion_oficial.py`](../proceso/validacion_oficial.py)): frase literal en el
  texto, confianza de 0,5 o más, la cifra escrita en su frase, fechas no posteriores al
  documento, topes de altura y velocidad.
- **Cruce.** Un encuentro o un suceso citado coincide con un incidente por la regla de fusión
  (mismo sitio y misma ventana). Uno solo: se enlaza y le aporta sus datos con una fuente
  oficial nueva y el incidente pasa a confirmado. Ninguno: un suceso de una respuesta
  parlamentaria con fecha y lugar entra como incidente nuevo por el flujo normal (misma
  validación, ubicación y construcción, versión `oficial/1`); los informes, cierres y
  sentencias no dan de alta; los encuentros de Airprox tampoco.
- **Visibilidad.** Lo público del incidente solo cambia en estado, presencia confirmada y
  fuentes (enlace y frase breve). El detalle va a campos internos: `detalle_oficial` (hora,
  punto y radio, número de drones y medidas según la autoridad), `drones.altura_m`,
  `drones.velocidad_ms`, `respuesta.deteccion`, `respuesta.resultado_contramedidas` y
  `encuentros`. La proyección pública ya no deja un objeto vacío si solo traía campos internos.
- **Presencia.** Una autoridad que en su propio documento dice que no se pudo demostrar que
  fueran drones (el cierre de la investigación de Copenhague) manda sobre la declaración que
  cita un medio; la regla horaria de declaraciones deja en paz esos incidentes.
- **Idempotencia.** Las aportaciones viven en sus registros y se vuelven a aplicar al rehacer
  un incidente desde su ficha y en cada recogida horaria; aplicadas, no cambian nada.
- **Nivel de detalle.** B cuenta también la hora y el radio de `detalle_oficial` y la
  confirmación de una autoridad leída directamente que respalda el estado.
- **Esquema 1.3.0** (hoy 1.5.0 con otros cambios): registros `encuentro`,
  `estadistica_oficial` y `documento_oficial`, con historial y sin borrado; campos internos nuevos de incidente y fuente. **Exportación 1.1.0**:
  `encuentros.jsonl`, `estadisticas_oficiales.jsonl`, `documentos_oficiales.jsonl`;
  `frecuencias.json` pone cada cifra oficial junto a los incidentes del observatorio en el
  mismo país, categoría y periodo (`referencias_oficiales`), sin corregir nada. Vocabulario
  1.1.0. AEGIS (PR #43): resumen del importador, vocabulario, documentación y condición de uso
  de la UKAB.

## 4. Completitud por campo y origen

Porcentaje sobre los incidentes activos de cada exportación. Las columnas son el origen del
dato (`procedencia`). `condiciones` y `trafico_aereo` son campos nuevos de otro cambio y no
están en la exportación de antes.

### Antes (376 activos)

| Campo | Lleno | medido | oficial | oficial_citado | parte | prensa | Sin respaldo |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `atribucion` | 0.8 % (3) | 0 | 0 | 3 | 0 | 0 | 0 |
| `consecuencias.cierre.minutos` | 9.0 % (34) | 0 | 0 | 0 | 0 | 34 | 0 |
| `consecuencias.danos` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `consecuencias.fallecidos` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `consecuencias.heridos` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `consecuencias.vuelos_cancelados` | 1.3 % (5) | 0 | 0 | 0 | 0 | 5 | 0 |
| `consecuencias.vuelos_desviados` | 7.7 % (29) | 0 | 0 | 0 | 0 | 29 | 0 |
| `consecuencias.vuelos_retrasados` | 5.1 % (19) | 0 | 0 | 0 | 0 | 19 | 0 |
| `detalle_oficial.inicio` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `detalle_oficial.medidas` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `detalle_oficial.numero` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `detalle_oficial.punto` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `detalle_oficial.radio_km` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `drones.altura_m` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `drones.clase` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `drones.luces` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `drones.modelo` | 6.6 % (25) | 0 | 0 | 0 | 0 | 25 | 0 |
| `drones.numero` | 75.3 % (283) | 0 | 1 | 0 | 0 | 282 | 0 |
| `drones.patron` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `drones.trayectoria` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `drones.velocidad_ms` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `estado` | 100.0 % (376) | 0 | 1 | 144 | 0 | 231 | 0 |
| `foco_termico` | 12.2 % (46) | 46 | 0 | 0 | 0 | 0 | 0 |
| `lugar.geocodificacion` | 66.5 % (250) | 0 | 0 | 0 | 0 | 250 | 0 |
| `lugar.localidad` | 18.4 % (69) | 0 | 0 | 0 | 0 | 69 | 0 |
| `lugar.nivel` | 100.0 % (376) | 0 | 1 | 0 | 0 | 375 | 0 |
| `lugar.nuts2` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `lugar.pais` | 100.0 % (376) | 0 | 1 | 0 | 0 | 375 | 0 |
| `lugar.punto` | 66.5 % (250) | 0 | 0 | 0 | 0 | 250 | 0 |
| `lugar.radio_km` | 66.5 % (250) | 0 | 0 | 0 | 0 | 250 | 0 |
| `lugar.region` | 71.0 % (267) | 0 | 0 | 0 | 0 | 267 | 0 |
| `lugar.suceso` | 92.3 % (347) | 0 | 0 | 0 | 0 | 347 | 0 |
| `objetivo.categoria` | 67.8 % (255) | 0 | 0 | 0 | 0 | 255 | 0 |
| `objetivo.nombre` | 67.3 % (253) | 0 | 0 | 0 | 0 | 253 | 0 |
| `objetivo.oaci` | 41.5 % (156) | 0 | 0 | 0 | 0 | 156 | 0 |
| `objetivo.uso` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `origen_demostrado_por` | 23.9 % (90) | 0 | 1 | 52 | 0 | 37 | 0 |
| `presencia_dron` | 100.0 % (376) | 0 | 1 | 45 | 0 | 330 | 0 |
| `pruebas.dron_estatal` | 60.1 % (226) | 0 | 1 | 0 | 0 | 225 | 0 |
| `pruebas.entrada_exterior` | 38.8 % (146) | 0 | 1 | 0 | 0 | 145 | 0 |
| `pruebas.evidencia` | 27.7 % (104) | 0 | 1 | 0 | 0 | 103 | 0 |
| `respuesta.deteccion` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `respuesta.medidas` | 34.3 % (129) | 0 | 0 | 0 | 0 | 129 | 0 |
| `respuesta.resultado_contramedidas` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `tiempo.duracion_min` | 11.4 % (43) | 0 | 0 | 0 | 0 | 43 | 0 |
| `tiempo.fin` | 11.7 % (44) | 0 | 1 | 0 | 0 | 43 | 0 |
| `tiempo.inicio` | 100.0 % (376) | 0 | 1 | 0 | 0 | 375 | 0 |
| `tipo` | 100.0 % (376) | 0 | 1 | 6 | 0 | 369 | 0 |


### Después (381 activos)

| Campo | Lleno | medido | oficial | oficial_citado | parte | prensa | Sin respaldo |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `atribucion` | 0.8 % (3) | 0 | 0 | 3 | 0 | 0 | 0 |
| `condiciones` | 33.1 % (126) | 126 | 0 | 0 | 0 | 0 | 0 |
| `consecuencias.cierre.minutos` | 8.9 % (34) | 0 | 0 | 0 | 0 | 34 | 0 |
| `consecuencias.danos` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `consecuencias.fallecidos` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `consecuencias.heridos` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `consecuencias.vuelos_cancelados` | 1.3 % (5) | 0 | 0 | 0 | 0 | 5 | 0 |
| `consecuencias.vuelos_desviados` | 7.6 % (29) | 0 | 0 | 0 | 0 | 29 | 0 |
| `consecuencias.vuelos_retrasados` | 5.0 % (19) | 0 | 0 | 0 | 0 | 19 | 0 |
| `detalle_oficial.inicio` | 1.3 % (5) | 0 | 5 | 0 | 0 | 0 | 0 |
| `detalle_oficial.medidas` | 0.3 % (1) | 0 | 1 | 0 | 0 | 0 | 0 |
| `detalle_oficial.numero` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `detalle_oficial.punto` | 1.0 % (4) | 0 | 4 | 0 | 0 | 0 | 0 |
| `detalle_oficial.radio_km` | 1.0 % (4) | 0 | 4 | 0 | 0 | 0 | 0 |
| `drones.altura_m` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `drones.clase` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `drones.luces` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `drones.modelo` | 6.6 % (25) | 0 | 0 | 0 | 0 | 25 | 0 |
| `drones.numero` | 75.1 % (286) | 0 | 1 | 0 | 0 | 285 | 0 |
| `drones.patron` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `drones.trayectoria` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `drones.velocidad_ms` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `estado` | 100.0 % (381) | 0 | 6 | 144 | 0 | 231 | 0 |
| `foco_termico` | 12.3 % (47) | 47 | 0 | 0 | 0 | 0 | 0 |
| `lugar.geocodificacion` | 65.9 % (251) | 0 | 1 | 0 | 0 | 250 | 0 |
| `lugar.localidad` | 18.4 % (70) | 0 | 1 | 0 | 0 | 69 | 0 |
| `lugar.nivel` | 100.0 % (381) | 0 | 3 | 0 | 0 | 378 | 0 |
| `lugar.nuts2` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `lugar.pais` | 100.0 % (381) | 0 | 3 | 0 | 0 | 378 | 0 |
| `lugar.punto` | 65.9 % (251) | 0 | 1 | 0 | 0 | 250 | 0 |
| `lugar.radio_km` | 65.9 % (251) | 0 | 1 | 0 | 0 | 250 | 0 |
| `lugar.region` | 70.3 % (268) | 0 | 0 | 0 | 0 | 268 | 0 |
| `lugar.suceso` | 91.9 % (350) | 0 | 2 | 0 | 0 | 348 | 0 |
| `objetivo.categoria` | 67.5 % (257) | 0 | 2 | 0 | 0 | 255 | 0 |
| `objetivo.nombre` | 66.9 % (255) | 0 | 2 | 0 | 0 | 253 | 0 |
| `objetivo.oaci` | 40.9 % (156) | 0 | 0 | 0 | 0 | 156 | 0 |
| `objetivo.uso` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `origen_demostrado_por` | 23.9 % (91) | 0 | 1 | 53 | 0 | 37 | 0 |
| `presencia_dron` | 100.0 % (381) | 0 | 3 | 46 | 0 | 332 | 0 |
| `pruebas.dron_estatal` | 60.4 % (230) | 0 | 2 | 0 | 0 | 228 | 0 |
| `pruebas.entrada_exterior` | 39.1 % (149) | 0 | 2 | 0 | 0 | 147 | 0 |
| `pruebas.evidencia` | 27.6 % (105) | 0 | 1 | 0 | 0 | 104 | 0 |
| `respuesta.deteccion` | 0.3 % (1) | 0 | 1 | 0 | 0 | 0 | 0 |
| `respuesta.medidas` | 33.9 % (129) | 0 | 0 | 0 | 0 | 129 | 0 |
| `respuesta.resultado_contramedidas` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `tiempo.duracion_min` | 11.3 % (43) | 0 | 0 | 0 | 0 | 43 | 0 |
| `tiempo.fin` | 11.5 % (44) | 0 | 1 | 0 | 0 | 43 | 0 |
| `tiempo.inicio` | 100.0 % (381) | 0 | 3 | 0 | 0 | 378 | 0 |
| `tipo` | 100.0 % (381) | 0 | 3 | 7 | 0 | 371 | 0 |
| `trafico_aereo` | 24.9 % (95) | 95 | 0 | 0 | 0 | 0 | 0 |

Lo que cambia por las fuentes de detalle: `estado` con origen oficial pasa de 1 a 6;
`detalle_oficial.inicio` de 0 a 5, `punto` y `radio_km` de 0 a 4 y `medidas` de 0 a 1;
`respuesta.deteccion` de 0 a 1; `presencia_dron` oficial de 1 a 3; las dos altas aportan lugar,
objetivo, pruebas, tiempo y tipo con origen oficial. Los campos vacíos lo están porque ninguna
fuente oficial los da: nada se ha rellenado.

## 5. Limitaciones y pendiente

- **Licencia de la UKAB**: no es Open Government Licence. Uso no comercial sin acuerdo previo
  con la UKAB, citándola. Está en la ficha de la fuente, en la exportación y en la
  documentación de AEGIS; un uso comercial necesita ese acuerdo.
- **Folketing**: descartado por la comprobación anti-robots de su web. Lo que dicen las
  respuestas danesas llega por la policía.
- **Airprox frente a la prensa**: sin enlaces mientras los incidentes de prensa tengan la fecha
  de la noticia.
- **Sucesos sin fecha o sin lugar** (56): el documento no los da con día y sitio; quedan
  guardados y declarados, no se completan.
- **Nivel A**: requiere datos del dron que solo dan informes de investigación de sucesos que el
  observatorio aún no tiene como incidentes.
