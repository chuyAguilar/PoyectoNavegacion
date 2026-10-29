# Plan — Meta 007 · El tracker en la Jetson Orin Nano, con Slicer en el PC

Lo escribe el agente de planificación con `/planear`, sin código. Lo que el autor autoriza es este archivo.

## Cambios de esta versión (2026-10-29, con P6–P18 contestadas)

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
- Pruebas: `test_escaneo_jetson.py` (fase 1), `test_guardian.py` y `test_sonda_privilegios.py` (fase 2), `test_v4l2.py` (fase 5), `test_clock_offset.py` (fase 6), `test_tegrastats_log.py` y `test_perfil_temporal.py` (fase 7) y `test_receta_jetson.py` (fase 8). Además, los casos nuevos de `test_transport.py`, `test_camera_backend.py` y `test_ajustes_camara.py`. Las salidas reales de `v4l2-ctl` y `tegrastats` van en `codigo/tests/data/linux/` (texto del escaneo, sin datos de paciente).

Modificar: los mismos que en la versión anterior.
- `camera/controls.py`, `camera/backend.py`, `transport/igtl.py`, `tracker.py`, `diagnostics/igtl_rate.py`, `gui/recipes.py` y `gui/panel.py`.
- Los perfiles gs1 y gs2 ganan `usb_port_linux`.
- `tests/conftest.py`: también niega `camera.v4l2.listar_camaras_v4l2` y `ejecutar_v4l2ctl`.
- El `skipif` de las pruebas que solo valen en Windows.
- `codigo/readme.md`, `docs/ARCHITECTURE.md` (§3.1, §3.5, §3.7 y §6) y `docs/CONTEXT.md` (§3, §4 y §6).

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

`linux/perfil_temporal.py`: `crear(base: Path, puerto: int, salida: Path) -> Path` y `main(argv=None) -> int`. No pisa un archivo que ya exista.

`camera/v4l2.py`, `camera/controls.py`, `camera/backend.py`, `transport/igtl.py`, `tracker.py`, `diagnostics/clock_offset.py`, `diagnostics/igtl_rate.py` y `diagnostics/tegrastats_log.py`: las firmas de la versión anterior, sin cambio. Las principales:
- `CamaraV4L2(ruta_puerto, dispositivo)`, `listar_camaras_v4l2`, `resolver_dispositivo`, `ejecutar_v4l2ctl(args, timeout_s=5.0)`, `parsear_list_ctrls`, `exposicion_ms_a_v4l2` y `class CapaLinuxV4L2` con `leer` y `aplicar`.
- `WebcamBackend(…, usb_port_linux=None, *, plataforma=sys.platform, …)`.
- `IgtlSender(port, iface=None)`, con `host`.
- `--igtl-iface` en el tracker.
- `estimate_offset(samples) -> dict`.
- `summarize(arrivals, gap_ms, clock_offset_ms=0.0)`.

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

- **Entrega:** `diagnostics/tegrastats_log.py` con su prueba sobre el log real del escaneo, `linux/perfil_temporal.py` con su prueba, y el protocolo P-7.
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
- **J5 (al cerrar) · La meta 007 cierra con los números de la Jetson** y la decisión del autor sobre dónde queda el tracker, como ADR-031 y ADR-033.

## Preguntas abiertas

P6–P18 están contestadas (2026-10-29). Las nuevas van también al final de `clarify.md`. La pregunta del método de Python 3.11 no se abre ahora: se abre al cerrar la fase 1, con el escaneo (P6).

- **P19 · Quién teclea lo que abre la cámara en la Jetson** (`camara rafaga` y `py … tracker`):
  - (a) El autor, en la sesión en vivo, con los comandos que le da el protocolo, por el mismo alias y el mismo guardián (recomendada). Mantiene la regla de `desarrollo` y `pruebas` («No abres la cámara, el tracker ni Slicer») y el autor está delante de la cámara y de Slicer de todos modos.
  - (b) Los agentes, por el guardián, en una sesión en vivo con el autor presente, que lo confirma antes. Cambia esa regla de los dos agentes.
- **P20 · La clave personal del autor hacia la Jetson** (alias `yahboom`) y su `sudo` allí:
  - (a) Con frase de paso, sin dejarla cargada en el agente de claves de Windows, y el `sudo` de su cuenta con contraseña (recomendada). Cierra el rodeo del hallazgo 7: aunque un agente intentara usarla, `BatchMode` falla sin la frase.
  - (b) Como esté hoy. Entonces B69 sube a alta.

## Títulos de commit

- Fase 1: «Escanea la Jetson en solo lectura (meta 007, fase 1)»
- Fase 2: «Pone la barrera de los agentes en la Jetson (meta 007, fase 2)»
- Fase 3: «Prepara el entorno de la Jetson (meta 007, fase 3)»
- Fase 4: «Hace que la suite corra en Linux (meta 007, fase 4)»
- Fase 5: «Abre las cámaras por V4L2 en la Jetson (meta 007, fase 5)»
- Fase 6: «Deja que Slicer reciba del tracker de la Jetson (meta 007, fase 6)»
- Fase 7: «Mide las dos cámaras a la vez en la Jetson (meta 007, fase 7)»
- Fase 8: «Lanza el tracker de la Jetson desde el panel (meta 007, fase 8)»
- Fase 9: «Documenta el trabajo con la Jetson y cierra la meta 007 (fase 9)»
