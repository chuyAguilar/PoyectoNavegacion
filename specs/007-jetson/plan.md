# Plan — Meta 007 · El tracker en la Jetson Orin Nano, con Slicer en el PC

Lo escribe el agente de planificación con `/planear`, sin código. Lo que el autor autoriza es este archivo.

## Cambios de esta versión (2026-11-04, con P28 y P29: la fase 7b)

- Entra la **fase 7b · Las dos cámaras a la vez en Windows**, entre la 7 y la 8, sin renumerar las demás (P29: «fase 7b: arreglar y medir»). Diagnostica primero la causa en vivo (parte A), arregla la capa de ajustes de Windows (parte B) y mide el P-7w largo (parte C).
- **La fase 7 cierra con la Jetson sola** (condición A, P28) y en su propio commit, antes de la 7b; el P-7w pasa a la 7b (propuesta de P31). La fase 7 no cambia de entrega.
- **B79** se arregla en la 7b con `igtl_rate listen --idle-s`; **B88** no hace falta y queda en el BACKLOG tal cual. **B89** no entra (no hay razón para mezclarla: es de la calibración, no de abrir cámaras).
- Archivos nuevos: `camera/dshow_props.py` y `tests/test_dshow_props.py`. Modificados: `camera/controls.py`, `diagnostics/probe_camera.py`, `diagnostics/igtl_rate.py`, `linux/perfil_temporal.py`, `tests/conftest.py` y sus pruebas. `camera/backend.py`, `tracker.py`, `vision/` y `transport/` no cambian.
- ADR propuesto: J7. Preguntas nuevas: P30 (qué se hace si la parte A descarta la vía elegida), P31 (dónde cierra la fase 7) y P32 (un puerto trasero solo para el diagnóstico).

### Lo leído para esta versión

- HEAD: `b211e83 Añade tegrastats_log y el protocolo de las dos cámaras, y anota B89 (meta 007, fase 7, sin el P-7)`. Árbol con `specs/007-jetson/clarify.md` modificado (P28 y P29) y un PDF sin seguir en `documentos/tecnicos/`.
- El encargo (`Claude outputs/fases/007/replan-7b-encargo.md`), `clarify.md` (P28, P29), `tasks.md`, `Claude outputs/fases/007/fase-7.md`, el protocolo `p7w.md`, el script `p7w/dos_camaras.ps1` (cabecera y lanzamiento) y las salidas `p7w/orden21_*`, `p7w/orden21b_*` y `p7w/corta_*` de los trackers.
- `docs/BACKLOG.md` B79, B88 y B89 e índice; `docs/DECISIONS.md`, índice (el último es ADR-034); `docs/CONTEXT.md` §4 (trampas 3 y 18); `docs/PRUEBAS.md`, índice (P01–P05).
- Código: `camera/controls.py` (`CapaWindowsDShow`: `indice`, `_abrir_cap`, `leer`, `aplicar`; `capa_para_plataforma`), `camera/backend.py` (`open()`: `_resolver_source`, `_comprobar_marca`, `_aplicar_controles`, y después el vídeo por MSMF), `camera/uvc.py` (`listar_camaras_dshow`, `_enumerar_dshow`, `_propiedades_moniker`: COM por ctypes sobre el moniker, con `BindToStorage`), `diagnostics/probe_camera.py` (`leer_controles`, `fijar`, `tras_msmf` y sus opciones), `diagnostics/igtl_rate.py` (`listen`, `NO_DATA_S = 5.0`, el CLI), `transport/igtl.py` (firmas), `linux/perfil_temporal.py` (`CLAVES`), `tests/conftest.py` (lo que niega) y quién usa `CapaWindowsDShow` (grep: `controls.py`, `probe_camera.py`, `test_ajustes_camara.py`, `test_sondear_camara.py`, `test_v4l2.py`).

### Hallazgos de esta versión (sin medir: son lo que la parte A mide)

15. **Falla la apertura corta por DSHOW, no la enumeración.** En `orden21b`, gs1 se resolvió bien (`-> indice MSMF 0`, y la capa pidió el índice DSHOW 0 por su puerto) y lo que falló fue `cv2.VideoCapture(0, CAP_DSHOW).isOpened()`, con el aviso de OpenCV `can't be used to capture by index`, que solo dice que el backend no abrió. La marca no llegó a leerse.
16. **La apertura corta de DSHOW abre un flujo de vídeo.** `CapaWindowsDShow` no pone FOURCC, tamaño ni fps, así que OpenCV arranca el grafo con el formato por defecto de la cámara, que puede ser sin comprimir. Con la otra cámara transmitiendo MJPG 1280x960 a ~88 fps por el mismo concentrador (`…USB(11)`), la reserva de ancho de banda isócrono de ese flujo puede no caber. Es la hipótesis principal (H1); las otras son que DSHOW no abra un dispositivo mientras otro proceso usa MSMF (H2) o algo del orden de los índices con una cámara ocupada (H3). Solas, las dos abren bien.
17. **La otra cámara bajó mientras tanto.** En `orden21b`, gs2 (la que sí abrió) dio 58 → 44 → 40 → 37 → 39 fps de cámara en 30 s, cuando sola da 88.7. No se sabe si es por el intento de gs1, por la luz o por la carga del PC; la parte A lo separa.
18. **Leer y escribir los controles no necesita vídeo.** DirectShow expone los controles de una cámara UVC en el filtro de captura, por `IAMVideoProcAmp` (brillo, contraste, saturación, nitidez, gamma, balance de blancos, compensación de contraluz, ganancia) e `IAMCameraControl` (exposición y foco), con `Get`/`Set` y una bandera auto/manual. El filtro se obtiene del mismo moniker que ya recorre `camera/uvc.py`, con `BindToObject` en vez de `BindToStorage`, sin grafo ni flujo: no reserva ancho de banda. Es la vía que propone la parte B (J7), si la parte A confirma que funciona con la otra cámara transmitiendo.
19. **B79 sigue mordiendo en el PC.** La marca tarda 1.3–2.7 s y abrir la cámara otros ~1–2 s (hasta ~8 s en el P-6); el listener se rinde a los 5 s, y el reintento del P-7 depende de B88 (el servidor no acepta el cliente nuevo hasta que falla un envío). Con el listener esperando lo suficiente en la primera conexión, B88 no interviene.

### Context7 (2026-11-04; solo API, sin rutas ni datos)

- **OpenCV** (`/opencv/opencv`, 5.x; instalado 4.11.0.86): `VideoCapture::open(index, apiPreference, params)` recorre los backends de captura por índice y, con `CAP_DSHOW`, devuelve `false` si `createCapture` no queda abierto, que es lo que produce el aviso de `orden21b`. En `cap_dshow.cpp`, poner `CAP_PROP_FOURCC` o `CAP_PROP_FPS` para el dispositivo y vuelve a montarlo (`stopDevice` + `setupDevice`): en DSHOW el formato se elige después de abrir, así que la apertura corta de hoy arranca con el formato por defecto. Que el constructor con `params` evite eso en DSHOW no está en lo consultado: por eso el plan no lo usa.
- **No confirmado por Context7:** qué interfaz de DirectShow usa OpenCV para cada `CAP_PROP_*` por DSHOW (en particular `CAP_PROP_AUTO_WB` y las banderas), ni la documentación de `IAMVideoProcAmp`/`IAMCameraControl` (Context7 no tiene la de DirectShow de Microsoft; solo enlaces de terceros, Vortice y windows-rs). Los IID, los índices de la vtable y los valores de las enumeraciones salen de `strmif.h` del SDK de Windows, y la fase los ata con la prueba de equivalencia en vivo (parte B, criterio 2): la capa nueva tiene que leer lo mismo que `cv2` por DSHOW en los 10 controles de cada cámara.

## Cambios de esta versión (2026-11-03, con P23: B77 antes de la fase 6)

- Entra la **fase 5b · El ruido de gs1 por V4L2 (B77)**, entre la 5 y la 6, sin renumerar las demás. Diagnostica primero, sin cámara, sobre las tres grabaciones del P-5, y después en una sesión en vivo con el autor (P-5b). Corrige solo si sale una causa clara y cae dentro de lo que dice P24.
- Los mínimos de P13 quedan confirmados tal cual (P23). Las fases 1 a 5 no cambian.
- Si P25 queda en (a), `linux/perfil_temporal.py` se adelanta de la fase 7 a la 5b, con una opción más (`--poner`), y la fase 7 solo lo usa. Cierra B81.
- Archivos nuevos: `diagnostics/ruido_pose.py` y su prueba. ADR propuesto, solo si hay corrección: J6. Preguntas nuevas: P24 y P25.

### Lo leído para esta versión

- HEAD: `76117f3 Cierra la fase 5 de la meta 007 con el P-5: bucle de 87.5 fps en la Jetson y 67.6 Hz en Slicer`. Árbol con `specs/007-jetson/clarify.md` modificado (P23) y el PDF de la meta 006 sin seguir.
- El encargo (`Claude outputs/fases/007/replan-b77-encargo.md`), `clarify.md` (P1–P23), `tasks.md`, `Claude outputs/fases/007/fase-5.md` y los resúmenes `p5_gs1_a_resumen.json`, `p5_pc_gs1_a_resumen.json` y `p5_gs1_a.json` (`--timing`). `docs/BACKLOG.md` B77; `docs/CONTEXT.md` §4 (trampas 3, 18, 19 y 20); `docs/PRUEBAS.md`, índice (P01–P05; nada de la meta 007).
- Las grabaciones, solo sus tablas y formas (sin medir nada): `p5_gs1_a.npz` 5249 frames, 5234 esquinas y envíos; `p5_gs2_a.npz` 5269 y 5243; `p5_pc_gs1_a.npz` 6203 y 6079. Las tres llevan `timestamps`, `frame_offsets`, `corners_2d`, `K`, `dist`, `sent_M` y `metadata_json` (filtro, detector, tamaño del marker y `capture`), y **ninguna lleva frames** (`frames_saved` vacío). El perfil, la calibración y el detector son los mismos en las dos máquinas (mismos sha256 en `metadata_json`).
- Código: `camera/v4l2.py` (los 11 controles del perfil y nada más), `camera/backend.py` (`open()`: la rama Linux), `camera/controls.py`, `camera/grabber.py` (la hora de captura por `perf_counter` en el hilo), `vision/pose.py` (`estimate_single_pose`, IPPE_SQUARE), `vision/filtering.py` (`OneEuroFilter`: `dt` con mínimo de 1 ms y el corte que sube con `beta·|dx|`), `vision/tracking.py` (`process_corners`), `diagnostics/pose_log.py` (`PoseLog`, `summarize`, `--save-frames`/`--frames-every`), `diagnostics/probe_camera.py` (`--leer --puerto`, por DSHOW), `tracker.py` (las opciones de grabación) y `linux/guardian.py` (`MODULOS`, `_args_py`: las rutas dentro del árbol o de `~/nav-salidas/`, y `linux.perfil_temporal` ya en la lista).
- Las salidas reales de `v4l2-ctl` del escaneo (`tests/data/linux/v4l2_list_ctrls_gs1.txt` y `_gs2.txt`).

### Hallazgos de esta versión (sin medir: son lo que la fase 5b mide)

10. **El ruido es de escala, no de posición lateral.** En gs1 por V4L2, sd x 0.010 mm y sd y 0.008 mm frente a sd z 0.074 mm. La z de un marker sale de su tamaño aparente: lo que la mueve es que las cuatro esquinas se abran o se cierren a la vez (umbral, brillo, desenfoque, compresión), más que el ruido independiente de cada esquina. La fase lo separa con el lado aparente en píxeles por frame.
11. **Lo grabado es lo filtrado.** `sent_M` sale del 1-Euro (`min_cutoff` 2.0, `beta` 0.05). En `OneEuroFilter`, un `dt` muy corto (frames que llegan en ráfaga) da una derivada grande, sube el corte y deja pasar más ruido. Recalcular la pose cruda desde `corners_2d` y volver a filtrarla con tiempos uniformes separa el detector del filtro sin cámara.
12. **Los controles que el perfil no nombra.** El perfil fija 11 controles. En Linux, `v4l2-ctl` lista además `hue`, `power_line_frequency` (60 Hz), `white_balance_temperature`, `focus_automatic_continuous` (por defecto 1; en el escaneo, 0), `pan`, `tilt` y `zoom`, que la capa V4L2 ni lee ni escribe. En Windows nadie los escribe tampoco: valen lo que la cámara tenga guardado. Si alguno difiere entre las dos cámaras o entre antes y después de una corrida, es candidato.
13. **La exposición seguramente es la misma.** El perfil pide 0.977 ms (el −10 de DSHOW, 2^−10 s); V4L2 la escribe y la lee en unidades de 100 µs, y la cámara da 10 (1.0 ms). El valor que la cámara guarda por Windows no se puede leer en esas unidades desde DSHOW. La fase lo trata como hipótesis, no como diferencia probada.
14. **gs2 por V4L2 está bien (0.040 mm).** Lo que le pase a gs1 no es de V4L2 en general: es de gs1 en la Jetson (su puerto del hub, sus controles, su escena) o de una interacción. Falta gs2 por MSMF en el PC para saber si V4L2 también la empeora algo.

### Context7 (2026-11-03; solo API, sin rutas ni datos)

