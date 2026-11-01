# Pruebas y ensayos aislados

Una prueba o un ensayo no pueden mandar un aviso ni tocar el estado de verdad, se ejecuten donde se
ejecuten. El 1 de noviembre de 2026 unas pruebas y simulaciones lanzadas como el usuario del
servicio mandaron dos avisos falsos de «saldo agotado»: la carpeta de casa sale de la base de
usuarios del sistema y no de `HOME`, así que un `HOME` temporal no aislaba nada, y leyeron el token
real y el estado real.

## Las dos variables

- `EODI_CASA_AISLADA`: si existe, sustituye a la carpeta de casa (`almacen/casa.casa()`), de la que
  sale todo lo que lee secretos, tokens o estado: `~/.eodi` y `~/datos`. Es la única variable que
  hace falta. No se llama `EODI_CASA` porque ese nombre ya lo usan los scripts del servidor con otro
  sentido.
- `EODI_SIN_AVISOS`: prohíbe el envío de forma explícita. `EODI_CASA_AISLADA` también lo prohíbe.

Con cualquiera de las dos, `recogida/avisos.enviador` no llega a la red (`EnvioDesactivado`; el aviso
no cuenta como enviado) y `recogida/visitas.avisador_privado` no devuelve avisador, aunque haya un
token a mano. Por esos dos sitios pasan todos los avisos de ntfy.

`EODI_SECRETOS` y las variables de cada estado (`EODI_GASTO_API_ESTADO`...) siguen mandando sobre la
casa si están puestas: quien aísla no debe heredarlas apuntando a lo real.

## Las pruebas

`tests/conftest.py` se carga antes que el código, y sin que haya que pasarle nada:

- quita del entorno todo lo `EODI_*` y las credenciales, y fija la casa a una carpeta temporal;
- cada prueba tiene su propia casa vacía, también para las rutas que los módulos calculan al
  importarse;
- un gancho de auditoría de Python corta en el acto abrir un fichero de `.eodi`, `datos` o `base` de
  la casa real, resolver un nombre o conectar con algo que no sea esta máquina. Vale para todo el
  código, pase o no por `casa()`.

`tests/test_aislamiento.py` lo demuestra en un proceso aparte: con un token falso en una casa real
simulada, las pruebas del gasto, del silencio y del resumen no lo abren y no conectan con nada. Un
control negativo comprueba que, sin esa configuración, el mismo montaje sí ve la lectura.

## Los ensayos

- `recogida.horaria --ensayo` no arranca sin `EODI_CASA_AISLADA` y pone `EODI_SIN_AVISOS`.
- `recogida.avisos ensayo` no envía ni anota nada (probado en `tests/test_aislamiento.py`).
- El ensayo del servidor prepara su propia casa dentro de su raíz con copias del estado, sin tokens:
  ni el de ntfy, ni el extractor, ni el gancho de despliegue, ni las claves de despliegue.
- Los scripts de simulación de una sesión empiezan por `almacen.casa.exigir_aislamiento()`, que no
  deja correr nada sin `EODI_CASA_AISLADA`.

## Cómo ejecutar en el servidor

Fuera de los minutos de la recogida, con tope de memoria y desde un clon de la sesión, nunca con el
entorno de un servicio. El ayudante `aislado.sh` del despliegue interno crea la carpeta, limpia el
entorno y fija las variables:

```sh
systemd-run --user --scope -p MemoryMax=4G \
  bash <despliegue>/aislado.sh <carpeta-de-sesion> python -m pytest --basetemp=<carpeta-de-sesion>/t
```

`--basetemp` deja los temporales en la carpeta de la sesión y no en `/tmp`. Lo mismo vale para una
simulación:

```sh
systemd-run --user --scope -p MemoryMax=4G \
  bash <despliegue>/aislado.sh <carpeta-de-sesion> python sim_mi_simulacion.py
```

`python -m recogida.auditoria_fichas` necesita leer la configuración de los buckets que le toque y
una base copiada: se le pasa con `--base`, y no escribe.
