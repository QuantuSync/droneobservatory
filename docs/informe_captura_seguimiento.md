# Captura y archivo del seguimiento en directo de drones sobre Ucrania

4 de octubre de 2026. Servicio nuevo del servidor de recogida del European Observatory of Drone
Incidents que escucha y archiva, tal como llegan, los datos de seguimiento en directo de amenazas
aéreas sobre Ucrania. Solo captura y guarda: no procesa, no clasifica y no publica nada. La razón
de hacerlo ya es que la fuente principal, NEPTUN, solo da el estado en vivo y no guarda historia:
lo que no se captura hoy se pierde. La reconstrucción de rutas con este archivo es trabajo
posterior.

Funcionamiento y órdenes: [`servidor.md`](servidor.md), «Captura del seguimiento en directo».

## 1. La fuente: lo comprobado en su documentación

Página para desarrolladores <https://neptun.in.ua/developers> (actualizada el 9 de julio de 2026)
y condiciones del API <https://neptun.in.ua/api-terms> (misma fecha), leídas el 4 de octubre de
2026 a las 11:44 UTC. Copia fechada del texto en
[`condiciones_neptun_2026-10-04/`](condiciones_neptun_2026-10-04/) con la huella del HTML
descargado; el HTML original, en el archivo privado del servidor.

| Lo descrito en el encargo | Lo que dice la documentación hoy | Comprobado en la práctica |
| --- | --- | --- |
| Flujo `wss://neptun.in.ua/api/v1/stream`, JSON | Igual. Cada mensaje es un sobre `{ type, ts, data }`; «Origin відкритий для будь-якого сайту» | Conecta sin clave; primer mensaje `snapshot`, después `alerts`, `upsert`, `remove` y `heartbeat` cada 15 s |
| Tipos snapshot, upsert, remove, heartbeat, alerts | Igual: `snapshot` (estado completo al conectar), `upsert` (`data: <Threat>`), `remove` (`data: { id }`), `heartbeat` (keep-alive), `alerts` (`data: { raions, oblasts }`) | Los cinco llegan en los primeros minutos |
| REST `threats`, `alerts`, `messages` | Igual, solo `GET`, CORS `*`. `messages` es «Жива стрічка повідомлень з Telegram-каналів» | Los tres responden 200; `threats` con `Cache-Control: public, max-age=5` |
| Sin clave, solo lectura | «Ключі API не потрібні. Сервіс безкоштовний і читальний (лише GET)» | Sin clave |
| REST no más de una vez cada 5 s, recomienda WebSocket | «опитуйте REST не частіше ніж раз на 5 секунд, а для реального часу використовуйте WebSocket або SDK» | El servicio usa una conexión WebSocket y el REST a una petición cada 10 s como mucho |
| Campos de cada amenaza | Los descritos (`id`, `type` uav/recon/missile/ballistic/kab/mig31k/unknown, `title`, `region`, `district`, `locality`, `lat`, `lon`, `heading`, `confidenceLevel`, `sourceCount`, `count`, `uncertaintyKm`, `positionQuality`, `areaOnly`, `confirmedAt`, `updatedAt`), con la velocidad dentro de `velocity: { bearingDeg, speedKmh }`, y además `status`, `explanationShort`, `advisory` y `trail` | Los mensajes reales traen además `lifecycle`, `displayConfidence`, `presumptiveCourse` y `destination`. Se guarda todo tal cual, sin elegir campos |
| Condición: enlace visible a NEPTUN | Igual: «Єдина обов’язкова умова — видиме посилання на NEPTUN поруч із картою/даними» | No se publica nada: queda como pendiente con su arreglo (apartado 8) |

**Condiciones literales** (de `/api-terms`, puntos 1 a 4; todos en
[`licencias_terceros.md`](licencias_terceros.md)):

