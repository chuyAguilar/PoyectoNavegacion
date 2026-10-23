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
    """Parametros de iter4/calibrar_camara.py (meta 002, fase 4; P18): tablero
    impreso en 3D (9x6 casillas = esquinas interiores 8x5, 25 mm nominales).
    El camino normal: las medidas del calibrador (>= 5) y las casillas que
    abarca cada una; el dialogo calcula el lado (dos decimales, como
    calibrar_camara.lado_desde_medidas) y pasa --square-mm, --medidas-mm y
    --casillas-por-medida. Si solo se sabe el lado, se escribe a mano.
    Detector: "ambos" (por defecto) calibra con los dos sobre las mismas
    vistas y se queda el de menor RMS de control. Pasa --reporte y --luz."""

    def __init__(self, parent, ruta_cfg):
        super().__init__(parent)
        self.setWindowTitle("Calibrar camara con tablero")
        self.ruta_cfg = ruta_cfg
        form = QFormLayout(self)
        self.slug = recetas.slug_de_perfil(ruta_cfg)
        # El padre es DialogoIntrinsecos (tiene .panel) o el propio panel.
        panel = getattr(parent, "panel", parent)
        cam = ((getattr(panel, "_cfg", None) or {}).get("camera", {})) or {}
        modo = (f"{cam.get('width', 'W')}x{cam.get('height', 'H')}"
                if cam.get("width") and cam.get("height") else "WxH")
        self.edit_out = QLineEdit(f"iter4/data/intrinsecos_{self.slug}_{modo}.yml")
        form.addRow("Salida (.yml):", self.edit_out)
        self.edit_vistas = QLineEdit(f"../Claude outputs/camaras/vistas_{self.slug}")
        form.addRow("Carpeta de vistas (PNG):", self.edit_vistas)
        self.spin_cols = QSpinBox()
        self.spin_cols.setRange(3, 20)
        self.spin_cols.setValue(8)
        form.addRow("Esquinas interiores (horiz):", self.spin_cols)
        self.spin_rows = QSpinBox()
        self.spin_rows.setRange(3, 20)
        self.spin_rows.setValue(5)
        form.addRow("Esquinas interiores (vert):", self.spin_rows)
        self.edit_medidas = QLineEdit()
        self.edit_medidas.setPlaceholderText("149.1, 149.1, 149.1, 149.1, 149.4")
        form.addRow(f"Medidas del calibrador (mm, >= {recetas.MIN_MEDIDAS},\n"
                    "misma orilla, mismo tramo):", self.edit_medidas)
        self.spin_casillas = QSpinBox()
        self.spin_casillas.setRange(1, 9)
        self.spin_casillas.setValue(4)
        form.addRow("Casillas que abarca cada medida:", self.spin_casillas)
        self.spin_sq = QDoubleSpinBox()
        self.spin_sq.setRange(0.0, 100.0)
        self.spin_sq.setDecimals(2)
        self.spin_sq.setSingleStep(0.01)
        self.spin_sq.setValue(0.0)
        self.spin_sq.setSpecialValueText("medir con calibrador")
        self.spin_sq.setSuffix(" mm")
        form.addRow("Lado de la casilla:", self.spin_sq)
        self.lbl_lado = QLabel()
        self.lbl_lado.setWordWrap(True)
        form.addRow(self.lbl_lado)
        self.combo_det = QComboBox()
        self.combo_det.addItems(list(recetas.DETECTORES_CALIBRACION))
        form.addRow("Detector de esquinas:", self.combo_det)
        self.spin_min = QSpinBox()
        self.spin_min.setRange(5, 60)
        self.spin_min.setValue(15)
        form.addRow("Vistas minimas en el ajuste:", self.spin_min)
        self.spin_ctrl = QSpinBox()
        self.spin_ctrl.setRange(0, 10)
        self.spin_ctrl.setValue(3)
        form.addRow("Vistas de control (fuera del ajuste):", self.spin_ctrl)
        self.edit_luz = QLineEdit(recetas.LUZ_POR_DEFECTO)
        form.addRow("Luz (caja y sala):", self.edit_luz)
        self._reporte_auto = self._reporte_defecto()
        self.edit_reporte = QLineEdit(self._reporte_auto)
        form.addRow("Reporte (.json):", self.edit_reporte)
        nota = QLabel("El lado es el MEDIDO con calibrador, nunca el nominal "
                      "(el RMS no ve un error de escala). ESPACIO=capturar vista "
                      "(20-30, bordes y esquinas de la imagen, inclinaciones "
                      "hasta ~45 grados, 40-80 cm; la rejilla 4x3 se pone verde "
                      "donde ya hay esquinas), u=quitar la ultima, q=calibrar y "
                      "guardar. Con 'ambos' se calibra con los dos detectores "
                      "y gana el de menor RMS de control. Criterio: RMS <= 0.5 "
                      "px, control <= 0.75 px, cobertura >= 0.8. Si se cumple, "
                      "el panel ofrece apuntar el perfil al .yml nuevo.")
        nota.setWordWrap(True)
        form.addRow(nota)
        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        form.addRow(botones)
        self.receta = None
        self.edit_medidas.textChanged.connect(self._actualizar_lado)
        self.spin_casillas.valueChanged.connect(self._actualizar_lado)
        self.combo_det.currentIndexChanged.connect(self._actualizar_reporte)
        self.edit_vistas.textChanged.connect(self._actualizar_reporte)
        self._actualizar_lado()

    def _reporte_defecto(self):
        return recetas.reporte_por_defecto(self.edit_vistas.text().strip() or ".",
                                           self.slug, self.combo_det.currentText())

    def _actualizar_reporte(self, *_):
        """El reporte sigue al detector y a la carpeta mientras no se edite a mano."""
        if self.edit_reporte.text().strip() == self._reporte_auto:
            self._reporte_auto = self._reporte_defecto()
            self.edit_reporte.setText(self._reporte_auto)

    def _actualizar_lado(self, *_):
        texto = self.edit_medidas.text().strip()
        if not texto:
            self.spin_sq.setReadOnly(False)
            self.lbl_lado.setText("Sin medidas: escribe el lado medido a mano. "
                                  "El camino normal son las medidas del "
                                  "calibrador.")
            return
        self.spin_sq.setReadOnly(True)
        try:
            medidas = recetas.parsear_medidas(texto)
            lado = recetas.lado_de_medidas(medidas, self.spin_casillas.value())
        except ValueError as e:
            self.spin_sq.setValue(0.0)
            self.lbl_lado.setText(f"Medidas: {e}")
            return
        self.spin_sq.setValue(lado)
        media = sum(medidas) / len(medidas)
        falta = ("" if len(medidas) >= recetas.MIN_MEDIDAS else
                 f" — faltan medidas: hacen falta {recetas.MIN_MEDIDAS}")
        self.lbl_lado.setText(f"Lado: media {media:.3f} mm / "
                              f"{self.spin_casillas.value()} casillas = "
                              f"{lado:.2f} mm ({len(medidas)} medidas){falta}")

    def componer(self):
        """La receta con lo escrito en el dialogo (ValueError si algo no vale)."""
        texto = self.edit_medidas.text().strip()
        medidas = None
        if texto:
            medidas = recetas.parsear_medidas(texto)
            if len(medidas) < recetas.MIN_MEDIDAS:
                raise ValueError(f"Hacen falta al menos {recetas.MIN_MEDIDAS} "
                                 f"medidas del calibrador; hay {len(medidas)}.")
            lado = recetas.lado_de_medidas(medidas, self.spin_casillas.value())
        else:
            lado = self.spin_sq.value()
            if lado < 5.0:
                raise ValueError("Escribe las medidas del calibrador (>= 5, "
                                 "del mismo tramo) o, si solo sabes el lado "
                                 "medido, escribelo con dos decimales; el "
                                 "nominal no vale.")
        return recetas.receta_calibrar_camara(
            self.ruta_cfg,
            output=self.edit_out.text().strip(),
            square_mm=lado,
            vistas_dir=self.edit_vistas.text().strip(),
            cols=self.spin_cols.value(),
            rows=self.spin_rows.value(),
            detector=self.combo_det.currentText(),
            min_vistas=self.spin_min.value(),
            n_control=self.spin_ctrl.value(),
            luz=self.edit_luz.text().strip() or None,
            medidas_mm=medidas,
            casillas_por_medida=self.spin_casillas.value(),
            reporte=self.edit_reporte.text().strip() or None,
        )

    def accept(self):
        try:
            self.receta = self.componer()
        except (ValueError, FileNotFoundError) as e:
            QMessageBox.warning(self, "Calibrar camara", str(e))
            return
        super().accept()


