# Corrección de errores de datos

European Observatory of Drone Incidents, 4 de octubre de 2026. Las horas son UTC. Un pull request
por bloque, en este orden. La base es de solo añadir: cada corrección entra como versión nueva con
su motivo en el historial, y lo retirado queda marcado como retirado con su causa. Todo se
reprocesa desde los mensajes y las citas ya guardados, sin volver a descargar ni llamar al
extractor salvo donde se dice.

Cifras «antes» medidas sobre la base de la rama `estado` de las 08:15 del 4 de octubre (la que
servía droneobservatory.eu), antes de cambiar nada.

| Bloque | Pull request | Fusionado |
| --- | --- | --- |
| 1. Víctimas y homenajes | #91 | 08:54 |
| 2. Partes regionales | #94 | 09:41 |
| 3. Zonas de lanzamiento | #95 | 09:50 |
| 4. Cruces de frontera | #96 | 10:49 |
| 5. Partes del mismo día | #99 | 10:58 |
| 6. Pendientes de presencia | #100 | 11:01 |
| 7. Fuentes españolas | #101 | 11:42 |
| Base en trozos de 50 MB | #107 | 12:47 |
| Cruces sin copias | #112 | 14:55 |
| Leipzig y Wunstorf | #113 | 15:06 |
| Base en memoria sin tope de 1 GiB | #114 | 15:45 |
| Ficha revisada con la hora de la ejecución | #118 | 16:40 |
| Frase del cruce, Leipzig completo y ensayo de la recogida | #120 | 17:50 |
| Mykoláiv por el anuncio oficial | #121 | 18:45 |

Resumen de cifras, antes y después:

| | Antes | Después |
| --- | ---: | ---: |
| Impactos con fallecidos igual a un año | 8 | 0 |
| Impactos retirados por homenaje u obituario | — | 30 |
| Impactos con la cifra de víctimas corregida | — | 75 |
| Fallecidos de los impactos, 2024 T4 a 2026 T4 | 17.276 | 164 |
| Impactos rusos localizados de Zaporiyia | 94 % (5.444 de 5.793) | 48,8 % (6.089 de 12.478) |
| Nombres distintos de zonas de lanzamiento | 85 | 24 |
| Ataques con cruces | 6 | 78 |
| Incursiones europeas enlazadas con su ataque | 0 | 123 |
| Cruces declarados solo por Ucrania, con su frase, dentro del ataque | — | 6 |
| Incidentes europeos publicados (Rumanía, Moldavia) | 513 (106, 57) el 4 de octubre por la mañana; 592 (145, 95) con las copias | 507 (105, 60) |
| Partes rusos con `incluido_en` | 6 | 78 |
| Incidentes españoles de la Guardia Civil | 0 | 0 (no hay notas de intrusiones de 2024 a hoy) |

## Bloque 1. Víctimas imposibles y homenajes guardados como impactos

### Causa

Dos fallos en la lectura por código de los mensajes de las administraciones
(`proceso/mensajes_guerra.py`):

1. **El año se leía como número de víctimas.** La cifra de víctimas se buscaba en todo el mensaje
   con un número de hasta cuatro cifras junto al verbo, y solo se quitaban las fechas sin año
   («30 грудня»). En «загинув 30 грудня 2024 року» quedaba «загинув 2024». Además, la cifra del
   mensaje entero (todas las armas, todos los lugares, acumulados desde el inicio de la invasión,
   ganado muerto) se asignaba al impacto si el mensaje daba un solo lugar: «Загинули 500 голів
   свійської тварини» (Pavlohrad, 500 fallecidos), «з початку повномасштабного вторгнення …
   поранені понад 2100 людей» (Zaporiyia, 2.100 heridos), las víctimas de un misil en Kryvyi Rih
   repetidas por el canal de Zaporiyia (130 heridos), edades sin guion («жінки 59 та 67 років»).
   Y al volver a leer un mensaje, el impacto se quedaba con la mayor cifra vista, así que una cifra
   mal leída no se corregía nunca.
2. **Los homenajes no se distinguían de un ataque.** La administración de Donetsk publica cada día,
   con la plataforma Меморіал, la memoria de un caído («…загинув 30 грудня 2024 року поблизу
   селища Роздольне… внаслідок атаки ворожого FPV-дрона»); la de Lviv, las despedidas de sus
   militares. Esos mensajes nombran un dron, un daño y un pueblo, y salían como impacto de la
   noche de su publicación.

### Cambios

- **Víctimas leídas frase a frase** (`_victimas_frase`): un número igual a un año que la frase
  escribe como fecha («30 грудня 2024 року», «у 2025 році») no es una cifra de víctimas; las
  edades sin guion y los animales tampoco; una cifra de más de 100 solo vale con la cifra pegada
  al verbo («загинули 120 людей», «поранено 130 осіб»); si no, el campo queda vacío.
- **Víctimas solo de frases de drones**: cuentan las frases cuya arma (la suya o la de la frase
  anterior) son drones y nada más, y que no dan un acumulado («з початку», «с начала», «за
  тиждень»). Mismo criterio para heridos y fallecidos. Siguen asignándose al impacto solo si el
  mensaje da un único lugar.
