# Informe: motor de deducción por descarte físico

Fecha: 2 de octubre de 2026. Pull request #50 (código, catálogo, esquema, exportación y este
informe). En AEGIS, PR #45 (importador, vocabulario y límites de movimiento por clase).

Para cada incidente europeo, cada impacto con lugar de la capa de guerra y cada ataque, el
motor dice con reglas físicas explícitas qué clases de dron son compatibles, cuáles quedan
descartadas (con la regla, su versión y los datos que lo hacen imposible) y cuáles quedan
indeterminadas, desde dónde pudo despegar cada clase compatible y, en los cruces a países de la
OTAN, si cabe que un señuelo sin guiado llegara con el viento. No hay ningún modelo de lenguaje
en la deducción: solo código (`proceso/deduccion/`) sobre un catálogo con fuentes
(`configuracion/catalogo_drones.json`) y los datos medidos de la base (condiciones de
Open-Meteo, interferencia GNSS de adsb.lol, puntos de los incidentes y de los impactos).

Lo deducido es interno, va en su propio bloque `deduccion` con origen `deducido`, método
`regla` y la versión de cada regla, no se mezcla con lo medido ni con lo oficial, no cambia el
nivel de detalle y no se publica en la web.

## 1. Resumen

- **Catálogo**: 48 modelos (46 reales y 2 referencias genéricas derivadas), 12 clases,
  147 fuentes numeradas y 22 zonas de lanzamiento. Cada cifra lleva su fuente y una frase
  literal de la fuente; de 251 comprobaciones de cifras del borrador, 220 coinciden con su
  fuente, 13 no coinciden (corregidas), 11 tenían la fuente inaccesible (se buscó otra o se usó
  la copia del archivo de Internet) y 7 no estaban en la fuente que se citaba. 58 entradas de
  corrección en total (cifras, fuentes y fechas). 143 campos quedan «sin fuente».
- **Validación**: 26 casos de modelo conocido evaluables (Gerbera y Geran-2 caídos en Polonia,
  Rumanía, Moldavia, Lituania, Letonia y Turquía, un Orlan-10 en Turquía y dos DJI
  identificados por la policía): **26 aciertos, 0 fallos graves, 0 indeterminados**; 3 de ellos
  están en la base y el resultado guardado también acierta. Con 41 encuentros de la UK Airprox
  Board con altura, descripción y tipo: la regla de viento no descarta nunca el tipo que da la
  UKAB, y la descripción apoya su tipo en 36 y va en contra en 1.
- **Poder de descarte, sin adornos: es bajo en Europa.** Ningún incidente europeo tiene hoy una
  clase descartada: la base no trae alturas, velocidades ni trayectorias, el viento medido en
  los incidentes nunca supera el límite de una clase con el margen, y la regla de distancia
  solo descarta cuando una autoridad declara que el dron entró desde fuera (en los casos con
  punto, no ocurre). De media quedan 7,4 clases compatibles por incidente con datos. Lo que sí
  da es la conclusión «despegue cercano o dron de largo alcance» en 18 incidentes (Hannover,
  Fráncfort, Leipzig, Varsovia, Sofía…), la zona de despegue por clase y, en la capa de guerra,
  descartes reales: 38 impactos con alguna clase descartada (los multirrotores de consumo y
  profesionales a cientos de kilómetros de la zona de lanzamiento) y 25 ataques.
- **Deriva** en los cruces a países de la OTAN: 30 incidentes evaluados; 1 compatible con
  deriva (Rumanía, base aérea, 2026), 1 no compatible (Vilna) y 28 indeterminados, casi todos
  porque el incidente solo tiene el día y el viento del día no tiene dirección.
- **Servidor**: temporizador propio en el minuto 5 con su cerrojo; una pasada completa tarda unos 12 minutos (la mayor parte es el horizonte de radar con el relieve) y una incremental, 1 minuto; 930 MB de memoria; 641 MB de teselas de Copernicus DEM tras la primera pasada.

## 2. Catálogo de prestaciones

**Ficheros** (cada uno con su esquema propio en `esquema/catalogo/1.0.0/`):

- `configuracion/catalogo_drones.json`: por modelo, nombre, otros nombres, país, fabricante,
  tipo de aeronave, clase del motor y 29 campos (motor, envergadura, diagonal, dimensiones,
  longitud, peso al despegue, carga u ojiva, velocidad de crucero y máxima, alcance, alcance y
  tipo de enlace, autonomía, techo, altura típica, viento máximo, temperatura, lluvia, navegación,
  comportamiento ante interferencia GNSS, sección radar, firma acústica, luces, capacidad
  nocturna, lanzamiento, recuperación, clase de la UE, Remote ID y rasgos para testigos). Cada
  valor: número con la unidad de la fuente (sin convertir ni redondear: el código convierte al
  usarlo) o texto, la fuente y la frase literal. Si dos fuentes discrepan, van las dos. Un campo
  sin dato fiable: `datos: []` y `sin_fuente: true`. Una cota abierta («más de 4 h») deja sin
  saber el extremo que no da.
- `configuracion/catalogo_fuentes.json`: 147 fuentes con enlace, fecha de publicación (null
  si la página no la da), día de consulta, tipo (fabricante, inteligencia, análisis técnico,
  prensa técnica, estimación OSINT, geográfica) y prioridad. **P2** (amalantra.ru) es de
  prioridad baja: los valores que solo dependen de ella (velocidad, peso, envergadura y alcance
  del Parodiya) quedan marcados como estimación débil y ninguna regla descarta con ellos (test
  `test_las_fuentes_de_prioridad_baja_solo_dan_estimaciones_debiles`).
- `configuracion/zonas_lanzamiento.json`: zonas de los partes ucranianos (apartado 4).

**Cómo se hizo.** Se partió del borrador. Cada cifra se comprobó abriendo su fuente; se
completó lo pedido con las webs de los fabricantes (dji.com, enterprise.dji.com, el manual del
Agras T50, autelrobotics.com, skydio.com, baykartech.com), War&Sanctions de la inteligencia
militar ucraniana, el Institute for Science and International Security, CSIS, RUSI, el
Ministerio de Defensa rumano y prensa técnica que cita una fuente técnica. Las tiendas de
terceros del borrador (techgadget, coptrz, lindinger) se sustituyeron por las fichas de DJI,
con las que coinciden.

**Correcciones principales respecto al borrador**:

| Modelo | Campo | Borrador | Fuente |
| --- | --- | --- | --- |
| Geran-2 (G1) | fuente | ficha War&Sanctions vigente | `uav/336` devuelve 404 el 2 de octubre de 2026; las ocho cifras coinciden en la copia del archivo de Internet del 11-09-2025, que es la que se cita |
| Shahed-136 térmico (G5) | fecha, alcance y enlace | 21-09-2026; >1.000 km y 220 km del propio dron | 27-06-2025; las cifras salen de un documento de 2022 sobre el concepto Shahed-236 |
| Gerbera | peso, alcance, velocidad, altura | 18 kg y 600 km «atribuidos a inteligencia» (Forbes) | Hay ficha primaria de War&Sanctions (L2): 2,5 m, 18 kg, 160 km/h, 600 km, hasta 3.000 m, catapulta elástica o neumática |
| Gerbera | motor | «pistón DLE60 de dos tiempos» [G6] | G6 solo dice DLE60; «dos tiempos» lo dice P1 |
| FP-1 | envergadura | 2,5 m | 6 m (EDR, Eurosatory 2026) |
| FP-1 | alcance y carga | 1.600 km; 60–120 kg | 1.600 km y hasta 120 kg (panel del Ministerio, 2025); 2.700 km con 60 kg (EDR, 2026) |
| UJ-22 Airborne | fabricante y autonomía | Ukrspecsystems; 6 h | UKRJET; 12 h (ArmyInform; 6 h solo con tiempo extremo), 7 h y 14 h en otras fuentes |
| UJ-26 Bober | atribución | prensa citando a la HUR | NV no atribuye las cifras a la HUR ni al fabricante |
| Orion | enlace | 200 km o 250–300 km | las dos páginas dicen «250 (300) km» |
| Lancet 51 / 52, ZALA 421-16E | velocidad, autonomía | solo War&Sanctions | el fabricante (versiones de exportación) da otras cifras: van las dos |
| Molniya-2 | todo | Forbes: 40–60 km, 90–120 km/h, 40 min, 5 kg | Forbes inaccesible; Ukrainska Pravda: unos 10 kg, 3–5 kg de carga, unos 30 km o 40 min |
| DJI Mavic 3 Classic | velocidad | 21 m/s, «15 m/s en algunos modos» | 21 m/s; 19 m/s en la UE; no hay ningún límite de 15 m/s |
| DJI Mavic 4 Pro | enlace | sin cifra CE; 30 km | 30 km es FCC; CE 15 km |
| DJI Matrice 30T | viento | 15 m/s | la ficha dice 12 m/s; 15 m/s solo en un blog comercial (van las dos) |
| DJI Matrice 30T / 350 RTK / 4TD | clase UE | C2 / sin fuente / C2 y C6 | C2 en la ficha y «M30T EU DOC C3» en la lista de declaraciones; C3; C6 solo con el firmware que dice D18, C2 en las declaraciones |
| Autel EVO Max 4T | peso, viento, enlace, IP | 1.999 g, 12 m/s, 15 km, IP43 | 1.999 g es el peso máximo al despegue (1.665 g el de despegue); 12 m/s solo en crucero (10,7 en despegue y aterrizaje); 15 km es FCC (CE 8 km); IP43 es un servicio a medida, no de serie |
| DJI Agras T50 | alcance | — | la ficha da «Max Flight Range 2000 m», que es el radio configurable del software: va como texto, no como alcance físico |
| Primorsko-Ajtarsk | coordenada | 46°40′34″N 38°07′49″E [B1] | es el pie de la figura 3 del informe del ISIS, que corresponde a Yeysk; la base está en 46°03′26″N 38°13′48″E (apartado 4) |

Además, una veintena de fechas de fuentes estaban desplazadas uno o más días (G6, G7, G8, P1,
P2, P3, I1, B2, B6, D13, D18…) o eran la de la ficha y no la de su última actualización (las de
War&Sanctions dicen «Updated: 04.05.2026»). Las dos fuentes del borrador que no se encontraron
(«weaponspecs» del FP-1 y «dronestrike» del UJ-22) no están en el catálogo: sus cifras salen de
otras fuentes. La lista completa de correcciones y comprobaciones está en el historial del PR.

**Lo que quedó «sin fuente»** (143 campos; la tabla del final da todos por modelo): el
Lancet-53 entero (ZALA solo dice que sale de un contenedor), las dimensiones y el peso de los
Lancet, la autonomía del Gerbera y del Parodiya, el techo y la autonomía del Geran-1 y del
Liutyi, la mayoría de las cifras del Italmas, el alcance del enlace del Geran-2 y del AKINCI,
la velocidad y la carga del FPV militar por radio, el viento máximo de todos los drones
militares, la sección radar de casi todos (solo hay una estimación «tan bajo como 0,01 m²» del
Geran-2), y en los DJI la diagonal, la resistencia a la lluvia y el Remote ID de los modelos de
consumo (DJI no publica grado IP para ellos).

**Referencias genéricas derivadas.** «Ala fija de reconocimiento mediana» (del Orlan-10 y el
Orlan-30) y «multirrotor pesado de carga» (del Agras T50 y el Matrice 350 RTK): sin cifras
propias, su envolvente se calcula con la de esos modelos y cada valor lleva la marca
`derivado`.

## 3. Clases y envolventes

Doce clases, cada una con los modelos de los que sale (la tabla de envolventes está al final):
multirrotor de consumo de menos de 250 g, multirrotor de consumo de 0,25 a 2 kg, multirrotor
profesional, multirrotor pesado de carga, FPV (consumo, militar por radio y por fibra), ala fija
táctica eléctrica, ala fija de reconocimiento de combustión, ala fija de media altitud y gran
autonomía, munición merodeadora, dron de ataque de largo alcance de pistón, señuelo de largo
alcance y dron de ataque a reacción. Cada clase dice su tipo de aeronave, su propulsión, su
tamaño para un testigo (pequeño, mediano o grande), si es de corto alcance, su valor en el
vocabulario de clases del esquema (`multirrotor_pequeno`, `ala_fija`, `ataque_largo_alcance` o
ninguno: el multirrotor pesado no tiene equivalente) y su clase de tamaño de AEGIS (`mini`,
`phantom` o `inspire`; las de ala fija y largo alcance no tienen). La misma tabla está en el
vocabulario 1.3.0 (`clases_deduccion`) y en `tools/vocabulario_eodi.json` de AEGIS.

**Envolvente.** Por campo, el mínimo de los mínimos y el máximo de los máximos de los modelos.
Para **descartar** hace falta la cota de **todos** los modelos de la clase con fuentes que no
sean débiles: si a uno le falta (por ejemplo, el Lancet-53, sin ninguna cifra), la clase no se
puede descartar por esa magnitud. Para decir que una clase **es compatible** basta con que un
modelo con dato cumpla. Algunas cotas se deducen y lo dicen (`deducida`): el alcance en aire en
calma no pasa de la autonomía por la velocidad máxima, y el tiempo de vuelo de un ala fija no
pasa de su alcance entre su velocidad de crucero más baja.

## 4. Zonas de lanzamiento

`configuracion/zonas_lanzamiento.json`, 22 zonas con las raíces con que las escriben los partes
de la Fuerza Aérea de Ucrania (las mismas que usaba la meteorología de la capa de guerra), su
punto con la fuente que lo da literalmente y las fuentes que documentan su uso (sobre todo los
partes del propio canal de la Fuerza Aérea, el ISIS, Molfar y Militarnyi).

**Primorsko-Ajtarsk.** La coordenada del borrador (46°40′34.48″N 38°07′49.75″E) es la del pie
de la figura 3 del informe del ISIS del 9 de julio de 2024 (B1), que es el emplazamiento de
almacenamiento y preparación de **Yeysk**, unos 69 km al norte. B1 no da ninguna coordenada de
Primorsko-Ajtarsk: solo lo nombra entre los cinco lugares principales de lanzamiento. Se
corrige así: la coordenada de B1 pasa a la zona de Yeysk; la base aérea de Primorsko-Ajtarsk
lleva 46°03′26″N 38°13′48″E (46,057222, 38,230000; B27) y el puerto de drones de junto a la
base, 46,066107, 38,220378 (Molfar, B7; a 1–2 km de la base, como dice Militarnyi, B2, que no
da coordenadas).

**Millerovo** 48°57′08″N 40°18′08″E (B31; Molfar sitúa la plataforma de cuatro lanzadores a unos
2 km al oeste) y **Hvardiiske** 45°06′58″N 33°58′44″E (B32; a unos 180 m del punto del
borrador; la Fuerza Aérea escribe solo «ТОТ АР Крим – Гвардійське», así que va como zona y no
como aeródromo).

