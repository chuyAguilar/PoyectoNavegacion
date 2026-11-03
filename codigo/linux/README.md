# codigo/linux — el trabajo con la Jetson Orin Nano

Lo de esta carpeta es para la meta 007 · El tracker en la Jetson Orin Nano, con Slicer en el PC (`specs/007-jetson/`). Se completa fase por fase; al cerrar la meta, en la fase 9 · Cómo se trabaja con la Jetson y cierre de la meta, dirá cómo llega el código, cómo se corren la suite y el tracker, cómo se paran y cómo se corta el acceso.

Hoy hay el escaneo (fase 1 · El escaneo de la Jetson, solo lectura), la barrera de los agentes (fase 2 · La barrera de seguridad para los agentes), el entorno de Python del tracker (fase 3 · El entorno en la Jetson), la suite en Linux (fase 4) y la capa V4L2 de la cámara (fase 5 · La capa V4L2 y cada cámara en la Jetson; abajo). Ningún agente se conecta a la Jetson hasta que la barrera esté instalada por el autor, probada con `probar_barrera.ps1` (30 de 30) y las reglas de `settings.json` aplicadas; entonces los agentes usan solo `ssh nav-jetson <verbo>`.

## Qué hay

- `escanear_jetson.sh`: el escaneo, en bash. Solo lee y lo imprime todo por la salida estándar; en la Jetson no escribe nada. Doce secciones: sistema, Python, CPU y GPU, memoria, disco, USB, V4L2, red, servicios, energía, temperatura y la cuenta. Cada orden lleva `timeout` de 10 s (10 s de `tegrastats`, cortado a propósito), ninguna empieza pasados 90 s y todo queda bajo 120 s. Al final, un `find` del HOME con `-newermt` dice si cambió algo desde el inicio (tiene que salir vacío).
- `escanear.ps1`: lo lanza desde el PC. Manda el script por la entrada estándar de `ssh <alias> timeout -k 5 120 bash --norc --noprofile -s` con `Start-Process` (una tubería de PowerShell 5.1 cambiaría los fines de línea), guarda lo que llega en un archivo que no pisa y espera con tope.
- `guardian.py`: el guardián de la cuenta `navagente` (abajo). `sonda_privilegios.py`: lo que haría un código del agente que intentara salirse. `tars_malos.py`: los tar que `wip recibir` niega, para la suite y `probar_barrera.ps1`.
- `instalar_guardian.sh` y `desinstalar_guardian.sh`: para el autor, con sudo y `--simular`. `probar_barrera.ps1`: los 30 casos de la barrera, desde el PC.
- `enviar_wip.ps1` y `instalar_entorno.sh` (fase 3 · El entorno en la Jetson): la copia sin commit de `codigo/` a la Jetson y el venv del tracker allí (abajo). Las versiones, en `codigo/requirements-jetson.txt`.
- `perfil_temporal.py` (fase 5b · El ruido de gs1 por V4L2, P25; lo usa también la fase 7): copia un perfil del tracker cambiando solo `transforms_port` (18945–18950), `camera.usb_port_linux` (un by-path) o `camera.controls.exposure_ms` (0.1–10 ms), con los comentarios y los fines de línea del base; cualquier otra clave se niega. En la Jetson, `ssh nav-jetson py wip linux.perfil_temporal --base profiles/tracker_config_gs1.yaml --poner CLAVE=VALOR --salida /home/navagente/nav-salidas/perfiles/<nombre>.yaml` (`--puerto N` es el atajo de `transforms_port`). La salida no se pisa. Su prueba: `tests/test_perfil_temporal.py`. El análisis del ruido, `diagnostics/ruido_pose.py`, corre en el PC (abajo, «El ruido en reposo»).
- Las pruebas, en `codigo/tests/`: `test_escaneo_jetson.py` (el escaneo), `test_guardian.py`, `test_sonda_privilegios.py` y `test_probar_barrera.py` (la barrera, sin Jetson: con un `ssh.exe` falso compilado con `Add-Type`), `test_entorno_jetson.py` (el entorno; `enviar_wip.ps1` con otro `ssh.exe` falso que calcula el sha256). Las de tope y grupo de procesos del guardián solo corren en Linux: en la Jetson pasan desde la fase 4 (abajo, «La suite en Linux»).

