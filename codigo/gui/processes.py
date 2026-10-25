# -*- coding: utf-8 -*-
"""
processes.py — Orquestador de subprocesos del panel (brief-01; era
gui/procesos.py). SIN Qt.

Lanza los scripts EXISTENTES como subprocesos (candado: UN proceso a la vez,
iter 1), lee su stdout en vivo linea a linea y los detiene por su camino
nativo. Mecanismo de Detener decidido por la sonda del Paso 1 (2026-08-13):

  1) PostMessage WM_CHAR 'q' a la ventana OpenCV del script — equivale a la
     tecla 'q': el script sale por su camino feliz, corre el finally
     (camara liberada, servidor pyigtl cerrado). VALIDADO empiricamente.
  2) Si no muere en unos segundos: terminate() — duro. La sonda demostro que
     CTRL_BREAK tambien mata duro SIN correr el finally (exit 0xC000013A),
     asi que no aporta nada sobre terminate() y no se usa.
  3) kill() como ultimo recurso.

Meta 003, fase 7b (clarify.md P12): las recetas con `stop_stdin` (el tracker
sin ventana, `--stop-stdin`) se lanzan con la entrada estandar en una tuberia
y se detienen escribiendo `q` y cerrandola: el tracker sale por el mismo
camino que con 'q' en la ventana (finally completo). Si no sale en
ESPERA_STDIN_S, terminate() y kill() como siempre, y lo dice.

Los callbacks (on_linea, on_fin) se invocan desde hilos de trabajo: el panel
los envuelve en señales Qt (emision cross-thread segura).
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import threading

WM_CHAR = 0x0102
ESPERA_Q_S = 4.0        # tras enviar 'q', cuanto esperar el cierre limpio
ESPERA_TERMINATE_S = 3.0
ESPERA_STDIN_S = 8.0    # tras escribir 'q' por stdin: hilo, camara y servidor (IgtlSender.close, tope 5 s)

# Meta 002, fase 2b (correccion, 2026-10-22): la aceleracion HW de MSMF hace
# que abrir la camara tarde 43-51 s en vez de 3.6-4.0 s, sin ganar fps. cv2 la
# lee del entorno al cargarse, asi que el panel se la pasa apagada a sus
# procesos (desde la meta 003, fase 4, tracker.py tambien la apaga solo, B28;
# el entorno sigue siendo la red de seguridad). El mismo nombre y la misma
# regla (setdefault: un valor puesto a mano se respeta) que
# camera.uvc.VAR_ACELERACION_MSMF; aqui sin importarlo (gui/ no carga camera/).
VAR_ACELERACION_MSMF = "OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"


def entorno_hijo(base, plataforma=sys.platform):
    """El entorno de un proceso del panel: `base` + PYTHONIOENCODING y, en Windows, MSMF sin aceleracion HW."""
    env = dict(base)
    env["PYTHONIOENCODING"] = "utf-8"
    if plataforma == "win32":
        env.setdefault(VAR_ACELERACION_MSMF, "0")
    return env


def _post_q(titulo_ventana):
    """Envia 'q' a la ventana con ese titulo exacto. True si la encontro."""
    hwnd = ctypes.windll.user32.FindWindowW(None, titulo_ventana)
    if not hwnd:
        return False
    ctypes.windll.user32.PostMessageW(hwnd, WM_CHAR, ord("q"), 0)
    return True


class Lanzador:
    """Gestiona el subproceso activo (uno a la vez) y su lectura de stdout."""

    def __init__(self, on_linea, on_fin):
        """on_linea(str): cada linea de stdout/stderr del hijo.
        on_fin(receta, exit_code): al terminar el hijo (cualquier causa)."""
        self._on_linea = on_linea
        self._on_fin = on_fin
        self._lock = threading.Lock()
        self._proc = None
        self._receta = None
        self._buffer = []

    # ------------------------------------------------------------------
    def hay_activo(self):
        with self._lock:
            return self._proc is not None and self._proc.poll() is None

    def receta_activa(self):
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                return self._receta
        return None

    def buffer_actual(self):
        """Copia de las lineas del proceso actual (o del ultimo terminado)."""
        with self._lock:
            return list(self._buffer)

    # ------------------------------------------------------------------
    def lanzar(self, receta):
        """Lanza la receta. Devuelve None si ok, o un mensaje de error."""
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                return (f"ya hay un proceso corriendo "
                        f"({self._receta.clave}); usar Detener primero")
            env = entorno_hijo(os.environ)
            try:
                proc = subprocess.Popen(
                    receta.argv,
                    cwd=receta.cwd,
                    # solo las recetas que se detienen por stdin la reciben en tuberia
                    stdin=subprocess.PIPE if getattr(receta, "stop_stdin", False) else None,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                    env=env,
                )
            except Exception as e:
                return f"no se pudo lanzar {receta.clave}: {e}"
            self._proc = proc
            self._receta = receta
            self._buffer = []
        threading.Thread(target=self._leer, args=(proc, receta),
                         daemon=True).start()
        if receta.timeout_s:
            threading.Thread(target=self._watchdog,
                             args=(proc, receta), daemon=True).start()
        return None

    def _leer(self, proc, receta):
        for linea in proc.stdout:
            linea = linea.rstrip("\r\n")
            with self._lock:
                self._buffer.append(linea)
            self._on_linea(linea)
        rc = proc.wait()
        with self._lock:
            if self._proc is proc:
                self._proc = None
        self._on_fin(receta, rc)

    def _watchdog(self, proc, receta):
        try:
            proc.wait(timeout=receta.timeout_s)
        except subprocess.TimeoutExpired:
            self._on_linea(f"[panel] watchdog: {receta.clave} no respondio en "
                           f"{receta.timeout_s:.0f}s — terminandolo")
            try:
                proc.terminate()
            except OSError:
                pass

    # ------------------------------------------------------------------
    def detener(self):
        """Detiene el proceso activo. BLOQUEANTE (usar detener_async desde la
        GUI). Devuelve un mensaje de resultado."""
        with self._lock:
            proc, receta = self._proc, self._receta
        if proc is None or proc.poll() is not None:
            return "no hay proceso corriendo"

        # 1a) sin ventana (fase 7b): 'q' por la entrada estandar, y se cierra
        if getattr(receta, "stop_stdin", False):
            if self._enviar_q_stdin(proc):
                return "cierre limpio (por la entrada estandar)"
        # 1b) camino nativo: tecla 'q' a la ventana OpenCV del script
        elif receta.ventana_titulo:
            enviado = _post_q(receta.ventana_titulo)
            self._on_linea(f"[panel] detener: enviando 'q' a la ventana "
                           f"'{receta.ventana_titulo}' "
                           f"({'ok' if enviado else 'ventana NO encontrada'})")
            fin = threading.Event()
            t0 = ESPERA_Q_S
            while t0 > 0:
                if proc.poll() is not None:
                    return "cierre limpio (por 'q')"
                if not enviado:  # la ventana pudo tardar en existir
                    enviado = _post_q(receta.ventana_titulo)
                fin.wait(0.25)
                t0 -= 0.25

        # 2) cierre duro
        self._on_linea(f"[panel] detener: {receta.clave} no cerro limpio con 'q' — "
                       f"terminate() (cierre DURO: el finally del script no "
                       f"corre; la camara puede tardar unos segundos en "
                       f"liberarse)")
        try:
            proc.terminate()
        except OSError:
            pass
        try:
            proc.wait(timeout=ESPERA_TERMINATE_S)
            return "cerrado con terminate() (duro)"
        except subprocess.TimeoutExpired:
            pass

        # 3) ultimo recurso
        try:
            proc.kill()
            proc.wait(timeout=2.0)
        except (OSError, subprocess.TimeoutExpired):
            pass
        return "cerrado con kill() (ultimo recurso)"

    def _enviar_q_stdin(self, proc):
        """Escribe 'q' en la entrada estandar del hijo, la cierra (el fin de la
        entrada tambien lo detiene) y espera hasta ESPERA_STDIN_S. True si salio."""
        self._on_linea("[panel] detener: enviando 'q' por la entrada estandar")
        if proc.stdin is None:
            self._on_linea("[panel] detener: el proceso no tiene la entrada estandar en tuberia")
        else:
            try:
                proc.stdin.write("q\n")
                proc.stdin.flush()
            except (OSError, ValueError) as e:      # tuberia rota o ya cerrada: se anota y se sigue
                self._on_linea(f"[panel] detener: no se pudo escribir en la entrada estandar ({e})")
            try:
                proc.stdin.close()
            except (OSError, ValueError):
                pass
        fin = threading.Event()
        restante = ESPERA_STDIN_S
        while restante > 0:
            if proc.poll() is not None:
                return True
            fin.wait(0.1)
            restante -= 0.1
        return proc.poll() is not None

    def detener_async(self, al_terminar=None):
        """Detiene en un hilo aparte para no congelar la GUI."""
        def _run():
            msg = self.detener()
            self._on_linea(f"[panel] detener: {msg}")
            if al_terminar:
                al_terminar(msg)
        threading.Thread(target=_run, daemon=True).start()
