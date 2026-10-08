# Cómo se fusiona un pull request

Los pull requests se fusionan con squash desde la línea de órdenes, indicando como autor
la dirección anónima de la cuenta:

```
gh pr merge <número> --squash --delete-branch \
  --author-email 192205734+QuantuSync@users.noreply.github.com \
  --subject "<título en español> (#<número>)" \
  --body-file <fichero con el mensaje>
```

**Condición.** GitHub solo acepta en `--author-email` una dirección que la cuenta pueda
usar en sus commits hechos desde la web: sus correos verificados y, si la cuenta tiene
activada la opción de mantener privado el correo (*Settings → Emails → Keep my email
addresses private*), la dirección anónima. Sin esa opción la orden falla con `Invalid
email address (mergePullRequest)` y no fusiona nada: así falló el 30 de septiembre de
2026 con los PR 9, 10 y 11. Con la opción activada, además, GitHub usa la dirección anónima por
defecto en todo lo que la cuenta hace desde la web.

**Desde el 8 de octubre de 2026 la rama `main` está protegida** con la regla de repositorio
«main protegida» (*Settings* → *Rules*; informe_blindaje.md, fase 4): nada entra sin PR ni sin
las comprobaciones en verde (`tests`, `web`, `datos-publicados` y `ficheros-del-pr`), con la rama
al día con `main`; sin empujes forzados, sin borrarla, con historial lineal. Solo una clave de
despliegue puede saltársela (la del servidor, si se vuelve a publicar en el repositorio); hoy no
hay ninguna con escritura. Ya no se publica con un push a `main`: se fusiona el PR con «rebase», que pone en
`main` el commit único de la rama tal cual, con su autor (la dirección anónima). Mientras la cuenta
no tenga la opción de correo privado, el squash con `--author-email` sigue sin servir y este es el
camino:

```
# a. traer main justo antes de fusionar
git fetch origin
# b. rebase sobre main
git switch <rama> && git rebase origin/main
# c. si el cambio toca la recogida o los datos: ensayo de punta a punta en el servidor, con la
#    exportación semanal (servidor/ensayo.sh, con ENSAYO_EXPORTACION=1; docs/servidor.md, «Ensayos»)
# d. un solo commit con el autor anónimo
git reset --soft origin/main
git commit -F <fichero con el mensaje>            # título «… (#<número>)» y el porqué
# e. comprobación obligatoria antes de publicar
git diff --name-only origin/main HEAD             # solo lo que el PR cambia a propósito
# f. subir la rama y esperar las comprobaciones (obligatorias para fusionar)
git push --force-with-lease origin <rama>
gh pr checks <número> --watch
# g. fusionar con rebase: el commit único entra en main con su autor
gh pr merge <número> --rebase --delete-branch
# h. el número de incidentes publicados no baja
```

Por qué existe cada paso:

- **a y b. Fetch y rebase justo antes.** Hasta el 8 de octubre de 2026 el servidor de recogida
  publicaba cada hora en `main` un commit «Actualiza los datos publicados» (`publicacion/ucrania.json`,
  `publicacion/incidentes.geojson` y `publicacion/incidentes_sin_ubicacion.json`). El commit
  único del paso d lleva el árbol de la rama: si la rama no tiene esos commits, el commit
  único deshace los datos que entraron en `main` mientras la rama vivía. Al fusionar el PR
  #26 se vio que el commit de datos 14e7a02 se habría revertido así; se detectó al comparar
  con `main` antes de publicar. Durante el rebase, un conflicto en `publicacion/` se resuelve
  siempre con la versión de `main` (en un rebase, `main` es «ours»:
  `git checkout --ours publicacion/<fichero>` y `git rebase --continue`), salvo que el PR
  cambie a propósito esos ficheros.
- **f. Tests sobre lo rebasado.** Lo que se fusiona es la rama ya rebasada, no la que pasó
  los tests antes: los datos nuevos de `main` también tienen que validar (la build de la web
  valida `publicacion/` contra el esquema).
