# Odesa casi sin impactos y tráfico aéreo sin memoria

European Observatory of Drone Incidents, 6 de octubre de 2026. Las horas son UTC. Este trabajo
diagnostica y arregla; no añade funciones nuevas. La base solo se amplía: un impacto que la lectura
nueva deja de dar queda retirado con su motivo, nada se borra.

**En resumen.**

- No era un retraso: el histórico de los cinco canales nuevos había entrado entero a las 23:17 del 5
  de octubre.
- La causa era el criterio de lugar. La administración de Odesa casi nunca nombra la localidad:
  escribe el distrito («в Одеському районі», «Ізмаїльський район») o solo la región («Одещина»,
  «південь Одещини»). El analizador descartaba los distritos de más de 50 km, que son casi todos
  los de 2020. Pasaba lo mismo en Kiev región, Poltava, Cherkasy, Járkov o Jmelnytskyi.
- Arreglo general, igual en todas las regiones: si el mensaje solo nombra el distrito, el lugar es
  el distrito, con su radio real y el nivel «distrito», y la ficha lo dice. Además, cuatro formas
  de escribir que se perdían y tres errores que encontré al revisar. Odesa pasa de **108 a
  169** impactos; Kiev región de 28 a 267; el total, de 13.224 a 15.727 (cifras del ensayo con
  la relectura completa; en producción entran a lo largo del día).
- Queda lo que la fuente no dice: unos 310 mensajes de Odesa (con repeticiones entre sus dos
  canales) que solo nombran la región. Con el criterio de todas las regiones no tienen lugar; el arreglo posible está en los pendientes.
- Redirecciones de Vercel: los unidos ya no gastan redirecciones masivas y un ataque inventado da
  404 real. La integración continua falla si las reglas pasan del 80 % de la capacidad.
- Tráfico aéreo: desde las 05:01 del 6 de octubre una traza de 1 GB del archivo del 25 de marzo
  dejaba el servidor sin memoria cada hora. Arreglado (cada traza con tope de tamaño) y, como
  protección general, todos los trabajos del servidor tienen ya tope de memoria; 8 no lo tenían.

## Qué pasaba

### a) ¿Faltaba histórico por entrar? No

En el servidor, `/home/eodi/datos/guerra/control.json` a las 03:09 del 6 de octubre:

| Canal | Región | `historico.terminado` | Desde | Páginas | Mensajes con drones guardados |
| --- | --- | --- | --- | ---: | ---: |
| `odeskaODA` (jefe de la administración de Odesa) | UA-51 | sí | 30-12-2024 | 328 | 664 |
| `odesaMVA` (administración militar de la ciudad) | UA-51 | sí | 19-10-2025 (el canal empieza ahí) | 145 | 96 |
| `volynskaODA` | UA-07 | sí | 30-12-2024 | 198 | 42 |
| `zhytomyrskaODA` | UA-18 | sí | 30-12-2024 | 364 | 112 |
| `ternopilskaODA` | UA-61 | sí | 31-12-2024 | 705 | 260 |

El diario de la recogida dice `pendientes=False` desde la de las 23:17 del 5 de octubre (en la de
las 22:17 aún `True`); las de las 00:17, 01:17 y 02:17 solo leyeron de 2 a 6 mensajes nuevos.
Los 1.174 mensajes de los cinco canales tienen su registro de lectura en la base. El histórico
terminó dentro de la ventana prevista y las cifras de las 02:30 ya eran las finales con el
analizador de entonces.

La capa de guerra con lugar empieza el 1 de enero de 2025 para todas las regiones (el lector baja
los históricos desde esa fecha): no hay mensajes de 2022 a 2024 de ningún canal. La muestra y las
comprobaciones van de enero de 2025 a octubre de 2026.

### b) El analizador no sacaba impactos: la causa

**Cuenta por etapas** (mensajes guardados con drones → con registro de lectura → que hablan de
drones → que describen un ataque → con lugar o para el extractor → impactos en la región →
publicados), con el analizador `mensajes-guerra/5`:

| Canal | Guardados | Tratados | Con dron | Ataque | Con lugar | Impactos en la región | Publicados |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Odesa, jefe (`odeskaODA`) | 664 | 664 | 656 | 466 | 130 (112 + 18 al extractor) | 97 | 97 |
| Odesa, ciudad (`odesaMVA`) | 96 | 96 | 95 | 56 | 14 | 13 | 13 |
| Odesa, web (`odesaoda`) | 463 | 463 | 459 | 375 | 97 | 74 | 74 |
| Volinia | 42 | 42 | 40 | 30 | 8 | 6 | 6 |
| Zhytómyr | 112 | 112 | 109 | 54 | 6 | 6 | 6 |
| Ternópil | 260 | 260 | 236 | 121 | 5 | 3 | 3 |
| Kiev región (`kyivoda`) | 3.204 | 3.198 | 3.112 | 684 | 43 | 28 | 28 |
| Kiev ciudad (`VA_Kyiv`) | 1.554 | 1.553 | 1.514 | 506 | 222 | 124 | 124 |

