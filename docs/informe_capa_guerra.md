# Informe: capa de guerra con lugar concreto en los dos sentidos

Fecha: 1 de octubre de 2026. Pull request: #37 (código, fusionado como `c178acc`) y este
informe. En AEGIS, PR #44 (documentación de los ficheros nuevos de la exportación).

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
dos ataques con solo dos focos (Volgogrado, 10-02-2026; Ilski, 31-12-2025).

## 6. Esquema, exportación y web

- Esquema 1.4.0 (menor): `impacto_guerra` y `restriccion_aeropuerto` nuevos;
  `ataque_ucrania.restricciones_aeropuertos` y `fuente.autoridad_ocupacion`;
  `foco_termico.linea_base.emplazamiento`.
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
- `servidor/guerra_reproceso.sh lote` reprocesa todo y lanza el lote histórico del extractor
  cuando termina el histórico.
