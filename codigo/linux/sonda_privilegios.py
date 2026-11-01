"""La sonda de privilegios: lo que haria un codigo del agente que intentara salirse (meta 007, fase 2).

Se lanza como la cuenta `navagente` en la Jetson (la primera vez el autor, con
`sudo -u navagente python3 -I sonda_privilegios.py`; desde la fase 3, `py wip linux.sonda_privilegios`)
y comprueba, con acciones inofensivas, que la cuenta no tiene ningun privilegio: `sudo -n true`
falla, no esta en los grupos que equivalen a root, no puede escribir fuera de su carpeta, un
`touch` en /etc falla (si no falla, lo borra y lo marca como fallo), `crontab -l` esta negado por
cron.deny, no tiene linger de systemd y `systemctl restart` de un servicio se le niega.

Salida: un JSON con cada comprobacion ({nombre, esperado, obtenido, pasa}) y el total. El codigo de
salida es 0 solo si ninguna comprobacion encuentra un privilegio. Solo biblioteca estandar y
Python >= 3.8 (corre con el python3 del sistema y con el venv).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

GRUPOS_PROHIBIDOS = ("sudo", "admin", "docker", "lxd", "adm", "disk")
RUTAS_SIN_ESCRITURA = ("/etc", "/usr", "/usr/local/bin", "/boot", "/opt", "/var/lib/nvpmodel",
                       "/etc/systemd/system", "/var/run/docker.sock", "/dev/nvme0n1", "/dev/mmcblk0",
                       "/etc/ssh/authorized_keys/navagente", "/usr/local/lib/nav-guardian/guardian")
ETC = Path("/etc")
TOPE_S = 10.0


def _ejecutar(argv: list) -> tuple:
    """(codigo, texto) de una orden con tope; 127 si no existe el programa."""
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=TOPE_S,
                           stdin=subprocess.DEVNULL)
    except FileNotFoundError:
        return 127, "no existe el programa"
    except subprocess.TimeoutExpired:
        return 124, "tope"
    texto = (r.stdout + r.stderr).strip().replace("\n", " | ")
    return r.returncode, texto[:300]


def _grupos() -> list:
    codigo, texto = _ejecutar(["id", "-nG"])
    if codigo == 0:
        return sorted(texto.split())
    try:
        import grp
        import pwd
        nombre = pwd.getpwuid(os.getuid()).pw_name
        return sorted(g.gr_name for g in grp.getgrall() if nombre in g.gr_mem)
    except Exception:  # noqa: BLE001 - sin id ni grp no hay grupos que mirar
        return []


def comprobar(ejecutar=_ejecutar, acceso=os.access, grupos=None, uid=None, etc=None,
              usuario=None, abrir=open, rutas=None) -> list:
    """Cada comprobacion como {nombre, esperado, obtenido, pasa}. Los parametros son para probarla
    sin Jetson; por defecto mira el sistema real."""
    etc = Path(etc) if etc is not None else ETC
    rutas = RUTAS_SIN_ESCRITURA if rutas is None else tuple(rutas)
    uid = os.getuid() if uid is None and hasattr(os, "getuid") else (uid if uid is not None else -1)
    usuario = usuario or os.environ.get("USER") or os.environ.get("LOGNAME") or "?"
    grupos = sorted(grupos) if grupos is not None else _grupos()
    r = []

    def anota(nombre: str, esperado: str, obtenido: str, pasa: bool) -> None:
        r.append({"nombre": nombre, "esperado": esperado, "obtenido": obtenido, "pasa": bool(pasa)})

    codigo, texto = ejecutar(["sudo", "-n", "true"])
    anota("sudo -n true falla", "codigo != 0", f"codigo {codigo}: {texto}", codigo != 0)

    anota("uid no es 0", "uid != 0", f"uid {uid}", uid != 0)

    for g in GRUPOS_PROHIBIDOS:
        anota(f"no esta en el grupo {g}", f"{g} fuera de los grupos", ", ".join(grupos) or "(ninguno)",
              g not in grupos)

    for ruta in rutas:
        if not os.path.exists(ruta):
            anota(f"sin escritura en {ruta}", "no existe o W_OK falso", "no existe", True)
            continue
        puede = acceso(ruta, os.W_OK)
        anota(f"sin escritura en {ruta}", "W_OK falso", f"W_OK {puede}", not puede)

    marca = etc / f"nav-sonda-{os.getpid()}"
    try:
        with abrir(marca, "x") as f:
            f.write("sonda\n")
    except PermissionError as e:
        anota("touch en /etc falla", "PermissionError", f"PermissionError: {e.strerror}", True)
    except OSError as e:
        anota("touch en /etc falla", "PermissionError", f"{type(e).__name__}: {e}", True)
    else:
        try:
            marca.unlink()
            detalle = "se creo (y se borro)"
        except OSError as e:
            detalle = f"se creo y no se pudo borrar: {e}"
        anota("touch en /etc falla", "PermissionError", detalle, False)

    codigo, texto = ejecutar(["crontab", "-l"])
    anota("crontab -l negado", "codigo != 0 (cron.deny)", f"codigo {codigo}: {texto}", codigo != 0)

    for archivo in ("cron.deny", "at.deny"):
        ruta = etc / archivo
        try:
            lineas = ruta.read_text(encoding="utf-8", errors="replace").split()
            esta = usuario in lineas
            anota(f"{usuario} en /etc/{archivo}", "presente", "presente" if esta else "ausente", esta)
        except OSError as e:
            anota(f"{usuario} en /etc/{archivo}", "presente", f"no se pudo leer: {e}", False)

    codigo, texto = ejecutar(["loginctl", "show-user", usuario, "-p", "Linger"])
    sin_linger = codigo != 0 or "Linger=no" in texto
    anota("sin linger de systemd", "Linger=no o sin sesion de logind", f"codigo {codigo}: {texto}",
          sin_linger)

    codigo, texto = ejecutar(["systemctl", "--no-ask-password", "restart",
                              "nav-sonda-inexistente.service"])
    anota("systemctl restart negado", "codigo != 0", f"codigo {codigo}: {texto}", codigo != 0)

    codigo, texto = ejecutar(["docker", "ps"])
    anota("docker ps negado", "codigo != 0 o sin docker", f"codigo {codigo}: {texto}", codigo != 0)

    return r


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Sonda de privilegios de la cuenta del agente en la Jetson.")
    parser.add_argument("--salida", default="-", help="archivo JSON de salida; - es la salida estandar")
    args = parser.parse_args(argv)
    resultados = comprobar()
    fallos = [c for c in resultados if not c["pasa"]]
    informe = {"comprobaciones": len(resultados), "privilegios_encontrados": len(fallos),
               "usuario": os.environ.get("USER") or os.environ.get("LOGNAME") or "?",
               "python": sys.version.split()[0], "detalle": resultados}
    texto = json.dumps(informe, indent=1, ensure_ascii=False) + "\n"
    if args.salida == "-":
        sys.stdout.write(texto)
    else:
        Path(args.salida).write_text(texto, encoding="utf-8")
    print(f"sonda: {len(fallos)} privilegios encontrados en {len(resultados)} comprobaciones",
          file=sys.stderr)
    return 0 if not fallos else 1


if __name__ == "__main__":
    sys.exit(main())
