# Informe: auditoría, Ministerio de Defensa ruso y GDELT

Tercer PR del Observatorio Europeo de Incidentes con Drones (EODI): auditoría
de cobertura de la Fuerza Aérea de Ucrania, arreglos pendientes, segunda
fuente de la capa de guerra (Ministerio de Defensa ruso, sentido UA_RU) y
recogida de noticias europeas en GDELT con su filtro, deduplicado y
agrupación provisional. No se publica ningún incidente europeo: eso va con el
extractor, en el siguiente PR.

## 1. Auditoría de cobertura de la Fuerza Aérea

Hecha solo con la caché local (`data/cache/kpszsu`, 3916 páginas, 78 106
publicaciones), sin descargar de nuevo. Para cada día desde el 1 de octubre
de 2022 (hora de Kyiv) sin parte detectado se buscaron las publicaciones de
esa mañana (de 4:00 a 13:00) que mencionan drones («БпЛА», «Шахед»,
«Shahed», «ударн», «дрон») junto a cifras. Antes de ampliar el detector había
días así en todos los años: 22 en 2022, 40 en 2023, 29 en 2024, 8 en 2025 y 3
en 2026. La auditoría queda en código (`recogida/auditoria.py`) y se repite
con cada histórico.

### Formatos que no se reconocían

Todos con test (`tests/test_parte_formatos.py`):

- **Verbos**: presente y pasiva («противник атакує», «атакують»,
  «атаковано»), «здійснив комбінований удар / повітряний напад / кілька
  хвиль атак», «завдали масованого удару» (adjetivo en medio), «запущено»,
  y el parte de 2025 sin verbo («противник 104-ма ударними БпЛА»).
- **Noches**: «У ніч з 28 лютого на 1 березня» fallaba por un error de
  precedencia en la expresión regular del mes; «з 31 грудня 2022 на 1
  січня 2023 року»; «У ніч на 24.03.23»; noches sin fecha al principio de
  línea («Цієї ночі», «Сьогодні вночі», «У новорічну ніч», «Протягом ночі (з
  00:10 13 квітня)»), que son la noche que acaba el día de la publicación.
- **Rangos con horas en palabras**: «Із 20.00 вечора 5-го до опівночі 6-го
  листопада», «Із 20-ї години 17-го по 04 годину 18 листопада», «Із вечора 13
  липня по 4 ранку 14 липня», «25 травня о 22.00 і тривала до 5.00 26
  травня».
- **Intervalos**: «З 00.00 год по 05.00 год 29 травня» (sin «період»); «у ніч
  на 30 травня з 23.30 по 4.30» (sin paréntesis); «із (19.30 17 квітня)».
- **Días**: «10 лютого 2023 року противник ...» (fecha suelta con año al
  principio de línea), «На початку доби», «У вечірній час», «Уранці 3-го
  липня», «18 серпня 2026 року протягом денної пори (з 07.00 по 18.30)».
- **Solo «N із M»** de drones derribados junto al periodo.
- **Firma regional**: solo cuenta al principio de línea (o como etiqueta
  «#повітряне_командування»). Dentro de una frase («знищено силами
  Повітряне командування "Схід"») cita al mando que derribó en un parte
  nacional. «Бойова робота» y «На відео» al principio son pies de vídeo.
- **Cifras**: números compuestos («тридцять п’ять», «двадцять три»), drones
  de reconocimiento marcados como ОТР, Orlan, Zala, Supercam o Мерлін fuera
  de las cuentas, el titular como respaldo cuando el cuerpo no da derribados,
  y «понад 70» derribados como rango de 70 al total lanzado.

Para no confundir avisos y reportajes, una noche sin fecha solo cuenta si hay
una cifra de drones (un aviso de «найближчим часом повідомимо» o una cita en
mitad de un reportaje no son partes).