`.gitattributes` deja los `*.sh` en LF también en el árbol de Windows: `escanear.ps1` manda el archivo tal cual y bash no correría un CRLF. Todo lo que va a la Jetson es ASCII.

## El escaneo (protocolo P-1)

Lo corre el autor, en PowerShell, desde la raíz del repo, con las cámaras ya enchufadas a la Jetson:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File codigo/linux/escanear.ps1 -Alias yahboom -Salida "Claude outputs/fases/007/escaneo/antes.txt" -TopeS 180
```

- Si la clave lleva frase de paso (P20), ssh la pide en la misma consola.
- Sale con 0 si llegaron las 12 secciones y la línea `ESCANEO_FIN`; con 2 si una entrada no vale (no conecta); con 3 si ssh falla o el escaneo queda a medias; con 124 si pasa de `-TopeS` (corta ssh). Lo recibido queda en `-Salida` en todos los casos.
- Si `nvpmodel -q` necesita root, el autor añade aparte la salida de `sudo nvpmodel -q`, en una sesión suya en la Jetson.

La salida trae nombres de máquina, IPs y la lista de procesos: va a `Claude outputs/` (fuera de git) y no se versiona tal cual.

## La barrera de los agentes (fase 2; el diseño, en `specs/007-jetson/plan.md`, § «La barrera»)

Tres capas. **La cuenta** `navagente`, creada por el autor con `instalar_guardian.sh`: sin contraseña, sin sudo, docker, lxd, adm ni disk, solo en `video`; en `cron.deny` y `at.deny`, sin linger; escribe solo en su carpeta, `/tmp` y `/dev/shm`. Es la barrera dura: lo que de verdad impide el daño es que esa cuenta no pueda hacerlo. **La entrada**: `sshd` fuerza el guardián para esa cuenta (`ForceCommand`, sin pty, sin reenvíos, sin contraseña, `ClientAliveInterval 5` × 3) con la clave en `/etc/ssh/authorized_keys/navagente`, de root, con `restrict,from="<subredes>"`. **El PC**: reglas de `settings.json` que dejan a los agentes solo `ssh nav-jetson …` (el texto exacto está en el plan; las aplica el autor): son blandas y sirven contra el error, no contra un rodeo.

### El guardián (`guardian.py`)

Corre con el `/usr/bin/python3 -I` del sistema (3.10 en la Jetson), solo biblioteca estándar, instalado por root en `/usr/local/lib/nav-guardian/guardian`. Lee `SSH_ORIGINAL_COMMAND`, lo parte sin shell (`partir` niega `;|&$\`<>` y los caracteres de control), lo compara con la lista blanca (`decidir`), comprueba las precondiciones y lo ejecuta en su propio grupo de procesos, con entorno limpio (`PATH=/usr/bin:/bin` más el `bin` del venv, sin `LD_*` ni `PYTHONPATH`), límites (archivo ≤ 2 GiB, 512 procesos, sin volcado, `oom_score_adj` 500) y tope. Códigos: **126** negado, **124** cortado por tope (o por desconexión), **125** error del guardián; el resto es el código del hijo.

Los verbos (`ssh nav-jetson ayuda` los lista):

