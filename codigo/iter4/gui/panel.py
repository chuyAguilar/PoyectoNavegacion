# -*- coding: utf-8 -*-
"""
panel.py — Panel de control GUI (brief-01, iter 1). PySide6.

Ventana unica: selector de perfil + semaforos de prerrequisitos + botones que
lanzan los scripts EXISTENTES como subprocesos (la GUI solo orquesta, no
reescribe logica) + panel de log con la salida en vivo.

Grupos de acciones (brief §4):
  1 Verificar/Preparar: identificar IDs, probar camara (bajo demanda).
  2 Calibrar: capturar dataset BA, correr BA, calibrar punta (dock),
    asistente "dodecaedro nuevo" (captura -> BA -> geometria calibrada).
  3 Operar: tracker (gating duro + recordatorio de Slicer), detener.

Uso (desde codigo\, con el venv):
    python iter4\gui\panel.py
    python iter4\gui\panel.py --selftest      # abre, refresca, imprime y cierra solo
    python iter4\gui\panel.py --perfil iter4/tracker_config_doctor.yaml
Teclas: F5 = refrescar semaforos.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

from PySide6.QtCore import QObject, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox,
    QVBoxLayout, QWidget,
)

import estado
import procesos
import recetas

COLORES = {
    estado.VERDE: "#1e8e3e",
    estado.AMARILLO: "#e8a100",
    estado.ROJO: "#c5221f",
    estado.GRIS: "#8a8a8a",
}

RE_NOMBRE_VALIDO = re.compile(r"^[A-Za-z0-9_\-]+$")


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


# ============================================================================
# Dialogos de parametros (defaults desde recetas.py; todo editable y visible)
# ============================================================================

def _geometrias(solo_teoricas=False):
    todas = sorted(estado.DIR_DATA.glob("reference_*.txt"))
    if solo_teoricas:
        return [p for p in todas if "calibrado" not in p.name.lower()]
    # teoricas primero, calibradas despues (para elegir semillas comodo)
    teo = [p for p in todas if "calibrado" not in p.name.lower()]
    cal = [p for p in todas if "calibrado" in p.name.lower()]
    return teo + cal


def _datasets():
    return sorted(estado.DIR_DATA.glob("*.npz"),
                  key=lambda p: p.stat().st_mtime, reverse=True)


class DialogoCaptura(QDialog):
    """Parametros de captura_calibracion.py. geometry_file SIEMPRE explicito
    (el default del script cae en la teorica vieja — CONTEXT §4)."""

    def __init__(self, parent, ruta_cfg, cfg):
        super().__init__(parent)
        self.setWindowTitle("Capturar dataset para BA")
        self.ruta_cfg = ruta_cfg
        form = QFormLayout(self)
        self.combo_geom = QComboBox()
        geom_perfil = estado.geometria_del_perfil(cfg, ruta_cfg)
        for p in _geometrias():
            self.combo_geom.addItem(p.name, str(p))
        if geom_perfil is not None:
            i = self.combo_geom.findText(Path(geom_perfil).name)
            if i >= 0:
                self.combo_geom.setCurrentIndex(i)
        form.addRow("Geometria (para IDs):", self.combo_geom)
        self.spin_dur = QSpinBox()
        self.spin_dur.setRange(10, 600)
        self.spin_dur.setValue(60)
        self.spin_dur.setSuffix(" s")
        form.addRow("Duracion:", self.spin_dur)
        slug = recetas.slug_de_perfil(ruta_cfg)
        self.edit_out = QLineEdit(f"iter4/data/captura_ba_{slug}.npz")
        form.addRow("Dataset de salida:", self.edit_out)
        self.spin_min = QSpinBox()
        self.spin_min.setRange(1, 6)
        self.spin_min.setValue(2)
        form.addRow("Min markers por frame:", self.spin_min)
        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        form.addRow(botones)
        self.receta = None

    def accept(self):
        try:
            self.receta = recetas.receta_captura(
                self.ruta_cfg,
                geometry_file=self.combo_geom.currentData(),
                duracion=self.spin_dur.value(),
                output=self.edit_out.text().strip(),
                min_markers=self.spin_min.value(),
            )
        except (ValueError, FileNotFoundError) as e:
            QMessageBox.warning(self, "Captura", str(e))
            return
        super().accept()

    @staticmethod
    def pedir(parent, ruta_cfg, cfg):
        d = DialogoCaptura(parent, ruta_cfg, cfg)
        return d.receta if d.exec() == QDialog.DialogCode.Accepted else None


class DialogoBA(QDialog):
    """Parametros de calibrar_rigid_body.py. Defaults v2 (--ancla 3
    --marker-mm 14.6 --no-sparse --no-depth, ADR-008/009, CONTEXT §4.13)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Bundle adjustment (offline)")
        form = QFormLayout(self)
        self.combo_in = QComboBox()
        for p in _datasets():
            self.combo_in.addItem(p.name, str(p))
        form.addRow("Dataset (.npz):", self.combo_in)
        self.combo_teo = QComboBox()
        for p in _geometrias():
            self.combo_teo.addItem(p.name, str(p))
        i = self.combo_teo.findText("reference_dodecaedro_v2.txt")
        if i >= 0:
            self.combo_teo.setCurrentIndex(i)
        self.combo_teo.currentIndexChanged.connect(self._teorico_cambiado)
        form.addRow("Teorica semilla:", self.combo_teo)
        self.edit_out = QLineEdit()
        form.addRow("Geometria de salida:", self.edit_out)
        self.spin_ancla = QSpinBox()
        self.spin_ancla.setRange(0, 999)
        self.spin_ancla.setValue(recetas.BA_V2["ancla"])
        form.addRow("Ancla (ID):", self.spin_ancla)
        self.spin_mm = QDoubleSpinBox()
        self.spin_mm.setRange(5.0, 50.0)
        self.spin_mm.setDecimals(1)
        self.spin_mm.setSingleStep(0.1)
        self.spin_mm.setValue(recetas.BA_V2["marker_mm"])
        self.spin_mm.setSuffix(" mm")
        form.addRow("Lado del marker:", self.spin_mm)
        self.spin_frames = QSpinBox()
        self.spin_frames.setRange(0, 5000)
        self.spin_frames.setValue(recetas.BA_V2["max_frames"])
        form.addRow("Max frames (0=todos):", self.spin_frames)
        self.spin_nfev = QSpinBox()
        self.spin_nfev.setRange(10, 10000)
        self.spin_nfev.setValue(recetas.BA_V2["max_nfev"])
        form.addRow("Max nfev:", self.spin_nfev)
        self.chk_nosparse = QCheckBox("(el dataset v2 lo exige — ADR-009)")
        self.chk_nosparse.setChecked(True)
        form.addRow("--no-sparse:", self.chk_nosparse)
        self.chk_nodepth = QCheckBox("(BA solo-2D — ADR-008)")
        self.chk_nodepth.setChecked(True)
        form.addRow("--no-depth:", self.chk_nodepth)
        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        form.addRow(botones)
        self.receta = None
        self._teorico_cambiado()

    def _teorico_cambiado(self, *_):
        teo = self.combo_teo.currentData()
        if not teo:
            return
        stem = Path(teo).stem
        propuesta = f"iter4/data/{stem}_calibrado.txt"
        if (estado.RAIZ_CODIGO / propuesta).exists():
            propuesta = f"iter4/data/{stem}_recalibrado.txt"
        self.edit_out.setText(propuesta)
        try:
            ids = estado.parsear_geometria(teo)
            if ids and self.spin_ancla.value() not in ids:
                self.spin_ancla.setValue(min(ids))
        except OSError:
            pass

    def _crear(self, sobrescribir=False):
        return recetas.receta_ba(
            input_npz=self.combo_in.currentData(),
            teorico=self.combo_teo.currentData(),
            output=self.edit_out.text().strip(),
            ancla=self.spin_ancla.value(),
            marker_mm=self.spin_mm.value(),
            max_frames=self.spin_frames.value(),
            max_nfev=self.spin_nfev.value(),
            no_sparse=self.chk_nosparse.isChecked(),
            no_depth=self.chk_nodepth.isChecked(),
            sobrescribir=sobrescribir,
        )

    def accept(self):
        teo = self.combo_teo.currentData()
        if teo:
            try:
                ids = estado.parsear_geometria(teo)
                if ids and self.spin_ancla.value() not in ids:
                    QMessageBox.warning(
                        self, "BA", f"El ancla ID {self.spin_ancla.value()} no "
                        f"esta en la teorica ({Path(teo).name}: IDs "
                        f"{min(ids)}-{max(ids)}). El BA abortaria.")
                    return
            except OSError as e:
                QMessageBox.warning(self, "BA", f"Teorica ilegible: {e}")
                return
        try:
            self.receta = self._crear()
        except (ValueError, FileNotFoundError) as e:
            if "CALIBRADA" in str(e):
                r = QMessageBox.question(
                    self, "BA — sobrescribir",
                    str(e) + "\n\n¿Sobrescribir de todos modos?")
                if r != QMessageBox.StandardButton.Yes:
                    return
                try:
                    self.receta = self._crear(sobrescribir=True)
                except (ValueError, FileNotFoundError) as e2:
                    QMessageBox.warning(self, "BA", str(e2))
                    return
            else:
                QMessageBox.warning(self, "BA", str(e))
                return
        super().accept()

    @staticmethod
    def pedir(parent):
        d = DialogoBA(parent)
        return d.receta if d.exec() == QDialog.DialogCode.Accepted else None


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


