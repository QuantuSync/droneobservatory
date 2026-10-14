# Informe: el servidor se repara solo, reglas de las sesiones y fichas por verificar (14 de octubre de 2026)

Lo que pasó la noche del 13 al 14 de octubre y lo que se hizo para que no vuelva a pasar. El
detalle de cada pieza: `docs/servidor.md` («Guardián del sistema»), `docs/operacion.md` («Cómo se
borra en el servidor», «Si el servidor no da señales», «Si la web no se actualiza») y
`docs/control_fichas.md`.

## Lo que pasó

1. **13 de octubre, 22:35 UTC.** Una sesión que limpiaba sus ficheros de prueba en el servidor
   ejecutó `sudo rm -f /dev/null`. sshd cortaba las conexiones antes del saludo y systemd no podía
   lanzar ningún servicio («Failed to set up standard input»): las recogidas de las 23:17 y las
   00:17 no arrancaron. Lo arregló a las 00:39 un reinicio por la API pedido por otra sesión.
2. **14 de octubre, 05:07 y 05:12 UTC.** Fallaron dos compilaciones de producción en Vercel: los
   datos publicados (generados con una rama sin fusionar) traían un campo, `traduccion`, que el
   código de main no conocía, y el build los validaba cerrados.
3. **Control de fichas.** Unas 600 fichas quedaron sin verificar al acabarse su tope de 4 dólares.
4. **Moldavia, 28 de noviembre de 2025.** La unión conservó EODI-2025-00247 y no la más antigua,
   00243.

## 1. El servidor se repara solo (PR #231)

Tres escalones; solo llega una incidencia por correo si ninguno lo arregla.

- **Guardián** (`eodi-guardian.timer`, cada 5 minutos y al minuto de arrancar, como root, con el
  Python del sistema y la entrada de un dato en vez de `/dev/null`, para que systemd pueda lanzarlo
  aunque falte): recrea `/dev/null`, `/dev/zero`, `/dev/random` y `/dev/urandom` con `mknod`, deja
  `/tmp` en 1777, reinicia sshd si no saluda en el puerto 22 y, por encima del 90 % de disco,
  limpia cachés y temporales propios (nunca datos).
- **Último recurso dentro**: si las dos últimas recogidas de este arranque fallan por el sistema
  (no por una fuente), relanza la recogida si acaba de reparar algo y, si no, reinicia el
  servidor, como mucho una vez cada 6 horas. Tras cualquier arranque lanza la recogida pendiente.
- **Último recurso fuera**: el vigía (`vigia-recogida`, cada 10 minutos, también lanzado por la
  tarea de Vercel) reinicia `eodi-recogida` por la API de Hetzner si `salud.json` lleva más de 30
  minutos sin renovarse, como mucho una vez cada 6 horas (secreto `EODI_HCLOUD_TOKEN`, el token del
  proyecto que ya existía). La incidencia del servidor se aplaza mientras eso está en marcha.

Cada reparación y cada arranque salen en la sección SISTEMA del resumen de las 08:00 de Madrid; lo
que el guardián no consigue arreglar, o si deja de pasar, es un problema de la vigilancia.

**Pruebas, en el servidor:**

| Prueba | Resultado |
|---|---|
| Ensayo completo antes de fusionar (recogida + exportación semanal) | código 0 |
| `/dev/null` borrado a propósito a las 07:57:57 | SSH cortado («Connection reset») a las 07:58:21; el guardián lo recreó a las 08:00:30, **a los 154 s**; ninguna unidad quedó en fallo |
| Clasificación del diario del 13 de octubre | 23:17 y 23:27 salen como fallos del sistema: con el guardián se habría reiniciado a las 23:27 (y antes, a las 22:40, `/dev/null` ya estaría recreado) |
| Simulacro del reinicio de último recurso dentro (`--simulacro-reinicio`) | decide reiniciar, no reinicia ni gasta el cupo de 6 horas |
| Simulacro del reinicio desde fuera (vigía con `simulacro_reinicio` y `forzar_reinicio`) | token válido, servidor 168118181 encontrado, «se reinicia por la API» sin pedirlo, incidencia aplazada |
| Reinicio real desde fuera a las 08:49 (minuto fuera de 10-45, sin recogida en marcha) | servidor arriba a las 08:49:55; el guardián lanzó la recogida pendiente a las 08:50:30 |
| Recogida siguiente | terminó correcta (código 0) y publicó a las 09:07 |