| Verbo | Qué hace | Tope |
|---|---|---|
| `ayuda` | la lista de verbos | — |
| `info <consulta>` | `sistema`, `python`, `cpu`, `memoria`, `disco`, `usb`, `red`, `puertos`, `servicios`, `energia` (`nvpmodel -q`), `temperatura`; `v4l2 <by-path>` (solo `--info --list-formats-ext --list-ctrls-menus`), `camara-libre <by-path>` (`fuser`), `puerto-libre <18944–18950>` | 10 s |
| `repo clonar` | clon parcial y disperso de `origin` en `~/nav/repo`, sin `herramientas/`, `documentos/`, `*.nrrd` ni `*.dcm` (los blobs no se descargan); solo si no existe | 600 s |
| `repo actualizar` / `repo estado` | `git pull --ff-only` / `log -1`, `status --short`, `sparse-checkout list`, `count-objects -vH`. No hay commit ni push | 300 / 30 s |
| `wip recibir` | un tar de `codigo/` por la entrada (≤ 50 MB), validado entero antes de extraer con `filter="data"`: niega `..`, rutas absolutas, enlaces, `*.nrrd`, `*.dcm`, lo que no esté bajo `codigo/` y `historico/`, `.venv/`, `__pycache__/`. Sustituye `~/nav-wip/codigo` (la anterior queda en `codigo.anterior`), enlaza `historico/` al del clon y devuelve el sha256 | 120 s |
| `wip estado` | el `ESTADO.json` de la última copia | 10 s |
| `entorno instalar <repo\|wip> [--gtsam]` | `bash linux/instalar_entorno.sh` de ese árbol (fase 3), sin sudo | 1800 s |
| `suite <repo\|wip> [-q] [-k EXPR] [tests/…]` | pytest del venv `~/.venvs/navegacion` en ese árbol | 900 s |
| `py <repo\|wip> <módulo> [args]` | `python -u -m <módulo>` del venv; módulos: `tracker` (7200 s), `camera.v4l2` (60), `diagnostics.igtl_rate` (900), `diagnostics.clock_offset` (600), `diagnostics.tegrastats_log` (60), `linux.perfil_temporal` (30), `linux.sonda_privilegios` (60). Toda ruta cae dentro del árbol o de `~/nav-salidas/`; `--record`, `--output` y `--salida` solo en `~/nav-salidas/`, con `~/` o absolutas | por módulo |
| `camara rafaga <by-path> <frames ≤ 1800>` | `v4l2-ctl --stream-mmap` a 1280×960 MJPG 90 fps. El único verbo que abre la cámara fuera del tracker; lo teclea el autor (P19) | 60 s |
| `medir tegrastats <s ≤ 900>` | `tegrastats` a `~/nav-salidas/tegrastats_<fecha>_<s>s.txt`; llegar al tope es su fin normal | s |
| `traer <ruta bajo ~/nav-salidas/>` | el archivo por la salida estándar (sustituye a scp) | 60 s |
| `procesos` / `parar <pid>` | `ps -u navagente` / SIGTERM al grupo de un pid que lanzó el guardián (SIGKILL a los 5 s) | 10 / 15 s |
| `registro [n ≤ 200]` | las últimas líneas de `~/nav-registro/guardian.jsonl` (por defecto 50) | 5 s |
| `prueba-tope` | `sleep 30` con 3 s de tope: solo para probar la barrera | 3 s |

Los árboles: `repo` es `~/nav/repo/codigo` (el clon) y `wip` es `~/nav-wip/codigo` (la copia sin commit). Lo pesado (`entorno`, `suite`, `py tracker`, `py camera.v4l2`, `camara`, `medir`) se niega si quedan menos de 5 GB libres, si alguna zona térmica legible pasa de 85 °C o si ya hay 3 pesadas en marcha; los listeners de `igtl_rate` y las demás `py` cuentan como ligeras. Cada orden corre en su grupo de procesos: al tope, SIGTERM al grupo y SIGKILL a los 5 s; si la sesión de sshd desaparece (el cliente murió; `ClientAlive` lo detecta en ≤ 15 s), el guardián lo nota en ≤ 0.5 s porque cambia su padre, y para el grupo igual. El guardián se niega si la cuenta no es `navagente`, si hay un pty, si no hay orden (sin shell) o si la orden lleva un metacaracter. `registro`: una línea JSON por intento (hora, IP, orden, permitido o motivo, código, duración, tope) en `~/nav-registro/guardian.jsonl` y en el diario (`logger -t nav-guardian`; el autor lo lee con `journalctl -t nav-guardian`). Un 126 es una negación y no se rodea: se dice en el reporte.

