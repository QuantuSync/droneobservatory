# Estado del sistema y quién dice qué

30 de septiembre de 2026. Las horas son UTC.

## 1. Estado del sistema (`estado.json`)

Al final de cada recogida horaria, el servidor sube `estado.json` al bucket R2
`eodi-teselas`, que se sirve en <https://tiles.droneobservatory.eu/estado.json>. No hay
commit en git, así que la web no se reconstruye cada hora. El formato está acordado con la
web, que ya lo valida (`web/src/datos/validar.ts`, `estadoSistema`):

```json
{"version": 1, "inicio": "2026-09-30T21:17Z", "fin": "2026-09-30T21:23Z",
 "resultado": "correcta", "ultima_correcta": "2026-09-30T21:23Z",
 "siguiente": "2026-09-30T22:17Z",
 "fuentes": [{"id": "fuerza_aerea_ua", "estado": "leida", "ultimo_dato": "2026-09-30T21:05Z"}, …]}
```

- **Resultado**: `correcta` (código 0), `con_avisos` (código 2: alguna fuente no se leyó,
  pero se publicó) o `fallida` (cualquier otro código). `ultima_correcta` sale del último
  estado publicado, que el servidor guarda en `/home/eodi/.eodi/estado.json`.
- **Siguiente**: la del minuto 17 posterior al fin.
- **Fuentes**, siempre las cinco y en este orden:

  | Id | Leída | Con aviso | No leída | Último dato |
  | --- | --- | --- | --- | --- |
  | `fuerza_aerea_ua`, `mindef_ru` | se leyó | — | canal sin verificar, sin cursor, hueco, descarga fallida o tope de tiempo | fecha del último parte procesado |
  | `gdelt` | se leyó | más de un día pendiente | — | final de la última franja procesada |
  | `oficiales` | todas leídas | alguna sin leer por tiempo o bloqueada | — | la nota más reciente leída |
  | `extractor` | llamó o no tenía nada que llamar | límite de gasto, servicio caído o sin tiempo | error definitivo del servicio | la última llamada |

  Si la recogida falla antes de dejar el estado de sus fuentes, las cinco salen como no
  leídas, con la fecha de su último dato del estado anterior.
- **Sin contenido**: solo horas y estados.
- **Subida**: con `curl --aws-sigv4` al punto S3 de R2, con `Content-Type:
  application/json` y `Cache-Control: public, max-age=60` (la web lo pide cada 5 minutos,
  sin caché). El CORS es el del bucket, que ya admite GET y HEAD desde droneobservatory.eu
  para cualquier objeto.
- **Si falla** (sin credenciales, sin red, R2 caído, error al componerlo), la recogida no
  cambia de resultado: queda un aviso en el diario.

### Credenciales

El token de Cloudflare de `%USERPROFILE%\.eodi\cloudflare_token.txt` no puede crear otros
tokens: la API responde 9109. Las credenciales temporales de R2, por su parte, caducan.
Por eso las credenciales S3 se derivan del propio token, como en la subida de las teselas:
el identificador del token como clave de acceso y el SHA-256 del token como secreto.
Quedan en `%USERPROFILE%\.eodi\r2_estado.env` y en el servidor en
`/home/eodi/.eodi/r2.env`, del usuario `eodi` y con permisos 600. `reconstruir.sh` las
deriva si faltan y las lleva al servidor. curl las recibe por su entrada, no por la línea
de órdenes.

Tienen los permisos de R2 del token, que alcanzan a toda la cuenta y no solo a este
bucket. Para limitarlas hay que crear en el panel de Cloudflare un token de R2 con
escritura solo en `eodi-teselas`, guardar sus credenciales en `r2_estado.env` y volver a
ejecutar `reconstruir.sh`.

## 2. Quién dice qué (`afirmaciones_publicas`)

Cada incidente de `incidentes.geojson` (y de `incidentes_sin_ubicacion.json`) publica el
valor de cada campo público según cada fuente pública:

