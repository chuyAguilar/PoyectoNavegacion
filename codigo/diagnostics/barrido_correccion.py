"""El barrido de `error_correction_rate` del detector del tracker (meta 006 · Grafo de
factores optico-inercial, fase 7d2 · Los IDs falsos del tablero en el detector del tracker;
B39, P66, P69). Fuera de la cadena: no abre camara ni red, no importa `vision.tracking`.

El problema (medido en la fase 7d): con `errorCorrectionRate` 0.6, el valor por defecto de
OpenCV y el de los perfiles (no lo fijan), el detector acepta un candidato a 7 bits de un ID
de `DICT_ARUCO_MIP_36h12` (`maxCorrectionBits` 12), y cada marcador `DICT_4X4_50` del
tablero ChArUco es un candidato con borde negro: salen IDs fantasma, a veces el de la
referencia. Bajar la tasa los quita y puede perder lecturas de la referencia real inclinada.
Este modulo mide las dos cosas, tasa por tasa, sobre carpetas de frames grabados
(`tracker --record --save-frames`, los PNG en gris que vio el detector), y elige con una
regla fijada antes de mirar los numeros (P69). Mide una variable: solo la tasa; el resto del
detector es el del perfil (`vision.detection.create_detector`, no se copia).

- `bits_efectivos`: cuantos bits corrige una tasa, `int(maxCorrectionBits * tasa)`.
- `detector_con_tasa`: el detector del perfil con esa tasa y nada mas cambiado.
- `leer_frame`: lo que lee un detector en un frame, SIN lista blanca: cuantas veces el ID de
  la referencia, con sus esquinas, y los IDs ajenos.
- `barrer` / `barrer_carpetas`: por categoria (`referencia`, `tablero`,
  `tablero_con_referencia`) y tasa, los frames, la referencia una vez o repetida, los
  fantasmas, y frente a la tasa de hoy (`BASE`) los frames perdidos y ganados y la
  diferencia de esquinas en los que leen las dos.
- `elegir`: la regla de P69 con P74. La tasa mas alta con 0 fantasmas en todos los frames
  (las tres categorias, tambien la referencia sola; reales y sinteticos), 0 frames con el ID
  de la referencia repetido y una perdida <= `PERDIDA_MAX` de los frames reales en que
  `BASE` lee la referencia. Si ninguna cumple, `None` (no se cambia nada y se replantea).
- `perfil_con_tasa`: la copia temporal de un perfil con esa tasa en `markers.detector`.

La regla mide el detector, no lo publicado: los repetidos se cuentan con `leer_frame`, que
llama a `detectMarkers` sin lista blanca ni `MarkerTracker`; el filtro de la fase 7d2b (un ID
repetido no se publica) no le llega, y una prueba comprueba que este modulo no lo importa.

Uso (desde codigo\\, con el venv y los argumentos explicitos, principio 7):

    python -m diagnostics.barrido_correccion barrer --config profiles\\tracker_config_gs1.yaml ^
        --id 100 --referencia <P5 gs1> <P5 gs2> --tablero <P6 gs1> <P6 gs2> ^
        --tablero-con-referencia <P7 gs1> <P7 gs2> ^
        --sinteticos "..\\Claude outputs\\fases\\006\\fase-7d2\\sinteticos.json" ^
        --salida <carpeta nueva> --timeout 900
    python -m diagnostics.barrido_correccion perfil --base profiles\\tracker_config_gs1.yaml ^
        --tasa 0.30 --salida <carpeta>\\gs1.yaml

`barrer` escribe `barrido.json` (la clave `elegida` es la tasa, o `null`; `regla`, la de
`elegir`) y `barrido.md` (la
tabla tasa x categoria y la elegida con su porque). Codigos: 0 eligio; 1 ninguna cumple; 2
entrada mala o la salida ya existe; 4 salto el tope (escribe lo hecho y no elige). `perfil`:
0 o 2; no escribe dentro de `codigo/profiles/` ni pisa nada.

Context7 (2026-11-11, `/websites/opencv`, documentacion 5.0; instalado 4.11.0):
`DetectorParameters.errorCorrectionRate` (0.6 por defecto) escala
`Dictionary.maxCorrectionBits`: se corrigen `maxCorrectionBits * errorCorrectionRate` bits;
«util para reducir la capacidad de correccion y evitar falsos positivos».
`ArucoDetector.detectMarkers(image) -> corners, ids, rejected`, en el mismo orden. Medido en
esta fase con `Dictionary.identify(bits, tasa)`: el producto se trunca (0.45 -> 5 bits).
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import io
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Sequence

import cv2
import numpy as np
import yaml

import profiles
from vision.detection import create_detector, get_dictionary

TAG = "[barrido]"
EXIT_OK = 0
EXIT_NINGUNA = 1
EXIT_USO = 2
EXIT_TOPE = 4
FORMATO = 1

TASAS = (0.60, 0.50, 0.45, 0.40, 0.30, 0.20)      # 7, 6, 5, 4, 3 y 2 bits con 36h12
BASE = 0.60                                       # la de hoy: el valor por defecto de OpenCV
PERDIDA_MAX = 0.01                                # P69
REGLA = "P69, P74"                                # la regla de `elegir`; va en barrido.json
CATEGORIAS = ("referencia", "tablero", "tablero_con_referencia")
CATEGORIAS_TABLERO = ("tablero", "tablero_con_referencia")
CLAVE_YAML = "error_correction_rate"
MAX_NOMBRES = 40                                  # cuantos nombres de frame guarda cada lista
AVISO_CADA = 100                                  # frames entre dos lineas de avance

_RE_CLAVE = re.compile(r"^(?P<sangria>[ ]*)(?P<clave>[A-Za-z_][A-Za-z0-9_]*):(?P<resto>.*)$")
_RE_VALOR = re.compile(r"^(?P<espacio>\s*)(?P<valor>.*?)(?P<coment>\s+#.*)?$")


def clave_tasa(tasa: float) -> str:
    """La tasa como clave de los diccionarios del barrido (y del JSON): `0.30`."""
    return f"{float(tasa):.2f}"


def _comprobar_tasa(tasa: float) -> float:
    if isinstance(tasa, bool) or not isinstance(tasa, (int, float, np.integer, np.floating)) \
            or not 0.0 < float(tasa) <= 1.0:
        raise ValueError(f"la tasa tiene que estar en (0, 1], no {tasa!r}")
    return float(tasa)


def bits_efectivos(diccionario: str, tasa: float) -> int:
    """Los bits que el detector corrige al identificar un candidato de `diccionario` con
    `errorCorrectionRate = tasa`: `int(maxCorrectionBits * tasa)`, leido del diccionario
    (12 en `DICT_ARUCO_MIP_36h12`: 7 bits con 0.60, 3 con 0.30). ValueError si la tasa no
    esta en (0, 1]."""
    t = _comprobar_tasa(tasa)
    return int(int(get_dictionary(diccionario).maxCorrectionBits) * t)


def detector_con_tasa(cfg_markers: dict, tasa: float):
    """El `ArucoDetector` del tracker para `cfg_markers` (la seccion `markers` de un perfil)
    con `detector.error_correction_rate = tasa` y nada mas cambiado. Trabaja sobre una copia:
    `cfg_markers` sale igual. Comprueba que el detector quedo con esa tasa."""
    t = _comprobar_tasa(tasa)
    cfg = copy.deepcopy(dict(cfg_markers))
    det = dict(cfg.get("detector") or {})
    det[CLAVE_YAML] = t
    cfg["detector"] = det
    with contextlib.redirect_stdout(io.StringIO()):         # create_detector imprime cada parametro
        detector = create_detector(cfg)
    leida = float(detector.getDetectorParameters().errorCorrectionRate)
    if leida != t:
        raise RuntimeError(f"el detector quedo con errorCorrectionRate {leida}, no {t}")
    return detector


def leer_frame(gray: np.ndarray, detector, id_ref: int) -> dict:
    """Lo que `detector` lee en `gray`, sin lista blanca: `n_ref` (cuantas detecciones del
    ID `id_ref`), `esquinas_ref` (sus esquinas, un array (4, 2) float32 por deteccion, en el
    orden del detector) y `ajenos` (los demas IDs leidos, con repeticion y ordenados)."""
    corners, ids, _rechazados = detector.detectMarkers(gray)
    esquinas_ref: list[np.ndarray] = []
    ajenos: list[int] = []
    if ids is not None:
        for k, mid in enumerate(ids.flatten().tolist()):
            if int(mid) == int(id_ref):
                esquinas_ref.append(np.asarray(corners[k], dtype=np.float32).reshape(4, 2))
            else:
                ajenos.append(int(mid))
    return {"n_ref": len(esquinas_ref), "esquinas_ref": esquinas_ref, "ajenos": sorted(ajenos)}


def _vacio() -> dict:
    return {"frames": 0, "ref_una": 0, "ref_doble": 0, "ref_detecciones": 0, "ajenos": 0, "frames_con_ajenos": 0,
            "fantasmas": 0, "frames_con_fantasma": 0, "fantasmas_id_ref": 0, "ajenos_por_id": {},
            "base_lee": 0, "perdidos": 0, "ganados": 0, "perdida": None, "comunes": 0, "frames_dif": 0,
            "max_dif_px": 0.0, "frames_fantasma": [], "frames_doble": [], "frames_perdidos": []}


def _apuntar(lista: list, nombre: str) -> None:
    if len(lista) < MAX_NOMBRES:
        lista.append(nombre)


def _sumar(s: dict, categoria: str, nombre: str, lectura: dict, base: dict) -> None:
    """Suma a `s` (la celda categoria x tasa) lo leido en un frame; `base` es lo leido con `BASE`."""
    n_ref, ajenos = int(lectura["n_ref"]), lectura["ajenos"]
    s["frames"] += 1
    s["ref_detecciones"] += n_ref
    if n_ref == 1:
        s["ref_una"] += 1
    elif n_ref >= 2:
        s["ref_doble"] += 1
        _apuntar(s["frames_doble"], nombre)
    s["ajenos"] += len(ajenos)
    s["frames_con_ajenos"] += 1 if ajenos else 0
    for mid in ajenos:
        s["ajenos_por_id"][str(mid)] = s["ajenos_por_id"].get(str(mid), 0) + 1
    # Fantasma: una deteccion que no es la referencia de verdad. Con el tablero solo, todas
    # (tambien las del ID de la referencia); con la referencia a la vista, los IDs ajenos y
    # las copias de mas del ID de la referencia.
    de_ref = n_ref if categoria == "tablero" else max(0, n_ref - 1)
    fantasmas = len(ajenos) + de_ref
    s["fantasmas"] += fantasmas
    s["fantasmas_id_ref"] += de_ref
    if fantasmas:
        s["frames_con_fantasma"] += 1
        _apuntar(s["frames_fantasma"], nombre)
    # Frente a la tasa de hoy
    lee, lee_base = n_ref >= 1, int(base["n_ref"]) >= 1
    s["base_lee"] += 1 if lee_base else 0
    if lee_base and not lee:
        s["perdidos"] += 1
        _apuntar(s["frames_perdidos"], nombre)
    if lee and not lee_base:
        s["ganados"] += 1
    if n_ref == 1 and int(base["n_ref"]) == 1:
        s["comunes"] += 1
        dif = float(np.max(np.abs(lectura["esquinas_ref"][0].astype(np.float64)
                                  - base["esquinas_ref"][0].astype(np.float64))))
        if dif > 0.0:
            s["frames_dif"] += 1
        s["max_dif_px"] = max(s["max_dif_px"], dif)


def barrer(grupos: Mapping[str, Iterable[tuple[str, np.ndarray]]], cfg_markers: dict, id_ref: int,
           tasas: Sequence[float] = TASAS) -> dict:
    """El barrido sobre frames en memoria. `grupos` da, por categoria (`CATEGORIAS`), los
    frames como `(nombre, gris)`; se recorren una vez, en orden, sin guardarlos.

    Devuelve, por categoria y tasa (`categorias[cat]["por_tasa"][clave_tasa(t)]`):
    `frames`; `ref_una` y `ref_doble` (frames con el ID `id_ref` una vez / dos o mas);
    `fantasmas` y `frames_con_fantasma` (con el tablero solo, toda deteccion; con la
    referencia a la vista, los IDs ajenos y las copias de mas de `id_ref`), `fantasmas_id_ref`
    (cuantos de ellos llevan el ID de la referencia) y `ajenos_por_id`; y frente a `BASE`:
    `base_lee` (frames en que `BASE` lee la referencia), `perdidos`, `ganados`, `perdida`
    (`perdidos / base_lee`, `None` sin frames), `comunes` (frames con la referencia una vez
    con las dos tasas), `max_dif_px` y `frames_dif` (la diferencia de sus esquinas). Los
    nombres de los frames con fantasmas, con repetidos y perdidos van en listas de hasta
    `MAX_NOMBRES`. `BASE` se mide siempre, aunque no este en `tasas`.
    """
    desconocidas = sorted(set(grupos) - set(CATEGORIAS))
    if desconocidas:
        raise ValueError(f"categorias desconocidas {desconocidas}; validas: {list(CATEGORIAS)}")
    pedidas = [_comprobar_tasa(t) for t in tasas]
    if not pedidas:
        raise ValueError("sin tasas que barrer")
    if len({clave_tasa(t) for t in pedidas}) != len(pedidas):
        raise ValueError(f"hay tasas repetidas: {pedidas}")
    todas = sorted({*pedidas, BASE}, reverse=True)
    diccionario = str(cfg_markers["dictionary"])
    detectores = {t: detector_con_tasa(cfg_markers, t) for t in todas}
    out = {"formato": FORMATO, "id_ref": int(id_ref), "base": BASE, "tasas": todas,
           "bits": {clave_tasa(t): bits_efectivos(diccionario, t) for t in todas},
           "diccionario": diccionario, "detector": dict(cfg_markers.get("detector") or {}),
           "opencv": cv2.__version__, "categorias": {}}
    for cat in CATEGORIAS:
        celdas = {clave_tasa(t): _vacio() for t in todas}
        n = 0
        for nombre, gray in grupos.get(cat, ()):
            if not isinstance(gray, np.ndarray) or gray.ndim != 2 or gray.dtype != np.uint8:
                raise ValueError(f"{nombre}: no es una imagen en gris de 8 bits")
            lecturas = {t: leer_frame(gray, detectores[t], id_ref) for t in todas}
            for t in todas:
                _sumar(celdas[clave_tasa(t)], cat, str(nombre), lecturas[t], lecturas[BASE])
            n += 1
        for s in celdas.values():
            s["perdida"] = (s["perdidos"] / s["base_lee"]) if s["base_lee"] else None
            s["ajenos_por_id"] = dict(sorted(s["ajenos_por_id"].items(), key=lambda kv: (-kv[1], int(kv[0]))))
        out["categorias"][cat] = {"frames": n, "por_tasa": celdas}
    return out


def frames_de(carpeta: Path) -> list[Path]:
    """Los `frame_*.png` de `carpeta`, ordenados."""
    return sorted(Path(carpeta).glob("frame_*.png"))


def barrer_carpetas(carpetas: Mapping[str, Sequence[Path]], cfg_markers: dict, id_ref: int,
                    tasas: Sequence[float], tope_s: float) -> dict:
    """`barrer` sobre los `frame_*.png` (en gris) de las carpetas de cada categoria. El
    nombre de cada frame es `<carpeta>/<archivo>`. Si pasan `tope_s` segundos, para con lo
    hecho y lo dice (principio 9): `completo` False y `frames_sin_leer`. ValueError si una
    carpeta no tiene frames o un PNG no es una imagen en gris."""
    if not tope_s > 0:
        raise ValueError(f"el tope tiene que ser > 0 s, no {tope_s}")
    listas: dict[str, list[Path]] = {}
    for cat, dirs in carpetas.items():
        listas[cat] = []
        for d in dirs:
            pngs = frames_de(Path(d))
            if not pngs:
                raise ValueError(f"no hay frame_*.png en {d}")
            listas[cat].extend(pngs)
    total = sum(len(v) for v in listas.values())
    estado = {"leidos": 0, "tope": False}
    t0 = time.monotonic()

    def _frames(cat: str) -> Iterator[tuple[str, np.ndarray]]:
        for k, png in enumerate(listas[cat]):
            if estado["tope"] or time.monotonic() - t0 > tope_s:
                if not estado["tope"]:
                    print(f"{TAG} TOPE de {tope_s:g} s: se para en {cat}, frame {k} de {len(listas[cat])} "
                          f"({estado['leidos']} de {total} leidos)", flush=True)
                estado["tope"] = True
                return
            gray = cv2.imread(str(png), cv2.IMREAD_UNCHANGED)
            if gray is None or gray.ndim != 2 or gray.dtype != np.uint8:
                raise ValueError(f"{png}: no es una imagen en gris de 8 bits")
            estado["leidos"] += 1
            if estado["leidos"] % AVISO_CADA == 0:
                print(f"{TAG} {estado['leidos']} de {total} frames ({cat}), {time.monotonic() - t0:.0f} s", flush=True)
            yield f"{png.parent.name}/{png.name}", gray

    out = barrer({cat: _frames(cat) for cat in listas}, cfg_markers, id_ref, tasas)
    out["carpetas"] = {cat: [str(Path(d)) for d in dirs] for cat, dirs in carpetas.items()}
    out["completo"] = not estado["tope"]
    out["frames_sin_leer"] = total - estado["leidos"]
    out["tope_s"] = float(tope_s)
    out["segundos"] = round(time.monotonic() - t0, 3)
    return out


def _celda(barrido: dict | None, cat: str, clave: str) -> dict | None:
    if not barrido:
        return None
    return ((barrido.get("categorias") or {}).get(cat) or {}).get("por_tasa", {}).get(clave)


def elegir(real: dict, sintetico: dict | None, perdida_max: float = PERDIDA_MAX) -> tuple[float | None, list[str]]:
    """La regla de P69 (con P74) sobre dos resultados de `barrer`: `real` (los frames de la
    sesion) y `sintetico` (o `None`). Elige la tasa mas alta de `real["tasas"]` que cumpla
    las tres:

    1. 0 fantasmas de cualquier ID en todos los frames de las tres categorias (tambien los
       de la referencia sola, P74), reales y sinteticos; un fantasma en un solo frame la
       descarta;
    2. 0 frames con el ID de la referencia dos o mas veces, en cualquier categoria;
    3. en `referencia` real, `perdidos <= perdida_max * base_lee` (los frames en que `BASE`
       lee la referencia y esta tasa no).

    Sin frames reales de alguna de las tres categorias, con un barrido sintetico sin frames
    del tablero o con un barrido cortado por el tope, la regla no se puede comprobar y
    ninguna cumple. La perdida sintetica no decide; un barrido sintetico sin frames de la
    referencia sola no falla (esos, los da la sesion).
    Devuelve `(tasa | None, razones)`: una linea por tasa con lo que cumple o por que cae.
    """
    if not 0.0 <= float(perdida_max) < 1.0:
        raise ValueError(f"perdida_max tiene que estar en [0, 1), no {perdida_max!r}")
    razones: list[str] = []
    elegida: float | None = None
    incompleto = real.get("completo", True) is False or (sintetico or {}).get("completo", True) is False
    for t in sorted((float(x) for x in real["tasas"]), reverse=True):
        clave = clave_tasa(t)
        bits = (real.get("bits") or {}).get(clave, "?")
        fallos: list[str] = []
        bien: list[str] = []
        if incompleto:
            fallos.append("el barrido se corto por el tope: no se elige con frames sin leer")
        n_frames = 0
        for origen, b in (("reales", real), ("sinteticos", sintetico)):
            if b is None:
                continue
            for cat in CATEGORIAS:
                c = _celda(b, cat, clave)
                if c is None or not c["frames"]:
                    if origen == "reales":
                        fallos.append(f"sin frames reales de '{cat}': la regla no se puede comprobar")
                    elif cat in CATEGORIAS_TABLERO:
                        fallos.append(f"el barrido sintetico no trae la tasa {clave} en '{cat}'" if c is None
                                      else f"el barrido sintetico no trae frames de '{cat}'")
                    continue
                n_frames += c["frames"]
                if c["fantasmas"]:                          # en cualquier categoria (P74)
                    fallos.append(f"{c['fantasmas']} fantasmas en {c['frames_con_fantasma']} de {c['frames']} frames "
                                  f"{origen} de '{cat}' ({c['fantasmas_id_ref']} con el ID de la referencia)")
                if c["ref_doble"]:
                    fallos.append(f"el ID de la referencia dos o mas veces en {c['ref_doble']} de {c['frames']} frames "
                                  f"{origen} de '{cat}'")
        ref = _celda(real, "referencia", clave)
        if ref is not None and ref["frames"]:
            if not ref["base_lee"]:
                fallos.append(f"la tasa {clave_tasa(BASE)} no lee la referencia en ningun frame real de 'referencia': "
                              f"la perdida no se puede medir")
            else:
                pct = 100.0 * ref["perdidos"] / ref["base_lee"]
                texto = f"perdida {pct:.2f} % ({ref['perdidos']} de {ref['base_lee']} frames reales; ganados {ref['ganados']})"
                if ref["perdidos"] > float(perdida_max) * ref["base_lee"] + 1e-9:
                    fallos.append(f"{texto} > {100.0 * float(perdida_max):.2f} %")
                else:
                    bien.append(texto)
        if fallos:
            razones.append(f"{clave} ({bits} bits): no cumple: " + "; ".join(fallos))
            continue
        razones.append(f"{clave} ({bits} bits): cumple: 0 fantasmas en {n_frames} frames (las tres categorias), 0 repetidos, "
                       + "; ".join(bien) + ("" if sintetico is not None else "; sin barrido sintetico"))
        if elegida is None:
            elegida = t
    razones.append(f"elegida: {clave_tasa(elegida)}" if elegida is not None
                   else "elegida: ninguna (no se cambia nada y se replantea, P69)")
    return elegida, razones


def _sha256(ruta: Path) -> str:
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


def _bloque_detector(lineas: list[str]) -> tuple[int, int | None, int]:
    """En las lineas de un perfil: (indice de la ultima clave de `markers.detector`, indice de
    la linea de `error_correction_rate` o None, sangria de las claves). ValueError si el
    perfil no trae el bloque `markers.detector` con una clave por linea."""
    pila: list[tuple[int, str]] = []
    ultima: int | None = None
    de_la_tasa: int | None = None
    sangria_claves = 0
    for i, linea in enumerate(lineas):
        texto = linea.rstrip("\r\n")
        if not texto.strip() or texto.lstrip().startswith("#") or texto.lstrip().startswith("-"):
            continue
        m = _RE_CLAVE.match(texto)
        if m is None:
            continue
        sangria = len(m.group("sangria"))
        while pila and pila[-1][0] >= sangria:
            pila.pop()
        pila.append((sangria, m.group("clave")))
        ruta = tuple(k for _, k in pila)
        if len(ruta) == 3 and ruta[:2] == ("markers", "detector"):
            ultima, sangria_claves = i, sangria
            if ruta[2] == CLAVE_YAML:
                if de_la_tasa is not None:
                    raise ValueError(f"markers.detector.{CLAVE_YAML} aparece dos veces en el perfil base")
                de_la_tasa = i
    if ultima is None:
        raise ValueError("el perfil base no trae el bloque markers.detector con una clave por linea: "
                         "no se sabe donde poner la tasa")
    return ultima, de_la_tasa, sangria_claves


def perfil_con_tasa(base: Path, tasa: float, salida: Path) -> Path:
    """La copia de `base` (un perfil del tracker) en `salida` con
    `markers.detector.error_correction_rate = tasa`. Copia el texto tal cual (comentarios y
    fines de linea) y cambia la linea de la clave o, si no esta, la anade al final del bloque
    `markers.detector` con una linea de comentario. Despues carga los dos con `profiles.load`
    y comprueba que lo unico distinto es esa clave; si no, borra la copia y falla.

    ValueError si la tasa no vale, la salida no termina en .yaml o cae dentro de
    `codigo/profiles/` (ahi solo van los perfiles del repo); FileExistsError si ya existe;
    FileNotFoundError si no existe `base`.
    """
    t = _comprobar_tasa(tasa)
    base, salida = Path(base), Path(salida)
    if not base.is_file():
        raise FileNotFoundError(f"no existe el perfil base {base}")
    if salida.suffix not in (".yaml", ".yml"):
        raise ValueError(f"la salida tiene que terminar en .yaml: {salida}")
    destino = salida.resolve()
    perfiles = profiles.PROFILES_DIR.resolve()
    if destino == perfiles or perfiles in destino.parents:
        raise ValueError(f"la salida cae dentro de {perfiles}: ahi solo van los perfiles del repo "
                         f"(la tasa entra en ellos en el cierre de la fase, no con una copia)")
    if salida.exists():
        raise FileExistsError(f"la salida ya existe, no se pisa: {salida}")
    cfg_base = profiles.load(base)
    diccionario = str(cfg_base["markers"]["dictionary"])
    texto = base.read_bytes().decode("utf-8")
    lineas = texto.splitlines(keepends=True)
    ultima, de_la_tasa, sangria = _bloque_detector(lineas)
    valor = f"{t:g}"
    if de_la_tasa is not None:
        linea = lineas[de_la_tasa]
        fin = linea[len(linea.rstrip("\r\n")):]
        m = _RE_CLAVE.match(linea.rstrip("\r\n"))
        coment = _RE_VALOR.match(m.group("resto")).group("coment") or ""
        lineas[de_la_tasa] = f"{m.group('sangria')}{CLAVE_YAML}: {valor}{coment}{fin}"
    else:
        fin = lineas[ultima][len(lineas[ultima].rstrip("\r\n")):] or "\n"
        if not lineas[ultima].endswith(("\n", "\r")):
            lineas[ultima] += fin
        margen = " " * sangria
        maximo = int(get_dictionary(diccionario).maxCorrectionBits)
        lineas[ultima + 1:ultima + 1] = [
            f"{margen}# {CLAVE_YAML}: copia temporal de diagnostics.barrido_correccion (meta 006, fase 7d2; B39).{fin}",
            f"{margen}# Corrige {bits_efectivos(diccionario, t)} de {maximo} bits de {diccionario}; sin la clave, 0.6 "
            f"({bits_efectivos(diccionario, BASE)} bits).{fin}",
            f"{margen}{CLAVE_YAML}: {valor}{fin}"]
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_bytes("".join(lineas).encode("utf-8"))
    try:
        cfg_copia = profiles.load(salida)
        tasa_copia = (cfg_copia["markers"].get("detector") or {}).pop(CLAVE_YAML, None)
        (cfg_base["markers"].get("detector") or {}).pop(CLAVE_YAML, None)
        if cfg_copia != cfg_base or tasa_copia is None or float(tasa_copia) != t:
            raise ValueError(f"la copia no es el perfil base mas markers.detector.{CLAVE_YAML} = {valor}")
    except Exception:
        salida.unlink()                                     # la acaba de crear esta llamada
        raise
    return salida


# ----------------------------------------------------------------------------
# La orden `barrer`: las entradas, el informe y los codigos
# ----------------------------------------------------------------------------

def leer_sinteticos(ruta: Path, cfg_markers: dict, id_ref: int, tasas: Sequence[float]) -> dict:
    """El barrido sintetico guardado en `ruta` (la salida de `barrer` sobre las escenas de
    `tests/escenas_b39.py`). ValueError si no es de este formato, o si no se hizo con el
    mismo ID de referencia, diccionario y parametros del detector, o le falta alguna tasa."""
    ruta = Path(ruta)
    if not ruta.is_file():
        raise ValueError(f"no existe el barrido sintetico {ruta}")
    try:
        s = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ValueError(f"{ruta.name}: no se pudo leer como JSON ({e})") from None
    if not isinstance(s, dict) or s.get("formato") != FORMATO or "categorias" not in s:
        raise ValueError(f"{ruta.name}: no es un barrido de formato {FORMATO}")
    if int(s.get("id_ref", -1)) != int(id_ref):
        raise ValueError(f"{ruta.name}: se hizo con el ID {s.get('id_ref')}, no con el {id_ref}")
    sin_tasa = lambda d: {k: v for k, v in dict(d or {}).items() if k != CLAVE_YAML}      # noqa: E731  (la tasa es lo que se barre)
    if s.get("diccionario") != str(cfg_markers["dictionary"]) or sin_tasa(s.get("detector")) != sin_tasa(cfg_markers.get("detector")):
        raise ValueError(f"{ruta.name}: se hizo con otro diccionario u otros parametros del detector que los del perfil")
    for t in tasas:
        for cat in CATEGORIAS_TABLERO:
            if _celda(s, cat, clave_tasa(t)) is None:
                raise ValueError(f"{ruta.name}: no trae la tasa {clave_tasa(t)} en '{cat}'")
    for cat in CATEGORIAS_TABLERO:
        if not s["categorias"][cat].get("frames"):
            raise ValueError(f"{ruta.name}: no trae frames de '{cat}' (un barrido sintetico vacio no comprueba nada)")
    if s.get("completo", True) is False:
        raise ValueError(f"{ruta.name}: es un barrido cortado por el tope")
    return s


def _pct(c: dict) -> str:
    return "n/a" if c["perdida"] is None else f"{100.0 * c['perdida']:.2f} %"


def tabla_md(barrido: dict, titulo: str) -> list[str]:
    """Las lineas Markdown de un resultado de `barrer`: una tabla por categoria, tasa por fila."""
    L = [f"### {titulo}", ""]
    for cat in CATEGORIAS:
        c = barrido["categorias"].get(cat)
        if not c or not c["frames"]:
            L += [f"**{cat}:** sin frames.", ""]
            continue
        L += [f"**{cat}** ({c['frames']} frames)", "",
              "| tasa | bits | ref. una vez | ref. dos o mas | fantasmas (frames) | con el ID de la ref. | perdidos | ganados | "
              "perdida | comunes | dif. max esquinas px |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for t in barrido["tasas"]:
            s = c["por_tasa"][clave_tasa(t)]
            L.append(f"| {clave_tasa(t)} | {barrido['bits'][clave_tasa(t)]} | {s['ref_una']} | {s['ref_doble']} | "
                     f"{s['fantasmas']} ({s['frames_con_fantasma']}) | {s['fantasmas_id_ref']} | {s['perdidos']} | "
                     f"{s['ganados']} | {_pct(s)} | {s['comunes']} | {s['max_dif_px']:.4f} ({s['frames_dif']} frames) |")
        L.append("")
    return L


def informe_md(datos: dict) -> str:
    """El texto de `barrido.md`: de donde sale, la elegida con su porque y las tablas."""
    real, sint = datos["real"], datos["sintetico"]
    elegida = datos["elegida"]
    L = ["# Barrido de error_correction_rate (meta 006, fase 7d2 · Los IDs falsos del tablero; B39)", "",
         f"- Generado: {datos['generado']} · OpenCV {real['opencv']} · perfil `{datos['perfil']}` · ID de la referencia "
         f"{real['id_ref']} · {real['diccionario']}",
         f"- Regla (P69, P74): la tasa mas alta con 0 fantasmas en todos los frames, tambien los de la referencia sola "
         f"(reales y sinteticos), 0 frames con el "
         f"ID de la referencia repetido y perdida <= {100.0 * datos['perdida_max']:.2f} % de los frames reales en que "
         f"{clave_tasa(BASE)} lee la referencia.",
         f"- **Elegida: {clave_tasa(elegida) if elegida is not None else 'ninguna'}**"
         + ("" if real.get("completo", True) else f" (barrido cortado por el tope de {real.get('tope_s'):g} s: "
            f"{real.get('frames_sin_leer')} frames sin leer)"), ""]
    L += [f"- {r}" for r in datos["razones"]] + [""]
    for cat, dirs in (real.get("carpetas") or {}).items():
        L.append(f"- Carpetas de '{cat}': " + (", ".join(f"`{d}`" for d in dirs) if dirs else "ninguna"))
    L.append(f"- Barrido sintetico: `{datos['sinteticos_ruta']}`" if sint is not None else "- Barrido sintetico: no se dio")
    L.append("")
    L += tabla_md(real, "Frames reales")
    if sint is not None:
        L += tabla_md(sint, "Frames sinteticos")
    L += ["Fantasma: con el tablero solo, toda deteccion; con la referencia a la vista, los IDs ajenos y las copias de mas "
          "del ID de la referencia. Perdido / ganado: frente a la tasa de hoy, frames en que una lee la referencia y la otra "
          "no. Comunes: frames con la referencia una vez con las dos tasas.", ""]
    return "\n".join(L)


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python -m diagnostics.barrido_correccion",
        description="Barre error_correction_rate del detector del tracker sobre frames grabados y elige con la regla de "
                    "P69 (meta 006, fase 7d2; B39). No abre camara ni red.")
    sub = ap.add_subparsers(dest="orden", required=True)
    b = sub.add_parser("barrer", help="El barrido sobre carpetas de frame_*.png y la regla.")
    b.add_argument("--config", required=True, type=Path, help="El perfil: de el salen el diccionario y markers.detector.")
    b.add_argument("--id", required=True, type=int, dest="id_ref", help="El ID de la referencia.")
    b.add_argument("--referencia", required=True, type=Path, nargs="+", metavar="DIR",
                   help="Carpetas con la referencia sola (P5).")
    b.add_argument("--tablero", type=Path, nargs="+", default=[], metavar="DIR", help="Carpetas con el tablero solo (P6).")
    b.add_argument("--tablero-con-referencia", type=Path, nargs="+", default=[], metavar="DIR",
                   help="Carpetas con el tablero y la referencia (P7).")
    b.add_argument("--sinteticos", type=Path, default=None, help="El JSON del barrido sintetico (fase-7d2/sinteticos.json).")
    b.add_argument("--tasas", type=float, nargs="+", default=list(TASAS), help=f"Las tasas (por defecto {list(TASAS)}).")
    b.add_argument("--perdida-max", type=float, default=PERDIDA_MAX, help=f"La perdida que se acepta (por defecto {PERDIDA_MAX}).")
    b.add_argument("--salida", required=True, type=Path, help="Carpeta de salida, nueva o vacia (no se pisa nada).")
    b.add_argument("--timeout", required=True, type=float, help="Tope en segundos (principio 9).")
    p = sub.add_parser("perfil", help="La copia temporal de un perfil con la tasa.")
    p.add_argument("--base", required=True, type=Path, help="El perfil base.")
    p.add_argument("--tasa", required=True, type=float, help="El valor de error_correction_rate.")
    p.add_argument("--salida", required=True, type=Path, help="El perfil nuevo (.yaml; no se pisa; fuera de codigo/profiles/).")
    return ap


def _orden_perfil(args) -> int:
    try:
        salida = perfil_con_tasa(args.base, args.tasa, args.salida)
    except (ValueError, OSError) as e:
        print(f"{TAG} ERROR: {e}")
        return EXIT_USO
    print(f"{TAG} {salida}: copia de {args.base} con markers.detector.{CLAVE_YAML} = {args.tasa:g}")
    return EXIT_OK


def _orden_barrer(args) -> int:
    salida = Path(args.salida)
    try:
        if not args.timeout > 0:
            raise ValueError("--timeout tiene que ser > 0")
        if not 0.0 <= args.perdida_max < 1.0:
            raise ValueError(f"--perdida-max tiene que estar en [0, 1), no {args.perdida_max}")
        tasas = [_comprobar_tasa(t) for t in args.tasas]
        cfg = profiles.load(args.config)
        cfg_markers = cfg["markers"]
        get_dictionary(str(cfg_markers["dictionary"]))
        carpetas = {"referencia": list(args.referencia), "tablero": list(args.tablero),
                    "tablero_con_referencia": list(args.tablero_con_referencia)}
        for cat, dirs in carpetas.items():
            for d in dirs:
                if not Path(d).is_dir():
                    raise ValueError(f"--{cat.replace('_', '-')}: no existe la carpeta {d}")
                if not frames_de(Path(d)):
                    raise ValueError(f"--{cat.replace('_', '-')}: no hay frame_*.png en {d}")
        if salida.exists() and (not salida.is_dir() or any(salida.iterdir())):
            raise ValueError(f"la salida ya existe y tiene algo, no se pisa: {salida}")
        sint = leer_sinteticos(args.sinteticos, cfg_markers, args.id_ref, tasas) if args.sinteticos is not None else None
    except (ValueError, OSError, KeyError, yaml.YAMLError) as e:
        print(f"{TAG} ERROR: {e}")
        return EXIT_USO
    ids_perfil = [int(m["id"]) for m in cfg_markers.get("list", []) or []]
    if args.id_ref not in ids_perfil:
        print(f"{TAG} AVISO: el ID {args.id_ref} no esta en markers.list de {Path(args.config).name} ({ids_perfil}); "
              f"se barre con ese ID y el detector del perfil")
    for t in sorted({*tasas, BASE}, reverse=True):
        print(f"{TAG} tasa {clave_tasa(t)}: {bits_efectivos(str(cfg_markers['dictionary']), t)} bits")
    try:
        real = barrer_carpetas(carpetas, cfg_markers, args.id_ref, tasas, args.timeout)
    except ValueError as e:
        print(f"{TAG} ERROR: {e}")
        return EXIT_USO
    elegida, razones = elegir(real, sint, args.perdida_max)
    datos = {"formato": FORMATO, "generado": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "perfil": str(args.config), "perfil_sha256": _sha256(args.config), "regla": REGLA,
             "perdida_max": float(args.perdida_max),
             "elegida": elegida, "razones": razones, "completo": bool(real["completo"]),
             "sinteticos_ruta": str(args.sinteticos) if args.sinteticos is not None else None,
             "sinteticos_sha256": _sha256(args.sinteticos) if args.sinteticos is not None else None,
             "real": real, "sintetico": sint}
    salida.mkdir(parents=True, exist_ok=True)
    with open(salida / "barrido.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
        f.write("\n")
    (salida / "barrido.md").write_text(informe_md(datos), encoding="utf-8", newline="\n")
    for r in razones:
        print(f"{TAG} {r}")
    print(f"{TAG} salida: {salida} (barrido.json, barrido.md); {real['segundos']:.0f} s")
    if not real["completo"]:
        print(f"{TAG} TOPE: quedaron {real['frames_sin_leer']} frames sin leer; no se elige")
        return EXIT_TOPE
    return EXIT_OK if elegida is not None else EXIT_NINGUNA


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.orden == "perfil":
        return _orden_perfil(args)
    return _orden_barrer(args)


if __name__ == "__main__":
    sys.exit(main())