- **SciPy** (`/scipy/scipy`): `scipy.signal.welch(x, fs, nperseg=…)` devuelve las frecuencias y la densidad espectral; `nperseg` por defecto 256 y, si es mayor que la serie, se recorta con aviso; `detrend` por defecto quita la media. Es lo que usa `espectro` en `ruido_pose`. `scipy` ya está en `requirements.txt` y en `requirements-jetson.txt`.
- **OpenCV** (`/websites/opencv`, `/opencv/opencv`; 4.13/5.0, instalado 4.11.0.86): `CAP_PROP_POS_MSEC` está documentada como la posición de un archivo de vídeo; la documentación no dice que con `CAP_V4L2` dé la hora del búfer del driver. `CAP_PROP_CONVERT_RGB` está documentada para DSHOW; para V4L2 con MJPG no se encontró que devuelva el JPEG sin decodificar. Por eso el plan **no** usa ninguna de las dos: la hora sigue siendo la del hilo de captura y el tamaño de cada JPEG queda fuera (va al BACKLOG si hace falta). `solvePnP` con `SOLVEPNP_IPPE_SQUARE` se reusa tal cual desde `vision/pose.py`, sin cambiar.

## Cambios de la versión del 2026-10-29 (con P6–P18 contestadas)

- **P8 lo cambia casi todo:** los agentes trabajan en la Jetson por SSH. Entra una fase nueva, la 2 · La barrera de seguridad para los agentes, con su diseño completo (§ «La barrera»), antes de que ningún agente toque la Jetson.
- **P6:** la fase 1 es ahora el escaneo del equipo, solo lectura, que corre el autor con su cuenta. El método de Python 3.11 se pregunta al cerrarla, con los datos; uv ya no se da por hecho.
- **P9:** la fase de red mide las tres redes (LAN, cable directo y Tailscale).
- **P16:** confirmado el panel en el PC por SSH, y además pasa por la misma barrera (J3).
- **P7, P10–P15, P17 y P18:** las recomendadas, ya en las fases. Los mínimos de P13 se confirman tras la fase 5 (era la 3) y antes de la 6.
- Las fases pasan de 7 a 9. B69 cambia de contenido; entran B70 y B71. Entra el ADR J4. Preguntas nuevas: P19 y P20.

## Lo leído

- HEAD: `7d2ac24 Avisa en dirección de las peticiones pendientes (meta 005, fase 4)`. Árbol con `memory.md` modificado y `specs/006-*`, `specs/007-*` sin seguir.
- `specs/007-jetson/spec.md`, `clarify.md` (P1–P18) y `tasks.md`, completos. `docs/constitution.md`, `memory.md`, `docs/CONTEXT.md` §3 y §4 (trampas 1–20), `CLAUDE.md`, `.claude/settings.json`, `.claude/settings.local.json`, `.claude/agents/desarrollo.md` y `pruebas.md`.
- `docs/BACKLOG.md`: índice hasta B65 y B23, B50, B53, B54, B55, B60. `docs/DECISIONS.md`: índice hasta ADR-034 (el plan sin autorizar de la meta 006 propone ADR-035 a ADR-039). `docs/ARCHITECTURE.md`: índice (§3.1, §3.5, §3.7 y §6 cambian). `docs/PRUEBAS.md`: índice (P01–P05).
- Código de `codigo/` (fuera de `historico/`), leído para la versión anterior del plan sobre el mismo HEAD: `camera/backend.py`, `camera/controls.py` (`capa_para_plataforma("linux")` lanza `NotImplementedError`), `camera/uvc.py`, `camera/grabber.py`, `tracker.py`, `transport/igtl.py`, `gui/recipes.py`, `gui/processes.py`, `diagnostics/igtl_rate.py`, `slicer/receive_marker0.py`, los perfiles, `tests/conftest.py` (B34), `tests/test_replay_marker0.py`. `pyigtl` 0.3.1 leído del venv.
- Tamaños (2026-10-29): `codigo/` sin `.venv` ocupa 166 MB, de los que 163 MB son `historico/` y 5.6 MB `tests/`. `origin` es `https://github.com/chuyAguilar/PoyectoNavegacion.git` (público, B60).

### Hallazgos que siguen valiendo

1. **El servidor OpenIGTLink solo escucha en 127.0.0.1.** `IgtlSender` crea `OpenIGTLinkServer(port=...)` con `local_server=True`. Con `local_server=False`, en Linux `pyigtl` toma la IP de `iface` por `ioctl` (por defecto `eth0`) y, si esa interfaz no existe, cae en silencio a 127.0.0.1. Hay que elegir la interfaz y comprobar a qué dirección quedó ligado (principio 7). Toca `transport/`: ADR J2 y verificación en vivo.
2. **PySide6 no tiene rueda para la Jetson.** Las ruedas arm64 de Linux se construyen en Ubuntu 24.04 (glibc 2.39) y la Jetson tiene glibc 2.35 (Qt for Python, Context7). Confirma P16.
3. **`WebcamBackend` en Linux caería en MSMF** (`backends.get(nombre, cv2.CAP_MSMF)` e `int(source)`). Hace falta la rama Linux en el backend, no solo en `controls`.
4. **`--stop-stdin` sirve por SSH:** el fin de la entrada estándar llega también cuando se corta la conexión (ADR-029).
5. **La latencia de `igtl_rate listen`** resta relojes de dos máquinas; hay que medir el desfase aparte.

### Hallazgos nuevos

6. **En Windows PowerShell 5.1 una tubería hacia un programa nativo pasa por texto** y corrompe un `tar` binario, y no existe la redirección `<`. Lo que manda bytes a la Jetson (escaneo, copia WIP) usa `Start-Process` con `-RedirectStandardInput` de un archivo, y el guardián devuelve el sha256 de lo recibido para compararlo.
7. **Los agentes corren como el usuario de Windows del autor.** Lo que ese usuario alcanza, un agente lo alcanza rodeando `settings.json` (p. ej. un `subprocess` desde el Python permitido). Por eso la barrera de verdad tiene que estar en la Jetson y no en el PC (B69, P20).
8. **Un agente que ejecuta Python en la Jetson ejecuta cualquier cosa que su cuenta pueda.** El código lo escribe él y llega por la copia WIP. La lista blanca del guardián filtra la entrada y deja registro, pero lo que de verdad impide el daño es que esa cuenta no tenga privilegios.
9. **Un `Match` en un archivo de `sshd_config.d/` puede alcanzar a lo que viene detrás** en el `sshd_config` principal de Ubuntu, que lo incluye arriba. El drop-in termina con `Match all` y se comprueba que la configuración efectiva de la cuenta del autor no cambió (`sshd -T -C user=…` antes y después).

### Context7 (2026-10-29; solo API, sin rutas ni datos)

- **OpenSSH** (`/openssh/openssh-portable`, `sshd.8`, `sshd_config.5`, `ssh_config.5`, `auth-options.c`, `session.c`):
  - `command="…"` en `authorized_keys` ejecuta esa orden e ignora la del cliente, que queda en `SSH_ORIGINAL_COMMAND`. Vale para shell, orden y subsistema (también sftp y scp). `ForceCommand` de `sshd_config` la reemplaza.
  - `restrict` apaga el reenvío de puertos, de agente y de X11, el pty y `~/.ssh/rc`. `from="patrones"` exige además la IP de origen, con CIDR.
  - `ForceCommand` se ejecuta con el shell de la cuenta y `-c`, ignora `~/.ssh/rc` y **no limita el reenvío**: hay que apagarlo aparte (`DisableForwarding`).
  - En un bloque `Match` valen `AuthorizedKeysFile`, `ForceCommand`, `DisableForwarding`, `PermitTTY`, `PermitUserRC`, `PermitTunnel`, `AllowAgentForwarding`, `PasswordAuthentication`, `KbdInteractiveAuthentication`, `ClientAliveInterval` y `ClientAliveCountMax`. Si una palabra aparece en varios `Match`, vale la primera.
  - El reenvío pasa por dos capas, `authorized_keys` y `sshd_config`, y tienen que permitirlo las dos.
  - `PermitUserEnvironment` está en `no` por defecto (si se activa, permite rodeos con `LD_PRELOAD`). `IdentitiesOnly yes` hace que el cliente use solo la clave configurada.
  - No se comprobó qué versión trae la Jetson: Ubuntu 22.04 suele traer la 8.9. El escaneo lo dice (`ssh -V`); las opciones de arriba existen desde antes de la 8.9 salvo que el escaneo diga otra cosa.
- **Python** (`/python/cpython`, `tarfile`): `extractall(filter="data")` rechaza rutas absolutas, `..`, enlaces que salen del destino y archivos de dispositivo, y quita dueño y permisos raros. Es de la 3.12 con retroportes de seguridad: el guardián comprueba `hasattr(tarfile, "data_filter")` y, si no está, se niega (principio 7). El escaneo lo mide.
- De la versión anterior, sin cambios: GTSAM (`/borglab/gtsam`, ruedas Linux aarch64 para 3.11–3.14), uv (`/websites/astral_sh_uv`, nivel 2 en aarch64), OpenCV (`CAP_V4L2`, `set()` True no asegura el valor), opencv-python (un paquete por entorno), pyigtl (sin `iface` en la documentación: sale del código), Qt for Python (glibc 2.39).
- Sin Context7 (no son librerías o no están): `v4l2-ctl`, `tegrastats`, `nvpmodel`, `nmcli`, `tailscale`, OpenSSH de Windows en lo que difiera del portable. Sus salidas se toman del escaneo.

## La barrera de seguridad para los agentes (P8)

Diseño de la fase 2. Objetivo: que un agente, por error o por un código suyo que salga mal, no pueda dejar la Jetson inservible ni cambiar nada del sistema, y que todo lo que haga quede registrado y con tope.

### Las tres capas

1. **La cuenta (la barrera dura, en el sistema operativo).** Una cuenta propia en la Jetson, `navagente`, creada por el autor:
   - Fuera de los grupos `sudo`, `admin`, `docker`, `lxd`, `adm` y `disk`. Pertenecer a `docker` equivale a ser root; la fase lo comprueba.
   - Solo en `video`, para las cámaras, y en `render` si el escaneo muestra que hace falta para algo que se mida.
   - Sin contraseña (`--disabled-password`), con `/bin/bash` como shell (hace falta para `ForceCommand`) y la carpeta `/home/navagente` en 0750.
   - En `/etc/cron.deny` y `/etc/at.deny`, y sin `linger` de systemd: no puede dejar nada programado que sobreviva a la sesión.
   - Lo único que puede escribir es su carpeta, `/tmp` y `/dev/shm`. La carpeta del proyecto es su carpeta: `~/nav/repo` (el clon), `~/nav-wip/codigo` (la copia sin commit), `~/nav-salidas/` (lo que se mide), `~/nav-registro/`, `~/.venvs/navegacion` y las cachés de pip o uv.
2. **La entrada (la orden forzada y el guardián).** En `sshd`, para esa cuenta y solo para ella:
   - La clave se lee de `/etc/ssh/authorized_keys/navagente`, de root, que la cuenta no puede editar.
   - Se fuerza el guardián (`ForceCommand`), sin pty, sin reenvío de ningún tipo, sin `~/.ssh/rc`, sin contraseña y con `ClientAliveInterval 5` × 3.
   - La clave lleva `restrict,from="<subredes>"`, las de las tres redes de P9.
   - El guardián (`/usr/local/lib/nav-guardian/guardian`, de root, 0755, lanzado con `/usr/bin/python3 -I` y solo biblioteca estándar) lee `SSH_ORIGINAL_COMMAND`, lo parte sin shell y solo ejecuta los verbos de su lista blanca. Fija la carpeta y un entorno limpio, y pone tope de tiempo y límites a cada orden.
   - Si se cambia la lista, se cambia en el repo: commit del autor y el autor reinstala con sudo. La cuenta no la puede tocar.
3. **El PC (la barrera blanda).** Reglas de `settings.json` que dejan a los agentes usar solo el alias `nav-jetson` y les niegan el alias personal del autor, `scp`, `sftp`, las opciones de `ssh` en la línea y la lectura de `~/.ssh/`. Sirven contra el error, no contra un rodeo (hallazgo 7). Lo que la refuerza es P20: la clave personal del autor con frase de paso, y el `sudo` del autor en la Jetson con contraseña.

### Los verbos del guardián (la lista blanca)

Todo lo que no está aquí se niega con código 126 y queda registrado. Ningún verbo invoca un shell; los argumentos se validan uno a uno.

- `ayuda`: la lista de verbos.
- `info <consulta>`: consultas fijas, solo lectura, cada una con su argv cerrado y 10 s de tope:
  - `sistema`, `python`, `cpu`, `memoria`, `disco`, `usb`, `red`, `puertos` (`ss -ltnp`), `servicios` (`systemctl list-units --type=service --state=running --no-pager`), `energia` (`nvpmodel -q`, si la cuenta lo puede leer) y `temperatura` (`/sys/class/thermal`).
  - `v4l2 <nombre by-path>`, con `v4l2-ctl --info --list-formats-ext --list-ctrls-menus`, sin ninguna opción `--set-*` ni `--stream-*`.
  - `camara-libre <nombre by-path>` (`fuser`) y `puerto-libre <puerto 18944–18950>`.
