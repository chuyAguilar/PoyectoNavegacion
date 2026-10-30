#!/usr/bin/env bash
# escanear_jetson.sh - el escaneo de la Jetson, solo lectura (meta 007, fase 1).
#
# Lo lanza escanear.ps1 desde el PC, con la cuenta y el alias del autor (protocolo P-1):
#   ssh <alias> timeout -k 5 120 bash --norc --noprofile -s
# con este archivo por la entrada estandar. Todo lo que recoge va a la salida estandar;
# en la Jetson no se escribe nada, y al final un find lo comprueba en el HOME.
#
# Reglas del archivo (las comprueba codigo/tests/test_escaneo_jetson.py):
#   - solo ASCII y LF;
#   - cada orden externa pasa por run, run_durante o hay, que le ponen timeout
#     (10 s por orden; ninguna orden empieza pasados 90 s, y el total queda bajo 120 s);
#   - ninguna redireccion a un archivo: solo 2>&1, >/dev/null y </dev/null;
#   - ninguna tuberia ni $(...) salvo $(timeout ...);
#   - nada que cambie el sistema, la red, los servicios o las camaras.
#
# Todo va dentro de main, que se llama en la ultima linea con </dev/null: bash lee el
# script entero antes de ejecutar nada (si llega cortado, no corre nada) y ninguna orden
# puede comerse el resto del script por la entrada estandar.
#
# Formato de la salida: cada seccion empieza con "=== [n/12] nombre ===", cada orden con
# "$ orden", y si no sale con 0 se anota "[codigo N]" o "[TOPE: ...]". Las dos ultimas
# lineas son "ESCANEO_FIN ..." y "TOPES: ...", que lee escanear.ps1.

seccion() {
    echo ""
    echo "=== [$1/12] $2 ==="
}

_orden() {
    local tope=$1
    local esperado=$2
    shift 2
    echo "\$ $*"
    ORDENES=$((ORDENES + 1))
    if [ "$SECONDS" -gt "$ARRANQUE_MAX" ]; then
        SALTADAS=$((SALTADAS + 1))
        echo "[saltada: van $SECONDS s y ninguna orden empieza pasados $ARRANQUE_MAX s]"
        return 0
    fi
    timeout -k 2 "$tope" "$@" </dev/null 2>&1
    local rc=$?
    if [ "$rc" -eq 124 ] || [ "$rc" -eq 137 ]; then
        if [ "$esperado" = si ]; then
            echo "[fin esperado: se corta a los $tope s a proposito]"
        else
            TOPES=$((TOPES + 1))
            LISTA_TOPES="$LISTA_TOPES [$*]"
            echo "[TOPE: cortada a los $tope s]"
        fi
    elif [ "$rc" -ne 0 ]; then
        FALLIDAS=$((FALLIDAS + 1))
        echo "[codigo $rc]"
    fi
    return 0
}

run() {
    _orden "$TOPE_ORDEN" no "$@"
}

run_durante() {
    local segundos=$1
    shift
    _orden "$segundos" si "$@"
}

hay() {
    timeout -k 2 5 which "$1" </dev/null >/dev/null 2>&1
}

