# Corrección de errores de datos

European Observatory of Drone Incidents, 4 de octubre de 2026. Las horas son UTC. Un pull request
por bloque, en este orden. La base es de solo añadir: cada corrección entra como versión nueva con
su motivo en el historial, y lo retirado queda marcado como retirado con su causa. Todo se
reprocesa desde los mensajes y las citas ya guardados, sin volver a descargar ni llamar al
extractor salvo donde se dice.

Cifras «antes» medidas sobre la base de la rama `estado` de las 08:15 del 4 de octubre (la que
servía droneobservatory.eu), antes de cambiar nada.

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