- **Homenajes, obituarios y memoria** (regla `HOMENAJE`, motivo `homenaje`): un mensaje de la
  plataforma Меморіал, con «на псевдо» o «позивний», «Пам'яті …», un premio póstumo o la muerte
  de alguien con fecha y año no es un impacto. Las frases de condolencia o de luto dentro de un
  parte («Світла пам'ять», «Схиляємо голови», «соболезнования») se saltan, sin anular el resto del
  parte.
- **Cada fuente guarda sus víctimas** (`lecturas[].victimas`, interno, esquema 1.9.0 ampliado) y
  el impacto lleva la mayor de sus fuentes: volver a leer un mensaje corrige la cifra.
- **Corrección de lo guardado** (`recogida/guerra.corregir`, cursor `guerra:correccion`, versión
  `victimas-homenajes/1`): una vez, dentro de la recogida horaria, vuelve a leer con las reglas
  nuevas el mensaje de cada fuente de los impactos vigentes desde los textos que guarda el lector
  en el servidor. Una fuente cuyo mensaje no describe un ataque con dron sobre un lugar se quita;
  un impacto sin fuentes queda retirado con su motivo; las víctimas se rehacen. Cada cambio deja
  su motivo en el historial. A mano: `python -m recogida.guerra corregir --base <db.age>`.
- Versión del analizador `mensajes-guerra/3`.

### Cifras

Medidas aplicando la corrección a una copia de la base de las 08:15 con los mensajes del servidor
(6.292 impactos vigentes revisados; ninguna fuente sin texto).

| | Antes | Después |
| --- | ---: | ---: |
| Impactos retirados (homenaje, obituario o memoria) | — | 30 |
| Impactos con la cifra de víctimas cambiada | — | 75 |
| Impactos con fallecidos igual a un año (2023, 2024 o 2025) | 8 | 0 |
| Impactos con más de 100 heridos o fallecidos | 12 | 0 |
| Impactos vigentes | 6.292 | 6.262 |

Entre los retirados, los seis del encargo: EODI-IG-2025-00179 (Rozdolne), EODI-IG-2025-00165,
EODI-IG-2026-03500 (premio póstumo a dos periodistas), EODI-IG-2026-00059, EODI-IG-2026-03471
(despedida de militares en Lviv) y EODI-IG-2026-00068. Los demás son memorias de Меморіал en
Donetsk, obituarios de civiles (Mariúpol 2022, Malotaranivka 2023) y un aviso de baños en Odesa
(«на водоймах Одеської області загинули 15 людей»).

Fallecidos y heridos de los impactos vigentes por trimestre (por el día del ataque, o el de la
publicación si el mensaje no lo da):

| Trimestre | Fallecidos antes | Fallecidos después | Heridos antes | Heridos después |
| --- | ---: | ---: | ---: | ---: |
| 2024 T4 | 4.048 | 0 | 0 | 0 |
| 2025 T1 | 2.100 | 12 | 2.313 | 93 |
| 2025 T2 | 526 | 23 | 660 | 264 |
| 2025 T3 | 50 | 16 | 138 | 87 |
| 2025 T4 | 4.152 | 14 | 490 | 156 |
| 2026 T1 | 34 | 24 | 368 | 200 |
| 2026 T2 | 6.100 | 28 | 298 | 168 |
| 2026 T3 | 195 | 43 | 487 | 321 |
| 2026 T4 | 71 | 4 | 63 | 4 |

La fila 2024 T4 eran homenajes fechados por el año de la muerte. Las víctimas que quedan son las
que una frase de drones atribuye a un único lugar: es una cota inferior de las víctimas de los
ataques con drones, no el total de cada región.

### Pruebas añadidas

`tests/test_victimas_guerra.py`: los seis mensajes reales (no son impactos y no dan un año como
víctimas), año en la frase, más de 100 solo con la cifra pegada al verbo, edades y ganado,
acumulados y misiles en el mismo mensaje, condolencia dentro de un parte, corrección de lo
guardado (retira el homenaje con su motivo, corrige la cifra, deja historial, una sola vez) y
relectura que corrige la cifra.

## Bloque 2. Impactos concentrados en Zaporiyia

### Diagnóstico región por región

Para cada región: si su administración está en `configuracion/canales_guerra.json`, cuántas
publicaciones con drones guardaba el lector en el servidor (todas con el histórico desde enero de
2025 completo), cuántas tenían registro en la base (las que llegaron al analizador) y cuántos
impactos localizados había.

| Región | Canal | Publicaciones guardadas | Con registro en la base | Impactos | Dónde se perdía |
| --- | --- | ---: | ---: | ---: | --- |
| Zaporiyia (UA-23) | `zoda_gov_ua` | 2.589 | 2.589 | 5.444 | — (su histórico terminó antes del único reproceso) |
| Dnipropetrovsk (UA-12) | `adm_dp` | 1.592 | 1.592 | 201 | Localización: nombra comunidades («Марганецькій, Покровській громадам») y distritos («Нікопольщина»), no pueblos |
| Donetsk (UA-14) | `DonetskaODA` | 1.396 | 1.396 | 92 | La mitad de sus publicaciones con drones son memoria de caídos (bloque 1); el resto, avisos y partes sin arma |
| Járkov (UA-63) | `kharkivoda`, `synegubov` | 3.472 | 22 | 7 | Recogida horaria: el histórico llegó después del reproceso y nunca se leyó |
| Jersón (UA-65) | `khersonskaODA` | 4.375 | 34 | 3 | Recogida horaria (igual) |
| Sumy (UA-59) | `Sumy_news_ODA` | 1.854 | 7 | 0 | Recogida horaria, y localización: solo da comunidades, nunca pueblos |
| Odesa (UA-51) | `odesaoda` | 462 (desde junio de 2025) | 99 | 12 | Recogida horaria; además el canal casi nunca nombra lugares («на півдні Одещини», «по Одеському району») |
| Kiev ciudad (UA-30) | `VA_Kyiv` | 1.538 | 37 | 3 | Recogida horaria |
| Kiev región (UA-32) | `kyivoda` | 3.113 | 220 | 1 | Recogida horaria; la mayoría son avisos de alarma |
| Poltava (UA-53) | `poltavskaoda` | 1.381 | 62 | 0 | Recogida horaria; publica pocos lugares |
| Jmelnitski (UA-68) | `khmelnytskaODA` | 311 | 311 | 2 | Publica avisos y daños sin lugar |
| Mykoláiv (UA-48) | — | — | — | 0 | No había canal: el de 2022 (`mykolaivskaODA`) está hoy en venta |
| Chernígov (UA-74) | — | — | — | 0 | No había canal |

**Causa principal.** La recogida horaria solo leía las publicaciones con número mayor que su
cursor o de las últimas 12 horas. El lector (temporizador del minuto 50) recorre el histórico
hacia atrás, por debajo del cursor, así que todo lo que añadía después no lo leía nadie hasta un
reproceso a mano. El único se hizo el 1 de octubre, cuando solo Zaporiyia, Dnipró, Donetsk y unas
pocas más tenían el histórico completo: de 36.443 publicaciones guardadas, 16.137 tenían registro.
La segunda causa es la localización: Sumy y Dnipró nombran comunidades («громада»), que el
nomenclátor no resolvía como lugar.

### Cambios

- **Recogida horaria en dos pasadas** (`recogida/guerra.procesar`): primero lo nuevo de todos los
  canales; después, con lo que quede del tope (como mucho 150 s), las publicaciones sin registro
  (histórico añadido después) y las leídas con otra versión del analizador o del nomenclátor. Un
  cambio de reglas llega así solo a todo lo guardado, poco a poco, sin reproceso a mano ni trabajo
  aparte en el servidor.
- **Comunidades como lugar** (`Nomenclator.unidades_en`): «Краснопільська громада», «Марганецькій,
  Покровській та Мирівській громадам», en cualquier caso, con el nivel nuevo `comunidad`: el punto
  es la localidad que da nombre a la comunidad y el radio abarca sus localidades (como mucho 50 km).
  Dos comunidades del mismo nombre se deshacen con el distrito del mensaje («Нікопольщина»). Los
  distritos solo valen si abarcan 50 km o menos (15 de 137): los de 2020 miden 50–105 km de radio y
  no son un lugar concreto. La localidad que nombra el mensaje gana a su comunidad. Esquema 1.9.0
  ampliado (`lugar.nivel`) y validación de la web.
- **Distrito en «-щина»** como pista para los homónimos («в Пушкарях на Новгород-Сіверщині»).
- **Líneas por lugar con varias armas** («Краснопільська громада: … обстріли БпЛА (3 вибухи), пуски
  КАБів»): la línea dice que el dron alcanzó ese lugar.
- **Parte de la frontera de Sumy** («Ситуація на прикордонні», «Протягом дня росіяни…»): es un
  parte diario, como el de Zaporiyia (se publica y se exporta; no se dibuja).
- **Nombres compuestos**: «Хутір-Михайлівська громада» no es el pueblo «Хутір».
- **Canales nuevos**: Chernígov (`chernigivskaODA`, su descripción enlaza cg.gov.ua), Mykoláiv
  (`mykolaiv_ova`, anunciado el 17 de julio de 2026 por el canal oficial del anterior jefe de la
  administración como el nuevo canal operativo) y Kursk (`Hinshtein`, enlazado desde el canal del
  Gobierno de la región, `kurskadm`, con insignia de verificado). El lector baja su histórico desde
  enero de 2025 en el temporizador del minuto 50, como el de los demás.
- **Segunda y última tanda del lote del histórico** (`guerra:lote_historico:2`): cuando el histórico
  de todos los canales y la relectura terminan, lo que el código no resuelve de las regiones
  recuperadas va al extractor por lotes, dentro del mismo presupuesto único de 5 USD (gastados 0,66
  en la primera tanda).
- Versión del analizador `mensajes-guerra/4`.

### Cifras

Lectura con el analizador nuevo de todo lo guardado en el servidor (copia del 4 de octubre a las
08:41). «Días con parte»: días en que la administración publica un parte de 24 horas.

| Región | Impactos antes | Impactos después | De ellos dibujados (no parte diario) | Días con parte | … con algún impacto localizado |
| --- | ---: | ---: | ---: | ---: | ---: |
| Zaporiyia | 5.444 | 6.708 | 400 | 617 | 561 (91 %) |
| Sumy | 0 | 2.999 | 524 | 627 | 534 (85 %) |
| Jersón | 3 | 2.111 | 2.109 | 552 | 468 (85 %) |
| Járkov (dos canales) | 7 | 1.816 | 716 | 525 | 358 (68 %) |
| Dnipropetrovsk | 201 | 627 | 598 | 77 | 44 (57 %) |
| Kiev ciudad | 3 | 192 | 192 | 8 | 3 |
| Odesa | 12 | 84 | 84 | 4 | 1 |
| Donetsk | 92 | 66 | 51 | 15 | 6 |
| Luhansk | 0 | 78 | 34 | 442 | 41 |
| Kiev región | 1 | 31 | 31 | 11 | 1 |
| Poltava | 0 | 26 | 26 | 10 | 0 |
| Jmelnitski | 2 | 2 | 2 | 1 | 0 |

Zaporiyia pasa de 5.444 de 5.793 impactos rusos localizados (94 %) a 6.708 de 14.823 (45 %). Odesa
tiene impactos en 74 de los 269 días en que publica algo de drones: su administración casi nunca
nombra el lugar, por política propia. Mykoláiv y Chernígov empiezan a contar cuando el lector baje su
histórico (unas horas desde la fusión).

Sentido contrario: los gobernadores rusos con parte diario son Briansk (gobierno regional: 92 días
con parte, 42 con lugar) y, desde ahora, Kursk. Los demás publican cada ataque por separado.

### Pruebas añadidas

`tests/test_partes_regionales.py`: base de la comunidad en todos sus casos, comunidad como lugar con
su centro y su alcance, la localidad gana a su comunidad, línea por lugar con varias armas, parte de
la frontera de Sumy, nombre compuesto, histórico que llega después del cursor y relectura con una
versión nueva del analizador.

## Bloque 3. Zonas de lanzamiento duplicadas por grafía

### Causa

El parte de la Fuerza Aérea escribe la misma zona de varias formas («Міллерово», «Міллєрово»,
«Мілерово», «Міллерево»; «Шаталово» y «Шаталове»; «Донецьк», «Донецьк - України», «Донецької
обл», «Донеччини») y el lector guardaba en `zonas_lanzamiento` lo escrito tal cual: 85 nombres
distintos en 4.611 ataques, que contaban como zonas distintas. Además dos zonas sin coma («Чауда
Гвардійське») eran una sola, y entraban como zona restos de otras frases («двома – Х-59/Х-69»,
«через Сумську»).

### Cambios

- **Tabla de nombres normalizados**, `configuracion/zonas_lanzamiento_nombres.json`, enlazada con el
  catálogo del motor de deducción (`configuracion/zonas_lanzamiento.json`): cada nombre normalizado
  lleva sus zonas del catálogo, y las raíces del catálogo más las variantes vistas en los partes
  («міллерев», «чуада», «донеччин»…). Las direcciones genéricas sin emplazamiento («Крим»,
  «Курська область», «Брянська область», «Краснодарський край», «Азовське море», «Каспійське
  море») se conservan como tales: no tienen punto ni crean zona. Una dirección solo cuenta si el
  nombre no da una zona concreta («Чауда – окупований Крим» es Чауда).
- `proceso/zonas_lanzamiento.py`: compara sin distinguir «є» de «е» ni el tipo de guion; un
  nombre puede dar dos zonas; lo que no es una zona (misiles, rutas, regiones de Ucrania) se
  descarta con su motivo; lo que no se reconoce va al **registro de revisión** (cursor
  `zonas_lanzamiento:revisar` de la base: nombre, cuántos ataques lo citan y uno de ejemplo), nunca
  como zona nueva.
- **Los partes nuevos** guardan la zona normalizada en `zonas_lanzamiento` y lo escrito en
  `zonas_lanzamiento_citadas` (interno, esquema 1.9.0 ampliado).
- **Los ataques guardados** se normalizan una vez por versión de la tabla en la recogida horaria
  (cursor `zonas_lanzamiento`), con su motivo en el historial; lo escrito pasa a
  `zonas_lanzamiento_citadas`.
- **Motor de deducción y corredores de la web**: los dos casan el nombre con la zona por las raíces
  del catálogo (`Zona.nombra` y `nombra` en `web/src/datos/guerraSatelite.ts`, la misma regla). Un
  test comprueba que cada nombre normalizado casa exactamente con sus zonas del catálogo y que las
  direcciones genéricas no casan con ninguna (salvo «Крим», que no tiene raíz en el catálogo y no
  casa con nada).

### Cifras

| | Antes | Después |
| --- | ---: | ---: |
| Nombres de zona distintos en los ataques | 85 | 24 (18 zonas del catálogo y 6 direcciones) |
| Ataques con zonas cambiadas | — | 305 |
| Nombres en el registro de revisión | — | 3: «Бєлгород», «Маріуполя» y «Шахти», un ataque cada uno |

Las más citadas, ya juntas: Приморсько-Ахтарськ 705 ataques, Курськ 643, Орел 549, Міллерово 521
(antes repartida en 7 grafías), Брянськ 381, Гвардійське 278, Чауда 257, Шаталово 183,
Донецьк 165.

### Pruebas añadidas

`tests/test_zonas_lanzamiento.py`: las grafías de los partes (las del encargo y las dobles), lo que
no es una zona y lo desconocido, que cada nombre normalizado casa con sus zonas del catálogo, y la
corrección de los ataques guardados con su registro de revisión y su historial.

## Bloque 4. Cruces de frontera sin enlazar

### Causa

Los cruces de un ataque solo salían de lo que declara el parte de la Fuerza Aérea («перетнули
кордон з Румунією»), y casi nunca lo declara: 6 ataques tenían `cruces`, cinco de ellos hacia
Bielorrusia. Las incursiones europeas en países fronterizos (262 incidentes vigentes en Rumanía,
Moldavia, Polonia, Lituania, Letonia, Estonia, Bulgaria, Eslovaquia y Hungría) no sabían de qué
ataque eran.

### Cambios

- **Enlace en la recogida horaria** (`proceso/cruces.py`, después de rehacer partes e incidentes):
  una incursión o un sobrevuelo de drones en un país fronterizo se enlaza con el ataque ruso de la
  Fuerza Aérea (sin los tramos ya sumados en otro) cuyo periodo contiene su inicio, con margen
  según la precisión de la hora (si solo se sabe el día, la noche que acaba ese día):
  - **por la fuente**: la incursión sale del propio parte del ataque o la fuente la relaciona con
    el ataque contra Ucrania («durante ataque a Ucrania», «atacul … asupra Ucrainei»);
  - **por la fecha**: coincide en fecha y viene de Ucrania: la fuente lo dice («din Ucraina»,
    «from Ukraine») o, en Rumanía y Moldavia (que solo reciben drones del ataque a través de
    Ucrania), el dron es de un Estado, entró desde fuera o la fuente dice que es ruso.
- **Lo que no se enlaza**: lo que viene de Bielorrusia («procedente de Bielorrusia», «from
  Belarus»), los globos de contrabando, los drones ucranianos (salvo un Shahed mal atribuido), los
  drones en el puerto de Constanza o en el mar sin una fuente que los relacione con el ataque, y,
  fuera de Rumanía y Moldavia, lo que el titular no da como dron ruso o venido de Ucrania (las
  fuentes de esos incidentes mezclan titulares de otros sucesos).
- **Los dos sentidos**: el incidente lleva `ataque` (id, noche con la regla única de las noches,
  `proceso/ataques.jornada`, y por qué se enlaza) y el ataque lista los incidentes en el cruce de
  su país (`cruces[].incidentes`); si el parte no declaró ese cruce, se añade con el número de
  drones del incidente. Lo que declaró el parte queda en `cruces_parte` (interno), para rehacer los
  cruces cada hora. Solo se guarda lo que cambia, con su motivo en el historial. Esquema 1.9.0
  ampliado y lista cerrada de campos públicos.
- **Web**: la ficha del incidente dice «Parte del ataque ruso contra Ucrania de la noche del X al
  Y», con el enlace al ataque y el motivo; la del ataque lista sus cruces con el enlace a cada
  incidente.

### Cifras

| | Antes | Después |
| --- | ---: | ---: |
| Ataques con `cruces` | 6 | 77 (72 con incidentes enlazados) |
| Incursiones europeas enlazadas con su ataque | 0 | 123 |
| … por la fuente / por la fecha | — | 45 / 78 |
| … por país | — | Rumanía 66, Moldavia 50, Polonia 4, Lituania 2, Letonia 1 |

Quedan sin enlazar 139 incidentes de esos países: los de Lituania y Letonia que vienen de
Bielorrusia o son globos, los drones marinos y ucranianos de Constanza, cierres de aeropuertos sin
relación con un ataque y sucesos de día sin ataque en curso.

### Pruebas añadidas

`tests/test_cruces.py`: la noche de un parte con la misma regla que la web, enlace por la fuente y
por la fecha, lo que no se enlaza (Bielorrusia, globos, drones ucranianos y marinos, Letonia sin
dron ruso), los dos sentidos en la base con su historial y sin escrituras repetidas.

## Bloque 5. Partes del mismo día

### Causa

El Ministerio de Defensa ruso publica de media 3,3 partes al día: tramos de la tarde («В период с
21.00 до 22.00 мск … три»), el de día y, por la mañana, el de toda la noche. Ese parte de la noche
no escribía las horas hasta 2026 («В течение прошедшей ночи … 50») y la regla de solapes lo
tomaba como contiguo al último tramo, así que la noche y sus tramos se sumaban; desde 2026 escribe
las horas («В течение прошедшей ночи с 20.00 мск 3 октября до 8.00 мск 4 октября … 559») y se ve
que cubre la noche entera. Solo 6 partes rusos llevaban `incluido_en`. Además, cinco partes de la
Fuerza Aérea guardaban mal su periodo (año equivocado, «Увечері 11 лютого» leído desde la medianoche,
noches publicadas tarde con el fin a la hora de publicación) y la noche de cada parte solo la
calculaba la web.

### Cambios

- **Parte de toda la noche** (`proceso/solapes.py`): el parte «В течение прошедшей ночи» sin horas
  cubre la noche desde las 20.00 de Moscú; si sus cifras no son menores que las de los tramos de esa
  noche publicados antes, en conjunto y región a región, es su total y los tramos quedan
  `incluido_en`. Los partes de día y de noche de la Fuerza Aérea se solapan una o dos horas pero
  cuentan cosas distintas: siguen sumándose los dos (la regla de solapes solo se aplica al
  ministerio ruso, como antes).
- **Periodos comprobados** (`proceso/periodos.py`, en cada recogida horaria, con su motivo en el
  historial): año equivocado del parte, ataque que empieza la tarde del día que escribe el parte,
  noche publicada tarde que acaba por la mañana.
- **Partes de resumen** (`resumen`, público): una semana, desde el inicio o más de dos días; nunca se
  suman con los diarios (ni en los datos ni en la web). Los resúmenes del ministerio ruso («Главное
  за день», «Итоги недели») ya se descartaban al leerlos y no hay ninguno guardado.
- **La noche de cada ataque en los datos publicados** (`jornada` en `ucrania.json`, con
  `proceso/ataques.jornada`): la misma regla que la web unificó en el PR #90 (`jornada` de
  `web/src/datos/ucrania.ts`): noche si el periodo acaba un día UTC después del que empieza, día si
  empieza y acaba el mismo día. Un fichero de casos compartido (`tests/fixtures/jornadas.json`) lo
  comprueban los tests de los dos lados, y un test de la web comprueba que la noche publicada de
  cada ataque es la que calcula la web.

