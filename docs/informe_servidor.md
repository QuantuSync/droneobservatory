# Migración de la recogida a un servidor propio

30 de septiembre de 2026. Las horas son UTC.

## 1. Por qué

GitHub no lanza a su hora las ejecuciones programadas: del 28 al 30 de septiembre lanzó 10
de 62 ([`informe_arreglo_horaria.md`](informe_arreglo_horaria.md)). El reloj que se montó
dentro del propio repositorio ([`informe_reloj.md`](informe_reloj.md)) lo resolvía con un
trabajo de GitHub Actions siempre en marcha. Un servidor pequeño con un temporizador de
systemd hace lo mismo sin depender de GitHub para la hora, y la recogida pasa a él.

## 2. Qué había del reloj y cómo queda

El reloj no estaba a medias: estaba fusionado en `main` (PR 9, commit `b8e303f`) y en marcha.

- Sin cambios sin commit en el clon. La rama `reloj-recogida` no existía ni en local ni en
  el remoto, y su pull request (el 9) estaba fusionado, no abierto.
- `reloj.yml` estaba en `main`, activo, con una ejecución en marcha desde las 15:00
  (la 36733434517, lanzada a mano). Se desactivó el workflow (`gh workflow disable`) y se
  canceló la ejecución a las 15:23. Había lanzado una recogida, la de las 15:17.
- Esta migración elimina `reloj.yml`, `recogida/reloj.py` y `tests/test_reloj.py`.
- En la lista de workflows de GitHub sigue apareciendo `prueba-reloj`, de una prueba
  anterior cuyo fichero ya no existe. No lanza nada; desaparece si se borran sus
  ejecuciones. No se ha tocado.

## 3. El servidor

| | |
| --- | --- |
| Nombre | `eodi-recogida`, proyecto EODI de Hetzner Cloud |
| Tipo y lugar | CX23 (2 núcleos, 4 GB, 40 GB), Núremberg (`nbg1`) |
| Sistema | Ubuntu 26.04 LTS |
| Dirección | 2.28.197.102 (IPv4), 2a01:4f8:1c1e:bafa::/64 (IPv6) |
| Creado | 30 de septiembre de 2026, 15:27 |
| Precio que da Hetzner | servidor 5,49 €/mes y dirección IPv4 0,50 €/mes, sin IVA: 5,99 €/mes (7,25 € con el 21 %) |

Cómo está montado, dónde están los secretos y cómo se reconstruye:
[`servidor.md`](servidor.md). En resumen:

- **Cortafuegos de Hetzner** con una sola regla: SSH entrante. Lo demás, cerrado.
- **Usuarios.** `eodi` ejecuta el observatorio, sin privilegios ni entrada por SSH.
  `operador` administra: entra con la clave SSH del servidor y usa `sudo`. Root no entra
  por SSH ni tiene clave autorizada, y ninguna cuenta tiene contraseña.
- **Endurecimiento.** SSH solo con clave; fail2ban (5 intentos en 10 minutos, veto de una
  hora); actualizaciones de seguridad automáticas con reinicio a las 04:45 si hace falta;
  zona horaria UTC; hora sincronizada; diario de systemd con tope de 200 MB y 90 días.
- **Observatorio.** Python 3.13, clon en `/home/eodi/droneobservatory` con su entorno
  virtual, y los secretos en `/home/eodi/.eodi/` con permisos 600: la clave age, las
  variables del extractor y dos claves de despliegue nuevas, cada una con escritura en un
  solo repositorio (`droneobservatory-datos` y `droneobservatory`).
- **Temporizador** en el minuto 17 de cada hora, con cerrojo, tope de 45 minutos y
  ejecución pendiente al arrancar. El script hace lo mismo que `recogida.yml`.

Todo sale de `servidor/reconstruir.sh`. Se ha ejecutado varias veces sobre el mismo
servidor: la primera lo creó y la última, ya con todo montado, terminó sin errores y lo
dejó igual.

## 4. GitHub

- **`recogida.yml`** pierde la programación y queda solo con lanzamiento a mano, para una
  emergencia. Conserva sus secretos y su clave de despliegue.
- **`reloj.yml`** se elimina.
- **Salud.** El trabajo `salud-recogida` del workflow de tests mira la fecha del último
  commit de la rama `estado` del repositorio de datos y señala en su resumen si tiene más
  de 2 horas. Como ese repositorio es privado, lo lee con una clave de despliegue nueva de
  solo lectura (secreto `EODI_DATOS_CLAVE_LECTURA`) y pide solo el commit: la base no se
  descarga.

