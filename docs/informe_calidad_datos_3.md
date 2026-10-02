# Calidad de los datos, tercera parte

European Observatory of Drone Incidents, 2 de octubre de 2026. Las horas son UTC. Continúa
[`informe_calidad_datos_2.md`](informe_calidad_datos_2.md). Cambios: PR #51 (reglas, esquema
1.6.0, formato de exportación 1.2.0, búsqueda dirigida, línea de tiempo), PR #54 y PR #55
(dos defectos de la fusión vistos con los datos reales) y, en AEGIS, PR #46 (importador y
documentación).

## 0. Resumen

| | Antes | Después |
| --- | ---: | ---: |
| Incidentes que sirve droneobservatory.eu | 383 | 466 |
| Activos en la base | 382 | 466 |
| Fechas de inicio con el día escrito por una fuente, una autoridad o un parte | 193 (51 %) | 274 (59 %) |
| Fechas que eran de publicación (declaradas como «día» o con un día que la frase no escribe) | 189 | 191, declaradas `aproximada` |
| Sucesos de la lista de Wikipedia «2025 European drone sightings» encontrados | 20 de 25 | 24 de 25 |
| Nivel de detalle A / B / C / D | 0 / 3 / 143 / 236 | 1 / 6 / 186 / 273 |
| Encuentros de UK Airprox enlazados con un incidente | 0 | 1 |
| Gasto del extractor (modo `calidad`, tope 2 USD) | — | 0,692 USD |

## 1. Fechas de los incidentes

### 1.1 De dónde salía la fecha

Medido sobre los 382 incidentes activos de la base del 2 de octubre a las 08:00, antes de
cambiar nada (`proceso/fechas.py` aplicado en modo lectura):

| Origen de la fecha de inicio | Incidentes | Precisión declarada |
| --- | ---: | --- |
| Ficha con el día explícito en la frase («22 de septiembre», «22.09.») | 43 | minuto, hora o día |
| Ficha con el día relativo a la publicación («anoche», «el lunes», «am Donnerstagabend») | 147 | minuto, hora o día |
| Ficha con un día que su frase no escribe (solo la hora, o nada) | 85 | minuto 21, hora 9, día 55 |
| Sin fecha en la ficha: fecha del primer artículo, por defecto | 104 | **día** (sin declarar que era de publicación) |
| Documento oficial | 2 | día |
| Parte de la Fuerza Aérea de Ucrania | 1 | aproximada |

Por qué 104 fichas no daban fecha: 33 no la traían; 31 la traían pero se rechazaba por ser
«más de una semana antes del primer artículo» (noticias que vuelven sobre un suceso pasado: una
nota de diciembre sobre el cierre de Copenhague del 22 de septiembre quedaba fechada en
diciembre); 21, porque su frase no estaba literal en la fuente; 8, por ser «posterior al primer
artículo» de un candidato que juntaba dos noches; 7, porque solo daban el mes; 4, confianza
baja. En total, **189 de 382 (49 %) llevaban en la práctica la fecha de la noticia**.

### 1.2 Contraste con datos medidos y oficiales

- **Notas oficiales con hora** (5 incidentes con `detalle_oficial.inicio`): 4 en el mismo día;
  Aalborg (EODI-2025-00238) estaba un día desplazado (prensa 26/09 08:30, policía de Jutlandia
  del Norte 25/09 21:44).
- **Cierres medidos con tráfico aéreo** (6 incidentes): los 6 en el mismo día. Copenhague
  22/09 (EODI-2025-00154): 18:30 hora frente a 18:26 medido. Bruselas 4/11 (EODI-2025-00072) y
  Múnich 2/10 (EODI-2025-00277): solo el día, correcto (medido 18:45 y 21:15).
- **Fechas desplazadas** al aplicar las reglas nuevas, sobre los incidentes activos antes o
  después: 355 en el mismo día; 16 un día después; 6 un día antes; 1 dos antes; 1 tres antes;
  1 dos después; 1 seis después (una hora sin día cuya nota salió seis días después: queda como
  fecha de publicación aproximada); y **22 más de tres días antes**: noticias retrospectivas
  que recuperan su fecha real (EODI-2026-00012 y EODI-2026-00061, de junio y mayo de 2026,
  son el cierre de Copenhague del 22/09/2025; EODI-2025-00164, de abril, es RAF Lakenheath del
  22/11/2024; EODI-2026-00202, de agosto, el encuentro de un Virgin Atlantic cerca de Heathrow
  del 8 de junio).

### 1.3 Lo corregido

