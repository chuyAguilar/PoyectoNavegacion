# -*- coding: utf-8 -*-
"""
comprobar_escala.py -- Comprobacion de escala de una calibracion intrinseca con
el tablero desplazado una distancia conocida (meta 002, fase 4).

Por que: el RMS de reproyeccion no ve un error de escala (un --square-mm
equivocado da la misma reproyeccion con una K distinta), asi que la escala se
mide aparte, contra una regla (clarify.md P6: |error| <= 1.0 mm por cada 100 mm).

Como: el tablero va sobre una base rigida que desliza contra una regla; el
autor lo pone en cada desplazamiento (p. ej. 0, 100 y 200 mm) y pulsa ESPACIO;
el script detecta las esquinas (calibrar_camara.detectar_esquinas, el mismo
detector que la calibracion), resuelve la pose del tablero con los intrinsecos
del perfil (solvePnP, SOLVEPNP_IPPE: puntos coplanares, >= 4) sobre
--frames-por-posicion frames y guarda la mediana de la traslacion. Al final,
la distancia que mide la camara entre posiciones menos la de la regla:
  - pasos: entre posiciones seguidas (0->100, 100->200): el criterio, cada uno
    con su tolerancia 1.0 mm por 100 mm de paso;
  - acumulados: cada posicion contra la primera (informativo).

Abre la camara SIEMPRE por su perfil, que ya tiene que apuntar al .yml (el
backend comprueba el tamano y entrega K y dist). Este modulo importa
camaras_uvc antes que cv2 (aceleracion HW de MSMF apagada, CONTEXT.md 4.18).
Todo con --timeout (vigilante) y la camara se libera (principio 9).

Context7 (2026-10-22, OpenCV 4.13; instalado 4.11): solvePnP con
SOLVEPNP_IPPE exige puntos coplanares y >= 4; imagePoints contiguos (N,1,2).

Uso (desde codigo\\, con el venv):
    python iter4\\comprobar_escala.py --config iter4\\tracker_config_gs1.yaml ^
        --cols 8 --rows 5 --square-mm 24.97 --detector clasico ^
        --desplazamientos-mm 0,100,200 --frames-por-posicion 30 --luz "caja nivel 2" ^
        --salida "..\\Claude outputs\\camaras\\escala_gs1.json" --timeout 600
Teclas: ESPACIO = medir esta posicion | q = salir antes
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import camaras_uvc  # noqa: F401  (antes de cv2: apaga la aceleracion HW de MSMF)
import cv2
import numpy as np

from calibrar_camara import DETECTORES, construir_objp, detectar_esquinas
from camera_backend import create_backend
from captura_calibracion import cargar_config
from sondear_camara import _vigilante

TOLERANCIA_MM_POR_100 = 1.0       # P6
VENTANA = "Comprobar escala - ESPACIO posicion, q salir"
SEGUNDOS_POR_POSICION = 15.0      # tope para juntar los frames de una posicion
MARGEN_S = 2.0


def log_info(m): print(f"[INFO] {m}", flush=True)
def log_warn(m): print(f"[WARN] {m}", flush=True)
def log_error(m): print(f"[ERROR] {m}", file=sys.stderr, flush=True)
def log_stats(m): print(f"[STATS] {m}", flush=True)


# ----------------------------------------------------------------------------
# Funciones puras (con prueba)
# ----------------------------------------------------------------------------

def tolerancia_mm(paso_mm: float, por_100: float = TOLERANCIA_MM_POR_100) -> float:
    """1.0 mm por cada 100 mm de paso (P6), proporcional al paso."""
    return abs(float(paso_mm)) / 100.0 * por_100


def errores_escala(tvecs, desplazamientos_mm) -> list[float]:
    """Distancia medida por la camara entre cada posicion y la primera, menos la de la regla.

    tvecs: traslaciones (3,) del tablero en la camara, una por posicion; desplazamientos_mm:
    la lectura de la regla en cada posicion. Devuelve len(tvecs) - 1 errores (mm), con signo
    (positivo = la camara mide mas que la regla).
    """
    t = [np.asarray(v, dtype=np.float64).flatten() for v in tvecs]
    d = [float(x) for x in desplazamientos_mm]
    if len(t) != len(d):
        raise ValueError(f"{len(t)} traslaciones y {len(d)} desplazamientos: tienen que ser los mismos")
    if len(t) < 2:
        raise ValueError("hacen falta al menos 2 posiciones")
    if any(v.shape != (3,) for v in t):
        raise ValueError("cada traslacion tiene que tener 3 componentes")
    return [float(np.linalg.norm(t[i] - t[0]) - abs(d[i] - d[0])) for i in range(1, len(t))]


def errores_pasos(tvecs, desplazamientos_mm) -> list[dict]:
    """Entre posiciones seguidas: paso de la regla, distancia medida, error y si cumple la tolerancia."""
    t = [np.asarray(v, dtype=np.float64).flatten() for v in tvecs]
    d = [float(x) for x in desplazamientos_mm]
    if len(t) != len(d) or len(t) < 2:
        raise ValueError("hacen falta al menos 2 posiciones, con su desplazamiento cada una")
    pasos = []
    for i in range(1, len(t)):
        regla = abs(d[i] - d[i - 1])
        medido = float(np.linalg.norm(t[i] - t[i - 1]))
        err = medido - regla
        tol = tolerancia_mm(regla)
        pasos.append({"de_mm": d[i - 1], "a_mm": d[i], "paso_regla_mm": regla,
                      "paso_medido_mm": round(medido, 3), "error_mm": round(err, 3),
                      "tolerancia_mm": round(tol, 3), "cumple": abs(err) <= tol + 1e-9})
    return pasos


def resumir_posicion(tvecs: list[np.ndarray]) -> dict:
    """Mediana y desviacion por eje de las traslaciones de una posicion."""
    if not tvecs:
        raise ValueError("sin poses en esta posicion")
    a = np.asarray([np.asarray(t, dtype=np.float64).flatten() for t in tvecs])
    return {"n": int(a.shape[0]), "mediana_mm": np.median(a, axis=0).round(3).tolist(),
            "sd_mm": a.std(axis=0).round(3).tolist() if a.shape[0] > 1 else [0.0, 0.0, 0.0],
            "distancia_mm": round(float(np.linalg.norm(np.median(a, axis=0))), 2)}


# ----------------------------------------------------------------------------
# Pose del tablero
# ----------------------------------------------------------------------------

def centro_tablero_mm(cols: int, rows: int, square_mm: float) -> np.ndarray:
    """El centro de las esquinas interiores, en el sistema del tablero (mm)."""
    return np.array([(cols - 1) / 2.0 * square_mm, (rows - 1) / 2.0 * square_mm, 0.0])


def pose_tablero(gray, cols: int, rows: int, square_mm: float, K, dist, metodo: str = "clasico"):
    """(rvec, t_centro) del tablero en la camara, o None si no se detecta.

    t_centro es la traslacion del CENTRO de las esquinas interiores, no del origen de objp:
    un tablero 8x5 admite dos ordenes de esquinas (girado 180 grados) y los detectores no
    siempre dan el mismo; el centro es el mismo en los dos, el origen no. rvec queda con
    esa ambiguedad (no se usa para la escala).
    """
    corners = detectar_esquinas(gray, cols, rows, metodo)
    if corners is None:
        return None
    objp = construir_objp(cols, rows, square_mm)
    ok, rvec, tvec = cv2.solvePnP(objp, np.ascontiguousarray(corners, dtype=np.float32).reshape(-1, 1, 2),
                                  np.asarray(K, dtype=np.float64), np.asarray(dist, dtype=np.float64),
                                  flags=cv2.SOLVEPNP_IPPE)
    if not ok:
        return None
    R, _ = cv2.Rodrigues(rvec)
    t_centro = R @ centro_tablero_mm(cols, rows, square_mm) + np.asarray(tvec, dtype=np.float64).flatten()
    return np.asarray(rvec, dtype=np.float64).flatten(), t_centro


def medir_posiciones(cam, cols: int, rows: int, square_mm: float, K, dist, metodo: str,
                     desplazamientos_mm: list[float], frames_por_posicion: int, limite: float,
                     leer_tecla=None, segundos_por_posicion: float = SEGUNDOS_POR_POSICION) -> list[dict]:
    """Ventana: por cada desplazamiento, ESPACIO junta hasta frames_por_posicion poses (o
    segundos_por_posicion) y guarda la mediana. q sale antes. `leer_tecla()` se inyecta en las
    pruebas (por defecto cv2.waitKey(1) & 0xFF). Devuelve una fila por posicion medida."""
    leer_tecla = leer_tecla if leer_tecla is not None else (lambda: cv2.waitKey(1) & 0xFF)
    filas: list[dict] = []
    i = 0
    cv2.namedWindow(VENTANA, cv2.WINDOW_NORMAL)
    try:
        while i < len(desplazamientos_mm) and time.monotonic() < limite:
            frame, _d, _ts = cam.read()
            if frame is None:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            previa = detectar_esquinas(gray, cols, rows, "clasico", rapido=True)
            disp = frame.copy()
            if previa is not None:
                cv2.drawChessboardCorners(disp, (cols, rows), previa, True)
            color = (0, 255, 0) if previa is not None else (0, 0, 255)
            cv2.putText(disp, f"Posicion {i + 1}/{len(desplazamientos_mm)}: regla en "
                        f"{desplazamientos_mm[i]:g} mm | tablero: {'DETECTADO' if previa is not None else 'no visto'}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            cv2.putText(disp, "ESPACIO = medir esta posicion   q = salir", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            cv2.imshow(VENTANA, disp)
            tecla = leer_tecla()
            if tecla == ord("q"):
                break
            if tecla != ord(" "):
                continue
            poses, fallos = [], 0
            t0 = time.monotonic()
            while (len(poses) < frames_por_posicion and time.monotonic() - t0 < segundos_por_posicion
                   and time.monotonic() < limite):
                frame, _d, _ts = cam.read()
                if frame is None:
                    continue
                p = pose_tablero(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), cols, rows, square_mm, K, dist, metodo)
                if p is None:
                    fallos += 1
                    continue
                poses.append(p[1])
            if not poses:
                log_warn(f"posicion {desplazamientos_mm[i]:g} mm: sin pose en {fallos} frames; vuelve a pulsar ESPACIO")
                continue
            fila = {"desplazamiento_mm": float(desplazamientos_mm[i]), "frames_sin_pose": fallos,
                    "segundos": round(time.monotonic() - t0, 2)}
            fila.update(resumir_posicion(poses))
            filas.append(fila)
            log_info(f"posicion {desplazamientos_mm[i]:g} mm: {fila['n']} poses, mediana {fila['mediana_mm']} mm "
                     f"(sd {fila['sd_mm']}), distancia {fila['distancia_mm']} mm")
            i += 1
    finally:
        cv2.destroyAllWindows()
    return filas


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

def _parsear_lista(texto: str) -> list[float]:
    try:
        v = [float(t) for t in texto.split(",") if t.strip()]
    except ValueError:
        raise ValueError(f"--desplazamientos-mm mal escrito: {texto!r} (forma: 0,100,200)")
    if len(v) < 2:
        raise ValueError("--desplazamientos-mm necesita al menos 2 posiciones")
    return v


def _guardar(estado: dict, salida: Path) -> None:
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(estado, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def main(argv: list[str] | None = None, abrir=None) -> int:
    ap = argparse.ArgumentParser(description="Comprobacion de escala de los intrinsecos con el tablero desplazado contra una regla.")
    ap.add_argument("--config", required=True, help="perfil con calibration_file apuntando al .yml que se comprueba")
    ap.add_argument("--cols", type=int, default=8, help="esquinas interiores horizontales")
    ap.add_argument("--rows", type=int, default=5, help="esquinas interiores verticales")
    ap.add_argument("--square-mm", type=float, required=True, help="lado de la casilla medido (el mismo que en la calibracion)")
    ap.add_argument("--detector", choices=DETECTORES, required=True, help="el detector con que se calibro")
    ap.add_argument("--desplazamientos-mm", required=True, help="lecturas de la regla, p. ej. 0,100,200")
    ap.add_argument("--frames-por-posicion", type=int, default=30, help="poses que se juntan por posicion (mediana)")
    ap.add_argument("--luz", help="nivel de la caja de luz y luz de la sala (P7)")
    ap.add_argument("--salida", required=True, help="JSON de salida")
    ap.add_argument("--timeout", type=float, required=True, help="tope en segundos")
    args = ap.parse_args(argv)

    try:
        desplazamientos = _parsear_lista(args.desplazamientos_mm)
    except ValueError as e:
        ap.error(str(e))
    if args.square_mm <= 0 or args.frames_por_posicion < 1:
        ap.error("--square-mm > 0 y --frames-por-posicion >= 1")

    cfg = cargar_config(args.config)
    cam_cfg = cfg["camera"]
    if not cam_cfg.get("calibration_file"):
        ap.error(f"el perfil {args.config} no tiene calibration_file: calibra primero (calibrar_camara.py) y apunta el perfil")
    salida = Path(args.salida)
    estado: dict = {"fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "argv": sys.argv[1:] if argv is None else argv,
                    "opencv": cv2.__version__, "perfil": args.config, "calibration_file": cam_cfg.get("calibration_file"),
                    "puerto": cam_cfg.get("usb_port_windows"), "detector": args.detector, "square_mm": args.square_mm,
                    "desplazamientos_mm": desplazamientos, "frames_por_posicion": args.frames_por_posicion,
                    "luz": args.luz, "tolerancia_mm_por_100": TOLERANCIA_MM_POR_100, "posiciones": []}
    log_info(f"Config: {args.config} ({cam_cfg.get('calibration_file')}); tablero {args.cols}x{args.rows} @ "
             f"{args.square_mm} mm; detector {args.detector}; regla en {desplazamientos} mm")
    vig = _vigilante(args.timeout, estado, salida)
    rc = 0
    cam = None
    try:
        cam = (abrir or (lambda c: create_backend(c)))(cam_cfg)
        cam.open()
        K, dist = cam.get_intrinsics()
        estado["K"] = np.asarray(K).tolist()
        estado["dist"] = np.asarray(dist).flatten().tolist()
        log_info("ESPACIO = medir la posicion que dice la ventana (tablero quieto sobre la base) | q = salir")
        filas = medir_posiciones(cam, args.cols, args.rows, args.square_mm, K, dist, args.detector,
                                 desplazamientos, args.frames_por_posicion, time.monotonic() + args.timeout - MARGEN_S)
        estado["posiciones"] = filas
        if len(filas) < 2:
            raise RuntimeError(f"solo {len(filas)} posiciones medidas: hacen falta al menos 2")
        tv = [f["mediana_mm"] for f in filas]
        ds = [f["desplazamiento_mm"] for f in filas]
        estado["pasos"] = errores_pasos(tv, ds)
        estado["errores_acumulados_mm"] = [round(e, 3) for e in errores_escala(tv, ds)]
        estado["cumple"] = all(p["cumple"] for p in estado["pasos"])
        print("\n| de (mm) | a (mm) | paso regla | paso medido | error | tolerancia | cumple |")
        print("|---|---|---|---|---|---|---|")
        for p in estado["pasos"]:
            print(f"| {p['de_mm']:g} | {p['a_mm']:g} | {p['paso_regla_mm']:g} | {p['paso_medido_mm']:.3f} | "
                  f"{p['error_mm']:+.3f} | {p['tolerancia_mm']:.2f} | {'si' if p['cumple'] else 'NO'} |")
        log_stats(f"errores acumulados contra la primera posicion: {estado['errores_acumulados_mm']} mm")
        if estado["cumple"]:
            log_info(f"Escala: cumple (|error| <= {TOLERANCIA_MM_POR_100} mm por 100 mm en todos los pasos)")
        else:
            log_warn("Escala: NO cumple en algun paso; revisar --square-mm (medida del calibrador), la regla y la base")
            rc = 1
    except (RuntimeError, ValueError, OSError) as e:
        estado["error"] = str(e)
        log_error(str(e))
        rc = 1
    finally:
        vig.cancel()
        if cam is not None:
            cam.close()
        _guardar(estado, salida)
        log_info(f"guardado {salida}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
