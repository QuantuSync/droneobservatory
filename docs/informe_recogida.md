# Informe de recogida

Segundo PR del Observatorio Europeo de Incidentes con Drones (EODI):
recogida automática y primera fuente, el canal oficial de la Fuerza Aérea
de Ucrania (`t.me/kpszsu`), con su histórico desde octubre de 2022.

## Pendientes del PR anterior

- **Credibilidad.** Una fuente D contradicha por otra de menor fiabilidad da
  3, igual que una A o B contradicha por una menos fiable. Si la
  contradicción viene de una fuente igual o más fiable sigue dando 4.
- **Dependabot** mensual para las acciones de GitHub y las dependencias de pip.
- **Carpeta local** del repositorio de datos renombrada de
  `C:\dev\atalaya-datos` a `C:\dev\droneobservatory-datos` sin bloqueos.
- `docs/informe_cimientos.md` actualizado con lo cerrado.

## Estado en el repositorio de datos

- `db.age` vive en la rama `estado` de `QuantuSync/droneobservatory-datos`
  como un único commit que se sustituye con un push forzado solo a esa rama
  (`almacen/remoto.py`). El historial de git no crece; el de cada ataque
  vive en la tabla `historial` de la base.
- **Identidad age** nueva. La clave privada está fuera de cualquier
  repositorio, en `%USERPROFILE%\.eodi\clave_age.txt`, con permisos solo
  para el usuario, y subida como secreto `EODI_CLAVE_AGE` del repositorio
  público. La variable admite el fichero completo con su línea de
  comentario; en local se carga del fichero si la variable no está.
- **Clave de despliegue** SSH ed25519 con escritura en
  `droneobservatory-datos`, subida como secreto
  `EODI_DATOS_CLAVE_DESPLIEGUE` del repositorio público. Las copias
  temporales se borraron tras subirla. Las operaciones locales usan las
  credenciales de gh por HTTPS.
- Los errores de git solo nombran el subcomando, para que una URL con
  credenciales no llegue al registro.

## Recogida base

- **Descarga educada** (`recogida/descarga.py`): pausa mínima entre
  peticiones al mismo sitio, identificación de navegador real, reintentos
  con espera doble cada vez y respeto de `Retry-After` con tope. Cada
  descarga lleva una comprobación de contenido: la página del canal debe
  traer su cabecera y la web oficial debe ser HTML. Si no, cuenta como
  bloqueo con código 200 y se reintenta.
- **Cursor por fuente** en la propia base (tabla `cursores`): la ejecución
  baja desde la portada hasta el último identificador leído. Si el cursor
  queda a más de 500 páginas la fuente no lee nada, para no dejar un hueco
  silencioso.
- **Caché** de páginas en bruto comprimidas en `data/cache/` (fuera de git).
  En la base solo se guarda el hecho, la frase de origen (25 palabras como
  máximo) y el enlace.
- **Registro de ejecución** solo con recuentos: páginas, publicaciones,
  partes, leídos, fallidos, nuevos y actualizados, y motivos de fallo
  agrupados.

## Fuente: Fuerza Aérea de Ucrania

- Configurada en `configuracion/fuentes.json` con fiabilidad B, sin marca de
  autoridad y pública. Una sola fuente B sin contradicción da credibilidad 2
  por la regla: B2.
- **Verificación en cada ejecución** antes de leer: insignia de verificado,
  título con «Повітряні Сили», y que la web oficial enlazada en la
  descripción (`sites.google.com/view/uaairforce`) sigue enlazando a
  `t.me/kpszsu`, también codificado en una redirección (`t.me%2Fkpszsu`).
  Si algo falla, la fuente no lee nada, el motivo va al registro y la
  ejecución horaria termina con código 2 para quedar en rojo.
- **Estado**: el ataque nace notificado y confirmado por la misma fuente,
  porque el parte oficial cuenta como confirmación. Sentido `RU_UA`.
- **Un parte por ataque.** Un segundo parte con el mismo inicio de periodo
  declarado actualiza el ataque y añade su fuente. Las cifras del parte más
  reciente sustituyen a las anteriores y el cambio queda en el historial.
  Reprocesar el mismo parte no toca la base.