«Ataque» quita las alertas, los mensajes sin daños, homenajes, colectas, balances y recuerdos.
Los 108 de Odesa publicados a las 02:30 son, sin repetir, los de los tres canales de Odesa juntados
por lugar y noche. **La pérdida está entre «ataque» y «con lugar»**: en el canal del jefe de
Odesa, 336 mensajes que describen un ataque se quedaban en «sin lugar». Después no se pierde
nada: los 97 impactos de su canal están en Odesa (ninguno en otra región ni sin región), ninguno
fusionado y todos publicados.

**Muestra de 60 mensajes del canal del jefe de Odesa**, uno al azar de cada sesentava parte del
canal, del 29 de enero de 2025 al 19 de septiembre de 2026, leídos uno a uno:

| | Mensajes |
| --- | ---: |
| Describen un ataque con dron o misil con daños en la región de Odesa | **29** |
| — convertidos en impacto | 5 |
| — enviados al extractor (ataque mixto de misiles y drones) | 2 |
| — perdidos: solo nombran el distrito | 10 |
| — perdidos: solo nombran la región o «el sur de la región» | 11 |
| — perdidos: el lugar está en una frase sin verbo de daño («атаки на Чорноморськ») | 1 |
| Reenvíos de mensajes del presidente sobre otras regiones o todo el país | 22 |
| Alertas, aniversarios y temas no militares | 9 |

Diez de los perdidos, con el motivo exacto:

| Mensaje | Fecha | Lo que dice | Por qué no salía |
| --- | --- | --- | --- |
| [odeskaODA/8390](https://t.me/odeskaODA/8390) | 29-01-2025 | «Вночі ворог атакував Ізмаїльський район ударними безпілотниками… Внаслідок атаки є пошкодження будівель» | Solo nombra el distrito de Izmaíl, de más de 50 km de radio: «sin lugar» |
| [odeskaODA/9554](https://t.me/odeskaODA/9554) | 05-05-2025 | «Внаслідок російського удару по Одеському району пошкоджена низка обʼєктів… знайдено тіло загиблої людини» | Distrito de Odesa (más de 50 km): «sin lugar» |
| [odeskaODA/9863](https://t.me/odeskaODA/9863) | 05-06-2025 | «Вночі ворог атакував ударними безпілотниками Білгород-Дністровський район… руйнація та загоряння амбулаторії» | Distrito de Bilhorod-Dnistrovskyi: «sin lugar» |
| [odeskaODA/11690](https://t.me/odeskaODA/11690) | 08-10-2025 | «Уночі зафіксовані атаки ударними безпілотниками по Одеському району. Пошкоджено скління адмінбудівлі» | Distrito de Odesa: «sin lugar» |
| [odeskaODA/12770](https://t.me/odeskaODA/12770) | 12-12-2025 | «Ворог масовано атакував Одеський район ударними безпілотниками… є пошкодження об’єкта енергетичної інфраструктури» | Distrito de Odesa: «sin lugar» |
| [odeskaODA/14126](https://t.me/odeskaODA/14126) | 15-02-2026 | «В Одеському районі пошкоджено… адміністративні обʼєкти залізничної станції… залізничну цистерну» | Distrito de Odesa: «sin lugar» |
| [odeskaODA/14886](https://t.me/odeskaODA/14886) | 23-03-2026 | «Один з дронів влучив в автобусну зупинку в Одеському районі… постраждало двоє людей» | Distrito de Odesa: «sin lugar» |
| [odeskaODA/18239](https://t.me/odeskaODA/18239) | 01-08-2026 | «У Подільському районі внаслідок атаки ворожих БпЛА постраждало двоє малолітніх дітей» | Distrito de Podilsk: «sin lugar» |
| [odeskaODA/12495](https://t.me/odeskaODA/12495) | 24-11-2025 | «атаку ворожих безпілотників по півдню Одещини… вдарили по цивільній портовій інфраструктурі» | Solo «el sur de la región»: «sin lugar» (sigue así; ver pendientes) |
| [odeskaODA/13818](https://t.me/odeskaODA/13818) | 28-01-2026 | «Вночі російські терористи продовжили атакувати мирну Одещину ударними дронами… пошкоджено житлову, соціальну та припортову інфраструктуру… троє людей постраждали» | Solo la región: «sin lugar» (sigue así; ver pendientes) |

### c) ¿Se perdían después? No

- **Región**: ninguno de los impactos de los canales de Odesa, Volinia, Zhytómyr, Ternópil o Kiev
  está en otra región ni sin región.
- **Deduplicación**: ningún impacto de esos canales está fusionado en otro; los 108 publicados son
  los mismos lugares de la misma noche dichos por dos canales de Odesa, juntados.
- **Criterio de lugar**: aquí estaba la pérdida (punto b): el distrito de más de 50 km no contaba.
- **Filtros de colectas, balances y recuerdos**: en el canal del jefe de Odesa quitan 4 balances,
  14 recuerdos y 1 homenaje. Leídos uno a uno, 2 eran partes reales: un balance que empieza «За
  останній тиждень ворог вже вдруге атакував цивільні судна» y cuenta el ataque de ese día a un
  mercante, y un resumen «Поділився оперативною ситуацією на Одещині» con impactos en el centro.
  Son 2 de 19; anotado en pendientes.

### d) ¿Son los canales que publican los partes? Sí; el formato es el problema

Los partes de ataques de Odesa salen en el canal del jefe de la administración (`odeskaODA`) y se
repiten en el de la web (`odesaoda`); la ciudad publica los de la ciudad (`odesaMVA`). Son texto,
no imagen ni vídeo. El problema es lo que escriben: el distrito o la región, casi nunca la
localidad.

- **Mando Sur** (Fuerzas de Defensa del Sur): publica en Facebook, sin canal de Telegram oficial que
  se pueda comprobar; sus partes repiten las mismas formas («в Одеському районі»), así que con el
  arreglo no añadirían lugares nuevos. No se usa.
- **Fuerza Aérea** (`kpszsu`): se usa para los ataques de cada noche y las regiones de cada ataque
  (`regiones_ucrania`), no para situar impactos: sus partes dicen «влучання на 9 локаціях» sin
  nombrar los lugares. Odesa aparece ahí como región atacada en sus noches.

### Lo mismo, más breve, en las otras regiones

- **Volinia, Zhytómyr, Ternópil**: el histórico está entero. Sus administraciones publican sobre
  todo alertas y reenvíos; de los mensajes con ataque, casi ninguno nombra un lugar. Zhytómyr gana
  4 lugares con los distritos; Volinia y Ternópil no cambian (no hay más que leer).
- **Kiev región**: 1.251 de sus 3.204 mensajes son alertas y 1.115 no dan daños; los que dan daños
  nombran el distrito («Бучанському районі», «Обухівському районі»): 641 se quedaban sin lugar.
  Con el arreglo, de 25 a 181 mensajes con lugar.
- **Kiev ciudad**: la administración de la ciudad escribe «по місту», «у місті» sin repetir el
  nombre: de 191 a 203 mensajes con lugar con la ciudad del canal.

## Qué he cambiado

Todo vale para todas las regiones por igual; nada es solo para Odesa. Versión del analizador
`mensajes-guerra/6` y esquema 1.13.0.

1. **El distrito es el lugar cuando el mensaje no nombra otro**
   ([`proceso/lugares_guerra.py`](../proceso/lugares_guerra.py)). Antes, un distrito de más de 50
   km de radio no se reconocía. Ahora se reconoce con su radio real (de 30 a 104 km en los
   distritos de 2020) y con nivel `distrito`, distinto de `localidad`. Se mantiene lo de antes: si
   el mismo mensaje nombra una localidad o una comunidad de ese distrito, cuenta la localidad y el
   distrito no; «Одещина», «Сумщина» (el nombre de la región) no son un distrito; «el sur de la
   región» tampoco. Las comunidades siguen con su tope de 50 km. La ficha del impacto dice «la
   fuente solo nombra el distrito, no la localidad» bajo el radio, y la leyenda del mapa lo explica.
   El esquema admite un radio de hasta 150 km en `impacto_guerra.lugar.radio_km` (antes 50); la
   comprobación de focos térmicos no evalúa un lugar de más de 10 km de radio, así que un
   distrito nunca se «confirma» por un fuego cualquiera.
2. **La ciudad del canal de una administración municipal.** La administración militar de Odesa y
   la de Kiev escriben «по місту», «у місті», «в одному з районів міста» sin repetir el nombre. En
   esos dos canales (campo `ciudad` en
   [`configuracion/canales_guerra.json`](../configuracion/canales_guerra.json)), «місто» es su
   ciudad, salvo «місто Чорноморськ» (nombra otra) o una cifra acumulada («лише цього року 866
   жителів міста постраждали»).
3. **El ataque con drones sobre un lugar** («здійснив масовану атаку на Одесу ударними БпЛА»,
   «атаки БпЛА на Кам'янське»): cuenta si la misma frase nombra los drones y el mensaje dice que
   hubo daños, fuego o víctimas. Sin arma en la frase («не припинялися атаки на Нікопольщину»), no.
4. **«Внаслідок обстрілу» en un mensaje que solo nombra drones** es la consecuencia de ese ataque
   con drones. En plural («внаслідок обстрілів», el balance de varios ataques) o en un parte diario
   de 24 horas, no: puede incluir otras armas.
5. **«Ушкоджено»** (sinónimo de «пошкоджено») y **«зайнявся»** (se incendió) son un daño.
6. **Tres errores encontrados al revisar**: un ataque que niega los daños («атакував Одесу…
   обійшлося без влучань та постраждалих») o del que no hay noticia de ninguno («інформація щодо
   руйнувань та постраждалих не надходила») no es un impacto; además, el nombre de una persona tras su cargo no es un lugar
   («Голова Одеської ОДА Олег Кіпер»: Олег también es una aldea; ocurría desde antes y daba un
   impacto falso en una aldea de Odesa, y «Начальник поліції Костянтинівки» uno en Kostiantynivka),
   y el puerto de una ciudad que no está en el nomenclátor da la ciudad («на території
   Ізмаїльського порту» → Izmaíl, puerto).
7. **El lote del histórico del extractor tiene una tercera tanda**
   ([`proceso/extraccion_guerra.py`](../proceso/extraccion_guerra.py)), con lo que queda del mismo
   presupuesto de 5 dólares (gastados 2,13): los ataques mixtos de misiles y drones de los canales
   nuevos y los que ahora tienen lugar por su distrito. Se envía sola cuando la relectura termina,
   como las dos anteriores.

Las protecciones siguen igual y tienen prueba propia: un año escrito como fecha no es una cifra de
víctimas; homenajes, colectas y balances no dan impactos aunque nombren un distrito; los nombres
de zonas de lanzamiento se normalizan como antes. Pruebas nuevas en
[`tests/test_odesa_distritos.py`](../tests/test_odesa_distritos.py).

**Cómo entra lo antiguo.** Con la versión nueva, la relectura de la recogida horaria vuelve a leer
los 41.123 mensajes guardados, unos 5.000 por recogida: unas 8 o 9 recogidas. Lo retirado por la
lectura nueva queda marcado con su motivo («el mensaje ya no lo dice»); en el ensayo, la relectura
completa no retiró ninguno. Después, la tercera tanda del extractor se envía y la recogida
siguiente la incorpora.

## Reparto por regiones, antes y después

Impactos rusos sobre Ucrania por región (`publicacion/ucrania.json`, sentido RU→UA). «Antes»: lo
publicado a las 05:31 del 6 de octubre, con el analizador `mensajes-guerra/5` y todo el histórico
ya leído. «Después»: el ensayo de punta a punta sobre una copia de la base real con la versión
nueva, relectura completa incluida (lo que dejarán las recogidas horarias cuando terminen de releer).
«Dibujados»: sin los partes diarios de primera línea, que se publican pero no se pintan.

| Región | Antes | Después | Dibujados antes | Dibujados después |
| --- | ---: | ---: | ---: | ---: |
| Zaporiyia (UA-23) | 6094 | 6194 | 318 | 417 |
| Járkov (UA-63) | 1281 | 2763 | 309 | 462 |
| Sumy (UA-59) | 2713 | 2744 | 469 | 498 |
| Jersón (UA-65) | 1204 | 1216 | 1202 | 1214 |
| Dnipropetrovsk (UA-12) | 616 | 731 | 591 | 703 |
| Cherníhiv (UA-74) | 596 | 715 | 312 | 370 |
| Kiev región (UA-32) | 28 | 267 | 28 | 266 |
| Poltava (UA-53) | 26 | 217 | 26 | 213 |
| Mykolaiv (UA-48) | 155 | 176 | 141 | 162 |
| Odesa (UA-51) | 108 | 169 | 108 | 169 |
| Kiev ciudad (UA-30) | 124 | 131 | 124 | 131 |
| Cherkasy (UA-71) | 26 | 100 | 26 | 100 |
| Luhansk (UA-09) | 86 | 88 | 35 | 36 |
| Donetsk (UA-14) | 73 | 73 | 59 | 59 |
| Kirovohrad (UA-35) | 40 | 64 | 40 | 64 |
| Jmelnytskyi (UA-68) | 8 | 22 | 8 | 22 |
| Leópolis (UA-46) | 16 | 20 | 16 | 20 |
| Zhytómyr (UA-18) | 6 | 10 | 6 | 10 |
| Ivano-Frankivsk (UA-26) | 7 | 9 | 1 | 3 |
| Volinia (UA-07) | 6 | 6 | 6 | 6 |
| Vínnytsia (UA-05) | 4 | 4 | 3 | 3 |
| Chernivtsí (UA-77) | 4 | 4 | 4 | 4 |
| Ternópil (UA-61) | 3 | 3 | 3 | 3 |
| Zakarpatia (UA-21) | 0 | 1 | 0 | 1 |
| **Total** | 13224 | 15727 | 3835 | 4936 |

Las subidas grandes son las regiones cuyas administraciones escriben el distrito: Kiev región (28 →
267), Poltava (26 → 217), Cherkasy (26 → 100), Járkov (dibujados 309 → 463; el resto, partes
diarios). Volinia, Ternópil, Vínnytsia y Chernivtsí no cambian: sus mensajes no nombran ni
distrito ni localidad. Kiev ciudad sube por «по місту».

## Odesa por mes

| Mes | Antes | Después |
| --- | ---: | ---: |
| 2025-01 | 2 | 4 |
| 2025-02 | 2 | 6 |
| 2025-03 | 10 | 15 |
| 2025-04 | 4 | 4 |
| 2025-05 | 3 | 6 |
| 2025-06 | 8 | 11 |
| 2025-07 | 8 | 9 |
| 2025-08 | 4 | 5 |
| 2025-09 | 1 | 3 |
| 2025-10 | 1 | 2 |
| 2025-11 | 4 | 6 |
| 2025-12 | 6 | 11 |
| 2026-01 | 9 | 16 |
| 2026-02 | 7 | 10 |
| 2026-03 | 8 | 10 |
| 2026-04 | 9 | 14 |
| 2026-05 | 5 | 13 |
| 2026-06 | 7 | 9 |
| 2026-07 | 1 | 4 |
| 2026-08 | 3 | 5 |
| 2026-09 | 6 | 6 |

Ningún mes queda vacío de enero de 2025 a septiembre de 2026. De los 169 impactos de Odesa, 108 son
localidades, 59 distritos y 2 instalaciones (una terminal portuaria).
Los lugares que más salen: Odesa (88), el distrito de Odesa (37), el de
Bilhorod-Dnistrovskyi (12), Chornomorsk (11), el distrito de Izmaíl (8) e Izmaíl (4).

Odesa sube menos que Kiev región porque la mitad de sus partes solo nombra la región: «Одещина»,
«південь Одещини», «об'єкти портової інфраструктури регіону». Con el analizador nuevo, en el canal
del jefe de la administración quedan 160 mensajes así y 150 en el de la web (los dos canales repiten muchos partes), frente
a 173 y 127 que sí dan lugar. Eso no tiene arreglo dentro del criterio de lugar de todas las
regiones; está en los pendientes.

Por decisión del 6 de octubre, Odesa se cierra con estas cifras del ensayo; no hay más
comprobaciones sobre ella. Los puertos del Danubio: con los distritos, dos noches de Izmaíl quedan
unidas por su ataque a un incidente europeo ([EODI-2025-00299](https://droneobservatory.eu/EODI-2025-00299),
Rumanía, 17 de enero de 2025, y [EODI-2025-00212](https://droneobservatory.eu/EODI-2025-00212),
Moldavia, 13 de febrero de 2025), sin crear incidentes: el ensayo publica los mismos 322 en el mapa
y 113 sin ubicación que antes.

## Redirecciones de Vercel

**El problema.** Cada incidente unido gastaba dos redirecciones masivas de Vercel (una por idioma)
de las 1.000 que incluye el plan: 601 en uso (300 unidos más `/es`). Con unos 499 unidos el
despliegue habría fallado y la web habría dejado de actualizarse.

**Lo hecho: los unidos ya no gastan redirecciones masivas.** Vercel sirve primero los ficheros del
despliegue y solo aplica las reescrituras de `vercel.json` a lo que no es un fichero. Dos reglas
(`/EODI-…` y `/en/EODI-…`) llevan esas direcciones a una sola función,
[`api/borde.ts`](../api/borde.ts), que consulta la lista que escribe el build (`/rutas.json`, con
los datos de ese despliegue):

| Dirección | Respuesta |
| --- | --- |
| Un incidente publicado (`/EODI-2025-00228`) | 200, su página. Es un fichero: la función no interviene y no añade tiempo |
| Un unido (`/EODI-2025-00002`, `/en/EODI-2025-00002`) | 308 permanente a la ficha del que lo absorbió, en su idioma |
| Un ataque que existe (`/EODI-UA-2022-0012`, `/en/…`) | 200, la portada con el mapa, como antes |
| Un ataque inventado (`/EODI-UA-2099-9999`, `/en/…`) | **404 real**, con la página 404 y las cabeceras de seguridad |
| Un incidente inventado (`/EODI-2099-99999`) | 404 real |
| `/es` | 308 a `/` (regla normal de `vercel.json`, no masiva) |

Probado en una vista previa de Vercel de la rama y en el servidor local con las pruebas de
navegador. La primera versión, como middleware, añadía unos 100 ms a todas las fichas y Vercel no
empaquetaba sus `import`: se cambió a la función tras los ficheros, que solo ven las direcciones
que no existen como fichero. Coste: una invocación de función por cada visita a una dirección de
unido, de ataque o inventada; las fichas de incidente, que son casi todo, no la usan.

**No hace falta ampliar la capacidad.** Con esto se usan 0 redirecciones masivas de 1.000 (se quita
`bulkRedirectsPath`) y 7 reglas de `vercel.json` de 2.048. Si algún día hiciera falta, ampliarla
cuesta 0,002 dólares al mes por cada 25.000 redirecciones más (documentación de Vercel, «Bulk
Redirects: Limits and pricing») y se compra en el panel del proyecto, *Settings → Advanced*; no se
puede hacer por la API. No la he comprado.

**Comprobación en la construcción.** `node scripts/comprobar-paginas.ts`, que la integración
continua ejecuta tras cada build, cuenta las reglas de `vercel.json` (tope 2.048) y las
redirecciones masivas si las hubiera (tope 1.000) y **falla si pasan del 80 %**, con un mensaje
como «redirecciones masivas: 801 de 1000 (más del 80 %); el despliegue fallará al pasar de 1000:
reducirlas o ampliar la capacidad en Vercel antes de fusionar». Comprueba además que cada unido
redirige a una ficha que existe, nunca desde una que existe, y que la lista de ataques es la
publicada. Hoy dice «reglas de vercel.json 7/2048, redirecciones masivas 0/1000».

## Ensayo, fusión y producción

**Ensayo** (paso c2 de [`fusiones.md`](fusiones.md)), en el servidor, como `eodi`, con
`systemd-run` (3 GB, prioridad baja, `OOMScoreAdjust=1000`, sin el cerrojo de la recogida), sobre
una copia propia de la base del disco, sin claves del extractor: relectura completa de los 41.147
mensajes con `mensajes-guerra/6` (24 min, ninguno retirado salvo los que la regla nueva quita a
propósito) y recogida completa con la exportación semanal sin subir: **código 0**, «ficheros
publicados con cambios: 3», «exportación semanal generada sin subir». Hicieron falta varios
intentos: uno cayó por la exportación sin la clave de cifrado en el guion, otro dio código 2 por
coincidir con la recogida de producción («oficiales: tope de 240 s agotado») y dos los mató el
núcleo por falta de memoria a las :42, cuando el tráfico aéreo dejaba el servidor sin memoria
(siguiente apartado). El último se hizo en dos fases para no coincidir con el minuto 40.

**Fusión**: PR #135, a las 07:59 UTC del 6 de octubre (`a0fb096`), por avance rápido con un solo
commit con la dirección anónima, con la lista de ficheros comprobada (42, ninguno de
`publicacion/`) y la CI en verde sobre la rama rebasada. Incidentes publicados antes y después: 435.

**Producción**: el despliegue de la web de `a0fb096` está en línea; `/EODI-UA-2099-9999` y
`/en/EODI-UA-2099-9999` dan 404, `/EODI-2025-00002` da 308 a `/EODI-2025-00228`, un ataque que
existe da 200. La capa Ucrania carga y la ficha de un ataque se abre con su fuente en móvil (390×844)
y en escritorio.

**Recogidas siguientes**: la de las 08:17 (la primera con el código nuevo) terminó bien y publicó
en `main` a las 08:33; releyó 5.364 mensajes con la versión nueva. La de las 09:17, también: publicó
a las 09:34 con código 0. Por decisión del 6 de octubre, Odesa se da por terminada aquí; la relectura
entra sola durante el día.

**Cuándo entra lo antiguo en producción.** Cada recogida relee unos 4.500 mensajes con la versión
nueva: la relectura acaba en unas 9 recogidas, hacia las 17:30 UTC del 6 de octubre. Después, la
recogida siguiente envía la tercera tanda del extractor y la de después la incorpora.

## Tráfico aéreo: el trabajo del minuto 40 dejaba el servidor sin memoria

**Qué pasó y desde cuándo.** `eodi-trafico` (minuto 40) procesa el archivo diario de adsb.lol: el
día nuevo y, día a día, el histórico de 522 días. A las 04:58 terminó el 24 de marzo de 2026 y
empezó el 25. A las 05:01 había subido a 6,3 GB y el servidor (7,7 GB, sin intercambio) se quedó sin
memoria: el núcleo mató el proceso. Como el día no se terminaba, cada ejecución volvía a empezar por
él: a las 05:42 y a las 06:42 lo mismo (6,6 y 6,7 GB), y esas dos veces el núcleo mató antes el
ensayo de esta sesión, que es el primero en morir por norma. La unidad no tenía tope de memoria.

**La causa.** El archivo del 25 de marzo lleva una traza anómala: `traces/39/trace_full_a6a739.json`,
21 MB en gzip y **1.006 MB descomprimida** (de 73.008 ficheros del día, ninguna otra traza pasa de 2
MB en gzip). El lector leía el tar en flujo, pero cada traza la cargaba entera: `read()`,
`gzip.decompress` y `json.loads` de 1 GB de JSON, más de 6 GB de objetos de Python. No era el volumen
del día ni un fichero dañado: una sola traza enorme.

**El arreglo** ([`recogida/adsb.py`](../recogida/adsb.py)). Cada traza se descomprime por bloques con
un tope de 64 MB (las normales no pasan de unos 20 MB); la que lo pasa se salta sin llegar a estar
entera en memoria y queda anotada con su nombre en `trazas_demasiado_grandes` del resumen del día,
aparte de las dañadas. Así la memoria no depende ni del tamaño de un día ni del de una traza: el tar
se lee en flujo y cada traza tiene su tope. Probado en el servidor con el día real del 25 de marzo
y el código nuevo, en una carpeta aparte: 72.954 trazas, 10.962 en Europa, **254 MB de memoria
máxima** (antes 6,4 GB), 542 s, la traza `a6a739` anotada como demasiado grande. Prueba nueva en
`tests/test_trafico.py`.

**Cortar el daño ya.** A las 07:23 se puso a `eodi-trafico` un tope de 3 GB en el servidor
(`systemctl set-property`, persistente). A las 07:40 volvió a intentar el 25 de marzo con el código
viejo, llegó a 3 GB y systemd lo paró a él solo (`CONSTRAINT_MEMCG`): el servidor no se quedó sin
memoria.

**Ningún trabajo programado sin tope.** De las 15 unidades del servidor, 8 no tenían tope de memoria:

| Unidad | Pico medido (4 días, con caché) | Tope nuevo |
| --- | ---: | ---: |
| `eodi-recogida` | 3,3 GB con la base en disco (5,7 GB antes, en memoria) | 5 GB |
| `eodi-deduccion` | 3,2 GB | 4 GB |
| `eodi-exportacion` | 2,5 GB | 4 GB |
| `eodi-catalogo` | 2,2 GB | 3 GB |
| `eodi-trafico` | 0,8 GB por día (6,4 GB con la traza enorme) | 3 GB |
| `eodi-detalle` | 0,6 GB | 1,5 GB |
| `eodi-busqueda` | 0,25 GB | 1 GB |
| `eodi-guerra` (lector de canales) | 0,1 GB | 1 GB |

Ya lo tenían `eodi-directo` (1,5 GB), `eodi-seguimiento` (150 MB), `eodi-seguimiento-archivo`,
`eodi-satelite`, `eodi-luces` y `eodi-focos-vivo` (1 GB). Los topes van en
[`servidor/configuracion.sh`](../servidor/configuracion.sh) y en cada unidad de
[`servidor/instalar.sh`](../servidor/instalar.sh); una prueba nueva
([`tests/test_servidor_topes.py`](../tests/test_servidor_topes.py)) falla si una unidad no lo tiene.

**Qué se perdió y qué se recupera.**

- **Recogida horaria**: ninguna falló por esto. Desde las 05:01: 05:17 bien, 06:17 publicó con aviso
  (código 2, «oficiales: tope de 240 s agotado», por coincidir con el ensayo), 07:17 bien,
  08:17, 09:17 y 10:17 bien (las dos últimas, ya con los topes: picos de 3,7 y 3,8 GB con el de
  5 GB). Ninguna recogida falló por falta de memoria.
- **«En directo»** (`eodi-directo`) y el seguimiento de Ucrania no se pararon: el núcleo solo mató al
  tráfico y a los ensayos de esta sesión.
- **Día nuevo**: el 5 de octubre se procesó a las 03:51, antes de la avería, y el 6 no se publica en
  adsb.lol hasta la madrugada del 7. **Densidad, Presión y la detección de cierres no han perdido
  ningún día reciente.**
- **Histórico**: se quedó parado en el 25 de marzo de 2026 desde las 05:01 (cuatro ejecuciones
  perdidas, unos 20 días de histórico sin procesar). Hay 503 días procesados (del 25 de noviembre de
  2024 al 5 de octubre de 2026) y el 6 de mayo de 2026 sigue como perdido (adsb.lol no lo publicó).
  Con el arreglo, el histórico sigue solo desde el 25 de marzo en las ejecuciones del minuto 40.

**Ensayo y fusión.** Prueba del día del 25 de marzo con el código nuevo (arriba) y ensayo de
recogida y exportación semanal sobre una copia de la base, con la rama: código 0. PR #136, fusionado
a las 09:03 UTC (`65b0ed1`), por avance rápido, con la CI en verde sobre la rama rebasada. Los
topes de memoria se aplicaron en el servidor con `systemctl set-property` a las 08:35 (los mismos
valores que `instalar.sh`, que los pone al reconstruir). La recogida de las 09:17 dejó el código
nuevo en el clon, y la ejecución del tráfico de las 09:40 procesó el 25 de marzo en 549 s con unos
360 MB, y siguió con el resto del histórico (el 10, el 1 y el 5 de febrero, unos 10 minutos por
día); la recogida de las 10:17, la segunda tras esta fusión, terminó bien y publicó.

## Pendientes, con su arreglo

- **Partes que solo nombran la región.** Unos 310 mensajes de Odesa (160 del canal del jefe de la
  administración y 150 del de la web, que repiten muchos) dicen
  «Одещина», «південь Одещини» o «об'єкти портової інфраструктури регіону» y nada más concreto. No
  son un lugar con el criterio de todas las regiones. Arreglo, si se decide: un impacto de nivel
  «región», sin punto en el mapa, que cuente en la cifra de la región y se liste en su ficha;
  cambia el criterio de todas las regiones y es una decisión, no una corrección.
- **Mensajes de seguimiento publicados días después** (la cifra de fallecidos que sube, una visita
  al lugar) crean otro impacto del mismo lugar y día sin ataque: Odesa tiene cuatro el 27 de enero
  de 2026. Pasa en todas las regiones (unos 900 impactos de más, sobre todo partes diarios de
  primera línea junto al parte de la noche). Arreglo: en `proceso/impactos_guerra._mismo`, cuando
  el mensaje declara el día, juntar con el impacto del mismo lugar y día; ensayarlo aparte porque
  toca a los partes diarios.
- **Balances y recuerdos que se llevan algún parte real**: 2 de 19 en el canal del jefe de Odesa
  («За останній тиждень ворог вже вдруге атакував цивільні судна… Цього разу…»). Arreglo: no
  tratar como balance un mensaje que cuenta un ataque de ese día («цього разу», «сьогодні»,
  «вночі»).
- **«Під ударом була Вилківська громада»**: la comunidad sin verbo de daño se pierde y queda solo
  el distrito. Arreglo: leer «під ударом» como impacto.
- **Los ataques mixtos de misiles y drones** no se pueden atribuir por código; van al extractor.
  La tercera tanda del lote del histórico se envía sola cuando termine la relectura (hacia
  las 17:30 UTC del 6 de octubre) y la recogida siguiente la incorpora: no hay que hacer nada, solo comprobar en el
  diario «lote … enviado» y después «incorporado».
- **La capa empieza en 2025.** No hay mensajes de 2022 a 2024 de ningún canal: el lector baja los
  históricos desde el 1 de enero de 2025. Arreglo, si se quiere: adelantar `GUERRA_DESDE` en
  `servidor/configuracion.sh` para todos los canales y dejar que el lector y la relectura lo
  incorporen (unas tres veces más mensajes).
