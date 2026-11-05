"""El resumen de un log de `tegrastats` (meta 007 · El tracker en la Jetson Orin Nano,
fase 7 · Las dos camaras a la vez en la Jetson).

`ssh nav-jetson medir tegrastats <s>` deja en `~/nav-salidas/tegrastats_<fecha>_<s>s.txt`
una linea por segundo (`tegrastats --interval 1000`). Esto la lee y da lo que pide el
criterio de la fase 7 (plan, P-7): la CPU media y maxima por nucleo, la RAM p50 y maxima,
la temperatura maxima (y si alguna zona llego al umbral de corte, 90 C), y de paso la GPU,
las frecuencias de CPU y la potencia de cada rail. Solo biblioteca estandar: no abre
camara, red ni nada de la cadena, y corre igual en la Jetson y en el PC.

El formato (Jetson Linux r36.4.4, Developer Guide, «Tegrastats Utility», por Context7;
las lineas reales del escaneo de la fase 1 estan en `tests/data/linux/`):

    10-30-2026 06:34:34 RAM 2695/7620MB (lfb 5x4MB) SWAP 0/12002MB (cached 0MB)
    CPU [0%@729,0%@729,...] GR3D_FREQ 0% cpu@52.531C soc2@51.843C ... tj@55.062C
    VDD_IN 4652mW/4652mW VDD_CPU_GPU_CV 580mW/580mW VDD_SOC 1453mW/1453mW

(en una sola linea). La fecha es MM-DD-AAAA de la hora local de la Jetson. `CPU` va
como `[X%@Z,...]` o `[X%,...]@Z`, con `off` si el nucleo esta apagado (cuenta aparte,
no como 0 %). `GR3D_FREQ` puede llevar `@[Y,...]`. Las temperaturas son `<zona>@<t>C`;
una zona en 0 C o por debajo (los `cv0@0C` del ejemplo de NVIDIA, sin lectura) no
cuenta. Los rails son `<RAIL> <instantanea>mW/<media>mW`; aqui se promedia la
instantanea (en el log del escaneo da lo mismo que la media del propio tegrastats).

Una linea vale si trae RAM, CPU y al menos una temperatura y tiene los mismos nucleos
que la primera; las demas (la orden `$ tegrastats ...`, la ultima cortada por SIGTERM)
se cuentan como descartadas y se dicen. Sin ninguna linea valida, o con la ventana
vacia, sale con 1 (principio 7).

La ventana: `--saltar-s` (el calentamiento del P-7, 60 s) y `--segundos` (300; 0 es
hasta el final) en segundos desde la primera linea valida, por su hora; si una linea no
trae hora, por su indice a 1 s. Si el log no llega al final de la ventana pedida, el
resumen lo dice (`ventana.completa` falso y un AVISO) y da el tramo real. La
temperatura maxima y el corte se dan tambien del log entero.

Uso (desde codigo/, con el venv; en la Jetson por el guardian, tope 60 s, con
`--input` y `--output` bajo `~/nav-salidas/`):

    python -m diagnostics.tegrastats_log --input tests/data/linux/tegrastats_escaneo_fase1.txt
    ssh nav-jetson py wip diagnostics.tegrastats_log --input ~/nav-salidas/tegrastats_<fecha>_390s.txt \\
        --saltar-s 60 --segundos 300 --etiqueta ollama-parado --output ~/nav-salidas/p7/ollama-parado_tegrastats.json

Sale con 0; con 1 si no hay lineas validas, la ventana queda vacia o la salida ya existe.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path

TAG = "[tegrastats_log]"
EXIT_OK = 0
EXIT_ERROR = 1
UMBRAL_CORTE_C = 90.0         # P-7: se corta si alguna zona llega a 90 C
INTERVALO_S = 1.0             # el guardian lanza `tegrastats --interval 1000`
FORMATO_FECHA = "%m-%d-%Y %H:%M:%S"
TEMP_MINIMA_VALIDA_C = 0.0    # <= 0 C: zona sin lectura (cv0@0C, -256C)

_RE_FECHA = re.compile(r"^(\d{2}-\d{2}-\d{4} \d{2}:\d{2}:\d{2})\s")
_RE_RAM = re.compile(r"\bRAM (\d+)/(\d+)MB")
_RE_SWAP = re.compile(r"\bSWAP (\d+)/(\d+)MB")
_RE_CPU = re.compile(r"\bCPU \[([^\]]*)\](?:@(\d+))?")
_RE_NUCLEO = re.compile(r"^(\d+(?:\.\d+)?)%(?:@(\d+))?$")
_RE_GR3D = re.compile(r"\bGR3D_FREQ (\d+(?:\.\d+)?)%")
_RE_TEMP = re.compile(r"(?<![\w%@\[,])([A-Za-z][A-Za-z0-9_]*)@(-?\d+(?:\.\d+)?)C(?![\w])")
_RE_RAIL = re.compile(r"\b([A-Z][A-Z0-9_]*) (\d+)mW/(\d+)mW")


@dataclass
class Muestra:
    """Una linea de tegrastats. `cpu_pct[i]` es None si el nucleo i estaba apagado."""
    t: _dt.datetime | None
    ram_mb: int
    ram_total_mb: int
    swap_mb: int | None
    swap_total_mb: int | None
    cpu_pct: list[float | None]
    cpu_mhz: list[int | None]
    gpu_pct: float | None
    temps_c: dict[str, float] = field(default_factory=dict)
    potencia_mw: dict[str, int] = field(default_factory=dict)


def parsear_linea(linea: str) -> Muestra | None:
    """La muestra de una linea, o None si no es una linea de tegrastats completa."""
    texto = linea.strip()
    ram = _RE_RAM.search(texto)
    cpu = _RE_CPU.search(texto)
    if ram is None or cpu is None:
        return None
    t = None
    fecha = _RE_FECHA.match(texto)
    if fecha is not None:
        try:
            t = _dt.datetime.strptime(fecha.group(1), FORMATO_FECHA)
        except ValueError:
            return None
    mhz_comun = int(cpu.group(2)) if cpu.group(2) else None
    pct: list[float | None] = []
    mhz: list[int | None] = []
    for entrada in cpu.group(1).split(","):
        entrada = entrada.strip()
        if entrada == "off":
            pct.append(None)
            mhz.append(None)
            continue
        m = _RE_NUCLEO.match(entrada)
        if m is None:
            return None
        pct.append(float(m.group(1)))
        mhz.append(int(m.group(2)) if m.group(2) else mhz_comun)
    if not pct:
        return None
    temps = {}
    for nombre, valor in _RE_TEMP.findall(texto):
        v = float(valor)
        if v > TEMP_MINIMA_VALIDA_C:
            temps[nombre] = v
    if not temps:
        return None
    swap = _RE_SWAP.search(texto)
    gr3d = _RE_GR3D.search(texto)
    return Muestra(
        t=t, ram_mb=int(ram.group(1)), ram_total_mb=int(ram.group(2)),
        swap_mb=int(swap.group(1)) if swap else None,
        swap_total_mb=int(swap.group(2)) if swap else None,
        cpu_pct=pct, cpu_mhz=mhz, gpu_pct=float(gr3d.group(1)) if gr3d else None,
        temps_c=temps, potencia_mw={r: int(i) for r, i, _media in _RE_RAIL.findall(texto)})


def parsear(texto: str) -> tuple[list[Muestra], int]:
    """Las muestras validas de un log y cuantas lineas no vacias se descartaron."""
    muestras: list[Muestra] = []
    descartadas = 0
    for linea in texto.splitlines():
        if not linea.strip():
            continue
        m = parsear_linea(linea)
        if m is None or (muestras and len(m.cpu_pct) != len(muestras[0].cpu_pct)):
            descartadas += 1
            continue
        muestras.append(m)
    return muestras, descartadas


def leer(ruta: Path) -> tuple[list[Muestra], int]:
    """`parsear` de un archivo. Lee bytes y decodifica sin fallar: el log es ASCII."""
    return parsear(Path(ruta).read_bytes().decode("utf-8", errors="replace"))


def tiempos_relativos(muestras: list[Muestra]) -> list[float]:
    """Segundos desde la primera muestra: por la hora si todas la traen; si no, por indice."""
    if muestras and all(m.t is not None for m in muestras):
        t0 = muestras[0].t
        return [(m.t - t0).total_seconds() for m in muestras]
    return [i * INTERVALO_S for i in range(len(muestras))]


def ventana(muestras: list[Muestra], saltar_s: float = 0.0,
            segundos: float = 0.0) -> tuple[list[Muestra], dict]:
    """Las muestras con `saltar_s <= t < saltar_s + segundos` (segundos 0: hasta el final)
    y lo que dice de la ventana: lo pedido, lo cubierto y si el log llega al final."""
    if saltar_s < 0 or segundos < 0:
        raise ValueError("--saltar-s y --segundos tienen que ser >= 0")
    rel = tiempos_relativos(muestras)
    fin = saltar_s + segundos if segundos > 0 else float("inf")
    dentro = [(r, m) for r, m in zip(rel, muestras) if saltar_s <= r < fin]
    info: dict = {"saltar_s": float(saltar_s), "segundos": float(segundos),
                  "log_s": rel[-1] if rel else 0.0, "muestras": len(dentro)}
    if dentro:
        info["desde_s"], info["hasta_s"] = dentro[0][0], dentro[-1][0]
    else:
        info["desde_s"] = info["hasta_s"] = None
    # Completa si la ultima muestra queda a menos de 1.5 intervalos del final pedido.
    info["completa"] = bool(dentro) and (segundos == 0 or
                                         (rel[-1] if rel else 0.0) >= fin - 1.5 * INTERVALO_S)
    return [m for _, m in dentro], info


def _media(xs: list[float]) -> float | None:
    return statistics.fmean(xs) if xs else None


def resumir(muestras: list[Muestra], umbral_c: float = UMBRAL_CORTE_C) -> dict:
    """CPU por nucleo (media, maxima, muestras apagado), RAM p50 y maxima, swap, GPU,
    temperatura maxima por zona y global (con si llego a `umbral_c` y cuando) y potencia."""
    if not muestras:
        raise ValueError("sin muestras")
    rel = tiempos_relativos(muestras)
    huecos = sum(1 for a, b in zip(rel, rel[1:]) if b - a > 1.5 * INTERVALO_S)
    n_nucleos = len(muestras[0].cpu_pct)
    nucleos = []
    todas: list[float] = []
    for i in range(n_nucleos):
        xs = [m.cpu_pct[i] for m in muestras if m.cpu_pct[i] is not None]
        fs = [m.cpu_mhz[i] for m in muestras if m.cpu_mhz[i] is not None]
        todas += xs
        nucleos.append({"nucleo": i, "media_pct": _media(xs), "max_pct": max(xs) if xs else None,
                        "apagado": len(muestras) - len(xs), "max_mhz": max(fs) if fs else None})
    ram = [m.ram_mb for m in muestras]
    swap = [m.swap_mb for m in muestras if m.swap_mb is not None]
    gpu = [m.gpu_pct for m in muestras if m.gpu_pct is not None]
    zonas: dict[str, float] = {}
    for m in muestras:
        for z, v in m.temps_c.items():
            zonas[z] = max(v, zonas.get(z, v))
    zona_max = max(zonas, key=lambda z: zonas[z])        # el primero si empatan
    cruce = next(((r, m) for r, m in zip(rel, muestras)
                  if max(m.temps_c.values()) >= umbral_c), None)
    rails: dict[str, list[int]] = {}
    for m in muestras:
        for r, v in m.potencia_mw.items():
            rails.setdefault(r, []).append(v)
    return {
        "muestras": len(muestras),
        "inicio": muestras[0].t.isoformat(sep=" ") if muestras[0].t else None,
        "fin": muestras[-1].t.isoformat(sep=" ") if muestras[-1].t else None,
        "span_s": rel[-1] - rel[0],
        "huecos": huecos,
        "cpu": {"nucleos": nucleos, "media_pct": _media(todas), "max_pct": max(todas) if todas else None},
        "ram_mb": {"p50": statistics.median(ram), "max": max(ram), "total": muestras[0].ram_total_mb},
        "swap_mb": {"max": max(swap) if swap else None, "total": muestras[0].swap_total_mb},
        "gpu_pct": {"media": _media(gpu), "max": max(gpu) if gpu else None},
        "temp_c": {"max": zonas[zona_max], "zona_max": zona_max, "por_zona": zonas,
                   "umbral": float(umbral_c), "llego_al_umbral": cruce is not None,
                   "primer_cruce_s": cruce[0] if cruce else None},
        "potencia_mw": {r: {"media": statistics.fmean(v), "max": max(v)} for r, v in rails.items()},
    }


def analizar(ruta: Path, saltar_s: float = 0.0, segundos: float = 0.0,
             umbral_c: float = UMBRAL_CORTE_C, etiqueta: str | None = None) -> dict:
    """Todo para un log: la ventana pedida y, del log entero, la temperatura y el corte."""
    muestras, descartadas = leer(ruta)
    if not muestras:
        raise ValueError(f"{ruta}: ninguna linea de tegrastats valida ({descartadas} descartadas)")
    dentro, info = ventana(muestras, saltar_s, segundos)
    if not dentro:
        raise ValueError(f"{ruta}: la ventana desde {saltar_s:g} s queda vacia "
                         f"(el log dura {info['log_s']:g} s)")
    entero = resumir(muestras, umbral_c)
    return {"archivo": str(ruta), "etiqueta": etiqueta, "lineas_validas": len(muestras),
            "descartadas": descartadas, "ventana": info, "resumen": resumir(dentro, umbral_c),
            "log_entero": {"muestras": entero["muestras"], "span_s": entero["span_s"],
                           "huecos": entero["huecos"], "temp_c": entero["temp_c"]}}


def _f(x: float | None, nd: int = 1) -> str:
    return "-" if x is None else f"{x:.{nd}f}"


def formato_texto(res: dict) -> str:
    """El resumen legible: lo que se pega en el reporte del P-7."""
    r, v, e = res["resumen"], res["ventana"], res["log_entero"]
    hasta = "el final" if v["segundos"] == 0 else f"{v['saltar_s'] + v['segundos']:g} s"
    lineas = [
        f"{TAG} {res['archivo']}" + (f" ({res['etiqueta']})" if res["etiqueta"] else ""),
        f"{TAG} {res['lineas_validas']} lineas validas, {res['descartadas']} descartadas; "
        f"log de {e['span_s']:g} s con {e['huecos']} huecos",
        f"{TAG} ventana {v['saltar_s']:g} s -> {hasta}: {r['muestras']} muestras "
        f"({_f(v['desde_s'], 0)}-{_f(v['hasta_s'], 0)} s; {r['inicio'] or '-'} a {r['fin'] or '-'})",
    ]
    if not v["completa"]:
        lineas.append(f"{TAG} AVISO: el log no llega al final de la ventana pedida "
                      f"(dura {v['log_s']:g} s): el resumen es del tramo real")
    c = r["cpu"]
    lineas.append(f"{TAG} CPU media {_f(c['media_pct'])} %, max {_f(c['max_pct'], 0)} % (todos los nucleos)")
    lineas.append(f"{TAG} CPU por nucleo (media/max %, max MHz): " + "; ".join(
        f"{n['nucleo']}: {_f(n['media_pct'])}/{_f(n['max_pct'], 0)} @{n['max_mhz'] or '-'}"
        + (f" ({n['apagado']} apagado)" if n["apagado"] else "") for n in c["nucleos"]))
    lineas.append(f"{TAG} RAM p50 {r['ram_mb']['p50']:g} MB, max {r['ram_mb']['max']} MB de "
                  f"{r['ram_mb']['total']}; swap max {r['swap_mb']['max']} MB; "
                  f"GPU media {_f(r['gpu_pct']['media'])} %, max {_f(r['gpu_pct']['max'], 0)} %")
    t = r["temp_c"]
    lineas.append(f"{TAG} temperatura max {t['max']:.1f} C ({t['zona_max']}); por zona: "
                  + ", ".join(f"{z} {x:.1f}" for z, x in t["por_zona"].items()))
    te = e["temp_c"]
    corte = (f"SI, a los {te['primer_cruce_s']:g} s del log" if te["llego_al_umbral"] else "no")
    lineas.append(f"{TAG} log entero: temperatura max {te['max']:.1f} C ({te['zona_max']}); "
                  f"llego a {te['umbral']:g} C: {corte}")
    if r["potencia_mw"]:
        lineas.append(f"{TAG} potencia (media/max mW): " + "; ".join(
            f"{k} {p['media']:.0f}/{p['max']}" for k, p in r["potencia_mw"].items()))
    return "\n".join(lineas)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Resume un log de tegrastats: CPU por nucleo, RAM, temperatura (meta 007, fase 7).")
    ap.add_argument("--input", required=True, type=Path, help="el log de `medir tegrastats`")
    ap.add_argument("--saltar-s", type=float, default=0.0,
                    help="segundos del principio que no cuentan (el calentamiento; defecto 0)")
    ap.add_argument("--segundos", type=float, default=0.0,
                    help="duracion de la ventana tras --saltar-s (defecto 0: hasta el final)")
    ap.add_argument("--umbral-c", type=float, default=UMBRAL_CORTE_C,
                    help=f"temperatura de corte que se comprueba (defecto {UMBRAL_CORTE_C:g})")
    ap.add_argument("--etiqueta", default=None, help="nombre de la condicion (p. ej. ollama-parado)")
    ap.add_argument("--output", type=Path, default=None, help="JSON con el resumen (no se pisa)")
    args = ap.parse_args(argv)
    if args.saltar_s < 0 or args.segundos < 0:
        ap.error("--saltar-s y --segundos tienen que ser >= 0")
    if args.output is not None and args.output.exists():
        print(f"{TAG} ERROR: la salida ya existe, no se pisa: {args.output}", file=sys.stderr)
        return EXIT_ERROR
    try:
        res = analizar(args.input, args.saltar_s, args.segundos, args.umbral_c, args.etiqueta)
    except (ValueError, OSError) as e:
        print(f"{TAG} ERROR: {e}", file=sys.stderr)
        return EXIT_ERROR
    print(formato_texto(res))
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{TAG} guardado {args.output}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