main() {
    export LC_ALL=C
    readonly TOPE_ORDEN=10
    readonly ARRANQUE_MAX=90
    ORDENES=0
    FALLIDAS=0
    TOPES=0
    SALTADAS=0
    LISTA_TOPES=""
    printf -v INICIO '%(%s)T' -1
    echo "ESCANEO_INICIO formato=1 epoch=$INICIO"

    seccion 1 "sistema"
    run hostname
    run date -Is
    run uname -a
    run cat /etc/os-release
    run cat /etc/nv_tegra_release
    run dpkg-query -W nvidia-jetpack nvidia-l4t-core
    run uptime

    seccion 2 "python"
    echo "PATH=$PATH"
    run which python3 python3.10 python3.11 python3.12 pip3 uv conda mamba micromamba
    run find /usr/bin /usr/local/bin -maxdepth 1 -name 'python3*'
    run python3 -c 'import sys, platform, tarfile; print(sys.version); print("glibc", platform.libc_ver()); print("tarfile.data_filter", hasattr(tarfile, "data_filter"))'
    run python3 -m pip --version
    run ldd --version
    run ls -d "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv" "$HOME/miniforge3" "$HOME/miniconda3" "$HOME/anaconda3" "$HOME/mambaforge" /opt/conda

    seccion 3 "cpu y gpu"
    run lscpu
    run nproc
    run cat /sys/devices/system/cpu/online
    run grep -H . /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors
    run grep -H . /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
    run grep -H . /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq
    run grep -H . /sys/devices/system/cpu/cpu*/cpufreq/scaling_max_freq
    run grep -H . /sys/class/devfreq/*/governor /sys/class/devfreq/*/cur_freq /sys/class/devfreq/*/max_freq
    run ls -l /usr/local/
    run cat /usr/local/cuda/version.json
    run /usr/local/cuda/bin/nvcc --version

    seccion 4 "memoria"
    run free -m
    run swapon --show
    run zramctl
    run grep -E '^(MemTotal|MemFree|MemAvailable|SwapTotal|SwapFree|CmaTotal|CmaFree):' /proc/meminfo
    run ps -eo pid,user,rss,pcpu,comm --sort=-rss

    seccion 5 "disco"
    run df -h
    run df -h /
    run lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT

    seccion 6 "usb"
    run lsusb
    run lsusb -t

    seccion 7 "v4l2"
    run ls -l /dev/video*
    run ls -l /dev/v4l/by-path/
    run ls -l /dev/v4l/by-id/
    if hay v4l2-ctl; then
        echo "v4l2-ctl: instalado"
        run v4l2-ctl --version
        run v4l2-ctl --list-devices
        for d in /dev/v4l/by-path/*-video-index0; do
            if [ -e "$d" ]; then
                echo "--- camara $d"
                run v4l2-ctl -d "$d" --info
                run v4l2-ctl -d "$d" --list-formats-ext
                run v4l2-ctl -d "$d" --list-ctrls-menus
            fi
        done
    else
        echo "v4l2-ctl: NO instalado (paquete v4l-utils, P12)"
    fi
    for d in /dev/v4l/by-path/*-video-index0; do
        if [ -e "$d" ]; then
            echo "--- udev de $d"
            run udevadm info --query=property --name="$d"
        fi
    done

    seccion 8 "red"
    run ip -br link
    run ip -br addr
    run ip route
    run nmcli device status
    run nmcli -t -f NAME,TYPE,DEVICE connection show --active
    run tailscale status --peers=false
    run tailscale ip
    run ss -ltnp
    run ss -lunp
    echo "--- el 18944 (si solo sale la cabecera, esta libre)"
    run ss -ltn 'sport = :18944'
    run systemctl is-active ufw
    run cat /etc/ufw/ufw.conf

    seccion 9 "servicios"
    run systemctl list-units --type=service --state=running --no-pager --no-legend
    run systemctl is-enabled ollama
    run systemctl is-active ollama
    run systemctl show ollama -p MainPID -p MemoryCurrent
    run ollama ps
    run ollama list
    run ps -o pid,rss,pcpu,etime,comm -C ollama
    run systemctl is-active docker jupyter jupyterlab

    seccion 10 "energia"
    run nvpmodel -q
    run cat /var/lib/nvpmodel/status

    seccion 11 "temperatura"
    run grep -H . /sys/class/thermal/thermal_zone*/type /sys/class/thermal/thermal_zone*/temp
    if hay tegrastats; then
        run_durante 10 tegrastats --interval 1000
    else
        echo "tegrastats: no esta en el PATH"
    fi

    seccion 12 "cuenta"
    run id
    run getent passwd "${USER:-nadie}"
    run getent group
    run ssh -V
    run cat /etc/ssh/sshd_config
    run ls -l /etc/ssh/sshd_config.d/
    run grep -H . /etc/ssh/sshd_config.d/*.conf

    echo ""
    echo "=== comprobacion final: lo que cambio en el HOME desde el inicio ==="
    local nuevos
    nuevos=$(timeout -k 2 15 find "$HOME" -maxdepth 2 -newermt "@$INICIO" 2>&1)
    if [ -z "$nuevos" ]; then
        echo "find: vacio (el escaneo no escribio nada en el HOME)"
    else
        echo "find: NO vacio. Cambio esto en el HOME desde el inicio:"
        echo "$nuevos"
    fi
    echo ""
    echo "ESCANEO_FIN segundos=$SECONDS ordenes=$ORDENES fallidas=$FALLIDAS topes=$TOPES saltadas=$SALTADAS"
    echo "TOPES:${LISTA_TOPES:- ninguno}"
}

main "$@" </dev/null