- `repo clonar`: solo si no existe, `git clone --filter=blob:none --sparse` de la URL fija de `origin`, en modo no-cone con `/*`, `!/herramientas/`, `!/documentos/`, `!*.nrrd`, `!*.dcm`. Los blobs de los datos de paciente no se descargan. `repo actualizar` (`git pull --ff-only`) y `repo estado` (`git log --oneline -1`, `git status --short`). No hay verbo de commit ni de push, y la cuenta no tiene credenciales de GitHub.
- `wip recibir`: lee un `tar` por la entrada, de 50 MB como mucho, y lo extrae en una carpeta temporal con `filter="data"`. Se niega si hay enlaces, rutas fuera de `codigo/`, `*.nrrd` o `*.dcm`. Si todo vale, sustituye `~/nav-wip/codigo` (la anterior queda como `.anterior`) y enlaza `historico/` al del clon, que no viaja. Devuelve el sha256 de lo recibido. `wip estado`.
- `entorno instalar [--gtsam]`: corre `codigo/linux/instalar_entorno.sh` del árbol que se diga, sin sudo, con 1800 s de tope. Si el método de Python que elija el autor tras la fase 1 pide sudo, esa parte la hace el autor.
- `suite <repo|wip> [-q] [-k EXPR] [ruta bajo tests/]`: pytest del venv, con 900 s de tope.
- `py <repo|wip> <modulo> [args]`: `python -u -m <modulo>` del venv, solo con estos módulos y topes: `tracker` (7200 s), `camera.v4l2` (60), `diagnostics.igtl_rate` (900), `diagnostics.clock_offset` (600), `diagnostics.tegrastats_log` (60), `linux.perfil_temporal` (30) y `linux.sonda_privilegios` (60). Un argumento con `/` tiene que caer dentro del árbol o de `~/nav-salidas/`, y `--record`, `--output` y `--salida` solo en `~/nav-salidas/`.
- `camara rafaga <nombre by-path> <frames ≤ 1800>`: `v4l2-ctl --stream-mmap --stream-count` a 1280×960 MJPG, con 60 s de tope. Es el único verbo que abre la cámara fuera del tracker. Quién lo teclea lo dice P19.
- `medir tegrastats <segundos ≤ 900>`: lo guarda en `~/nav-salidas/`.
- `traer <ruta bajo ~/nav-salidas/>`: lo saca por la salida estándar (sustituye a scp).
- `procesos`: los procesos de la cuenta. `parar <pid>`: solo uno lanzado por el guardián (SIGTERM; a los 5 s, SIGKILL al grupo).
- `registro [n ≤ 200]`: las últimas líneas del registro.
- `prueba-tope`: duerme 30 s con 3 s de tope. Solo sirve para probar la barrera.

### Lo prohibido (por la cuenta, y además por el guardián)

`sudo`, `su`, `pkexec`; `apt`, `apt-get`, `dpkg -i`, `snap` y `pip` fuera del venv; `reboot`, `shutdown`, `poweroff` y `systemctl` salvo las consultas de `info`; `nvpmodel` salvo `-q`; `jetson_clocks`; firmware, arranque y flasheo (`nvbootctrl`, `efibootmgr`, `fwupdmgr`, los scripts de flash de L4T, `/boot`, `/boot/efi`); particiones y discos (`fdisk`, `parted`, `mkfs`, `dd`, `mount`, `/dev/nvme*`, `/dev/mmcblk*`); servicios del sistema y de usuario; `docker`; `ollama` (parar, arrancar o cargar modelos); `crontab` y `at`; `ssh` hacia fuera desde la Jetson; escribir fuera de la carpeta del proyecto; un shell interactivo (sin orden, el guardián se niega).

### Lo que el guardián hace además

- **Tope y limpieza.** Cada orden corre en su propio grupo de procesos. Al tope, SIGTERM al grupo, y a los 5 s SIGKILL; sale con 124. Si se corta la conexión, el guardián recibe SIGHUP o SIGPIPE y para el grupo igual.
- **Límites** a cada hijo: archivo de 2 GiB como mucho, 512 procesos, sin volcado de memoria y `oom_score_adj` 500, para que, si falta memoria, el sistema mate antes lo del agente que Ollama o el escritorio.
- **Antes de lo pesado** (`entorno`, `suite`, `py`, `camara`, `medir`): se niega si quedan menos de 5 GB libres en `/`, si alguna zona térmica pasa de 85 °C o si ya hay 3 órdenes pesadas en marcha (la fase 7 necesita 2 trackers y 2 listeners: los listeners de `igtl_rate` cuentan como ligeros).
- **Registro.** Una línea JSON por intento en `~/nav-registro/guardian.jsonl`: hora, IP de origen, orden original, permitido o negado con su motivo, código de salida, duración y si se cortó por tope. La misma línea va al diario del sistema con `logger -t nav-guardian`, que la cuenta no puede borrar; el autor lo lee con `journalctl -t nav-guardian`.
- **Entorno limpio:** `PATH=/usr/bin:/bin` más el `bin` del venv, `HOME`, `LANG=C.UTF-8` y `PYTHONNOUSERSITE=1`. Sin `LD_*` ni `PYTHONPATH`. Si la cuenta que lo corre no es `navagente`, se niega.

### Lo que queda siempre para el autor

Todo lo que pide sudo: crear y borrar la cuenta, instalar o cambiar el guardián y `sshd`, `apt` (p. ej. `v4l-utils`, P12), la configuración de red (IPs del cable directo, cortafuegos), parar, arrancar o cargar Ollama (P15), `nvpmodel` y `jetson_clocks` (que no se usan, P17), reiniciar y actualizar JetPack o firmware. Además, lo físico (cables, cámaras, caja de luz, Marker0), Slicer, su clave personal, los commits y los push, y aplicar los cambios de `settings.json` y de `~/.ssh/config`.

**Para cortar el acceso de golpe:** `sudo mv /etc/ssh/authorized_keys/navagente /etc/ssh/authorized_keys/navagente.off && sudo pkill -u navagente`. Para deshacerlo todo, `sudo bash desinstalar_guardian.sh`.

### Cómo se prueba la barrera antes de usarla

Es el criterio de la fase 2. Ningún agente usa `nav-jetson` hasta que el autor lo da por bueno. Son cuatro pruebas:
1. `probar_barrera.ps1`, con los casos negados y permitidos de la fase 2.
2. La sonda de privilegios, ejecutada como lo haría un código del agente.
3. El escaneo del autor antes y después, comparado.
4. El simulacro de corte.

### Lo que el autor aplica (texto exacto)

**En la Jetson,** con `instalar_guardian.sh`. Primero `--simular`, que imprime cada cambio sin hacerlo, y después de verdad. El drop-in `/etc/ssh/sshd_config.d/60-nav-guardian.conf`:

```
Match User navagente
    AuthorizedKeysFile /etc/ssh/authorized_keys/%u
    ForceCommand /usr/local/lib/nav-guardian/guardian
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    DisableForwarding yes
    PermitTTY no
    PermitUserRC no
    PermitTunnel no
    AllowAgentForwarding no
    ClientAliveInterval 5
    ClientAliveCountMax 3
Match all
```

y `/etc/ssh/authorized_keys/navagente` (root, 0644), una línea:

```
restrict,from="<subred LAN>,<subred del cable directo>,100.64.0.0/10" ssh-ed25519 <clave pública de nav_agente_ed25519> nav-agente@BigDaddy
```

El script, en este orden:
1. `sudo sshd -T -C user=<autor>,host=<pc>,addr=<ip del pc>` a un archivo.
2. Crea la cuenta, los grupos, `cron.deny` y `at.deny`, el guardián y los dos archivos.
3. `sudo sshd -t`: si falla, borra el drop-in y para sin recargar.
4. Repite el `sshd -T` del paso 1 y lo compara: si cambió algo, borra el drop-in y para.
5. `sudo systemctl reload ssh`. Recargar no corta las sesiones abiertas: el autor deja una abierta con su cuenta mientras tanto.

**En el PC,** la clave de los agentes, sin frase de paso porque la usa `BatchMode`:
- `ssh-keygen -t ed25519 -f $HOME\.ssh\nav_agente_ed25519 -C nav-agente@BigDaddy`, y Enter dos veces.
- En `$HOME\.ssh\config` (fuera del repo):

```
Host nav-jetson-lan
    HostName <IP de la Jetson en la LAN>
Host nav-jetson-cable
    HostName <IP de la Jetson en el cable directo>
Host nav-jetson-ts
    HostName <nombre o IP de Tailscale de la Jetson>
Host nav-jetson
    HostName <la de la red que se use por defecto>
Host nav-jetson nav-jetson-*
    User navagente
    IdentityFile ~/.ssh/nav_agente_ed25519
    IdentitiesOnly yes
    BatchMode yes
    RequestTTY no
    ForwardAgent no
    ClearAllForwardings yes
    ConnectTimeout 10
    ServerAliveInterval 5
    ServerAliveCountMax 3
```

**En `.claude/settings.json`,** añadido a `allow`:

```
"Bash(ssh nav-jetson*)",
"PowerShell(ssh nav-jetson*)",
"PowerShell(powershell -NoProfile -ExecutionPolicy Bypass -File codigo/linux/enviar_wip.ps1 *)",
"PowerShell(powershell -NoProfile -ExecutionPolicy Bypass -File codigo/linux/probar_barrera.ps1 *)"
```

y a `deny`:

```
"Bash(ssh yahboom*)", "PowerShell(ssh yahboom*)",
"Bash(ssh -*)", "PowerShell(ssh -*)",
"Bash(ssh *@*)", "PowerShell(ssh *@*)",
"Bash(scp *)", "PowerShell(scp *)",
"Bash(sftp *)", "PowerShell(sftp *)",
"Read(~/.ssh/**)", "Edit(~/.ssh/**)"
```

Las opciones de `ssh` van en `~/.ssh/config`, no en la línea: por eso se puede negar `ssh -*`. El panel no pasa por estas reglas (es un programa del autor) y pone sus opciones en el argv.

**En `.claude/agents/desarrollo.md` y `pruebas.md`,** una regla más en «Reglas» (la aplica la dirección con permiso del autor): «En la Jetson, solo por `ssh nav-jetson <verbo>` (los verbos, en `codigo/linux/README.md`); un 126 es una negación del guardián y no se rodea: se dice en el reporte». Si P19 queda en (a), esa misma regla añade: «`camara rafaga` y `py … tracker` los teclea el autor en la sesión en vivo».

## Archivos

Crear:
- `codigo/linux/escanear_jetson.sh` (fase 1): el escaneo, solo lectura, ASCII y LF, cada orden con `timeout 10` y todo con tope de 120 s. Escribe solo por la salida estándar. Recoge:
  - Sistema: `uname`, `/etc/os-release`, `/etc/nv_tegra_release`, versión de JetPack con `dpkg-query -W`, `uptime`.
  - Python: versiones, `pip`, si hay uv o conda, glibc y `tarfile.data_filter`.
  - CPU y GPU: `lscpu`, gobernador y frecuencias, `devfreq`, CUDA.
  - Memoria: `free`, swap y zram. Disco: `df`, `lsblk`.
  - USB: `lsusb`, `lsusb -t`.
  - V4L2: `/dev/video*`, `/dev/v4l/by-path/` y `by-id/`; si hay `v4l2-ctl`, `--info`, `--list-formats-ext` y `--list-ctrls-menus` de cada `index0`; `udevadm info` de cada una.
  - Red: `ip -br addr`, `ip route`, `nmcli device status`, `tailscale status` e `ip`, `ss -ltnp`, `ufw` activo o no.
  - Servicios: los que corren, si Ollama arranca solo y `ollama ps`.
  - Energía: `nvpmodel -q`. Temperatura: las zonas y 10 s de `tegrastats`.
  - La cuenta: `id`, su shell, los grupos `sudo`, `docker` y `video`. `ssh -V` y el `sshd_config` (es legible).
  - Al final, `find ~ -maxdepth 2 -newer <marca>`, que tiene que salir vacío: no escribió nada.