- **c. Ensayo de la recogida.** Todo cambio que toque la recogida (`recogida/`, `proceso/`,
  `almacen/`, `exportacion/`, `esquema/`, `configuracion/`) se ensaya antes de fusionar con
  una recogida completa sobre una copia de la base real de la rama `estado`: `--base` la lee
  de un fichero local y `--ensayo` publica en una carpeta aparte y no sube nada. Sin la clave
  del extractor en el entorno no gasta. Tiene que terminar con «ficheros publicados», con
  «ensayo: exportación semanal generada sin subir» y salida 0 o 2 (avisos). Desde el 5 de
  octubre de 2026 el ensayo genera también la exportación semanal para AEGIS sobre la base que
  deja la propia recogida, sin subir nada (`<carpeta>/exportacion/`); si no valida (un valor
  sin regla de origen en `exportacion/procedencia.py`) el ensayo sale con 1 y no se fusiona. La
  exportación del lunes 5 de octubre no se generó por un campo que una regla nueva empezó a
  rellenar sin origen; con este paso se habría visto antes de fusionar. La CI hace lo mismo con
  una base de prueba (`python -m tests.base_prueba`, que tiene un ejemplo de cada campo del
  esquema). El 4 de octubre de 2026 tres recogidas no publicaron (12:17, 15:17 y 16:17)
  por límites y cambios que solo se habían probado por partes: el de 100 MiB de GitHub por
  fichero, el tope de 1 GiB de la base en memoria y una ficha guardada con la hora del reloj,
  que la publicación rechazó como fecha futura.
- **d. Un commit, autor anónimo.** Como hasta ahora (ver más abajo).
- **e. Comprobar la lista de ficheros.** `git diff --name-only origin/main HEAD` tiene que
  listar solo ficheros que el PR modifica de verdad. Las rutas de los datos publicados son las
  que salen en `git log --name-only --grep="Actualiza los datos publicados" origin/main`. Si
  aparece alguna que el PR no toca a propósito, se aborta, no se publica y se vuelve al paso
  a.
- **f y g. Comprobaciones y rebase.** La protección exige que las comprobaciones pasen sobre la
  rama al día con `main`; si `main` avanza, GitHub pide rebasar y se vuelve al paso a. La
  comprobación `ficheros-del-pr` falla si el PR deshace en `main` algo que su rama no cambia (lo
  que pasó con los PR #84 y #87) o si borra ficheros de `docs/`, `esquema/`, `configuracion/` o
  `tests/fixtures/` sin una línea «Borra a propósito: <ruta>» en su descripción. Nunca se fuerza
  un push sobre `main` (la protección tampoco lo deja). No se fusiona entre el minuto 12 y el 40
  de la hora: es cuando corre la recogida, que reinicia la detección en directo y lee el código
  del clon al empezar.
- **h. Comprobar producción.** Después de fusionar, el número de incidentes que sirve
  droneobservatory.eu (la lista `incidentes` de `/datos/resumen.json`) no puede haber bajado
  respecto al de antes; si baja, se revierte el PR con otro PR. Los datos publicados ya no están
  en el repositorio: el almacén guarda una instantánea de cada día (`publicacion/historial/`).

En `main` queda un commit por pull request con autor anónimo, igual que con el squash.
Las diferencias: los commits atómicos de la rama se sustituyen por ese único commit
antes de fusionar (GitHub conserva el enlace a los anteriores en el aviso de push
forzado del pull request) y el commit no lleva la firma de GitHub.

Por qué:

- **`--author-email`.** Sin esta opción, GitHub firma el commit del squash con el correo
  principal de la cuenta, que es el personal, y queda para siempre en el historial de un
  repositorio público. Los commits del workflow de recogida ya usan la dirección anónima;
  los merges tienen que usar la misma. Los anteriores al 30 de septiembre de 2026 (hasta
  el del PR 8) salieron con el correo personal y no se han reescrito.
- **Squash.** Un commit por pull request en `main`, con el porqué en el mensaje. Los
  commits atómicos de la rama se quedan en el pull request.
- **Mensaje en español y sin líneas de atribución** al final.
- **`--delete-branch`.** La rama se borra al fusionar.

Antes de fusionar: la puerta local (`pytest`, `ruff check`, `ruff format --check`,
`mypy --strict` y la exportación de ensayo `python -m tests.base_prueba --salida <carpeta>`,
comando a comando) y el workflow de tests, en verde.

**Ensayos y trabajos en el servidor.** Un ensayo del paso c lanzado en el servidor, o cualquier
otro trabajo de una sesión allí, sigue las normas de [`servidor.md`](servidor.md), apartado
«Trabajos de las sesiones en el servidor»: desde el 5 de octubre de 2026, 3 GB como mucho por
trabajo y 4 GB entre todos los de las sesiones en marcha, a cualquier hora (también durante la
recogida), con prioridad baja de procesador y de disco, `OOMScoreAdjust=1000`, uno por sesión y
sin el cerrojo de la recogida. Las fusiones, en cambio, siguen sin hacerse entre los minutos 12 y
40 (paso f).

Después de fusionar conviene comprobar el autor:

```
git log -1 --format='%an <%ae>' origin/main
```

La configuración global de git de la máquina no se toca. En el clon de trabajo, los
commits de la rama llevan la misma dirección anónima con la configuración local del
repositorio (`git config user.email`, sin `--global`).
