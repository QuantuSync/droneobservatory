# Focos térmicos de NASA FIRMS en los impactos de la capa de guerra

Fecha: 1 de octubre de 2026. Rama `firms-focos-termicos`, PR #27.

Cada impacto declarado con lugar preciso se cruza con las anomalías térmicas que detectan
los satélites (NASA FIRMS). Si en su radio y su ventana aparece un foco nuevo, o una
fuente de calor habitual con una potencia anómala, el impacto lleva un foco térmico
detectado, que la web muestra con una marca y una línea en su ficha. La ausencia de foco no
demuestra nada y no se publica.

## 1. Inventario de impactos con lugar en la base

Base real descargada de la rama `estado` y descifrada fuera del repositorio el 1 de octubre
de 2026 (08:05 UTC). Sin llamadas nuevas al extractor.

| Tipo | Cuántos | Precisión de lugar | Hora |
| --- | --- | --- | --- |
| Ataques RU→UA (partes de la Fuerza Aérea) | 1095 | — | periodo del parte |
| … que declaran localizaciones con impacto (`localizaciones_impacto` > 0) | 447 (5562 localizaciones como mínimo) | sin lugar: el parte solo da la cifra | periodo |
| … que nombran lugares con impacto (`lugares_impacto`) | 24 ataques, 48 nombres | **región**: el analizador de partes solo reconoce regiones (y Kiev ciudad, UA-30, que es una región ISO) | periodo con minuto (19) o aproximado (5) |
| Regiones con impacto de esos ataques (nombre que casa con una región del ataque) | 47 | región (decenas de km) | periodo |
| Ataques UA→RU (Ministerio de Defensa ruso) | 3506 | el parte solo da derribos por región; ningún impacto | — |
| Incidentes en territorio ruso o ucraniano | 0 | — | — |
| Fichas negativas del extractor que hablan de ataques en Rusia o en Crimea (Saki, Engels y Sarátov, una refinería del suroeste, instalaciones petroleras, aeropuertos) | una decena, identificadas a mano entre las fichas negativas | ninguna: una ficha negativa no lleva lugar (las instrucciones del extractor excluyen los ataques de la guerra en Ucrania y Rusia) | — |
| Incidentes vigentes con prueba de impacto (el dron explotó o cayó: evidencia `explosion` o `caida`) | 46 | 17 sin punto (región o país); 11 fuera de la zona de FIRMS (Alemania, Chipre); **18 con punto y radio de 3 a 10 km dentro de la zona** (Moldavia, Rumanía, Bulgaria, Lituania, Estonia, Finlandia, Polonia) | 15 con solo el día, 3 con minuto |

Conclusión: hoy los únicos impactos evaluables son los 18 incidentes con punto. Los
impactos de los partes ucranianos solo se conocen por región y quedan como no evaluables;
para evaluarlos haría falta que el parte (o una fuente que lo acompañe) diera la localidad o
la instalación, y un nomenclátor de Ucrania. Los ataques en Rusia no existen en la base como
impactos: el extractor los descarta por diseño. Ninguno de los candidatos pendientes los
convertiría en impactos con lugar.

## 2. Fuentes y fechas de FIRMS

Comprobado el 1 de octubre de 2026 con `/api/data_availability/csv/<clave>/ALL` y la
documentación de la API de área (`/api/area/csv/<clave>/<fuente>/<oeste,sur,este,norte>/<días>/<fecha>`,
de 1 a 5 días por llamada, 5000 transacciones cada 10 minutos):

| Producto | Fechas |
| --- | --- |
| `VIIRS_SNPP_SP` | 2012-01-20 a 2026-06-30 |
| `VIIRS_NOAA20_SP` | 2018-04-01 a 2026-06-30 |
| `MODIS_SP` | 2000-11-01 a 2026-06-30 |
| `VIIRS_SNPP_NRT`, `VIIRS_NOAA20_NRT`, `MODIS_NRT` | 2026-07-01 en adelante |
| `VIIRS_NOAA21_NRT` | 2024-01-17 en adelante (NOAA-21 no tiene SP) |

- **Zona**: 22° E a 60° E y 43° N a 61° N. Cubre Ucrania, Moldavia, Crimea y la Rusia
  europea hasta los Urales; `tests/test_firms.py` comprueba que caen dentro Ust-Luga,
  Primorsk, Kirishi, Tuapse, Novorossiysk, Volgogrado, Sarátov, Kstovo, Riazán, Nizhnekamsk,
  Ufá, Perm, Oremburgo, Engels, Sebastopol, Odesa, Leópolis, Uzhgorod, Chisináu y Galați.