Se comparó lo que el parser extraía antes y después para todos los partes de
la caché: 13 partes cambian y los 13 son correcciones (periodos antes
aproximados ahora exactos, «тридцяти п’яти» que daba 5, derribados que
incluían drones de reconocimiento); uno deja de ser parte (un pie de vídeo).

### Tabla por año

«Partes antes» es lo que detectaba la versión anterior (informe de
recogida); «Días sin parte antes», lo que daba la auditoría con esa versión.

| Año | Días | Partes antes | Partes después | Fallidos antes | Fallidos después | Días sin parte antes | Días sin parte después | Sin explicar |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2022 | 92 | 12 | 18 | 1 | 2 | 80 | 74 | 0 |
| 2023 | 365 | 139 | 167 | 4 | 4 | 227 | 200 | 0 |
| 2024 | 366 | 258 | 276 | 3 | 1 | 110 | 93 | 0 |
| 2025 | 365 | 355 | 363 | 1 | 1 | 13 | 5 | 0 |
| 2026 | 270 | 276 | 280 | 2 | 1 | 5 | 2 | 0 |
| Total | 1458 | 1040 | 1104 | 11 | 9 | 435 | 374 | 0 |

Los días sin parte que quedan, por explicación de las publicaciones de esa
mañana:

- **2022**: 58 sin publicaciones de drones con cifras (noches sin ataque), 7
  con solo notas de un mando regional (por diseño, ver informe de recogida),
  6 con solo derribos sin ataque declarado, 3 sin cifras de drones.
- **2023**: 186 sin publicaciones de drones con cifras, 5 notas regionales, 5
  sin cifras de drones, 4 solo derribos.
- **2024**: 81 sin publicaciones de drones con cifras, 6 notas regionales, 3
  sin cifras, 2 solo derribos, 1 solo reconocimiento.
- **2025**: 5 sin publicaciones de drones con cifras: 1 y 7 de abril, 20 de abril
  (Pascua ortodoxa) y 9 y 10 de mayo (alto el fuego anunciado para el Día de la
  Victoria).
- **2026**: 2 sin publicaciones de drones con cifras: 12 de abril (Pascua) y
  11 de mayo.

No queda ningún día sin explicar, así que no hay enlaces de ejemplo.

### Reproceso

`python -m recogida.historico --fuente fuerza_aerea_ua --solo-cache` incorpora
la caché a la base de la rama `estado` sin volver a descargarla: los ataques
publicados conservan su identificador y cada cambio de cifras queda en el
historial. Da 63 ataques nuevos (5 de 2022, 25 de 2023, 20 de 2024, 8 de
2025 y 5 de 2026); casi todos los demás cambian porque ganan el campo
`derribados_categoria`. Después se pone al día con la relectura de 48 horas.

Muestra de comprobación (semilla 1), comparada con el texto: las cinco cifras,
periodos y categorías coinciden. Siguen las dos limitaciones ya conocidas: en
6858 falta Приморсько-Ахтарськ (va en otra frase) y las regiones de 6858 y
68985 incluyen objetivos u orígenes de misiles del mismo parte.

## 2. Arreglos

- **Relectura de 48 horas.** Cada ejecución baja también hasta las
  publicaciones de las últimas 48 horas; un parte editado actualiza su ataque
  y el cambio queda en el historial. Para que releer lo mismo no cambie la
  base cada hora, el registro de fallidos, su resolución y el cursor solo
  escriben si el valor cambia (test: releer sin cambios deja la base
  idéntica byte a byte).
- **«Derribados o neutralizados».** Campo público `derribados_categoria`:
  `derribados_o_neutralizados` cuando la cifra viene de una frase con
  «подавл», «знешкодж» o equivalente (en ruso, «подавлены», «РЭБ»); si no,
  `derribados`. En el esquema, la lista cerrada de campos y los tests.
- **Autor de los commits automáticos**: QuantuSync con
  `192205734+QuantuSync@users.noreply.github.com` (id de `gh api user`), tanto
  en `main` como en la rama `estado`.

## 3. Fuente: Ministerio de Defensa ruso (D3)

