#!/usr/bin/env bash
# desinstalar_guardian.sh - quita la barrera de los agentes de la Jetson (meta 007, fase 2).
#
# Lo corre el autor, con sudo, en la Jetson. Ningun agente lo corre.
#
#   sudo bash desinstalar_guardian.sh [--simular] [--borrar-cuenta]
#
# Quita el drop-in de sshd, la clave de los agentes y el guardian, comprueba sshd -t, recarga ssh
# y para los procesos de la cuenta. Solo con --borrar-cuenta borra la cuenta navagente con su
# carpeta (el clon, la copia WIP, el venv, las salidas y el registro) y la saca de cron.deny y
# at.deny. Con --simular imprime cada cambio sin hacerlo. Solo ASCII y LF.

set -euo pipefail

CUENTA=navagente
GUARDIAN_DIR=/usr/local/lib/nav-guardian
CLAVE_DESTINO=/etc/ssh/authorized_keys/$CUENTA
DROPIN=/etc/ssh/sshd_config.d/60-nav-guardian.conf

SIMULAR=0
BORRAR_CUENTA=0

uso() {
    sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
    case "$1" in
        --simular) SIMULAR=1; shift ;;
        --borrar-cuenta) BORRAR_CUENTA=1; shift ;;
        -h|--help|--ayuda) uso; exit 0 ;;
        *) echo "ERROR: argumento desconocido: $1" >&2; uso >&2; exit 2 ;;
    esac
done

[ "$(id -u)" -eq 0 ] || { echo "ERROR: hay que correrlo con sudo" >&2; exit 1; }

if [ "$SIMULAR" -eq 1 ]; then
    echo "=== SIMULACION: se imprime cada cambio y no se hace ninguno ==="
fi

hacer() {
    echo "+ $*"
    if [ "$SIMULAR" -eq 0 ]; then
        "$@"
    fi
}

echo "=== 1. El drop-in de sshd y la clave ==="
if [ -e "$DROPIN" ]; then hacer rm -f "$DROPIN"; else echo "no esta $DROPIN"; fi
if [ -e "$CLAVE_DESTINO" ]; then hacer rm -f "$CLAVE_DESTINO"; else echo "no esta $CLAVE_DESTINO"; fi
if [ -e "$CLAVE_DESTINO.off" ]; then hacer rm -f "$CLAVE_DESTINO.off"; fi
if [ "$SIMULAR" -eq 0 ]; then
    sshd -t || { echo "ERROR: sshd -t fallo despues de quitar el drop-in; no se recarga ssh" >&2; exit 1; }
fi
hacer systemctl reload ssh

echo ""
echo "=== 2. Los procesos y el guardian ==="
if getent passwd "$CUENTA" >/dev/null; then
    hacer pkill -u "$CUENTA" || echo "(no habia procesos de $CUENTA)"
fi
if [ -d "$GUARDIAN_DIR" ]; then hacer rm -rf "$GUARDIAN_DIR"; else echo "no esta $GUARDIAN_DIR"; fi

echo ""
if [ "$BORRAR_CUENTA" -eq 1 ]; then
    echo "=== 3. La cuenta $CUENTA, con su carpeta ==="
    if getent passwd "$CUENTA" >/dev/null; then
        sleep 1
        hacer pkill -KILL -u "$CUENTA" || true
        hacer deluser --remove-home "$CUENTA"
    else
        echo "no existe la cuenta $CUENTA"
    fi
    for archivo in /etc/cron.deny /etc/at.deny; do
        if [ -f "$archivo" ] && grep -qx "$CUENTA" "$archivo"; then
            hacer sed -i "/^$CUENTA\$/d" "$archivo"
        fi
    done
else
    echo "=== 3. La cuenta $CUENTA se conserva (con --borrar-cuenta se borra con su carpeta) ==="
fi
echo ""
echo "Listo."
