# Informe: noticias desde GKG y arreglos de los partes

Cuarto PR del Observatorio Europeo de Incidentes con Drones (EODI): la
recogida horaria de noticias deja la API DOC de GDELT y lee los ficheros GKG,
y se corrigen los partes de las dos fuentes de la capa de guerra.

## 1. Noticias en vivo desde los ficheros GKG

La API DOC devolvía 429 casi siempre (informe anterior). Se retira del código,
con su histórico por días; la recogida lee ahora los ficheros GKG 2.0 que
GDELT publica cada 15 minutos (`recogida/gdelt.py`).

- **Franjas.** Los índices de última actualización (`lastupdate.txt` y
  `lastupdate-translation.txt`) dicen cuál es la última franja; la última
  procesable es la menor de las dos. Cada ejecución procesa todas las franjas
  pendientes desde la última procesada, las dos (inglés y traducido), con un
  tope de 192 por ejecución; el cursor avanza franja a franja.
- **En flujo, sin guardar.** Cada fichero se descarga en memoria, se
  descomprime y se lee fila a fila; no se escribe en disco.
- **Qué se toma de cada fila:** URL, fecha de la franja, medio, idioma de
  origen (`srclc:` del flujo traducido; el flujo inglés es inglés), temas
  propios de GDELT (sin las taxonomías largas `TAX_`, `WB_`, `UNGP_`...,
  como mucho 20), lugares del GKG (solo para saber si son europeos) y el
  titular de la página, que viene en `<PAGE_TITLE>` de los campos extra con
  entidades HTML. El texto nunca.
- **Qué pasa:** el titular nombra un dron (el vocabulario de 30 idiomas del
  filtro) y el medio es europeo o el artículo sitúa algo en un país europeo.
  Rusia, Bielorrusia y Ucrania siguen fuera como países del medio.
- **País del medio.** El GKG no lo trae. Sale de la lista de dominios por
  país que publica GDELT (`recogida/medios_gdelt.py` genera
  `configuracion/medios_europa.json`): 12 863 medios europeos cuyo país no se
  deduce del dominio de primer nivel; el resto se resuelve por el sufijo
  (`.de` → DE, `.uk` → GB). Un dominio de la lista que no es un medio de
  noticias y cuyo nombre choca con la comprobación de términos del repositorio
  se omite por su huella SHA-256.
- El filtro sin modelo, las réplicas y la agrupación en candidatos no cambian.
- **Ficheros que faltan.** El 27 de septiembre de 2026 el índice del flujo
  traducido anunciaba ficheros que daban 404 durante más de una hora. La
  ejecución se para en la primera franja que falta y la reintenta en la
  siguiente; si seis horas después de la última franja anunciada sigue sin
  estar, se da por perdida (se cuenta como «ausentes») y se sigue.
- **En rojo** si tras la ejecución quedan franjas pendientes de más de un día.
- **Cursor heredado.** El cursor de la API DOC (`hasta`) se convierte en la
  franja que lo contiene: la primera ejecución recupera desde ahí.
- **Prueba en local** con ficheros reales de dos horas: 4 franjas, 9007
  filas, 19 con dron en el titular y relación con Europa, 3 artículos nuevos
  tras el filtro, en 7,9 s.

## 2. Doble conteo del Ministerio de Defensa ruso

`proceso/solapes.py`. El ministerio publica tramos del día y de la noche y, a
veces, un resumen de un periodo que ya cubrían tramos publicados antes («За
период с 20.00 мск 8 апреля по 06.00 мск 9 апреля ... 158» tras «В период с
22.00 до 22.15 мск ... пять»).

- **Total.** Un parte con inicio exacto que cubre tramos publicados antes que
  él es el total si sus cifras no son menores que las de esos tramos, en
  conjunto y región a región. Los tramos quedan enlazados a él con el campo
  público `incluido_en` y no se suman. Si dos totales se anidan, el tramo va
  al mayor.
- **Solape sin total.** De dos tramos exactos que se pisan más de 15 minutos,
  cuenta el de más derribos y el otro queda enlazado con `solapado_con`.
- **Noches sin horas** («в течение прошедшей ночи»): su inicio es aproximado
  y no prueba que cubran a nadie. El ministerio las publica a continuación del
  último tramo, así que se toman como contiguas y siempre cuentan.
- **Un fin aproximado** es la hora de publicación de un parte que solo da el
  inicio («В период с 20.00 мск 25.05»): cubre hasta que se publica.
- Los enlaces se recalculan con todos los ataques UA_RU en cada ejecución
  horaria y en el histórico; un cambio queda en el historial.