def yml_del_perfil(ruta_cfg, cfg=None):
    """(ruta del .yml al que apunta el perfil, None) o (None, motivo)."""
    try:
        cfg = cfg if cfg is not None else estado.cargar_perfil(ruta_cfg)
    except Exception as e:
        return None, f"el perfil no se puede leer: {e}"
    declarada = ((cfg or {}).get("camera") or {}).get("calibration_file") or ""
    if not declarada:
        return None, (f"{Path(ruta_cfg).name} no tiene calibration_file: "
                      f"calibra y apunta el perfil primero")
    ruta = estado.resolver_ruta(declarada, Path(ruta_cfg).parent)
    if ruta is None:
        return None, f"calibration_file no existe: {declarada}"
    return ruta, None


class DialogoComprobarEscala(QDialog):
    """Parametros de iter4/comprobar_escala.py (meta 002, fase 4; P18): el
    perfil activo ya apunta a un .yml; el lado y el detector salen de ese
    .yml (el ganador de la calibracion) y se pueden cambiar."""

    def __init__(self, parent, ruta_cfg, ruta_yml):
        super().__init__(parent)
        self.setWindowTitle("Comprobar escala con regla")
        self.ruta_cfg = ruta_cfg
        form = QFormLayout(self)
        slug = recetas.slug_de_perfil(ruta_cfg)
        try:
            campos = perfil_editor.leer_campos_yml(ruta_yml)
        except OSError:
            campos = {}
        info = QLabel(f"Perfil: {Path(ruta_cfg).name}  |  .yml: {Path(ruta_yml).name}\n"
                      f"El .yml declara: detector {campos.get('detector', '-')}, "
                      f"lado {campos.get('square_mm', '-')} mm, criterio cumplido "
                      f"{'si' if campos.get('criterio_cumplido') == '1' else 'NO o sin dato'}")
        info.setWordWrap(True)
        form.addRow(info)
        self.spin_sq = QDoubleSpinBox()
        self.spin_sq.setRange(0.0, 100.0)
        self.spin_sq.setDecimals(2)
        self.spin_sq.setSingleStep(0.01)
        self.spin_sq.setSpecialValueText("medir con calibrador")
        self.spin_sq.setSuffix(" mm")
        try:
            self.spin_sq.setValue(round(float(campos.get("square_mm", 0.0)), 2))
        except ValueError:
            self.spin_sq.setValue(0.0)
        form.addRow("Lado de la casilla (el de la calibracion):", self.spin_sq)
        self.combo_det = QComboBox()
        self.combo_det.addItems(list(recetas.DETECTORES_ESCALA))
        if campos.get("detector") in recetas.DETECTORES_ESCALA:
            self.combo_det.setCurrentText(campos["detector"])
        form.addRow("Detector (el ganador):", self.combo_det)
        self.spin_cols = QSpinBox()
        self.spin_cols.setRange(3, 20)
        self.spin_cols.setValue(8)
        form.addRow("Esquinas interiores (horiz):", self.spin_cols)
        self.spin_rows = QSpinBox()
        self.spin_rows.setRange(3, 20)
        self.spin_rows.setValue(5)
        form.addRow("Esquinas interiores (vert):", self.spin_rows)
        self.edit_pos = QLineEdit(recetas.POSICIONES_ESCALA)
        form.addRow("Posiciones de la regla (mm):", self.edit_pos)
        self.spin_frames = QSpinBox()
        self.spin_frames.setRange(1, 300)
        self.spin_frames.setValue(recetas.FRAMES_POR_POSICION)
        form.addRow("Frames por posicion:", self.spin_frames)
        self.edit_luz = QLineEdit(recetas.LUZ_POR_DEFECTO)
        form.addRow("Luz (caja y sala):", self.edit_luz)
        self.edit_salida = QLineEdit(f"../Claude outputs/camaras/escala_{slug}.json")
        form.addRow("Salida (.json):", self.edit_salida)
        self.spin_timeout = QSpinBox()
        self.spin_timeout.setRange(60, 3600)
        self.spin_timeout.setValue(900)
        self.spin_timeout.setSuffix(" s")
        form.addRow("Autocierre del script:", self.spin_timeout)
        nota = QLabel("El tablero va sobre una base rigida con la regla pegada. "
                      "Va y vuelve entre las dos marcas SIN GIRAR el tablero; "
                      "en cada posicion, quieto, ESPACIO (la ventana dice que "
                      "lectura de la regla toca). q sale antes. Criterio: "
                      "|error| <= 1.0 mm por cada 100 mm de paso (0.8 mm con "
                      "pasos de 80 mm).")
        nota.setWordWrap(True)
        form.addRow(nota)
        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        form.addRow(botones)
        self.receta = None

    def componer(self):
        if self.spin_sq.value() < 5.0:
            raise ValueError("El lado de la casilla tiene que ser el medido "
                             "con calibrador (el de la calibracion).")
        return recetas.receta_comprobar_escala(
            self.ruta_cfg,
            square_mm=self.spin_sq.value(),
            detector=self.combo_det.currentText(),
            desplazamientos_mm=self.edit_pos.text().strip(),
            salida=self.edit_salida.text().strip(),
            cols=self.spin_cols.value(),
            rows=self.spin_rows.value(),
            frames_por_posicion=self.spin_frames.value(),
            luz=self.edit_luz.text().strip() or None,
            timeout=self.spin_timeout.value(),
        )

    def accept(self):
        try:
            self.receta = self.componer()
        except (ValueError, FileNotFoundError) as e:
            QMessageBox.warning(self, "Comprobar escala", str(e))
            return
        super().accept()