- **Canal**: vista pública web de `t.me/mod_russia`, paginando con `before`.
  En cada ejecución se comprueba la insignia de verificado y el título
  «Минобороны России»; si falla, no se lee nada, el motivo va al registro y
  la ejecución queda en rojo. El canal no enlaza una web oficial que lo
  confirme, así que no hay tercera comprobación como en la Fuerza Aérea.
- **Qué cuenta**: los partes de drones derribados sobre un territorio o un
  mar («дежурными средствами ПВО перехвачены и уничтожены N украинских
  беспилотных летательных аппаратов ... над территорией ...»). Se ignoran
  los resúmenes del día («Главное за день», «Итоги недели», «Сводка»), los
  derribos en la zona de combate del balance diario (sin «над территорией»),
  los relatos del frente (sin defensa aérea de guardia ni «попытка киевского
  режима») y los misiles (una viñeta de misiles no aporta región).
- **Periodo**: el que declara el parte, de hora de Moscú a UTC con
  `Europe/Moscow`. Variantes con test: «с 20.00 мск 13 июня до 7.00 мск 14
  июня», fechas en cifras («30.07») y «т.г.», «C» latina, «до полуночи»,
  «24.00», solo el inicio, «Около 15.05 мск», «в районе 21.00», «Около 10
  часов», «В 13.40 мск», «в течение (прошедшей, сегодняшней) ночи»,
  «Сегодня ночью», «Ночью 16 ноября», «В ночь с 20 на 21 сентября», «в
  ночные и утренние часы», «в течение дня», «Утром», «В утренние часы 10
  апреля», «Сегодня днем», «Вечером» y «По состоянию на 20.00 мск».
- **Cifra**: la del parte, sin la del intento que trae el preámbulo («при
  попытке ... с применением трех беспилотников»). Si la primera cifra abre
  la lista por regiones con dos puntos, es el total; si no, se suman las
  cifras de las frases o viñetas con derribos («уничтожены пять и перехвачены
  три ..., четыре БПЛА над ...», «Еще пять БПЛА подавлено ...»). Singular
  sin cifra es 1; «все / украинские беспилотники уничтожены» son todos los
  del intento. Números en letras, compuestos e instrumentales.
- **Tipo de dron**: campo público `tipos_dron` con `ala_fija` («самолетного
  типа») o `multirrotor`.
- **Regiones**: por ISO 3166-2 con `configuracion/regiones_rusia.json` (69
  entradas). Crimea, Sebastopol y las zonas ocupadas llevan su código
  ucraniano (UA-43, UA-40, UA-14, UA-09, UA-23, UA-65), que es el de la norma;
  Abjasia, GE-AB. Un distrito («Ступинского района Московской области») se
  salta porque lleva detrás su región. Una palabra con mayúscula que no es
  región ni está en la lista de palabras que no lo son deja el parte como
  fallido: así el vocabulario crece con el uso. Los mares no tienen código.
- **Estado y credibilidad**: confirmado como el resto de partes de la capa de
  guerra; fiabilidad D, una sola fuente D sin contradicción da credibilidad 3
  por la regla. Campo público `reivindicacion_de_parte: true`. Fuente pública
  en la capa de Ucrania e interna fuera de ella.
- **Fallidos**: a `partes_fallidos`, sin publicar, como en la Fuerza Aérea.

### Histórico y cobertura

Recorrido completo en local con el mismo mecanismo reanudable: 2246 páginas,
37 701 publicaciones desde el 1 de octubre de 2022 (hora de Moscú), sin
ninguna página de bloqueo. Procesado con `python -m recogida.historico
--fuente mindef_ru --solo-cache`.