- **El día del suceso se comprueba con su frase** (`proceso/fechas.py`, léxico en
  `configuracion/fechas.json`: meses, días de la semana, expresiones relativas y de noche en 33
  idiomas y la zona horaria de cada país). Una fecha relativa se resuelve con la hora local del
  medio cuando publicó la nota: una nota de las 07:10 de Berlín que dice «heute Nacht» habla de
  la noche anterior. Si la frase escribe otro día que el de la ficha, se corrige al de la frase
  con su hora (el día siguiente solo vale de madrugada). Se buscan también las otras frases y
  el titular de la misma nota.
- **Una fecha sin día escrito no vale como día**: si ninguna frase lo escribe, el inicio es la
  fecha de publicación de la nota con precisión `aproximada` (se conserva la hora si la frase la
  daba), y `tiempo.origen_inicio` lo declara (`publicacion`, con el motivo). La regla ya existía
  para los documentos oficiales; ahora vale en todos los caminos.
- **Validación contra la propia nota**: el inicio se compara con la publicación de la fuente que
  lo dice, no con la primera del candidato; uno de más de una semana antes vale si su frase
  escribe el día. Los 31 inicios rechazados solo por la ventana se recuperan sin llamar al
  extractor (`validacion_ficha.recuperar_inicio`).
- **La fecha oficial manda** sobre la de prensa (`detalle.inicio_oficial`); si la autoridad solo
  da el día y la prensa da la hora de ese día, queda la hora con el día confirmado.
- **Reproceso**: por código para todas las fichas guardadas; el extractor solo para los
  candidatos nuevos o separados (sección 2). Cada cambio queda en el historial del incidente,
  con `origen_inicio` (fuente y motivo) en el documento.

Después: 274 fechas verificadas (77 explícitas, 191 relativas, 6 oficiales; un parte sin
`origen_inicio` porque su incidente no se rehace) y 191 de publicación declaradas
(`aproximada`). Precisión: aproximada 192, día 158, hora 75, minuto 41.

### 1.4 Efecto en los cruces que dependen de la fecha

| Cruce | Antes | Después |
| --- | --- | --- |
| Fusión | 97 fusiones vigentes | 184; la ventana se mide con la actividad del suceso (inicio y fin), no con la fecha de las noticias, en día local y con la madrugada como noche de la víspera; con la fecha de publicación, ese día o el anterior; queda el incidente ya publicado |
| UK Airprox | 0 encuentros enlazados | 1: UKAB-2026107 con EODI-2026-00202 (Heathrow, 8 de junio de 2026), cuya fecha real se recuperó |
| Tráfico aéreo medido | 144 incidentes evaluados, 6 cierres medidos | 223 evaluados, 10 cierres medidos (entre ellos Colonia/Bonn 5/11/2025 y Múnich 3/10); la evaluación sigue en las recogidas horarias (150 s por ejecución, incidentes primero) |
| Condiciones medidas | 351 evaluadas | 466 (todas las activas) |
| FIRMS | 1 detectado, 16 no detectados, 29 no evaluables | 1 / 16 / 35; una fecha de publicación abre la ventana a la víspera |

Las ventanas de tráfico, condiciones y FIRMS tratan ahora una fecha `aproximada` como la de
publicación: desde el comienzo de la víspera hasta la nota.

## 2. Incidentes que faltaban