- **Fin de los resúmenes.** El parser no leía «по 06.00 мск» como fin del
  periodo y lo dejaba en la hora de publicación; ahora sí.

### Cifra a partir del desglose

Al probar la regla con la caché apareció un error anterior: el parser sumaba
la cifra de cabecera y la del desglose («уничтожены ... четыре ... Два БПЛА
перехвачены над ... и по одному БПЛА сбито над ...» daba 6 en vez de 4) y
contaba una sola vez «по одному» sobre varias regiones («11 ... над
Белгородской, четыре над Брянской, по одному БПЛА над Курской, Калужской,
Ростовской областями и Республикой Крым» daba 11 o 12 en vez de 19). Si cada
«над» del parte tiene su cifra y no hay una cabecera que diga otra cosa, la
cifra es la suma del desglose. Cambian 126 partes; en una muestra de 8 con la
regla final (semilla 21), los 8 son correcciones, como 42006: 14 + 16 + 3 + 1 +
1 = 35, donde antes daba 33.

### Derribos rusos por año

Suma de `derribados` de los ataques UA_RU por año del identificador, antes y
después de reprocesar la caché. «De ello, parser» es el efecto del desglose
y del fin de los resúmenes; «de ello, solapes», lo que deja de sumarse por
los enlaces.

| Año | Antes | Tras el parser nuevo | Contados sin doble conteo | Cambio total | De ello, parser | De ello, solapes | `incluido_en` | `solapado_con` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2023 | 717 | 761 | 761 | +44 | +44 | +0 | 0 | 0 |
| 2024 | 7932 | 7678 | 7671 | −261 | −254 | −7 | 2 | 1 |
| 2025 | 29 919 | 29 865 | 29 789 | −130 | −54 | −76 | 4 | 7 |
| 2026 | 86 460 | 86 460 | 86 455 | −5 | +0 | −5 | 0 | 2 |
| Total | 125 028 | 124 764 | 124 676 | −352 | −264 | −88 | 6 | 10 |

El doble conteo por solapes es pequeño: los resúmenes que cubren tramos ya
publicados solo aparecen en abril de 2025 y algún día suelto de 2024. En 2026
los partes no se solapan salvo en dos mañanas.

## 3. Derribos rusos por región

Desde 2024 el parte da en viñetas la cifra de cada región («▪️67 БпЛА – над
территорией Краснодарского края», «двадцать шесть – над ...», «по девять БПЛА –
над территориями Белгородской и Саратовской областей»). Se guarda en el campo
público `regiones[].derribados` solo si las cifras de regiones y mares suman
la cifra del parte. Los mares cuentan para la suma pero no tienen código. Una
cifra para varias regiones juntas no da reparto: así son casi todos los partes
de 2026. Resultado: 2795 de 3499 ataques UA_RU con reparto.

Esquema (`region_ucrania.derribados`), lista cerrada de campos públicos y
tests con casos reales (51077, 37778, 34717, 52931, 29663, 54825, 65571,
47400, 41579, 45167, 47131, 28732).

## 4. Fuerza Aérea: regiones de misiles y zonas en otra frase

- **Regiones por arma.** Cada región del parte se atribuye al arma nombrada
  antes en su cláusula; si hay dos armas a menos de 40 letras («влучання ракет
  та ударних БпЛА») cuenta para las dos; sin arma antes, la siguiente; sin
  ninguna en la cláusula, la única de la frase o, si no se sabe, drones. Las
  que solo aparecen por los misiles van al campo público nuevo
  `regiones_misiles` y ya no cuentan como afectadas por drones. «Зенітними
  ракетними підрозділами» son las unidades que derriban, no misiles.
- **Orígenes fuera.** Una región con «із», «з» o «від» delante (y «над» en la
  frase del ataque) es el origen del lanzamiento: «із окупованої території
  Донеччини», «із повітряного простору Курської та Запорізької областей».
  Antes entraban como regiones afectadas.
- **Zonas de lanzamiento en otra frase:** «район пусків (безпілотників) –
  Єйськ» cuando el arma nombrada antes es un dron, «Пуски ... здійснювались з
  напрямку ...» y la dirección antes de la cifra («атакували з
  південно-східного напрямку (Приморсько-Ахтарськ - рф), застосувавши 11
  ...»). El «район пусків» de los misiles no cuenta.