Si cambia el guardián (la lista blanca o su código), cambia en el repo (commit del autor) y el autor lo copia con sudo: la cuenta no puede tocarlo. Solo el guardián: `sudo install -o root -g root -m 0755 /tmp/nav-instalar/guardian.py /usr/local/lib/nav-guardian/guardian`; `ssh nav-jetson ayuda` dice su versión en la primera línea. El instalador no es idempotente (para si ya está el drop-in): para reinstalarlo todo, antes `desinstalar_guardian.sh` sin `--borrar-cuenta`.

### Lo que hace el autor (protocolo P-2)

En la Jetson, con su cuenta y sudo, tras copiar `codigo/linux/` y la clave pública de los agentes a `/tmp/nav-instalar/`:

```bash
sudo bash /tmp/nav-instalar/instalar_guardian.sh --simular --clave /tmp/nav-instalar/nav_agente_ed25519.pub --desde "<subred LAN>,<subred del cable>,100.64.0.0/10" --autor <su usuario> --pc <ip del pc>
sudo bash /tmp/nav-instalar/instalar_guardian.sh --clave … --desde … --autor … --pc …     # de verdad, con otra sesion suya abierta
```

El instalador guarda `sshd -T -C user=<autor>…` antes, crea la cuenta, deja sus grupos en exactamente {`navagente`, `video`} con `usermod -G video` (el `adduser` de la Jetson Yahboom añade siete grupos más; si sobra o falta uno, para con su lista), instala el guardián, la clave y el drop-in, hace `sshd -t`, repite el `sshd -T` y lo compara (si cambió algo para el autor, borra el drop-in y para) y solo entonces `systemctl reload ssh`. En el PC, el autor crea la clave sin frase de paso (`ssh-keygen -t ed25519 -f $HOME\.ssh\nav_agente_ed25519 -C nav-agente@BigDaddy`), añade los alias `nav-jetson`, `nav-jetson-lan`, `-cable` y `-ts` a `~/.ssh/config` (con `User navagente`, `IdentitiesOnly`, `BatchMode`, `RequestTTY no`, `ClearAllForwardings yes`; el texto, en el plan) y corre:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File codigo/linux/probar_barrera.ps1 -Alias nav-jetson -Salida "Claude outputs/fases/007/barrera" -TopeS 30
```

Los 30 casos: 1–16 negados por el guardián (126), 17–20 cuatro tar malos sin que cambie `wip estado`, 21–23 negados por `sshd` (reenvío `-L` sin saludo SSH por el 9999, `-tt` sin pty, `sftp` que no conecta), 24 `prueba-tope` con 124 y ≤ 4 s en el registro, 25 el cliente matado al 1 s sin dejar ningún `sleep`, 26–30 permitidos con 0. La tabla queda en `-Salida` (puede llevar espacios: cada argumento se cita) y el script sale con 0 solo con 30 de 30. Después: la sonda (`sudo -u navagente /usr/bin/python3 -I /tmp/nav-instalar/sonda_privilegios.py`, 0 privilegios en 28 comprobaciones; un grupo suplementario que no sea `video` cuenta como privilegio), el escaneo repetido como `despues.txt` y el simulacro de corte.

**Para cortar el acceso de golpe:** `sudo mv /etc/ssh/authorized_keys/navagente /etc/ssh/authorized_keys/navagente.off && sudo pkill -u navagente`; se deshace moviéndolo de vuelta. **Para deshacerlo todo:** `sudo bash desinstalar_guardian.sh` (quita el drop-in, la clave y el guardián y recarga ssh; con `--borrar-cuenta` borra también la cuenta con su carpeta).

## El entorno en la Jetson (fase 3)

El código llega de dos maneras. **El clon** (`ssh nav-jetson repo clonar`, una vez; luego `repo actualizar`): `~/nav/repo`, disperso y parcial, sin `herramientas/`, `documentos/`, `*.nrrd` ni `*.dcm`; trae lo commiteado. **La copia WIP**, lo que aún no tiene commit, desde la raíz del repo en el PC:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File codigo/linux/enviar_wip.ps1 -Alias nav-jetson -TopeS 180
```