## 2. Ninguna sesión puede romper el sistema

- El fichero de instrucciones que leen todas las sesiones abiertas en `C:\dev\Observatorio AEGIS`
  (fuera de este repositorio) lleva las reglas fijas: no preguntar, fusionar con
  `gh pr merge <n> --rebase` fuera de los minutos 12-40, ensayo completo y recogida real
  siguiente, nunca `rm`, nunca tocar `/dev`, `/etc`, `/usr`, `/bin`, `/boot`, `/proc`, `/sys`,
  nunca publicar datos de una rama sin fusionar, correo de los commits, proveedores, el mapa manda,
  probar como una persona, nada depende del dueño, terminar con TAREA_TERMINADA.
- La configuración de esas sesiones, en la misma carpeta, añade un gancho previo a cada orden de
  Bash y PowerShell (`hooks/bloqueo_sistema.py`) que bloquea, también dentro de una orden por SSH,
  borrar, mover, cambiar permisos o sobrescribir rutas del sistema (`rm`, `mv`, `unlink`, `ln`,
  `chmod`, `find -delete`, `dd of=`, `tee`, `sed -i`, redirecciones a `/dev/*` salvo `/dev/null`
  y compañía, `os.remove`/`shutil.rmtree` con esas rutas), borrar carpetas del sistema de Windows y
  formatear discos, y explica a la sesión por qué. Prueba: `hooks/prueba_bloqueo.py` (31 órdenes
  permitidas y 36 prohibidas, todas bien). Durante el encargo bloqueó de verdad una orden que
  contenía `rm -f /dev/null` y, tras un ajuste, deja pasar los `sed -i` normales.
- `servidor/borrar.py`: el ayudante de borrado del servidor; solo borra dentro de `/home/eodi`
  (salvo base, datos, secretos, clon y navegadores), `/home/operador`, `/tmp` y `/var/tmp`.

## 3. La web nunca deja de compilar por los datos (PR #232)

- Build tolerante (`web/scripts/tolerancia.ts`): un campo desconocido se ignora, un elemento que
  no cumple el esquema se quita y los demás se publican, un fichero ilegible se toma de la web
  anterior y la previsión inválida se omite; todo queda en el registro con líneas `AVISO DE DATOS`.
  Probado con los datos reales manipulados (campo nuevo, ataque roto, fichero ilegible): código 0.
- Vigilancia del despliegue (`recogida/despliegue_web.py`, paso del vigía, secreto
  `EODI_VERCEL_TOKEN`): producción tiene que ser del último commit de main y estar en verde; si
  falla se pide otro una vez y, si vuelve a fallar, se abre «La web no se publica en Vercel».
- Producción en verde con cada commit de main de hoy (9f73d2c a las 07:41, f792ee3 a las 07:57);
  su registro dice «datos: 0 avisos de datos».

## 4. Las fichas que quedaban por verificar (PR #233)

Repaso del control con el código de main (`python -m recogida.control_fichas repaso`, modo
`control_repaso` con 6 dólares más), en tres pasadas por lotes de 09:41 a 10:12 UTC:

| Pasada | Llamadas | Gasto real | Citas traducidas | Fichas verificadas |
|---|---|---|---|---|
| 1 (pares y fichas) | 556 | 4,0176 USD | 7.771 | 1 (y 17 pares revisados: 2 distintos) |
| 2 | 192 | 1,2453 USD | 1.926 | 0 |
| 3 | 80 | 0,4247 USD | 654 | 0 |
| **Total** | **828** | **5,6876 USD** (tope 6) | **10.351** | |