- **Partes que el parser no entiende**: no se publican. Quedan en la tabla
  interna `partes_fallidos` con su enlace, su motivo y su fecha, y se cuentan.
  Si un parser posterior los lee, se marcan como resueltos sin borrarlos.

### Parser (`recogida/parte.py`)

Por código, sin extractor. Solo drones: las cifras de misiles del mismo parte
se ignoran.

- **Periodo** tal como lo declara el parte, en hora de Kyiv convertida a UTC
  con `Europe/Kyiv` (`tzdata` fijado para que funcione también en Windows).
  Cubre las variantes siguientes:
  - «У ніч на 26 вересня (з 18:00 25 вересня)», con día de la semana, coma o
    «9-го»;
  - «Протягом дня 25 вересня (із 7.00 до 18.30)»;
  - «(із 20.00 23.09 по 07.00 24.09)», con fechas numéricas;
  - «У період із 14.30 по 20.30 7 травня»;
  - «Із 18.30 25 грудня по 03.00 26 грудня»;
  - «2 жовтня уночі», «Уночі, з 5 на 6 жовтня», «6 жовтня з 15:00 по 20:00»,
    con «24.00» como medianoche;
  - «Увечері».

  El fin es «станом на» cuando aparece; si no, la hora de publicación con
  precisión aproximada. Una noche sin hora de inicio empieza a las 18:00 del
  día anterior con precisión aproximada (es la hora que declaran los partes
  que sí la dan). Una fecha de inicio con el mes o el día equivocado se
  corrige si el día es la víspera; si no, el periodo se da por incoherente y
  el parte no se publica.
- **Lanzados por modelo.** Desde 2025 los partes dan una sola cifra para
  Shahed, Gerbera y señuelos juntos. Por eso cada modelo nombrado recibe un
  rango de 0 a esa cifra, y el total va en el campo nuevo `lanzados.total`.
  Una subcuenta («понад 50 із них – реактивні») fija el mínimo de su modelo.
  Asignación de modelos:
  - Shahed, Geran y reactivos van a `shahed_geran`.
  - Gerbera, imitadores y «Пародія» van a `gerbera_senuelos`.
  - Italmas, Bandérol/Dan-T, Lancet y «інших типів» van a `otros`.

  Los drones de reconocimiento (Orlan, Zala, Supercam) no cuentan. «До 17»
  da un rango de 0 a 17. Una cifra sin máximo («понад 200») deja el parte
  como ilegible.
- **Derribados**: la cifra de drones de la frase de derribos. Se suman las
  viñetas sin la cabecera, que repite el total de todas las armas. «58 з
  59» son 58. «Усі цілі» y «100% дронів» son todos los lanzados. El titular
  solo cuenta si el cuerpo no da la cifra, porque a veces suma drones de
  reconocimiento. Desde 2025 los partes dan «збито/подавлено» en una sola
  cifra, así que `derribados` incluye lo neutralizado por guerra electrónica
  cuando el parte no lo separa.
- **Perdidos por guerra electrónica**: la cláusula «локаційно втрачені».
  Vale la primera frase que la da, porque titular y cuerpo la repiten. Se
  saltan las viñetas de misiles y los «понад N».
- **Zonas de lanzamiento**: la lista tras «з напрямків» o «з району», antes
  de la cifra o entre paréntesis, sin «ТОТ», «АР» ni «рф». Acaba en la
  siguiente arma o subcuenta.
- **Lugares con impacto y con restos, regiones.** Se cuentan las
  localizaciones que declara el parte («на 19 локаціях») en los campos nuevos
  `localizaciones_impacto` y `localizaciones_restos`. Las regiones sin nombre
  de lugar no dan lugares. Las regiones se reconocen con el vocabulario
  `configuracion/regiones_ucrania.json`, que tiene raíces de oblast, nombre
  corto y capital por código ISO 3166-2; si casan varias raíces, manda la
  más larga. Las frases de puntos de lanzamiento no dan regiones.
- **Cruces a otros países**: una cláusula con «перетнули», «у бік» o «в
  повітряний простір» y un país del vocabulario. La cifra sale de esa misma
  cláusula. Los cruces se guardan en el ataque; abrir incidentes de
  incursión queda para el PR de fusión.