| Zona | Tipo | Punto [fuente] | Uso documentado en |
| --- | --- | --- | --- |
| Primorsko-Ajtarsk, base aérea | aerodromo | 46.057222, 38.23 [B27] | B1, B14, B2, B27 |
| Primorsko-Ajtarsk, «droneport» junto a la base aérea («Port Arthur» en documentos de Alabuga) | instalacion_lanzamiento | 46.066107, 38.220378 [B7] | B2, B7 |
| Kursk (Jalino / Kursk-Vostochny) | aerodromo | 51.75, 36.295 [B4] | B1, B15, B5, B7 |
| Oriol (aeródromo Oryol-Yuzhny) | zona | 52.935, 36.001667 [B29] | B15 |
| Tsymbulove / Tsimbulova, región de Oriol («gran droneport», «Orlando» en documentos de Alabuga) | instalacion_lanzamiento | 53.36893, 35.815759 [B7] | B12, B15, B2, B8 |
| Briansk | zona | 53.214167, 34.176389 [B30] | B14 |
| Millerovo | aerodromo | 48.952222, 40.302222 [B31] | B15, B7 |
| Hvardiiske, Crimea ocupada | zona | 45.116111, 33.978889 [B32] | B14 |
| Cabo Chauda, Crimea ocupada (polígono) | poligono | 45.0025, 35.83944 [B42] | B1, B11, B15 |
| Shatalovo | aerodromo | 54.34, 32.473333 [B33] | B16, B3 |
| Donetsk ocupado (dirección) | zona | sin punto | B14, B15 |
| Donetsk, aeropuerto internacional (ocupado) | aerodromo | 48.075, 37.725556 [B34] | B10, B12, B34 |
| Yeysk (emplazamiento de almacenamiento y preparación junto a la base aérea) | instalacion_lanzamiento | 46.676244, 38.130486 [B1] | B1, B18 |
| Balaklava, Crimea ocupada | zona | 44.505344, 33.597952 [B43] | B20, B25 |
| Kacha, Crimea ocupada | aerodromo | 44.783056, 33.561389 [B36] | B17, B9 |
| Seshcha | aerodromo | 53.715, 33.338889 [B37] | B19, B3 |
| Dzhankói, Crimea ocupada | zona | 45.700833, 34.417222 [B38] | — |
| Belbek, Crimea ocupada | zona | 44.691944, 33.574444 [B39] | B21 |
| Engels | zona | 51.481111, 46.210556 [B40] | — |
| Berdiansk (ocupado) | zona | 46.814722, 36.758056 [B41] | B22 |
| Prymorsk, provincia de Zaporiyia (ocupado) | zona | 46.73333333, 36.35 [B44] | B23 |
| Navlia, provincia de Briansk («Navoiy» en documentos de Alabuga) | instalacion_lanzamiento | 52.855678, 34.517882 [B3] | B2, B3 |

El radio de cada zona como origen no sale de las fuentes: lo pone el motor por tipo (5 km un
aeródromo o una instalación, 10 km un polígono, 30 km una zona nombrada por su ciudad) y se
resta de la distancia. Dzhankói y Engels no tienen fuente de lanzamiento de drones (solo de
misiles): solo cuentan si un parte las nombra como zona de lanzamiento. «Donetsk ocupado» es
una dirección sin punto y no sirve para medir.

## 5. Reglas

Cada regla tiene identificador y versión (todas 1.0.0) y da, por clase, una evidencia:
descarta, compatible, condición, indicio a favor o en contra, o anotación. Una regla sin los
datos que necesita no dice nada de la clase. Márgenes (todos a favor de no descartar):

| Regla | Qué mira | Descarta si | Margen |
| --- | --- | --- | --- |
| `distancia` (guerra) | Distancia de la zona de lanzamiento declarada en el parte del ataque al impacto (UA→RU: distancia a las fronteras reconocidas de Ucrania, cota inferior sin línea del frente) | La distancia que queda supera el alcance en el suelo de todos los modelos de la clase: alcance en calma más el viento más fuerte medido en su banda de vuelo por su tiempo máximo | Se restan el radio de la zona y el del lugar; 10 % sobre el alcance. Sin viento medido no descarta |
| `distancia` (Europa) | Cota inferior de la distancia a lo más cercano de fuera del país: tierra de otro país (polígonos de Natural Earth menos 2,5 km) o aguas internacionales (costa más 12 millas) | Solo si una autoridad (o algo medido) declara que el dron entró desde fuera: si no, es la condición «solo con despegue dentro del país». Si ninguna clase de corto alcance llega desde fuera: conclusión «despegue cercano o dron de largo alcance». Si el exterior está más lejos que el enlace: «solo con vuelo programado» | Igual que la anterior; el radio del lugar se resta |
| `meteorologia` | Viento en la banda de vuelo de la clase (10 m, 100 m y los niveles de 1000, 925, 850 y 700 hPa, con sus alturas de la atmósfera estándar), temperatura en superficie y lluvia | El viento más flojo de la banda, menos 2 m/s, pasa del límite de todos los modelos en un 25 %; o la temperatura queda 10 °C fuera del intervalo de trabajo de todos. Ala fija sin límite publicado: su velocidad de crucero frente al viento (valor deducido); descarta solo si debe quedarse sobre el sitio (15 min o más), si no, condición «solo con el viento a favor» | 2 m/s de error del viento de un modelo meteorológico, 25 %, 10 °C. La lluvia nunca descarta (solo anota el grado IP si lo hay) |
| `autonomia` | Permanencia declarada frente al tiempo máximo de vuelo | Nunca: si la pasa en un 10 %, condición «solo con relevos (operador cerca) o varios drones» | 10 % |
| `velocidad` | Velocidad observada (o entre dos avistamientos fechados) frente a la máxima | Solo si la velocidad es oficial y la más baja del rango pasa la máxima de todos en un 20 %; si no es oficial, condición | 20 % |
| `radar` | Detección por radar declarada | Solo con sección radar con fuente en todos los modelos y por debajo de 0,01 m²; sin ella, nada | Hoy no hay ninguna clase con esa sección radar: la regla nunca actúa |
| `simultaneidad` | Sitios con ventanas que se solapan, más separados de lo que la clase recorre en el tiempo más largo que pudo pasar entre uno y otro (con el viento a favor y sin pasar de su alcance) | Nunca: condición «varios drones o equipos» y conclusión | 20 % sobre lo que recorre; se restan los radios |
| `descripcion` | Lo que dicen testigos, pilotos y fuentes (forma, sonido de motor, tamaño, luces, modelo nombrado) frente a los rasgos de la clase | Nunca: indicio a favor o en contra | — |
| `gnss` | Interferencia GNSS medida (media o alta) en la zona | Nunca: anota si la navegación de la clase depende del GNSS, lo resiste (antena CRPA, Kometa, navegación visual o inercial, fibra) o no hay dato | — |

**Combinación**, sin votar por mayoría: descartada si alguna regla física la descarta y nada la
apoya; **indeterminada con conflicto** si una regla la descarta y la descripción (o el modelo
que da la fuente) la apoya, con las reglas enfrentadas guardadas; compatible si alguna regla
física pudo evaluarla y ninguna la descarta, con sus condiciones e indicios; indeterminada sin
datos si ninguna regla física la evaluó. Si todas las clases evaluadas quedan descartadas, las
pruebas no encajan: todas pasan a indeterminadas con el conflicto «ninguna clase compatible».
Ningún caso real llegó a conflicto (los tests lo comprueban con el ejemplo pedido: viento que
descarta un multirrotor pequeño y testigo que dice que era pequeño).