| Suceso | Por qué no entró | Corrección (general) | Ahora |
| --- | --- | --- | --- |
| Múnich, 3/10/2025 | Se fundió con el del 2/10 en el candidato: las noticias del primer cierre siguieron todo el día 3, así que nunca pasaron 12 horas sin artículos (704 artículos en un candidato). La ficha mezcló las dos noches y su inicio se rechazó como «posterior al primer artículo» | Un titular de repetición («erneut», «wieder Drohnenalarm», «à nouveau», «again», en 28 idiomas) 18 horas o más después del inicio del candidato abre otro, que recibe las noticias siguientes del sitio; la fusión mide la actividad del suceso y un incidente con solo el día ya no hace de puente entre dos noches (PR #55) | EODI-2025-00116, 4/10 00:00 («in der Nacht»), cierre medido; el 2/10 es EODI-2025-00340 |
| Lieja, 4/11/2025 | El candidato de Lieja existía, pero sus titulares nombran Bruselas y Lieja y la ficha situó el suceso en Bruselas: se fundió en el de Bruselas | Un incidente por objetivo: si dos titulares o más nombran a la vez el objetivo del candidato y el que da la ficha (en cualquiera de sus nombres), el suceso de ese candidato es su objetivo | EODI-2025-00231 en el aeropuerto de Lieja (fecha de publicación, 4/11 20:30) |
| Sønderborg | Los titulares escriben «Sonderborg» o «Sönderborg» y el nomenclátor solo tenía «Sønderborg»: la «ø» no se normalizaba | Pliegue de ø, æ, œ, ß, ł, đ, ð, þ en la normalización | EODI-2025-00349 |
| Esbjerg | Su candidato existía (dos medios) pero nunca pasó por el extractor: el lote del histórico no llegó a él | Prioridad del extractor para los candidatos nunca extraídos con noticias de dos medios o más (instalación) o tres (localidad), en la recogida horaria y en el reproceso | EODI-2025-00383 |
| Skrydstrup | Como Esbjerg; ya extraído, la ficha sitúa el suceso en Aalborg, que los titulares nombran declinado («Aalborgu») | La regla del objetivo compartido no se cumple con un solo titular | **Sigue faltando**: queda declarado |
| Astillero de Kiel | Estaba (EODI-2025-00314) pero solo a nivel de región (Schleswig-Holstein), sin punto, y la comparación solo cuenta los que tienen punto | Afinado de región a localidad: la única localidad de la región que nombran las frases y los titulares («Werft in Kiel») | Punto en Kiel |
| Ørland | Estaba (EODI-2025-00086) sin situar: «kampflybasen på Ørlandet» no casaba (forma definida noruega; «kampflybase» no era palabra de tipo; Ørland es un aeropuerto en el nomenclátor) | Forma definida «-landet»; palabras de base aérea («kampflybase», «flystasjon», «flyvestation», «Fliegerhorst») también para los aeropuertos | EODI-2025-00341 en Ørland |

**Cobertura frente a Wikipedia**: 20 de 25 antes; 22 de 25 solo con las reglas (Kiel y
Ørland); **24 de 25** tras el extractor. Falta Skrydstrup (arriba).

### 2.1 Búsqueda dirigida

`recogida/busqueda_dirigida.py`: para cada anomalía candidata del tráfico aéreo (interrupción
sin incidente y sin mal tiempo) en un aeropuerto de cobertura alta, se leen los GKG de GDELT
de ese día y el siguiente y se buscan titulares con el nombre del aeropuerto o de su ciudad, en
cualquiera de sus nombres, y una palabra de dron; lo hallado entra como artículos del
aeropuerto por el flujo normal y sus candidatos van primero al extractor. También se miran los
documentos oficiales guardados. Temporizador propio (`eodi-busqueda`, minuto 2).

Aplicada a las anomalías candidatas con cobertura alta (169 al empezar, 216 al terminar: el
histórico de tráfico añade más): 57 días de GKG leídos en 3 h 44 min; **27 anomalías con
noticias**, 2796 titulares hallados (1220 nuevos o sin candidato), 26 candidatos, **9
incidentes**: 2 nuevos (EODI-2025-00322, Colonia/Bonn 5/11/2025, con cierre medido; y
EODI-2025-00323, Berlín 2/11/2025), 2 que completan sucesos ya buscados (Múnich 3/10 y Lieja
4/11) y 5 fundidos en incidentes existentes. Ningún documento oficial guardado casó. Las demás
anomalías siguen internas.

## 3. Nivel de detalle e indicadores

Nueva escala, por código (`exportacion/procedencia.py`): A, trayectoria, altura o velocidad del
dron medida u oficial; B, hora de minuto u hora y radio de 5 km o menos, y confirmación oficial
**o cierre medido en un aeropuerto de cobertura alta**; C, confirmado con origen oficial u
oficial citado; D, solo prensa o parte. Siete indicadores por incidente. Esquema 1.6.0
(`tiempo.origen_inicio`, `indicadores`, `lugar.geocodificacion` `frase_origen` y `oficial`),
formato de exportación 1.2.0 y vocabulario 1.2.0 (la sesión del motor de deducción subió
después a 1.7.0 / 1.3.0 sobre este cambio).

Calculado sobre exportaciones generadas con `exportacion.semanal.generar`:

| | Antes (regla y datos anteriores) | Regla nueva, datos anteriores | Después |
| --- | ---: | ---: | ---: |
| Activos | 382 | 382 | 466 |
| A | 0 | 0 | 1 |
| B | 3 | 5 | 6 |
| C | 143 | 142 | 186 |
| D | 236 | 235 | 273 |
| `tiene_cierre_medido` | — | 6 | 10 |
| `tiene_condiciones_medidas` | — | 229 | 304 |
| `tiene_respuesta_militar_observada` | — | 73 | 113 |
| `tiene_interferencia_gnss_medida` | — | 33 | 55 |
| `tiene_foco_termico` | — | 1 | 1 |
| `tiene_confirmacion_oficial_directa` | — | 5 | 6 |
| `fecha_del_suceso_verificada` | — | 5 | 275 |

El A es EODI-2026-00202: la altura del dron la da el encuentro de la UK Airprox Board enlazado.
AEGIS (PR #46): el importador resume los incidentes con cada indicador y por origen de la
fecha, y `docs/eodi.md` explica la escala y cuándo una fecha sirve para cruzar con datos
propios.

## 4. Ubicaciones imprecisas

De los 130 incidentes activos que solo llegaban a región o país al empezar: 7 se afinan con las
frases de origen y los titulares (`lugar.geocodificacion` `frase_origen`: Kiel, Isaccea, el
aeropuerto de Split…), 10 quedan fundidos o retirados y 113 siguen declarados sin punto (84 de
nivel país). La localidad que se llama como su región no cuenta («Tulcea» es casi siempre la
provincia) y un suceso de nivel país no se afina. Ningún documento oficial dio un punto para un
incidente sin punto. Con los incidentes nuevos, se publican 162 sin ubicación de 466.

## 5. Web, servidor y extractor

- **Línea de tiempo**: opaca en escritorio (color sólido del panel, el que ya usaba el
  teléfono). Fondo calculado antes en escritorio `rgba(9, 14, 25, 0.9)`, después
  `rgb(11, 17, 29)`; en los teléfonos de 360×800, 390×844 y 412×915 ya era opaca.
  Capturas: [antes](capturas/linea-tiempo-antes-escritorio.png) y
  [después](capturas/linea-tiempo-despues-escritorio.png) en escritorio, y las de los tres
  teléfonos (`capturas/linea-tiempo-{antes,despues}-<ancho>x<alto>.png`).
- **Capa Ucrania en producción**, vista normal: con el periodo completo dibuja las regiones
  rusas y ucranianas, los impactos y las marcas de foco
  ([capturas](capturas/ucrania-periodo-completo-escritorio.png),
  [zoom](capturas/ucrania-regiones-impactos-focos-escritorio.png)); «Ver todo» aparece al
  elegir un tramo y desaparece al pulsarlo ([captura](capturas/ucrania-tramo-ver-todo-escritorio.png)).
- **Regla de omitir build** de Vercel: omite con un commit sin cambios en `web/`,
  `publicacion/` ni `vercel.json` y construye con ellos (probada con commits reales de la rama).
- **FIRMS**: el error «foco_termico: 31 is greater than the maximum of 30» salió en las
  recogidas del 1 de octubre a las 20:24 y 21:25 y desapareció con el PR #44; desde las 22:21,
  cada ejecución horaria termina el cruce («focos térmicos: … evaluados»).
- **Extractor**: modo `calidad`, 0,692 USD de 2 en tres tandas (269 peticiones y 0,4729 USD;
  162 y 0,215; 2 y 0,0042). El primer lote se recortó por el peor caso de cada petición, como
  en las revisiones anteriores. Las recogidas horarias siguieron dentro de su límite diario.

## 6. Incidencias y lo que queda

- **needrestart reinició unidades en marcha.** Al reconstruir el servidor (`reconstruir.sh`,
  necesario por la unidad nueva), la actualización de paquetes disparó `needrestart`, que
  reinició `eodi-trafico.service` (el histórico de tráfico perdió cinco minutos de un día, que
  se volvió a procesar), la búsqueda dirigida y una unidad de prueba de la sesión del motor de
  deducción (se repitió y terminó bien), y se quedó esperando a esas unidades de tipo oneshot.
  Se cortó el cliente `systemctl` bloqueado. Arreglado en el PR #54: las unidades `eodi-` quedan
  excluidas (`/etc/needrestart/conf.d/50-eodi.conf`, puesto también en el servidor).
- **Dos defectos de la fusión vistos con los datos reales**, corregidos en los PR #54 (el
  destino no heredaba las afirmaciones de fuentes compartidas y la exportación semanal no
  validaba) y #55 (puente entre dos noches; notas de publicación que hacían dudosa una fusión
  clara).