- **No son partes**:
  - las alertas en tiempo real («БпЛА курсом на ...»);
  - los pies de vídeo, que no ligan el periodo con cifras de drones;
  - los balances firmados por un mando aéreo regional («Повітряне
    командування "Захід"»), que son parciales y pisarían las cifras del
    parte nacional de esa noche.

### Esquema

Tres campos públicos nuevos en el ataque: `lanzados.total`,
`localizaciones_impacto` y `localizaciones_restos`. El total se valida contra
la suma de mínimos y máximos por modelo. El esquema sigue en 1.0.0 porque
`ucrania.json` no se había publicado nunca.

### Ficheros publicados

`publicacion/ucrania.json` y `publicacion/incidentes.geojson`, generados desde
la base con sus listas cerradas de campos y con saltos de línea LF.

## Workflow horario (`.github/workflows/recogida.yml`)

- Cada hora en el minuto 17 y a mano. Solo corre si el repositorio es
  `QuantuSync/droneobservatory` y la rama es `main`. Nunca usa
  `pull_request_target` ni se dispara desde contribuciones externas.
- Permisos por defecto de solo lectura. El trabajo tiene `contents: write`,
  necesario para el commit de los ficheros publicados.
- Acciones fijadas por hash. La clave de host de GitHub va fijada en vez de
  confiar en la primera conexión. La clave de despliegue se escribe en el
  directorio temporal del runner y se borra al final pase lo que pase.
- Pasos:
  1. descargar `db.age` con la clave de despliegue;
  2. descifrar con `EODI_CLAVE_AGE`;
  3. verificar y recoger lo nuevo desde el cursor;
  4. regenerar los ficheros;
  5. cifrar y subir `db.age` a `estado`, solo si la base ha cambiado;
  6. si `ucrania.json` o `incidentes.geojson` han cambiado, hacer commit en
     `main` solo con esos ficheros, con autor QuantuSync y el correo de la
     cuenta, sin trailers.
- Sin artefactos descargables. El registro solo lleva recuentos.
- Una sola ejecución a la vez (`concurrency`), para que dos no se pisen la
  rama `estado`.

## Valores justificados

| Valor | Dónde | Por qué |
| --- | --- | --- |
| 3 s entre peticiones al mismo sitio | `descarga.py` | Unas 20 por minuto, el ritmo de una persona que pasa páginas deprisa. El histórico (3916 páginas) cupo en unas 3,3 horas y una ejecución horaria pide dos o tres páginas |
| 4 reintentos, espera de 5 s doblada | `descarga.py` | 75 s en total: supera un corte breve sin alargar una ejecución fallida |
| `Retry-After` con tope de 300 s | `descarga.py` | Obedece al servidor sin quedar colgado |
| 30 s de límite por petición | `descarga.py` | Una página del canal pesa unos 110 kB |
| 500 páginas como máximo por ejecución | `fuerza_aerea.py` | Unas 10 000 publicaciones, más de medio año al ritmo del canal (unas 50 al día). Si no basta, es mejor no leer que dejar un hueco |
| 18:00 como inicio aproximado de la noche | `parte.py` | Es la hora que declaran los partes que sí dan el inicio |
| 1 día de margen para inferir el año | `parte.py` | Un parte habla de la noche que acaba de pasar |
| 80 % de mayúsculas para reconocer el titular | `parte.py` | El cuerpo, con nombres propios y siglas, no pasa de un 20 % |
| 30 letras previas para detectar reconocimiento | `parte.py` | Basta para «проводив повітряну розвідку трьома ...» |
| Avance cada 100 páginas | `recorrido.py` | Unas 40 líneas en todo el histórico |
| 10 reintentos de 0,5 s al guardar el avance | `recorrido.py` | En Windows un lector ajeno bloquea el reemplazo un instante; esto cortó el recorrido una vez |
| Semilla 1 para la muestra | `historico.py` | Solo hace la muestra reproducible; su valor no importa |
| Minuto 17 | `recogida.yml` | Evita el pico de las horas en punto |
| 30 min de límite del trabajo | `recogida.yml` | Una ejecución normal tarda menos de dos minutos |
| Dependabot mensual | `dependabot.yml` | Pocas dependencias: basta una revisión al mes |

## Histórico