### Cifras

| | Antes | Después |
| --- | ---: | ---: |
| Partes rusos con `incluido_en` | 6 | 78 |
| Partes rusos con `solapado_con` | 10 | 9 |
| Partes con el periodo corregido | — | 5 |
| Partes de resumen | 0 | 0 |

Media diaria de drones que el Ministerio de Defensa ruso dice haber derribado, por trimestre (cada
parte en su noche o su día, sin los tramos incluidos en otro):

| Trimestre | Antes | Después |
| --- | ---: | ---: |
| 2023 T3 | 5,3 | 5,3 |
| 2023 T4 | 7,7 | 7,7 |
| 2024 T1 | 11,2 | 11,2 |
| 2024 T2 | 18,9 | 18,6 |
| 2024 T3 | 24,6 | 24,3 |
| 2024 T4 | 33,7 | 32,3 |
| 2025 T1 | 44,1 | 43,8 |
| 2025 T2 | 75,9 | 75,9 |
| 2025 T3 | 91,8 | 91,5 |
| 2025 T4 | 122,6 | 122,6 |
| 2026 T1 | 173,4 | 173,4 |
| 2026 T2 | 292,4 | 292,4 |
| 2026 T3 | 502,3 | 502,3 |

La corrección pesa sobre todo en 2024 (hasta un 4 %): desde mediados de 2025 el ministerio apenas
publica tramos sueltos de la tarde.

