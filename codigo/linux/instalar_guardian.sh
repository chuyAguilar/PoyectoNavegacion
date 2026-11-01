#!/usr/bin/env bash
# instalar_guardian.sh - pone la barrera de los agentes en la Jetson (meta 007, fase 2).
#
# Lo corre el autor, con sudo, en la Jetson (protocolo P-2). Ningun agente lo corre.
# Primero con --simular, que imprime cada cambio sin hacerlo; despues de verdad, con una sesion
# suya abierta aparte (recargar ssh no corta las sesiones abiertas).
#
#   sudo bash instalar_guardian.sh [--simular] --clave <nav_agente_ed25519.pub> \
#        --desde "<subred LAN>,<subred del cable>,100.64.0.0/10" --autor <usuario> --pc <ip del pc> \
#        [--origen <carpeta con guardian.py>]
#
# Hace, en este orden (plan de la meta 007, seccion 'Lo que el autor aplica'):
#   1. sshd -T -C user=<autor>,host=<pc>,addr=<pc> a un archivo (la configuracion efectiva del autor).
#   2. Crea la cuenta navagente (sin contrasena, /bin/bash, HOME 0750, solo en video), la saca de
#      sudo/admin/docker/lxd/adm/disk si estuviera, la pone en cron.deny y at.deny, le quita el
#      linger, instala el guardian en /usr/local/lib/nav-guardian/guardian (root, 0755), escribe
#      /etc/ssh/authorized_keys/navagente (root, 0644, restrict,from=...) y el drop-in
#      /etc/ssh/sshd_config.d/60-nav-guardian.conf.
#   3. sshd -t: si falla, borra el drop-in y para sin recargar.
#   4. Repite el sshd -T del paso 1 y lo compara: si cambio algo, borra el drop-in y para.
#   5. systemctl reload ssh, y muestra la configuracion efectiva de navagente.
#
# Solo ASCII y LF. Para deshacerlo: desinstalar_guardian.sh. Para cortar el acceso de golpe:
#   sudo mv /etc/ssh/authorized_keys/navagente /etc/ssh/authorized_keys/navagente.off && sudo pkill -u navagente

set -euo pipefail

CUENTA=navagente
GUARDIAN_DIR=/usr/local/lib/nav-guardian
GUARDIAN=$GUARDIAN_DIR/guardian
CLAVES_DIR=/etc/ssh/authorized_keys
CLAVE_DESTINO=$CLAVES_DIR/$CUENTA
DROPIN=/etc/ssh/sshd_config.d/60-nav-guardian.conf
GRUPOS_PROHIBIDOS="sudo admin docker lxd adm disk"

SIMULAR=0
CLAVE=""
DESDE=""
AUTOR=""
PC=""
ORIGEN="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

uso() {
    sed -n '2,24p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
    case "$1" in
        --simular) SIMULAR=1; shift ;;
        --clave) CLAVE="${2:-}"; shift 2 ;;
        --desde) DESDE="${2:-}"; shift 2 ;;
        --autor) AUTOR="${2:-}"; shift 2 ;;
        --pc) PC="${2:-}"; shift 2 ;;
        --origen) ORIGEN="${2:-}"; shift 2 ;;
        -h|--help|--ayuda) uso; exit 0 ;;
        *) echo "ERROR: argumento desconocido: $1" >&2; uso >&2; exit 2 ;;
    esac
done

fallo() {
    echo "ERROR: $*" >&2
    exit 1
}