**Zona de despegue posible.** Para cada clase compatible, con el triángulo de velocidades: con
velocidad propia V (la máxima de la clase), viento W y tiempo t, los puntos desde los que llega
forman el círculo de centro P − t·W y radio t·V; la unión hasta su tiempo máximo (limitado por
su alcance en calma) es la envolvente convexa del incidente y del último círculo. Polígono de 24
vértices, cruzado con tierra del país, de otros países y mar por muestreo. Es una cota
superior. Por encima de 400 km de radio no se dibuja (largo alcance). Ejemplos:

| Incidente | Clase | Radio (km) | Desplazado por el viento (km) | País / otros / mar |
| --- | --- | ---: | ---: | --- |
| EODI-2025-00154 Copenhague (22/09/2025) | multirrotor_consumo_sub250 | 25 | 9.6 | 44% / 0% / 56% |
| EODI-2025-00154 Copenhague (22/09/2025) | multirrotor_consumo | 41 | 9.3 | 45% / 9% (SE 9%) / 46% |
| EODI-2025-00154 Copenhague (22/09/2025) | multirrotor_profesional | 76 | 20.3 | 39% / 18% (SE 18%) / 42% |
| EODI-2025-00154 Copenhague (22/09/2025) | multirrotor_pesado_carga | 76 | 20.3 | 39% / 18% (SE 18%) / 42% |
| EODI-2025-00060 Vilna (25/09/2025) | multirrotor_consumo_sub250 | 25 | 4.3 | 100% / 0% / 0% |
| EODI-2025-00060 Vilna (25/09/2025) | multirrotor_consumo | 41 | 4.2 | 88% / 12% (BY 12%) / 0% |
| EODI-2025-00060 Vilna (25/09/2025) | multirrotor_profesional | 76 | 9.1 | 72% / 28% (BY 28%) / 0% |
| EODI-2025-00060 Vilna (25/09/2025) | multirrotor_pesado_carga | 76 | 9.1 | 72% / 28% (BY 28%) / 0% |
| EODI-2026-00124 Galați (29/05/2026) | multirrotor_consumo_sub250 | 25 | 0.0 | 82% / 18% (MD 10%, UA 8%) / 0% |
| EODI-2026-00124 Galați (29/05/2026) | multirrotor_consumo | 41 | 0.0 | 75% / 25% (MD 14%, UA 11%) / 0% |
| EODI-2026-00124 Galați (29/05/2026) | multirrotor_profesional | 76 | 0.0 | 72% / 28% (MD 14%, UA 14%) / 0% |
| EODI-2026-00124 Galați (29/05/2026) | multirrotor_pesado_carga | 76 | 0.0 | 72% / 28% (MD 14%, UA 14%) / 0% |
| EODI-2025-00072 Bruselas (04/11/2025) | multirrotor_consumo_sub250 | 25 | 0.0 | 100% / 0% / 0% |
| EODI-2025-00072 Bruselas (04/11/2025) | multirrotor_consumo | 41 | 0.0 | 100% / 0% / 0% |
| EODI-2025-00072 Bruselas (04/11/2025) | multirrotor_profesional | 76 | 0.0 | 88% / 10% (FR 0%, NL 10%) / 2% |
| EODI-2025-00072 Bruselas (04/11/2025) | multirrotor_pesado_carga | 76 | 0.0 | 88% / 10% (FR 0%, NL 10%) / 2% |

**Deriva** (`deriva` 1.0.0), solo en países de la OTAN, con entrada desde fuera y con el punto a
200 km o menos del territorio de las partes (Ucrania, Rusia, Bielorrusia): se toma el punto de
esa frontera más cercano y el viento medido en la banda del señuelo. Compatible con deriva si
el punto queda a sotavento (menos de 45° más la dispersión de las direcciones) y a una distancia
que el viento cubre en su tiempo máximo; no compatible si va contra el viento (90° o más) o más
lejos de lo que el viento lleva; indeterminada con viento flojo, sin dirección (solo el día), con
las direcciones repartidas más de 45° o a menos de 5 km de la frontera.

**Horizonte de radar** (`horizonte_radar` 1.0.0), en cada incidente con punto en una
instalación: radar en el punto con la antena a 15 m (supuesto declarado en el resultado; no hay
datos públicos de las antenas), refracción normal (radio efectivo de 4/3), 36 sectores de 10°,
perfil cada 250 m hasta 30 km sobre Copernicus DEM GLO-90; por sector y a 1, 2, 5, 10, 20 y
30 km, la altura sobre el terreno por debajo de la cual un dron queda oculto.

## 6. Resultados en la base

Pasada completa sobre la base del 2 de octubre de 2026 (382 incidentes vigentes, 753 impactos
con lugar que no son partes diarios ni FPV, 4.605 ataques):

| Tipo | Casos | Con alguna clase descartada | Sin ninguna compatible (sin datos) | Compatibles de media | Con conflicto |
| --- | ---: | ---: | ---: | ---: | ---: |
| Incidentes | 382 | 0 | 147 | 7,36 | 0 |
| Impactos de guerra | 753 | 38 | 80 | 6,96 | 0 |
| Ataques | 4.605 | 25 | 4.124 (sin impactos con lugar) | 0,81 | 0 |

- En los impactos, las clases descartadas son los multirrotores (de consumo, profesionales y
  pesados: 37–38 impactos) y el ala fija táctica eléctrica (6): impactos a cientos de km de la
  zona de lanzamiento del parte o de las fronteras de Ucrania. Las de largo alcance quedan
  compatibles o indeterminadas (algún modelo sin dato).
- Conclusiones en incidentes: «despegue cercano o dron de largo alcance» en 18 (los que están a
  más de 100 km de cualquier exterior: Hannover, Fráncfort, Leipzig, Varsovia, Sofía, Wunstorf);
  «varios drones o equipos» en 2. Interferencia GNSS medida en 85: alta en 10, media en 23.
- Ningún incidente europeo con clase descartada. Es lo que dan los datos: sin altura, velocidad
  ni trayectoria, con viento medido por debajo de los límites con margen y sin entrada declarada
  por una autoridad en los incidentes con punto.

**Deriva en los cruces a países de la OTAN** (30 evaluados):

| Resultado | Incidentes |
| --- | --- |
| Compatible con deriva | EODI-2026-00189 (dron derribado sobre una base aérea de Rumanía): 97 km de la frontera ucraniana, viento de 9,6 m/s hacia donde cayó (0,3° de desvío, dispersión 23°) |
| No compatible con deriva | EODI-2026-00049 (Vilna): desplazamiento a 121° del viento de 4,7 m/s: exige rumbo propio |
| Indeterminado | 28: 22 con solo el día o sin medida (sin dirección del viento), 3 con viento flojo, 2 con las direcciones de la banda repartidas y 1 pegado a la frontera |

Los cruces que dan los partes de la capa de guerra (a Bielorrusia y Rumanía, sin punto de caída)
quedan indeterminados en su ataque: el parte da el país, no el punto.

## 7. Validación

**Casos de modelo conocido** (`configuracion/validacion_deduccion.json`, 28 casos con sus
fuentes, punto de su localidad de OpenStreetMap Nominatim y la clase real; dos excluidos porque
su modelo no está en el catálogo: un Geran-4 en Moldavia y un Maya ucraniano en Bulgaria). Se
evalúan con el viento y la temperatura de su punto y su día y sin el nombre del modelo (si no,
la regla de descripción lo apoyaría sola):

| Resultado | Casos |
| --- | ---: |
| Acierto (la clase real queda compatible) | 26 |
| Fallo grave (la clase real queda descartada) | **0** |
| Indeterminado | 0 |
| De ellos en la base (Galați 2026 ×2 y Cuhureștii de Jos), con el resultado guardado | 3 aciertos |