Hace un tar de `codigo/` con el `tar.exe` de Windows sin `.venv`, `__pycache__`, `.pytest_cache`, `historico/`, `*.nrrd` ni `*.dcm`; lo comprueba con la regla del guardián antes de mandarlo (si algo no vale, sale con 2 sin conectar); lo manda por `wip recibir` con `Start-Process -RedirectStandardInput` y compara su sha256 con el que devuelve el guardián (0 si coinciden; 3 si no, si ssh falla o si el guardián niega; 124 si pasa el tope). En la Jetson queda en `~/nav-wip/codigo`, con `historico/` enlazado al del clon.

El venv, con `ssh nav-jetson entorno instalar <repo|wip> [--gtsam]`, que corre `linux/instalar_entorno.sh` de ese árbol como `navagente`, sin sudo:
1. uv 0.13.6 en `~/.local/share/nav-uv/0.13.6/uv`, bajado de GitHub Releases y comprobado contra el sha256 escrito en el script (clarify P21). No toca el PATH ni los perfiles.
2. `~/.venvs/navegacion` con el CPython 3.11.9 que baja uv (`--managed-python`; el 3.10 del sistema no se toca). Si ya está con ese Python, se reutiliza; si hay otro, se aparta como `navegacion.anterior-<fecha>`.
3. `requirements-jetson.txt` (las versiones del PC, con `==`; sin PySide6, open3d, pyorbbecsdk2 ni matplotlib).
4. La comprobación: cada paquete con su versión y un `ArucoDetector` que encuentra un marcador sintético.
5. Con `--gtsam`, gtsam 4.3.0 en un venv aparte, `~/.venvs/prueba-gtsam`, con un grafo de prueba: solo para saber si instala (meta 006); el del tracker no lo lleva.
6. Los MB de cada parte y lo libre en `/`. Las líneas `ENTORNO_…` son el resumen; sale con 0, 2 (entrada) o 3 (un paso falló).

Después: `ssh nav-jetson py wip linux.sonda_privilegios` (0 privilegios) y `ssh nav-jetson suite wip -q`.

## La suite en Linux (fase 4)

`ssh nav-jetson suite wip` (o `suite repo`) corre la misma suite que el PC, con 0 fallos. Lo que cambia fuera de Windows, cada salto con su motivo en la prueba:
- **El replay de Marker0** (`tests/test_replay_marker0.py`, y `test_explain_pose.py`, que importa sus `TOL_*`): en Windows, 1e-9 mm, 1e-9° y 1e-6 px, como siempre; en Linux, 1e-3 mm, 1e-3° y 1e-3 px (clarify P22, 2026-11-02). En la Jetson (ARM) la pose sobre las esquinas grabadas da lo mismo que en el PC (2.3e-13 mm, 4.4e-13°), pero detectar sobre los PNG da esquinas que difieren hasta en 6.1e-05 px, y la 4×4 del ejemplo (que usa esas esquinas) hasta 3.3e-05 mm y 1.1e-04°.
- **El sha de la calibración** (B74): `diagnostics/explain_pose.py` compara el sha grabado con el del `.yml` con LF y con CRLF, porque la grabación es del árbol del PC (CRLF) y git y la Jetson lo tienen en LF.
- **La copia WIP solo lleva `codigo/`**: las 8 pruebas de `test_como_funciona.py` que leen `docs/` y la de `.gitattributes` de `test_escaneo_jetson.py` se saltan si no están; con `suite repo` corren.
- **El panel corre en el PC (P16)**: sin PySide6 se saltan `import gui.panel` y el `--selftest`; las dos del lanzador (`CREATE_NEW_PROCESS_GROUP`) se saltan fuera de Windows. Las recetas sí corren: fuera de Windows, `tests/conftest.py` les da el python de la suite en vez de `codigo/.venv/Scripts/python.exe`.
- **El guardián**: las cuatro «solo Linux» corren; su salida es un archivo de verdad (`Popen` pide `fileno()`).