def apuntar_perfil(padre, panel, ruta_yml, perfil, encabezado=""):
    """Apunta camera.calibration_file del perfil al .yml: valida, muestra el
    antes/despues, pide confirmacion y aplica con backup (perfil_editor,
    ADR-018: la unica mutacion de config del panel). True si se aplico."""
    err = perfil_editor.validar_yml_intrinsecos(ruta_yml)
    if err:
        QMessageBox.warning(padre, "Intrinsecos",
                            f"El .yml NO valida como calibracion: {err}")
        return False
    valor = perfil_editor.valor_para_perfil(ruta_yml, estado.DIR_DATA)
    try:
        actual, nueva = perfil_editor.previsualizar_cambio(perfil, valor)
    except (ValueError, OSError) as e:
        QMessageBox.critical(padre, "Intrinsecos", str(e))
        return False
    r = QMessageBox.question(
        padre, "Confirmar edicion del perfil (ADR-018)",
        (f"{encabezado}\n\n" if encabezado else "")
        + f"Se editara {Path(perfil).name} — UNICA linea, con backup "
        f"timestampeado:\n\n"
        f"  ANTES:    {actual.strip()}\n"
        f"  DESPUES:  {nueva.strip()}\n\n¿Aplicar?")
    if r != QMessageBox.StandardButton.Yes:
        panel.log_msg(f"perfil NO editado (cancelado): {Path(perfil).name}")
        return False
    try:
        backup, _a, _n = perfil_editor.aplicar_cambio(perfil, valor)
    except (ValueError, OSError) as e:
        QMessageBox.critical(padre, "Intrinsecos", f"NO aplicado: {e}")
        return False
    panel.log_msg(f"perfil editado (ADR-018): {Path(perfil).name} -> "
                  f"calibration_file: {valor}")
    panel.log_msg(f"  backup: {backup.name}")
    panel.refrescar()
    return True