Descargado en local con `recogida.historico` (reanudable: el avance se guarda
tras cada página y las páginas ya descargadas salen de la caché). Recorrió
3916 páginas, desde la publicación 80601 (27 de septiembre de 2026) hasta el
29 de septiembre de 2022, sin ninguna página de bloqueo. Se cortó una vez por
el bloqueo de Windows descrito arriba y se reanudó sin repetir descargas. La
base construida desde cero se subió a `estado`. Tiene 1025 ataques, porque 4
partes actualizaron un ataque del mismo periodo, 11 partes fallidos
registrados y el cursor en la publicación 80601.

### Cobertura por año

| Año | Publicaciones leídas | Partes detectados | Leídos bien | Fallidos | Motivo más frecuente |
| --- | ---: | ---: | ---: | ---: | --- |
| 2022 | 232 | 12 | 11 | 1 | cifra de lanzados sin máximo |
| 2023 | 6851 | 139 | 135 | 4 | sin cifras de drones |
| 2024 | 16463 | 258 | 255 | 3 | sin cifras de drones |
| 2025 | 25270 | 355 | 354 | 1 | sin cifras de drones |
| 2026 | 29290 | 276 | 274 | 2 | cifra de lanzados sin máximo |
| Total | 78106 | 1040 | 1029 | 11 | sin cifras de drones |

«Publicaciones leídas» son todas las del canal en ese año desde el 1 de
octubre de 2022 (hora de Kyiv). «Partes detectados» son los resúmenes de
ataque con drones; el resto son alertas, vídeos y avisos.

**2022 está incompleto por diseño.** Entre octubre y diciembre de 2022 el
canal no publicaba un parte nacional por noche, sino notas de derribos de
cada mando regional, varias por noche y parciales. El parser no las agrega:
fundirlas por periodo haría que una nota pisara a otra. Solo entran los 11
partes con estructura de parte nacional.

Motivos de fallo, 11 en total:

- **Sin cifras de drones (8):** el parte habla de drones pero no da ninguna
  cifra propia de drones. Por ejemplo, solo da el total de «повітряних цілей»,
  o la única cifra es de drones de reconocimiento.
- **Cifra de lanzados sin máximo (3):** «понад 200 ударних безпілотників».

### Muestra de comprobación

Cinco partes elegidos al azar entre los leídos bien, con semilla 1, y lo
extraído de cada uno. Los cinco se han comparado con su texto: lanzados,
derribados, perdidos, periodo y zonas coinciden. Diferencias vistas:

- en 8483 faltan las zonas, que van en una frase distinta de la cifra;
- en 15429 falta Єйськ, escrito «район пусків – Єйськ»;
- las regiones de 8483 incluyen las de los objetivos de los misiles del
  mismo parte.

En la primera pasada, la muestra sacó además a la luz que las frases de
puntos de lanzamiento añadían Crimea como región afectada; se corrigió antes
de subir la base.

#### https://t.me/kpszsu/8483

- Periodo: 2023-12-13T16:00Z (aproximada) → 2023-12-14T05:19Z (aproximada)
- Lanzados: total 42; shahed_geran 0–42, gerbera_senuelos 0–42, otros 0–42
- Derribados 41; perdidos por guerra electrónica desconocido
- Localizaciones con impacto desconocido; con restos desconocido
- Zonas de lanzamiento: —
- Regiones: UA-65, UA-48, UA-51; cruces: —
- Frase de origen: «У ніч на 14 грудня 2023 року російські окупанти атакували ударними БпЛА та зенітними керованими ракетами С-300.»

#### https://t.me/kpszsu/15429

- Periodo: 2024-06-13T15:00Z (aproximada) → 2024-06-14T04:48Z (aproximada)
- Lanzados: total 17; shahed_geran 17, gerbera_senuelos 0, otros 0
- Derribados 17; perdidos por guerra electrónica desconocido
- Localizaciones con impacto desconocido; con restos desconocido
- Zonas de lanzamiento: —
- Regiones: UA-68, UA-63, UA-48, UA-51, UA-23, UA-12, UA-35; cruces: —
- Frase de origen: «У ніч на 14 червня 2024 року російські окупанти завдали ракетно-авіаційного удару по Україні, застосувавши ракети різних типів та ударні БпЛА типу «Shahed».»

#### https://t.me/kpszsu/17641