- `codigo/linux/escanear.ps1` (fase 1): `-Alias yahboom -Salida <txt> -TopeS 180`. Lanza el escaneo con `Start-Process ssh … -RedirectStandardInput <sh> -RedirectStandardOutput <txt>` y espera con tope (hallazgo 6).
- `codigo/linux/guardian.py` (fase 2): el guardián. Solo biblioteca estándar y Python ≥ 3.8: corre con el `python3` del sistema y no con el venv, que es de la cuenta. Lo Linux (`pwd`, `resource`, `os.killpg`) se importa dentro de las funciones, para que la suite lo pruebe en Windows.
- `codigo/linux/__init__.py`, `codigo/linux/sonda_privilegios.py` (fase 2): lo que haría un código del agente que intentara salirse. Todo inofensivo: `sudo -n true`; grupos; `os.access(W_OK)` en `/etc`, `/usr`, `/boot`, `/opt`, `/var/lib/nvpmodel`, `/etc/systemd/system`, `/var/run/docker.sock` y los discos de bloque; un `touch` en `/etc` que tiene que fallar (si no falla, lo borra y lo marca como fallo); `crontab -l` con `cron.deny`; `loginctl show-user -p Linger`; y `systemctl --no-ask-password restart nav-sonda-inexistente.service`. Da un JSON con cada comprobación y un total.
- `codigo/linux/instalar_guardian.sh`, `codigo/linux/desinstalar_guardian.sh` (fase 2): para el autor, con sudo y `--simular` (§ «Lo que el autor aplica»). El de desinstalar quita el drop-in, la clave y el guardián, recarga `ssh`, para los procesos de la cuenta y, solo con `--borrar-cuenta`, la borra.
- `codigo/linux/probar_barrera.ps1` (fase 2): los casos de la fase 2, cada uno con lo esperado. Escribe una tabla en `Claude outputs/fases/007/barrera/` y sale con 0 solo si todos dan lo esperado.
- `codigo/linux/enviar_wip.ps1` (fase 3): `tar` de `codigo/` sin `.venv`, `__pycache__`, `.pytest_cache`, `historico/`, `*.nrrd` ni `*.dcm`, a un temporal. Lo manda con `Start-Process ssh nav-jetson wip recibir -RedirectStandardInput` y compara el sha256 local con el que devuelve el guardián.
- `codigo/linux/instalar_entorno.sh` (fase 3): crea `~/.venvs/navegacion` con Python 3.11 por el método que elija el autor tras la fase 1, instala `requirements-jetson.txt` y comprueba los imports (`cv2.aruco.ArucoDetector`, `pyigtl`, `scipy`). Con `--gtsam`, prueba `gtsam`. Dice el disco usado. Sin sudo.
- `codigo/requirements-jetson.txt` (fase 3): `opencv-python` 4.11.0.86, numpy, scipy, pyyaml, pyigtl 0.3.1 y pytest con las versiones del venv del PC, y `gtsam` comentado. Sin `pyorbbecsdk2`, `open3d`, `pyside6` ni `matplotlib`.
- `codigo/linux/perfil_temporal.py` (fase 7, P18): copia un perfil y cambia solo `transforms_port` (18945–18950), con la salida en `~/nav-salidas/perfiles/`.
- `codigo/linux/README.md`: cómo se trabaja con la Jetson (los verbos, la copia WIP, el clon, la suite, el tracker, cómo se para, cómo se comprueba que la cámara y el puerto quedan libres, el corte de acceso). Empieza en la fase 1 y se completa en la 9.
- `codigo/camera/v4l2.py` (fase 5), `codigo/diagnostics/clock_offset.py` (fase 6), `codigo/diagnostics/tegrastats_log.py` (fase 7) y `codigo/profiles/jetson.yaml` (fase 8), como en la versión anterior. `jetson.yaml` lleva el alias `nav-jetson`, el árbol (`repo`) y la interfaz; ni IP ni secretos.
- `codigo/diagnostics/ruido_pose.py` (fase 5b): el análisis del ruido en reposo de una o varias grabaciones de `tracker --record`, sin cámara y en cualquier máquina. Lee solo el `.npz` (y los PNG de `--save-frames`, si los hay); escribe un JSON y un Markdown que no pisan nada.
- `codigo/tests/test_ruido_pose.py` (fase 5b): sobre series sintéticas (una normal, una de dos valores, una con un seno de frecuencia conocida, tiempos uniformes y en ráfaga) y sobre el dataset del replay de Marker0, donde `refiltrar` con los tiempos grabados tiene que reproducir `sent_M` (≤ 1e-9 mm en Windows, ≤ 1e-3 mm en Linux, P22).
- Si P25 queda en (a): `codigo/linux/perfil_temporal.py` y `codigo/tests/test_perfil_temporal.py` se adelantan de la fase 7 a la 5b (firma en «Funciones y clases»).
- Pruebas: `test_escaneo_jetson.py` (fase 1), `test_guardian.py` y `test_sonda_privilegios.py` (fase 2), `test_v4l2.py` (fase 5), `test_clock_offset.py` (fase 6), `test_tegrastats_log.py` y `test_perfil_temporal.py` (fase 7) y `test_receta_jetson.py` (fase 8). Además, los casos nuevos de `test_transport.py`, `test_camera_backend.py` y `test_ajustes_camara.py`. Las salidas reales de `v4l2-ctl` y `tegrastats` van en `codigo/tests/data/linux/` (texto del escaneo, sin datos de paciente).

Modificar: los mismos que en la versión anterior.
- `camera/controls.py`, `camera/backend.py`, `transport/igtl.py`, `tracker.py`, `diagnostics/igtl_rate.py`, `gui/recipes.py` y `gui/panel.py`.
- Los perfiles gs1 y gs2 ganan `usb_port_linux`.
- `tests/conftest.py`: también niega `camera.v4l2.listar_camaras_v4l2` y `ejecutar_v4l2ctl`.
- El `skipif` de las pruebas que solo valen en Windows.
- `codigo/readme.md`, `docs/ARCHITECTURE.md` (§3.1, §3.5, §3.7 y §6) y `docs/CONTEXT.md` (§3, §4 y §6).

En la fase 5b, además:
- `codigo/linux/README.md`: § «El ruido en reposo (B77)», con el protocolo P-5b y cómo se traen los PNG.
- Solo si sale una causa que P24 deja corregir en la fase: `camera/v4l2.py` (los controles fijos de Linux, J6), sus pruebas en `test_v4l2.py` y, si hace falta, el caso nuevo en `test_camera_backend.py` de que en Windows `open()` sigue haciendo las mismas llamadas. Nada más de `camera/`, ni `grabber.py`, `tracker.py`, `vision/` o `transport/`.

En la fase 7b:
- Crear `codigo/camera/dshow_props.py`: los controles de una cámara por COM sobre el filtro de captura de DirectShow (`IAMVideoProcAmp`, `IAMCameraControl`), por ctypes, sin dependencia nueva y sin abrir vídeo. La parte pura (la tabla de controles, las unidades, qué se escribe) se prueba sin cámara; la parte COM es fina y se comprueba en vivo.
- Crear `codigo/tests/test_dshow_props.py`: la tabla, las conversiones, `CapaWindowsCOM` con un dispositivo falso (lee, escribe solo lo que difiere, relee, `AjustesNoAplicados`, la marca sin escribir nada) y que un puerto con 0 o más de 1 cámara para.
- Modificar `codigo/camera/controls.py`: `capa_para_plataforma("win32")` devuelve `CapaWindowsCOM` (parte B, J7). `CapaWindowsDShow` se queda igual, para la sonda y la comparación. El docstring lo dice.
- Modificar `codigo/diagnostics/probe_camera.py`: `--capa cv2|com` (obligatoria con `--leer`, `--fijar` y `--tras-msmf`; principio 7) y `--comparar-capas` (lee por las dos y dice cada diferencia). Es lo que usa la parte A.
- Modificar `codigo/diagnostics/igtl_rate.py`: `--idle-s` en `listen` (B79). Sin la opción, los 5 s de hoy: el banco y las pruebas no cambian.
- Modificar `codigo/linux/perfil_temporal.py`: `camera.usb_port_windows` en `CLAVES`, para la marca cruzada sin mover cables (criterio 3 de la parte B). El nombre del módulo no cambia aunque sirva también en Windows.
- Modificar `codigo/tests/conftest.py`: niega también `camera.dshow_props.abrir_filtro` (la única función que toca COM de verdad).
- Modificar las pruebas: `test_ajustes_camara.py` (`capa_para_plataforma("win32")` da `CapaWindowsCOM`), `test_v4l2.py` (la línea 494, lo mismo), `test_sondear_camara.py` (`--capa` y `--comparar-capas`), `test_igtl_rate.py` (`--idle-s`) y `test_perfil_temporal.py` (la clave nueva).
- Fuera de git: `Claude outputs/fases/007/p7b.md` (el protocolo de las partes A y C) y `p7w.md` y `p7w/dos_camaras.ps1` al día: el listener con `--idle-s 60` y sin el bucle de reintento.
- `docs/ARCHITECTURE.md` (§3.1 y el árbol), `docs/CONTEXT.md` §4 (la trampa nueva: la apertura corta por DSHOW no abre con la otra cámara transmitiendo por el mismo concentrador, si la parte A lo confirma) y §6, `codigo/readme.md` (la sonda) y `docs/BACKLOG.md` (B79 cerrada).
- No cambian: `camera/backend.py`, `camera/grabber.py`, `camera/uvc.py` (se reusan sus funciones), `camera/v4l2.py`, `tracker.py`, `vision/`, `transport/`, los perfiles del repo y los scripts de Slicer.

Lo que aplica el autor o la dirección, no `desarrollo`: `.claude/settings.json`, `~/.ssh/config`, los agentes `desarrollo.md` y `pruebas.md`, `CLAUDE.md` §4 y §5 (el texto, en el reporte de la fase 9) y todo lo de la Jetson que pide sudo. Nada se mueve. `slicer/receive_marker0.py` no cambia: `run(host=…)` ya existe.

## Funciones y clases

`linux/guardian.py` (nuevo):
- `CUENTA = "navagente"`; `CODIGO_NEGADO = 126`; `CODIGO_TOPE = 124`; `CODIGO_ERROR = 125`.
- `@dataclass(frozen=True) class Orden: verbo: str; argv: list[str]; cwd: str; tope_s: float; pesada: bool; entrada: bool`: lo que se va a ejecutar. `entrada` dice si el hijo recibe la entrada estándar.
- `class Negado(Exception)`: lleva el motivo.
- `MODULOS: dict[str, float]` y `CONSULTAS: dict[str, list[str]]`: la lista blanca y sus topes.
- `partir(original: str) -> list[str]`: `shlex.split`. Niega caracteres de control, `;|&$\`<>` y órdenes de más de 4096 caracteres.
- `dentro_de(arg: str, raices: list[Path]) -> Path`: resuelve la ruta y niega si cae fuera de las raíces.
- `decidir(argv: list[str], home: Path) -> Orden`: pura. Lanza `Negado`.
- `precondiciones(orden: Orden, home: Path, leer_temp=None, libre_gb=None, pesadas_en_marcha=None) -> None`: disco, temperatura y número de pesadas. Lanza `Negado`.
- `entorno_limpio(home: Path, venv: Path | None) -> dict[str, str]`.
- `limites_hijo() -> None`: el `preexec_fn` con los `setrlimit` y `oom_score_adj`.
- `ejecutar(orden: Orden, registro: "Registro") -> int`: `Popen(start_new_session=True)`, espera con tope y para el grupo.
- `recibir_wip(entrada: BinaryIO, home: Path, max_bytes: int = 50 * 2**20) -> str`: devuelve el sha256. Lanza `Negado` si algún miembro no vale.
- `class Registro: __init__(self, ruta: Path, logger: bool = True); escribir(self, evento: dict) -> None`.
- `main(entorno: dict | None = None) -> int`.

`linux/sonda_privilegios.py`: `comprobar() -> list[dict]`, donde cada elemento es `{nombre, esperado, obtenido, pasa}`, y `main(argv=None) -> int`, que sale con 0 solo si ninguna comprobación encuentra un privilegio.

`linux/perfil_temporal.py` (cambia si P25 queda en (a); si no, la de antes):
- `CLAVES: dict[str, type]`: las únicas que se pueden cambiar, con su tipo: `transforms_port` (int, 18945–18950), `camera.usb_port_linux` (str, con el patrón `RE_BYPATH` de `camera.v4l2`) y `camera.controls.exposure_ms` (float, 0.1–10.0).
- `crear(base: Path, salida: Path, cambios: dict[str, object]) -> Path`: copia el perfil y cambia solo esas claves. Niega una clave fuera de `CLAVES`, una que no exista en el perfil base o un valor del tipo o rango equivocado. No pisa un archivo que ya exista.
- `main(argv=None) -> int`: `--base`, `--salida`, `--puerto N` (atajo de `transforms_port`, para la fase 7) y `--poner CLAVE=VALOR`, que se repite.

`diagnostics/ruido_pose.py` (nuevo, fase 5b). Solo numpy, scipy, cv2 y `vision/`; no abre cámara ni red:
- `serie_pose(rec: dict, nombre: str = "Marker0") -> dict[str, np.ndarray]`: de lo que da `pose_log.load_recording`, los frames con exactamente una detección del id del marker: `t`, `esquinas` (N, 4, 2), `xyz_crudo` (la pose de `vision.pose.estimate_single_pose` sin filtro, con el `K`, el `dist` y el `size_mm` grabados) y `xyz_enviado` (de `sent_M`).
- `refiltrar(t: np.ndarray, xyz: np.ndarray, min_cutoff: float, beta: float) -> np.ndarray`: el `PositionFilter` de `vision/filtering.py` sobre esa serie, con los tiempos que se le den.
- `intervalos(t: np.ndarray) -> dict`: los `dt` en ms (p1, p50, p99, máx), la fracción con `dt` < 2 ms y la fracción con `dt` > 1.5 veces la mediana.
- `ruido_esquinas(esquinas: np.ndarray) -> dict`: la sd en px de cada esquina en x e y, la del centroide, la del lado medio aparente y la correlación entre el lado aparente y la z cruda.
- `bimodalidad(x: np.ndarray, paso: float) -> dict`: el coeficiente de Sarle, el histograma con ese paso, la partición en dos grupos (k-medias en 1D: centros, fracción, separación entre centros dividida por la sd dentro del grupo) y la longitud media de las rachas en cada grupo (si alterna frame a frame o por bloques).
- `espectro(x: np.ndarray, fs: float, n: int = 3) -> dict`: `scipy.signal.welch`, con las `n` frecuencias de más potencia y la fracción de la potencia total de cada una.
- `ruido_imagen(pngs: list[Path], esquinas: list[np.ndarray]) -> dict`: con el marker quieto, la sd temporal por píxel en una zona blanca fuera del marker y en una negra dentro del borde (máscaras desde las esquinas), el contraste medio blanco − negro, el ancho de borde del 10 al 90 % y el cociente de gradiente en las fronteras de bloques de 8 px frente al de dentro (bloqueo de JPEG).
- `analizar(npz: Path, frames_dir: Path | None = None, nombre: str = "Marker0") -> dict`: todo lo anterior para una grabación: sd z enviada, sd z cruda, sd z refiltrada con los tiempos grabados (tiene que dar la enviada) y refiltrada con tiempos uniformes a la fps media, más los bloques de arriba.
- `comparar(resultados: dict[str, dict], referencia: str) -> dict`: cada número frente al de la referencia, en cociente.
- `formato_markdown(comparacion: dict) -> str`.
- `main(argv=None) -> int`: `--input ETIQUETA=RUTA.npz` (se repite), `--frames ETIQUETA=CARPETA` (opcional, por grabación), `--referencia ETIQUETA`, `--output JSON` y `--output-markdown MD`; los dos últimos no se pisan.

