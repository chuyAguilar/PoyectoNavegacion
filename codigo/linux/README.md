# codigo/linux — el trabajo con la Jetson Orin Nano

Lo de esta carpeta es para la meta 007 · El tracker en la Jetson Orin Nano, con Slicer en el PC (`specs/007-jetson/`). Se completa fase por fase; al cerrar la meta, en la fase 9 · Cómo se trabaja con la Jetson y cierre de la meta, dirá cómo llega el código, cómo se corren la suite y el tracker, cómo se paran y cómo se corta el acceso.

Hoy hay el escaneo (fase 1 · El escaneo de la Jetson, solo lectura) y la barrera de los agentes (fase 2 · La barrera de seguridad para los agentes). Ningún agente se conecta a la Jetson hasta que la barrera esté instalada por el autor, probada con `probar_barrera.ps1` (30 de 30) y las reglas de `settings.json` aplicadas; entonces los agentes usan solo `ssh nav-jetson <verbo>`.

## Qué hay

- `escanear_jetson.sh`: el escaneo, en bash. Solo lee y lo imprime todo por la salida estándar; en la Jetson no escribe nada. Doce secciones: sistema, Python, CPU y GPU, memoria, disco, USB, V4L2, red, servicios, energía, temperatura y la cuenta. Cada orden lleva `timeout` de 10 s (10 s de `tegrastats`, cortado a propósito), ninguna empieza pasados 90 s y todo queda bajo 120 s. Al final, un `find` del HOME con `-newermt` dice si cambió algo desde el inicio (tiene que salir vacío).
- `escanear.ps1`: lo lanza desde el PC. Manda el script por la entrada estándar de `ssh <alias> timeout -k 5 120 bash --norc --noprofile -s` con `Start-Process` (una tubería de PowerShell 5.1 cambiaría los fines de línea), guarda lo que llega en un archivo que no pisa y espera con tope.
- `guardian.py`: el guardián de la cuenta `navagente` (abajo). `sonda_privilegios.py`: lo que haría un código del agente que intentara salirse. `tars_malos.py`: los tar que `wip recibir` niega, para la suite y `probar_barrera.ps1`.
- `instalar_guardian.sh` y `desinstalar_guardian.sh`: para el autor, con sudo y `--simular`. `probar_barrera.ps1`: los 30 casos de la barrera, desde el PC.
- Las pruebas, en `codigo/tests/`: `test_escaneo_jetson.py` (el escaneo), `test_guardian.py`, `test_sonda_privilegios.py` y `test_probar_barrera.py` (la barrera, sin Jetson: con un `ssh.exe` falso compilado con `Add-Type`). Las de tope y grupo de procesos del guardián solo corren en Linux (en la Jetson, fase 4).

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