- **Recogida horaria**: dentro de la ejecución de cada hora, y solo si han pasado 3 horas o
  más desde la última descarga correcta, los dos últimos días de los cuatro productos NRT
  (cuatro llamadas). Un fallo no cambia el código de salida de la recogida: queda en el
  diario, sin la clave, y en `estado.json` como fuente `firms` no leída; la ejecución
  siguiente lo vuelve a intentar.
- **Histórico**: desde el 1 de octubre de 2022, SP de cada producto mientras lo hay y NRT
  desde el día siguiente al último SP; unos 1100 tramos de 5 días.
- **Almacenamiento**: `/home/eodi/datos/firms/<producto>/<año>/<AAAA-MM-DD>.csv.gz`, un fichero
  por día también cuando no hay focos (así consta como descargado). Fuera del repositorio y de
  la base. En la base solo entran la evaluación de cada impacto (`focos_termicos`, con
  historial) y los focos que cuentan (`focos_casados`, solo inserciones).
- **Clave**: `%USERPROFILE%\.eodi\firms_map_key.txt`, secreto `EODI_FIRMS_MAP_KEY` del
  repositorio y línea `EODI_FIRMS_MAP_KEY` del `extractor.env` del servidor (600). Toda URL o
  mensaje de error pasa por `redactar` antes de llegar al registro; las excepciones no se
  encadenan (llevarían la URL). Probado en `tests/test_firms.py`.

## 3. Regla final y umbrales

Por código, sin modelo (`proceso/focos_termicos.py`):

1. Impacto evaluable: punto con radio de precisión de 10 km o menos. Radio de búsqueda: ese
   radio, con un mínimo de 2 km. Sin punto o con radio mayor: no evaluable
   (`sin_lugar_preciso`); fuera de la zona: `fuera_de_zona`; base anterior a octubre de 2022:
   `sin_datos_firms`.
2. Ventana: del inicio del periodo a 36 horas después de su fin. Si la fuente solo da el día,
   el fin es el final de ese día.
3. Confianza: se descartan VIIRS «l» y MODIS por debajo de 30 (la clase baja de MODIS según
   FIRMS).
4. Línea base: los focos de cualquier confianza en el mismo radio en los 30 días anteriores.
   Un foco de la ventana es de un sitio habitual si hay uno de la base a 1 km (VIIRS) o 2 km
   (si interviene MODIS); cuenta si es nuevo o si su potencia (FRP) pasa de **4 veces** la
   mayor de ese sitio en la base con el mismo instrumento.
5. Detectado si cuentan **al menos 2 focos**. Si cuenta uno solo: no detectado
   (`foco_aislado`). Si no, `sin_focos`, `solo_baja_confianza` o `fuente_habitual`.
6. Una evaluación se rehace mientras su ventana cerró hace menos de 7 días; si falta algún día
   de datos de la ventana o hay menos de 20 días de base, queda pendiente.

**Cómo se fijaron los umbrales.** Se evaluaron todas las noches de mayo a julio de 2025 en 12
instalaciones con calor habitual o atacadas alguna vez (refinerías de Kirishi, Riazán,
Tuapse, Volgogrado, Sarátov y Kstovo; Ust-Luga; depósito Kristall de Engels; puerto de
Primorsk; centrales de Burshtyn, Zmiiv y Trypillia): 1068 noches-instalación.

- La razón entre la potencia de un foco de sitio habitual y la mayor de su base (1789 focos)
  tuvo mediana 0,26, percentil 95 de 1,43 y **percentil 99 de 3,14** (máximo 8,65). Con factor
  3 pasaban 21 focos; con 4, 6. En los ataques validados la razón pasó de 8 (Sarátov: 11,6 MW
  frente a 1,4) y de 17 (Kirishi).
- Con un solo foco bastando salían 21 noches positivas: 15 eran focos sueltos en Riazán,
  Volgogrado y Sarátov sin ataque conocido (quemas o antorchas en píxeles nuevos). Todos los
  ataques detectados tuvieron 3 focos o más. Exigir 2 deja **4 noches positivas** (2 episodios):
  - Engels, 4-5 y 5-6 de junio de 2025: 40 focos de hasta 296 MW a 0,3 km del depósito
    Kristall, primer foco el 6 de junio a las 00:33 UTC. **Ataque real**: dron ucraniano la
    noche del 5 al 6 de junio, incendio de varios días (Ukrainska Pravda, 6 de junio de 2025;
    Euromaidan Press, 8 de junio de 2025). La noche anterior sale porque su ventana llega a 36
    horas después.
  - Kirishi, 26-27 de julio de 2025: 7 focos de poca potencia (0,5-4,4 MW) a unos 2 km de la
    refinería, en varios pasos de día y de noche, sin focos en la base. No consta ataque
    (los de 2025 fueron el 29 de agosto y el 14 de septiembre): **falso positivo** probable, un
    sitio con calor que la base de 30 días no vio.