`camera/v4l2.py`, solo si hay corrección (J6, P24): `CONTROLES_FIJOS_LINUX: dict[str, int]` (los controles que el perfil no nombra y que la capa deja siempre en un valor, p. ej. `focus_automatic_continuous: 0`) y `CapaLinuxV4L2.aplicar(..., fijos: dict[str, int] | None = None)`, que los escribe después de los del perfil con la misma relectura. Qué controles y qué valores lo dice el P-5b; el plan no los fija de antemano.

`camera/v4l2.py`, `camera/controls.py`, `camera/backend.py`, `transport/igtl.py`, `tracker.py`, `diagnostics/clock_offset.py`, `diagnostics/igtl_rate.py` y `diagnostics/tegrastats_log.py`: las firmas de la versión anterior, sin cambio. Las principales:
- `CamaraV4L2(ruta_puerto, dispositivo)`, `listar_camaras_v4l2`, `resolver_dispositivo`, `ejecutar_v4l2ctl(args, timeout_s=5.0)`, `parsear_list_ctrls`, `exposicion_ms_a_v4l2` y `class CapaLinuxV4L2` con `leer` y `aplicar`.
- `WebcamBackend(…, usb_port_linux=None, *, plataforma=sys.platform, …)`.
- `IgtlSender(port, iface=None)`, con `host`.
- `--igtl-iface` en el tracker.
- `estimate_offset(samples) -> dict`.
- `summarize(arrivals, gap_ms, clock_offset_ms=0.0)`.

`camera/dshow_props.py` (nuevo, fase 7b). Solo ctypes y `camera.uvc`; no importa cv2:
- `IID_IBASE_FILTER`, `IID_IAM_VIDEO_PROC_AMP`, `IID_IAM_CAMERA_CONTROL` y los índices de la vtable (`GetRange`, `Set`, `Get`), de `strmif.h`.
- `CONTROLES_COM: dict[str, tuple[str, int]]`: nombre del perfil → (`"procamp"` o `"camara"`, la propiedad). Los 10 de `controls.CONTROLES_CV2`: `exposure_ms` → (camara, Exposure), `focus` → (camara, Focus), `gain`, `brightness`, `contrast`, `saturation`, `sharpness`, `gamma`, `backlight` → procamp, y `auto_white_balance` → (procamp, WhiteBalance), que se lee y escribe por la bandera auto/manual.
- `@dataclass class Lectura: valor: int; auto: bool`.
- `a_perfil(nombre: str, lectura: Lectura) -> float | bool`: en las unidades del perfil, las mismas que `controls.de_nativos_dshow` (exposición en ms desde log2 de segundos; `auto_white_balance` desde la bandera).
- `a_nativo(nombre: str, valor) -> tuple[int, bool]`: (valor, auto) para `Set`, con `controls.exposicion_ms_a_dshow`; todo lo demás manual.
- `class Dispositivo(Protocol)`: `get(grupo: str, propiedad: int) -> Lectura`, `set(grupo: str, propiedad: int, valor: int, auto: bool) -> bool`, `close() -> None`.
- `abrir_filtro(puerto: str, listar=None) -> Dispositivo`: el moniker de la única cámara DSHOW de ese puerto (`uvc.listar_camaras_dshow`, el mismo `resolver_indice`), `BindToObject(IBaseFilter)` y `QueryInterface` de las dos interfaces. ValueError si el puerto tiene 0 o más de 1; OSError si COM falla, con el HRESULT. No construye grafo ni abre vídeo.
- `class CapaWindowsCOM` (cumple `controls.CapaAjustes`): `__init__(self, abrir: Callable[[str], Dispositivo] | None = None)`; `leer(self, puerto: str, nombres: list[str]) -> dict[str, float]`; `aplicar(self, puerto: str, controls: dict, *, forzar: bool = False) -> dict`. Mismo contrato que `CapaWindowsDShow`: escribe solo lo que difiere, relee siempre, lanza `controls.AjustesNoAplicados` y devuelve las mismas claves (`indice`, `antes`, `leidos`, `antes_nativos`, `leidos_nativos`, `escritos`, `set_false`, `diferencias`, `forzado`, `segundos`), para que `backend.py` no cambie.

`camera/controls.py`: `capa_para_plataforma(plataforma)` igual de firma; en `win32` devuelve `dshow_props.CapaWindowsCOM()`.

`diagnostics/probe_camera.py`: `leer_controles(puerto, capa=None)` y `fijar(puerto, controls, capa=None, forzar=False)` sin cambio de firma; nuevo `capa_por_nombre(nombre: str) -> CapaAjustes` (`"cv2"` o `"com"`) y `comparar_capas(puerto: str) -> dict` (lee los 10 por las dos y devuelve `{"cv2", "com", "diferencias"}`). CLI: `--capa {cv2,com}` y `--comparar-capas`.

`diagnostics/igtl_rate.py`: `listen(..., idle_s: float = NO_DATA_S, ...)`, que sustituye a `NO_DATA_S` dentro del bucle y en el mensaje; `--idle-s` (positivo) en `listen`. `bench` no la pasa: sigue en 5 s.

`linux/perfil_temporal.py`: `CLAVES` gana `camera.usb_port_windows` (str, con la forma `PCIROOT(…)#…`, la que da `uvc.datos_puerto`).

`gui/recipes.py` (cambia respecto de la versión anterior: pasa por el guardián):
- `SSH_OPCIONES: list[str]`: `-T`, `-o BatchMode=yes`, `-o IdentitiesOnly=yes`, `-o ConnectTimeout=10`, `-o ServerAliveInterval=5` y `-o ServerAliveCountMax=3`.
- `cargar_jetson(ruta: Path) -> dict`: valida el alias, el árbol (`repo` o `wip`) y la interfaz.
- `receta_tracker_jetson(ruta_cfg: str, jetson: dict) -> Receta`: `ssh <opciones> nav-jetson py repo tracker --config profiles/tracker_config_gs1.yaml --no-window --stop-stdin --igtl-iface <iface>`, con `stop_stdin=True`. Ya no hay `cd` ni ruta de python: los pone el guardián.

## Fases

Reglas para todas:
- Lo que se hace por `nav-jetson` lo puede correr un agente desde la fase 3, con la barrera probada y las reglas de `settings.json` aplicadas por el autor.
- Lo que abre una cámara o necesita Slicer va como protocolo en vivo con el autor, con los comandos de PowerShell, de la Jetson y de Slicer juntos y en orden (regla del autor, 2026-10-25); quién teclea lo que abre la cámara lo dice P19.
- Cada corrida lleva tope (principio 9). Las salidas vuelven con `traer` a `Claude outputs/fases/007/` (fuera de git).
- La caja de luz va al máximo (CONTEXT §4.20) y se usa el Marker0 de 80 mm (B55). Ollama sigue como esté, salvo en la fase 7 (P15). MAXN_SUPER tal cual, sin `jetson_clocks` (P17).
- En cada fase, en el PC: la suite, el replay y `gui.panel --selftest` sin cambio.

### Fase 1 · El escaneo de la Jetson, solo lectura (ligera)

- **Entrega:** `linux/escanear_jetson.sh`, `linux/escanear.ps1`, `test_escaneo_jetson.py` y el principio de `linux/README.md`. El test comprueba que el script:
  - es ASCII, con LF y sin `sudo`, `su`, `apt`, `dpkg -i`, `rm`, `tee`, `>` hacia un archivo, `systemctl` con verbos que cambian algo, `nvpmodel -m`, `jetson_clocks` ni `--set-ctrl`;
  - lleva un `timeout` en cada orden.
- **Protocolo P-1 (el autor, con su cuenta y el alias `yahboom`, las cámaras ya en la Jetson):** `escanear.ps1 -Alias yahboom -Salida "Claude outputs/fases/007/escaneo/antes.txt" -TopeS 180`. Si `nvpmodel -q` necesita root, el autor añade aparte la salida de `sudo nvpmodel -q`.
- **Criterio:**
  1. El escaneo termina en ≤ 180 s con sus 12 secciones (sistema, Python, CPU y GPU, memoria, disco, USB, V4L2, red, servicios, energía, temperatura y la cuenta) y ninguna orden cortada por tope sin explicar.
  2. `find` al final sale vacío: no escribió nada.
  3. Se reportan:
     - Ubuntu, L4T y JetPack; el Python del sistema y su glibc; `tarfile.data_filter` sí o no; uv o conda sí o no.
     - Núcleos y gobernador; la RAM total y libre; el disco libre.
     - Las dos cámaras en `by-path` con su ruta, distinguibles por puerto.
     - Si hay `v4l2-ctl`. Si lo hay: que el modo 1280×960 MJPG 90 fps aparece y los 11 controles del perfil, con `focus` en 500 (gs1) y 332 (gs2).
     - Los nombres de interfaz y las IPs de LAN y Tailscale, y si hay un segundo puerto Ethernet o Wi-Fi para el cable directo.
     - Si `ufw` está activo y los puertos que escuchan; si 18944 está libre.
     - Los servicios que corren y la memoria que usa Ollama.
     - `nvpmodel -q`, las temperaturas en reposo, `ssh -V` y los grupos de la cuenta del autor.
- **Al cerrar:** la dirección abre la pregunta del método de Python 3.11, con el número libre siguiente y los datos del escaneo, y, si falta `v4l2-ctl`, le pide al autor instalar `v4l-utils` (P12). La fase 2 no la necesita; la fase 3 sí.
- **Cadena:** no se toca.

### Fase 2 · La barrera de seguridad para los agentes (pesada)

- **Entrega:** `linux/guardian.py`, `linux/sonda_privilegios.py`, `linux/__init__.py`, `instalar_guardian.sh`, `desinstalar_guardian.sh`, `probar_barrera.ps1`, `test_guardian.py`, `test_sonda_privilegios.py` y la parte de la barrera en `linux/README.md`. En el reporte, los textos de § «Lo que el autor aplica», con las subredes y los nombres sacados del escaneo.
- **En la suite del PC** (`test_guardian.py`), sin Jetson:
  - `decidir` da la `Orden` esperada para cada verbo permitido y lanza `Negado` para cada caso prohibido de la lista (al menos uno por cada línea de § «Lo prohibido»).
  - `partir` niega los metacaracteres; `dentro_de` niega `..`, las rutas absolutas fuera y los enlaces.
  - `recibir_wip` niega los `tar` fabricados con `../`, una ruta absoluta, un enlace, un `.nrrd`, un `.dcm`, un archivo fuera de `codigo/` y uno de más de 50 MB, y en ninguno extrae nada.
  - `entorno_limpio` no lleva `LD_*` ni `PYTHONPATH`.
  - Las de tope y grupo de procesos se saltan en Windows («solo Linux») y corren en la Jetson en la fase 4.
- **Protocolo P-2 (el autor):**
  - a) Copia `codigo/linux/` a `/tmp/nav-instalar/` con su cuenta.
  - b) `sudo bash instalar_guardian.sh --simular …` y lo lee.
  - c) Lo corre de verdad, con una sesión suya abierta aparte.
  - d) Aplica `~/.ssh/config` y la clave en el PC.
  - e) Corre `probar_barrera.ps1`.
  - f) Repite el escaneo como `despues.txt`.
  - g) El simulacro de corte: aparta la clave, comprueba que `ssh nav-jetson ayuda` da «Permission denied», la devuelve y comprueba que vuelve a responder.
- **Los casos de `probar_barrera.ps1`:**
  - **Negados, con 126:**
    1. `ssh nav-jetson` sin orden.
    2. `sudo true`.
    3. `apt-get install x`.
    4. `reboot`.
    5. `systemctl stop ollama`.
    6. `nvpmodel -m 0`.
    7. `jetson_clocks`.
    8. `bash -c id`.
    9. `py wip os`.
    10. `py wip tracker --record /etc/x`.
    11. `traer ../../etc/passwd`.
    12. `info "red; id"`.
    13. `docker ps`.
    14. `ollama list`.
    15. `crontab -l`.
    16. `git push`.
    17–20. Cuatro `tar` malos por `wip recibir`, sin que cambie `wip estado`.
  - **Negados por `sshd`:**
    21. `ssh -L 9999:localhost:22`, y el puerto local no abre.
    22. `ssh -t`, sin pty.
    23. `sftp`, que no conecta.
  - **Tope:** 24. `prueba-tope` sale con 124 en ≤ 4 s y `procesos` no deja nada.
  - **Corte:** 25. Un `prueba-tope` con el cliente matado a los 1 s, y después `procesos` vacío.
  - **Permitidos, con 0:** 26–30. `ayuda`, `info sistema`, `info red`, `procesos` y `registro 50`.
- **Criterio:**
  1. Los 30 casos dan lo esperado: 30 de 30.
  2. El registro tiene una línea por intento, en `guardian.jsonl` y en `journalctl -t nav-guardian`, y las dos cuentas coinciden.
  3. La sonda, lanzada desde un `python3 -I` como la cuenta, no encuentra ningún privilegio en sus comprobaciones (0 de K; K sale del código, se espera ≥ 15). Esta fase no la puede lanzar por `py` porque aún no hay venv. Por eso la primera corrida la hace el autor con `sudo -u navagente python3 -I sonda_privilegios.py`, y la fase 3 la repite por `py`.
  4. Entre `antes.txt` y `despues.txt` cambian solo la cuenta nueva, el drop-in, la clave, el guardián, `cron.deny` y `at.deny`, más lo volátil (hora, `uptime`, temperatura y memoria libre). Mismos servicios, mismo `nvpmodel` y mismos puertos.
  5. El `sshd -T` de la cuenta del autor queda igual antes y después.
  6. El simulacro de corte funciona en los dos sentidos.
  7. En el PC: la suite, el replay y el selftest, sin cambio en lo de antes.

  Hasta que se cumpla todo esto, ningún agente usa `nav-jetson`. El autor aplica entonces las reglas de `settings.json` y la dirección, las de los agentes.
