# -*- coding: utf-8 -*-
"""
panel.py — Panel de control GUI (brief-01 + refinamiento brief-02). PySide6.

Ventana unica: selector de perfil + semaforos de prerrequisitos + botones que
lanzan los scripts EXISTENTES como subprocesos (la GUI solo orquesta, no
reescribe logica) + panel de log con la salida en vivo.

Grupos de acciones:
  1 Verificar/Preparar: identificar IDs, probar camara (bajo demanda).
  2 Calibrar (orden brief-02 M4): asistente "dodecaedro nuevo" (captura ->
    cobertura -> BA, en asistente.py), calibrar punta (dock). Los botones
    sueltos de captura/BA se quitaron en brief-02 M4 (redundantes con el
    asistente y peligrosos con defaults del stylus viejo); un BA sobre un
    dataset viejo sin recapturar queda disponible SOLO por CLI.
  3 Operar: tracker (gating duro + recordatorio de Slicer), detener.

Uso (desde codigo\, con el venv):
    python iter4\gui\panel.py
    python iter4\gui\panel.py --selftest      # abre, refresca, imprime y cierra solo
    python iter4\gui\panel.py --perfil iter4/tracker_config_doctor.yaml
Teclas: F5 = refrescar semaforos.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from PySide6.QtCore import QObject, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox,
    QVBoxLayout, QWidget,
)

import estado
import perfil_editor
import procesos
import recetas
from asistente import AsistenteDodecaedro

COLORES = {
    estado.VERDE: "#1e8e3e",
    estado.AMARILLO: "#e8a100",
    estado.ROJO: "#c5221f",
    estado.GRIS: "#8a8a8a",
}


class FilaSemaforo(QWidget):
    """Una fila: punto de color + titulo + detalle (fail-loud: el detalle
    explica el porque)."""

    def __init__(self, chequeo, parent=None):
        super().__init__(parent)
        fila = QHBoxLayout(self)
        fila.setContentsMargins(4, 2, 4, 2)
        self.punto = QLabel("●")  # ●
        self.punto.setFixedWidth(22)
        f = self.punto.font()
        f.setPointSize(14)
        self.punto.setFont(f)
        self.titulo = QLabel()
        self.titulo.setStyleSheet("font-weight: bold;")
        self.titulo.setFixedWidth(210)
        self.detalle = QLabel()
        self.detalle.setWordWrap(True)
        fila.addWidget(self.punto)
        fila.addWidget(self.titulo)
        fila.addWidget(self.detalle, stretch=1)
        self.actualizar(chequeo)

    def actualizar(self, chequeo):
        self.chequeo = chequeo
        color = COLORES.get(chequeo.estado, COLORES[estado.GRIS])
        self.punto.setStyleSheet(f"color: {color};")
        self.punto.setToolTip(chequeo.estado)
        self.titulo.setText(chequeo.titulo)
        self.detalle.setText(chequeo.detalle)


class _Puente(QObject):
    """Callbacks del Lanzador (hilos de trabajo) -> señales Qt (hilo GUI)."""
    linea = Signal(str)
    fin = Signal(object, int)


class DialogoDivot(QDialog):
    """Parametros de calibrar_tip_divot.py (dock del manual paso 2)."""

    def __init__(self, parent, ruta_cfg):
        super().__init__(parent)
        self.setWindowTitle("Calibrar punta (dock/divot)")
        self.ruta_cfg = ruta_cfg
        form = QFormLayout(self)
        self.combo_divot = QComboBox()
        self.combo_divot.addItems(["DOCK", "A", "B", "C"])
        form.addRow("Divot:", self.combo_divot)
        self.spin_id = QSpinBox()
        self.spin_id.setRange(0, 999)
        self.spin_id.setValue(recetas.DOCK_DEFAULTS["plate_id"])
        form.addRow("Marker de la placa (ID):", self.spin_id)
        self.spin_mm = QDoubleSpinBox()
        self.spin_mm.setRange(10.0, 200.0)
        self.spin_mm.setDecimals(2)
        self.spin_mm.setValue(recetas.DOCK_DEFAULTS["plate_mm"])
        self.spin_mm.setSuffix(" mm")
        form.addRow("Lado del marker (medir con calibrador):", self.spin_mm)
        self.spin_timeout = QSpinBox()
        self.spin_timeout.setRange(60, 3600)
        self.spin_timeout.setValue(recetas.DOCK_DEFAULTS["timeout"])
        self.spin_timeout.setSuffix(" s")
        form.addRow("Autocierre del script:", self.spin_timeout)
        slug = recetas.slug_de_perfil(ruta_cfg)
        self.edit_out = QLineEdit(f"iter4/data/StylusTipToDodecaedro_{slug}_dock")
        form.addRow("Salida (sin extension):", self.edit_out)
        nota = QLabel("En la ventana del script: ESPACIO=capturar postura "
                      "(6 orientaciones distintas), q=terminar y calcular. "
                      "OJO: el script se autocierra al cumplirse el tiempo.")
        nota.setWordWrap(True)
        form.addRow(nota)
        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        form.addRow(botones)
        self.receta = None

    def accept(self):
        try:
            self.receta = recetas.receta_divot(
                self.ruta_cfg,
                output_matriz=self.edit_out.text().strip(),
                divot=self.combo_divot.currentText(),
                plate_id=self.spin_id.value(),
                plate_mm=self.spin_mm.value(),
                timeout=self.spin_timeout.value(),
            )
        except (ValueError, FileNotFoundError) as e:
            QMessageBox.warning(self, "Divot", str(e))
            return
        super().accept()

    @staticmethod
    def pedir(parent, ruta_cfg):
        d = DialogoDivot(parent, ruta_cfg)
        return d.receta if d.exec() == QDialog.DialogCode.Accepted else None


class DialogoCalibrarCamara(QDialog):
    """Parametros de iter4/calibrar_camara.py (M3b): tablero del repo
    (9x6 casillas = esquinas interiores 8x5 @ 25 mm, readme §8)."""

    def __init__(self, parent, ruta_cfg):
        super().__init__(parent)
        self.setWindowTitle("Calibrar camara con tablero")
        self.ruta_cfg = ruta_cfg
        form = QFormLayout(self)
        slug = recetas.slug_de_perfil(ruta_cfg)
        self.edit_out = QLineEdit(f"iter4/data/camera_calibration_{slug}.yml")
        form.addRow("Salida (.yml):", self.edit_out)
        self.spin_cols = QSpinBox()
        self.spin_cols.setRange(3, 20)
        self.spin_cols.setValue(8)
        form.addRow("Esquinas interiores (horiz):", self.spin_cols)
        self.spin_rows = QSpinBox()
        self.spin_rows.setRange(3, 20)
        self.spin_rows.setValue(5)
        form.addRow("Esquinas interiores (vert):", self.spin_rows)
        self.spin_sq = QDoubleSpinBox()
        self.spin_sq.setRange(5.0, 100.0)
        self.spin_sq.setDecimals(1)
        self.spin_sq.setValue(25.0)
        self.spin_sq.setSuffix(" mm")
        form.addRow("Lado de la celda:", self.spin_sq)
        self.spin_min = QSpinBox()
        self.spin_min.setRange(5, 60)
        self.spin_min.setValue(12)
        form.addRow("Vistas minimas:", self.spin_min)
        nota = QLabel("Patron del repo: data/recursos/"
                      "calibration_pattern_9x6_25mm.pdf impreso al 100% sobre "
                      "superficie rigida. ESPACIO=capturar vista (15-30, "
                      "variadas), q=calibrar y guardar. Criterio: RMSE < 1 px.")
        nota.setWordWrap(True)
        form.addRow(nota)
        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        form.addRow(botones)
        self.receta = None

    def accept(self):
        try:
            self.receta = recetas.receta_calibrar_camara(
                self.ruta_cfg,
                output=self.edit_out.text().strip(),
                cols=self.spin_cols.value(),
                rows=self.spin_rows.value(),
                square_mm=self.spin_sq.value(),
                min_vistas=self.spin_min.value(),
            )
        except (ValueError, FileNotFoundError) as e:
            QMessageBox.warning(self, "Calibrar camara", str(e))
            return
        super().accept()


class DialogoIntrinsecos(QDialog):
    """M3: gestion de intrinsecos del perfil activo.
    (a) Correr una calibracion con tablero (calibrar_camara.py).
    (b) Apuntar camera.calibration_file del perfil a un .yml validado —
        UNICA mutacion de config permitida (ADR-018): edicion textual
        quirurgica con backup, via perfil_editor.py."""

    def __init__(self, panel):
        super().__init__(panel)
        self.panel = panel
        self.setWindowTitle("Calibracion de camara e intrinsecos (M3)")
        self.resize(520, 260)
        caja = QVBoxLayout(self)

        cfg = panel._cfg or {}
        cam = cfg.get("camera", {}) or {}
        ctype = str(cam.get("camera_type", "?")).lower()
        actual = cam.get("calibration_file") or "(vacio = fabrica del SDK)"
        texto = (f"Perfil: {Path(panel.perfil_activo()).name}  |  "
                 f"camera_type: {ctype}\n"
                 f"calibration_file actual: {actual}")
        if ctype == "femtobolt":
            texto += ("\nNota: la Femto usa calibracion de FABRICA; apuntar "
                      "un .yml aqui es solo para overrides especiales.")
        info = QLabel(texto)
        info.setWordWrap(True)
        caja.addWidget(info)

        btn_correr = QPushButton("Correr calibracion con tablero…")
        btn_correr.clicked.connect(self._correr)
        caja.addWidget(btn_correr)

        caja.addWidget(QLabel("O apuntar el perfil a un .yml existente:"))
        fila = QHBoxLayout()
        self.combo_yml = QComboBox()
        for p in sorted(estado.DIR_DATA.glob("*.yml")):
            self.combo_yml.addItem(p.name, str(p))
        fila.addWidget(self.combo_yml, stretch=1)
        btn_examinar = QPushButton("Examinar…")
        btn_examinar.clicked.connect(self._examinar)
        fila.addWidget(btn_examinar)
        caja.addLayout(fila)
        btn_apuntar = QPushButton("Validar y apuntar el perfil al .yml elegido")
        btn_apuntar.clicked.connect(self._apuntar)
        caja.addWidget(btn_apuntar)

        cierre = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        cierre.rejected.connect(self.reject)
        caja.addWidget(cierre)

    def _correr(self):
        d = DialogoCalibrarCamara(self, self.panel.perfil_activo())
        if d.exec() == QDialog.DialogCode.Accepted and d.receta:
            self.accept()   # cerrar para ver el log en el panel
            self.panel.lanzar_receta(d.receta)

    def _examinar(self):
        ruta, _f = QFileDialog.getOpenFileName(
            self, "Elegir .yml de calibracion", str(estado.DIR_DATA),
            "Calibracion (*.yml *.yaml)")
        if not ruta:
            return
        i = self.combo_yml.findData(ruta)
        if i < 0:
            etiqueta = Path(ruta).name
            if Path(ruta).resolve().parent != estado.DIR_DATA.resolve():
                etiqueta += " (fuera de data\\)"
            self.combo_yml.addItem(etiqueta, ruta)
            i = self.combo_yml.count() - 1
        self.combo_yml.setCurrentIndex(i)

    def _apuntar(self):
        ruta_yml = self.combo_yml.currentData()
        if not ruta_yml:
            QMessageBox.warning(self, "Intrinsecos", "No hay .yml elegido.")
            return
        err = perfil_editor.validar_yml_intrinsecos(ruta_yml)
        if err:
            QMessageBox.warning(self, "Intrinsecos",
                                f"El .yml NO valida como calibracion: {err}")
            return
        perfil = self.panel.perfil_activo()
        valor = perfil_editor.valor_para_perfil(ruta_yml, estado.DIR_DATA)
        try:
            actual, nueva = perfil_editor.previsualizar_cambio(perfil, valor)
        except (ValueError, OSError) as e:
            QMessageBox.critical(self, "Intrinsecos", str(e))
            return
        r = QMessageBox.question(
            self, "Confirmar edicion del perfil (ADR-018)",
            f"Se editara {Path(perfil).name} — UNICA linea, con backup "
            f"timestampeado:\n\n"
            f"  ANTES:    {actual.strip()}\n"
            f"  DESPUES:  {nueva.strip()}\n\n¿Aplicar?")
        if r != QMessageBox.StandardButton.Yes:
            return
        try:
            backup, _a, _n = perfil_editor.aplicar_cambio(perfil, valor)
        except (ValueError, OSError) as e:
            QMessageBox.critical(self, "Intrinsecos", f"NO aplicado: {e}")
            return
        self.panel.log_msg(f"perfil editado (ADR-018): {Path(perfil).name} -> "
                           f"calibration_file: {valor}")
        self.panel.log_msg(f"  backup: {backup.name}")
        self.panel.refrescar()
        self.accept()


# ============================================================================
# Ventana principal
# ============================================================================

class Panel(QMainWindow):
    def __init__(self, perfil_inicial=None):
        super().__init__()
        self.setWindowTitle("Panel de Navegacion Quirurgica — brief-02 (iter 2)")
        self.resize(980, 760)
        self.settings = QSettings("PoyectoNavegacion", "PanelGUI")
        self.filas = {}
        self.chequeos = []
        self._chk = {}
        self._cfg = None
        self.origen_actual = None
        self.resultado_camara = None   # (ruta_perfil, Chequeo)
        self.asistente = None

        self.puente = _Puente()
        self.puente.linea.connect(self._linea_hijo)
        self.puente.fin.connect(self._proceso_termino)
        self.lanzador = procesos.Lanzador(
            on_linea=self.puente.linea.emit,
            on_fin=lambda receta, rc: self.puente.fin.emit(receta, rc))

        central = QWidget()
        raiz = QVBoxLayout(central)

        # --- Fila superior: perfil + refrescar ---
        arriba = QHBoxLayout()
        arriba.addWidget(QLabel("Perfil activo:"))
        self.combo = QComboBox()
        perfiles = estado.listar_perfiles()
        for p in perfiles:
            self.combo.addItem(p.name, str(p))
        arriba.addWidget(self.combo, stretch=1)
        self.btn_refrescar = QPushButton("Refrescar (F5)")
        arriba.addWidget(self.btn_refrescar)
        raiz.addLayout(arriba)

        # --- Semaforos ---
        self.grupo_sem = QGroupBox("Prerrequisitos (estado real del repo)")
        self.caja_sem = QVBoxLayout(self.grupo_sem)
        raiz.addWidget(self.grupo_sem)

        # --- Acciones ---
        fila_acc = QHBoxLayout()
        g1 = QGroupBox("1 · Verificar / Preparar")
        c1 = QVBoxLayout(g1)
        self.btn_ids = QPushButton("Verificar IDs")
        self.btn_camara = QPushButton("Probar camara")
        self.btn_calcam = QPushButton("Calibracion de camara…")
        c1.addWidget(self.btn_ids)
        c1.addWidget(self.btn_camara)
        c1.addWidget(self.btn_calcam)
        c1.addStretch(1)
        # brief-02 M4: asistente primero, dock despues; sin botones sueltos
        # de captura/BA (viven dentro del asistente).
        g2 = QGroupBox("2 · Calibrar")
        c2 = QVBoxLayout(g2)
        self.btn_asistente = QPushButton("Asistente: dodecaedro nuevo…")
        self.btn_divot = QPushButton("Calibrar punta (dock)…")
        c2.addWidget(self.btn_asistente)
        c2.addWidget(self.btn_divot)
        c2.addStretch(1)
        g3 = QGroupBox("3 · Operar")
        c3 = QVBoxLayout(g3)
        self.btn_tracker = QPushButton("Arrancar tracker")
        self.btn_detener = QPushButton("Detener proceso")
        self.btn_detener.setEnabled(False)
        c3.addWidget(self.btn_tracker)
        c3.addWidget(self.btn_detener)
        c3.addStretch(1)
        fila_acc.addWidget(g1)
        fila_acc.addWidget(g2)
        fila_acc.addWidget(g3)
        raiz.addLayout(fila_acc)

        self.botones = {
            "ids": self.btn_ids, "camara": self.btn_camara,
            "calcam": self.btn_calcam,
            "asistente": self.btn_asistente, "divot": self.btn_divot,
            "tracker": self.btn_tracker, "detener": self.btn_detener,
        }

        # --- Log ---
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(8000)
        self.log.setFont(QFont("Consolas", 9))
        self.log.setPlaceholderText("Salida de los scripts y eventos del panel...")
        raiz.addWidget(self.log, stretch=1)

        self.setCentralWidget(central)

        # --- Cableado ---
        self.btn_refrescar.clicked.connect(self.refrescar)
        QShortcut(QKeySequence("F5"), self, activated=self.refrescar)
        self.combo.currentIndexChanged.connect(self._perfil_cambiado)
        self.btn_ids.clicked.connect(self._accion_ids)
        self.btn_camara.clicked.connect(self._accion_camara)
        self.btn_calcam.clicked.connect(self._accion_calcam)
        self.btn_asistente.clicked.connect(self._accion_asistente)
        self.btn_divot.clicked.connect(self._accion_divot)
        self.btn_tracker.clicked.connect(self._accion_tracker)
        self.btn_detener.clicked.connect(self._accion_detener)

        # Perfil inicial: CLI > ultima seleccion > canonico (ADR-015)
        if not perfiles:
            self.log_msg("[ROJO] No hay iter4/tracker_config*.yaml — nada que evaluar.")
            return
        objetivo = None
        if perfil_inicial:
            objetivo = Path(perfil_inicial).name
        elif self.settings.value("perfil_activo"):
            objetivo = Path(str(self.settings.value("perfil_activo"))).name
        idx = self.combo.findText(objetivo) if objetivo else -1
        if idx < 0:
            idx = self.combo.findText("tracker_config.yaml")
        self.combo.setCurrentIndex(max(idx, 0))
        self.refrescar()

    # ------------------------------------------------------------------
    def perfil_activo(self):
        return self.combo.currentData()

    def _perfil_cambiado(self, _idx):
        self.settings.setValue("perfil_activo", self.perfil_activo())
        self.resultado_camara = None
        # El asistente depende del perfil (semilla default, recetas): se
        # descarta y se recrea al reabrir.
        if self.asistente is not None:
            self.asistente.close()
            self.asistente = None
        self.refrescar()

    def log_msg(self, texto):
        self.log.appendPlainText(f"[{time.strftime('%H:%M:%S')}] [panel] {texto}")

    def _linea_hijo(self, texto):
        self.log.appendPlainText(texto)
        # brief-02 M5: feed en vivo al origen (monitor del BA en el asistente)
        if self.origen_actual is not None and hasattr(self.origen_actual,
                                                      "linea_hijo"):
            self.origen_actual.linea_hijo(texto)

    # ------------------------------------------------------------------
    def refrescar(self):
        ruta = self.perfil_activo()
        if not ruta:
            return
        self.chequeos, self._cfg = estado.evaluar_todo(ruta)
        if self.resultado_camara and self.resultado_camara[0] == ruta:
            self.chequeos = [self.resultado_camara[1] if c.clave == "camara"
                             else c for c in self.chequeos]
        for c in self.chequeos:
            if c.clave not in self.filas:
                fila = FilaSemaforo(c)
                self.filas[c.clave] = fila
                self.caja_sem.addWidget(fila)
            else:
                self.filas[c.clave].actualizar(c)
        self._chk = {c.clave: c for c in self.chequeos}
        self._set_botones()
        ok, malos = estado.apto_para_tracker(self.chequeos)
        self.log_msg(f"semaforos refrescados ({Path(ruta).name}): apto para "
                     f"tracker: {'SI' if ok else 'NO'}"
                     + ("" if ok else f" — bloquean: {malos}"))
        for c in self.chequeos:
            if c.estado == estado.ROJO:
                self.log_msg(f"  ROJO {c.titulo}: {c.detalle}")

    def _set_botones(self):
        corriendo = self.lanzador.hay_activo()

        def verde(k):
            return k in self._chk and self._chk[k].estado == estado.VERDE

        libre = not corriendo
        self.btn_ids.setEnabled(libre and verde("entorno") and verde("config"))
        self.btn_camara.setEnabled(libre and verde("config"))
        self.btn_calcam.setEnabled(libre and verde("entorno")
                                   and verde("config"))
        self.btn_asistente.setEnabled(libre and verde("entorno")
                                      and verde("config"))
        self.btn_divot.setEnabled(libre and verde("entorno")
                                  and verde("config") and verde("geometria"))
        ok, malos = estado.apto_para_tracker(self.chequeos)
        self.btn_tracker.setEnabled(libre and ok)
        self.btn_tracker.setToolTip(
            "" if ok else f"Bloqueado por: {', '.join(malos)} (fail-loud)")
        self.btn_divot.setToolTip(
            "" if verde("geometria") else
            "Requiere geometria CALIBRADA (la punta es del mismo ensamble)")
        self.btn_detener.setEnabled(corriendo)
        self.combo.setEnabled(libre)

    # ------------------------------------------------------------------
    def lanzar_receta(self, receta, origen=None):
        """Lanza una receta con eco del comando y confirmacion de overwrite
        (fail-loud). API publica: tambien la usa el asistente."""
        if self.lanzador.hay_activo():
            QMessageBox.warning(self, "Panel", "Ya hay un proceso corriendo. "
                                "Usar 'Detener proceso' primero.")
            return False
        if receta.clave != "ba":  # el BA ya valida overwrite en el asistente
            existentes = [o for o in receta.outputs
                          if (estado.RAIZ_CODIGO / o).exists()]
            if existentes:
                r = QMessageBox.question(
                    self, "Sobrescribir",
                    "Esta accion pisaria archivos existentes:\n  "
                    + "\n  ".join(str(e) for e in existentes)
                    + "\n\n¿Continuar?")
                if r != QMessageBox.StandardButton.Yes:
                    self.log_msg(f"{receta.clave}: cancelado por el usuario "
                                 f"(no sobrescribir)")
                    return False
        self.log_msg(f">> {receta.descripcion}")
        self.log_msg(f">> cwd: {receta.cwd}")
        self.log_msg(f">> comando: {receta.comando_legible()}")
        err = self.lanzador.lanzar(receta)
        if err:
            self.log_msg(f"ERROR: {err}")
            QMessageBox.critical(self, "Panel", err)
            return False
        self.origen_actual = origen
        self._set_botones()
        return True

    def _proceso_termino(self, receta, rc):
        veredicto = "OK" if rc == 0 else "FALLO — revisar el log (fail-loud)"
        self.log_msg(f"[fin] {receta.clave}: exit={rc} {veredicto}")
        if receta.clave == "sonda_camara":
            detalle = ""
            for ln in reversed(self.lanzador.buffer_actual()):
                if ln.startswith("[CAMARA]"):
                    detalle = ln.replace("[CAMARA] ", "")
                    break
            est = estado.VERDE if rc == 0 else estado.ROJO
            chi = estado.Chequeo("camara", "Camara", est,
                                 f"{detalle} (sondeada {time.strftime('%H:%M:%S')})")
            self.resultado_camara = (self.perfil_activo(), chi)
        origen = self.origen_actual
        self.origen_actual = None
        self.refrescar()
        if origen is not None:
            origen.proceso_termino(receta, rc, self.lanzador.buffer_actual())

    # ------------------------------------------------------------------
    def _accion_ids(self):
        self.lanzar_receta(recetas.receta_identificar_ids(self.perfil_activo()))

    def _accion_camara(self):
        self.lanzar_receta(recetas.receta_sonda_camara(self.perfil_activo()))

    def _accion_calcam(self):
        DialogoIntrinsecos(self).exec()

    def _accion_asistente(self):
        if self.asistente is None:
            self.asistente = AsistenteDodecaedro(self)
        self.asistente.show()
        self.asistente.raise_()

    def _accion_divot(self):
        receta = DialogoDivot.pedir(self, self.perfil_activo())
        if receta:
            self.lanzar_receta(receta)

    def _accion_tracker(self):
        cfg = self._cfg or {}
        puerto = ((cfg.get("igtlink") or {}).get("transforms_port", 18944))
        r = QMessageBox.question(
            self, "Tracker — Slicer primero",
            f"El tracker SE BLOQUEA si Slicer no esta conectado (CONTEXT §4.5).\n\n"
            f"¿Slicer ya esta conectado como cliente OpenIGTLink "
            f"(localhost:{puerto}, conector Active)?")
        if r != QMessageBox.StandardButton.Yes:
            self.log_msg("tracker: cancelado — conectar Slicer primero "
                         "(MANUAL_simplificado §4.1)")
            return
        self.lanzar_receta(recetas.receta_tracker(self.perfil_activo()))

    def _accion_detener(self):
        self.log_msg("solicitando detencion (primero 'q' a la ventana del "
                     "script, luego cierre duro si no responde)...")
        self.lanzador.detener_async()

    # ------------------------------------------------------------------
    def closeEvent(self, event):
        if self.lanzador.hay_activo():
            receta = self.lanzador.receta_activa()
            r = QMessageBox.question(
                self, "Salir",
                f"Hay un proceso corriendo ({receta.clave if receta else '?'}).\n"
                f"¿Detenerlo y salir?")
            if r != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.lanzador.detener()   # sincrono; a lo sumo unos segundos
        event.accept()


def main():
    ap = argparse.ArgumentParser(description="Panel de control (brief-02).")
    ap.add_argument("--perfil", default=None,
                    help="Perfil inicial (ruta o nombre del yaml).")
    ap.add_argument("--selftest", action="store_true",
                    help="Abre, refresca, imprime estados/botones/asistente, "
                         "cierra solo.")
    args = ap.parse_args()

    app = QApplication(sys.argv)
    panel = Panel(perfil_inicial=args.perfil)
    panel.show()

    if args.selftest:
        def dump_y_cerrar():
            print(f"[panel-selftest] perfil={Path(panel.perfil_activo()).name}")
            for c in panel.chequeos:
                print(f"[panel-selftest] {c.clave}={c.estado} :: {c.detalle}")
            ok, malos = estado.apto_para_tracker(panel.chequeos)
            print(f"[panel-selftest] apto_tracker={'SI' if ok else 'NO'}"
                  + ("" if ok else f" bloquean={malos}"))
            for clave, boton in panel.botones.items():
                print(f"[panel-selftest] boton_{clave}_habilitado="
                      f"{boton.isEnabled()}")
            # brief-02 M1: evidencia de la semilla default del asistente
            a = AsistenteDodecaedro(panel)
            print(f"[panel-selftest] asistente_semilla_default="
                  f"{a.combo_teo.currentText()}")
            print(f"[panel-selftest] asistente_semilla_info="
                  f"{a.lbl_ids_semilla.text()}")
            print(f"[panel-selftest] asistente_ba_defaults="
                  f"frames={a.spin_frames.value()},nfev={a.spin_nfev.value()},"
                  f"autocorte={a.chk_autocorte.isChecked()}")
            a.deleteLater()
            print("[panel-selftest] cerrando OK")
            panel.close()
            app.quit()
        QTimer.singleShot(1200, dump_y_cerrar)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