# Las entradas, antes de tocar nada (principio 7).
[ -n "$CLAVE" ] || { echo "ERROR: falta --clave <archivo .pub de la clave de los agentes>" >&2; exit 2; }
[ -n "$DESDE" ] || { echo "ERROR: falta --desde <subredes separadas por coma>" >&2; exit 2; }
[ -n "$AUTOR" ] || { echo "ERROR: falta --autor <tu usuario en la Jetson>" >&2; exit 2; }
[ -n "$PC" ] || { echo "ERROR: falta --pc <ip del PC desde el que entras>" >&2; exit 2; }
[ "$(id -u)" -eq 0 ] || fallo "hay que correrlo con sudo"
[ -f "$CLAVE" ] || fallo "no existe la clave $CLAVE"
[ "$(wc -l < "$CLAVE")" -le 1 ] || fallo "la clave $CLAVE tiene mas de una linea"
grep -Eq '^ssh-ed25519 [A-Za-z0-9+/=]+( [^ ]+)?$' "$CLAVE" || fallo "la clave $CLAVE no es una clave publica ssh-ed25519 de una linea"
ssh-keygen -l -f "$CLAVE" >/dev/null || fallo "ssh-keygen no reconoce la clave $CLAVE"
echo "$DESDE" | grep -Eq '^[0-9A-Fa-f.:/]+(,[0-9A-Fa-f.:/]+)*$' || fallo "--desde tiene que ser subredes CIDR separadas por coma, sin espacios"
getent passwd "$AUTOR" >/dev/null || fallo "no existe el usuario $AUTOR"
[ -f "$ORIGEN/guardian.py" ] || fallo "no esta $ORIGEN/guardian.py (usa --origen)"
command -v sshd >/dev/null || fallo "no se encuentra sshd"
command -v /usr/bin/python3 >/dev/null || fallo "no esta /usr/bin/python3"
/usr/bin/python3 -I -c 'import sys, tarfile; assert sys.version_info >= (3, 8), sys.version; assert hasattr(tarfile, "data_filter"), "sin tarfile.data_filter"' \
    || fallo "el python3 del sistema no sirve para el guardian (>= 3.8 y tarfile.data_filter)"
/usr/bin/python3 -I -c 'import ast, sys; ast.parse(open(sys.argv[1], encoding="utf-8").read())' "$ORIGEN/guardian.py" \
    || fallo "guardian.py no compila"
if [ -e "$DROPIN" ]; then
    fallo "ya existe $DROPIN: desinstala antes (desinstalar_guardian.sh) o borralo tu"
fi

TMP=$(mktemp -d /tmp/nav-instalar.XXXXXX)
echo "Temporales en $TMP"
if [ "$SIMULAR" -eq 1 ]; then
    echo "=== SIMULACION: se imprime cada cambio y no se hace ninguno ==="
fi

hacer() {
    echo "+ $*"
    if [ "$SIMULAR" -eq 0 ]; then
        "$@"
    fi
}

escribir() {
    # escribir <ruta> <modo> con el contenido por la entrada estandar
    local ruta=$1 modo=$2 contenido
    contenido=$(cat)
    echo "+ escribir $ruta (root:root $modo):"
    echo "$contenido" | sed 's/^/    | /'
    if [ "$SIMULAR" -eq 0 ]; then
        printf '%s\n' "$contenido" > "$ruta"
        chown root:root "$ruta"
        chmod "$modo" "$ruta"
    fi
}

echo ""
echo "=== 1. La configuracion efectiva de sshd para $AUTOR desde $PC, antes ==="
sshd -T -C "user=$AUTOR,host=$PC,addr=$PC" > "$TMP/sshd_autor_antes.txt"
echo "guardada en $TMP/sshd_autor_antes.txt ($(wc -l < "$TMP/sshd_autor_antes.txt") lineas)"

echo ""
echo "=== 2. La cuenta $CUENTA ==="
if getent passwd "$CUENTA" >/dev/null; then
    echo "la cuenta $CUENTA ya existe; se revisan sus grupos y carpetas"
else
    hacer adduser --disabled-password --gecos "nav-agente (meta 007)" --shell /bin/bash "$CUENTA"
fi
for g in $GRUPOS_PROHIBIDOS; do
    if getent group "$g" >/dev/null && id -nG "$CUENTA" 2>/dev/null | tr ' ' '\n' | grep -qx "$g"; then
        hacer deluser "$CUENTA" "$g"
    fi
done
hacer usermod -aG video "$CUENTA"
hacer chmod 0750 "/home/$CUENTA"
for d in nav nav-wip nav-salidas nav-registro .venvs; do
    hacer install -d -o "$CUENTA" -g "$CUENTA" -m 0750 "/home/$CUENTA/$d"