## 5. Lo que se encontró por el camino

1. **IPv6 con Telegram.** En la primera recogida de prueba la Fuerza Aérea no se leyó:
   agotó su tope de 300 s. Desde el servidor la conexión por IPv6 con `t.me` falla casi
   siempre (12 de 14 intentos; por IPv4, 0 de 14) y Python esperaba los 30 s del tiempo
   límite en cada página antes de pasar a IPv4. Con IPv4 por delante (`/etc/gai.conf`) las
   43 páginas se leen en 126 s, igual que en GitHub. Está en `instalar.sh`.
2. **Python 3.13.** Ubuntu 26.04 trae Python 3.14 y no tiene paquete del 3.13: se instala
   de `ppa:deadsnakes/ppa`, que se ha añadido a las actualizaciones automáticas.
3. **Un usuario más de los pedidos.** Sin root por SSH y con `eodi` sin privilegios hacía
   falta alguien que administre: `operador`.
4. **Núremberg.** La lista de tipos de servidor daba el CX23 como no disponible en `nbg1`,
   pero Hetzner lo creó allí sin objeciones.
5. **Una fuente oficial bloqueada.** En las dos recogidas de prueba, una de las páginas
   oficiales no se pudo descargar desde el servidor (`bloqueadas=1`, motivo `descarga`);
   desde GitHub se leían todas. No deja la recogida con avisos. Falta ver cuál es y si es
   un veto a la dirección del servidor.

## 6. Comprobaciones

Antes de fusionar, con el script del servidor lanzado a mano como `eodi`:

| Hora | Resultado |
| --- | --- |
| 15:34 | Código 2 en 8 min 43 s: la Fuerza Aérea agotó su tope (punto 1 de la sección 5). El resto se leyó y la base se subió a la rama `estado` |
| 15:53 | Código 0 en 4 min 12 s, ya con IPv4 por delante: las dos fuentes de partes, GDELT, las fuentes oficiales y el extractor, y la base subida a la rama `estado`. Ficheros publicados sin cambios |

Los tests del script (`tests/test_servidor.py`) usan un repositorio local y un doble de
Python: publica con código 0 y con código 2, no publica con otro código, no hace commit
sin cambios, descarta lo que no llegó a enviarse y no se lanza con el cerrojo tomado. Solo
corren en Linux (en Windows se saltan): pasan en el servidor y en el workflow de tests.

Tras la fusión se comprueban dos recogidas seguidas lanzadas por el temporizador y un
reinicio del servidor, y el resultado se añade a este informe.

## 7. Lo que queda sin decidir

1. **Aviso cuando la recogida se para.** La comprobación de salud solo corre cuando hay
   un push o un pull request. Si el servidor se cae en una semana sin cambios, nadie lo
   ve. Opciones: un aviso por correo desde el propio servidor cuando la unidad falla, o
   una comprobación programada en GitHub (que llegaría tarde, pero llegaría).
2. **La rama `estado` como señal.** La base solo se sube si ha cambiado. Hasta ahora
   cambia en todas las ejecuciones; si alguna vez no lo hiciera, la comprobación daría un
   aviso falso.
3. **Recogida con avisos.** Cuando la recogida sale con código 2, la unidad queda como
   fallida en systemd, igual que el workflow quedaba en rojo. Es la única señal: no hay
   quien la mire salvo entrando en el servidor.
4. **Emergencia y servidor a la vez.** Nada impide lanzar `recogida.yml` a mano mientras
   el servidor recoge: el cerrojo es local. Hay que parar antes el temporizador.
5. **Fusiones a `main` durante una recogida.** Si `main` cambia entre que el script
   actualiza el clon y publica, el envío se rechaza y la unidad falla; los ficheros se
   publican en la recogida siguiente. Conviene no fusionar entre el minuto 17 y el 25.
6. **Secretos antiguos en GitHub.** Siguen en el repositorio para el workflow de
   emergencia: la clave age, las variables del extractor y la clave de despliegue
   «droneobservatory: rama estado». Si se prescinde de la emergencia, sobran.
7. **Copias de seguridad del servidor.** No se han contratado: nada de lo que hay en él
   es irrecuperable y se reconstruye con una orden.
8. **Clave de host del servidor.** Se anota en la primera conexión, sin comprobarla por
   otro canal.
9. **Tests del script en local.** La puerta local en Windows no los ejecuta.