- Periodo: 2024-08-10T15:00Z (aproximada) → 2024-08-11T09:12Z (aproximada)
- Lanzados: total 57; shahed_geran 57, gerbera_senuelos 0, otros 0
- Derribados 53; perdidos por guerra electrónica desconocido
- Localizaciones con impacto desconocido; con restos desconocido
- Zonas de lanzamiento: Приморсько-Ахтарськ, Єйськ, Курськ
- Regiones: UA-14, UA-48, UA-51, UA-71, UA-05, UA-35, UA-65, UA-32, UA-23, UA-59, UA-56; cruces: —
- Frase de origen: «У ніч на 11 серпня 2024 року ворог атакував 4-ма балістичними ракетами KN-23 із Воронезької області та 57-ма ударними БпЛА типу «Shahed» із районів Приморсько-Ахтарськ,»

#### https://t.me/kpszsu/34249

- Periodo: 2025-05-11T20:00Z (minuto) → 2025-05-12T05:30Z (minuto)
- Lanzados: total 108; shahed_geran 0–108, gerbera_senuelos 0–108, otros 0
- Derribados 55; perdidos por guerra electrónica 30
- Localizaciones con impacto desconocido; con restos desconocido
- Zonas de lanzamiento: Брянськ, Орел, Шаталово, Міллерово, Приморсько-Ахтарськ, Чауда
- Regiones: UA-51, UA-48, UA-14, UA-18; cruces: —
- Frase de origen: «У ніч на 12 травня (із 23.00 11 травня) противник атакував 108-ма ударними БпЛА типу Shahed і безпілотниками-імітаторами різних типів із напрямків: Брянськ, Орел, Шаталово,»

#### https://t.me/kpszsu/78165

- Periodo: 2026-09-13T15:00Z (minuto) → 2026-09-14T05:00Z (minuto)
- Lanzados: total 108; shahed_geran 0–108, gerbera_senuelos 0–108, otros 0
- Derribados 85; perdidos por guerra electrónica desconocido
- Localizaciones con impacto 7; con restos desconocido
- Zonas de lanzamiento: Орел, Курськ, Донецьк, Гвардійське
- Regiones: —; cruces: —
- Frase de origen: «У ніч на 14 вересня (з 18:00 13 вересня) противник атакував 108 ударними БпЛА типу Shahed (в т.ч. реактивними), Гербера, дронами-імітаторами типу “Пародія” із напрямків:»

## Sigue abierto

- **Notas de mandos regionales de 2022.** Para cubrir octubre a diciembre de
  2022 habría que agregar las notas de cada mando por noche sin contar dos
  veces. Encaja en el PR de fusión.
- **Regiones de los misiles.** Las regiones afectadas son las que nombra el
  parte fuera de los puntos de lanzamiento. Cuando el parte mezcla drones y
  misiles pueden incluir objetivos de misiles; separarlas exige analizar la
  frase entera, algo más propio del extractor.
- **Zonas en otra frase** («Пуски здійснювались з трьох напрямків: ...») o
  como «район пусків – X» no se recogen.
- **Derribados desde 2025** incluyen lo «подавлено» por guerra electrónica
  cuando el parte da una sola cifra; `perdidos_guerra_electronica` queda
  entonces «desconocido». Falta decidir si la web debe explicarlo.
- **Ediciones de partes ya leídos.** La ejecución horaria solo lee
  publicaciones posteriores al cursor; si el canal edita un parte antiguo,
  el cambio no se recoge.
- **Clave de despliegue sin límite de rama.** GitHub no permite limitar una
  clave de despliegue a una rama, y en un repositorio privado del plan
  gratuito no hay reglas de rama. La clave podría escribir en `main` del
  repositorio de datos; el código solo empuja a `estado`.
- **Correo en el workflow.** El autor de los commits automáticos lleva el
  correo de la cuenta, visible en el workflow público, igual que en el
  historial de commits.
- **Informe de cobertura** en `data/historico/cobertura.md` (fuera de git);
  lo esencial está copiado aquí.

## Atascos

Ninguno sin resolver. El recorrido del histórico se cortó una vez por un
`PermissionError` de Windows al reemplazar el fichero de avance mientras
otro proceso lo leía; se añadió un reintento y se reanudó.