- **Cadena:** no se toca.

### Fase 3 · El entorno en la Jetson (ligera)

- **Entrega:** `requirements-jetson.txt`, `linux/instalar_entorno.sh` (con el método que haya elegido el autor) y `linux/enviar_wip.ps1`.
- **Lo que hace el agente por `nav-jetson`:**
  - `repo clonar` y `repo estado`.
  - `enviar_wip.ps1`.
  - `entorno instalar --gtsam`, con su tiempo y su disco.
  - `py wip linux.sonda_privilegios`, ahora por `py`.
  - `suite wip -q`, para hacer inventario de lo que falla en Linux.
- **En vivo con el autor:** `camara rafaga <gs1> 900` y `camara rafaga <gs2> 900`, que dan los fps de la cámara sola.
- **Criterio:**
  1. El venv tiene Python 3.11.x, cv2 4.11.0.86 con `cv2.aruco.ArucoDetector`, pyigtl 0.3.1 y scipy.
  2. Se anota si `gtsam` instala (sí o no, y su versión), los MB del entorno y el disco libre que queda.
  3. El clon no tiene `herramientas/` ni `documentos/`, y `git count-objects -v` (por `repo estado`) dice cuánto ocupa.
  4. El sha256 de `enviar_wip` coincide en los dos lados.
  5. La sonda por `py` da 0 privilegios.
  6. El inventario de la suite: cuántas pasan, fallan y se saltan, con la lista de fallos.
  7. Las ráfagas dan los fps de cada cámara: se esperan ≥ 85.

  Si algo de esto no se obtiene, la fase lo dice y para.
- **Cadena:** no se toca.

### Fase 4 · La suite corre en Linux (ligera)

- **Entrega y criterio:** los de la antigua fase 2.
  - `skipif(sys.platform != "win32")` en las pruebas que solo valen en Windows, cada una con su motivo, y el fixture B34 preparado para Linux.
  - En el PC: las de siempre más las nuevas, todas en verde, ninguna saltada en Windows salvo las de guardián marcadas «solo Linux».
  - En la Jetson (`suite wip`): 0 fallos, con N pasadas y M saltadas. Las pruebas de tope y grupo de procesos de `test_guardian.py` pasan allí.
  - El replay de gs1 y gs2 en la Jetson, con la tolerancia de hoy (P14: 1e-9 mm, 1e-9° y 1e-6 px). Se esperan 0.0 mm, 0.0° y 0.0 px. Si da otra cosa, se mide la diferencia máxima, se dice y decide el autor.
- **Cómo se mide:** lo corre el agente (`suite` en la Jetson; la del PC, como siempre), cada una con su tiempo.
- **Cadena:** no se toca código de la cadena. El replay en ARM es la primera prueba de que la aritmética da lo mismo.

### Fase 5 · La capa V4L2 y cada cámara en la Jetson (pesada)

- **Entrega:** la de la antigua fase 3. `camera/v4l2.py` con pruebas sobre las salidas reales del escaneo, `controls.capa_para_plataforma("linux")`, `WebcamBackend` en Linux, `usb_port_linux` en los dos perfiles y el fixture B34 que niega también `camera.v4l2`.
- **Protocolo P-5 (en vivo, en la Jetson y sin la red):** el tracker de cada cámara con `py wip diagnostics.igtl_rate listen --host 127.0.0.1` como cliente, en la misma Jetson. Para cada cámara, cuatro corridas:
  - a) Sin ventana, 60 s, Marker0 quieto, con `--record ~/nav-salidas/…` y `--timing`.
  - b) Con ventana, 60 s. Hace falta un escritorio en la Jetson; si el autor no lo usa, se anota «sin medir» y no bloquea.
  - c) Con el perfil de la otra cámara en ese puerto: tiene que parar por la marca.
  - d) Sin cliente: tiene que abortar con código 3 sin abrir la cámara.

  Tras cada corrida, `info camara-libre` e `info puerto-libre 18944`.
- **Criterio:** el de la antigua fase 3.
  1. Cada cámara abre por su ruta by-path y comprueba su marca. Los ajustes coinciden con el perfil y el frame es de 1280×960.
  2. La c) para por la marca y la d) sale con código 3.
  3. Los fps de cámara y de bucle, la sd z en reposo frente a 0.030–0.043 mm y el % de frames con pose.
  4. La cámara y el 18944 libres en todas las corridas.
  5. En el PC, el tracker de Windows abre gs1 como hoy: corrida corta con Slicer, de 64 a 67 Hz.

  Con estos números la dirección le propone al autor confirmar los mínimos de P13 antes de la fase 6.
- **Cadena:** `camera/` cambia solo en la rama Linux. Lo comprueban la prueba de que en Windows `open()` hace las mismas llamadas a cv2, el replay en los dos sistemas y la corrida con Slicer en el PC.

### Fase 5b · El ruido de gs1 por V4L2 (B77) (pesada)

Pesada porque puede tocar `camera/` (la cadena del principio 6). Si cierra solo con el diagnóstico, no toca la cadena. Primero se diagnostica y solo después, si hay causa clara, se corrige (P23).

- **Parte A · Sin cámara (el agente).** Entrega `diagnostics/ruido_pose.py`, `test_ruido_pose.py` y, si P25 queda en (a), `linux/perfil_temporal.py` con su prueba. Corre `ruido_pose` en el PC sobre `p5_gs1_a`, `p5_gs2_a` y `p5_pc_gs1_a` (referencia: `p5_pc_gs1_a`; los saltos de esa corrida perturbada se cuentan aparte, como en el P-5). Lo que tiene que decir, por grabación:
  - la sd z enviada, cruda y refiltrada (con los tiempos grabados y con tiempos uniformes);
  - los `dt` (p1, p50, p99, < 2 ms);
  - la sd de las esquinas, la del lado aparente y su correlación con z;
  - la bimodalidad de la z cruda y del lado aparente, con la longitud de las rachas;
  - las tres frecuencias de más potencia de la z cruda.

  Con eso, una lectura en tres casos, que decide qué se mira en vivo:
  - (i) **El filtro:** la z cruda de gs1 en la Jetson tiene la misma sd que la del PC y lo que sube es la filtrada, con `dt` en ráfaga. La causa está en código compartido (`grabber`, el 1-Euro): se para la corrección por P24.
  - (ii) **La imagen, de escala:** la z cruda ya es el doble, el lado aparente lleva el ruido y la correlación con z es alta. Hay que ver la imagen (P-5b).
  - (iii) **Otra cosa:** se dice con los números y el P-5b se corre igual.
- **Parte B · Protocolo P-5b (en vivo, el autor; caja de luz al máximo, Marker0 de 80 mm en la misma posición que en el P-5 para gs1, ~361 mm, y sin mover el soporte entre la Jetson y el PC).** Lo que abre una cámara lo teclea el autor (P19); los `info` y los `traer` los puede correr el agente. Cada corrida: 60 s sin ventana, con su listener (`igtl_rate listen`) lanzado antes como en el P-5, y `--record`, `--timing` y `--save-frames <carpeta> --frames-every 600` (unos 9 PNG por corrida), todo bajo `~/nav-salidas/b77/` en la Jetson y bajo `Claude outputs/fases/007/b77/` en el PC.
  - 0. Antes y después de la sesión: `ssh nav-jetson info v4l2 <gs1>` e `info v4l2 <gs2>` a un archivo, y en el PC `python -m diagnostics.probe_camera --leer --puerto <usb_port_windows> --salida … --timeout 60` de cada cámara cuando está en el PC. Son la lista completa de controles de cada lado (hallazgo 12).
  - J1 y J2: gs1 en la Jetson, dos corridas seguidas. Repetibilidad: ¿sigue en ~0.074?
  - J3: gs2 en la Jetson, en su posición del P-5 (~326 mm).
  - J4 (solo si P25 queda en (a)): gs1 en el puerto del hub de gs2 (se intercambian los dos cables; gs2 queda en el de gs1, sin abrirse), con un perfil temporal hecho con `py wip linux.perfil_temporal --base profiles/tracker_config_gs1.yaml --poner camera.usb_port_linux=<by-path de 2.2> --salida ~/nav-salidas/perfiles/gs1_puerto22.yaml`. Una sola variable: el puerto. La marca de focus sigue protegiendo de la cámara equivocada.
  - W1: gs1 en el PC (su puerto de Windows), con `igtl_rate listen` local en vez de Slicer, para no tener la perturbación de la corrida extra del P-5.
  - W2: gs2 en el PC, igual, en su posición (~326 mm). Responde al hallazgo 14.
  - Tras cada corrida en la Jetson, `info camara-libre` e `info puerto-libre 18944`.
  - El agente trae los `.npz`, los `.json` y los PNG con `traer` (uno por archivo, con `Start-Process -RedirectStandardOutput`, como en el P-5) y corre `ruido_pose` sobre las grabaciones de la sesión, con W1 de referencia y los PNG de cada una.
- **La puerta.** Con A y B, una causa es clara si cumple las dos cosas:
  - una sola variable (un control, el puerto, la exposición) separa las corridas de ruido alto de las de ruido normal;
  - y explica la diferencia de `ruido_imagen` o del lado aparente entre J1–J2 y W1.

  Si no hay una causa así, la fase cierra aquí con los números (P23) y el autor decide.
- **Parte C · La corrección, solo si la puerta la da y P24 la deja dentro de la fase.**
  - Si es un control que el perfil no nombra: `CONTROLES_FIJOS_LINUX` en `camera/v4l2.py` (J6), con sus pruebas sobre las salidas del escaneo.
  - Si es la exposición: una sesión más con un perfil temporal de `exposure_ms` 0.9 (la cámara da 9) para ver la sensibilidad, y el autor decide con ese número si se cambia el perfil.
  - Si es el puerto o el hub: no hay corrección de código. Se dice qué puerto usar y lo decide el autor.
  - Si es del filtro, del hilo de captura o de la cámara (el sensor, el JPEG): no se corrige en esta fase.

  La verificación de una corrección es una segunda sesión corta, P-5b2: J5 y J6, gs1 en la Jetson, dos corridas, con la WIP corregida (y los `info v4l2` de antes y después).
- **Criterio:**
  1. A: los números de las tres grabaciones del P-5 en `b77/analisis_p5.md`, y la lectura (i), (ii) o (iii) con los números que la sostienen. `refiltrar` con los tiempos grabados reproduce `sent_M` (≤ 1e-9 mm en Windows, ≤ 1e-3 mm en Linux).
  2. B: la sd z de J1, J2, J3, W1, W2 (y J4) con su % con pose y su fps de bucle (≥ 60, P13; se esperan ~87), y `ruido_imagen` de cada una frente a W1. La lista de controles que difieren entre la Jetson y el PC, o entre gs1 y gs2, o «ninguno».
  3. Una causa, con la variable y su número, o «sin causa clara» con lo que se descartó.
  4. Si hubo corrección: gs1 por V4L2 en reposo da una sd z de 0.030–0.050 mm en J5 y en J6; gs2 por V4L2 no sube de 0.050; la cámara a ≥ 85 fps.
  5. Si no la hubo: la fase cierra con los números de 1–3, B77 queda al día con ellos y el autor decide (P23).
  6. En el PC, siempre: la suite, el replay en 0.0 y `gui.panel --selftest` sin cambio; en la Jetson, `suite wip` con 0 fallos.
- **Cadena:** las partes A y B no la tocan: `ruido_pose` y `perfil_temporal` no los importa el tracker, y el P-5b usa el código de la fase 5 sin cambios. Si hay parte C, cambia solo `camera/v4l2.py`, que solo carga la rama Linux. Lo comprueban:
  - la prueba de que en Windows `open()` hace las mismas llamadas a cv2 (con y sin `usb_port_linux`);
  - el replay en el PC (0.0 mm / 0.0° / 0.0 px) y en la Jetson (P22);
  - una corrida de gs1 en el PC con Slicer, de 64 a 68 Hz, como el criterio 5 de la fase 5.

  Nombres, puerto, mensajes y jerarquía de OpenIGTLink no cambian.

### Fase 6 · Slicer en el PC recibe de la Jetson, por las tres redes (pesada)

- **Entrega:** `IgtlSender(port, iface)`, `tracker --igtl-iface`, `diagnostics/clock_offset.py`, `igtl_rate listen --clock-offset-ms` y sus pruebas con el servidor falso (B34).
- **Antes, el autor:** configura el cable directo, con una IP fija en cada lado (`/30` privada, p. ej. 10.77.0.1 el PC y 10.77.0.2 la Jetson; en la Jetson con `nmcli` y sudo, en el PC desde la configuración del adaptador). Si `ufw` está activo, abre 18944/tcp y el puerto UDP del eco en las tres interfaces. Si la Jetson tiene un solo puerto Ethernet, la LAN se mide por Wi-Fi o se alternan las redes; lo dice el escaneo. Los alias `nav-jetson-lan`, `-cable` y `-ts` del `~/.ssh/config` apuntan a cada una.
- **Protocolo P-6 (PC + Jetson + Slicer),** con gs1, por cada red (LAN, cable y Tailscale):
  - a) `py repo diagnostics.clock_offset serve` en la Jetson y `measure` en el PC, antes y después.
  - b) Slicer conectado a `<IP>:18944` (`receive_marker0.py`, `run(seconds=30, host="<IP>")`) y luego el tracker con `--igtl-iface <interfaz>`. Se miden los Hz en Slicer y se comprueba que no aparece `DodecaedroToTracker`.
  - c) `igtl_rate listen --host <IP> --seconds 30 --clock-offset-ms <a>` en el PC, en lugar de Slicer: latencia p50 y p95.
  - d) Una vez, la línea base: el tracker en el PC con el listener local.
  - e) El tracker con una interfaz que no existe: tiene que abortar con código 2 sin abrir la cámara.
  - f) Al parar, la cámara y el 18944 libres en la Jetson.