Lo que quedaba sin verificar eran, sobre todo, las citas de las fichas de la capa de Ucrania
(ataques e impactos): las fichas de Europa ya estaban verificadas salvo una. Con lo publicado a las
10:34 UTC, **1.377 ataques y 8.828 impactos** de Ucrania llevan ya todas sus citas traducidas, con
el original desplegable. El control no corrigió ningún dato en estas pasadas (solo tradujo). Quedan
sin traducir **8.561 citas de Ucrania y 439 de Europa**: las hace la madrugada (`eodi-control`,
01:41 UTC, hasta 0,08 dólares por noche).

Uniones: la regla conservaba la ficha de fecha de alta más antigua, que cambia al reconstruir la
base. Ahora conserva la de número de registro menor, y la recogida corrige sola las uniones del
control que conservaron la más nueva: solo había dos, **Moldavia** (00247 → **00243**, con 00328 y
00046 llevando también a ella) y **2026-00084** (en vez de 2026-00114, con 2026-00329). La ficha
publicada sigue igual (el mismo punto en Chisináu, las mismas fuentes y lo verificado) con el
número más antiguo; las demás uniones (111, de la regla general anterior al control, del 4 de
octubre) no son del control y no se tocan. El primer ensayo falló («valor sin origen» en la
exportación) y el segundo dejaba Moldavia sin punto; el tercero, con el método definitivo, terminó
con código 0 y la salida igual a la publicada salvo los números.

## 5. Limpieza menor

- Ramas: no quedaba ninguna rama fusionada en GitHub (las fusiones las borran solas); al terminar
  solo queda `main`.
- Réplica pública de Helsinki, medida en frío a las 07:35 UTC desde Madrid: completa (cada
  fichero con la huella de su manifiesto, el mismo que el de Núremberg) y al día (última pasada
  correcta 07:32, sin pendientes). Ficheros principales: 0,24-0,76 s en Helsinki frente a
  0,19-0,81 s en Núremberg (una lectura de `estado.json` tardó 2,3 s una vez). Mapa de fondo, 40
  trozos de 16 KB al azar: mediana 0,33 s en Helsinki (0,49 s el 9 de octubre) frente a 0,24 s en
  Núremberg; p90 0,54 s y una lenta de 3,7 s.

## 6. Comprobación

- Ensayos completos en el servidor (recogida más exportación semanal) antes de cada fusión que
  toca datos, recogida o servidor: #231 código 0; #233 código 0 al tercer intento (los dos
  primeros se pararon en el ensayo, como debe ser: «valor sin origen» y Moldavia sin punto).
- Recogidas reales siguientes, todas con código 0 y publicadas: 07:17, 08:17, la lanzada por el
  guardián tras el reinicio (08:50, publicó a las 09:07), 09:17 y 10:17 (la que aplicó Moldavia).
- Producción de Vercel en verde con cada commit de main (la última comprobación, fcc962d a las
  10:34) y con «datos: 0 avisos de datos» en su registro.
- Playwright contra producción, Chromium y WebKit, con gestos reales (dedo en Android, iPhone y
  tableta; ratón y rueda en escritorio), en español y en inglés:
  - `control-fichas-recorridos.spec.ts`: 30 de 30 (Bulgaria, Núremberg, **Moldavia en 00243** y
    los enlaces de 00247, 00328 y 00046 que llevan a ella, y fichas corregidas, entre ellas los
    ataques de Ucrania EODI-UA-2026-1044, 1049 y 1051 con sus citas traducidas y el original
    desplegable), sin errores de consola ni enlaces internos rotos;
  - `recorridos.spec.ts`: 31 de 31;
  - `atribuido.spec.ts` y `hoja.spec.ts` con 00243 en 360×800, 390×844, 412×915 y escritorio:
    23 de 23.

La exportación para AEGIS no cambia de formato (ningún PR toca `exportacion/` ni `esquema/`).
