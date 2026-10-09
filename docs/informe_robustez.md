# La web a prueba de caídas y los créditos del autor

European Observatory of Drone Incidents, 9 de octubre de 2026. Dos bloques: que la web aguante una
avalancha de visitas y siga funcionando si cae el almacén principal (PR #193), y los créditos del
autor en la web, en los datos y en el repositorio (PR #192).

**En corto.** El mapa de fondo y todo lo que la web pedía al almacén de Hetzner pasan ahora por la
red de Vercel con caché: con 15 visitas nuevas por segundo desde una sola dirección no hubo ni un
error y, de cada 1 500 peticiones del almacén, solo 4 llegaron a Hetzner. Hay una copia pública
del almacén en Helsinki que se pone al día sola cada 2 minutos; con el almacén principal caído (lo
probamos apuntándolo a una dirección que no responde) la web carga entera desde Helsinki. La
primera carga es más rápida que antes. El autor, su ORCID, la licencia y la cita recomendada van
dentro de cada fichero de datos, en las páginas y en el repositorio.

## Bloque 1. Que aguante y no se caiga

### Qué había

El navegador pedía directamente al almacén público de Núremberg el mapa de fondo (por trozos,
con peticiones Range a un fichero de 24,6 GB), `estado.json`, `directo.json` y las capas (GPS,
focos, luces, satélite, rutas). Hetzner limita cada bucket a 750 peticiones por segundo: el informe
del blindaje calculó que con unas 13 a 20 visitas nuevas por segundo el mapa empezaría a cargar a
trozos. Y si el almacén caía, la web se quedaba sin mapa.

### Qué se ha cambiado

- **El almacén, a través de Vercel.** La web pide todo eso a su propio dominio, en
  `/almacen/<objeto>`, y lo sirve una función (`api/almacen.ts`, en Fráncfort, junto a Núremberg)
  con la caché de Vercel delante: el primer visitante de cada región lo trae del almacén y los
  siguientes lo reciben de la caché. El mapa de fondo se pide por trozos en la propia dirección
  (`/almacen/europa-z14.pmtiles?o=<desde>&l=<largo>`). Cuánto guarda la caché: el mapa de fondo un
  año (el fichero no cambia: si un día cambia, cambia de nombre), `estado.json` y `directo.json`
  30 segundos, los datos publicados 60 segundos, las capas 5 minutos y las versiones mensuales un
  día. Lo guardado se sigue sirviendo hasta 7 días si el almacén falla.
- **Copia pública de reserva en Helsinki** (`droneobservatory-reserva`), con los mismos objetos y
  las mismas cabeceras que la de Núremberg. Se pone al día sola cada 2 minutos y justo después de
  cada publicación (unidad `eodi-reserva`).
- **Si el principal no responde** en 3 segundos o da un error, la función sirve desde Helsinki y
  durante un minuto ya no prueba Núremberg. Si la propia función fallara, el navegador pide a
  Helsinki directamente. Y el build de la web baja los datos de Helsinki si Núremberg no responde.
- **La vigilancia** avisa si la copia de Helsinki lleva más de 30 minutos sin estar al día
  (`salud.json`, problema «reserva»).
- La política de seguridad de contenido ya no admite Núremberg (el navegador no lo pide); admite
  solo Helsinki, para el caso de que la función falle.
- `docs/operacion.md`: qué hacer si cae el almacén principal, si cae Vercel y cómo comprobar la
  copia de Helsinki.

### Por qué la caché de Vercel y no dos almacenes: lo que se midió

El encargo pedía probar primero en una vista previa que la caché de Vercel guarda bien los trozos
del mapa. Se probaron dos formas el 9 de octubre:

1. **Reescritura directa de `/…` al almacén, con la caché de reescrituras activada.** La caché dio
   «HIT» desde la segunda petición, pero guardó el primer trozo pedido (bytes 0 a 16 383) y lo
   devolvió para **cualquier** otro rango: pedidos los bytes 16 384–20 000 o 500 000–600 000,
   respondía con los bytes 0–16 383 y la cabecera `Content-Range` del primero. Comparado byte a
   byte con el almacén: distinto en los cinco rangos probados. El mapa habría salido roto. La
   documentación de Vercel lo dice así: no guarda respuestas a peticiones con Range. Descartada.
2. **Función que recibe el trozo en la dirección y responde con 200.** Cada trozo es una dirección
   distinta y la caché la guarda tal cual. En la vista previa: siete trozos, todos idénticos byte a
   byte al almacén; el mismo trozo pedido dos veces, la segunda desde la caché («HIT»); la versión
   mensual de 27 MB, entera e idéntica.

El plan B (repartir el mapa de fondo entre Núremberg y Helsinki) solo duplicaría el tope: unas 26 a
40 visitas nuevas por segundo. Con la caché, el tope del almacén deja de importar para todo lo que
ya está guardado, que en una avalancha es casi todo (todos los visitantes piden la misma vista
inicial). Helsinki se usa como reserva.

Una visita nueva a la portada, medida en un navegador real, hace 37 peticiones a la web, de ellas 10
al almacén (6 trozos del mapa de fondo y 4 ficheros): unas 10 o 12 según el tamaño de la pantalla.
El informe del blindaje contaba de 37 a 57 trozos del mapa: aquella medida incluía las peticiones de
toda la página hasta quedar quieta; la de hoy cuenta solo las del almacén, con la página recién
abierta. Al mover el mapa se piden más trozos, que también se guardan.

### Prueba de carga, antes y después

Moderada y breve, como la del blindaje: escalones de 10 segundos con pausas de un minuto. Cada
«visita» pide a la vez las 37 direcciones de una visita nueva real (portada, código, datos y los
trozos del mapa), grabadas con un navegador. Desde el servidor (una sola dirección IP).

| Visitas nuevas por segundo | Peticiones por segundo | Visitas sin ningún error | p50 | p95 | Peticiones del almacén que llegaron a Hetzner |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | 187 | 50 de 50 | 43 ms | 124 ms | 25 de 500 (la primera vez) |
| 10 | 371 | 100 de 100 | 41 ms | 76 ms | 4 de 1 000 |
| 12 | 444 | 120 de 120 | 40 ms | 72 ms | 3 de 1 200 |
| 15 | 545 | 150 de 150 | 40 ms | 75 ms | 4 de 1 500 |
| 20 | 200 (*) | 200 de 200 | 43 ms | 87 ms | 6 de 2 000 |

(*) A 20 visitas por segundo las 200 visitas salieron bien, pero el generador de una sola máquina no
pudo lanzarlas al ritmo pedido (tardó 37 s en vez de 10): esa fila dice que no hubo errores, no que
se sostuvieran 20 por segundo. No se subió más para no disparar la protección de Vercel contra
ataques desde una sola dirección (en el blindaje saltó hacia las 9 000 peticiones seguidas).

Se lanzó también a la vez desde el equipo del dueño, como segunda dirección: su conexión no pasó de
55 peticiones por segundo y dio errores de red del propio equipo (ninguna respuesta de error de
Vercel), así que esa parte no cuenta.

**Antes:** el almacén ponía el tope en unas 13 a 20 visitas nuevas por segundo (750 peticiones por
segundo del bucket). **Ahora:** con la caché, cada visita nueva manda al almacén unas 0,003
peticiones (4 de cada 1 500): el tope de 750 por segundo queda lejísimos, y lo que marca la
capacidad es la red de Vercel, que no se puede saturar desde aquí sin incumplir sus condiciones.
Medido sin un solo error: 15 visitas nuevas por segundo desde una sola dirección; una avalancha real
viene de muchas direcciones y de muchas regiones, y cada región guarda su copia.

### Primera carga, antes y después

Producción, caché del navegador vacía, cinco pasadas por perfil (`web/scripts/medir-carga.ts`;
móvil emulado con el procesador cuatro veces más lento):

| | Antes (hacia las 14:20 UTC) | Después (hacia las 16:05 UTC) |
| --- | ---: | ---: |
| Escritorio, mapa listo (mediana) | 2 144 ms | 1 622 ms |
| Móvil, mapa listo (mediana) | 3 716 ms | 2 590 ms |
| Escritorio, primera pintura | 288 ms | 268 ms |
| Móvil, primera pintura | 360 ms | 324 ms |

No empeora: mejora, porque los trozos del mapa llegan por la misma conexión que la página en vez de
abrir otra con el almacén. Un primer visitante de una región en la que la caché aún no tiene el
trozo espera un poco más ese trozo (unos 0,4 a 0,8 s en vez de 0,2 a 0,6 s).

### Prueba de caída del almacén principal

**En una vista previa** (rama `prueba-caida-principal`, solo para la prueba), con el almacén
principal apuntado a `https://10.255.255.1`, una dirección que no responde, en la función y en la
configuración que lee el build:

- El build bajó los datos publicados y las versiones de Helsinki («versiones del almacén
  principal: fetch failed; se leen de la reserva») y la web se construyó con los mismos 442
  incidentes.
- La función: la primera petición tardó 3,7 s (los 3 s del tope más Helsinki) y respondió desde la
  reserva (`x-almacen: reserva`); las siguientes fueron directas a Helsinki, sin esperar.
- En un navegador real, en 360×800, 390×844, 412×915 y escritorio: el mapa entero, con todas las
  peticiones del almacén servidas por la web desde Helsinki y ningún error. Capturas revisadas
  una a una: el mapa de fondo, los marcadores, la barra de estado y los botones, iguales que con el
  principal. Tiempo hasta el mapa listo: 7,9 s el primer visitante (la función arrancando y
  esperando el tope), 1,7 s los siguientes.

**En producción**, bloqueando en el navegador la función (como si fallara Vercel al servir el
almacén): en los cuatro tamaños, el mapa entero con todo pedido directamente a Helsinki (de 9 a 11
peticiones, ninguna fallida), en 2,4 a 5,7 s. En la vista previa este camino no se puede probar:
Helsinki solo admite peticiones del dominio de la web.

**Lo que se vio por el camino**: Helsinki lee más lento en frío que Núremberg. Cuarenta trozos al
azar del mapa de fondo: mediana 0,49 s en Helsinki y 0,22 s en Núremberg; 7 de 40 por encima de
1,5 s en Helsinki (el más lento, 4,4 s) y ninguno en Núremberg. Una zona del fichero recién subido
llegó a tardar 32 s y dio dos 504 a los 60 s; media hora después respondía en 0,4 s. Por eso la
función espera a Helsinki hasta 10 s (y el navegador, 15 s antes de ir a Helsinki por su cuenta).
Como reserva vale; como almacén principal, no. Queda como pendiente volver a medirlo (abajo).

**Si la caída dura horas** la web sigue con los últimos datos publicados (la recogida publica en
Núremberg); `docs/operacion.md` explica cómo cambiar los papeles de los dos almacenes con un PR para
que los datos nuevos lleguen igual.

### La copia de Helsinki

- **Mapa de fondo**: copiado una vez desde el servidor, de Núremberg a Helsinki, por partes de 128
  MiB y comprobando la huella SHA-256 mientras subía (la de siempre, `393c9a0d…11c98`): 42 minutos,
  490 MB de memoria como trabajo de sesión.
- **Lo demás** (662 objetos, unos 130 MB): la primera pasada copió 660 en 7,8 minutos; un PUT dio
  504 en Helsinki y lo copió la pasada siguiente. Después, una pasada sin cambios tarda menos de un
  segundo. Los dos manifiestos de los datos publicados, idénticos.
- **Al día solo**: unidad `eodi-reserva` cada 2 minutos y la recogida justo después de publicar
  (con un tope de 90 s para no retrasarla: un PUT colgado lo termina la pasada siguiente). Copia lo
  nuevo o cambiado con sus cabeceras, el manifiesto el último; borra lo retirado solo si el
  listado de Núremberg salió entero (nunca las versiones ni el historial).
- **Vigilancia**: `salud.json` lleva `copias.reserva_web`; si pasan 30 minutos sin estar al día,
  abre la incidencia.
- **Coste: 0 €.** El precio base del almacenamiento de objetos de Hetzner es por cuenta e incluye
  1 TB: con la copia se ocupan unos 57 GB.

### Consumo del plan de Vercel

El token nuevo, del equipo, no puede leer la facturación (la API responde «Plan not found» y la
línea de órdenes «User not found»), así que el consumo se estima con lo medido:

- **Transferencia**: una visita nueva baja 1,68 MB, de ellos 0,45 MB del almacén, que antes no
  pasaban por Vercel. El plan incluye 1 TB al mes: unas 600 000 visitas nuevas.
- **Peticiones**: 37 por visita (antes 27). El plan incluye 10 millones al mes: unas 270 000
  visitas nuevas.
- **Función**: solo trabaja cuando la caché no tiene el trozo; en la prueba de carga, 42 veces en
  620 visitas simuladas (6 200 peticiones del almacén).
- En los últimos 30 días (blindaje, 7 de octubre): 74 217 peticiones y 5,5 GB. **Con el tráfico de
  hoy, 0 € de más.** Por encima de lo incluido, Vercel cobraría unos 2 USD por millón de peticiones
  y 0,15 USD por GB: con un millón de visitas nuevas al mes, del orden de 150 USD. Es una decisión
  tuya (pendientes, abajo): Vercel deja fijar un tope de gasto.

### Fusión

PR #193, fusionado a las 15:51 UTC con las comprobaciones en verde y el ensayo completo de recogida
y exportación sobre una copia de la base real con código 0 (dos veces: el segundo, sobre el commit
final). Recogidas siguientes: la de las 16:17 terminó bien y publicó (aún con el guion anterior,
que se lee entero al empezar); la de las 17:17 terminó bien, publicó y dejó la copia de Helsinki al
día dentro de la propia recogida («copia de reserva al día», 5 objetos). Tras la fusión se instaló
en el servidor la unidad `eodi-reserva` (`instalar.sh`, sin parar nada) y se activó su
temporizador a las 16:42.

## El dominio

`droneobservatory.eu` está registrado en **Arsys** (Arsys Internet S.L.U., que también da el correo
del dominio); los servidores de nombres son los de Hetzner desde el 3 de octubre de 2026. El registro
de los `.eu` (EURid) no publica la fecha de caducidad ni el estado de la renovación: solo se ven en
el panel de Arsys. El dueño lo comprobó allí el 9 de octubre de 2026: **caduca el 27 de septiembre
de 2027 y tiene la renovación automática activada**. No hay que pagar ni activar nada ahora.

Lo único que conviene mirar antes de esa fecha, en el panel de Arsys (*Área de cliente* →
*Dominios* → `droneobservatory.eu`): que el método de pago guardado siga vigente en septiembre de
2027 (si caduca antes, la renovación automática falla) y que el correo de contacto del dominio sea
uno que se lee, porque allí llegan los avisos.

## Bloque 2. Créditos del autor

PR #192. Una sola fuente, `configuracion/licencia_datos.json`, con el autor («Dr. Lucas Alaniz
Pintos» / «Lucas Alaniz Pintos, PhD»), su ORCID enlazado (<https://orcid.org/0009-0008-5179-2534>),
el correo del aviso legal y la cita recomendada: «Alaniz Pintos, L. (2026). European Observatory of
Drone Incidents. Versión AAAA-MM. https://droneobservatory.eu. Licencia CC BY 4.0.» y, en inglés,
«… Version YYYY-MM. … Licence CC BY 4.0.».

- **En la web**, sin tapar el mapa: «Metodología y datos abiertos», la página de independencia, el
  aviso legal, el pie de todas las páginas de texto y la ayuda, en español y en inglés. La mención
  junto a las atribuciones del mapa de fondo **no se ha puesto**: a 360 px necesita 569 px y hay
  344; se cortaba en «Lucas Alaniz Pin…».
- **Dentro de cada fichero de datos** publicado y descargable (incidentes, sin ubicación, Ucrania,
  previsión y las descargas de la web): el miembro `licencia` lleva autor, ORCID, licencia, cita y
  dirección; cada objeto del almacén lleva además `x-amz-meta-autor` y `x-amz-meta-orcid`, y las
  descargas de `/datos/…` y `/almacen/…` la cabecera `Link` con `rel="author"`.
- **Versiones mensuales**: `metadatos.json` con autor y cita nueva desde la 2026-11. La 2026-10 ya
  publicada no cambia.
- **Datos estructurados** (schema.org): el autor como persona con su ORCID, en el conjunto de datos y
  en el sitio.
- **`llms.txt`** y **exportación semanal** (manifiesto con `creditos`, formato 1.8.0; el importador
  lee el manifiesto por claves y sigue igual).
- **Repositorio**: `CITATION.cff` en la raíz y el apartado de autoría y cita en el LEEME.

Fusión: PR #192, a las 16:43 UTC, con las comprobaciones en verde y el ensayo completo de recogida y
exportación sobre una copia de la base real con código 0 (la exportación de ensayo salió en formato
1.8.0 con `creditos`). Antes de fusionar se cambió en el esquema 1.8.0 una palabra copiada del 1.7.0
(«límites de movimiento» pasa a «cotas de movimiento»).

## Comprobación en producción

Del 9 de octubre, de 15:52 a 16:55 UTC:

- **Mapa** en un navegador real, en 360×800, 390×844, 412×915 y escritorio: entero y con todas las
  peticiones del almacén servidas por la web (10 a 12 por visita, ninguna directa a Hetzner, ningún
  error); mapa listo en 1,6 a 3,0 s. Capturas revisadas una a una: nada nuevo encima del mapa, y
  abrir y cerrar la ayuda y la metodología no lo mueve.
- **Créditos**: «Autoría» (autor, ORCID enlazado y contacto) al final de la ayuda y, con la cita
  recomendada, en «Metodología y datos abiertos», a 360 px y en escritorio; la cita de la versión
  2026-10 sigue la de siempre.
- **Páginas de texto sin ejecutar código** (`/metodologia`, `/independencia`, `/aviso-legal`,
  `/ayuda`, `/incidentes`, `/paises/pl` y sus versiones en inglés): todas 200, con el autor y el
  ORCID en el pie; la cita en metodología, independencia, aviso legal y ayuda; el autor como
  persona con su ORCID en los datos estructurados de la portada (sitio) y de metodología (conjunto
  de datos).
- **Ficheros descargados** (`/datos/incidentes.geojson`, `ucrania.json`, `prevision.json`,
  `incidentes_sin_ubicacion.json`): el miembro `licencia` con CC BY 4.0, el autor con su ORCID y
  la cita «Alaniz Pintos, L. (2026). European Observatory of Drone Incidents. Versión 2026-10…»;
  los CSV con la cabecera `Link` de licencia y autor. `llms.txt` con autor y cita en los dos
  idiomas.
- **Almacén principal caído**: probado en la vista previa (arriba).
- **Incidentes publicados**: 442 antes y después de cada fusión.
- **Vigilancia**: `salud.json` sin problemas y sin incidencias abiertas; `copias.reserva_web` al
  día.
- **Recogidas tras las fusiones**: 16:17 (tras #193) y 17:17 (tras #192) correctas y publicadas;
  la de las 18:17 también, con la copia de Helsinki al día dentro de la recogida. Tras la de las 17:17, los ficheros publicados llevan
  `x-amz-meta-autor` y `x-amz-meta-orcid` en Núremberg y en Helsinki.

## Pendientes, con su arreglo

1. **El consumo del plan de Vercel no se puede leer con el token del equipo.** Arreglo: mirarlo en
   Vercel → *Usage* a final de mes (o crear un token de la cuenta con lectura de la facturación y
   dejarlo en `%USERPROFILE%\.eodi\`); y decidir si se fija un tope de gasto en *Settings* →
   *Billing* → *Spend Management* (con un tope, Vercel pausa los proyectos al llegar; sin él, cobra
   lo que pase de lo incluido).
2. **Helsinki lee más lento en frío que Núremberg** (mediana 0,49 s frente a 0,22 s). Arreglo:
   volver a medirlo dentro de una semana, con 40 trozos al azar pedidos con Range a cada almacén
   como en «Prueba de caída»; si sigue así,
   volver a subir el mapa de fondo con `servidor/preparar_almacen.py --reserva --desde-principal
   --forzar` (otra subida queda en otro sitio del almacén) y medir otra vez.
3. **Con una caída larga de Núremberg, los datos nuevos no llegan a la web** (la recogida publica
   allí). Arreglo: el cambio de papeles con un PR, descrito en `docs/operacion.md`.