- **Criterio:**
  1. Slicer recibe `Marker0ToTracker` desde la Jetson por las tres redes, con sus Hz.
  2. La latencia p50 y p95 con su incertidumbre (±RTT mín/2), frente a la línea base.
  3. La e) y la f) cumplen.
  4. Se compara con los mínimos de P13 (≥ 55 Hz por LAN; latencia añadida p95 ≤ 10 ms por LAN y ≤ 30 ms por Tailscale; para el cable se reporta frente al de la LAN) y se dice si se llega o no.
  5. En el PC, sin `--igtl-iface`, el log dice `127.0.0.1:18944` y una corrida con Slicer da los Hz de siempre.
- **Cadena:** cambia la dirección en la que escucha el servidor, solo con la opción. Nombres, puerto, mensajes y jerarquía no cambian. Se verifica en vivo con Slicer en las dos máquinas (ADR J2).

### Fase 7 · Las dos cámaras a la vez en la Jetson (ligera)

- **Entrega:** `diagnostics/tegrastats_log.py` con su prueba sobre el log real del escaneo, `linux/perfil_temporal.py` con su prueba (si la fase 5b ya lo hizo, P25, aquí solo se usa con `--puerto`), y el protocolo P-7.
- **Protocolo P-7:**
  - `py wip linux.perfil_temporal --base profiles/tracker_config_gs2.yaml --puerto 18946 --salida ~/nav-salidas/perfiles/gs2_18946.yaml` (P18).
  - gs1 y gs2 sin ventana en dos procesos, cada uno con su listener local, y `medir tegrastats`.
  - 60 s de calentamiento y después 300 s por condición.
  - Dos condiciones (P15): Ollama parado, que el autor para con `sudo systemctl stop ollama`, y Ollama con el modelo que el autor diga cargado. Al terminar, el autor lo deja como estaba.
  - Se corta antes si alguna temperatura llega a 90 °C (el guardián no deja arrancar por encima de 85 °C).
- **Criterio:** en las dos condiciones se reportan:
  - los fps de cámara y de bucle de cada una, frente a ≥ 45 fps (P13);
  - la CPU media y máxima por núcleo, y la RAM p50 y máxima;
  - la temperatura máxima, y si se cortó por temperatura.

  Al parar, las dos cámaras y los dos puertos quedan libres.
- **Cadena:** no cambia.
- **Al día (2026-11-04, P28 y P29):** la fase cierra con la condición A sola (no hay B: el proyecto no usa Ollama). El P-7w del PC no es de esta fase: pasa a la 7b. Si P31 queda en (a), `desarrollo` la cierra con `/cerrar-fase` ya, con los números del P-7 en la Jetson (cámara 86.2 / 86.2 fps, bucle 63.2 / 63.2, CPU 95.5 % de media, GPU 0 %, 69.9 °C máx.), y el autor hace su commit antes de empezar la 7b.

### Fase 7b · Las dos cámaras a la vez en Windows (pesada)

Añadida el 2026-11-04 por P29. Pesada (ADR-022): toca cómo se comprueba la marca y se aplican los ajustes de toda cámara en Windows, que es la cadena del principio 6. En dos tiempos: `desarrollo` implementa la parte A y la B sin cámara; las sesiones en vivo son del autor. Tres partes, en orden; cada una cierra con su commit.

**Parte A · El diagnóstico (en vivo, ~15 min).**
- **Entrega, sin cámara:** `camera/dshow_props.py` solo de lectura (`abrir_filtro`, `CapaWindowsCOM.leer`), `probe_camera --capa` y `--comparar-capas`, `igtl_rate listen --idle-s`, sus pruebas, y el protocolo `Claude outputs/fases/007/p7b.md` (parte A). Hasta la parte B, el tracker sigue con `CapaWindowsDShow`: nada de la cadena cambia en esta parte.
- **Protocolo P-7b-A** (montaje del P-7w: gs1 en `…USB(3)`, gs2 en `…USB(4)`, caja de luz al máximo; todo con tope y `--salida` en `Claude outputs/fases/007/p7b/`). Para tener una cámara transmitiendo se usa el tracker de siempre, sin ventana, con su listener (`--idle-s 60`), y se anota su fps de cámara antes, durante y después de cada paso (hallazgo 17):
  - A0. Cada cámara sola: `probe_camera --puerto <p> --comparar-capas`. Lo esperado: 0 diferencias en los 10 controles de cada una (si hay alguna, la vía COM no está lista y se para aquí).
  - A1. gs2 transmitiendo; `probe_camera --puerto <gs1> --leer --capa cv2` con `OPENCV_VIDEOIO_DEBUG=1` en esa consola. Lo esperado: reproduce el fallo, y el registro de OpenCV dice en qué paso (el formato, el grafo o el `Run`).
  - A2. gs2 transmitiendo; `probe_camera --puerto <gs1> --leer --capa com`. Si lee la marca (focus 500) y los 10 controles, la vía de J7 vale. Es la medida que decide.
  - A3. gs2 transmitiendo a poco ancho de banda (`probe_camera --source <gs2> --backend MSMF --modos 640x480:MJPG --fps 30 --segundos 60 --controles no`) y, mientras, A1 otra vez. Si así abre, la causa es el ancho de banda (H1).
  - A4. Lo mismo con los papeles cambiados (gs1 transmitiendo, gs2 leída), A1 y A2.
  - A5, solo si P32 queda en (a): gs2 en un puerto trasero (otro controlador), sin tocar los perfiles, y A1 otra vez. Al acabar, el cable vuelve a su puerto.
- **Criterio de la parte A:** una tabla con A0–A4 (y A5 si se hace): abre o no, el mensaje, el fps de la cámara que transmite en cada paso, y una lectura de la causa (H1, H2, H3 u otra) con lo que la apoya. Y una decisión: si A0 da 0 diferencias y A2 lee, la parte B sigue con J7; si no, se aplica lo que diga P30 sin preguntar otra vez.

**Parte B · El arreglo (sin cámara y luego en vivo, ~15 min).**
- **Entrega:** `CapaWindowsCOM.aplicar`, `capa_para_plataforma("win32")` → `CapaWindowsCOM`, `perfil_temporal` con `camera.usb_port_windows`, las pruebas al día y `p7w.md` y `dos_camaras.ps1` al día (`--idle-s 60`, sin bucle). Linux no cambia: `capa_para_plataforma("linux")` sigue dando `CapaLinuxV4L2` y `camera/v4l2.py` no se toca.
- **Criterio, sin cámara:** la suite del PC en verde con su tiempo; el replay de gs1 y gs2 a 0.0 mm / 0.0° / 0.0 px y `explain_pose` sin cambio; `gui.panel --selftest` bien; en la Jetson, `suite wip` con 0 fallos.
- **Criterio, en vivo (P-7b-B):**
  1. Cada cámara sola, `probe_camera --comparar-capas`: 0 diferencias en 10 de 10, después del cambio.
  2. La escritura por COM: con una cámara sola, `probe_camera --puerto <p> --capa com --fijar gain=12` y relectura por `--capa cv2`: 12; y de vuelta a 11, también leído por las dos.
  3. La marca cruzada: un perfil temporal de gs1 con el puerto de gs2 (`perfil_temporal --poner camera.usb_port_windows=…`); el tracker para con «declarado 500, leido 332», código 1, sin escribir ajustes y sin abrir el vídeo.
  4. Una cámara sola en el PC con Slicer: `Marca comprobada (focus=500)`, `Ajustes aplicados … (escritos: ninguno)` con los mismos valores que en `corta_gs1_tracker.txt`, y 64–68 Hz en Slicer en 30 s, como en el P-6 (65.7).
  5. Las dos a la vez, en los dos órdenes (gs1 → gs2 y gs2 → gs1), 30 s cada uno con `dos_camaras.ps1`: las dos con la marca comprobada, los ajustes aplicados y fps de cámara ≥ 45 (P13), código 0, y todo libre al parar.
- **Cadena (principio 6):** cambia solo cómo se leen y escriben los controles antes del vídeo; el índice, el vídeo por MSMF, el modo, la calibración, la detección, el filtro y lo que se envía no cambian. Se verifica con la suite, el replay, el selftest, los criterios 1–4 y la `suite wip` de la Jetson.

**Parte C · El P-7w largo (en vivo, ~20 min).**
- **Entrega:** el P-7w de `p7w.md` tal como está (reposo de 60 s, gs1 y gs2 450 s, `typeperf` y `nvidia-smi` 390 s, resúmenes en 60–360 s), con los listeners de `--idle-s 60`; y la tabla Jetson frente a PC en el reporte.
- **Criterio:** por cámara, el fps de cámara y de bucle frente a ≥ 45 (P13); la CPU media y máxima por hilo y total, la RAM p50 y mínima disponible, la GPU (uso, decodificador, memoria) y el reposo de antes restado o al lado; los mensajes por segundo de cada listener; todo libre al parar. Junto a la columna de la Jetson (P-7, condición A). Con eso el autor decide dónde corre el tracker (P4, P28).

Si la parte A acaba en P30 (b) o (c), la parte B cambia de entrega según esa respuesta y la parte C no cambia.

### Fase 8 · El panel del PC lanza y para el tracker de la Jetson (pesada)

- **Entrega:** `profiles/jetson.yaml`, `recipes.cargar_jetson`, `recipes.receta_tracker_jetson` y el botón «Arrancar tracker en la Jetson» (solo si existe `jetson.yaml`), con sus pruebas: el argv exacto, `BatchMode`, rutas con `/`, `stop_stdin=True` y que la orden remota es un verbo del guardián (`decidir` la acepta).
- **Protocolo P-8 (PC + Slicer + Jetson):**
  - a) «Arrancar tracker en la Jetson», con Slicer conectado a la IP.
  - b) «Detener tracker».
  - c) Arrancar y cortar la red 10 s.
  - d) Arrancar sin Slicer.
- **Criterio:**
  1. La a) da los Hz de la fase 6 en esa red.
  2. La b) sale con código 0 dentro de `ESPERA_STDIN_S` (8 s), sin `terminate()`.
  3. En la c), el tracker de la Jetson sale solo en menos de 30 s, y la cámara y el 18944 quedan libres.
  4. La d) sale con código 3 y el panel lo dice.
  5. Cada corrida queda en el registro del guardián.
  6. En el PC, los botones locales hacen lo de siempre.
- **Cadena:** no cambia (el panel compone comandos).

### Fase 9 · Cómo se trabaja con la Jetson y cierre de la meta (ligera)

- **Entrega:**
  - `linux/README.md` completo.
  - `docs/CONTEXT.md`: §3 (la Jetson como máquina del tracker y la cuenta `navagente`); §4, con las trampas nuevas: `pyigtl` cae a loopback, los nombres V4L2, PySide6 sin rueda en 22.04, la tubería binaria de PowerShell 5.1, el `Match` de `sshd_config.d` y las que salgan; y §6.
  - `docs/ARCHITECTURE.md` §3.1, §3.5, §3.7 y §6, y `codigo/readme.md`.
  - `specs/007-jetson/resultados.md` con todos los números frente a los mínimos.
  - En el reporte, el texto propuesto para `CLAUDE.md` §4 («La Jetson», una regla) y §5 (la Jetson en el entorno y los comandos por `nav-jetson`).
  - Lo que va al BACKLOG.
- **Criterio:**
  - Cada número del criterio de cierre del spec está en `resultados.md` con su fuente.
  - El registro del guardián de toda la meta sin un 126 que no esté explicado en un reporte.
  - Ninguna línea pasa de 2 000 caracteres.
  - La suite, el replay y el selftest en el PC sin cambio, y la suite en la Jetson.
  - El autor decide con los números (P4) si el tracker se queda en la Jetson o vuelve al PC.
- **Cadena:** no cambia.

## Lo que va al BACKLOG

Números propuestos; los fija la dirección.