class AsistenteDodecaedro(QDialog):
    """Flujo "dar de alta un dodecaedro nuevo" (brief §2.4): teorica semilla ->
    capturar dataset -> correr BA -> geometria *_calibrado.txt. Encadena los
    scripts existentes en el orden correcto; NO edita el YAML del perfil
    (decision §E.1: la GUI muestra la instruccion final)."""

    def __init__(self, panel):
        super().__init__(panel)
        self.setWindowTitle("Asistente: dodecaedro nuevo (captura → BA)")
        self.panel = panel
        self.resize(560, 460)
        caja = QVBoxLayout(self)

        form = QFormLayout()
        self.combo_teo = QComboBox()
        for p in _geometrias(solo_teoricas=True):
            self.combo_teo.addItem(p.name, str(p))
        self.combo_teo.currentIndexChanged.connect(self._teorica_cambiada)
        form.addRow("Teorica semilla (IDs nuevos):", self.combo_teo)
        self.edit_nombre = QLineEdit("reference_dodecaedro_nuevo")
        form.addRow("Nombre base de salida:", self.edit_nombre)
        self.spin_ancla = QSpinBox()
        self.spin_ancla.setRange(0, 999)
        form.addRow("Ancla (ID, cara superior):", self.spin_ancla)
        self.spin_mm = QDoubleSpinBox()
        self.spin_mm.setRange(5.0, 50.0)
        self.spin_mm.setDecimals(1)
        self.spin_mm.setValue(recetas.BA_V2["marker_mm"])
        self.spin_mm.setSuffix(" mm")
        form.addRow("Lado del marker:", self.spin_mm)
        self.spin_dur = QSpinBox()
        self.spin_dur.setRange(10, 600)
        self.spin_dur.setValue(60)
        self.spin_dur.setSuffix(" s")
        form.addRow("Duracion de captura:", self.spin_dur)
        caja.addLayout(form)

        self.lbl_captura = QLabel("1) Capturar dataset: pendiente")
        self.lbl_ba = QLabel("2) Bundle adjustment: pendiente")
        self.lbl_resumen = QLabel("")
        self.lbl_resumen.setWordWrap(True)
        self.lbl_resumen.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        caja.addWidget(self.lbl_captura)
        caja.addWidget(self.lbl_ba)
        caja.addWidget(self.lbl_resumen)

        fila_botones = QHBoxLayout()
        self.btn_capturar = QPushButton("1) Capturar dataset")
        self.btn_ba = QPushButton("2) Correr BA")
        self.btn_ba.setEnabled(False)
        self.btn_copiar = QPushButton("Copiar ruta de la geometria")
        self.btn_copiar.setEnabled(False)
        fila_botones.addWidget(self.btn_capturar)
        fila_botones.addWidget(self.btn_ba)
        fila_botones.addWidget(self.btn_copiar)
        caja.addLayout(fila_botones)

        self.btn_capturar.clicked.connect(self._capturar)
        self.btn_ba.clicked.connect(self._correr_ba)
        self.btn_copiar.clicked.connect(self._copiar)
        self._teorica_cambiada()

    # ------------------------------------------------------------------
    def _teorica_cambiada(self, *_):
        teo = self.combo_teo.currentData()
        if not teo:
            return
        try:
            ids = estado.parsear_geometria(teo)
            if ids:
                self.spin_ancla.setValue(min(ids))
        except OSError:
            pass

    def _nombre(self):
        return self.edit_nombre.text().strip()

    def _dataset(self):
        slug = self._nombre().replace("reference_", "")
        return f"iter4/data/captura_ba_{slug}.npz"

    def _salida(self):
        return f"iter4/data/{self._nombre()}_calibrado.txt"

    def _validar_campos(self):
        if not self.combo_teo.currentData():
            QMessageBox.warning(self, "Asistente", "No hay teorica semilla "
                                "(reference_*.txt sin 'calibrado') en data\\.")
            return False
        if not RE_NOMBRE_VALIDO.match(self._nombre()):
            QMessageBox.warning(self, "Asistente", "Nombre base invalido: usar "
                                "solo letras, numeros, '_' y '-'.")
            return False
        teo = self.combo_teo.currentData()
        ids = estado.parsear_geometria(teo)
        if not ids:
            QMessageBox.warning(self, "Asistente",
                                f"La teorica {Path(teo).name} no tiene lineas "
                                f"validas (vacia/corrupta).")
            return False
        if self.spin_ancla.value() not in ids:
            QMessageBox.warning(self, "Asistente",
                                f"El ancla ID {self.spin_ancla.value()} no esta "
                                f"en la teorica (IDs {min(ids)}-{max(ids)}).")
            return False
        return True

    def _set_campos(self, habilitar):
        for w in (self.combo_teo, self.edit_nombre, self.spin_ancla,
                  self.spin_mm, self.spin_dur):
            w.setEnabled(habilitar)

    # ------------------------------------------------------------------
    def _capturar(self):
        if not self._validar_campos():
            return
        try:
            receta = recetas.receta_captura(
                self.panel.perfil_activo(),
                geometry_file=self.combo_teo.currentData(),
                duracion=self.spin_dur.value(),
                output=self._dataset(),
            )
        except (ValueError, FileNotFoundError) as e:
            QMessageBox.warning(self, "Asistente", str(e))
            return
        self.lbl_captura.setText("1) Capturar dataset: CORRIENDO "
                                 "(rota el dodecaedro mostrando TODAS las caras)")
        self.btn_capturar.setEnabled(False)
        self.btn_ba.setEnabled(False)
        self._set_campos(False)
        if not self.panel.lanzar_receta(receta, origen=self):
            # cancelado (overwrite) o no se pudo lanzar: restaurar honesto
            self.lbl_captura.setText("1) Capturar dataset: no lanzado (cancelado "
                                     "o proceso ocupado)")
            self.btn_capturar.setEnabled(True)
            self._set_campos(True)

    def _correr_ba(self):
        try:
            receta = recetas.receta_ba(
                input_npz=self._dataset(),
                teorico=self.combo_teo.currentData(),
                output=self._salida(),
                ancla=self.spin_ancla.value(),
                marker_mm=self.spin_mm.value(),
            )
        except (ValueError, FileNotFoundError) as e:
            if "CALIBRADA" in str(e):
                r = QMessageBox.question(self, "Asistente — sobrescribir",
                                         str(e) + "\n\n¿Sobrescribir?")
                if r != QMessageBox.StandardButton.Yes:
                    return
                receta = recetas.receta_ba(
                    input_npz=self._dataset(),
                    teorico=self.combo_teo.currentData(),
                    output=self._salida(),
                    ancla=self.spin_ancla.value(),
                    marker_mm=self.spin_mm.value(),
                    sobrescribir=True,
                )
            else:
                QMessageBox.warning(self, "Asistente", str(e))
                return
        self.lbl_ba.setText("2) Bundle adjustment: CORRIENDO (puede tardar "
                            "MINUTOS largos; el progreso de scipy se ve en el log)")
        self.btn_ba.setEnabled(False)
        self.btn_capturar.setEnabled(False)
        self._set_campos(False)
        if not self.panel.lanzar_receta(receta, origen=self):
            self.lbl_ba.setText("2) Bundle adjustment: no lanzado (cancelado "
                                "o proceso ocupado)")
            self.btn_ba.setEnabled(True)
            self.btn_capturar.setEnabled(True)
            self._set_campos(True)

    def _copiar(self):
        ruta_para_yaml = f"data/{self._nombre()}_calibrado.txt"
        QGuiApplication.clipboard().setText(ruta_para_yaml)
        self.panel.log_msg(f"asistente: copiado al portapapeles: {ruta_para_yaml}")

    # ------------------------------------------------------------------
    def proceso_termino(self, receta, rc, buffer):
        """Llamado por el panel al terminar un proceso lanzado por este
        asistente. La cadena se corta VISIBLEMENTE si un paso falla."""
        if receta.clave == "captura":
            if rc == 0:
                utiles = ""
                for ln in reversed(buffer):
                    m = re.search(r"Frames utiles:\s*(\d+)", ln)
                    if m:
                        utiles = f" ({m.group(1)} frames utiles)"
                        break
                self.lbl_captura.setText(f"1) Capturar dataset: OK{utiles} "
                                         f"→ {self._dataset()}")
                self.lbl_ba.setText("2) Bundle adjustment: listo para correr")
                self.btn_ba.setEnabled(True)
            else:
                self.lbl_captura.setText(
                    f"1) Capturar dataset: FALLO (exit {rc}) — revisar el log; "
                    f"la cadena se corta aca")
            self.btn_capturar.setEnabled(True)
            self._set_campos(True)
        elif receta.clave == "ba":
            if rc == 0:
                rmse = ""
                for ln in buffer:
                    m = re.search(r"RMSE 2D:\s*([\d.]+)\s*->\s*([\d.]+)\s*px", ln)
                    if m:
                        rmse = f"RMSE 2D {m.group(1)} → {m.group(2)} px. "
                salida_abs = estado.RAIZ_CODIGO / self._salida()
                existe = salida_abs.exists()
                self.lbl_ba.setText(f"2) Bundle adjustment: OK → {self._salida()}"
                                    if existe else
                                    f"2) BA termino exit 0 pero NO se encuentra "
                                    f"{self._salida()} — revisar el log")
                self.lbl_resumen.setText(
                    f"{rmse}ADVERTENCIA (ADR-003): el RMSE que reporta el BA no "
                    f"es confiable por si solo — validar por reproyeccion "
                    f"independiente antes de operar.\n\n"
                    f"Para usar la geometria nueva, editar el perfil YAML a "
                    f"mano (la GUI no muta configs):\n"
                    f"  rigid_bodies[0].geometry_file: data/{self._nombre()}"
                    f"_calibrado.txt")
                self.btn_copiar.setEnabled(existe)
            else:
                self.lbl_ba.setText(f"2) Bundle adjustment: FALLO (exit {rc}) — "
                                    f"revisar el log; la cadena se corta aca")
                self.btn_ba.setEnabled(True)
            self.btn_capturar.setEnabled(True)
            self._set_campos(True)