class DialogoIntrinsecos(QDialog):
    """M3: gestion de intrinsecos del perfil activo.
    (a) Correr una calibracion con tablero (calibrar_camara.py).
    (b) Comprobar la escala con regla (comprobar_escala.py; P18), con el .yml
        al que ya apunta el perfil.
    (c) Apuntar camera.calibration_file del perfil a un .yml validado —
        UNICA mutacion de config permitida (ADR-018): edicion textual
        quirurgica con backup, via perfil_editor.py."""

    def __init__(self, panel):
        super().__init__(panel)
        self.panel = panel
        self.setWindowTitle("Calibracion de camara e intrinsecos (M3)")
        self.resize(520, 300)
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

        self.yml_activo, motivo = yml_del_perfil(panel.perfil_activo(), cfg)
        self.btn_escala = QPushButton("Comprobar escala con regla…")
        self.btn_escala.clicked.connect(self._comprobar_escala)
        self.btn_escala.setEnabled(self.yml_activo is not None)
        self.btn_escala.setToolTip(
            f"Con {self.yml_activo.name}" if self.yml_activo is not None else motivo)
        caja.addWidget(self.btn_escala)

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

    def _comprobar_escala(self):
        if self.yml_activo is None:
            return
        d = DialogoComprobarEscala(self, self.panel.perfil_activo(), self.yml_activo)
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
        if apuntar_perfil(self, self.panel, ruta_yml, self.panel.perfil_activo()):
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
        if receta.clave == "calibrar_camara":
            self._ofrecer_apuntar(receta, rc)

    def _ofrecer_apuntar(self, receta, rc):
        """P18: si la calibracion cumple el criterio, ofrece apuntar el perfil
        al .yml nuevo con el mecanismo de siempre (apuntar_perfil, ADR-018).
        Si no lo cumple, no lo ofrece y dice por que en el log."""
        salida = recetas.valor_arg(receta.argv, "--output")
        perfil = recetas.valor_arg(receta.argv, "--config")
        if not salida or not perfil:
            return
        ruta_yml = Path(salida)
        ruta_yml = ruta_yml if ruta_yml.is_absolute() else estado.RAIZ_CODIGO / ruta_yml
        perfil = Path(perfil)
        perfil = perfil if perfil.is_absolute() else estado.RAIZ_CODIGO / perfil
        try:
            cfg = estado.cargar_perfil(perfil)
        except Exception as e:
            self.log_msg(f"calibracion: no se puede leer el perfil {perfil.name}: {e}")
            return
        actual = ((cfg or {}).get("camera") or {}).get("calibration_file") or ""
        ok, valor = perfil_editor.ofrecer_apuntar(rc, ruta_yml, actual, estado.DIR_DATA)
        if not ok:
            self.log_msg(f"calibracion: no se ofrece apuntar el perfil: {valor}")
            return
        campos = perfil_editor.leer_campos_yml(ruta_yml)
        encabezado = (f"La calibracion cumple el criterio (detector "
                      f"{campos.get('detector', '?')}, RMS de control "
                      f"{campos.get('rms_control_px', '?')[:6]} px). Se ofrece "
                      f"apuntar el perfil al .yml nuevo: {valor}")
        apuntar_perfil(self, self, ruta_yml, perfil, encabezado)

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
            # P18: los dialogos de calibracion y escala componen su receta sin
            # lanzarla (ninguna camara se abre aqui).
            d = DialogoCalibrarCamara(panel, panel.perfil_activo())
            d.edit_medidas.setText("149.1, 149.1, 149.1, 149.1, 149.4")
            d.spin_casillas.setValue(6)
            r = d.componer()
            print(f"[panel-selftest] calcam_lado={d.spin_sq.value():.2f}")
            print(f"[panel-selftest] calcam_argv={' '.join(r.argv[2:])}")
            d.deleteLater()
            gs1 = estado.DIR_ITER4 / "tracker_config_gs1.yaml"
            yml, motivo = yml_del_perfil(gs1)
            if yml is None:
                print(f"[panel-selftest] escala_no_disponible={motivo}")
            else:
                e = DialogoComprobarEscala(panel, str(gs1), yml)
                print(f"[panel-selftest] escala_argv={' '.join(e.componer().argv[2:])}")
                e.deleteLater()
            print("[panel-selftest] cerrando OK")
            panel.close()
            app.quit()
        QTimer.singleShot(1200, dump_y_cerrar)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