- **Reproceso de la caché:** cambian las regiones de 196 de 1088 ataques; 96
  tienen `regiones_misiles`; los ataques sin zonas de lanzamiento bajan de 300
  a 213; ninguna cifra de derribos cambia. En las muestras revisadas con la
  regla final (11 cambios, semillas 11 y 23), 10 son correcciones. El otro,
  2558, pierde Poltava: «завдав удару по одному з оперативних аеродромів на
  Полтавщині» lleva un «з» delante que no es un origen.

## 5. Reivindicación de parte

`reivindicacion_de_parte: true` también en los ataques de la Fuerza Aérea,
porque también es parte en la guerra; la descripción del esquema lo dice. Se
aplica a los ataques ya existentes al actualizarlos: los 1088 lo llevan tras
el reproceso.

## Reproceso

`python -m recogida.historico --fuente fuerza_aerea_ua --solo-cache` y después
`--fuente mindef_ru --solo-cache --base <la anterior>` (opción nueva para
encadenar fuentes sobre una base local), sin descargar de nuevo. Ningún
ataque nuevo; se conservan los identificadores y cada cambio queda en el
historial. El workflow horario se desactivó mientras tanto para que no
escribiera en la rama `estado` una base con el código anterior.

## Valores justificados

| Valor | Dónde | Por qué |
| --- | --- | --- |
| 15 minutos por franja | `gdelt.py` | Es el ritmo de publicación de los ficheros GKG |
| 0,5 s entre peticiones a GDELT | `gdelt.py` | Son ficheros estáticos, no una API; cada uno tarda de 0,6 a 1,1 s en bajar |
| 192 franjas por ejecución | `gdelt.py` | 48 horas, unos 12 minutos: recupera un corte de dos días en una ejecución sin pasar del límite de 45 minutos |
| 6 horas antes de dar un fichero por perdido | `gdelt.py` | El traducido llegó a ir más de una hora por detrás de su índice; seis horas dejan margen y no retienen las noticias en inglés más de un día |
| 1 día de hueco tolerado | `gdelt.py` | Igual que con la API DOC: más, y la ejecución queda en rojo |
| 1 día de primera ventana | `gdelt.py` | Sin cursor se empieza un día atrás |
| 20 temas como mucho | `gdelt.py` | Los temas propios de GDELT de un artículo de drones son menos; las taxonomías largas no ayudan a clasificar y engordan la base |
| 15 minutos de solape tolerado | `solapes.py` | Los tramos consecutivos del ministerio se pisan hasta 10 minutos por redondeo («до 4.05» y «с 4.00») |
| 40 letras entre dos armas | `parte.py` | «ракет та ударних БпЛА» o «ракет і дронів»: dos armas de la misma cláusula que comparten las regiones |
| 5 palabras entre la preposición de origen y la región | `parte.py` | «із Ростовської обл. – рф, ТОТ Криму» |

## Decisiones tomadas aquí

- **Europa por el medio o por el lugar.** Además de los medios europeos, pasa
  un artículo de un medio de fuera si el GKG lo sitúa en un país europeo («Spain
  Asks Morocco to Adjust Drone Altitudes After Melilla Airport Incident»). La
  API DOC solo permitía filtrar por el país del medio.
- **Regiones sin arma clara** van a las de drones, como antes: la capa es de
  drones y así no se pierde ninguna.
- **Cifra rusa con desglose**: la suma del desglose solo sustituye a la
  cabecera si no la contradice; si la contradice, se queda la cifra de antes
  (hay listas con una viñeta sin «над» que el desglose no cuenta).
- Los enlaces entre tramos se aplican solo al sentido UA_RU: los partes de la
  Fuerza Aérea no publican tramos que se solapen.

## Sigue abierto

- **Histórico de noticias con GKG** desde el 1 de enero de 2025: va en el
  siguiente PR, repartido en trabajos de GitHub Actions.
- **Ediciones de partes** más allá de 48 horas y **notas regionales de 2022**
  de la Fuerza Aérea (informes anteriores).
- **Regiones de la Fuerza Aérea**: un «з» que no marca el origen («по одному з
  оперативних аеродромів на Полтавщині», 2558) hace perder la región.
- **Cifras rusas de listas incompletas** (una viñeta sin «над»): quedan con la
  cifra de cabecera y sin reparto.
- **Lista de medios de GDELT** de 2018: los medios nuevos se resuelven por el
  sufijo o por el lugar del artículo; los de dominio genérico (`.com`, `.eu`)
  que no están en la lista solo pasan por el lugar.

## Atascos

Ninguno sin resolver. Un commit local entró con un error de mypy porque la
comprobación iba en una tubería sin `pipefail`; se detectó antes de subir, se
corrigió en el mismo commit y la puerta se pasa ahora con un script que
comprueba el código de salida de cada comando.