En Windows no se salta ninguna de estas: si falta `docs/` o PySide6, fallan.

**El guardián 3 (2026-11-02).** Con el guardián 2, `info temperatura` y toda orden pesada salían con 125 (`TypeError: can't concat NoneType to bytes`): las zonas cv0, cv1 y cv2 de la Jetson dan EAGAIN al leer `temp` y `read_text` no lo soportaba. El 3 lee las zonas con `os.read` y salta las que no responden (B75). Se instala como dice arriba («Solo el guardián»); `ssh nav-jetson ayuda` dice «nav-guardian 3 (2026-11-02)».

## La cámara por V4L2 (fase 5)

El tracker es el mismo (`python -m tracker --config profiles/tracker_config_gs1.yaml …`); lo que cambia fuera de Windows está en `codigo/camera/` (ADR J1 del plan; `clarify.md` P11 y P12):
- **La identidad** es `camera.usb_port_linux` de los mismos perfiles gs1 y gs2: el nombre del enlace bajo `/dev/v4l/by-path/` (`platform-3610000.usb-usb-0:2.1:1.0-video-index0` es gs1, focus 500; `…0:2.2…` es gs2, focus 332; medidos en el escaneo). Lo fija el puerto USB físico: el `/dev/videoN` cambia con el orden de arranque (en el escaneo gs1 era `video2`; el 2026-11-02, `video0`) y `by-id` no distingue las dos (misma serie). `camera/v4l2.py` lista los enlaces (`listar_camaras_v4l2`) y resuelve el dispositivo (`resolver_dispositivo`, igualdad exacta: 0 o 2 coincidencias paran).
- **Los controles** van por `v4l2-ctl` en un subproceso con tope de 5 s (`CapaLinuxV4L2`; `capa_para_plataforma("linux")` la devuelve): se leen todos con `--list-ctrls-menus`, se escribe solo lo que difiere con `--set-ctrl=<control>=<valor>` (uno por llamada, `auto_exposure` antes que `exposure_time_absolute`), se relee y se compara en las unidades de la cámara; un valor fuera del rango que declara la cámara para antes de escribir. La exposición va en unidades de 100 µs: los 0.977 ms del perfil son `exposure_time_absolute=10` (lo que la cámara ya tenía) y se releen como 1.0 ms. `exposure_manual: true` es `auto_exposure=1` (Manual Mode).
- **El video** se abre con `cv2.VideoCapture("/dev/videoN", cv2.CAP_V4L2)` tras la marca y los ajustes, con las mismas llamadas de FOURCC MJPG, 1280×960, 90 fps y warmup que en Windows; el `backend: MSMF` del perfil se ignora y el log lo dice. En Windows nada cambia (`plataforma` es `sys.platform`).

Desde el PC, sin abrir ningún flujo de video (lo puede correr un agente): `ssh nav-jetson py wip camera.v4l2 --listar` y `ssh nav-jetson py wip camera.v4l2 --leer --puerto <by-path>`. `--aplicar --config profiles/tracker_config_gs1.yaml [--forzar]` escribe en la cámara: lo teclea el autor (P19), igual que el tracker. Las pruebas: `tests/test_v4l2.py`, sobre las salidas reales de `v4l2-ctl` en `tests/data/linux/`; el fixture B34 niega `listar_camaras_v4l2` y `ejecutar_v4l2ctl`.

