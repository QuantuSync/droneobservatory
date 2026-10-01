# Informe: capa de guerra con lugar concreto en los dos sentidos

Fecha: 1 y 2 de octubre de 2026. Pull requests: #37 (código, `c178acc`), #38 (orden del
histórico), #39 (partes diarios del frente), #40 (lote del histórico desde la recogida
horaria), #43 (reivindicaciones sin arma), #44 (máximo de días de la línea base de FIRMS), #46
(FIRMS en zonas que arden a diario y ataques FPV), #47 (comprobación de webs oficiales lentas)
y el de este informe. En AEGIS, PR #44 (documentación de los ficheros nuevos de la
exportación). El borrador de este informe entró por error en el commit de #43; el PR del
informe lo completa.

Hasta ahora la capa de guerra del European Observatory of Drone Incidents solo sabía cuántos
drones lanzaba cada parte y sobre qué regiones decía derribarlos. No sabía **dónde** caían.
Este cambio añade fuentes oficiales que nombran localidades e instalaciones, un nomenclátor
para situarlas, la comprobación con focos térmicos de NASA FIRMS en los dos sentidos y su
dibujo en la web.

## 1. Diagnóstico de la web en producción (antes de tocar nada)

Síntoma: con la capa Ucrania activa y el zoom entre Moscú, Riazán, Tula, Oriol y Briansk no se
dibujaba nada; solo las regiones de Ucrania coloreadas.

Lo que servía producción (`/datos/ucrania-resumen.json`, `/datos/ucrania.json` y
`/mapa/*.geojson`):

1. **Ninguna región rusa llegaba a la web.** `web/src/datos/derivar.ts` (`resumirUcrania`)
   filtraba las regiones por el prefijo `UA-`: los ataques UA→RU (3.506 en la base) existían en
   `publicacion/ucrania.json`, con sus regiones `RU-…`, pero el resumen que lee el mapa las
   descartaba. El resumen de producción solo tenía códigos `UA-`.
2. **No había geometría de Rusia.** La web solo tenía `ucrania-regiones.geojson`; aunque el
   resumen hubiera traído las regiones rusas, no había polígonos donde pintarlas.
3. **El clic las rechazaba.** `App.tsx` (`abrirRegion`) solo abría fichas de códigos `UA-`.
4. **Las marcas de foco de la capa estaban vacías.** La lista `focos` del resumen de producción
   no tenía ningún elemento: la única detección de FIRMS publicada era la del incidente
   EODI-2026-00200 (Galați), que pertenece a la capa de **incidentes**, no a la de Ucrania. Los
   ataques UA→RU tenían 1 evaluación «detectado», 16 «no detectado» y 76 «no evaluable», y
   ninguna se publicaba en la capa.
5. **Cómo se hicieron las capturas de FIRMS.** `docs/capturas/firms-foco-escritorio.png` y
   `firms-foco-390x844.png` se tomaron en la capa **Incidentes** con la ficha del incidente de
   Galați abierta. Eran correctas para ese incidente, pero no decían nada de la capa Ucrania: en
   la vista normal de esa capa no había marca que ver.