| Año | Días | Publicaciones | Partes | Leídos bien | Fallidos | Días con parte | Días sin parte | Sin explicar |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2022 | 92 | 2220 | 0 | 0 | 0 | 0 | 92 | 0 |
| 2023 | 365 | 9111 | 257 | 255 | 2 | 112 | 253 | 0 |
| 2024 | 366 | 10617 | 1269 | 1266 | 3 | 344 | 22 | 0 |
| 2025 | 365 | 9774 | 1330 | 1327 | 3 | 358 | 7 | 0 |
| 2026 | 270 | 5979 | 728 | 728 | 0 | 267 | 3 | 0 |
| Total | 1458 | 37 701 | 3584 | 3576 | 8 | 1081 | 377 | 0 |

- **2022 sin partes, por el canal.** De octubre a diciembre de 2022 el
  ministerio no publicaba partes propios de drones derribados sobre su
  territorio: solo balances del frente («сбиты семь самолётов и 45
  беспилотников») y relatos. Los días sin parte se explican así: 57 sin
  publicaciones de drones con cifras, 24 sin derribos (frente, vídeo), 6
  resúmenes y 5 derribos en la zona de combate.
- **2023**: los partes propios empiezan a ser diarios a mediados de año. De
  los 253 días sin parte, 98 solo traen derribos en la zona de combate, 79 no
  traen drones con cifras, 73 son del frente o vídeos, 2 resúmenes y 1 sin
  cifras.
- Un parte cuenta por publicación y periodo: el ministerio publica varios
  tramos al día (7:00-14:00, 14:00-20:00, noche), y cada uno es un ataque.
  Dos partes con el mismo inicio de periodo se funden como en la Fuerza
  Aérea (78 veces en el histórico).
- **Fallidos (8)**: 5 sin periodo declarado (por ejemplo «5 января пресечена
  ...» o un parte sin hora) y 3 sin cifra («БПЛА обнаружены и уничтожены»
  sin decir cuántos).

Muestra de comprobación (semilla 1: 38358, 55608, 62102, 63685, 66302),
comparada con el texto: cifras, periodos y regiones coinciden en las cinco.

## 4. GDELT (C3)

### Recogida actual

- **API DOC 2.0**, modo artlist en JSON, hasta 250 artículos por llamada, con
  los filtros dentro de `query`: `(drone OR drones OR UAV OR UAVs)` y los
  medios de 42 países europeos (`sourcecountry:`), en dos consultas de 21
  países. Quedan fuera Rusia, Bielorrusia y Ucrania, cuyos medios cubren la
  guerra y ahogarían las noticias de incidentes en el resto de Europa.
- **Solo términos ingleses en la consulta.** La prueba desde un runner mostró
  que la API busca sobre la traducción inglesa del artículo: «Drohne» y
  «lennokki» solos dieron 0 artículos en un día, y «drone» devolvió titulares
  en alemán y polaco. El vocabulario por idioma (`configuracion/gdelt.json`,
  30 idiomas europeos más ruso y ucraniano, en singular y plural) se usa en el
  filtro local sobre el titular original.
- **Ritmo**: 6 s entre peticiones, porque la API pide una cada 5 s en su
  propia respuesta 429; 6 reintentos con esperas de 10 s dobladas. Cada
  ejecución pide desde el cursor con una hora de solape; una ventana que llega
  a 250 artículos se parte en dos hasta 15 minutos.
- **Si no responde**, el cursor no avanza y la siguiente ejecución recupera el
  hueco. Con más de un día pendiente la ejecución queda en rojo. Si nunca ha
  respondido, el cursor se fija en el inicio de la primera ventana para que
  el hueco cuente.
- **Tabla interna `articulos`**: URL canónica (https, sin «www.», sin
  fragmento ni parámetros de seguimiento), medio, fecha, idioma (ISO 639-1),
  país del medio (ISO 3166-1), titular, temas y lugares (la API DOC no trae
  temas; los lugares salen del titular) y número de réplicas. Nunca el texto.
  Tabla `candidatos` con tipo, lugar, inicio, último artículo y artículos.
  Ninguna de las dos admite DELETE.
