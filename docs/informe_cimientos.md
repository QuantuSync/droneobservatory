# Informe de cimientos

Estado de las decisiones del primer PR del Observatorio Europeo de Incidentes
con Drones (EODI): lo decidido, lo que sigue abierto, lo que queda fuera de
este PR y las interpretaciones tomadas para poder implementar.

## Decidido

### Nombre e identificadores

- **Nombre:** Observatorio Europeo de Incidentes con Drones / European
  Observatory of Drone Incidents, siglas EODI, dominio droneobservatory.eu.
  Repositorios `QuantuSync/droneobservatory` (público) y
  `QuantuSync/droneobservatory-datos` (privado).
- **Identificadores:** `EODI-AAAA-NNNNN` (incidente), `EODI-UA-AAAA-NNNN`
  (ataque de Ucrania) y `EODI-EP-AAAA-NNNN` (episodio). El esquema los valida,
  también la referencia al episodio desde el incidente. El esquema sigue en
  1.0.0 porque no se ha publicado ninguna versión.
- **Variable de la clave:** `EODI_CLAVE_AGE`.
- **Carpeta local:** renombrada a `C:\dev\droneobservatory` sin bloqueos.

### Licencias

- Código: Apache-2.0 (`LICENSE`, texto completo).
- Datos publicados (`incidentes.geojson`, `ucrania.json`): CC BY 4.0
  (`LICENSE-DATOS`, con el enlace oficial, y README).

### Desmentido reversible

- Se permite desmentido → confirmado solo si lo provoca una autoridad con
  fiabilidad igual o mayor que la de la fuente que desmintió. Cualquier otra
  fuente se rechaza, tanto al transitar como al validar un historial escrito.
- La reversión es un paso más del historial: el desmentido anterior sigue
  visible. El motivo del desmentido se conserva tras la reversión.

### Capa de Ucrania pública

- `ucrania.json` publica los ataques con sus regiones identificadas por código
  ISO 3166-2 y ordenadas por él, con su propia lista cerrada de campos
  (`CAMPOS_PUBLICOS_ATAQUE`) y los mismos tests que `incidentes.geojson`.

### Otras

- **Acciones de GitHub** fijadas por hash completo del commit, con la versión
  en un comentario (checkout v7.0.1, setup-python v7.0.0).
- **Frase de daños:** máximo 25 palabras, en el esquema y por código.
- **Credibilidad:** una sola fuente C o D sin contradicción da 3; solo fuentes
  E o F da 6. El resto de la regla no cambia.
- **Segunda clave solo para cifrar: descartada.** La recogida necesita leer la
  base para actualizarla, así que necesita la identidad completa; una clave que
  solo cifre no le sirve.

## Sigue abierto

- **Forma de `ucrania.json`.** Las regiones van anidadas dentro de cada ataque.
  No hay un índice por región que agrupe todos los ataques que la afectan; si
  la web lo necesita habría que añadirlo con su propia lista de campos.
- **Frases de origen y CC BY 4.0.** `LICENSE-DATOS` aclara que las frases de
  origen son citas breves de terceros y no quedan cubiertas por CC BY 4.0.
  Conviene que alguien con criterio jurídico confirme esa redacción.
- **Una fuente D contradicha por otra menos fiable** no cumple «sin
  contradicción» y queda en 6. La regla no lo dice de forma explícita.
- **Reversión en la capa de Ucrania.** Se aplica la misma regla que en la capa
  general; el parte oficial cuenta como autoridad si está marcado así.
- **Actualización de las acciones fijadas.** Con hash fijo no se actualizan
  solas; falta decidir cómo y cada cuánto se revisan.

## Fuera de este PR

- **Contenido del repositorio de datos** (`droneobservatory-datos`): qué se
  guarda allí y cómo. Tendrá su propio PR.
- **Vocabulario de AEGIS:** `control.vocabulario_aegis` sigue siendo un objeto
  libre de texto a texto hasta ese PR.

## Interpretaciones vigentes

### Esquema

- **Visibilidad efectiva.** Cada propiedad lleva `x-visibilidad`. Los tipos
  compartidos (instante, rango, punto) marcan sus subcampos como públicos y la
  visibilidad efectiva es la más restrictiva de la cadena: `control.alta.valor`
  es interno porque `control.alta` lo es.