```json
{"campo": "drones.numero", "fuente_id": "gdelt-510b5643ca99465d", "medio": "news.yam.md",
 "fiabilidad": "C", "credibilidad": 3,
 "fecha": {"valor": "2026-09-30T05:00Z", "precision": "aproximada"},
 "valor": {"min": 1, "max": 1}}
```

- Salen de las afirmaciones que ya se guardaban (el valor que dio el extractor para cada
  campo, con la fuente de la que sale). Cada una se traduce a su campo público: `drones` es
  `drones.numero`, `inicio` es `tiempo.inicio`, `cierre` es `consecuencias.cierre.valor`,
  y así los demás. El valor va con el formato de ese campo: un rango, un instante, un texto
  o una lista.
- Las exclusiones son las de las fuentes (`solo_fuentes_publicas`): nunca fiabilidad E ni
  F, ni fuentes internas fuera de la capa de Ucrania, como el Ministerio de Defensa ruso.
- La lista cerrada de campos (`exportacion/campos.py`) crece solo con
  `afirmaciones_publicas` y sus claves. Los tests comprueban que lo publicado está en ella,
  que no sale ninguna fuente E, F o interna y que cada valor tiene el formato de su campo.
- Con la base del 30 de septiembre, 232 de los 233 incidentes del mapa llevan
  afirmaciones: 1989 en total, todas de fuentes C (noticias). Las declaraciones oficiales y
  las notas de fuentes oficiales no tienen afirmaciones por campo: respaldan el estado, que
  ya se publica con su historial.

## 3. Comprobación

Antes de fusionar, la puerta local (pytest, ruff check, ruff format --check y mypy
--strict) y el workflow de tests estaban en verde. Ese workflow incluye los tests del
script del servidor en Linux (sube el estado con código 0, 2 y 1; sin credenciales avisa;
si la subida falla, la recogida no falla; las credenciales no van en la línea de órdenes)
y el build de la web, que validó `incidentes.geojson` con `afirmaciones_publicas`.

Tras la fusión (commit `0a1c8ed`, 20:26), con recogidas lanzadas a mano:

| Hora | Resultado |
| --- | --- |
| 20:27 a 20:31 | Correcta (código 0), pero sin `estado.json`. El script se lee entero antes de poner el clon al día, así que esta recogida corrió aún el `recogida.sh` anterior, con el código de Python nuevo. Pasará lo mismo cada vez que cambie el script: su efecto llega en la recogida siguiente |
| 20:31 a 20:35 | Correcta (código 0), «estado.json publicado en el bucket» |

<https://tiles.droneobservatory.eu/estado.json> respondió entonces 200 con los datos de
esa recogida: inicio 20:31, fin 20:35, `correcta`, última correcta 20:35, siguiente 21:17.
Las cuatro fuentes de datos salen como leídas; el extractor, con aviso, porque el límite
de gasto diario ya estaba alcanzado. Cabeceras: `Content-Type: application/json`,
`Cache-Control: public, max-age=60` y `Access-Control-Allow-Origin:
https://droneobservatory.eu`. La web en producción sirve `incidentes.geojson` con los 233
incidentes del mapa y 1989 afirmaciones públicas.

## 4. Lo que queda sin decidir

1. **Credenciales de R2 con alcance de cuenta.** Limitarlas al bucket exige crear el token
   en el panel de Cloudflare (sección 1).
2. **Base sin cambios.** Si una recogida no cambia la base, no la sube, y la rama `estado`
   no se actualiza. Con el aviso por incidencia, dos horas así darían un aviso falso.
   Ahora `estado.json` dice cuándo terminó la última recogida y sería una señal mejor para
   ese aviso.
3. **Fuentes oficiales.** Una fuente bloqueada por su servidor deja las oficiales «con
   aviso» aunque las demás se lean.