done
for archivo in /etc/cron.deny /etc/at.deny; do
    if [ -f "$archivo" ] && grep -qx "$CUENTA" "$archivo"; then
        echo "$CUENTA ya esta en $archivo"
    else
        echo "+ anadir $CUENTA a $archivo"
        if [ "$SIMULAR" -eq 0 ]; then
            echo "$CUENTA" >> "$archivo"
            chmod 0644 "$archivo"
        fi
    fi
done
if command -v loginctl >/dev/null; then
    hacer loginctl disable-linger "$CUENTA" || echo "(loginctl disable-linger fallo: la cuenta aun no tiene sesion de logind; no es grave)"
fi

echo ""
echo "=== 2b. El guardian ==="
hacer install -d -o root -g root -m 0755 "$GUARDIAN_DIR"
hacer install -o root -g root -m 0755 "$ORIGEN/guardian.py" "$GUARDIAN"
if [ "$SIMULAR" -eq 0 ]; then
    "$GUARDIAN" --autocomprobar | head -n 1
fi

echo ""
echo "=== 2c. La clave y el drop-in de sshd ==="
hacer install -d -o root -g root -m 0755 "$CLAVES_DIR"
escribir "$CLAVE_DESTINO" 0644 <<EOF
restrict,from="$DESDE" $(cat "$CLAVE")
EOF
escribir "$DROPIN" 0644 <<'EOF'
# nav-guardian (meta 007, fase 2): la cuenta de los agentes solo ejecuta el guardian.
# Lo instala codigo/linux/instalar_guardian.sh; lo quita desinstalar_guardian.sh.
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
EOF

if [ "$SIMULAR" -eq 1 ]; then
    echo ""
    echo "=== 3-5. En la simulacion no se escribe el drop-in, asi que sshd -t, la comparacion y el reload se hacen en la corrida real ==="
    echo "SIMULACION terminada sin cambios."
    exit 0
fi

echo ""
echo "=== 3. sshd -t ==="
if ! sshd -t; then
    rm -f "$DROPIN"
    fallo "sshd -t fallo: se borro $DROPIN y no se recargo ssh"
fi
echo "sshd -t: bien"

echo ""
echo "=== 4. La configuracion efectiva de $AUTOR, despues, comparada ==="
sshd -T -C "user=$AUTOR,host=$PC,addr=$PC" > "$TMP/sshd_autor_despues.txt"
if ! diff "$TMP/sshd_autor_antes.txt" "$TMP/sshd_autor_despues.txt" > "$TMP/sshd_autor_diff.txt"; then
    cat "$TMP/sshd_autor_diff.txt"
    rm -f "$DROPIN"
    fallo "la configuracion efectiva de $AUTOR cambio con el drop-in: se borro $DROPIN y no se recargo ssh"
fi
echo "sin cambios para $AUTOR (0 lineas de diff)"

echo ""
echo "=== 5. systemctl reload ssh ==="
hacer systemctl reload ssh
echo ""
echo "=== La configuracion efectiva de $CUENTA desde $PC ==="
sshd -T -C "user=$CUENTA,host=$PC,addr=$PC" | grep -iE '^(forcecommand|authorizedkeysfile|permittty|disableforwarding|passwordauthentication|kbdinteractiveauthentication|permituserrc|permittunnel|allowagentforwarding|clientaliveinterval|clientalivecountmax|allowtcpforwarding|x11forwarding) ' || true
echo ""
echo "=== Resumen ==="
id "$CUENTA"
ls -l "$GUARDIAN" "$CLAVE_DESTINO" "$DROPIN"
ls -ld "/home/$CUENTA"
echo "grupos prohibidos presentes: $(id -nG "$CUENTA" | tr ' ' '\n' | grep -xE "$(echo "$GRUPOS_PROHIBIDOS" | tr ' ' '|')" | tr '\n' ' ')(ninguno es lo esperado)"
echo "Listo. En el PC: ssh nav-jetson ayuda; y despues probar_barrera.ps1."