- **Desconocido frente a vacío.** Un campo ausente significa «aún no
  procesado»; el valor literal `"desconocido"` significa «ninguna fuente lo
  dice». Por eso los rangos admiten `"desconocido"` y se añadió
  `"desconocido"` a `consecuencias.cierre.valor` y a `consecuencias.danos.nivel`.
- **Campo añadido `origen_demostrado_por`** (interno, lista de `rastreo` y
  `restos`). Sin él no se puede aplicar «un avistamiento sin origen demostrado
  nunca es incursión».
- **Dirección de la trayectoria** en grados de 0 a 360 (entrada y salida).
- **Coordenadas.** Máximo 5 decimales, comprobado por código (el
  `multipleOf` de JSON Schema falla con decimales binarios).
- **Frases breves.** El límite de 25 palabras cuenta palabras separadas por
  espacios.
- **Tipo `ataque_guerra`.** No es un tipo válido de incidente: existe solo como
  tipo fijo del ataque en la capa de Ucrania.
- **Regiones de la capa de Ucrania.** El patrón acepta cualquier código ISO
  3166-2, porque en el sentido UA_RU las regiones afectadas son rusas.
- **Categorías de objetivo en la capa de Ucrania:** energia, residencial,
  ferrocarril, puerto, industrial y otra.
- **Fuentes del Ministerio de Defensa ruso.** Se identifican con el indicador
  `interna_fuera_de_ucrania`; dentro de la capa de Ucrania pueden ser públicas.
- **Campos de la fuente que dependen del incidente.** `credibilidad` y
  `campos_respaldados` se guardan en el documento del incidente; la tabla común
  de fuentes no los incluye.

### Validaciones

- **Precedencia de la interrupción aeroportuaria.** Se exige ese tipo cuando hay
  cierre con objetivo aeropuerto o cuando algún número de vuelos desviados,
  cancelados o retrasados tiene mínimo mayor que cero.
- **Estado inicial.** Todo historial empieza en notificado; si la primera fuente
  es una autoridad se registran notificado y confirmado con la misma fuente.
- **Motivo de desmentido.** Obligatorio con estado desmentido y prohibido si el
  historial no tiene ningún desmentido.
- **Proporción de señuelos.** Solo se deriva y se comprueba cuando los tres
  números de lanzados son exactos (mínimo igual a máximo).
- **Fechas futuras.** La hora actual se pasa como argumento a las validaciones
  para que los tests sean deterministas.

### Credibilidad

La regla se evalúa en este orden: 5, 4, 1, 2, 3, 6.

- **Autoridad que contradice frente a autoridad que confirma:** 5.
- **«Contradice una fuente de igual o mayor fiabilidad»** se compara con la
  mejor fiabilidad entre las fuentes que respaldan el dato.
- **Dos fuentes C (o D) independientes:** 3, igual que una sola.
- **Una A o B contradicha por una fuente de menor fiabilidad:** 3.
- **Independencia.** Cada declaración lleva el identificador de su nota
  original; las réplicas comparten nota y cuentan una sola vez.

### Almacén y cifrado

- **Nada se borra en ninguna tabla**: DELETE está bloqueado por trigger en
  todas. Afirmaciones e historial tampoco admiten UPDATE.
- **Límite de los triggers.** SQLite no puede impedir `DROP TABLE` ni `DROP
  TRIGGER` a quien tenga acceso de escritura al fichero. La protección de fondo
  es el cifrado y el control de acceso a la base.
- **Fecha del historial.** Es la hora del sistema en el momento de escribir.
- **Regiones de un ataque.** Si una versión posterior del ataque deja de incluir
  una región, su fila no se borra; el documento del ataque es el que manda.
- **Una sola variable de clave.** `EODI_CLAVE_AGE` contiene la identidad y el
  destinatario se deriva de ella.

### Exportación

- **Incidentes y ataques sin fuentes públicas** no se publican.
- **Historial de estados.** Si un cambio lo provocó una fuente no pública, el
  historial publicado conserva el cambio y la fecha pero omite el identificador
  de la fuente.
- **Desmentidos.** Se publican con su estado y su motivo.

### Workflow

- La indicación de usar un minuto distinto de 0 solo aplica a programaciones
  horarias; como el workflow no tiene ninguna, no hay minuto que fijar.

## Atascos

Ninguno.