> 1\. Безкоштовно та відкрито. API надається безкоштовно, без ключів і реєстрації. Дозволено як
> некомерційне, так і комерційне використання — за умови дотримання цих правил, зокрема
> атрибуції (п. 3).
>
> 2\. Лише читання. Публічні ендпоінти доступні лише для читання (метод GET та підписка на
> WebSocket). […]
>
> 3\. Обов’язкова атрибуція. Будь-який сервіс, що використовує дані NEPTUN, повинен показувати
> видиме посилання на NEPTUN (https://neptun.in.ua/) поруч із картою або даними — напр. «Дані:
> Карта повітряних тривог — NEPTUN». Прибирати, приховувати чи видавати дані за власні
> заборонено.
>
> 4\. Чесне навантаження. Снапшот-ендпоінти кешуються на кілька секунд — опитуйте REST не частіше
> ніж раз на 5 секунд, а для реального часу використовуйте WebSocket або SDK (одне з’єднання
> замість постійних запитів). […]

Ni las condiciones del API ni las generales (`/terms`, que tratan de la web y de la aplicación
móvil) prohíben guardar o archivar los datos, ni piden clave ni registro. Lo único distinto de lo
descrito: `robots.txt` lleva `Disallow: /api/` para todos los agentes. Es una indicación para los
rastreadores que indexan el sitio; el uso programático del API es el que ofrece su página para
desarrolladores y regulan sus condiciones, y el servicio lo hace como piden (una conexión
WebSocket, el REST muy por debajo de su tope, con la identificación del observatorio y su web).

## 2. Cómo está montado

- **`eodi-seguimiento.service`** ([`recogida/seguimiento.py`](../recogida/seguimiento.py)), siempre
  en marcha, un solo proceso con cinco tareas: el flujo de NEPTUN, el respaldo REST, los mensajes
  de `/messages`, la lectura del canal de la Fuerza Aérea y su propia vigilancia (registro cada
  30 s, resumen cada 10 minutos, huella de su código cada 5 minutos).
  - Cada mensaje del flujo se guarda entero en una línea `{"recibido", "via": "ws", "crudo"}`, con
    el texto tal como llegó: se escribe como cadena JSON y vuelve idéntico byte a byte al leerlo
    (lo comprueba un test). Un mensaje binario iría en base64 con `"binario": true`.
  - Reconexión con espera creciente (2, 4, 8… hasta 300 s, y vuelta a 2 tras una conexión de más
    de un minuto); un minuto sin mensajes es una conexión muerta. Al recibir el primer mensaje
    tras reconectar se anota el hueco: desde la última recepción hasta esa, con el motivo y las
    consultas de respaldo hechas mientras tanto. Al arrancar, el hueco desde la última recepción
    de la ejecución anterior (servicio parado o reiniciado).
  - Respaldo REST (`threats` y `alerts`, alternos) solo si el corte pasa de 30 s. Un único ritmo
    para todo el REST: ninguna petición sale antes de 10 s de la anterior.
  - `/messages` cada dos minutos, guardado solo si cambia; si el mensaje más antiguo de una
    respuesta es posterior al más nuevo de la anterior, se anota `hueco_mensajes`.
  - Identificación: `EODI-bot/1.0 (European Observatory of Drone Incidents;
    +https://droneobservatory.eu)`.
- **Convivencia con la recogida horaria.** `MemoryMax=150M`, `Nice=15`, E/S en reposo,
  `Restart=always`. No toma ningún cerrojo ajeno ni toca la base o el clon. No se reinicia con
  cada publicación horaria: solo sale (y systemd lo relanza) si cambia la huella de su propio
  código en el clon.
- **`eodi-seguimiento-archivo.timer`** ([`recogida/seguimiento_archivo.py`](../recogida/seguimiento_archivo.py)),
  minuto 3 de cada hora, `Nice=19`, E/S en reposo, 1 GB como mucho, su propio cerrojo: espera
  fuera de los minutos 15 a 40 y a que la recogida no esté en marcha (sin tocar su cerrojo);
  comprime las horas cerradas, escribe el índice de cada día terminado y sube cada día terminado a
  la copia de seguridad.

## 3. Dónde se guarda y dónde está la copia

- **Archivo**: `/home/eodi/datos/seguimiento/` (700, de `eodi`), fuera del repositorio, de la
  carpeta que publica la web y del almacén público: `neptun/AAAA/MM/neptun-AAAA-MM-DDTHH.jsonl.gz`
  y `kpszsu/AAAA/MM/kpszsu-AAAA-MM-DDTHH.jsonl.gz` por hora UTC de recepción, `huecos.jsonl`,
  `indices/AAAA-MM-DD.json` y `copias/AAAA-MM-DD.json`. Nada se borra ni se reescribe.
- **Copia de seguridad**: bucket privado `droneobservatory-archivo` de Hetzner Object Storage
  (`nbg1`), prefijo `seguimiento/`, con las mismas credenciales del proyecto que el almacén
  público. Sin política pública: sin credenciales responde 403. Elegido frente al repositorio
  privado de datos porque el archivo crece sin parar y sin cambios (no es código ni estado que
  versionar: cada día son ficheros nuevos que nunca cambian), un repositorio de git no debe
  crecer así, y el almacén ya está pagado con 1 TB incluido.

## 4. Canal de la Fuerza Aérea (t.me/kpszsu)

**Lo que había.** La recogida horaria lee el canal para los partes de cada noche y guarda en la
base solo lo que el analizador de partes reconoce. Las páginas leídas quedan en una caché de
páginas HTML (`data/cache/kpszsu/antes-<id>.html.gz`), que se sobrescribe en cada relectura: en el
servidor, desde la publicación 81139 (28 de septiembre de 2026); en este equipo, una copia de 4076
páginas con el canal entero, de la publicación 1985 (29 de septiembre de 2022) a la 81943 (30 de
septiembre de 2026), 79 118 publicaciones. Ahí están también los mensajes de seguimiento («БпЛА
на …, курс …», «Нова група ударних БпЛА…», «Реактивний БпЛА…»), con su identificador y su hora de
publicación al segundo, pero solo en su última versión (sin ediciones ni hora de cada edición), sin
hora de recepción y sin garantía de completitud entre lecturas horarias. No había un archivo de
seguimiento propiamente dicho.

**Lo que se guarda desde ahora.** El mismo servicio lee cada minuto la página más reciente y guarda
en bruto el bloque HTML de cada publicación nueva o cambiada (versión 0, 1, 2…), con su
identificador, su hora de publicación y la hora de recepción, en
`kpszsu/AAAA/MM/kpszsu-AAAA-MM-DDTHH.jsonl`. Si entre dos lecturas se han publicado más de las que
caben en una página, lee las anteriores hasta enlazar; cada 10 minutos relee la segunda página para
las ediciones.

**Cuántos mensajes de seguimiento hay ya guardados.** En la copia local, contados con un patrón
de texto aproximado (solo para dimensionar; no se clasifica nada): unos 33 300 desde octubre de
2022, regulares desde junio de 2023 (51 ese mes, 155 en julio de 2023) y creciendo (4209 en
septiembre de 2026, sobre 5914 publicaciones del canal).

**¿Se puede recuperar el histórico?** Sí, con el lector actual (`recogida/telegram.py`, la vista
`t.me/s/kpszsu?before=<id>` hacia atrás): unas 4100 páginas a una cada 3 s, unas 3 h 30 min de
peticiones, sin coste económico, unos 50 MB comprimidos. En la práctica ya está casi todo en la
copia local de la caché: bastaría con convertirla al formato del archivo (minutos) y leer las
páginas que falten. Lo que no se puede recuperar: las ediciones anteriores y su hora, y las
publicaciones borradas. No se ha recuperado.

## 5. Volumen medido

En el servidor, del arranque (4 de octubre de 2026, 12:51 UTC) a las 16:00 UTC, una tarde
tranquila. Líneas por hora de recepción, amenazas distintas (ids de snapshot, upsert y remove) y
tamaño del fichero de la hora:

| Hora (UTC) | heartbeat | upsert | remove | alerts | snapshot | `/messages` (cambios) | Amenazas distintas | Sin comprimir | Comprimido |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 12 (desde 12:51) | 33 | 22 | 13 | 6 | 2 | 5 | 25 | 262 KB | 44 KB |
| 13 (parado 13:36–13:49) | 190 | 139 | 84 | 12 | 1 | 24 | 92 | 882 KB | 113 KB |
| 14 | 236 | 126 | 63 | 16 | 1 | 30 | 66 | 1205 KB | 194 KB |
| 15 | 232 | 107 | 64 | 18 | 0 | 30 | 64 | 1170 KB | 189 KB |

- **Por hora entera** (14 y 15): unas 460 líneas, de 64 a 66 amenazas distintas, 1,2 MB sin
  comprimir y 190 KB comprimido. El heartbeat llega cada 15 s (236 por hora con el flujo
  completo). De lo que ocupa, dos tercios son las respuestas de `/messages` (unos 26 KB cada
  una, 30 por hora), que comprimen bien.
- **Fuerza Aérea**: de 6 a 21 publicaciones nuevas por hora esta tarde, de 3 a 5 KB comprimidos
  por hora; ninguna edición vista todavía.
- **Por día**: a este ritmo, 24 × 0,19 MB ≈ **4,6 MB comprimidos al día** (unos 28 MB sin
  comprimir). Las noches de ataque con cientos de drones traen muchos más `upsert` y `remove`:
  la previsión es de **5 a 15 MB al día, de 150 a 450 MB al mes**, un 0,05 % al mes de la cuota
  de 1 TB del almacén. En el servidor, con 62 GB libres, son más de diez años.
- **Memoria**: el servicio ocupa 21–26 MB (pico 25,9 MB, sobre el tope de 150 MB); el trabajo
  del archivo y las pruebas de copia y restauración, 17 MB.
- `/messages` aporta texto que el flujo no trae (mensajes de canales de Telegram que NEPTUN
  agrega, con canal, texto y hora). Cada dos minutos basta: en lo medido nunca faltó un tramo
  entre dos respuestas (ningún `hueco_mensajes`).
- Además de lo documentado, la fuente emite amenazas de tipo `fpv` (`"type":"fpv","title":"FPV-дрон"`)
  y los campos `lifecycle`, `displayConfidence`, `presumptiveCourse` y `destination`. Se guardan
  tal cual.

## 6. Muestra de mensajes reales

Diez mensajes de cada tipo del flujo, repartidos por el periodo medido, tal como se guardaron
(hora de recepción, fichero y línea, y el texto del mensaje; los largos, cortados con su tamaño
total). Solo hubo cuatro `snapshot`: la fuente manda uno por conexión. Los textos de `/messages`
no se reproducen aquí (son publicaciones de canales de terceros); están en el archivo. Datos:
[Карта повітряних тривог — NEPTUN](https://neptun.in.ua/).

**snapshot** (4 recibidos; 4 en la muestra)

```
2026-10-04T12:51:48.216421Z neptun-2026-10-04T12.jsonl.gz:4
{"type":"snapshot","ts":"2026-10-04T12:51:48.006Z","data":{"threats":[{"id":"trk_00238167","type":"fpv","title":"FPV-дрон","region":"","district":"","locality":"Канівське","lat":47.69488,"lon":35.1128,"heading":null,"confidenceLevel":"medium","sourceCount":1,"updatedAt":"2026-10-04T12:50:15Z","explanationShort":"FPV-дрон — Канівське. Підтверджень: 1.","statu… [6925 bytes]
2026-10-04T12:52:30.871322Z neptun-2026-10-04T12.jsonl.gz:16
{"type":"snapshot","ts":"2026-10-04T12:52:30.06Z","data":{"threats":[{"id":"trk_00238166","type":"uav","title":"БпЛА","region":"Сумська область","district":"","locality":"Недригайлів","lat":51.103991290759936,"lon":34.24425279602661,"heading":220,"confidenceLevel":"medium","sourceCount":5,"updatedAt":"2026-10-04T12:52:01Z","explanationShort":"БпЛА курсом на … [7074 bytes]
2026-10-04T13:49:20.410549Z neptun-2026-10-04T13.jsonl.gz:336
{"type":"snapshot","ts":"2026-10-04T13:49:20.004Z","data":{"threats":[{"id":"trk_00238312","type":"uav","title":"БпЛА","region":"Київська область","district":"","locality":"Бориспіль","lat":50.68865906776992,"lon":31.158484948866786,"heading":201,"confidenceLevel":"medium","sourceCount":6,"updatedAt":"2026-10-04T13:48:33Z","explanationShort":"БпЛА курсом на … [16043 bytes]
2026-10-04T14:46:41.932314Z neptun-2026-10-04T14.jsonl.gz:366
{"type":"snapshot","ts":"2026-10-04T14:46:41.008Z","data":{"threats":[{"id":"trk_00238379","type":"uav","title":"БпЛА","region":"Дніпропетровська область","district":"","locality":"Письменне","lat":47.995494861005795,"lon":36.24268406010508,"heading":305,"confidenceLevel":"medium","sourceCount":8,"updatedAt":"2026-10-04T14:40:05Z","explanationShort":"БпЛА ку… [4670 bytes]
```

**upsert** (403 recibidos; 10 en la muestra)

```
2026-10-04T12:52:24.106221Z neptun-2026-10-04T12.jsonl.gz:8
{"type":"upsert","ts":"2026-10-04T12:52:23.991Z","data":{"id":"trk_00238159","type":"uav","title":"БпЛА","region":"Сумська область","district":"","locality":"Ромни","lat":50.984911101801664,"lon":33.905863919746416,"heading":229,"confidenceLevel":"medium","sourceCount":6,"updatedAt":"2026-10-04T12:52:01Z","explanationShort":"БпЛА курсом на Ромни. Підтверджен… [617 bytes]
2026-10-04T13:05:54.107178Z neptun-2026-10-04T13.jsonl.gz:54
{"type":"upsert","ts":"2026-10-04T13:05:53.99Z","data":{"id":"trk_00237985","type":"uav","title":"БпЛА","region":"Дніпропетровська область","district":"","locality":"Дніпро","lat":48.4647,"lon":35.0462,"heading":222,"confidenceLevel":"medium","sourceCount":3,"updatedAt":"2026-10-04T12:12:37Z","explanationShort":"БпЛА — Дніпро, Дніпропетровська область. Підтв… [635 bytes]
2026-10-04T13:26:24.108002Z neptun-2026-10-04T13.jsonl.gz:216
{"type":"upsert","ts":"2026-10-04T13:26:24.01Z","data":{"id":"trk_00238225","type":"fpv","title":"FPV-дрон","region":"Запорізька область","district":"Олександрівський район","regionKey":"олександрівський","locality":"Запоріжжя","lat":47.8388,"lon":35.1396,"heading":null,"confidenceLevel":"medium","sourceCount":2,"updatedAt":"2026-10-04T13:26:04Z","explanatio… [639 bytes]
2026-10-04T13:35:24.389540Z neptun-2026-10-04T13.jsonl.gz:310
{"type":"upsert","ts":"2026-10-04T13:35:24.173Z","data":{"id":"trk_00238267","type":"uav","title":"БпЛА","region":"Київ","district":"","locality":"Лісовий масив","lat":50.46391308348122,"lon":30.64793373955241,"heading":128.761404127664,"confidenceLevel":"high","sourceCount":3,"updatedAt":"2026-10-04T13:34:51Z","explanationShort":"БпЛА — Лісовий масив, Київ.… [757 bytes]
2026-10-04T13:59:54.113412Z neptun-2026-10-04T13.jsonl.gz:452
{"type":"upsert","ts":"2026-10-04T13:59:54.04Z","data":{"id":"trk_00238119","type":"uav","title":"Рій БпЛА (3+)","region":"Одеська область","district":"","lat":45.41250000000001,"lon":30.7625,"heading":null,"confidenceLevel":"high","sourceCount":2,"count":3,"updatedAt":"2026-10-04T13:54:05Z","explanationShort":"Рій БпЛА баражують над морем. Підтверджень: 2."… [585 bytes]
2026-10-04T14:27:24.153824Z neptun-2026-10-04T14.jsonl.gz:208
{"type":"upsert","ts":"2026-10-04T14:27:24.069Z","data":{"id":"trk_00238352","type":"uav","title":"БпЛА","region":"Запорізька область","district":"","locality":"Оріхів","lat":47.567,"lon":35.787,"heading":196,"confidenceLevel":"high","sourceCount":2,"updatedAt":"2026-10-04T14:26:54Z","explanationShort":"БпЛА — Оріхів, Запорізька область. Підтверджень: 2.","s… [672 bytes]
2026-10-04T14:40:24.042406Z neptun-2026-10-04T14.jsonl.gz:316
{"type":"upsert","ts":"2026-10-04T14:40:23.964Z","data":{"id":"trk_00238341","type":"uav","title":"БпЛА","region":"Харківська область","district":"","locality":"Харків","lat":50.17988656692176,"lon":36.39067560548774,"heading":210,"confidenceLevel":"medium","sourceCount":9,"updatedAt":"2026-10-04T14:40:05Z","explanationShort":"БпЛА курсом на Харків. Підтверд… [770 bytes]
2026-10-04T14:58:54.104389Z neptun-2026-10-04T14.jsonl.gz:462
{"type":"upsert","ts":"2026-10-04T14:58:53.943Z","data":{"id":"trk_00238388","type":"fpv","title":"FPV-дрон","region":"Запорізька область","district":"","locality":"Кушугум","lat":47.6586,"lon":35.2706,"heading":null,"confidenceLevel":"medium","sourceCount":1,"updatedAt":"2026-10-04T14:58:16Z","explanationShort":"FPV-дрон — Кушугум, Запорізька область. Підтв… [668 bytes]
2026-10-04T15:15:24.078099Z neptun-2026-10-04T15.jsonl.gz:128
{"type":"upsert","ts":"2026-10-04T15:15:23.952Z","data":{"id":"trk_00238406","type":"uav","title":"БпЛА","region":"","district":"","locality":"Дергачі","lat":50.22422025862877,"lon":36.34774356160882,"heading":231,"confidenceLevel":"medium","sourceCount":2,"count":2,"updatedAt":"2026-10-04T15:15:13Z","explanationShort":"БпЛА курсом на Дергачі. Підтверджень: … [568 bytes]
2026-10-04T15:30:54.113548Z neptun-2026-10-04T15.jsonl.gz:263
{"type":"upsert","ts":"2026-10-04T15:30:54.02Z","data":{"id":"trk_00238429","type":"uav","title":"БпЛА","region":"Полтавська область","district":"","locality":"Кременчук","lat":48.82036841062527,"lon":33.58679191791975,"heading":336,"confidenceLevel":"medium","sourceCount":13,"count":3,"updatedAt":"2026-10-04T15:28:14Z","explanationShort":"БпЛА курсом на Кре… [649 bytes]
```

**remove** (231 recibidos; 10 en la muestra)

```
2026-10-04T12:52:24.283070Z neptun-2026-10-04T12.jsonl.gz:11
{"type":"remove","ts":"2026-10-04T12:52:24.095Z","data":{"id":"trk_00238163"}}
2026-10-04T13:05:54.397905Z neptun-2026-10-04T13.jsonl.gz:58
{"type":"remove","ts":"2026-10-04T13:05:54.145Z","data":{"id":"trk_00238178"}}
2026-10-04T13:26:54.430766Z neptun-2026-10-04T13.jsonl.gz:222
{"type":"remove","ts":"2026-10-04T13:26:54.25Z","data":{"id":"trk_00238215"}}
2026-10-04T13:50:54.444100Z neptun-2026-10-04T13.jsonl.gz:360
{"type":"remove","ts":"2026-10-04T13:50:54.242Z","data":{"id":"trk_00238316"}}
2026-10-04T13:58:24.226640Z neptun-2026-10-04T13.jsonl.gz:439
{"type":"remove","ts":"2026-10-04T13:58:24.135Z","data":{"id":"trk_00238311"}}
2026-10-04T14:14:24.028442Z neptun-2026-10-04T14.jsonl.gz:111
{"type":"remove","ts":"2026-10-04T14:14:23.937Z","data":{"id":"trk_00238329"}}
2026-10-04T14:36:54.101861Z neptun-2026-10-04T14.jsonl.gz:288
{"type":"remove","ts":"2026-10-04T14:36:53.984Z","data":{"id":"trk_00238352"}}
2026-10-04T15:00:54.271150Z neptun-2026-10-04T15.jsonl.gz:10
{"type":"remove","ts":"2026-10-04T15:00:54.021Z","data":{"id":"trk_00238390"}}
2026-10-04T15:16:54.078802Z neptun-2026-10-04T15.jsonl.gz:139
{"type":"remove","ts":"2026-10-04T15:16:53.947Z","data":{"id":"trk_00238438"}}
2026-10-04T15:34:24.109526Z neptun-2026-10-04T15.jsonl.gz:287
{"type":"remove","ts":"2026-10-04T15:34:23.95Z","data":{"id":"trk_00238457"}}
```

**heartbeat** (711 recibidos; 10 en la muestra)

```
2026-10-04T12:51:54.746089Z neptun-2026-10-04T12.jsonl.gz:6
{"type":"heartbeat","ts":"2026-10-04T12:51:54.64Z"}
2026-10-04T13:09:39.709079Z neptun-2026-10-04T13.jsonl.gz:91
{"type":"heartbeat","ts":"2026-10-04T13:09:39.641Z"}
2026-10-04T13:27:24.719105Z neptun-2026-10-04T13.jsonl.gz:227
{"type":"heartbeat","ts":"2026-10-04T13:27:24.64Z"}
2026-10-04T13:57:39.728340Z neptun-2026-10-04T13.jsonl.gz:430
{"type":"heartbeat","ts":"2026-10-04T13:57:39.64Z"}
2026-10-04T14:15:24.706710Z neptun-2026-10-04T14.jsonl.gz:121
{"type":"heartbeat","ts":"2026-10-04T14:15:24.641Z"}
2026-10-04T14:33:09.708866Z neptun-2026-10-04T14.jsonl.gz:245
{"type":"heartbeat","ts":"2026-10-04T14:33:09.641Z"}
2026-10-04T14:51:54.722816Z neptun-2026-10-04T14.jsonl.gz:405
{"type":"heartbeat","ts":"2026-10-04T14:51:54.64Z"}
2026-10-04T15:09:39.828063Z neptun-2026-10-04T15.jsonl.gz:82
{"type":"heartbeat","ts":"2026-10-04T15:09:39.64Z"}
2026-10-04T15:27:54.846549Z neptun-2026-10-04T15.jsonl.gz:233
{"type":"heartbeat","ts":"2026-10-04T15:27:54.64Z"}
2026-10-04T15:46:39.724913Z neptun-2026-10-04T15.jsonl.gz:363
{"type":"heartbeat","ts":"2026-10-04T15:46:39.64Z"}
```

**alerts** (54 recibidos; 10 en la muestra)

```
2026-10-04T12:51:48.251807Z neptun-2026-10-04T12.jsonl.gz:5
{"type":"alerts","ts":"2026-10-04T12:51:48.006Z","data":{"version":1791118079,"updatedAt":"2026-10-04T12:47:59.318708623Z","raions":[{"key":"бахмутський","name":"Бахмутський район","oblast":"Донецька область","since":"2026-10-04T04:28:27.163841Z","level":"red","reasons":["Ракетна загроза (червоний рівень)"]},{"key":"бердянський","name":"Бердянський район","o… [10264 bytes]
2026-10-04T12:59:49.831089Z neptun-2026-10-04T12.jsonl.gz:85
{"type":"alerts","ts":"2026-10-04T12:59:49.637Z","data":{"version":1791118786,"updatedAt":"2026-10-04T12:59:46.997528176Z","raions":[{"key":"бахмутський","name":"Бахмутський район","oblast":"Донецька область","since":"2026-10-04T04:28:27.163841Z","level":"red","reasons":["Ракетна загроза (червоний рівень)"]},{"key":"бердянський","name":"Бердянський район","o… [11538 bytes]
2026-10-04T13:16:39.791551Z neptun-2026-10-04T13.jsonl.gz:140
{"type":"alerts","ts":"2026-10-04T13:16:39.637Z","data":{"version":1791119795,"updatedAt":"2026-10-04T13:16:35.290976773Z","raions":[{"key":"бахмутський","name":"Бахмутський район","oblast":"Донецька область","since":"2026-10-04T04:28:27.163841Z","level":"red","reasons":["Ракетна загроза (червоний рівень)"]},{"key":"бердянський","name":"Бердянський район","o… [9382 bytes]
2026-10-04T13:34:59.933519Z neptun-2026-10-04T13.jsonl.gz:307
{"type":"alerts","ts":"2026-10-04T13:34:59.637Z","data":{"version":1791120895,"updatedAt":"2026-10-04T13:34:55.150198219Z","raions":[{"key":"бахмутський","name":"Бахмутський район","oblast":"Донецька область","since":"2026-10-04T04:28:27.163841Z","level":"red","reasons":["Ракетна загроза (червоний рівень)"]},{"key":"бердянський","name":"Бердянський район","o… [8537 bytes]
2026-10-04T14:05:49.796754Z neptun-2026-10-04T14.jsonl.gz:48
{"type":"alerts","ts":"2026-10-04T14:05:49.637Z","data":{"version":1791122744,"updatedAt":"2026-10-04T14:05:44.968647653Z","raions":[{"key":"бахмутський","name":"Бахмутський район","oblast":"Донецька область","since":"2026-10-04T04:28:27.163841Z","level":"red","reasons":["Ракетна загроза (червоний рівень)"]},{"key":"бердянський","name":"Бердянський район","o… [12206 bytes]
2026-10-04T14:17:29.766259Z neptun-2026-10-04T14.jsonl.gz:138
{"type":"alerts","ts":"2026-10-04T14:17:29.637Z","data":{"version":1791123444,"updatedAt":"2026-10-04T14:17:24.958582123Z","raions":[{"key":"бахмутський","name":"Бахмутський район","oblast":"Донецька область","since":"2026-10-04T04:28:27.163841Z","level":"red","reasons":["Ракетна загроза (червоний рівень)"]},{"key":"бердянський","name":"Бердянський район","o… [7111 bytes]
2026-10-04T14:41:34.665718Z neptun-2026-10-04T14.jsonl.gz:328
{"type":"alerts","ts":"2026-10-04T14:41:34.637Z","data":{"version":1791124893,"updatedAt":"2026-10-04T14:41:33.558113508Z","raions":[{"key":"бахмутський","name":"Бахмутський район","oblast":"Донецька область","since":"2026-10-04T04:28:27.163841Z","level":"red","reasons":["Ракетна загроза (червоний рівень)"]},{"key":"бердянський","name":"Бердянський район","o… [9149 bytes]
2026-10-04T15:02:34.819449Z neptun-2026-10-04T15.jsonl.gz:27
{"type":"alerts","ts":"2026-10-04T15:02:34.638Z","data":{"version":1791126151,"updatedAt":"2026-10-04T15:02:31.078481427Z","raions":[{"key":"бахмутський","name":"Бахмутський район","oblast":"Донецька область","since":"2026-10-04T04:28:27.163841Z","level":"red","reasons":["Ракетна загроза (червоний рівень)"]},{"key":"бердянський","name":"Бердянський район","o… [9177 bytes]
2026-10-04T15:30:29.884320Z neptun-2026-10-04T15.jsonl.gz:259
{"type":"alerts","ts":"2026-10-04T15:30:29.637Z","data":{"version":1791127827,"updatedAt":"2026-10-04T15:30:27.291016659Z","raions":[{"key":"бахмутський","name":"Бахмутський район","oblast":"Донецька область","since":"2026-10-04T04:28:27.163841Z","level":"red","reasons":["Ракетна загроза (червоний рівень)"]},{"key":"бердянський","name":"Бердянський район","o… [8704 bytes]
2026-10-04T15:34:49.941047Z neptun-2026-10-04T15.jsonl.gz:290
{"type":"alerts","ts":"2026-10-04T15:34:49.637Z","data":{"version":1791128087,"updatedAt":"2026-10-04T15:34:47.002925397Z","raions":[{"key":"бахмутський","name":"Бахмутський район","oblast":"Донецька область","since":"2026-10-04T04:28:27.163841Z","level":"red","reasons":["Ракетна загроза (червоний рівень)"]},{"key":"бердянський","name":"Бердянський район","o… [7848 bytes]
```


## 7. Comprobación en producción

1. **Activo, dentro de su tope y más de dos horas guardando sin huecos sin explicar.** En marcha
   desde las 12:51 UTC (`NRestarts=0`), 21–26 MB de 150 MB. Huecos anotados del flujo, todos con
   su motivo: 12:52:24–12:52:30 (6 s, el corte provocado), 13:36:39–13:49:20 (761 s, la parada
   provocada) y 14:45:39–14:46:41 (62 s, la fuente dejó de mandar mensajes un minuto y el
   servicio reconectó solo). De 13:49 a 16:00 no hay más.
2. **Ficheros por hora con todos los tipos y legibles.** `neptun-2026-10-04T12…T16`, con
   snapshot, upsert, remove, heartbeat y alerts (tabla del apartado 5), y `kpszsu-…`; las horas
   cerradas comprimidas en el minuto 3 por `eodi-seguimiento-archivo` (código 0 cada vez) y
   leídas con `zcat`.
3. **Corte provocado.** A las 12:52:28 se cerró su conexión TCP con NEPTUN (`ss -K`, solo ese
   socket): el servicio anotó `desconectado` («ConnectionClosedError: no close frame received
   or sent»), reconectó a las 12:52:30 y escribió el hueco 12:52:24,7–12:52:30,9 (6,2 s) en el
   fichero de la hora y en `huecos.jsonl`.
4. **Dos recogidas horarias con el servicio en marcha.** Las de las 13:17 y 14:17 terminaron bien
   y publicaron en `main`, con picos de 3,6 GB las dos (las de las doce horas anteriores, sin el
   servicio: de 3,2 a 4,2 GB) y 17,8 y 8,5 minutos. La de las 12:17, antes del servicio, falló al
   subir la base (pasaba de 100 MB; lo arreglaron los PR #106 y #107 de otra sesión).
5. **Copia de seguridad.** Forzada a las 14:04 para el día en curso (`copiar --dia 2026-10-04`,
   4 ficheros subidos, 17 MB de memoria). Restaurado
   `seguimiento/neptun/2026/10/neptun-2026-10-04T13.jsonl.gz`: 115 680 bytes, SHA-256
   `6b6bd397…dcbc60`, igual a la anotada en el objeto y a la del fichero del servidor, idéntico
   byte a byte y 454 líneas legibles. Sin credenciales el bucket responde 403 al objeto y al
   listado.
6. **Aviso.** Servicio parado de 13:36:43 a 13:49:20 (12,6 minutos). Al volver anotó el hueco
   largo; la recogida de las 14:17 lo llevó a `estado.json` (`ultimo_hueco_largo`) y el vigía
   abrió la incidencia #111 «La captura del seguimiento en directo no recibe datos». Se cierra
   sola cuando pasan dos horas sin huecos largos. El servicio sigue en marcha.

La web acepta el `estado.json` con el campo nuevo sin mostrar nada distinto: comprobado en
producción a 360×800, 390×844, 412×915 y 1440×900 («datos al día», sin errores en la consola,
sin desbordamiento horizontal).

## 8. Pendientes, cada uno con su arreglo

- **Atribución a NEPTUN.** Cuando se publique algo derivado de estos datos, cada vista y cada
  fichero llevarán junto a los datos el enlace visible «Дані: Карта повітряних тривог — NEPTUN»
  (<https://neptun.in.ua/>), traducido en cada idioma de la web, la nota de que NEPTUN es un
  agregador y no un sistema oficial de alerta, y en los ficheros abiertos un campo `atribucion`;
  un test de esa capa lo comprobará antes de publicarla
  ([`licencias_terceros.md`](licencias_terceros.md)).
- **Ediciones antiguas del canal de la Fuerza Aérea.** Las ediciones de una publicación que ya no
  está en las dos primeras páginas no se ven por la vista web. Arreglo: leer el canal con una
  cuenta de Telegram (API MTProto, que da la hora de cada edición) si hace falta esa precisión.
- **Cifra de un día entero.** El primer día completo es el 5 de octubre: su índice
  (`indices/2026-10-05.json`, con mensajes por tipo, amenazas distintas, huecos y tamaño) se
  escribe a las 00:03 UTC del 6 y se copia al bucket. Arreglo: anotar aquí su tamaño y
  sustituir la previsión del apartado 5.
- **Respaldo REST en producción.** No ha hecho falta todavía (ningún corte pasó de 30 s con el
  servicio en marcha); está cubierto por los tests. Arreglo: cuando un corte largo lo active, el
  hueco anotado llevará `respaldo_rest` con las consultas hechas; comprobarlo entonces en
  `huecos.jsonl`.
- **Histórico del canal anterior a hoy.** Convertir la copia local de la caché al formato del
  archivo y completar con el lector las páginas que falten (apartado 4).