### Pruebas añadidas

`tests/test_partes_del_dia.py` y `web/tests/jornadas.test.ts`: la misma noche en los dos lados con
los casos compartidos, la noche de cada ataque publicado, el parte de toda la noche que incluye el
tramo de la tarde (y no lo incluye si el tramo dice más), los periodos mal guardados con los partes
reales y el parte de resumen que no se suma.

## Bloque 6. Pendientes de la revisión de presencia de dron

### Siete incidentes con una noticia de «otra vez» sin separar

Medidos con la hora de la fuente frente a la hora del suceso (la regla separa cuando la noticia de
repetición se publica 18 horas o más después del suceso, es decir, pasada su noche):

| Incidente | Lo que dice la fuente | Resultado |
| --- | --- | --- |
| EODI-2025-00066, Volkel | Suceso el 21 de noviembre a las 19:00; el 23 a las 09:45 «Another mystery drone sighted over … Volkel» y a las 11:30 «Wéér drones bij vliegbasis Volkel» | **Otra noche**: esas grafías no estaban entre las palabras de repetición. Se añaden («another mystery drone», «another unidentified drone», «wéér») y la corrección única de la recogida separa el candidato; la parte nueva se extrae en la recogida horaria (va delante en el extractor) |
| EODI-2025-00136, Zaventem | Cierre a las 21:45; a las 06:30 «rond middernacht opnieuw even gesloten» | La misma noche (8 h 45 min después del suceso): un solo incidente |
| EODI-2026-00293, Zaventem | Su única noticia es la de «Erneut Drohne … gesichtet» | Es la repetición misma, ya separada de la anterior: nada que separar |
| EODI-2025-00228, Aalborg | Ninguna noticia de repetición del suceso (la marca venía de «Paar dagen na Kopenhagen») | Un solo incidente |
| EODI-2025-00335, Bruselas | Las de «opnieuw», «for third time in a week» y «à nouveau» son de la misma tarde y noche del 6 de noviembre | La misma noche |
| EODI-2025-00072, Bruselas | Noticias del 10 de noviembre sobre la intrusión anterior, sin repetición | Un solo incidente |
| EODI-2026-00116, Berlín | «Dron opäť zastavil letisko v Berlíne» a las 05:00, 11 horas después del cierre | La misma noche |

### Cierre de una pista (Schiphol)

`proceso/presencia.cierre_de_pista`: un suceso en un aeropuerto sin cierre registrado cuya fuente
cuenta que se cerró o se suspendió una pista por un dron («закрыта», «приостанавливал работу
взлетно-посадочной полосы», «runway», «Landebahn», «baan») se registra como cierre y como
interrupción del aeropuerto, con su motivo en el historial. Con el cierre, la autoridad del
aeropuerto actúa por el dron y la presencia queda confirmada con la regla vigente (salvo que la
autoridad lo deje abierto). Las palabras de cierre en ruso y ucraniano se añaden a la regla del
cierre en la frase. EODI-2025-00058 pasa a «Drones cierran una pista del aeropuerto de Ámsterdam
Schiphol», dron confirmado; el mismo cambio alcanza a EODI-2026-00065 (Múnich). La corrección única
de la recogida (criterio de presencia, versión `presencia/2`) lo aplica a todo lo guardado.

### Alturas de UK Airprox y de los informes de investigación

Los 967 encuentros de la UK Airprox Board guardados traen su altura (en pies: 861 sin referencia,
96 en nivel de vuelo, 10 sobre el terreno) con origen oficial y método por código; 60 documentos de
investigación dan la altura de 61 sucesos con su frase y su confianza, y cuando el suceso es un
incidente del observatorio la altura llega a `drones.altura_m` (proceso/detalle.py). Lo que faltaba
era que el motor de deducción la usara:

- **Regla de altura** (`R9`, `proceso/deduccion/reglas.py`): una clase cuyo techo (altitud máxima
  sobre el nivel del mar, de todos sus modelos con dato fiable) queda por debajo de la altura
  observada, con un 10 % de margen, queda descartada. Una altura sobre el terreno nunca es mayor que
  la altitud sobre el mar, así que pasar el techo descarta con cualquier referencia. Solo descarta
  con altura oficial; con la de la prensa queda como condición.
- **Los encuentros como casos del motor** (`motor.caso_de_encuentro`, tipo `encuentro` en la tabla
  `deducciones`), con su punto, su hora y su altura en metros. Los incidentes con encuentros
  enlazados toman también su altura.
- Medido sobre la base: 6 de los 967 encuentros quedan con clases descartadas por altura (los de
  6.000 metros o más: ala fija táctica eléctrica, multirrotores pequeños y pesados).

### Pruebas añadidas

`tests/test_pendientes_presencia.py`: la otra noche de Volkel, la reapertura de la misma noche en
Zaventem que no se separa, el cierre de la pista de Schiphol que confirma la presencia, la altura
oficial de un encuentro que descarta clases y la de la prensa que no.

## Bloque 7. Dos fuentes españolas

### 7.1 Cifras oficiales agregadas de España

Van en `configuracion/cifras_contexto.json` y en la exportación semanal interna
(`contexto_pais.jsonl`, con su esquema propio y su origen por valor): son contexto de país, nunca
incidentes, y ningún recuento de incidentes las lee. Cada enlace se comprobó el 4 de octubre de 2026:

| Periodo | Categoría | Cifra | Publicador | Origen | Comprobación |
| --- | --- | ---: | --- | --- | --- |
| 2019 | Incidencias con drones en aeropuertos de Aena | 132 | Gobierno (respuesta 184/001553) | oficial | PDF del Congreso, 200 |
| 2020 | ídem | 58 | ídem | oficial | ídem |
| 2021 | ídem | 68 | ídem | oficial | ídem |
| 2022 | ídem | 74 | ídem | oficial | ídem |
| 2023 (hasta el 26 de noviembre) | ídem | 80 | ídem | oficial | ídem |
| 2019-2023 | Incidencias con afección a las operaciones | 8 de 412 (menos del 2 %) | ídem | oficial | ídem |
| 2020 (una semana) | Vuelos de drones detectados por SIGLO-CD | 112 | Guardia Civil / Ministerio del Interior | oficial | interior.gob.es responde 403; copia del archivo de Internet |
| 2023 (Cumbre de Granada) | Drones detectados | 47 (11 en Málaga y 36 en Granada) | Interior y Defensa | oficial citado en prensa | elradar.es, 200 |

Cambios frente a la tabla del encargo, con su prueba:

