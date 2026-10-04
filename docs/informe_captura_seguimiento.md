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

Pendiente de las horas de producción (se completa en este mismo informe).

## 6. Muestra de mensajes reales

Pendiente de las horas de producción (se completa en este mismo informe).

## 7. Comprobación en producción

Pendiente (se completa en este mismo informe).

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
- **Histórico del canal anterior a hoy.** Convertir la copia local de la caché al formato del
  archivo y completar con el lector las páginas que falten (apartado 4).
