# -*- coding: utf-8 -*-
"""
procesos.py — Orquestador de subprocesos del panel (brief-01). SIN Qt.

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

Los callbacks (on_linea, on_fin) se invocan desde hilos de trabajo: el panel
los envuelve en señales Qt (emision cross-thread segura).
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import threading

WM_CHAR = 0x0102
ESPERA_Q_S = 4.0        # tras enviar 'q', cuanto esperar el cierre limpio
ESPERA_TERMINATE_S = 3.0


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
            env = dict(os.environ)
            env["PYTHONIOENCODING"] = "utf-8"
            try:
                proc = subprocess.Popen(
                    receta.argv,
                    cwd=receta.cwd,
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

        # 1) camino nativo: tecla 'q' a la ventana OpenCV del script
        if receta.ventana_titulo:
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
        self._on_linea(f"[panel] detener: {receta.clave} no cerro con 'q' — "
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

    def detener_async(self, al_terminar=None):
        """Detiene en un hilo aparte para no congelar la GUI."""
        def _run():
            msg = self.detener()
            self._on_linea(f"[panel] detener: {msg}")
            if al_terminar:
                al_terminar(msg)
        threading.Thread(target=_run, daemon=True).start()