- **Respuesta parlamentaria original encontrada**: pregunta escrita 184/001553 de Jon Iñarritu (EH
  Bildu), contestada el 19 de diciembre de 2023 (BOCG, Congreso, serie D, núm. 64, de 15 de enero
  de 2024); texto en https://www.congreso.es/entradap/l15p/e0/e_0006966_n_000.pdf. Las seis cifras
  de Aena pasan a origen **oficial** con ese enlace. La de 2023 llega hasta el 26 de noviembre, y
  la de afección es exacta: 8 de 412.
- **El enlace de Europa Press del encargo responde 404**; la noticia está en
  https://www.europapress.es/nacional/noticia-aeropuertos-registran-80-incidencias-drones-2023-solo-dos-afectacion-operaciones-20240121133353.html.
  Ya no hace falta como origen.
- **Los 112 vuelos de SIGLO-CD son de una semana de febrero de 2020**, no de 2022: la nota de
  Interior es del 22 de febrero de 2020 («Este sistema ha detectado en la última semana 112 vuelos
  de RPAS»). La dirección del encargo y la real responden 403 al acceso automático (protección de la
  web de Interior); se comprobó en la copia del archivo de Internet del 19 de mayo de 2025.

### 7.2 Lector de la Guardia Civil

`recogida/guardia_civil.py`, fuente de detalle `guardia_civil` (fiabilidad A, grupo de
investigaciones), con el mismo tratamiento que las demás: el temporizador de las fuentes de detalle
recoge, la recogida horaria extrae la nota y la cruza con los incidentes.

- **Sin canal RSS que funcione**: la página de canales solo enlaza un Atom que responde 404. Se leen
  la lista de noticias (10 por página) y el buscador general con cada palabra (dron, drones, RPAS,
  UAS, aeronave no tripulada, PEGASO, antidron), y la nota completa de las candidatas. Sin
  robots.txt (404); identificación del observatorio y 3 s entre peticiones.
- **Qué es incidente**: un dron que sobrevuela o entra en una instalación (aeropuerto, base, cárcel,
  puerto, central, estadio, edificio oficial, evento); los de las cárceles cuentan aunque lleven
  droga. **Se descartan** las redes de contrabando con drones, el uso de drones por la propia
  Guardia Civil (equipos PEGASO, despliegues) y la divulgación (proyectos, jornadas).
- **Confirma y da de alta**: una nota que corresponde a un incidente de la prensa se une a él y lo
  confirma (cruce de las fuentes de detalle); una que no encaja con ninguno da de alta un incidente
  (`extraccion_oficial.FUENTES_ALTA`).
- **Condiciones de reutilización**: el aviso legal de web.guardiacivil.es limita el uso a la
  descarga y el uso privado y pide autorización a la Dirección General para cualquier otro; no cita
  la Ley 37/2007. Se guardan título, fecha, enlace, atribución y los pasajes sobre drones (nunca la
  nota entera) y se publica solo el enlace, la atribución y una frase breve citada.

**Histórico de 2024 a hoy**: la lista de noticias (912 notas, de 2019 a octubre de 2026) y el
buscador dan 8 notas que nombran drones; ninguna es un incidente: dos proyectos europeos y
seguridad de la Vuelta (divulgación y uso propio), búsquedas con el equipo de drones de la
Guardia Civil, una operación contra el narcotráfico y un creador de contenido denunciado en el
Parque Regional de Gredos (espacio natural, no instalación). Por eso hoy ningún incidente español
procede de la Guardia Civil; el lector queda en la recogida y entrará la primera nota que cuente
una intrusión.

### Pruebas añadidas

`tests/test_fuentes_espana.py`: las cifras de contexto validan con su esquema, con su origen y con
la respuesta del Congreso como fuente de Aena; la lista de noticias; qué es incidente y qué no
(con las notas reales descartadas); el registro como fuente oficial de detalle que da de alta.

## Incidencia: la base pasó de 100 MiB y la recogida de las 12:17 no publicó

**Causa.** GitHub rechaza cualquier fichero de más de 100 MiB (104.857.600 bytes). El `db.age` de
la rama `estado` de las 11:34 ocupaba 104.290.885 bytes; la recogida de las 12:17 leyó 6.265
publicaciones de guerra (2.687 nuevas, la recuperación del bloque 2) y enlazó 200 cruces, la base
creció por encima del límite y el `git push` de `almacen/remoto.subir` falló: «la recogida falló con
código 1: no se publica». Nada se perdió: la recogida siguiente parte de la base de las 11:34 y
vuelve a leer lo mismo, porque los cursores viven dentro de la base. La base sin comprimir mide
1.013 MB; con gzip 9 seguiría en 102 MB, así que subir la compresión no bastaba.