- Tasa de positivos en noches sin ataque: 2 de 1068 (0,2 %).

## 4. Validación con casos reales documentados (2024-2026)

Coordenadas de OpenStreetMap (Nominatim y Overpass); las de Primorsk y Ust-Luga, aproximadas.
Ventana: la noche del ataque en hora UTC.

| Caso | Fecha | Resultado | Detalle |
| --- | --- | --- | --- |
| Ust-Luga, complejo de Novatek | 21-01-2024 | no detectado | ningún foco a menos de 138 km en toda la ventana: nubes |
| Refinería de Tuapse | 25-01-2024 | no detectado | ningún foco a menos de 124 km |
| Refinería de Volgogrado | 03-02-2024 | no detectado | ningún foco a menos de 36 km |
| Refinería de Kstovo (NORSI) | 12-03-2024 | no detectado | ningún foco a menos de 147 km |
| Refinería de Kirishi | 13-03-2024 | no detectado | ningún foco a menos de 63 km |
| Refinería de Riazán | 13-03-2024 | no detectado | ningún foco a menos de 138 km |
| Central de Burshtyn | 22-03-2024 | **detectado** | 3 focos VIIRS (NOAA-20) a 0,7 km, 01:16 UTC |
| Central de Zmiiv | 22-03-2024 | no detectado | el foco más cercano, a 15 km |
| Central de Trypillia | 11-04-2024 | no detectado | el foco más cercano, a 20 km |
| Refinería de Tuapse | 17-05-2024 | no detectado | ningún foco a menos de 96 km |
| Depósito Kristall, Engels | 08-01-2025 | no detectado | ningún paso con focos a menos de 300 km: nubes de invierno |
| Depósito Kristall, Engels | 06-06-2025 | **detectado** | 40 focos (NOAA-21) a 0,3 km, 00:33 UTC, hasta 296 MW |
| Refinería de Riazán | 24-01-2025 | no detectado | ningún foco a menos de 783 km |
| Refinería de Kstovo (NORSI) | 29-01-2025 | no detectado | ningún foco a menos de 373 km |
| Refinería de Volgogrado | 03-02-2025 | **detectado** | 13 focos (NOAA-21) a 2,2 km, 23:01 UTC, sin base |
| Refinería de Sarátov | 10-08-2025 | **detectado** | 10 focos (NOAA-21) a 0,5 km, 00:13 UTC; 27 MW frente a 1,4 de las antorchas |
| Puerto de Primorsk | 12-09-2025 | no detectado | el foco más cercano, a 35 km |
| Refinería de Kirishi (KINEF) | 14-09-2025 | **detectado** | 10 focos (NOAA-21) a 1,9 km, 23:16 UTC; 6,1 MW frente a 0,36 de la base |

Controles, los mismos sitios en noches sin ataque conocido: Kirishi 14-08-2024, Riazán
20-09-2024, Tuapse 10-10-2024, Sarátov 15-05-2025, Kstovo 20-06-2025 (249 focos de antorcha
en la base), Volgogrado 25-06-2025 (5 focos de antorcha en la ventana, descartados como
fuente habitual), Ust-Luga 15-07-2025 y Riazán 10-03-2026: **8 de 8 sin foco detectado**.

Aciertos: 5 de 18 ataques detectados, 0 falsos positivos en 8 controles. Los 13 fallos son
todos `sin_focos`: ningún foco válido dentro del radio en toda la ventana, y casi siempre
ninguno en decenas o cientos de kilómetros. Son noches de invierno con nubes, incendios
apagados antes del paso siguiente o el fuego tapado por el humo; la regla no descartó ningún
foco real. Por eso la ausencia no se publica. Ningún acierto depende de que la base sea
cero: Sarátov y Kirishi tenían antorchas en la base y pasaron por potencia y por píxeles
nuevos.

## 5. Resultado en los impactos de la base

Con los datos descargados para la validación (antes del despliegue):

