# Informe de cimientos

Lo que el diseño no decide y queda pendiente, y las interpretaciones tomadas
para poder implementar. Todo lo aquí anotado es revisable.

## Sin decidir

- **Licencia.** El repositorio público no tiene licencia. Sin ella, por
  defecto nadie puede reutilizar el código ni los datos publicados.
- **Formato del identificador de episodio.** El esquema acepta cualquier texto
  no vacío. Los ejemplos de test usan `EP-AAAA-MM-DD`, que no es una decisión.
- **Si un desmentido puede revertirse.** Hoy desmentido es final: no hay
  transición de salida.
- **Vocabulario de AEGIS.** `control.vocabulario_aegis` es un objeto libre de
  texto a texto hasta que se defina el vocabulario.
- **Exportación de la capa de Ucrania.** Solo se genera `incidentes.geojson`.
  La capa de Ucrania no tiene geometría puntual (se agrega por región) y su
  formato público está por definir.
- **Flujo hacia `droneobservatory-datos`.** El repositorio privado existe con un README
  mínimo; qué se guarda allí y cómo (por ejemplo, la base cifrada) está por
  decidir.
- **Versiones de las acciones de GitHub.** El workflow usa `actions/checkout@v4`
  y `actions/setup-python@v5` por etiqueta; falta decidir si se fijan por hash.
- **Límite de la frase de daños.** `consecuencias.danos.frase` es una frase
  breve propia, no de origen; no tiene límite de palabras.

## Interpretaciones tomadas

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
  `restos`). La ficha no tiene dónde guardar la prueba de origen y sin ella no
  se puede aplicar «un avistamiento sin origen demostrado nunca es incursión».
- **Dirección de la trayectoria** en grados de 0 a 360 (entrada y salida).
- **Coordenadas.** Máximo 5 decimales, comprobado por código (el
  `multipleOf` de JSON Schema falla con decimales binarios).
- **Frase de origen.** El límite de 25 palabras se impone en el esquema (patrón)
  y por código; las palabras se cuentan separando por espacios.
- **Tipo `ataque_guerra`.** No es un tipo válido de incidente: existe solo como
  tipo fijo del ataque en la capa de Ucrania.
- **Regiones de la capa de Ucrania.** El patrón acepta cualquier código ISO
  3166-2, porque en el sentido UA_RU las regiones afectadas son rusas.
- **Categorías de objetivo en la capa de Ucrania.** El diseño deja la lista
  abierta; se cierra con energia, residencial, ferrocarril, puerto, industrial y
  otra.
- **Fuentes del Ministerio de Defensa ruso.** Se identifican con el indicador
  `interna_fuera_de_ucrania` en la configuración y en la fuente; dentro de la
  capa de Ucrania pueden ser públicas.
- **Campos de la fuente que dependen del incidente.** `credibilidad` y
  `campos_respaldados` se guardan en el documento del incidente; la tabla común
  de fuentes no los incluye.

### Validaciones

- **Precedencia de la interrupción aeroportuaria.** Se exige ese tipo cuando hay
  cierre con objetivo aeropuerto o cuando algún número de vuelos desviados,
  cancelados o retrasados tiene mínimo mayor que cero.
- **Estado inicial.** Todo historial empieza en notificado; si la primera fuente
  es una autoridad se registran notificado y confirmado con la misma fuente.
- **Motivo de desmentido.** Obligatorio con estado desmentido y prohibido en
  cualquier otro.
- **Proporción de señuelos.** Solo se deriva y se comprueba cuando los tres
  números de lanzados son exactos (mínimo igual a máximo).
- **Fechas futuras.** La hora actual se pasa como argumento a las validaciones
  para que los tests sean deterministas.

### Credibilidad

La regla se evalúa en este orden: 5, 4, 1, 2, 3, 6. Casos que la redacción no
cubre de forma literal:

- **Autoridad que contradice frente a autoridad que confirma:** 5.
- **«Contradice una fuente de igual o mayor fiabilidad»** se compara con la
  mejor fiabilidad entre las fuentes que respaldan el dato.
- **Dos fuentes C independientes:** 3, igual que una sola.
- **Una A o B contradicha por una fuente de menor fiabilidad:** 3 (deja de ser
  «coherente con el resto», pero la contradicción no alcanza el 4).
- **Solo fuentes D, E o F:** 6.
- **Independencia.** Cada declaración lleva el identificador de su nota
  original; las réplicas comparten nota y cuentan una sola vez.

### Almacén y cifrado

- **Nada se borra en ninguna tabla**, no solo en incidentes: DELETE está
  bloqueado por trigger en todas. Afirmaciones e historial tampoco admiten
  UPDATE.
- **Límite de los triggers.** SQLite no puede impedir `DROP TABLE` ni `DROP
  TRIGGER` a quien tenga acceso de escritura al fichero. La protección de fondo
  es el cifrado y el control de acceso a la base.
- **Fecha del historial.** Es la hora del sistema en el momento de escribir.
- **Regiones de un ataque.** Si una versión posterior del ataque deja de incluir
  una región, su fila no se borra; el documento del ataque es el que manda.
- **Una sola variable de clave.** `EODI_CLAVE_AGE` contiene la identidad y el
  destinatario se deriva de ella. Si la recogida se ejecuta en otra máquina
  convendría una segunda variable solo con el destinatario, para que esa
  máquina pueda cifrar sin poder descifrar.

### Exportación

- **Incidentes sin fuentes públicas** no se publican.
- **Historial de estados.** Si un cambio lo provocó una fuente interna, el
  historial publicado conserva el cambio y la fecha pero omite el identificador
  de la fuente.
- **Desmentidos.** Se publican con su estado y su motivo.

### Workflow

- La indicación de usar un minuto distinto de 0 solo aplica a programaciones
  horarias; como el workflow no tiene ninguna, no hay minuto que fijar.

## Atascos

Ninguno.