Por modelo: 12 Gerbera (Polonia 5, Lituania 2, Rumanía 2, Moldavia 2 y Turquía 1), 11
Geran-2/Shahed (Rumanía 8, Moldavia 2, Letonia 1), 1 Orlan-10 (Turquía), 1 DJI Mini 2 (Dublín,
incautado por la policía) y 1 DJI sin modelo (Wilhelmshaven, policía). En el caso de
Gaižiūnai (Lituania, Gerbera entrado desde Bielorrusia según la autoridad) el motor descarta los
multirrotores de consumo por distancia y deja el señuelo compatible: es el único caso de la
validación en que descarta algo. Un caso de la base (EODI-2025-00261, Cuhureștii de Jos) tiene
«Shahed» como modelo según la prensa y la fuente oficial dice Gerbera: el motor no lo usa para
descartar (la descripción nunca descarta).

**Encuentros de la UK Airprox Board** (41 desde 2022 con altura, descripción y tipo
multirrotor o ala fija según la UKAB, con el viento de Open-Meteo en su punto y su hora): la
regla de viento no descarta nunca el tipo de la UKAB (0 incoherencias); la descripción apoya su
tipo en 36, no tiene rasgos en 4 y va en contra en 1 (UKAB-2024033, «a very small drone or model
aircraft» que la UKAB clasifica como ala fija: el catálogo no tiene aeromodelos pequeños de ala
fija, todas sus alas fijas son medianas o grandes).

**Lectura honesta.** Cero fallos graves, pero con un poder de descarte bajo: acertar es fácil
cuando casi nada se descarta. Las validaciones son un control de seguridad (las reglas no
contradicen casos conocidos), no una medida de lo que discrimina el motor.

## 8. Esquema, exportación y AEGIS

- **Esquema 1.7.0** (menor): definición común `deduccion` y `evidencia_deduccion`, campo interno
  `deduccion` en incidente, ataque e impacto; el origen `deducido` deja de estar reservado. La
  base guarda lo deducido en la tabla `deducciones` (con historial, sin borrado) y la
  exportación lo pega a cada documento, como hace con FIRMS y las mediciones.
- **Procedencia**: `procedencia["deduccion"] = {origen: deducido, metodo: regla, fuentes: [],
  regla: {nombre: motor_deduccion, version}}`. El nivel de detalle se calcula sin el bloque
  (test que compara la exportación con y sin deducción).
- **Exportación 1.3.0**: además del bloque, `catalogo_drones.json`, `catalogo_fuentes.json`,
  `zonas_lanzamiento.json` (tal como están, con sus esquemas en `esquema/catalogo/`),
  `clases_dron.json` (clases con su envolvente) y `deduccion_validacion.json` (resumen de la
  validación, de Airprox y del poder de descarte). Vocabulario 1.3.0 con `clases_deduccion`.