# ============================================================================
# Ventana principal
# ============================================================================

class Panel(QMainWindow):
    def __init__(self, perfil_inicial=None):
        super().__init__()
        self.setWindowTitle("Panel de Navegacion Quirurgica — brief-01 (iter 1)")
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
        c1.addWidget(self.btn_ids)
        c1.addWidget(self.btn_camara)
        c1.addStretch(1)
        g2 = QGroupBox("2 · Calibrar")
        c2 = QVBoxLayout(g2)
        self.btn_captura = QPushButton("Capturar dataset BA…")
        self.btn_ba = QPushButton("Correr BA…")
        self.btn_divot = QPushButton("Calibrar punta (dock)…")
        self.btn_asistente = QPushButton("Asistente: dodecaedro nuevo…")
        for b in (self.btn_captura, self.btn_ba, self.btn_divot,
                  self.btn_asistente):
            c2.addWidget(b)
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
            "captura": self.btn_captura, "ba": self.btn_ba,
            "divot": self.btn_divot, "asistente": self.btn_asistente,
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
        self.btn_captura.clicked.connect(self._accion_captura)
        self.btn_ba.clicked.connect(self._accion_ba)
        self.btn_divot.clicked.connect(self._accion_divot)
        self.btn_asistente.clicked.connect(self._accion_asistente)
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
        self.refrescar()

    def log_msg(self, texto):
        self.log.appendPlainText(f"[{time.strftime('%H:%M:%S')}] [panel] {texto}")

    def _linea_hijo(self, texto):
        self.log.appendPlainText(texto)

    # ------------------------------------------------------------------
    def refrescar(self):
        ruta = self.perfil_activo()
        if not ruta:
            return
        self.chequeos, self._cfg = estado.evaluar_todo(ruta)
        # resultado de la sonda de camara (si es de este perfil) pisa el GRIS
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

        def no_rojo(k):
            return k in self._chk and self._chk[k].estado != estado.ROJO

        libre = not corriendo
        self.btn_ids.setEnabled(libre and verde("entorno") and verde("config"))
        self.btn_camara.setEnabled(libre and verde("config"))
        self.btn_captura.setEnabled(libre and verde("entorno")
                                    and verde("config") and no_rojo("geometria"))
        self.btn_ba.setEnabled(libre and verde("entorno"))
        self.btn_divot.setEnabled(libre and verde("entorno")
                                  and verde("config") and verde("geometria"))
        self.btn_asistente.setEnabled(libre and verde("entorno")
                                      and verde("config"))
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
        if receta.clave != "ba":  # el BA ya valida overwrite en su dialogo
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

    def _accion_captura(self):
        receta = DialogoCaptura.pedir(self, self.perfil_activo(), self._cfg)
        if receta:
            self.lanzar_receta(receta)

    def _accion_ba(self):
        receta = DialogoBA.pedir(self)
        if receta:
            self.lanzar_receta(receta)

    def _accion_divot(self):
        receta = DialogoDivot.pedir(self, self.perfil_activo())
        if receta:
            self.lanzar_receta(receta)

    def _accion_asistente(self):
        if self.asistente is None:
            self.asistente = AsistenteDodecaedro(self)
        self.asistente.show()
        self.asistente.raise_()

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
    ap = argparse.ArgumentParser(description="Panel de control (brief-01).")
    ap.add_argument("--perfil", default=None,
                    help="Perfil inicial (ruta o nombre del yaml).")
    ap.add_argument("--selftest", action="store_true",
                    help="Abre, refresca, imprime estados y botones, cierra solo.")
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
            print("[panel-selftest] cerrando OK")
            panel.close()
            app.quit()
        QTimer.singleShot(1200, dump_y_cerrar)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