Arreglo (en #37):

- `resumirUcrania` conserva todos los códigos de región; la web valida `UA-` y `RU-`.
- Geometría nueva `web/public/mapa/rusia-regiones.geojson` (62 regiones de la Rusia europea,
  189 KB, de Natural Earth simplificadas a 0,02°) y nombres en español e inglés.
- Las regiones rusas se rellenan en **grises neutros** por intensidad de ataques en el periodo
  elegido, con borde discontinuo; las ucranianas siguen en su color. Así se distinguen sin usar
  colores fuera de la paleta de estados.
- Impactos con lugar en los dos sentidos: puntos pequeños (relleno: fuente oficial; anillo:
  reivindicación de parte), agrupados con contador al alejar (hasta el zoom 7), con la marca
  de foco térmico encima cuando FIRMS lo confirma. Respetan la línea de tiempo; «Ver todo»
  muestra todos.
- Ficha de región rusa: ataques en el periodo, derribos, último ataque, la fuente con su
  puntuación (por ejemplo «Cifras de Минобороны России D3 · reivindicación de parte») y la
  lista de impactos. Ficha de impacto: lugar, tipo de objetivo, fecha, fuente con puntuación
  y enlace, «reivindicación de parte» cuando lo es, y la comprobación de FIRMS.

## 2. Fuentes

Todas se leen en el servidor (nunca en Vercel ni en GitHub Actions) desde la vista pública de
Telegram, con el identificador `EODI-bot/1.0 (+https://droneobservatory.eu)`, pausas entre
peticiones y comprobación de que lo descargado es el canal y no una página de bloqueo. En cada
lectura se verifica que el canal es el oficial: título esperado, insignia de verificación si
la tiene, enlace del canal a su web oficial y, cuando la web oficial se puede abrir desde el
servidor, que la web enlace al canal (se comprueba una vez al día; vale 30 días). Si la
verificación falla, el canal no se lee esa vez y `estado.json` lo dice.

### 2.1 Administraciones militares regionales de Ucrania (fiabilidad B, origen oficial)

Se enlazan al ataque nocturno y a la región del canal; nunca a incidentes europeos.

| Región | Canal | Cómo se verificó |
| --- | --- | --- |
| Vinnytsia (UA-05) | VinnytsiaODA | insignia, web enlaza |
| Dnipropetrovsk (UA-12) | adm_dp | insignia; la web no carga desde el servidor, enlace comprobado en el archivo de Internet |
| Donetsk (UA-14) | DonetskaODA | descripción enlaza dn.gov.ua, web enlaza |
| Zakarpattia (UA-21) | zoda_inform | web enlaza |
| Zaporizhzhia (UA-23) | zoda_gov_ua | web enlaza |
| Ivano-Frankivsk (UA-26) | IF_ODA | web enlaza |
| Kyiv (región, UA-32) | kyivoda | insignia, koda.gov.ua |
| Kirovohrad (UA-35) | kirovohradskaODA | web enlaza |
| Luhansk (UA-09) | luhanskaVTSA | archivo de Internet |
| Lviv (UA-46) | people_of_action | insignia, archivo de Internet |
| Odesa (UA-51) | odesaoda | título y descripción; web no carga desde el servidor |
| Poltava (UA-53) | poltavskaoda | insignia |
| Rivne (UA-56) | ODA_RV | web enlaza |
| Sumy (UA-59) | Sumy_news_ODA | web enlaza |
| Járkov (UA-63) | kharkivoda y synegubov (misma institución) | web enlaza |
| Jersón (UA-65) | khersonskaODA | web enlaza (el título mezcla una «c» latina: se compara un fragmento) |
| Jmelnytsky (UA-68) | khmelnytskaODA | web enlaza |
| Cherkasy (UA-71) | cherkaskaODA | archivo de Internet |
| Chernivtsí (UA-77) | chernivetskaODA | web enlaza |
| Kyiv (ciudad, UA-30) | VA_Kyiv | archivo de Internet |

Descartados: Volyn, Zhytomyr (`zt_gov_ua` es el consejo regional, no la administración
militar), Mykolaiv y Ternópil, porque ni su web oficial enlaza un canal ni el canal enlaza la
web oficial: no se puede probar que sean oficiales.

### 2.2 Estado Mayor de Ucrania (parte, credibilidad C)

`GeneralStaffZSU`: insignia y descripción que enlaza sus cuentas oficiales (zsu.gov.ua está
tras una protección anti-bots y no enlaza el canal). Es **reivindicación de parte**, simétrica
del Ministerio de Defensa ruso (D3): su credibilidad solo sube con una fuente independiente o
con un foco de FIRMS. Solo se registra cuando el mensaje dice que el medio fueron drones
propios («Сили безпілотних систем», «із застосуванням ударних БпЛА»…); si el arma no consta,
no se registra (las listas de objetivos alcanzados sin arma mezclan misiles y artillería).
Contenido con licencia CC BY 4.0.

### 2.3 Gobernadores rusos (parte, C)

Con lugar concreto (localidad o instalación) y verificación oficial: Briansk (`E_V_Kovalchuk` y
el canal del gobierno regional), Moscú (`mos_sobyanin`, insignia), Leningrado
(`drozdenko_au_lo`), Smolensk (`anohin67`), Nizhni Nóvgorod (`glebnikitin_nn`), Uliánovsk,
Daguestán (`Glava_RD`), Krasnodar (`admkrai`), Samara (`SamarOblast`), Perm (`mahonin59`),
Osetia del Norte (`alania_gov`), Oriol (`Klychkov_Andrey`) y Tambov (`tmbcan`). Los seis
últimos se verificaron con el archivo de Internet porque sus webs no abren desde el servidor.

Descartados: Bélgorod (`vvgladkov` ya no es el canal del gobernador en ejercicio); Vorónezh
(`gusev_36`), el gobernador y el centro operativo de Krasnodar (`kondratyevvi`,
`opershtab23`), la región de Moscú (`vorobiev_live`), Sarátov (`busargin_r`) y Bashkortostán
(`radiyhabirov`), porque ni su web oficial ni una copia en el archivo de Internet enlazan el
canal; y las regiones cuya web oficial no abre desde fuera de Rusia sin copia archivada (no se
pudo saber cuál es su canal oficial). Krasnodar queda cubierta por la administración regional
(`admkrai`).
No se encontró ningún canal de autoridades de ocupación con lugar concreto que se pudiera
verificar: el campo `autoridad_ocupacion` existe y se marcaría, pero hoy no hay ninguno.

### 2.4 Rosaviatsia (serie interna)

`favt_info`, canal oficial de la Agencia Federal de Transporte Aéreo (la web favt.gov.ru enlaza
`favt_ru`, que remite a él). Publica «ВВЕДЕНЫ/СНЯТЫ ограничения» por aeropuerto, sin hora en el
texto y sin mencionar drones. Se guarda como serie **interna**: aeropuerto, inicio (hora del
mensaje), fin (respuesta que la levanta o el siguiente mensaje del aeropuerto, como mucho 48
horas), horas y el ataque UA→RU de esa noche. No crea incidentes y no se publica; va a la
exportación para AEGIS (`restricciones_aeropuertos.jsonl`) y a cada ataque
(`restricciones_aeropuertos`, interno).

### 2.5 Línea del frente

No se usa. DeepStateMap limita su API a entidades voluntarias o de defensa y prohíbe
redistribuir; el ISW prohíbe el uso sin permiso escrito. No hay otra fuente legible por
máquina con condiciones que lo permitan.

## 3. Nomenclátor

`configuracion/nomenclator_guerra.json.gz` (6,5 MB), generado por
`recogida/nomenclator_guerra.py`:

- Ucrania: KATOTTH (codificador oficial) con el punto de OSM (etiqueta `katotth`) o de
  GeoNames; 29.627 de 29.703 localidades situadas. Los territorios ocupados llevan siempre su
  código ISO ucraniano.
- Rusia europea: 139.799 localidades de GeoNames con su nombre ruso.
- 18.393 instalaciones de OSM en los dos países: 43 refinerías, 622 depósitos de combustible,
  1.346 centrales, 940 subestaciones, 1.450 aeródromos, 84 puertos, 6.260 instalaciones
  ferroviarias, 7.561 industriales y 87 militares.
- Formas declinadas en ucraniano y ruso («у Броварах», «в Перми») y transcripción latina:
  1.273.372 formas, de las que 198.438 (15,6 %) son ambiguas. Una forma ambigua se resuelve
  por la región del canal, por la comunidad o el distrito citados, o se queda sin resolver
  (va al extractor o no se registra). Nunca hay alias iguales a un país, una región o una
  institución, y 2.693 palabras comunes («затоки», «поля»…) solo cuentan como lugar con un
  tipo delante («с. Затоки»).
- Cada punto se comprueba dentro de su región (con 10 km de margen).

## 4. Lectura: código primero, extractor después

`proceso/mensajes_guerra.py` lee cada mensaje: arma (solo drones; los misiles de los mismos
mensajes no se registran), impacto o derribo, víctimas, noche, tipo de objetivo y lugar, con
plantillas y el nomenclátor. Lo que no consta queda vacío. Solo va al extractor lo que el
código no resuelve, con el texto mínimo, esquema JSON, la frase de origen obligatoria y
confianza; lo que devuelve se vuelve a resolver contra el nomenclátor. Límite propio de 0,20
USD al día y un lote único de 5 USD para el histórico desde el 1 de enero de 2025, con
prioridad para energía, combustible e industria.

Reglas que salieron de leer los mensajes reales del servidor:

- **Partes diarios.** Las administraciones (sobre todo Zaporiyia) publican cada mañana la
  lista de localidades atacadas en 24 horas, casi siempre con FPV en la línea del frente. Se
  guardan con `parte_diario`, sin enlazar a un ataque nocturno, se publican en `ucrania.json`
  y se exportan, pero **no se dibujan** (eran 5.186 de los primeros 5.711 impactos RU→UA y
  tapaban el resto) y no se cruzan con FIRMS.
- **Estado Mayor.** Solo se registra si el mensaje dice que el medio fueron drones propios
  («Сили безпілотних систем», «із застосуванням ударних БпЛА»…). «Ударними БпЛА» detrás de
  «управління», «керування», «з», «із» o «проти» es el objetivo, no el arma (#43). De 2.410
  mensajes del Estado Mayor desde enero de 2025 salen 21 impactos: la mayoría de sus mensajes
  son partes del frente sin arma o sin lugar.
- **Drones como objetivo** («місце запуску ударних БпЛА») no cuentan como arma; los lugares
  de lanzamiento («із напрямків…») no son lugares alcanzados; un mensaje que vuelve sobre un
  ataque pasado («відвідав», «проверил как…») no crea otro impacto.
- **Ciudad frente a aldeas homónimas**: con el mismo nombre oficial, gana la ciudad; los
  nombres de lugar se tapan antes de deducir el tipo de objetivo («Залізничне» no es un
  ferrocarril).

El histórico se recorre en este orden: Estado Mayor, gobernadores, Rosaviatsia y después las
administraciones regionales (#38), para tener cuanto antes impactos situados en Rusia.

## 5. FIRMS en los dos sentidos y Kirishi

Los focos térmicos se evalúan ahora también sobre cada impacto con lugar (los dos sentidos) y
la credibilidad del impacto sube cuando aparece un foco nuevo en su sitio.

**Falso positivo de Kirishi.** La refinería tiene una antorcha permanente a 2,6–3,0 km del
centro: un píxel por pasada, de hasta 4,4 MW, más frecuente en invierno. La línea base de 7
días no la absorbía. Se añadió una **línea base por emplazamiento** de 365 días: un foco no
cuenta si su píxel aparece en el 90 % de las noches de referencia del sitio, salvo que en la
misma pasada haya 3 focos o más (un incendio de verdad).

Validación con 12 refinerías rusas (Kirishi, Volgogrado, Sarátov, Kstovo, Novokuibyshevsk,
Kuibyshev, Yaroslavl, Moscú, Tuapsé, Afipski, Ilski y Slaviansk), 104 ataques documentados y
36 noches de control sin ataque, radio de 3 km, noches de 18:00 a 08:00 hora de Moscú:

| | Regla anterior | Con línea base por emplazamiento |
| --- | --- | --- |
| Ataques detectados | 28 de 104 | 26 de 104 |
| Falsos positivos en noches de control | 1 de 36 (Kirishi, 26-07-2025) | 0 de 36 |
| Noches positivas en total (7.596) | 131 | 84 |
| … lejos de cualquier suceso conocido | 76 | 33 |

En Kirishi solo quedan los ataques reales (13-09-2025, 25-03-2026 y 04-05-2026). Se pierden
dos ataques con solo dos focos (Volgogrado, 10-02-2026; Ilski, 31-12-2025). En producción, el
impacto del Estado Mayor «Уражено Кірішський НПЗ» del 13-09-2025 sale «detectado» con la
regla nueva.

**Fuego habitual y frente (#46).** Con los primeros impactos situados, FIRMS dio «detectado» en
Zaporiyia con 574 y 673 focos en los 30 días anteriores dentro del radio (fuego cada día) y en
ataques FPV de Pokrovsk y Kostiantynivka. Ahí un foco nuevo no dice nada del dron. Ahora:

- un radio que ardió 15 o más de los 30 días de la base, repartido en 15 o más celdas de 0,01°,
  queda «no evaluable» (motivo `fuego_frecuente`); las antorchas caen en uno a tres píxeles y
  no llegan;
- los impactos con FPV en la frase, como los partes diarios, no se cruzan con FIRMS;
- las detecciones se rehacen en cada recogida (son pocas), para que les llegue cualquier
  cambio de regla.

Con las 12 refinerías: 25 de 104 ataques (antes 26) y 0 de 36 controles; la única pérdida es
Volgogrado 18-08-2025, cuando la refinería aún ardía del ataque del 13 de agosto (172 focos en
la base), un caso que FIRMS no puede separar.

**Fallo corregido (#44).** La recogida de las 21:17 del 1 de octubre dejó sin cruce de FIRMS a
todo (también a los incidentes): `linea_base.dias` llegaba a 31 porque los 30 días empiezan a
la hora del inicio y tocan 31 fechas, y el esquema ponía 30 como máximo. El máximo pasa a 31.

## 6. Esquema, exportación y web

- Esquema 1.4.0 (menor): `impacto_guerra` y `restriccion_aeropuerto` nuevos;
  `ataque_ucrania.restricciones_aeropuertos` y `fuente.autoridad_ocupacion`;
  `foco_termico.linea_base.emplazamiento`. Después otra sesión subió a 1.5.0; #44 y #46 solo
  amplían lo válido en 1.5.0 (máximo 31 y motivo `fuego_frecuente`), así que lo ya escrito
  sigue valiendo.
- Exportación para AEGIS 1.1.0 (la misma versión que estrenan los ficheros de detalle de #35;
  aún no se ha publicado ninguna 1.1.0): `guerra_impactos.jsonl`, `guerra_mensajes.jsonl` y
  `restricciones_aeropuertos.jsonl`, con `procedencia` (`metodo` `codigo` o `extractor`), y los
  impactos en `afirmaciones.jsonl`. El importador de AEGIS es genérico (copia lo que lista el
  manifiesto) y no cambia.
- Web pública: los impactos con lugar, sus fuentes y la comprobación de FIRMS. Rosaviatsia y
  los mensajes leídos no se publican.

## 7. Servidor

- `eodi-guerra.timer` (minuto 50, cerrojo propio `guerra.lock`, tope 55 minutos): lee los
  canales nuevos y avanza el histórico 40 minutos por hora, reanudable.
- La recogida horaria (minuto 17) procesa lo leído, con un tope de 240 s, y aplica FIRMS.
- `estado.json` lista cuatro fuentes nuevas (`ova_ua`, `estado_mayor_ua`, `gobernadores_ru`,
  `rosaviatsia`); un fallo suyo no rompe la recogida horaria.
- El lote del histórico del extractor lo envía la propia recogida horaria, una sola vez,
  cuando el histórico de todos los canales está completo y todo lo leído procesado, y lo
  incorpora una recogida posterior (#40). Antes, el script esperaba al lote hasta 24 horas con
  el cerrojo de la recogida tomado.
- `servidor/guerra_reproceso.sh` relee todo tras un cambio del analizador o del nomenclátor
  (la recogida horaria solo relee las últimas 12 horas). Se lanzó a las 22:31 UTC del 1 de
  octubre tras #43: 12.427 mensajes en 3 min 55 s y 1,6 GB.
- Rosaviatsia no se leyó ninguna vez: favt.gov.ru deja colgada la primera conexión (25 s) y
  responde en menos de un segundo a la siguiente, y la comprobación hacía dos intentos de
  20 s. Ahora son intentos de 10 s con tres reintentos (#47).

**Consumo.** Recogida horaria antes (1 de octubre, 10:00–18:22): 4–6 minutos y 1,1–1,6 GB de
pico. Después: la primera con la capa (7.229 mensajes por procesar) tardó 18 minutos y 2 GB;
las siguientes, 12–13 minutos y 1,6–2 GB, de los que la capa de guerra son unos 15 s más la
carga del nomenclátor (unos 480 MB, que se liberan al terminar el paso). El resto del aumento
es el cruce de FIRMS vaciando los impactos pendientes (unos 3 minutos por pasada mientras
quedan) y la medición del tráfico aéreo de #33, fusionada esa misma tarde. El servidor tiene
3,8 GB. El lector (`eodi-guerra.service`) usa 40 MB y unos 20 s de CPU por hora. Disco: 26 MB
en `datos/guerra` a mitad del histórico. Como la recogida publica ahora hacia el minuto 29,
`docs/fusiones.md` amplía la ventana sin fusiones del minuto 12–30 al 12–40.

## 8. Resultados

Cifras de la base a las 23:30 UTC del 1 de octubre, con el histórico en 13 de 37 canales
(Estado Mayor, Briansk, Leningrado, Moscú, Nizhni Nóvgorod, Smolensk y seis administraciones
regionales completos).

| | Antes | Después |
| --- | --- | --- |
| Impactos con lugar RU→UA | 0 | 5.711 (525 sin contar los partes diarios; 430 enlazados a un ataque) |
| Impactos con lugar UA→RU | 0 | 427 (373 enlazados a un ataque; 12 en instalaciones) |
| Regiones rusas en la web | 0 (la web descartaba los códigos `RU-`) | 58 |
| Evaluaciones de FIRMS «detectado» | 1 (incidente de Galați) | 13: 6 RU→UA, 6 UA→RU y Galați |
| Impactos de guerra con credibilidad subida por un foco | — | 9 (3 RU→UA, 6 UA→RU) |
| Gasto del extractor de guerra | — | 0,0085 USD (diario); lote del histórico aún sin enviar |
| Restricciones de Rosaviatsia | — | 0 (ver sección 7) |

UA→RU por fuente: Gobierno de la región de Briansk 248, gobernador de Briansk 92, gobernador
de Leningrado 42, Estado Mayor ucraniano 21, alcalde de Moscú 18, gobernador de Nizhni
Nóvgorod 5, gobernador de Smolensk 1. Por región: Briansk 340, Leningrado 43, Moscú 18, Nizhni
Nóvgorod 5, Krasnodar 4 y otras 17 entre Sarátov, Tambov, Lípetsk, Samara, Kursk, región de
Moscú y territorios ocupados de Ucrania (con su código ucraniano).

FIRMS «detectado» en impactos de guerra: Kirishi (refinería, 13-09-2025), Briansk, Zernovo,
Brajlov, Sevsk y Zelenogrado en el sentido UA→RU; Nikopol, Pavlohrad, Ivano-Frankivsk y
Zaporiyia en el RU→UA. Las de Pokrovsk y Kostiantynivka (FPV) quedan guardadas pero ya no se
publican ni suben la credibilidad, y la de Zaporiyia se rehace con la regla de fuego habitual.
Un foco es un indicio físico, no una confirmación: Zelenogrado (28-05-2025, «sin daños
graves») tiene un foco a menos de 7 km sin línea base, que puede ser otro fuego.

## 9. Comprobación en producción

Capturas de droneobservatory.eu en la vista normal, sin ningún truco: capa Ucrania y «Ver
todo» en la línea de tiempo, tomadas el 1 de octubre poco después de la
publicación de las 23:30.

- `capturas/guerra-ver-todo-escritorio.png` y `guerra-ver-todo-390x844.png`: vista inicial.
  Regiones rusas en grises por intensidad, con borde discontinuo; Ucrania en su color; grupos
  de impactos con su número.
- `capturas/guerra-rusia-escritorio.png`: zoom entre Moscú, Riazán, Tula, Oriol y Briansk.
  Briansk y Kursk en el gris más claro (más ataques en el periodo), grupos de impactos en
  Briansk (137, 74, 47, 22…) y en Moscú (19), y marcas de foco (punto claro) junto a los
  impactos con foco.
- `capturas/guerra-rusia-390x844.png`: lo mismo en móvil.
- `capturas/guerra-ucrania-escritorio.png` y `guerra-ucrania-390x844.png`: Ucrania con sus
  grupos (Zaporiyia, Dnipró, Donetsk, Járkov) y la frontera rusa.
- `capturas/guerra-ficha-impacto-escritorio.png`: ficha de un impacto en Почеп (Briansk):
  «Reivindicación de parte», lugar, tipo de objetivo «la fuente no lo dice», fecha, ataque de
  esa noche, credibilidad 3 y sus dos fuentes con su puntuación C3 y enlace.
- `capturas/guerra-ficha-region-rusa-escritorio.png`: ficha de Kursk: ataques en el periodo
  según el Ministerio de Defensa ruso, «Cifras de Минобороны России D3 · reivindicación de
  parte», derribos, impactos con lugar y partes que la citan.

Las capturas se hicieron con Playwright: en escritorio, arrastrando el mapa y con la rueda;
en móvil, con el teclado del mapa, porque el arrastre táctil emulado no lo mueve. Las de
`firms-foco-*.png` de la sesión de FIRMS siguen siendo del incidente de Galați en la capa
Incidentes (sección 1).

## 10. Pendiente

- **Histórico**: quedan 24 canales (8 gobernadores, Rosaviatsia, la administración de la
  ciudad de Kyiv y 14 administraciones regionales). A unas 40 minutos por hora tardará
  alrededor de un día. Cuando termine, la recogida horaria enviará sola el lote del extractor
  (tope de 5 USD) y lo incorporará; las cifras de la sección 8 crecerán sin más intervención.
- **Palabras corrientes** (`configuracion/palabras_comunes_guerra.json`): conviene regenerarlas
  con el histórico completo.
- **Precisión del Estado Mayor**: algunas frases siguen sin decir el arma del ataque concreto
  aunque el mensaje hable de drones propios en otra parte; son reivindicación de parte (C3) y
  así se marcan.
- **Autoridades de ocupación**: el campo existe pero no hay ningún canal verificado.
- **Rosaviatsia**: con #47 la primera pasada (23:50 UTC del 1 de octubre) ya no se cuelga, pero
  favt.gov.ru respondió 502 a los cuatro intentos, así que el canal sigue sin verificar y sin
  leer. El lector lo reintenta cada hora; hasta la primera comprobación correcta no hay serie
  de restricciones. Si la web sigue fallando, la alternativa es aceptar una copia reciente del
  archivo de Internet como prueba de que la web enlaza el canal, como ya se hace con otras webs
  oficiales que no abren desde el servidor.