**Protocolo P-5 (el autor, en vivo; la caja de luz al máximo, Marker0 de 80 mm quieto a ~37 cm).** Por cámara, con `<gs>` = `gs1` o `gs2` y `<bp>` su by-path; el cliente es `igtl_rate` en la misma Jetson, sin red:
1. En una consola: `ssh nav-jetson py wip diagnostics.igtl_rate listen --host 127.0.0.1 --port 18944 --seconds 75` (arranca antes que el tracker: el tracker lo espera hasta 30 s y, si no llega, aborta con código 3).
2. En otra: `ssh nav-jetson py wip tracker --config profiles/tracker_config_<gs>.yaml --no-window --duration 60 --record ~/nav-salidas/p5_<gs>_a.npz --timing ~/nav-salidas/p5_<gs>_a.json` (corrida a). Se anotan `[Webcam] Puerto … -> /dev/videoN`, «Marca comprobada», «Ajustes aplicados», «Tamano real 1280x960», las líneas `[FPS]` y la final `[Captura]` (fps de cámara y de bucle) y los Hz del listener.
3. Corrida b, con ventana: igual sin `--no-window`, solo si hay un escritorio en la Jetson con `DISPLAY`; si no, «sin medir».
4. Corrida c: el perfil de la otra cámara sobre este puerto (`--config profiles/tracker_config_<otra>.yaml` no sirve porque cada perfil lleva su propio puerto; se usa un perfil temporal fuera del repo con el `usb_port_linux` de esta cámara y la `marca` de la otra, p. ej. `~/nav-salidas/perfiles/<gs>_marca_cruzada.yaml`): tiene que parar con «no es la del perfil … focus: declarado …, leido …» sin escribir ni abrir.
5. Corrida d: el tracker sin el listener: abortar con código 3 («Slicer no se conecto al puerto 18944 en 30 s») sin abrir la cámara.
6. Tras cada corrida: `ssh nav-jetson info camara-libre <bp>` (sin salida = libre) y `ssh nav-jetson info puerto-libre 18944` (solo la cabecera = libre).
7. La sd z en reposo y el % de frames con pose salen del `.npz` con `ssh nav-jetson traer p5_<gs>_a.npz > "Claude outputs/fases/007/p5_<gs>_a.npz"` y `python -m diagnostics.pose_log --stats` en el PC (o el script que use el reporte de la fase).

## El ruido en reposo (fase 5b, B77)

En el P-5 (2026-11-03) gs1 por V4L2 dio en reposo una sd z de 0.074 mm frente a 0.032–0.043 por MSMF en el PC, y gs2 por V4L2 0.040. `python -m diagnostics.ruido_pose` (en el PC, sin cámara; no está en la lista blanca del guardián) separa sobre el `.npz` de `tracker --record` lo que se mezcla en esa sd: la pose cruda de IPPE sin filtro, la misma pose refiltrada con el 1-Euro (con los tiempos grabados tiene que reproducir `sent_M`; con tiempos uniformes dice si las ráfagas de frames suben el ruido), los intervalos entre frames, la sd de las esquinas y del lado aparente, la bimodalidad, el espectro y la **deriva** (la pendiente y las medias por segundo, que el filtro deja pasar, frente al residuo rápido). Con los PNG de `--save-frames` mide también la imagen (nivel de blanco por PNG, contraste, ancho de borde, bloqueo JPEG). `--input ETIQUETA=RUTA.npz` se repite, `--frames ETIQUETA=CARPETA` es opcional, `--referencia ETIQUETA` fija frente a qué se comparan en cociente, y `--output` y `--output-markdown` no se pisan.

**Parte A (sin cámara, 2026-11-03).** Sobre las tres grabaciones del P-5 (`Claude outputs/fases/007/b77/analisis_p5.md`): el filtro no añade ruido (0 % de frames con dt < 2 ms; refiltrada uniforme 0.0733 frente a 0.0737 grabada), no hay dos valores (Sarle 0.38, separación de k-medias 2.8, la de una normal) y lo que sobra en gs1 es **una deriva lenta de la escala aparente**: z baja casi en línea recta −3.9 µm/s, 0.23 mm en 60 s; su sd lenta (0.071) es casi toda la sd enviada (0.074) y el ruido rápido tras el filtro es 0.022 mm (gs2: 0.032; PC: MAD 0.032). Quitando la recta, gs1 queda en 0.029 mm. Lo que puede derivar así: el calentamiento de la cámara, el asentamiento del soporte o la luz; no el hub, el formato ni la decodificación.