**Cambios.** Dos arreglos que se suman. Otra sesión cambió la compresión a xz (#106,
`almacen/cifrado.py`): la base pasa a unos 50 MB. Este trabajo (#107, fusionado a las 12:47) hace
que `almacen/remoto.subir` la guarde en trozos de 50 MB (`db.age.000`, `db.age.001`…) y que
`descargar` los vuelva a unir, para que el crecimiento no vuelva a chocar con el límite; una rama
con el `db.age` entero de antes se sigue leyendo. Todos los lectores de la rama (recogida horaria,
deducción, detalle, catálogo, exportación, búsqueda dirigida, satélite) pasan por esas dos
funciones, y cada trabajo del servidor toma `main` al empezar. Pruebas en `tests/test_remoto.py`:
base grande en tres trozos que se vuelven a unir, tamaño justo y vacío, y lectura de la rama
antigua.

**Comprobación.** La recogida de las 13:17 terminó a las 13:34 («base subida a la rama estado»,
«estado.json publicado en el almacén»), con 6.159 publicaciones de guerra leídas y 2.402 impactos
nuevos. La rama `estado` tiene un solo trozo, `db.age.000`, de 49.644.381 bytes, y se abre y se
lee entera.

## Cruces convertidos en incidentes duplicados

**Causa, en una línea.** `proceso/incursiones.registrar` daba de alta un incidente «Drones del
ataque ruso contra Ucrania cruzan a …» por cada cruce de un ataque, y desde el bloque 4 los
cruces de un ataque incluyen los países de las incursiones europeas enlazadas: cada incidente
enlazado volvía en la recogida siguiente como copia con el parte como única fuente.

El mecanismo era anterior (EODI-2024-00001, alta del 28 de septiembre, salió de un cruce que sí
declaraba el parte); el enlace del bloque 4 lo disparó en masa el 4 de octubre: 76 altas nuevas,
todas con una pareja del mismo país enlazada con el mismo ataque.

**Cambios (#112).**

- Enlazar nunca crea un incidente. `incursiones.registrar` desaparece; `incursiones.retirar` retira
  las altas que salían solo del parte (versiones `incursion/1` y `/2`) con su motivo: duplicado del
  incidente del mismo país y noche (el enlace con el ataque queda en él), cruce declarado solo por
  Ucrania o sin cruce en el parte. La Fuerza Aérea de Ucrania no es autoridad sobre el espacio
  aéreo de otro país: su parte no confirma por sí solo un dron en Rumanía o en Moldavia.
- Un cruce que cuenta solo el parte queda dentro del ataque (`cruces` y `cruces_parte`) con la
  frase literal que lo dice (`cruces[].frase`, campo nuevo del esquema 1.11.0). El lector la guarda
  desde ahora (`recogida/parte.py`, `frases_cruces`); las de los seis partes guardados antes están
  en `configuracion/frases_cruces.json`, copiadas del canal oficial. La ficha del ataque lo muestra
  como «Declarado por Ucrania; sin incidente del país», con la frase. No cuenta en el total europeo
  ni por país, ni en la capa de presión.
- Pasa a incidente europeo solo si lo cuenta una fuente del país afectado: entra por las noticias o
  las fuentes oficiales y `proceso/cruces.py` lo enlaza.
- **La cita tiene que respaldar el titular** (`proceso/cita_titular.py`): alguna cita guardada debe
  nombrar el país, el lugar o un nombre propio del titular. Un incidente cuyas fuentes son solo
  partes de guerra y no pasa la comprobación no se publica (`exportacion/geojson.publicables`).

**Revisión uno por uno de las 77 altas desde el parte** (75 de Rumanía y Moldavia, 2 de Polonia;
ninguna otra de nivel país tenía un parte de guerra como única fuente, en ningún país):

| Resultado | Incidentes |
| --- | ---: |
| Duplicado de otro del mismo país y la misma noche: retirado, el enlace queda en el bueno | 76 |
| Sin pareja, el parte dice el cruce (kpszsu/20107, «Один безпілотник увійшов в повітряний простір Румунії»): retirado, queda como cruce declarado por Ucrania en EODI-UA-2024-0174 | 1 (EODI-2024-00001) |
| Sin pareja y sin cruce en el parte | 0 |

EODI-2025-00378 (Borcea), EODI-2025-00222 y EODI-2025-00260 siguen publicados, enlazados con
EODI-UA-2025-0028, -0032 y -0046, y esos ataques los listan como cruces.

**Comprobación de cita y titular en toda la base** (sin cambiar nada fuera de este encargo): de los
515 incidentes publicados tras la retirada, 73 no la pasan. Arreglo pendiente para cada tipo: (A)
guardar como cita la frase de la nota que nombra el lugar, cuando la tiene; (B) comparar también
los nombres del lugar en otras escrituras; (C) revisar a mano si la cita es de otro suceso.

Agrupados por tipo de fallo, con su titular y la primera cita guardada:

**A. La cita cuenta el hecho sin nombrar el país ni el lugar** (54)

| Incidente | Titular | Cita |
| --- | --- | --- |
| EODI-2025-00013 | Dos turistas detenidos por volar dron cerca del aeropuerto de Bardufoss | «To turister innbrakt etter mistanke om ulovlig droneflyvning.» |
| EODI-2025-00034 | Dron interrumpe el aeropuerto de Vilna sin que se identifique su propietario | «jei dronas, pavyzdžiui, priklausė privačiam asmeniui» |
| EODI-2025-00059 | Hombre detenido por volar dron en zona prohibida del aeropuerto de Sandefjord | «Mannen har fløyet innenfor sikkerhetssonen til flyplassen.» |
| EODI-2025-00065 | Cinco drones perturban el tráfico aéreo en el aeropuerto de Dresde | «In den ersten neun Monaten dieses Jahres sichteten Piloten und Tower-Mitarbeiter bereits fünf unerlaubte Fluggeräte.» |
| EODI-2025-00088 | Drones no autorizados retrasan vuelos en el aeropuerto de Gibraltar | «tras la detección de drones no autorizados» |
| EODI-2025-00091 | Sobrevuelos sospechosos sobre la base de Kleine Brogel en Bélgica | «mai multe zboruri suspecte ale unor aparate neidentificate» |
| EODI-2025-00102 | Globos meteorológicos cierran el aeropuerto de Vilna | «Uosto uždarymas paveikė apie 5 tūkstančius keleivių ir 30 skrydžių» |
| EODI-2025-00114 | Posibles drones observados sobre el aeropuerto de Riga | «Katru nedēļu manai mājai pāri pārlido kāds drons» |
| EODI-2025-00119 | Dron no identificado obliga a cerrar el aeropuerto de Gibraltar | «La presencia de un dron obligó en la noche del sábado a cerrar por precaución el aeropuerto» |
| EODI-2025-00132 | Vuelo retrasado en el aeropuerto de Bergen por un dron no autorizado | «Avinor opplyser til NTB at flyplassen ikke ble stengt, men at én flyavgang ble holdt igjen i ti minutter.» |
| EODI-2025-00134 | Casi colisión entre un avión y un posible dron cerca del aeropuerto de Heathrow | «A passenger jet came so close to colliding with a drone that the object filled the plane's windscreen.» |
| EODI-2025-00140 | Múltiples avistamientos de drones sobre Arna, Suecia | «Ifølge stasjonssjefen skal det dreie seg om flere store droner.» |
| EODI-2025-00142 | Posible dron casi colisiona con un Airbus A320 sobre Londres | «the plane flew in clear skies at 9,200ft - far beyond the 400ft UK limit for flying drones.» |
| EODI-2025-00143 | Incidente de posible dron cerca del aeropuerto de Southampton | «a drone was involved in a near-miss with a passenger plane» |
| EODI-2025-00145 | Dron detectado en el aeropuerto de Sundsvall Timrå obliga a desviar un vuelo | «En person är nu misstänkt för vårdslöshet i flygtrafik.» |
| EODI-2025-00146 | Cierre de pista en Bergen por un dron en zona prohibida | «Det førte til at rullebanen ble stengt en kort periode.» |
| EODI-2025-00149 | Posibles drones sobrevuelan una base militar belga | «deux observations de drones au-dessus d'une base militaire» |
| EODI-2025-00150 | Investigación completada sobre posibles drones en RAF Lakenheath | «unidentified aircraft» |
| EODI-2025-00152 | Drones no identificados cerca del aeropuerto de Dublín durante visita de Zelenskyy | «generated for the purpose of putting pressure on EU and Ukrainian interests» |
| EODI-2025-00164 | Actividad de drones cerca de RAF Lakenheath causa incidente con helicóptero policial | «a drone coming close to them» |
| EODI-2025-00166 | Drones sobre el aeropuerto de Alta obligan a intervenir a la policía | «Dronepiloten vil bli anmeldt for flyvningen, ilagt et forelegg og dronen vil bli inndratt.» |
| EODI-2025-00170 | Drones ilegales sobre el aeropuerto de Riga en enero | «nelikumīgi pilotētajiem droniem» |
| EODI-2025-00184 | Drones sobre el aeropuerto militar de Bardufoss obligan a desviar vuelos | «Drohnen gesichtet worden waren» |
| EODI-2025-00202 | Posibles drones cierran el aeropuerto de Hannover y retrasan un transporte de órgano | «An die Drohnenflieger» |
| EODI-2025-00256 | Sobrevuelo de dron sobre la pólvora Eurenco de Bergerac | «C'était un drone du commerce, classique» |
| EODI-2025-00259 | Drones rusos penetran el espacio aéreo de Rumania durante ataque masivo | «tijekom masovnog ruskog napada dronovima i raketama na Ukrajinu» |
| EODI-2025-00290 | Dron entra en el espacio aéreo de Rumania y provoca el despegue de cazas de la OTAN | «tijekom ruskog napada na ukrajinsku infrastrukturu» |
| EODI-2025-00334 | Drones cierran el aeropuerto de Berlín-Brandenburg durante dos horas | «Tussen 20.08 uur en 21.58 uur heeft de luchthaven van de Duitse hoofdstad al het vliegverkeer stilgelegd.» |
| EODI-2025-00346 | Posibles drones rusos penetran en el espacio aéreo de la base aérea de Ramstein | «offenbar steckt Russland dahinter» |
| EODI-2025-00363 | Dron misterioso encontrado en la playa de Burgas | «O dronă a fost descoperită aruncată de valuri pe plaja» |
| EODI-2025-00395 | Dron ucraniano detonado cerca del Puerto de Constanza | «Ar fi vorba despre o dronă militară ucraineană cu încărcătură explozivă la bord.» |
| EODI-2025-00399 | Un dron obliga a paralizar el Aeropuerto de Lanzarote | «causó la paralización de todas las operaciones» |
| EODI-2025-00401 | Un posible dron provoca el desvío de tres vuelos en el aeropuerto de Gran Canaria | «Se produjo el avistamiento de un dron que sobrevolaba cerca del recinto aeroportuario.» |
| EODI-2026-00001 | Dron no autorizado detectado cerca del aeropuerto de Split | «39-godišnjeg njemačkog državljanina osumnjičenog za nedopušteno upravljanje dronom» |
| EODI-2026-00032 | Dron detectado en zona prohibida del aeropuerto de Vilna | «sulaikė droną bei jo operatorių» |
| EODI-2026-00047 | Turista vuela un posible dron cerca del aeropuerto de Svolvær durante el despegue de un avión | «Ein eldre mann plutseleg letta ei drone frå bakken like ved bilen.» |
| EODI-2026-00056 | Drone agricola bloquea el aeropuerto de Cuneo-Levaldigi | «Un uomo di 55 anni, agricoltore, senza licenza di volo né autorizzazione o assicurazione, ne ha fatto volare uno» |
| EODI-2026-00083 | Dron sobre el aeropuerto de Split obliga a cerrar la pista durante diez minutos | «egy 36 éves magyar állampolgárt, akit őrizetbe vettek és kihallgattak» |
| EODI-2026-00145 | Dron estrellado cerca de la base aérea de Wunstorf | «möglicherweise mit Sprengstoff bestückt» |
| EODI-2026-00154 | Posible dron detectado cerca de la frontera de Rumania en Suceava | «după detectarea unei drone în apropierea frontierei» |
| EODI-2026-00166 | Dron no autorizado vuela sobre el aeropuerto de Budapest | «egy gyártelep épületéről reptette szabálytalanul a drónját egy férfi» |
| EODI-2026-00174 | Dron derribado en el espacio aéreo de Letonia | «The incident came as Russia and Ukraine traded fresh drone strikes.» |
| EODI-2026-00189 | Dron ruso derribado sobre base aérea en Rumania | «El objetivo, un dron ruso que había traspasado a territorio aliado» |
| EODI-2026-00216 | Drones ucranianos atacan un depósito petroliero en Letonia | «două drone ucrainene au intrat dinspre Rusia și au lovit instalații petroliere» |
| EODI-2026-00242 | Un dron entra en el espacio aéreo de Rumania y se estrella en el mar | «Rrmunski vojni radari noćas su ponovno zabilježili bespilotne letjelice u blizini granice s Ukrajinom.» |
| EODI-2026-00246 | Posibles drones caídos en Letonia provocan la dimisión del gobierno de Riga | «incidentului de securitate ce a avut loc în urmă cu o săptămână» |
| EODI-2026-00253 | Dos drones militares impactan contra una base de combustible en Rēzekne, Letonia | «Divi bruņoti droni ietriecās uzņēmuma East-West Transit naftas rezervuāros.» |
| EODI-2026-00280 | Posibles drones sobre el aeropuerto de Luxemburgo obligan a cerrar el espacio aéreo | «Unbekannte Drohnen.» |
| EODI-2026-00303 | Cierre temporal del aeropuerto de Múnich por avistamiento sospechoso | «Beide Start- und Landebahnen wurden am Sonntagnachmittag für eine halbe Stunde dichtgemacht.» |
| EODI-2026-00309 | Dron estrellado cerca de la base aérea de Wunstorf | «Trümmerteile einer mutmaßlich abgestürzten Drohne» |
| EODI-2026-00379 | Dos drones rusos explotan en Moldavia | «Dronele lansate de […] Rusă reprezintă un pericol pentru cetățeni.» |
| EODI-2026-00381 | Múltiples drones de origen desconocido sobrevuelan el espacio aéreo de Moldavia | «drone de origine necunoscută» |
| EODI-2026-00389 | Dron cruza el espacio aéreo de Lituania desde Bielorrusia y obliga a cerrar el espacio aéreo | «briefly closing its airspace» |
| EODI-2026-00427 | Drones y cohetes rusos violan el espacio aéreo de Moldavia y explotan en el sur | «sâmbătă dimineața» |


**B. La cita está en otra escritura (cirílico o griego) y el nombre del lugar no se compara** (5)

| Incidente | Titular | Cita |
| --- | --- | --- |
| EODI-2025-00058 | Drones cierran una pista del aeropuerto de Ámsterdam Schiphol | «Аэропорт Схипхол приостанавливал работу взлетно-посадочной полосы из-за дрона.» |
| EODI-2025-00127 | Un dron bloquea seis vuelos en el aeropuerto de Sofía | «Собственикът на дрона, блокирал 6 полета» |
| EODI-2026-00150 | Dron caído en Leipzig causa incidente diplomático entre Alemania y Rusia | «в Лейпциге нашли какой-то там упавший беспилотник» |
| EODI-2026-00356 | Drones turcos violan el espacio aéreo griego sobre el Egeo | «Τέσσερα μη επανδρωμένα αεροσκάφη (UAV).» |
| EODI-2026-00367 | Dos drones cierran temporalmente el aeropuerto de Vasil Levski en Sofía | «по предварителна информация дроновете били управлявани от любители фотографи.» |


**C. La cita nombra otro país y no el del titular** (14)

| Incidente | Titular | Cita (país que nombra) |
| --- | --- | --- |
| EODI-2025-00060 | Dron avistado obliga a cerrar temporalmente el aeropuerto de Vilna | (GR) «galimai pastebėto drono» |
| EODI-2025-00094 | Drones cerca de la base aérea de Geilenkirchen causan desvío de vuelos | (PL) «Primili smo prijave o dronu u vazduhu» |
| EODI-2025-00099 | Dron sobre el aeropuerto de Vilna obliga a desviar un vuelo | (PL) «policija tikina gavusi pranešimą apie pastebėtą droną» |
| EODI-2025-00156 | Varios drones paralizan el aeropuerto de Gibraltar y obligan a desviar un avión militar | (ES) «varios drones irrumpieran en el espacio aéreo próximo a la pista» |
| EODI-2026-00011 | Dron incautado en la base aérea de Gilze-Rijen | (PL) «De politie weet inmiddels wie de drone bestuurde.» |
| EODI-2026-00013 | Dron en zona prohibida afecta al tráfico aéreo en el aeropuerto de Stavanger | (PL) «Politiet var i kontakt med dronepiloten, en mindreårig gutt og hans mor» |
| EODI-2026-00045 | Dron en la zona de vuelo prohibido del aeropuerto de Memmingen interrumpe operaciones | (PL) «der Flugbetrieb wird direkt eingestellt» |
| EODI-2026-00149 | Dron marroquí causa retraso en vuelo a Melilla sin cruzar la frontera | (GR) «Een Marokkaanse drone die aan de Marokkaanse kant van de grens bleef.» |
| EODI-2026-00258 | Dron no autorizado en el espacio aéreo de Moldavia | (ES) «În contextul atacurilor masive ale Federației Ruse asupra Ucrainei» |
| EODI-2026-00264 | Tres drones violan el espacio aéreo de Moldavia | (ES) «MAE convoacă ambasadorul rus după ce trei drone au încălcat spațiul aerian» |
| EODI-2026-00320 | Dron ucraniano se estrella en una central eléctrica de Estonia | (GR) «ces drones militaires ukrainiens chargés d'explosifs ont fini accidentellement leur course sur leur territoire» |
| EODI-2026-00346 | Dron detectado en el aeropuerto de Rzeszów causa desviación de vuelos | (LV) «Dron z zapalnikiem na lotnisku» |
| EODI-2026-00368 | Drone derribado sobre la cárcel de Poggioreale en Nápoles | (PL) «Un drone di grandi dimensioni, di fabbricazione europea e del valore stimato di circa 10mila euro, neutralizzato dai sistemi di difesa della Polizia Penitenziar» |
| EODI-2026-00428 | Drones sobre el aeropuerto de Berlín causan múltiples interrupciones | (LV) «kolejny alarm, który niedawno zamknął całe lotnisko na 45 minut.» |

**Pruebas** (`tests/test_incursiones.py`): enlazar un incidente existente con su ataque no crea
ninguno; un cruce solo ucraniano queda en el ataque con su frase y no sale entre los publicados;
EODI-2025-00417 se retira como duplicado de EODI-2025-00378 y el enlace queda en este; sin pareja,
cruce declarado si el parte lo dice y retirada si no; la frase de los partes guardados antes.

### Leipzig/Halle y Wunstorf (#113, #118)

- **Leipzig/Halle, 4 de agosto de 2026**: el suceso estaba en seis registros publicados, los cinco
  señalados (00391, 00239, 00129, 00190, 00318) y EODI-2026-00134, el mismo dron con el cierre de
  100 minutos que dio la policía. Se unen en `configuracion/incidentes_revisados.json`
  (`recogida/revisados.py`) en el que elige la regla de siempre: **EODI-2026-00134**, confirmado,
  con 801 fuentes, el inicio del 4 de agosto escrito por una fuente y el cierre. Las fusiones
  llevan su motivo y `revisar_fusiones` no las deshace.
- **EODI-2026-00283**: sus tres noticias (18 de septiembre) son del dron de Wunstorf, pero la ficha
  tomó la fecha y el lugar de Leipzig. Su candidato se vuelve a extraer una vez; si la ficha nueva
  sigue dando Leipzig o una fecha anterior a septiembre, se retira con el motivo (el suceso de
  Wunstorf tiene otros registros).
- La primera extracción (recogida de las 16:17) usó la hora del reloj y la publicación, que valida
  con la de inicio, la rechazó como fecha futura: esa recogida no publicó. #118 extrae con la hora
  de la ejecución.
- Pendiente con su arreglo: el dron de Wunstorf está en varios registros (2026-00023, 00145, 00276,
  00297, 00309, 00363) y Leipzig tiene más noticias tardías sueltas (2026-00128, 00231, 00353,
  00369, 00377); se añaden a `incidentes_revisados.json` tras revisarlos uno por uno.

### Tope de 1 GiB de la base en memoria (#114)

La recogida de las 15:17 falló con «database or disk is full» en la primera escritura (la retirada
de las altas): la base se abre con `sqlite3.deserialize`, que no deja crecer una base en memoria
por encima de 1 GiB, y la del 4 de octubre medía 1.044 MB tras la recuperación del bloque 2. No era
el disco (62 GB libres). `almacen/cifrado.descifrar` copia la base deserializada a una base en
memoria normal (0,8 s), sin tocar el disco en claro. Comprobado con la base real: escribir 100 MB
falla con la deserializada y entra con la copia.

### Comprobación en producción (recogida de las 17:17, publicada a las 17:33)

| | Antes (publicación de las 13:34) | Después (17:33) |
| --- | ---: | ---: |
| Incidentes europeos publicados | 592 | 509 |
| Rumanía | 145 | 105 |
| Moldavia | 95 | 60 |

- Ningún incidente publicado se titula «… cruzan a …» ni tiene un parte de guerra como única
  fuente; la recogida retiró las 77 altas («incursiones del parte retiradas: 77»).
- EODI-2025-00378, EODI-2025-00222 y EODI-2025-00260 siguen publicados, con `ataque` apuntando a
  EODI-UA-2025-0028, -0032 y -0046, y cada uno de esos ataques los lista en `cruces[].incidentes`.
- Leipzig/Halle: los seis registros quedaron en EODI-2026-00134 (801 fuentes, inicio el 4 de
  agosto, cierre de 100 minutos). Quedaban dos más del mismo suceso fechados por su publicación
  (EODI-2026-00286 del 7 de agosto y EODI-2026-00364 del 9): se añaden al grupo en #120.
- EODI-2026-00283 se volvió a extraer a las 17:32; la ficha nueva seguía dando Leipzig y el 4 de
  agosto, y se retiró con el motivo. Sus tres noticias de Wunstorf siguen en su candidato.
- El cruce declarado por Ucrania de EODI-UA-2024-0174 se publicaba sin su frase: faltaba
  `cruces[].frase` en la lista de campos públicos (`exportacion/campos.py`); se añade en #120.
- La capa de presión por país se calcula en la web con los incidentes publicados: refleja las
  cifras corregidas.

### Punto 2 de la comprobación en producción: capa de guerra por región (17:33)

Impactos rusos localizados publicados tras la recuperación del histórico (35.973 publicaciones
leídas de unas 37.000 guardadas; quedan las de los canales nuevos):

| Región | Impactos | Capturas |
| --- | ---: | --- |
| Zaporiyia | 6.089 (48,8 % de 12.478) | — |
| Sumy | 2.701 | `errores-region-punto2-sumy-*` |
| Járkov | 1.254 | `errores-region-punto2-jarkov-*` |
| Jersón | 1.198 | `errores-region-punto2-jerson-*` |
| Dnipropetrovsk | 610 | — |
| Chernígov | 225 | — |
| Odesa | 73 | `errores-region-punto2-odesa-*` |
| Mykoláiv | 0 | `errores-region-punto2-mykolaiv-*` |

Zaporiyia queda en el 48,8 % del total: cumple el objetivo de la mitad o menos. En los días con
parte diario, la lectura del histórico completo da impactos localizados el 91 % de los días en
Zaporiyia, el 85 % en Sumy y en Jersón y el 68 % en Járkov. Odesa casi nunca nombra el lugar
(política de su administración: «на півдні Одещини»): 74 de los 269 días en que publica algo de
drones. Mykoláiv no tenía impactos porque el lector se saltaba su canal: su web no enlaza ningún
canal; se verifica desde #121 por el anuncio del canal oficial del anterior jefe de la
administración (con insignia de verificado), que enlaza t.me/mykolaiv_ova.

Cinco fichas al azar, con lugar, fecha y fuente correctos (capturas
`errores-impacto-punto2-*-escritorio.png`):

| Ficha | Lugar | Fecha | Fuente y cita |
| --- | --- | --- | --- |
| EODI-IG-2026-03516 | Zolochiv (Járkov) | 04/10/2026 08:59 UTC | Харківська ОВА: «…удару дроном по цивільному автомобілю у селищі Золочів» |
| EODI-IG-2026-05283 | Járkov ciudad | 29/09/2026 16:08 UTC | Харківська ОВА: «Харків пошкоджено скління багатоквартирного будинку…» |
| EODI-IG-2026-03517 | Jersón ciudad | 04/10/2026 08:53 UTC | Херсонська ОВА: «…атакували з дрона у Корабельному районі Херсона» |
| EODI-IG-2026-03486 | Euroterminal, Odesa | 25/09/2026 08:49 UTC | Одеська ОВА: «…повторний удар по поштовому терміналу» |
| EODI-IG-2026-04483 | Comunidad de Nedryhailiv (Sumy) | 02/10/2026 16:42 UTC | Сумська ОВА: «…у Недригайлівській громаді ворожий дрон влучив у цивільну автівку» |

## Comprobación en producción del encargo

En droneobservatory.eu y en los datos publicados, tras la recogida de las 18:17 (publicada a las
18:33), con capturas a 390×844 y escritorio en `docs/capturas`:

1. **EODI-IG-2025-00179 ya no se publica y ninguna ficha da un año como fallecidos.** De los
   13.337 impactos publicados, la cifra de fallecidos más alta es 40 (EODI-IG-2025-05883) y
   ninguna está entre 1900 y 2100. Capturas `errores-region-punto1-donetsk-*` y
   `errores-impacto-punto1-donetsk-*`.
2. **Capa de guerra**: Odesa, Járkov, Jersón y Sumy muestran impactos localizados; Mykoláiv
   empieza a tenerlos con #121 (sección del punto 2, arriba). Cinco fichas al azar con lugar,
   fecha y fuente correctos. Zaporiyia queda en el 48,8 % del total.
3. **Corredores sin zonas repetidas**: 24 nombres normalizados. Capturas
   `errores-punto3-corredores-*`.
4. **Rumanía y Moldavia enlazados con el ataque de su noche, en los dos sentidos**:
   EODI-2025-00316 (Rumanía) y EODI-2025-00261 (Moldavia) llevan «Parte del ataque»; las fichas
   de EODI-UA-2025-0311 y -0317 los listan como cruces, ya sin copias (capturas `errores-punto4-*`,
   rehechas a las 18:35). Además EODI-2025-00378 en EODI-UA-2025-0028
   (`errores-cruces-ataque-borcea-*`) y el cruce declarado por Ucrania con su frase en
   EODI-UA-2024-0174 (`errores-cruces-cruce-declarado-*`), comprobados también a 360×800 y
   412×915, sin desbordamiento horizontal.
5. **La última noche coincide**: EODI-UA-2026-1027, noche del 3 al 4 de octubre, 135 drones en
   `ucrania.json` y en «Noche a noche» (capturas `errores-punto5-noche-a-noche-*`).
6. **Incidente español de la Guardia Civil**: no hay ninguno que mostrar. Entre 2024 y hoy la
   Guardia Civil no ha publicado ninguna nota de un dron que sobrevuele o entre en una
   instalación (bloque 7.2); el lector queda en la recogida y la primera que se publique entrará
   con su fuente oficial.
7. **La recogida horaria publica tras cada despliegue**: 17:17 (publicada a las 17:33) y 18:17
   (18:33). Las de las 12:17, 15:17 y 16:17 no publicaron, por las causas y arreglos de las
   secciones de incidencias (#107, #114, #118); desde #120 todo cambio de la recogida se ensaya
   de punta a punta sobre una copia de la base antes de fusionar (`docs/fusiones.md`, paso c2).

## Pendientes, con su arreglo

- **Unas pocas publicaciones de colectas o de balance guardadas como impactos** (bloque 1): el
  analizador las lee como impactos porque nombran drones y lugares. Arreglo: un marcador de
  colecta y de balance en `proceso/mensajes_guerra.py` y subir su versión; la relectura de la
  recogida horaria las retira sola.
- **Odesa nombra pocos lugares** (bloque 2): es la práctica de su administración. Arreglo: leer
  también el canal del jefe de la administración (`odeskaODA`) cuando su carácter oficial pueda
  probarse por la web o por un anuncio con insignia (la comprobación 6 de #121 ya lo permite).
- **Bélgorod sin canal probado** (bloque 2): ni la web del Gobierno de la región ni otro canal
  oficial enlazan el del gobernador. Arreglo: el mismo de Odesa, con la cadena o el anuncio.
- **EODI-UA-2025-0008 junta dos noches** (bloque 5): el parte cubre más de una jornada y no está
  marcado como resumen. Arreglo: revisar su periodo con `proceso/periodos.py` y, si es de varias
  noches, marcarlo como resumen para que no se sume.
- **Guardia Civil** (bloque 7.2): el aviso legal pide autorización de la Dirección General para
  usos distintos del privado. Arreglo: solicitarla por escrito; mientras, solo se publica enlace,
  atribución y una frase breve.
- **Nota de Interior sobre SIGLO-CD** (bloque 7.1): interior.gob.es responde 403 al acceso
  automático; la cifra sale de la copia del archivo de Internet. Arreglo: comprobarla a mano en la
  web y guardar la fecha de la comprobación.
- **73 incidentes cuya cita no respalda el titular** (sección de cruces): listados arriba, sin
  cambiar. Arreglo por tipo: guardar como cita la frase que nombra el lugar (A), comparar nombres
  en otras escrituras (B), revisar a mano las de otro país (C).
- **Wunstorf en varios registros y noticias tardías de Leipzig sueltas**: añadirlos a
  `configuracion/incidentes_revisados.json` tras revisarlos uno por uno.
- **Tamaño de la base**: en claro mide ya más de 1 GiB; la sesión que la lleva
  al disco del servidor la sacará de memoria.