| Resultado | Cuántos |
| --- | --- |
| Detectado | 1: EODI-2026-00200, Galați (restos de drones rusos, 25-04-2026), 4 focos VIIRS a 7,4 km. Galați está frente a Reni (Ucrania), atacada la misma noche: el foco puede ser de ese ataque, al otro lado del Danubio, dentro del radio de 10 km de la ciudad |
| No detectado | 16, todos `sin_focos` |
| Pendiente | 1 (EODI-2026-00168, del 30 de septiembre: su ventana aún no tenía todos sus días) |
| No evaluable | 75: 47 regiones de partes ucranianos y 17 incidentes sin punto (`sin_lugar_preciso`); 11 incidentes fuera de la zona (`fuera_de_zona`) |

Las cifras definitivas, calculadas en el servidor, están en el apartado 7.

## 6. Web

- Ficha de incidente, de ataque y panel de región: fila «Satélite» con «Foco térmico detectado
  por satélite» / «Thermal hotspot detected by satellite», la hora UTC del primer foco, el
  instrumento y el satélite, la distancia y un enlace al visor de FIRMS en ese día y esa
  posición (`/map/#d:<día>..<día>;@<lon>,<lat>,<zoom>z`). Solo enlace: la web no carga nada de
  terceros y la CSP no cambia.
- Mapa: un punto claro con borde oscuro arriba a la derecha del símbolo de un incidente (o de
  una pila que contenga uno) con foco; en la capa de Ucrania, en el centro de la región, que
  se calcula en el build a partir de su contorno público (el parte no da el punto). Sin color:
  los colores son solo para los estados. Entrada en la ayuda, que hace de leyenda.
- Metodología y licencias, en español e inglés: qué significa la marca, sus límites (nubes,
  antorchas, la ausencia no demuestra nada) y la atribución obligatoria de FIRMS.
- `estado.json` trae `firms` como sexta fuente; la web la valida y la nombra.
- La regla de omitir build (`web/scripts/omitir-build.ts`) no cambia: el foco viaja dentro de
  `publicacion/`, que ya dispara el despliegue.
- Comprobado en local con un foco de prueba en 360×800, 390×844, 412×915 y 1440×900: la línea
  cabe sin desbordar y el documento no tiene desplazamiento horizontal. Capturas de producción
  en `docs/capturas/`.

## 7. Despliegue, reconstrucción histórica y fusión

- **PR #27** fusionado el 1 de octubre a las 09:34 UTC (f4c6713), con el procedimiento nuevo
  de `docs/fusiones.md` (apartado 9). Servidor actualizado con `bash servidor/reconstruir.sh`
  (instala `/home/eodi/datos/firms` con permisos 700 y deja `EODI_FIRMS_MAP_KEY` en
  `extractor.env`, 600, junto a las variables del extractor).
- **Histórico**: lanzado a las 09:35 con `systemd-run --unit=eodi-firms-historico` y terminado
  a las 10:38 (dos tandas, sin solaparse con la horaria). 5375 ficheros diarios, 51 MB:
  SP de Suomi NPP, NOAA-20 y MODIS del 2022-10-01 al 2026-06-30 (1369 días cada uno), NRT de
  los tres del 2026-07-01 al 2026-10-01 y NOAA-21 NRT del 2024-01-17 al 2026-10-01 (989 días).
  Mucho menos de lo previsto: el rectángulo, de noche y con la confianza que da FIRMS, trae
  de cientos a pocos miles de focos al día.
- **Recogida de las 10:17: fallida.** La exportación rechazó la ventana de EODI-2026-00203
  (del 30 de septiembre) como «fecha futura»: la ventana acaba 36 horas después del fin del
  impacto y la validación comprueba que ningún instante sea futuro. No publicó ni subió la
  base; `estado.json` la dio por fallida y la vigilancia no llegó a avisar (la última
  correcta era de las 09:21). Arreglado en el **PR #30** (la comprobación ya no mira
  `foco_termico.ventana`), con test que reproduce el caso y el ciclo completo comprobado sobre
  la base real.
- **PR #28**: mientras el histórico llegaba producto a producto, un impacto antiguo se habría
  evaluado con solo algunos productos y no se habría vuelto a mirar; ahora se reevalúa todo
  hasta un día después de terminar el histórico.
- **PR #31**: la exportación semanal para AEGIS (PR #29, de la misma mañana) lee los documentos
  guardados, que no llevan el foco; ahora añade el bloque completo desde su tabla.