- **AEGIS** (PR #45): `tools/vocabulario_eodi.json` al día, el resumen del importador
  cuenta los incidentes con deducción y da la validación, y `limites_por_clase(carpeta)` devuelve
  por clase los límites de movimiento (velocidades, autonomía, alcance, techo, altura típica,
  viento y peso, con su unidad y `None` donde no hay cota) y su clase de tamaño de AEGIS. Puerta
  local completa: 791 tests, ruff, formato y mypy --strict con numpy 2.4.6 y mypy 2.1.0.

## 9. Servidor

`eodi-deduccion.timer` en el minuto 5 de cada hora, `servidor/deduccion.sh` con su propio cerrojo (`deduccion.lock`), `Nice=15` y E/S en reposo; nunca toma el cerrojo de la recogida horaria (solo lee la base de la rama `estado`). La recogida horaria incorpora los resultados a la tabla `deducciones` en segundos. Detalle y órdenes en [`servidor.md`](servidor.md), «Motor de deducción».

Medido en el servidor (CX23, 2 vCPU, 3,8 GB) el 2 de octubre de 2026, con la rama antes de fusionar, como `eodi` y con prioridad baja, justo después de la recogida horaria:

| | Primera pasada (todo) | Pasada incremental |
| --- | ---: | ---: |
| Duración | 12 min 0 s | 1 min 9 s |
| CPU | 11 min 30 s | 51 s |
| Memoria (RSS máxima) | 933 MB | 932 MB |
| Casos calculados | 383 incidentes, 777 impactos, 4.605 ataques | 0 (todo sin cambios) |
| Teselas de relieve descargadas | 150 (el tope por ejecución), 641 MB | 0 |

La memoria es la de la base descifrada en memoria (unos 390 MB) más el cálculo; el pico de la recogida horaria es de 1,6–2 GB y van a horas distintas (minuto 5 frente al 17). El relieve se completa en las ejecuciones siguientes (tope de 150 teselas por ejecución) y luego solo crece con los incidentes nuevos en sitios nuevos. Disco libre del servidor: 31 GB. El horizonte de radar se calcula, por tanto, para todos los incidentes con punto en una instalación, no solo para los de nivel B: cabe.

## 10. Límites y pendiente

- **Poder de descarte bajo en Europa** mientras la base no tenga alturas, velocidades,
  trayectorias o entradas declaradas por una autoridad en incidentes con punto. Las reglas de
  velocidad, radar y simultaneidad están listas para cuando las haya.
- **Catálogo con huecos**: las clases militares no tienen viento máximo con fuente; el
  Lancet-53, el FPV militar por radio y algunas variantes del Geran-2 no tienen cifras, y por eso
  esas clases no se pueden descartar por distancia ni por viento. Cualquier ficha nueva con
  fuente sube el poder de descarte sin cambiar código (subiendo la versión del catálogo).
- **Alturas de vuelo**: los multirrotores no tienen altura típica con fuente (DJI da la altitud
  máxima de despegue, no la de vuelo), así que su banda va del suelo a su techo y el viento a
  favor que se suma es el más fuerte de toda esa banda: cota alta y conservadora.
- **Horizonte de radar**: la altura de la antena es un supuesto (15 m) y el DEM es de superficie
  (incluye edificios y árboles en parte).
- **Deriva**: sin la hora del incidente no hay dirección del viento; 22 de los 30 cruces no
  la tienen.
- **Aeromodelos**: no hay clase de aeromodelo pequeño de ala fija (caso de Airprox del apartado
  7).

## Anexo: tablas del catálogo

### Modelos y cifras principales

Velocidad máxima en km/h, autonomía en min, alcance en km, viento máximo en m/s y peso al despegue en kg, convertidos desde la unidad de cada fuente; entre corchetes, las fuentes. «sin fuente»: ninguna fuente fiable lo da.

| Clase | Modelo | Vel. máx. (km/h) | Autonomía (min) | Alcance (km) | Viento máx. (m/s) | Peso (kg) |
| --- | --- | --- | --- | --- | --- | --- |
| multirrotor_consumo_sub250 | DJI Mini 4 Pro | 57,6 [D19] | 30–45 [D19] | 18–25 [D19] | 10,7 [D19] | ≤ 0,249 [D19] |
| multirrotor_consumo | DJI Air 3 | 68,4–75,6 [D20] | 42–46 [D20] | 32 [D20] | 12 [D20] | 0,72 [D20] |
| multirrotor_consumo | DJI Air 3S | 68,4–97,2 [D21] | 41–45 [D21] | 32 [D21] | 12 [D21] | 0,724 [D21] |
| multirrotor_consumo | DJI Mavic 3 Classic | 68,4–75,6 [D3] | 40–46 [D3] | 30 [D3] | 12 [D3] | 0,895 [D3] |
| multirrotor_consumo | DJI Mavic 3 Pro | 75,6 [D5] | 37–43 [D5] | 28 [D5] | 12 [D5] | 0,958–0,963 [D5] |
| multirrotor_consumo | DJI Mavic 4 Pro | 90–97,2 [D9] | 45–51 [D10, D9] | 41 [D9] | 12 [D9] | 1,063 [D9] |
| multirrotor_consumo | Autel EVO II Pro V3 | 43,2–72 [A1] | 37–40 [A1, A2] | 25 [A1] | 10,7–12 [A1] | 1,191–1,27 [A1] |
| multirrotor_profesional | DJI Mavic 3 Enterprise | 68,4–75,6 [D7] | 36–45 [D7, D8] | 24–32 [D7] | 12 [D7] | 0,899–1,05 [D7] |
| multirrotor_profesional | DJI Mavic 3T | 68,4–75,6 [D7] | 36–45 [D7, D8] | 24–32 [D7] | 12 [D7] | 0,899–1,05 [D7] |
| multirrotor_profesional | DJI Matrice 4T | 75,6 [D23] | 42–49 [D16, D23] | 35 [D23] | 12 [D16, D23] | 1,219–1,43 [D16, D23] |
| multirrotor_profesional | DJI Matrice 4TD | 54–75,6 [D24] | 47–54 [D16, D24] | 10–43 [D24] | 12 [D16, D24] | 1,85–2,09 [D16, D24] |
| multirrotor_profesional | DJI Matrice 30T | 82,8 [D12, D13] | 36–41 [D12] | sin fuente | 12–15 [D12, D13] | 3,76–4,069 [D12] |
| multirrotor_profesional | DJI Matrice 350 RTK | 82,8 [D14] | 55 [D14] | sin fuente | 12 [D14, D15] | 6,47–9,2 [D14] |
| multirrotor_profesional | Autel EVO II Dual 640T V3 | 72 [A3] | 38 [A3, A4] | 22–25 [A3] | 10,7 [A3] | 1,209–1,27 [A3] |
| multirrotor_profesional | Autel EVO Max 4T | 82,8 [A5, A6] | 42 [A5, A6] | 25 [A5, A6] | 10,7–12 [A5, A6] | 1,645–1,999 [A5, A6] |
| multirrotor_profesional | Skydio X10 | 57,6–72,4 [S1, S2] | 40 [S2, S3] | sin fuente | 12,8 [S2] | 2,11–2,49 [S2] |
| multirrotor_pesado_carga | DJI Agras T50 | 36 [D25] | 6–16 [D25] | sin fuente | 6 [D25] | 39,9–103 [D25] |
| multirrotor_pesado_carga | Referencia genérica: multirrotor pesado de carga | 36–82,8 [D14, D25] (derivado) | 6–55 [D14, D25] (derivado) | sin fuente | 6–12 [D14, D15, D25] (derivado) | 6,47–103 [D14, D25] (derivado) |
| fpv | DJI Avata 2 | 68,4–97,2 [D22] | 21–23 [D22] | 13 [D22] | 10,7 [D22] | 0,377 [D22] |
| fpv | FPV militar por radio | sin fuente | sin fuente | 5–15 [F8] | sin fuente | 9,072 [F9] |
| fpv | FPV por fibra óptica | sin fuente | sin fuente | 10–50 [F5, F6, F7] | sin fuente | sin fuente |
| ala_fija_tactica_electrica | Supercam S350 | sin fuente | 270 [T2] | 240 [T2] | sin fuente | 15,5 [T2] |
| ala_fija_tactica_electrica | ZALA 421-16E | sin fuente | 210–240 [T16, T3] | 50 [T16] | sin fuente | 10,5–12 [T16, T3] |
| ala_fija_reconocimiento_combustion | Orlan-10 | 150 [T11] | 960 [T7] | 150–600 [T12, T7] | sin fuente | 18 [T7] |
| ala_fija_reconocimiento_combustion | Orlan-30 | 170 [T1] | 480 [T1] | 600 [T1] | sin fuente | sin fuente |
| ala_fija_reconocimiento_combustion | Referencia genérica: ala fija de reconocimiento mediana | 150–170 [T1, T11] (derivado) | 480–960 [T1, T7] (derivado) | 150–600 [T1, T12, T7] (derivado) | sin fuente | — [T7] (derivado) |
| ala_fija_male | Forpost-R | 200 [M3] | sin fuente | sin fuente | sin fuente | sin fuente |
| ala_fija_male | Orion | sin fuente | 1.440–1.800 [M1, M2] | sin fuente | sin fuente | 1.150 [M1, M2] |
| ala_fija_male | Bayraktar AKINCI | 444,5 [M4] | 1.200 [M4] | 6.000 [M4] | sin fuente | 6.000 [M4] |
| municion_merodeadora | Lancet Izdeliye-51 | sin fuente | 40–50 [T13, T4] | 45 [T13] | sin fuente | sin fuente |
| municion_merodeadora | Lancet Izdeliye-52 | sin fuente | 30 [T14] | 35 [T14] | sin fuente | sin fuente |
| municion_merodeadora | Lancet Izdeliye-53 | sin fuente | sin fuente | sin fuente | sin fuente | sin fuente |
| municion_merodeadora | KUB-UAV | sin fuente | 30 [T6] | sin fuente | sin fuente | sin fuente |
| municion_merodeadora | Italmas | sin fuente | sin fuente | 200 [I1] | sin fuente | sin fuente |
| municion_merodeadora | Molniya-1 | sin fuente | sin fuente | 30–35 [F1] | sin fuente | 7–8 [F1] |
| municion_merodeadora | Molniya-2 | sin fuente | 40 [F3] | 30 [F3] | sin fuente | 10 [F3] |
| ataque_largo_alcance_piston | Geran-2 | sin fuente | 600–720 [G1] | 1.000–2.500 [G1, G10, L5] | sin fuente | 200 [G1, L5] |
| ataque_largo_alcance_piston | Geran-2 serie «Э» (Kometa) y variantes | sin fuente | sin fuente | sin fuente | sin fuente | sin fuente |
| ataque_largo_alcance_piston | Shahed-136 con guiado térmico (ejemplar MS001) | sin fuente | sin fuente | 1.000 [G5] | sin fuente | sin fuente |
| ataque_largo_alcance_piston | Geran-1 | sin fuente | sin fuente | 700–1.000 [L1, L5] | sin fuente | 135 [L1, L5] |
| ataque_largo_alcance_piston | Liutyi | sin fuente | sin fuente | 800–2.000 [L10, L9] | sin fuente | 250–300 [L9] |
| ataque_largo_alcance_piston | FP-1 | 205 [L11] | 1.080 [L11] | 1.600–2.700 [L11, L12] | sin fuente | 330 [L11] |
| ataque_largo_alcance_piston | UJ-26 Bober | sin fuente | 420 [L13] | 1.000 [L13] | sin fuente | 150 [L13] |
| ataque_largo_alcance_piston | UJ-22 Airborne | 160–200 [L14, L16] | 360–840 [L14, L15, L16] | 800 [L14, L15] | sin fuente | 85 [L16] |
| senuelo_largo_alcance | Gerbera | 160 [G7, G8, L2] | sin fuente | 300–600 [G7, G8, L2] | sin fuente | 18–40 [G7, G8, L2] |
| senuelo_largo_alcance | Parodiya | 180–200 [P2] (débil) | sin fuente | 600 [P2] (débil) | sin fuente | 10–15 [P2] (débil) |
| ataque_reaccion | Geran-3 | 300–600 [L6, L7] | sin fuente | 1.000–2.500 [L6, L7] | sin fuente | 250–370 [L6] |
| ataque_reaccion | Tu-141 Strizh | 1.110 [L17] | sin fuente | 1.000 [L17] | sin fuente | 5.370 [L17] |

### Clases y envolventes

Cota de la clase (el mayor de sus modelos con dato). «parcial»: a algún modelo le falta el dato; sirve para decir que la clase puede, no para descartarla.

| Clase | Modelos | Alcance en calma (km) | Vel. máx. (m/s) | Tiempo de vuelo (min) | Viento máx. (m/s) | Esquema | AEGIS |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| multirrotor_consumo_sub250 | 1 | 25 | 16 | 45 | 10,7 | multirrotor_pequeno | mini |
| multirrotor_consumo | 6 | 41 | 27 | 51 | 12 | multirrotor_pequeno | phantom |
| multirrotor_profesional | 9 | 75,9 (deducida) | 23 | 55 | 15 | multirrotor_pequeno | inspire |
| multirrotor_pesado_carga | 2 | 75,9 (deducida) | 23 | 55 | 12 | — | — |
| fpv | 3 | 50 | 27 (parcial: falta 2) | 23 (parcial: falta 2) | 10,7 (parcial: falta 2) | multirrotor_pequeno | mini |
| ala_fija_tactica_electrica | 2 | 240 | sin dato | 270 | sin dato | ala_fija | — |
| ala_fija_reconocimiento_combustion | 3 | 600 | 47,2 | 960 | sin dato | ala_fija | — |
| ala_fija_male | 3 | 6.000 (parcial: falta 2) | 123,5 (parcial: falta 1) | 1.800 (parcial: falta 1) | sin dato | ala_fija | — |
| municion_merodeadora | 7 | 200 (parcial: falta 2) | sin dato | 50 (parcial: falta 3) | sin dato | ala_fija | — |
| ataque_largo_alcance_piston | 8 | 2.700 (parcial: falta 1) | 56,9 (parcial: falta 6) | 1.080 (deducida) (parcial: falta 3) | sin dato | ataque_largo_alcance | — |
| senuelo_largo_alcance | 2 | 600 (parcial: falta 1) | 44,4 (parcial: falta 1) | 300 (deducida) (parcial: falta 1) | sin dato | ataque_largo_alcance | — |
| ataque_reaccion | 2 | 2.500 | 308,3 | sin dato | sin dato | ataque_largo_alcance | — |

### Campos sin fuente por modelo

| Modelo | Campos sin fuente |
| --- | --- |
| DJI Mini 4 Pro | motor, envergadura, diagonal, longitud, carga_util, velocidad_crucero, altura_tipica, lluvia, interferencia_gnss, rcs, firma_acustica, luces, nocturna, lanzamiento, recuperacion, remote_id, rasgos_testigos |
| DJI Air 3 | motor, envergadura, diagonal, longitud, carga_util, velocidad_crucero, altura_tipica, lluvia, interferencia_gnss, rcs, firma_acustica, nocturna, lanzamiento, recuperacion, remote_id, rasgos_testigos |
| DJI Air 3S | motor, envergadura, diagonal, longitud, carga_util, velocidad_crucero, altura_tipica, lluvia, interferencia_gnss, rcs, firma_acustica, luces, nocturna, lanzamiento, recuperacion, remote_id, rasgos_testigos |
| DJI Mavic 3 Classic | motor, envergadura, diagonal, longitud, carga_util, velocidad_crucero, altura_tipica, lluvia, interferencia_gnss, rcs, firma_acustica, lanzamiento, recuperacion, remote_id, rasgos_testigos |
| DJI Mavic 3 Pro | motor, envergadura, diagonal, longitud, carga_util, velocidad_crucero, altura_tipica, lluvia, interferencia_gnss, rcs, firma_acustica, nocturna, lanzamiento, recuperacion, remote_id, rasgos_testigos |
| DJI Mavic 4 Pro | motor, envergadura, diagonal, longitud, carga_util, velocidad_crucero, altura_tipica, lluvia, interferencia_gnss, rcs, firma_acustica, luces, lanzamiento, recuperacion, remote_id, rasgos_testigos |
| Autel EVO II Pro V3 | envergadura, longitud, carga_util, velocidad_crucero, altura_tipica, rcs, firma_acustica, lanzamiento, recuperacion, rasgos_testigos |
| DJI Mavic 3 Enterprise | motor, envergadura, longitud, carga_util, velocidad_crucero, altura_tipica, lluvia, interferencia_gnss, rcs, firma_acustica, lanzamiento, recuperacion, remote_id, rasgos_testigos |
| DJI Mavic 3T | motor, envergadura, longitud, carga_util, velocidad_crucero, altura_tipica, lluvia, interferencia_gnss, rcs, firma_acustica, lanzamiento, recuperacion, remote_id, rasgos_testigos |
| DJI Matrice 4T | motor, envergadura, longitud, velocidad_crucero, altura_tipica, lluvia, interferencia_gnss, rcs, firma_acustica, lanzamiento, recuperacion, remote_id, rasgos_testigos |
| DJI Matrice 4TD | motor, envergadura, longitud, carga_util, velocidad_crucero, altura_tipica, interferencia_gnss, rcs, firma_acustica, lanzamiento, recuperacion, remote_id, rasgos_testigos |
| DJI Matrice 30T | motor, envergadura, longitud, carga_util, velocidad_crucero, alcance, altura_tipica, interferencia_gnss, rcs, firma_acustica, lanzamiento, recuperacion, remote_id, rasgos_testigos |
| DJI Matrice 350 RTK | motor, envergadura, longitud, velocidad_crucero, alcance, altura_tipica, interferencia_gnss, rcs, firma_acustica, lanzamiento, recuperacion, rasgos_testigos |
| Autel EVO II Dual 640T V3 | envergadura, longitud, carga_util, velocidad_crucero, altura_tipica, rcs, firma_acustica, lanzamiento, recuperacion, rasgos_testigos |
| Autel EVO Max 4T | envergadura, longitud, carga_util, velocidad_crucero, altura_tipica, rcs, firma_acustica, lanzamiento, recuperacion, rasgos_testigos |
| Skydio X10 | envergadura, diagonal, longitud, carga_util, velocidad_crucero, alcance, altura_tipica, rcs, firma_acustica, lanzamiento, recuperacion, clase_ue, rasgos_testigos |
| DJI Agras T50 | envergadura, longitud, velocidad_crucero, altura_tipica, interferencia_gnss, rcs, firma_acustica, lanzamiento, recuperacion, clase_ue, rasgos_testigos |
| DJI Avata 2 | motor, envergadura, diagonal, longitud, carga_util, velocidad_crucero, altura_tipica, lluvia, interferencia_gnss, rcs, firma_acustica, luces, nocturna, lanzamiento, recuperacion, remote_id, rasgos_testigos |
| FPV militar por radio | envergadura, diagonal, longitud, carga_util, velocidad_crucero, velocidad_maxima, enlace_alcance, autonomia, techo, altura_tipica, viento_maximo, temperatura, lluvia, navegacion, interferencia_gnss, rcs, firma_acustica, luces, nocturna, lanzamiento, recuperacion, clase_ue, remote_id |
| FPV por fibra óptica | motor, envergadura, diagonal, dimensiones, longitud, mtow, carga_util, velocidad_crucero, velocidad_maxima, enlace_alcance, autonomia, techo, viento_maximo, temperatura, lluvia, navegacion, interferencia_gnss, rcs, firma_acustica, luces, nocturna, lanzamiento, recuperacion, clase_ue, remote_id |
| Supercam S350 | diagonal, dimensiones, longitud, velocidad_maxima, enlace_tipo, techo, viento_maximo, lluvia, navegacion, interferencia_gnss, rcs, firma_acustica, luces, nocturna, clase_ue, remote_id, rasgos_testigos |
| ZALA 421-16E | diagonal, dimensiones, longitud, velocidad_maxima, viento_maximo, lluvia, navegacion, interferencia_gnss, rcs, luces, clase_ue, remote_id, rasgos_testigos |
| Orlan-10 | diagonal, dimensiones, altura_tipica, viento_maximo, lluvia, rcs, firma_acustica, luces, clase_ue, remote_id, rasgos_testigos |
| Orlan-30 | motor, diagonal, dimensiones, mtow, velocidad_crucero, enlace_tipo, altura_tipica, viento_maximo, temperatura, lluvia, navegacion, interferencia_gnss, rcs, firma_acustica, luces, nocturna, clase_ue, remote_id, rasgos_testigos |
| Forpost-R | motor, diagonal, dimensiones, mtow, carga_util, velocidad_crucero, alcance, enlace_tipo, autonomia, altura_tipica, viento_maximo, temperatura, lluvia, navegacion, interferencia_gnss, rcs, firma_acustica, luces, nocturna, lanzamiento, recuperacion, clase_ue, remote_id, rasgos_testigos |
| Orion | diagonal, dimensiones, velocidad_maxima, alcance, altura_tipica, viento_maximo, temperatura, lluvia, navegacion, rcs, firma_acustica, clase_ue, remote_id, rasgos_testigos |
| Bayraktar AKINCI | diagonal, enlace_alcance, viento_maximo, temperatura, lluvia, navegacion, interferencia_gnss, rcs, firma_acustica, luces, clase_ue, remote_id, rasgos_testigos |
| Lancet Izdeliye-51 | envergadura, diagonal, dimensiones, longitud, mtow, velocidad_maxima, techo, altura_tipica, viento_maximo, temperatura, lluvia, interferencia_gnss, rcs, luces, lanzamiento, recuperacion, clase_ue, remote_id, rasgos_testigos |
| Lancet Izdeliye-52 | envergadura, diagonal, dimensiones, longitud, mtow, velocidad_maxima, techo, altura_tipica, viento_maximo, temperatura, lluvia, interferencia_gnss, rcs, luces, lanzamiento, recuperacion, clase_ue, remote_id, rasgos_testigos |
| Lancet Izdeliye-53 | motor, envergadura, diagonal, dimensiones, longitud, mtow, carga_util, velocidad_crucero, velocidad_maxima, alcance, enlace_alcance, enlace_tipo, autonomia, techo, altura_tipica, viento_maximo, temperatura, lluvia, interferencia_gnss, rcs, firma_acustica, luces, nocturna, recuperacion, clase_ue, remote_id, rasgos_testigos |
| KUB-UAV | diagonal, dimensiones, mtow, velocidad_maxima, alcance, enlace_alcance, enlace_tipo, techo, altura_tipica, viento_maximo, temperatura, lluvia, navegacion, interferencia_gnss, rcs, firma_acustica, luces, nocturna, recuperacion, clase_ue, remote_id, rasgos_testigos |
| Italmas | envergadura, diagonal, dimensiones, longitud, mtow, carga_util, velocidad_crucero, velocidad_maxima, enlace_alcance, enlace_tipo, autonomia, techo, altura_tipica, viento_maximo, temperatura, lluvia, navegacion, interferencia_gnss, rcs, firma_acustica, luces, nocturna, recuperacion, clase_ue, remote_id, rasgos_testigos |
| Molniya-1 | diagonal, dimensiones, velocidad_crucero, velocidad_maxima, enlace_alcance, enlace_tipo, autonomia, techo, altura_tipica, viento_maximo, temperatura, lluvia, navegacion, interferencia_gnss, rcs, firma_acustica, luces, nocturna, lanzamiento, recuperacion, clase_ue, remote_id, rasgos_testigos |
| Molniya-2 | envergadura, diagonal, dimensiones, longitud, velocidad_crucero, velocidad_maxima, enlace_alcance, techo, altura_tipica, viento_maximo, temperatura, lluvia, navegacion, interferencia_gnss, rcs, firma_acustica, luces, lanzamiento, recuperacion, clase_ue, remote_id, rasgos_testigos |
| Geran-2 | diagonal, dimensiones, velocidad_maxima, enlace_alcance, techo, viento_maximo, temperatura, lluvia, luces, recuperacion, clase_ue, remote_id |
| Geran-2 serie «Э» (Kometa) y variantes | envergadura, diagonal, dimensiones, longitud, mtow, velocidad_crucero, velocidad_maxima, alcance, enlace_alcance, autonomia, techo, altura_tipica, viento_maximo, temperatura, lluvia, rcs, firma_acustica, luces, recuperacion, clase_ue, remote_id |
| Shahed-136 con guiado térmico (ejemplar MS001) | envergadura, diagonal, dimensiones, longitud, mtow, carga_util, velocidad_crucero, velocidad_maxima, autonomia, techo, altura_tipica, viento_maximo, temperatura, lluvia, navegacion, rcs, firma_acustica, luces, lanzamiento, recuperacion, clase_ue, remote_id, rasgos_testigos |
| Geran-1 | diagonal, dimensiones, velocidad_maxima, enlace_alcance, enlace_tipo, autonomia, techo, altura_tipica, viento_maximo, temperatura, lluvia, navegacion, interferencia_gnss, rcs, firma_acustica, luces, nocturna, recuperacion, clase_ue, remote_id |
| Liutyi | diagonal, dimensiones, velocidad_crucero, velocidad_maxima, enlace_alcance, enlace_tipo, autonomia, techo, altura_tipica, viento_maximo, temperatura, lluvia, interferencia_gnss, rcs, firma_acustica, luces, nocturna, lanzamiento, recuperacion, clase_ue, remote_id |
| FP-1 | diagonal, dimensiones, longitud, enlace_alcance, enlace_tipo, techo, altura_tipica, viento_maximo, temperatura, lluvia, navegacion, interferencia_gnss, rcs, firma_acustica, luces, nocturna, recuperacion, clase_ue, remote_id |
| UJ-26 Bober | motor, diagonal, dimensiones, velocidad_maxima, enlace_alcance, enlace_tipo, techo, altura_tipica, viento_maximo, temperatura, lluvia, interferencia_gnss, rcs, firma_acustica, luces, recuperacion, clase_ue, remote_id |
| UJ-22 Airborne | diagonal, dimensiones, viento_maximo, temperatura, lluvia, interferencia_gnss, rcs, firma_acustica, luces, nocturna, recuperacion, clase_ue, remote_id, rasgos_testigos |
| Gerbera | diagonal, dimensiones, enlace_alcance, autonomia, techo, viento_maximo, temperatura, lluvia, firma_acustica, luces, recuperacion, clase_ue, remote_id |
| Parodiya | diagonal, dimensiones, velocidad_crucero, enlace_alcance, enlace_tipo, autonomia, techo, altura_tipica, viento_maximo, temperatura, lluvia, navegacion, interferencia_gnss, firma_acustica, luces, nocturna, lanzamiento, recuperacion, clase_ue, remote_id |
| Geran-3 | diagonal, dimensiones, velocidad_crucero, enlace_alcance, enlace_tipo, autonomia, altura_tipica, viento_maximo, temperatura, lluvia, rcs, firma_acustica, luces, nocturna, recuperacion, clase_ue, remote_id, rasgos_testigos |
| Tu-141 Strizh | diagonal, carga_util, velocidad_crucero, enlace_alcance, enlace_tipo, autonomia, viento_maximo, temperatura, lluvia, navegacion, interferencia_gnss, rcs, firma_acustica, luces, nocturna, clase_ue, remote_id, rasgos_testigos |