- **Filtro sin modelo**: el titular nombra un dron, no es ocio ni comercio
  («espectáculo», «Lichtshow», «review», «boda», «delivery»...) y trae una
  señal de incidente (aeropuerto, militar, infraestructura, espacio aéreo,
  avistamiento, policía, cierre) o un lugar del nomenclátor.
- **Réplicas**: misma URL canónica, o titular casi idéntico en las 72 horas
  anteriores (85 % de palabras comunes, sin el nombre del medio al final). La
  réplica no se guarda: suma una al original.
- **Agrupación provisional** con la regla de fusión del diseño: mismo
  objetivo o puntos a menos de la suma de radios más 10 km, mismo tipo
  aparente, y la ventana (con precisión de hora, inicios a menos de 6 horas;
  con precisión de día, el mismo día o el siguiente; más de 12 horas sin
  actividad, candidato nuevo). La fecha de un artículo es la de publicación,
  así que se agrupan con precisión de día. Un artículo sin lugar, con varios
  lugares o que encaja en dos candidatos abiertos no se agrupa. Los
  candidatos crecen de una ejecución a otra.
- **Nomenclátor inicial** (`configuracion/lugares_europa.json`, generado con
  `recogida/lugares_osm.py` desde OpenStreetMap, ODbL con atribución en el
  fichero y en el README): 796 aeropuertos con código OACI e IATA, 229
  aeródromos militares y 53 centrales nucleares de 39 países europeos, con
  coordenadas, radio (5 km aeropuertos y bases, 2 km centrales) y los nombres
  en los idiomas de OpenStreetMap. Un nombre completo casa solo; una ciudad
  («Munich», «Madrid») solo si el titular nombra además el tipo de lugar
  («airport», «Flughafen»...). Ucrania queda fuera: va en la capa de guerra.

### Histórico desde el 1 de enero de 2025

**Prueba de la API DOC con fechas antiguas.** Tres sondas desde runners de
GitHub, con peticiones espaciadas y reintentos:

- Cuando responde, devuelve artículos de fechas antiguas: 139 el 1 de enero de
  2025, 129 el 15 de enero de 2025 y 126 el 15 de enero de 2024 (tres países,
  un día). La cobertura de la API llega, por tanto, más atrás de enero de 2025.
- Pero no responde de forma fiable: en la tercera sonda, 38 de 45 intentos
  dieron 429 y 2 fallaron por red; 3 de las 12 consultas no salieron en 6
  intentos con esperas de hasta 150 s. Desde la IP local, todas las
  peticiones dieron 429 durante horas.
- Una recogida de prueba de los últimos 5 días en un runner, con 6 s entre
  peticiones y 6 reintentos, no obtuvo ni un artículo en 2 horas: seis días
  seguidos sin respuesta y se detuvo.
- Estimación con la API: un día de los 42 países son del orden de mil
  artículos, al menos 6 llamadas por el límite de 250; 634 días son unas 3800
  llamadas con éxito. Al ritmo observado (5 respuestas en una hora de sonda),
  serían cientos de horas. No es un camino fiable.

**GKG 2.0: medido y descartado por tiempo.** Ocho ficheros de cada flujo de
fechas repartidas entre enero de 2025 y septiembre de 2026:

| Flujo | Tamaño medio comprimido | Descarga media | Filtrado |
| --- | ---: | ---: | ---: |
| Inglés (`gkg.csv.zip`) | 4,2 MB | 0,64 s | 0,07 s (13 MB sin comprimir, unas 1000 filas) |
| Traducido (`translation.gkg.csv.zip`) | 7,2 MB | 1,1 s | 0,12 s estimado |

Hacen falta los dos flujos, porque las noticias en otros idiomas solo van en el
traducido. Del 1 de enero de 2025 al 26 de septiembre de 2026 hay 634 días ×
96 franjas = 60 864 franjas: **unos 694 GB** comprimidos y, en serie, unos
60 864 × 1,93 s ≈ **117 500 s, casi 33 horas**. Supera las 12 horas: no se
lanzó.

