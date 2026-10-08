# Archivo de las alertas aéreas de Ucrania de alerts.in.ua

8 de octubre de 2026. Servicio nuevo del servidor de recogida del European Observatory of Drone
Incidents que archiva las alertas aéreas que declaran las autoridades de cada región de Ucrania,
tal como las reparte [alerts.in.ua](https://alerts.in.ua/). Solo consulta y guarda: no procesa,
no clasifica y no publica nada. La razón de hacerlo ya es que la API solo da el último mes de
histórico: cada día que pasa se pierde el día más antiguo. Servirá más adelante para reconstruir el
avance de cada oleada distrito a distrito, saber qué amenaza iba hacia el Danubio y mejorar las
rutas y el tipo de dron.

Funcionamiento y órdenes: [`servidor.md`](servidor.md), «Alertas aéreas de Ucrania de
alerts.in.ua»; qué hacer si se para: [`operacion.md`](operacion.md). Código:
[`recogida/alertas.py`](../recogida/alertas.py). PR #168.

Atribución: cada dato archivado lleva su fuente, «alerts.in.ua». En cualquier uso futuro se
presentará como «alerta declarada por las autoridades ucranianas, recogida por alerts.in.ua».

## 1. Qué da la API de verdad

Comprobado el 8 de octubre de 2026 a las 07:37 UTC desde el servidor, con el token del
observatorio, contra la documentación de <https://devs.alerts.in.ua/>.

- **Responde bien.** `/v1/alerts/active.json` y `/v1/regions/<uid>/alerts/month_ago.json`
  responden 200 con el token en la cabecera `Authorization: Bearer`. Con `If-Modified-Since` y la
  `Last-Modified` anterior responde 304 sin cuerpo cuando nada ha cambiado. Cada respuesta es
  `{"alerts": [...], "meta": {"last_updated_at", "type": "full"}, "disclaimer"}`.
- **Campos de cada alerta** (todos presentes en las 75 activas y en las 15 832 del histórico):
  `id`, `location_title` (en ucraniano), `location_title_en`, `location_type` (`oblast`, `raion`,
  `hromada`, `city`), `location_uid`, `location_oblast`, `location_oblast_uid`, `started_at`,
  `finished_at` (nulo si sigue abierta), `updated_at`, `alert_type` (`air_raid`,
  `artillery_shelling`, `urban_fights`…), `alert_level` (`yellow` o `red`), `notes` y `country`.
  Las activas traen además `location_raion` en las de municipio y `threats`.
- **El nivel viene siempre**, en las activas y en el histórico.
- **La lista de amenazas solo viene en las activas.** Cada amenaza lleva `threat_type` (vistas:
  `drones`, `unspecified_missiles`; la documentación cita además `ballistic_missiles`,
  `cruise_missiles`, `guided_aerial_bombs`, `mig31k_departure`, actividad de aviación táctica y
  estratégica), `level`, `started_at` y, casi siempre, `source_message`: el mensaje oficial del que
  sale («Дронова загроза (жовтий рівень)», «Ракетна загроза (червоний рівень)»…). A las 07:37, 69
  de las 75 activas traían amenazas (83 en total, 71 con mensaje). **El histórico no trae ninguna
  amenaza**: el campo no existe en ninguna de las 15 832 alertas. Las amenazas solo se conservan si
  se capturan en vivo.
- **El histórico guarda un solo nivel por alerta.** La noche del 4 al 5 de octubre, el distrito de
  Izmaíl figura en el histórico como una alerta «amarilla» de 22:31 a 23:58 UTC; NEPTUN registró que
  a las 22:41:51 pasó a rojo («Масована дронова загроза», ataque masivo de drones). Esa subida de
  nivel no queda en el histórico: solo en las activas de ese momento.
- **Zona horaria.** Todas las horas vienen en UTC, en ISO 8601 con milisegundos y `Z`
  (`2026-10-04T22:31:56.261Z`); `meta.last_updated_at` viene como `2026/10/08 07:36:34 +0000`. Se
  guardan tal cual y, en la tabla, repetidas como `utc` en una forma única.
- **Detalle del histórico.** El histórico de una región (oblast) trae sus distritos, municipios y
  ciudades: el de Dnipropetrovsk, 1 434 alertas de distrito, 399 de municipio y 395 de ciudad. Con
  el identificador de un distrito (101, Izmaíl) responde 404. Basta con las 27 regiones.
- **Rarezas** que se guardan tal cual: `location_oblast_uid` repite a veces el identificador de la
  propia zona (104 en el distrito de Odesa) en lugar del de la región; algunas alertas siguen
  abiertas desde hace años (Luhansk desde el 4 de abril de 2022, Crimea desde el 10 de diciembre de
  2022, Vovchansk desde el 20 de mayo de 2024) y aparecen siempre, en las activas y en el histórico.

## 2. Histórico descargado

Descarga del 8 de octubre de 2026 de 07:39:57 a 08:08:11 UTC: las 27 regiones, una consulta cada
65 s (el límite del histórico es 2 por minuto), todas con 200, 7,6 MB en crudo. Como trabajo de
sesión (`systemd-run`, 500 MB, prioridad baja), con el resultado escrito ya en el formato del
archivo; después, `python -m recogida.alertas tabla-desde-crudo` la pasó a la tabla (1,7 s, 43 MB).

- **15 832 alertas distintas.**
- **Cobertura.** El histórico trae las alertas que terminaron en los 30 días anteriores a la
  consulta o que siguen abiertas: el fin más antiguo es el 8 de septiembre de 2026 a las 08:02:29
  UTC (Shostka y Sumy). Para todas las regiones a la vez, completo desde el **8 de septiembre de
  2026 hacia las 08:08 UTC** (la última región se consultó a las 08:08:11) hasta el 8 de octubre a
  las 08:08 UTC; la captura continua sigue desde ahí. El 8 de septiembre es un día parcial; del 9
  de septiembre en adelante, días completos.
- **La noche del 4 al 5 de octubre y las siguientes están dentro** (apartado 7).
- Niveles: 9 538 amarillas y 6 294 rojas. Tipos: 15 553 aéreas, 278 de artillería, 1 de combates.
  Zonas: 13 509 distritos, 1 059 municipios, 1 051 ciudades y 213 regiones enteras (Kyiv ciudad y
  las de larga duración).

## 3. Cómo funciona la captura

`eodi-alertas.service`, siempre en marcha desde el 8 de octubre de 2026 a las 09:17:28 UTC, con el
mismo modelo que `eodi-seguimiento`:

- **Activas cada minuto**, con `If-Modified-Since`. Se guarda en crudo, comprimida al cerrarse la
  hora, cada respuesta cuyo cuerpo cambia; un 304 no guarda nada.
- **Histórico de las 27 regiones una vez al día** (también al arrancar), una región por minuto y
  con `If-Modified-Since` por región, para rellenar los huecos de la captura y traer la hora de fin
  oficial. Nunca duplica: cada alerta se compara con lo último que dio la misma vía.
- **Ritmo de consultas.** Ninguna consulta sale antes de 20 s de la anterior: como mucho 3 por minuto entre
  todas (la API admite 8 a 10, y 2 el histórico); el histórico, una por minuto. Fallo de red o 5xx:
  espera 1, 2, 4… hasta 15 minutos; 429: todo parado 5 minutos; 401 o 403: aviso a la vigilancia y
  nuevo intento cada 10 minutos.
- **Tabla de alertas que solo se amplía**: una línea por versión, con el identificador, el número
  de versión, la vía (activas o histórico), el tipo de cambio (`nueva`, `cambia`,
  `sale_de_activas`), la fuente «alerts.in.ua», las horas en UTC y la alerta tal como llegó. Cuando
  una alerta deja de estar entre las activas se anota en el minuto (su fin aproximado) y el
  histórico del día siguiente añade otra versión con el `finished_at` oficial; nada se sobrescribe.
- **Token**: en `/home/eodi/.eodi/alerts_in_ua_token` (600, del usuario `eodi`), en la cabecera; no
  aparece en el repositorio, en el diario ni en el archivo (hay una prueba que lo comprueba).
- **Arranque tras reinicio**: la unidad está habilitada (`WantedBy=multi-user.target`) y systemd
  la relanza a los 30 s si se para. Tope de memoria 300 MB (usa unos 30 MB; pico 38 MB).
- Sale y se relanza sola solo cuando cambia su propio código en el clon.

Medido en la primera hora y media (09:17 a 10:52 UTC): 10 consultas cada 10 minutos (las
activas cada minuto, más el histórico mientras duró la segunda pasada), ningún error; de cada
10 respuestas de las activas, de 4 a 7 traían cambios y se guardaron y el resto fueron 304. La
tabla pasó de 15 832 a 15 884 alertas, con 103 versiones por cambio y 45 salidas de las
activas. Memoria: pico de 50 MB. Una hora de mucha actividad ocupa unos 480 KB comprimida en
crudo (la de las 09) y la tabla, unos 11 KB por hora sin histórico.

## 4. Copias

Las mismas que el archivo de NEPTUN, sin nada nuevo que mantener: `eodi-seguimiento-archivo`
(minuto 3) comprime las horas cerradas, las anota en el índice del día y las sube cada hora al
bucket privado `droneobservatory-archivo` (`seguimiento/alertas/…` y
`seguimiento/alertas_tabla/…`, cada objeto con su SHA-256); `eodi-replica` (minuto 47) las
lleva cifradas a Helsinki (`droneobservatory-replica`, `archivo/seguimiento/alertas…age`).

- **Primera copia**: 8 de octubre a las 10:03:01 UTC, las 6 horas cerradas (07, 08 y 09, crudo
  y tabla; 1,7 MB comprimidos). **Primera réplica**: a las 10:47 UTC, 8 objetos del archivo.
- **Restauración de un día** (10:53 UTC): `seguimiento_archivo.sh restaurar-dia --dia
  2026-10-08` a una carpeta aparte bajó los 26 objetos del día (NEPTUN, Fuerza Aérea y alertas)
  comprobando cada huella, en un par de segundos; los 6 de alertas, idénticos byte a byte al
  archivo del servidor (15 976 líneas de tabla). La hora 07 de la tabla bajada de Helsinki y
  descifrada con `replica.sh restaurar`, también idéntica.

## 5. Vigilancia

`salud.json` lleva `alertas` (unidad y última respuesta correcta). Dos problemas nuevos:

- `alertas`: la API no ha dado una respuesta correcta (200, o 304 sin cambios) en 15 minutos, o la
  unidad no está en marcha. Con las activas cada minuto, son 15 consultas seguidas sin respuesta.
  Se mide la respuesta y no el cambio de los datos: con 304 la API confirma que no hay nada nuevo,
  y en horas tranquilas pueden pasar más de 15 minutos sin que cambie ninguna alerta.
- `alertas_autorizacion`: la API respondió 401 o 403 (token no válido o IP bloqueada), desde ese
  momento hasta la siguiente respuesta correcta.

Los avisa `vigia-recogida` con la incidencia «El servidor del observatorio necesita atención» y el
correo de «Run failed».

**Alarma de prueba** (8 de octubre de 2026, 09:20 UTC): la vigilancia real, con el código del clon,
compuso `salud.json` sobre una copia de los registros del servidor con `alertas.json` cambiado a
propósito (última respuesta hace 20 minutos y un 401) y lo subió al almacén; a continuación se lanzó
`vigia-recogida` a mano. El trabajo falló (correo al dueño) y abrió la incidencia #169 con las dos
frases: «El archivo de alertas de alerts.in.ua está «active» y tuvo respuesta de la API por última
vez el 2026-10-08 09:00 UTC: más de 15 minutos sin datos nuevos.» y «La API de alerts.in.ua
respondió 401 el 2026-10-08T09:20:31…: el token no vale o la IP está bloqueada.» La pasada siguiente del servidor volvió a subir el `salud.json` real y la incidencia se cerró
sola a las 10:01 UTC.
La vigilancia real de ese momento no tenía ningún problema.

## 6. Servidor desde cero

`servidor/instalar.sh` crea la unidad `eodi-alertas`, `servidor/configuracion.sh` define su
carpeta, cerrojo, token, registro y topes, y `servidor/reconstruir.sh` lleva el token desde
`%USERPROFILE%\.eodi\alerts_in_ua_token.txt` y habilita la unidad. Los datos los trae
`seguimiento_archivo.sh restaurar-todo` (el mismo paso que el archivo del seguimiento); el estado
para no repetir se rehace solo con la tabla. En el servidor actual la unidad se instaló con el
bloque de `instalar.sh` solo (sin ejecutar el script entero, que toma el cerrojo de la recogida
para poner al día el clon) en cuanto la recogida de las 09:17 dejó el código en el clon.

## 7. Comprobación de lo archivado

Sobre la tabla tras la descarga del histórico (15 832 alertas), sin construir nada encima.

### Qué parte tiene nivel y qué parte tiene amenazas

- **Nivel**: 15 832 de 15 832 (100 %).
- **Lista de amenazas**: 0 de las 15 832 del histórico; el histórico no la trae. Desde el arranque
  de la captura la traen las activas: de las 97 alertas vistas en las activas entre las 09:17 y las 10:52 UTC, 85 (88 %) traen la
lista, con drones y misiles sin especificar, y casi siempre su mensaje oficial.

### Noche del 4 al 5 de octubre: región de Odesa y el Danubio

Alertas de la región de Odesa del 4 de octubre a las 17:00 al 5 a las 06:00 UTC (hora de Ucrania =
UTC + 3), todas aéreas:

| Inicio (UTC) | Fin (UTC) | Distrito | Nivel en el histórico |
| --- | --- | --- | --- |
| 4 oct 17:40:45 | 17:59:43 | Berezivka | amarillo |
| 4 oct 17:53:34 | 18:11:07 | Podilsk | amarillo |
| **4 oct 22:31:56** | **23:58:15** | **Izmaíl** | amarillo |
| **4 oct 22:31:56** | **23:58:15** | **Bolhrad** | amarillo |
| 4 oct 22:31:56 | 23:58:15 | Bilhorod-Dnistrovskyi | amarillo |
| 4 oct 23:16:57 | 23:52:59 | Odesa | rojo |
| 5 oct 00:47:43 | 01:23:02 | Odesa | amarillo |
| 5 oct 02:22:58 | 02:38:38 | Bilhorod-Dnistrovskyi | amarillo |
| 5 oct 03:09:25 | 04:42:39 | Odesa | amarillo |

- **La región de Odesa** entró en alerta de drones esa tarde a las **17:40:45 UTC** (Berezivka,
  20:40 en Ucrania), y en la noche, la del ataque, a las **22:31:56 UTC** (01:31 en Ucrania), con
  los tres distritos del sur a la vez. No hubo alerta de la región entera: las autoridades la
  declaran por distritos.
- **Izmaíl y Bolhrad: 22:31:56 UTC** (22:31:56,261 y 22:31:56,728; 01:31 en Ucrania), las dos
  hasta las 23:58:15. El histórico no trae el tipo de amenaza; el nivel amarillo es el de drones según la
  documentación de la API.
- **Cuadra con NEPTUN.** En el archivo del seguimiento, el mensaje `alerts` de NEPTUN que llegó a
  las 22:32:39 UTC trae Izmaíl, Bolhrad y Bilhorod-Dnistrovskyi con `since` 22:31:56,08 / ,24 / ,40
  y motivo «Дронова загроза (жовтий рівень)»: la misma hora al segundo, con una diferencia de
  0,2 s, lo que apunta a la misma fuente oficial. A las 22:41:51 NEPTUN los da en rojo, «Масована
  дронова загроза» (ataque masivo de drones), cosa que el histórico de alerts.in.ua no guarda
  (apartado 1). Las otras horas de la noche también coinciden: Berezivka 17:40:45, Podilsk 17:53:34
  y Odesa 23:16:57, 00:47:43 y 03:09:25, en los dos. En las amenazas de NEPTUN de esa noche en la
  región de Odesa constan drones desde las 19:25 UTC (sin distrito), una bomba guiada sobre Odesa a
  las 23:17 y una amenaza balística sobre Chornomorsk a las 23:20 (la alerta roja del distrito de
  Odesa empieza a las 23:16:57).

### Alertas por día y por región

Alertas distintas por día de inicio (UTC) y región, del archivo tal como quedó tras la descarga. Las
filas anteriores al 7 de septiembre son alertas que siguen abiertas desde entonces; el 8 de
septiembre es parcial y el 8 de octubre llega hasta las 08:08 UTC.

| Día (UTC) | Kharkiv | Dnipropetrovsk | Kyiv (región) | Zaporizhzhia | Sumy | Kirovohrad | Mykolaiv | Odesa | Chernihiv | Poltava | Cherkasy | Donetsk | Zhytomyr | Kherson | Vinnytsia | Rivne | Kyiv (ciudad) | Khmelnytskyi | Volyn | Ternopil | Chernivtsi | Lviv | Ivano-Frankivsk | Zakarpattia | Luhansk | Crimea | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2022-04-04 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | 1 | · | 1 |
| 2022-12-10 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | 1 | 1 |
| 2024-05-20 | 2 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | 2 |
| 2026-03-10 | 1 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | 1 |
| 2026-08-29 | · | 1 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | 1 |
| 2026-09-07 | · | 3 | · | · | · | · | · | · | · | · | · | 2 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | 5 |
| 2026-09-08 | 81 | 71 | 23 | 35 | 24 | 26 | 16 | 16 | 17 | 19 | 17 | 34 | 8 | 15 | 5 | · | 3 | · | · | · | · | · | · | · | · | · | 410 |
| 2026-09-09 | 62 | 78 | 49 | 25 | 40 | 34 | 24 | 20 | 26 | 18 | 24 | 16 | 6 | 24 | 17 | 1 | 8 | 5 | · | · | 1 | · | · | · | · | · | 478 |
| 2026-09-10 | 82 | 86 | 50 | 21 | 33 | 44 | 16 | 23 | 33 | 25 | 16 | 8 | 13 | 2 | 5 | 11 | 7 | 4 | 10 | 3 | 1 | 2 | · | · | · | · | 495 |
| 2026-09-11 | 76 | 73 | 32 | 46 | 43 | 19 | 20 | 28 | 21 | 12 | 3 | 24 | 14 | 8 | · | 5 | 4 | 3 | 2 | · | · | · | · | · | · | · | 433 |
| 2026-09-12 | 64 | 76 | 31 | 50 | 12 | 45 | 34 | 34 | 10 | 17 | 27 | 40 | 8 | 30 | 16 | 20 | 7 | 11 | 7 | 3 | 4 | 3 | 1 | · | · | · | 550 |
| 2026-09-13 | 66 | 58 | 20 | 35 | 16 | 20 | 10 | 12 | 14 | 19 | 10 | · | 20 | 5 | 12 | 13 | 3 | 8 | 7 | 6 | 1 | 5 | 3 | · | · | · | 363 |
| 2026-09-14 | 70 | 49 | 28 | 42 | 34 | 23 | 9 | 17 | 22 | 16 | 13 | 24 | 9 | 3 | 14 | 2 | 1 | 2 | · | · | 2 | · | · | · | · | · | 380 |
| 2026-09-15 | 61 | 77 | 49 | 70 | 33 | 23 | 32 | 32 | 27 | 19 | 20 | 56 | 11 | 24 | 16 | 7 | 5 | 5 | 9 | 3 | 3 | 7 | 6 | 6 | · | · | 601 |
| 2026-09-16 | 78 | 76 | 63 | 37 | 34 | 35 | 30 | 29 | 40 | 24 | 22 | 8 | 11 | 13 | 9 | 9 | 8 | 3 | 7 | 3 | 4 | 7 | 6 | 6 | · | · | 562 |
| 2026-09-17 | 80 | 94 | 54 | 35 | 31 | 35 | 33 | 42 | 29 | 22 | 19 | 8 | 13 | 19 | 11 | 7 | 8 | 3 | 6 | 3 | 3 | 7 | 6 | 6 | · | · | 574 |
| 2026-09-18 | 68 | 80 | 57 | 40 | 24 | 44 | 25 | 50 | 28 | 19 | 21 | 24 | 16 | 15 | 11 | 4 | 5 | 3 | 2 | 3 | 1 | · | · | · | · | · | 540 |
| 2026-09-19 | 73 | 95 | 75 | 9 | 29 | 47 | 38 | 43 | 30 | 37 | 23 | 8 | 15 | 21 | 2 | 7 | 8 | 2 | 3 | · | · | · | · | · | · | · | 565 |
| 2026-09-20 | 76 | 78 | 66 | 9 | 31 | 59 | 44 | 29 | 34 | 33 | 36 | · | 23 | 22 | 24 | 7 | 7 | 6 | · | · | 1 | · | · | · | · | · | 585 |
| 2026-09-21 | 87 | 85 | 49 | 51 | 44 | 43 | 31 | 31 | 20 | 34 | 26 | 16 | 17 | 14 | 12 | 10 | 7 | 7 | 2 | 6 | 3 | · | 3 | · | · | · | 598 |
| 2026-09-22 | 70 | 116 | 51 | 42 | 39 | 35 | 32 | 37 | 43 | 32 | 20 | · | 14 | 16 | 23 | · | 10 | 6 | · | · | 2 | · | · | · | · | · | 588 |
| 2026-09-23 | 67 | 95 | 58 | 47 | 35 | 65 | 38 | 34 | 20 | 44 | 30 | 56 | 22 | 14 | 27 | 12 | 10 | 10 | 6 | 9 | 4 | · | · | · | · | · | 703 |
| 2026-09-24 | 98 | 69 | 27 | 51 | 42 | 21 | 32 | 31 | 5 | 23 | 13 | 32 | 22 | 12 | 5 | 10 | 5 | 6 | 14 | · | 5 | 1 | · | · | · | · | 524 |
| 2026-09-25 | 82 | 71 | 75 | 34 | 64 | 50 | 44 | 39 | 21 | 41 | 34 | · | 17 | 17 | 20 | 2 | 10 | 5 | · | 3 | 1 | · | · | · | · | · | 630 |
| 2026-09-26 | 82 | 63 | 36 | 26 | 43 | 32 | 41 | 36 | 15 | 34 | 18 | 8 | 8 | 12 | 20 | · | 9 | 4 | · | · | · | · | · | · | · | · | 487 |
| 2026-09-27 | 90 | 51 | 27 | 38 | 30 | 34 | 39 | 34 | 15 | 17 | 11 | 8 | 12 | 13 | 14 | 10 | 4 | 2 | 2 | · | · | · | · | · | · | · | 451 |
| 2026-09-28 | 93 | 89 | 55 | 30 | 38 | 40 | 34 | 43 | 23 | 27 | 24 | 16 | 21 | 12 | 17 | 19 | 9 | 1 | 10 | · | · | · | · | · | · | · | 601 |
| 2026-09-29 | 68 | 61 | 50 | 49 | 37 | 31 | 34 | 19 | 36 | 21 | 18 | 24 | 30 | 11 | 23 | 22 | 9 | 3 | 3 | 3 | 1 | · | 2 | · | · | · | 555 |
| 2026-09-30 | 89 | 55 | 27 | 43 | 27 | 19 | 27 | 13 | 20 | 14 | 16 | 41 | 31 | 13 | 18 | 18 | 7 | 13 | 11 | 6 | 1 | 3 | · | · | · | · | 512 |
| 2026-10-01 | 96 | 62 | 66 | 60 | 31 | 27 | 19 | 10 | 33 | 27 | 16 | 8 | 5 | 17 | 2 | 9 | 13 | 3 | 2 | · | · | · | · | · | · | · | 506 |
| 2026-10-02 | 79 | 71 | 50 | 30 | 34 | 38 | 26 | 23 | 18 | 27 | 19 | 16 | 6 | 9 | 7 | 1 | 6 | · | · | · | · | · | · | · | · | · | 460 |
| 2026-10-03 | 78 | 36 | 65 | 75 | 37 | 11 | 20 | 32 | 41 | 12 | 7 | 16 | 13 | 7 | 3 | 6 | 12 | 2 | 3 | · | · | · | · | · | · | · | 476 |
| 2026-10-04 | 76 | 61 | 54 | 26 | 43 | 35 | 21 | 19 | 32 | 24 | 13 | 8 | 15 | 9 | 10 | 11 | 10 | 7 | 4 | 3 | 1 | · | · | · | · | · | 482 |
| 2026-10-05 | 69 | 81 | 39 | 58 | 27 | 31 | 40 | 40 | 17 | 18 | 18 | 32 | 13 | 13 | 6 | 10 | 2 | 4 | 6 | · | · | · | · | · | · | · | 524 |
| 2026-10-06 | 95 | 85 | 47 | 25 | 30 | 27 | 32 | 36 | 25 | 23 | 13 | 8 | 18 | 4 | 12 | 4 | 3 | 3 | · | · | · | · | · | · | · | · | 490 |
| 2026-10-07 | 82 | 64 | 45 | 33 | 59 | 48 | 39 | 25 | 26 | 28 | 21 | 8 | 22 | 5 | 23 | 7 | 8 | 6 | 2 | 6 | · | 2 | · | · | · | · | 559 |
| 2026-10-08 | 20 | 18 | 17 | 2 | 11 | 6 | 7 | 2 | 4 | 3 | 4 | · | 7 | 3 | 4 | 16 | 2 | 2 | 7 | 3 | · | 1 | · | · | · | · | 139 |
| Total | 2361 | 2228 | 1435 | 1174 | 1055 | 1047 | 887 | 879 | 745 | 729 | 572 | 549 | 460 | 402 | 388 | 260 | 210 | 139 | 125 | 63 | 39 | 38 | 27 | 18 | 1 | 1 | 15832 |

## 8. Pendientes

- **Amenazas del último mes**: no se pueden recuperar (el histórico no las trae). Arreglo: ninguno
  posible hacia atrás; desde el 8 de octubre a las 09:17 UTC las guarda la captura.
- **Subidas de nivel dentro de una alerta** (amarillo a rojo): el histórico guarda un solo nivel.
  Arreglo: las guarda la captura de las activas desde el 8 de octubre; para lo anterior, NEPTUN
  (desde el 4 de octubre a las 12:51 UTC).