- **Recogida lanzada a mano a las 10:43** (cerrojo libre tras el histórico), con todo lo
  anterior: correcta, publicada en `main` (a1d6c7b). Cruce: 93 evaluaciones, 2 pendientes.
  `estado.json`: resultado `correcta` y `firms` leída con su última descarga correcta.
- **Recogida horaria de las 11:17** (la primera del temporizador con todo desplegado):
  correcta en 4 minutos; cruce sin cambios (93 evaluaciones iguales, 2 pendientes); `firms`
  leída. FIRMS no se descargó porque no habían pasado 3 horas desde las 10:17.
- **Ficheros públicos**: solo EODI-2026-00200 lleva `foco_termico`, con resultado, primer
  foco, satélite, instrumento, distancia y número de focos. Ningún `no_detectado`,
  `no_evaluable`, motivo, FRP ni línea base en `incidentes.geojson`, `ucrania.json` ni
  `incidentes_sin_ubicacion.json`.
- **Producción**: droneobservatory.eu sirve la marca y la línea de EODI-2026-00200; capturas
  en `docs/capturas/firms-foco-escritorio.png` y `docs/capturas/firms-foco-390x844.png`. La
  suite `e2e/telefono.spec.ts` pasa contra producción en 360×800, 390×844 y 412×915, en vertical
  y en horizontal.

Resultado en la base tras el histórico completo:

| Resultado | Cuántos |
| --- | --- |
| Detectado | 1 (EODI-2026-00200, Galați: 4 focos VIIRS de NOAA-21 a 7,4 km, 26-04-2026 10:45 UTC) |
| No detectado | 16 |
| No evaluable | 76 (47 regiones de partes ucranianos y 29 incidentes sin punto o fuera de la zona) |
| Pendiente | 2 (impactos de las últimas 36 horas) |

## 9. Cambio en el procedimiento de fusión

Al fusionar el PR #26 se vio que el procedimiento anterior (reset --soft y un commit con el
árbol de la rama) revertía los commits de datos que el servidor sube a `main` cada hora
mientras la rama vive (el 14e7a02 se habría deshecho). `docs/fusiones.md` queda así: fetch y
rebase sobre `origin/main` justo antes (en conflicto en los datos publicados gana `main`),
tests y CI sobre la rama rebasada, commit único con el autor anónimo, comprobación obligatoria
de `git diff --name-only origin/main HEAD` (ningún fichero de datos que el PR no toque a
propósito), push solo por avance rápido y, después, que el número de incidentes de producción
no baje. Cada paso lleva su porqué en el documento.

Resultado en las fusiones de esta tarea:

| PR | main antes | Ficheros de datos en la diferencia | Datos publicados antes y después | Incidentes en producción |
| --- | --- | --- | --- | --- |
| #27 | 177042c, un commit de datos del servidor que entró mientras la rama vivía: se hizo rebase a las 09:31 y se repitió la CI | ninguno | idénticos (mismos blobs) | 374 → 374 |
| #28 | f4c6713 | ninguno | idénticos | 374 → 374 |
| #30 | f51fb8d (PR #29 de otra sesión, entró entre la CI y la fusión) | ninguno | idénticos | 374 → 374 |
| #31 | 9810848 | ninguno | idénticos | 374 → 376 (recogida de las 10:43) |

En el #30 hubo un fallo de procedimiento: `main` había avanzado con el PR #29 y el rebase rehízo
el commit, pero no repetí la CI sobre la rama rebasada antes del push (paso c). Lo comprobé
después: puerta local (867 tests, ruff, mypy) y workflow de `main` en verde sobre 9810848.
Ningún fichero de datos publicados cambió por estas fusiones, así que no hubo que restaurar
nada.

## 8. Límites

- Hoy solo 18 impactos son evaluables. Los partes de la Fuerza Aérea dan las regiones, no las
  localidades; los ataques en Rusia no están en la base como impactos.
- El radio de una ciudad (10 km) puede contener fuegos ajenos al impacto (quemas agrícolas,
  otro ataque cercano, como en Galați). La marca es un indicio físico, no una confirmación.
- Nubes, humo y la hora de paso explican que 13 de 18 ataques documentados no tengan foco.
- La base de 30 días no ve un sitio con calor que no estuvo activo ese mes (Kirishi, julio de
  2025).
- El procesado estándar (SP) sustituye al NRT meses después; una evaluación solo se rehace la
  primera semana tras su ventana.
- NOAA-21 solo tiene NRT, que FIRMS podría reprocesar.