**Protocolo P-5b (el autor, en vivo; la versión completa para copiar y pegar, con lo que se espera de cada orden, en `Claude outputs/fases/007/p5b.md`).** Caja de luz al máximo, Marker0 de 80 mm quieto en la posición del P-5 (~36 cm de gs1, ~33 cm de gs2); gs1 (focus 500) en `platform-3610000.usb-usb-0:2.1:1.0-video-index0` y gs2 (focus 332) en `…0:2.2…`. En cada corrida se anota la hora y los minutos desde que la cámara se enchufó. Lo que abre una cámara lo teclea el autor (P19); `info`, `traer`, `linux.perfil_temporal` y el análisis los corre el agente.
1. Antes: `enviar_wip.ps1`; `info camara-libre <bp>` (sin líneas) e `info puerto-libre 18944` (solo la cabecera); `ssh nav-jetson info v4l2 <bp>` de las dos cámaras a un archivo (`| Out-File -Encoding utf8 …`): los 18 controles con su `value=`.
2. Cada corrida: en una consola `ssh nav-jetson py wip diagnostics.igtl_rate listen --host 127.0.0.1 --port 18944 --seconds 75 --timeout 60 --device Marker0ToTracker`; en otra, dentro de los 60 s, `ssh nav-jetson py wip tracker --config <perfil> --no-window --duration 60 --record /home/navagente/nav-salidas/b77/<corrida>.npz --timing /home/navagente/nav-salidas/b77/<corrida>.json --save-frames /home/navagente/nav-salidas/b77/<corrida>_frames --frames-every 600` (9 PNG por minuto). Después, `camara-libre` y `puerto-libre`.
3. Las corridas: **J1 y J2**, gs1 seguidas sin tocar nada (si la deriva sigue en J2 es continua; si desaparece, era asentamiento); **J3**, gs2; **J4**, gs1 en el puerto del hub de gs2 (se intercambian los dos conectores, gs2 no se abre) con el perfil temporal `ssh nav-jetson py wip linux.perfil_temporal --base profiles/tracker_config_gs1.yaml --poner camera.usb_port_linux=platform-3610000.usb-usb-0:2.2:1.0-video-index0 --salida /home/navagente/nav-salidas/perfiles/gs1_puerto22.yaml` y `--config /home/navagente/nav-salidas/perfiles/gs1_puerto22.yaml` (una variable: el puerto); al acabar, `info v4l2` de las dos y los cables como estaban. **W1 y W2**, gs1 y gs2 en el PC por MSMF con `python -m diagnostics.igtl_rate listen …` local y el mismo tracker con `--record`, `--timing`, `--save-frames … --frames-every 600` bajo `Claude outputs/fases/007/b77/`, tras leer sus controles con `python -m diagnostics.probe_camera --leer --puerto "<usb_port_windows>" --salida … --timeout 60`.
4. Traer: cada archivo con `Start-Process -FilePath ssh -ArgumentList 'nav-jetson','traer','/home/navagente/nav-salidas/b77/<archivo>' -RedirectStandardOutput '<ruta en el PC>' -NoNewWindow -Wait -PassThru` (el `>` de PowerShell 5.1 rompe los bytes); los PNG son `<corrida>_frames/frame_00000.png`, `frame_00600.png`, … (el que no exista da 126 y se borra el archivo vacío). Se comprueba con `zipfile.testzip()` y el número de frames.
5. El análisis: `python -m diagnostics.ruido_pose --input W1=… --frames W1=… --input J1=… --frames J1=… … --referencia W1 --output …/analisis_p5b.json --output-markdown …/analisis_p5b.md`. Lo que decide: `deriva_z_enviada` (pendiente, sd lenta, sd tras quitar la recta) frente a `sd_rapida`, `imagen.nivel_blanco_por_png` y las listas de controles Jetson/PC y gs1/gs2. Una causa es clara solo si una variable separa las corridas con deriva de las sin deriva y explica la imagen; si es calor, mecánica o luz, no hay corrección de código en la fase (P24).