Alternativas, de mejor a peor:

1. **GKG en paralelo en GitHub Actions**: una matriz de trabajos por meses
   (cada uno, unas 2900 franjas y hora y media), que filtra en flujo y solo
   guarda las filas que pasan; se fusiona con la base como el histórico de la
   API. El volumen sigue siendo de ~700 GB de descarga, pero repartido y con
   buena conexión.
2. **Solo el flujo inglés de GKG**: 256 GB y unas 12,5 horas en serie; pierde
   las noticias que no están en inglés.
3. **API DOC poco a poco**: `recogida/historico_gdelt.py` ya existe
   (reanudable por días, con tope de tiempo y fusión con la base fresca al
   subir); podría correr en huecos de poco tráfico durante semanas.
4. **Las tablas públicas de GDELT en un almacén de datos en la nube**,
   filtrando en el servidor; tiene coste por volumen consultado y exige una
   cuenta ajena al proyecto.

### Artículos y candidatos

Ni la prueba desde el runner ni la IP local obtuvieron artículos, así que en
este PR **no hay artículos ni candidatos reales** que contar por mes ni una
muestra de 10 candidatos. La tabla y la muestra salen con
`python -m recogida.informe_gdelt` en cuanto la recogida horaria guarde
datos; los tests comprueban el filtro, el deduplicado, la agrupación y el
informe con artículos de ejemplo.

## Valores justificados

| Valor | Dónde | Por qué |
| --- | --- | --- |
| 48 h de relectura | `fuente.py` | Los canales corrigen partes durante la mañana y a veces al día siguiente. Medido: en 48 horas la Fuerza Aérea llegó a 570 publicaciones, 29 páginas, unos 90 s a 3 s por página |
| 500 páginas por ejecución | `fuente.py` | Unas 10 000 publicaciones, tres meses al ritmo medio de 2026 (unas 110 al día) |
| 4:00 a 13:00 como «esa mañana» | `auditoria.py` | Los partes de la noche salen en esa franja en los dos canales |
| 5 enlaces de ejemplo por año | `auditoria.py` | Lo pedido |
| 12 como mediodía | `parte.py` | Una hora de inicio de 12 o más en una noche es de la víspera; «8 вечора» son las 20 |
| 2000 para años de dos cifras | `parte.py`, `mindef.py` | «24.03.23» es de este siglo |
| 20:00 como inicio aproximado de la noche | `mindef.py` | Es la hora que declaran los partes del ministerio que dan el inicio («с 20.00 мск 13 июня») |
| 1 día de margen para el año | `mindef.py` | Un parte habla de las horas que acaban de pasar |
| 6 s entre peticiones a GDELT | `gdelt.py` | La API pide una cada 5 s en su propia respuesta 429 |
| 6 reintentos, espera de 10 s doblada | `gdelt.py` | Desde un runner, 38 de 45 peticiones dieron 429; así una consulta sale en unas cuatro de cada cinco ejecuciones (10,5 minutos como mucho) |
| 45 minutos de trabajo | `recogida.yml` | Dos consultas de GDELT pueden sumar 21 minutos con sus reintentos |
| 15 minutos de ventana mínima | `gdelt.py` | La API indexa cada 15 minutos |
| 1 h de solape | `gdelt.py` | La API tarda en indexar algunos artículos |
| 1 día de primera ventana | `gdelt.py` | Sin cursor se empieza un día atrás |
| 1 día de hueco tolerado | `gdelt.py` | El cursor no avanza si la API no responde; con más de un día sin respuesta la ejecución queda en rojo |
| 21 países por consulta | `gdelt.py` | Dos consultas de unos 600 caracteres; menos peticiones bajo el límite |
| 10 km, 6 h, 12 h | `noticias.py` | Regla de fusión del diseño |
| Precisión de día para los artículos | `noticias.py` | La fecha de un artículo es la de publicación, no la del suceso |
| 72 h para buscar réplicas | `noticias.py` | Las réplicas de una nota de agencia salen en uno o dos días |
| 85 % de palabras comunes, 6 palabras | `noticias.py` | «Casi idéntico»: deja pasar un signo o el nombre del medio y no dos noticias que solo comparten el lugar; con menos de 6 palabras se exige igualdad |
| 4 letras de alias | `noticias.py` | Con menos, siglas como «CPH» casan con cualquier cosa |
| Radio 5 km (aeropuerto, base), 2 km (central) | `lugares_osm.py` | Un aeropuerto grande o una base ocupan unos 3 km de lado; una central, menos de 1 km |
| 150 km para el país de un lugar sin OACI | `lugares_osm.py` | Toma el país del aeropuerto europeo más cercano; más lejos es probable que esté fuera de Europa |
| 30 s entre consultas a Overpass | `lugares_osm.py` | El servidor público pide no encadenar consultas pesadas |
| 10 minutos tras un día sin respuesta, 6 fallos seguidos | `historico_gdelt.py` | Deja pasar un bloqueo temporal por exceso; después para y sube lo hecho |
| Semilla 1, 10 candidatos | `informe_gdelt.py` | Solo hace la muestra reproducible |