- **B66 · Decodificar MJPEG por hardware en la Jetson** (NVJPG, GStreamer o `jetson-utils`). Entra si en las fases 5 y 7 decodificar se lleva una parte grande del bucle o no se llega a los mínimos. Es optimización y pide otra dependencia. Prioridad media si no se llega, baja si se llega.
- **B67 · Las herramientas de cámara en Linux:** `diagnostics.probe_camera`, `measure_modes`, la calibración y «Verificar IDs» del panel. Esta meta solo lleva el tracker. Prioridad baja mientras se calibre en el PC.
- **B68 · El 18944 abierto en la red sin autenticación:** OpenIGTLink no autentica. En LAN, cualquiera puede conectarse primero y dejar a Slicer fuera. Haría falta solo Tailscale o una regla de cortafuegos. Prioridad media.
- **B69 (cambia) · La barrera del PC es blanda.** Los agentes corren como el usuario de Windows del autor y podrían usar su clave personal o rodear `settings.json` desde Python (hallazgo 7). La cuenta `navagente` acota el daño solo si el acceso es por ella. Con P20 en (a) queda mitigado; si no, la prioridad sube a alta. Haría falta un usuario de Windows aparte para los agentes. Prioridad media.
- **B70 · Cuota de disco real para `navagente`** (cuotas de ext4) en vez del chequeo de 5 GB libres del guardián, que no impide llenar el disco dentro de una sola orden. Prioridad baja.
- **B71 · Lo que escucha en la red de la Jetson** (JupyterLab, Ollama u otros, si el escaneo los ve en 0.0.0.0). Queda porque no es de esta meta y tocarlo pide sudo y al autor. Prioridad según lo que se vea: media si hay algo sin autenticación.
- **Al día en B50:** si el escaneo ve `exposure_dynamic_framerate` en `--list-ctrls`, es la candidata a explicar la bajada de fps con poca luz. Se anota y no se toca.
- **Al día en B53:** con el tracker remoto, la parada mientras espera a Slicer tarda hasta 30 s. Se ve en la fase 8.
- **B23 pasa a Cerrados** al cerrar la meta, con lo que la cerró.
- **De la fase 5b:**
  - **B77** pasa a Cerrados si la parte C deja gs1 en 0.030–0.050 mm en J5 y J6. Si no, queda al día con los números de A y B, la causa o lo descartado, y la prioridad que diga el autor (media si no hay causa; alta si la causa puede dar un resultado equivocado en uso).
  - **B81** pasa a Cerrados si P25 queda en (a): `linux.perfil_temporal` existe.
  - **Nueva, solo si la lectura es (i):** el 1-Euro con `dt` en ráfaga en Linux. La corrección toca `grabber` o el filtro, compartidos con Windows, y pide su ADR. Prioridad media.
  - **Nueva, solo si la imagen apunta a la compresión:** el tamaño del JPEG por frame en Linux no se puede medir con lo que hay (Context7 no confirma `CAP_PROP_CONVERT_RGB` con V4L2 y MJPG; el guardián no tiene un verbo que guarde la ráfaga). Haría falta un modo de `camera.v4l2` o de `camara rafaga` que guarde los JPEG. Prioridad baja; media si la lectura (ii) no tiene otra causa.
  - **Nueva, solo si hace falta el brillo por frame:** `PoseLog` no guarda el brillo medio del marker por frame, que diría si el lado aparente se mueve con la luz. Toca la grabación del tracker. Prioridad baja.

- **De la fase 7b:**
  - **B79** pasa a Cerrados con `igtl_rate listen --idle-s` (parte A).
  - **B88** queda tal cual (baja): con `--idle-s` el listener no se reconecta y el P-7w no la necesita. Se anota «Al día» con eso.
  - **B89** no cambia: no es de esta fase.
  - **Nueva, si la parte A confirma H1:** dos cámaras transmitiendo por el mismo concentrador del PC dejan poco margen de ancho de banda; con J7 la apertura corta ya no lo pide, pero un tercer dispositivo o un modo más pesado podría no caber. Haría falta medir con USBView el reparto por controlador y, si estorba, llevar una cámara a otro controlador (cambia su `usb_port_windows`, ADR-024). Prioridad baja; media si en la parte C alguna cámara queda por debajo de 45 fps.
  - **Nueva, si el hallazgo 17 se confirma** (la cámara que transmite baja de fps cuando la otra intenta abrir): qué la baja y si pasa también con J7. Prioridad media: es una caída de fps en uso.
  - **Nueva:** `CapaWindowsDShow` queda solo para la sonda; si en una meta posterior nada la usa, se archiva. Prioridad baja.

## ADR que se proponen

Números por fijar: el plan sin autorizar de la meta 006 propone ADR-035 a ADR-039.

- **J1 · El tracker corre también en Linux aarch64 (Jetson), con una capa V4L2.**
  - La identidad, en `usb_port_linux` (ruta by-path) del mismo perfil (P11).
  - En Linux el backend es siempre V4L2 y los controles van por `v4l2-ctl` con el mismo formato de `controls` (P12).
  - El entorno, en `requirements-jetson.txt` con las versiones del PC y Python 3.11 por el método que elija el autor tras el escaneo.
  - Windows no cambia.
  - Alternativas: perfiles aparte; cv2 `set/get` por V4L2 o ioctl.
- **J2 · El servidor OpenIGTLink escucha en la interfaz que se le dice** (`--igtl-iface`, solo Linux; por defecto 127.0.0.1 como hoy, P10). Aborta si `pyigtl` cae a loopback. Nombres, puerto, mensajes y jerarquía no cambian (principio 6). La consecuencia: el puerto queda expuesto en esa red (B68).
- **J3 · El panel se queda en el PC y lanza el tracker de la Jetson por SSH, a través del guardián, y lo para por la entrada estándar.** Extiende ADR-029. Confirma P16 con el criterio del autor (estable y reproducible en otras máquinas):
  - En el PC, PySide6 instala por pip.
  - En la Jetson habría que compilarlo (glibc 2.35 frente a 2.39), y eso no se reproduce en otra máquina.
  - El cliente OpenSSH viene con Windows 10/11, Linux y macOS.
  - Lo propio de cada máquina (el alias y la clave) está fuera del repo, y `jetson.yaml` no lleva IP.
  - El escritorio remoto le quitaría CPU al tracker.
  - Al pasar por el guardián, el panel queda acotado y registrado como los agentes.
- **J4 · Los agentes trabajan en la Jetson por una cuenta sin privilegios con orden forzada, un guardián con lista blanca, tope y registro, y lo que pide sudo queda siempre para el autor.**
  - Contenido: § «La barrera».
  - Cambia `CLAUDE.md` §4 y §5 y las reglas de `desarrollo` y `pruebas`; no cambia la constitución (lo cumple el principio 9).
  - Alternativas descartadas: solo patrones de `settings.json` (blandos, hallazgo 7); la orden forzada en `authorized_keys` de la propia cuenta (la cuenta podría editarla, hallazgo 8); un contenedor (complica cámaras y red, y `docker` es root); que el autor corra todo (P8 lo descarta).
- **J6 (solo si hay parte C con un control) · En Linux, la capa V4L2 deja además en un valor fijo los controles que el perfil no nombra**, de una lista cerrada en `camera/v4l2.py` (`CONTROLES_FIJOS_LINUX`), con la misma relectura que los del perfil. El perfil no cambia y Windows tampoco. Alternativas: una clave nueva del perfil (`controls_linux`), que haría falta si el valor cambia de una cámara a otra; escribirlos también por DSHOW en Windows, que cambia la cadena que hoy funciona. Lo decide P24.
- **J7 (fase 7b, si la parte A lo confirma) · En Windows, la marca y los ajustes se leen y se escriben por COM sobre el filtro de captura de DirectShow** (`IAMVideoProcAmp` e `IAMCameraControl`, `camera/dshow_props.py`), sin abrir vídeo, en lugar de la apertura corta de `cv2` por DSHOW. Corrige la parte de Windows de la fase 2b de la meta 002 (la apertura corta antes del vídeo por MSMF): mismo formato de `controls`, mismas unidades, misma relectura y la misma comprobación de la marca antes de escribir nada. La consecuencia: dos trackers abren gs1 y gs2 a la vez en el PC; la sonda guarda la vía de `cv2` para comparar. Alternativas: abrir con un modo ligero por `cv2` (no está documentado que DSHOW lo respete al abrir, Context7); ordenar las aperturas entre procesos (frágil y cambia cómo se lanzan); una cámara en otro controlador USB (un cambio de montaje, no de código, y solo vale si la causa es el ancho de banda); `pygrabber` u otra dependencia (no hace falta: ya hay COM por ctypes en `camera/uvc.py`). No cambia el orden de apertura de las cámaras.
- **J5 (al cerrar) · La meta 007 cierra con los números de la Jetson** y la decisión del autor sobre dónde queda el tracker, como ADR-031 y ADR-033.

## Preguntas abiertas

P6–P29 están contestadas (P19–P21 el 2026-10-29, P22 el 2026-11-02, P23–P27 el 2026-11-03, P28 y P29 el 2026-11-04). Abiertas: P30, P31 y P32, de la fase 7b (al final de esta sección). Las nuevas van también al final de `clarify.md`. La pregunta del método de Python 3.11 no se abre ahora: se abre al cerrar la fase 1, con el escaneo (P6).

- **P19 · Quién teclea lo que abre la cámara en la Jetson** (`camara rafaga` y `py … tracker`):
  - (a) El autor, en la sesión en vivo, con los comandos que le da el protocolo, por el mismo alias y el mismo guardián (recomendada). Mantiene la regla de `desarrollo` y `pruebas` («No abres la cámara, el tracker ni Slicer») y el autor está delante de la cámara y de Slicer de todos modos.
  - (b) Los agentes, por el guardián, en una sesión en vivo con el autor presente, que lo confirma antes. Cambia esa regla de los dos agentes.
- **P20 · La clave personal del autor hacia la Jetson** (alias `yahboom`) y su `sudo` allí:
  - (a) Con frase de paso, sin dejarla cargada en el agente de claves de Windows, y el `sudo` de su cuenta con contraseña (recomendada). Cierra el rodeo del hallazgo 7: aunque un agente intentara usarla, `BatchMode` falla sin la frase.
  - (b) Como esté hoy. Entonces B69 sube a alta.

- **P24 · Hasta dónde corrige la fase 5b** si sale una causa clara:
  - (a) Solo dentro de la rama Linux de `camera/v4l2.py`: un control que el perfil no nombra, fijo para las dos cámaras (J6). Si la causa está en código compartido con Windows (`grabber`, el 1-Euro, `tracker.py`, `vision/`) o pide una clave nueva del perfil, la fase cierra con el diagnóstico y la corrección se replanea con su ADR (recomendada). Mantiene corta la fase y no toca la cadena de Windows, que hoy da 0.032–0.043 mm.
  - (b) También en código compartido, dentro de la fase, con su ADR y la verificación de la cadena en las dos máquinas. Más rápida si la causa es el filtro, pero la fase deja de ser corta y cambia Windows.
- **P25 · Adelantar `linux.perfil_temporal` a la fase 5b**, con `--poner` para el puerto y la exposición:
  - (a) Sí (recomendada). Permite J4 (una sola variable: el puerto del hub) y la prueba de la exposición sin tocar los perfiles del repo. Cierra B81 (el módulo está en la lista del guardián y no existe), y la fase 7 lo usa tal cual. Pide intercambiar los cables de las dos cámaras en la Jetson durante J4.
  - (b) No. J4 y la prueba de la exposición no se hacen, y la exposición y el puerto quedan como hipótesis sin medir. `perfil_temporal` sigue en la fase 7.

- **P30 · Si la parte A descarta la vía COM** (A0 con diferencias, o A2 tampoco lee con la otra cámara transmitiendo):
  - (a) Si A3 o A5 dicen que es el ancho de banda: una cámara pasa a un puerto de otro controlador, con su `usb_port_windows` nuevo en el perfil (ADR-024; los intrínsecos no cambian, son de la cámara), y la parte B solo verifica (recomendada). Sin código en la cadena; la parte C igual.
  - (b) Ordenar las aperturas: un paso previo que comprueba la marca y aplica los ajustes de las dos cámaras antes de que ninguna transmita, y los trackers que esperan a ese paso. Pide su ADR y cambia cómo se lanzan; la fase se alarga.
  - (c) Parar la 7b con el diagnóstico, dejarlo en el BACKLOG con prioridad alta y medir el P-7w con una cámara sola.
- **P31 · Dónde cierra la fase 7:**
  - (a) Ya, con la Jetson (condición A), en su propio commit, y el P-7w pasa a la 7b (recomendada). La fase 7 cumplió su criterio en la Jetson y la 7b es otra máquina y otro arreglo.
  - (b) Junto con la 7b, cuando esté el P-7w, en un solo cierre. Deja la casilla de la 7 abierta varios días.
- **P32 · Un puerto trasero solo para el diagnóstico (A5):**
  - (a) Sí: gs2 a un puerto trasero durante A5, sin tocar los perfiles, y de vuelta al acabar (recomendada). Separa el ancho de banda del concentrador de lo demás en un solo paso.
  - (b) No: los cables no se mueven y la causa se lee solo con A1–A4.

## Títulos de commit

- Fase 7 (cierre, si P31 queda en (a)): «Cierra la fase 7 de la meta 007 con el P-7 en la Jetson»
- Fase 7b, parte A: «Añade la lectura de controles por COM y --idle-s al listener (meta 007, fase 7b)»
- Fase 7b, parte B: «Lee y escribe los ajustes de Windows por COM, sin abrir vídeo (meta 007, fase 7b)»
- Fase 7b, cierre con el P-7w: «Cierra la fase 7b de la meta 007 con las dos cámaras a la vez en el PC»

- Fase 5b: «Diagnostica el ruido de gs1 por V4L2 (meta 007, fase 5b, B77)». Si hay parte C, el de cierre: «Fija los controles de Linux que bajan el ruido de gs1 (meta 007, fase 5b)».
- Fase 1: «Escanea la Jetson en solo lectura (meta 007, fase 1)»
- Fase 2: «Pone la barrera de los agentes en la Jetson (meta 007, fase 2)»
- Fase 3: «Prepara el entorno de la Jetson (meta 007, fase 3)»
- Fase 4: «Hace que la suite corra en Linux (meta 007, fase 4)»
- Fase 5: «Abre las cámaras por V4L2 en la Jetson (meta 007, fase 5)»
- Fase 6: «Deja que Slicer reciba del tracker de la Jetson (meta 007, fase 6)»
- Fase 7: «Mide las dos cámaras a la vez en la Jetson (meta 007, fase 7)»
- Fase 8: «Lanza el tracker de la Jetson desde el panel (meta 007, fase 8)»
- Fase 9: «Documenta el trabajo con la Jetson y cierra la meta 007 (fase 9)»