- **Un reproceso murió por falta de memoria** (2,2 GB al cifrar la base, con el histórico de
  tráfico y la búsqueda dirigida en marcha); murió antes de subir la base y se repitió con la
  búsqueda parada. El reproceso no es parte de la recogida horaria.
- **Producción**: de 383 a 466. En el último paso bajó de 491 a 466 al fundir 25 duplicados:
  EODI-2025-00159, 00262, 00324, 00330, 00361, 00373, 00374, 00385, 00389 y EODI-2026-00092,
  00102, 00103, 00110, 00134, 00143, 00164, 00177, 00240, 00265, 00266, 00270, 00287, 00324,
  00342, 00347 (Galați 29/05/2026, el dron explosivo de Leipzig del 5/08/2026, la incursión en
  Polonia del 9-10/09/2025, Moldavia 30/09-1/10/2026, Berlín 31/10/2025, el portaaviones en
  Malmö…). Sus enlaces dejan de llevar a un incidente propio.
- **Pendiente**: Skrydstrup (la ficha da Aalborg); la evaluación de tráfico de los incidentes
  nuevos, que la recogida horaria completa en las próximas horas (Lieja 4/11 aún sin evaluar al
  cierre); las anomalías candidatas que deje el histórico de tráfico hasta el 6 de octubre las
  busca el temporizador nuevo.