## Decisiones tomadas aquí

- **Recogida por fuente.** `recogida/fuente.py` describe una fuente de partes
  (canal, verificación, detector, parser y un perfil con sentido, idioma,
  zona, versión y si es reivindicación de parte). La ejecución horaria
  recorre todas: si una no puede leerse (canal no verificado, sin cursor o
  con un hueco demasiado grande), las demás sí y la ejecución queda en rojo.
- **El histórico incorpora a la base** de la rama `estado` en vez de crear
  una nueva, para no cambiar identificadores ya publicados.
- **`reivindicacion_de_parte` solo en el ministerio.** La Fuerza Aérea
  también es una parte, pero la instrucción era marcar al ministerio; el
  campo no aparece en sus ataques.
- **«Московского региона»** va a RU-MOS (la región incluye la ciudad, RU-MOW,
  que tiene su propio código cuando se nombra «Москва»).
- **Nomenclátor en forma Unicode descompuesta (NFD).** El hook de pre-push
  confundía «Iași» con una palabra prohibida porque `grep -w` no toma «ș»
  como letra. Es el mismo texto y la búsqueda normaliza igual.

## Sigue abierto

- **Histórico de GDELT** desde el 1 de enero de 2025: sin hacer (punto 4).
- **Muestra de candidatos**: pendiente de que haya artículos.

- **Regiones de los misiles** y **zonas en otra frase** en la Fuerza Aérea
  (del informe de recogida).
- **Partes del ministerio que se solapan.** Tramos del día y noche por
  separado, y a veces un «Всего в ночное время» que los suma: sumar ataques
  UA_RU de un mismo día sin mirar los periodos contaría dos veces.
- **Reparto por región del ministerio.** Desde 2025 el parte da cifras por
  región en viñetas; solo se guardan las regiones, no sus cifras.
- **Notas de mandos regionales de 2022 y notas de solo derribos de 2023** de
  la Fuerza Aérea siguen fuera, por diseño.
- **Historial del reproceso.** Añadir `derribados_categoria` deja un cambio
  en el historial de casi cada ataque de la Fuerza Aérea.
- **Días sin ataque.** Los días sin parte de 2025 y 2026 coinciden con
  Pascuas y altos el fuego; la web debería distinguir «sin ataque» de «sin dato».

## Atascos

- **GDELT sin datos.** La API DOC rechaza con 429 todas las peticiones desde
  la IP local y casi todas desde los runners de GitHub; la recogida de prueba
  de 5 días no obtuvo ningún artículo. El código está hecho y probado con
  respuestas de ejemplo, pero no hay artículos ni candidatos reales. Si la
  recogida horaria tampoco consigue respuesta, quedará en rojo pasado un día
  (ver punto 4 y las alternativas).
