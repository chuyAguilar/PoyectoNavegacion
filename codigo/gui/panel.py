# -*- coding: utf-8 -*-
"""
panel.py — Panel de control GUI (brief-01 + refinamiento brief-02). PySide6.

Ventana unica: selector de perfil + semaforos de prerrequisitos + botones que
lanzan los scripts EXISTENTES como subprocesos (la GUI solo orquesta, no
reescribe logica) + panel de log con la salida en vivo.

Grupos de acciones:
  1 Verificar/Preparar: identificar IDs (y con ello la camara) y calibrar
    camara: una ventana de tres pasos sin campos (enfocar, tablero, escala;
    meta 002, fase 5, P21), con lo fijo en calibration_window.py.
  2 Operar: tracker (gating duro + recordatorio de Slicer), detener.
Meta 003, fase 7b (P10, P12, P13): «Detener tracker» en 2, que detiene las dos
recetas del tracker limpio: sin ventana por la entrada estandar, con ventana con
'q' a la ventana.
Meta 003, fase 8a (P14 = b, P16 = b; ADR-030 propuesto): un boton por modo. En 1,
«Verificar IDs y colocar la cámara» (identify_ids con deteccion, cruz y fps de la
camara; se va «Vista previa»). En 2, «Arrancar tracker» lanza el tracker SIN
ventana (--no-window --stop-stdin) y «Arrancar tracker con ventana» el de siempre.
Los perfiles y el comando a mano no cambian.
Meta 004, fase 2b (P10): «Verificar IDs y colocar la cámara» pone el semaforo
«Camara» (verde si cierra con codigo 0, rojo con el motivo si no) y se va el
boton de la sonda corta (`gui/camera_probe.py` queda para la CLI).
Meta 003, fase 3 (ADR-027): se van el asistente "dodecaedro nuevo" y
"Calibrar punta (dock)" (archivados en codigo/historico/iter4/dodecahedron/);
los perfiles se listan de codigo/profiles/.

Uso (desde codigo\\, con el venv):
    python -m gui.panel
    python -m gui.panel --selftest      # abre, refresca, imprime y cierra solo
    python -m gui.panel --perfil profiles/tracker_config_gs1.yaml
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
    QApplication, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox,
    QVBoxLayout, QWidget,
)

from gui import calibration_window as calibracion
from gui import status as estado
from gui import profile_editor as perfil_editor
from gui import processes as procesos
from gui import recipes as recetas

COLORES = {
    estado.VERDE: "#1e8e3e",
    estado.AMARILLO: "#e8a100",
    estado.ROJO: "#c5221f",
    estado.GRIS: "#8a8a8a",
}

# Las recetas que «Detener tracker» detiene (meta 003, fase 7b; P12).
CLAVES_TRACKER = ("tracker", "tracker_sin_ventana")


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
    ruta = estado.resolver_ruta(declarada)
    if ruta is None:
        return None, f"calibration_file no existe: {declarada}"
    return ruta, None


def apuntar_perfil(padre, panel, ruta_yml, perfil, encabezado=""):
    """Apunta camera.calibration_file del perfil al .yml: valida, muestra el
    antes/despues, pide confirmacion y aplica con backup (perfil_editor,
    ADR-018: la unica mutacion de config del panel). True si se aplico.
    Desde la fase 5 (P21) no tiene boton propio: la usa la oferta que sigue a
    una calibracion que cumple el criterio (Panel._ofrecer_apuntar)."""
    err = perfil_editor.validar_yml_intrinsecos(ruta_yml)
    if err:
        QMessageBox.warning(padre, "Calibración",
                            f"El archivo de la calibración no vale: {err}")
        return False
    valor = perfil_editor.valor_para_perfil(ruta_yml, estado.DIR_DATA)
    try:
        actual, nueva = perfil_editor.previsualizar_cambio(perfil, valor)
    except (ValueError, OSError) as e:
        QMessageBox.critical(padre, "Calibración", str(e))
        return False
    r = QMessageBox.question(
        padre, "Usar la calibración nueva (ADR-018)",
        (f"{encabezado}\n\n" if encabezado else "")
        + f"Se cambiará una sola línea de {Path(perfil).name} (antes se "
        f"guarda una copia del archivo):\n\n"
        f"  ANTES:    {actual.strip()}\n"
        f"  DESPUÉS:  {nueva.strip()}\n\n¿Cambiarla?")
    if r != QMessageBox.StandardButton.Yes:
        panel.log_msg(f"perfil NO editado (cancelado): {Path(perfil).name}")
        return False
    try:
        backup, _a, _n = perfil_editor.aplicar_cambio(perfil, valor)
    except (ValueError, OSError) as e:
        QMessageBox.critical(padre, "Calibración", f"No se cambió: {e}")
        return False
    panel.log_msg(f"perfil editado (ADR-018): {Path(perfil).name} -> "
                  f"calibration_file: {valor}")
    panel.log_msg(f"  backup: {backup.name}")
    panel.refrescar()
    return True


class DialogoMedirTablero(QDialog):
    """«Volver a medir el tablero…» (P21): las medidas del calibrador y los
    cuadros que abarca cada una; muestra cuanto mide cada cuadro y, al
    guardar, reescribe el archivo del tablero (calibracion.escribir_tablero)."""

    def __init__(self, parent, ruta_tablero):
        super().__init__(parent)
        self.setWindowTitle("Volver a medir el tablero")
        self.ruta_tablero = ruta_tablero
        self.tablero = None
        try:
            actual = calibracion.leer_tablero(ruta_tablero)
        except (OSError, ValueError):
            actual = None
        caja = QVBoxLayout(self)
        # Texto elegido por el autor (2026-10-23, P21).
        guia = QLabel(
            "Solo hace falta si imprimes un tablero nuevo.\n"
            "El programa necesita saber cuánto mide cada cuadro de verdad "
            "(la impresora nunca es exacta).\n\n"
            "1. Abre el calibrador sobre una columna del tablero.\n"
            "2. Una punta en el borde de ARRIBA de un cuadro negro.\n"
            "3. La otra punta en el borde de ARRIBA de otro cuadro negro, más "
            "abajo. Cuenta cuántos cuadros avanzaste.\n"
            "4. Anota lo que marca. Repítelo "
            f"{calibracion.MEDIDAS_TABLERO} veces en otras columnas.\n\n"
            "Ejemplo: 6 cuadros → 149.1 mm")
        guia.setTextFormat(Qt.TextFormat.PlainText)
        guia.setWordWrap(True)
        caja.addWidget(guia)
        form = QFormLayout()
        self.spin_cuadros = QSpinBox()
        self.spin_cuadros.setRange(1, calibracion.MAX_CASILLAS_POR_MEDIDA)
        self.spin_cuadros.setValue(actual.casillas_por_medida if actual else 6)
        form.addRow("Cuadros que avanzaste:", self.spin_cuadros)
        self.edit_medidas = QLineEdit(
            ", ".join(recetas._num(m) for m in actual.medidas_mm) if actual else "")
        self.edit_medidas.setPlaceholderText("149.1, 149.1, 149.1, 149.1, 149.4")
        form.addRow(f"Lo que marcó ({calibracion.MEDIDAS_TABLERO} veces):", self.edit_medidas)
        caja.addLayout(form)
        self.lbl_lado = QLabel()
        self.lbl_lado.setStyleSheet("font-weight: bold;")
        caja.addWidget(self.lbl_lado)
        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Save
                                   | QDialogButtonBox.StandardButton.Cancel)
        botones.button(QDialogButtonBox.StandardButton.Save).setText("Guardar")
        botones.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        caja.addWidget(botones)
        self.edit_medidas.textChanged.connect(self._actualizar)
        self.spin_cuadros.valueChanged.connect(self._actualizar)
        self._actualizar()

    def _actualizar(self, *_):
        n = calibracion.MEDIDAS_TABLERO
        try:
            medidas = recetas.parsear_medidas(self.edit_medidas.text())
        except ValueError:
            self.lbl_lado.setText("Escribe solo números, con punto decimal y "
                                  "separados por comas.")
            return
        if len(medidas) < n:
            self.lbl_lado.setText(f"Llevas {len(medidas)} de {n} medidas.")
            return
        lado = recetas.lado_de_medidas(medidas, self.spin_cuadros.value())
        self.lbl_lado.setText(f"Cada cuadro mide: {lado:.2f} mm")

    def accept(self):
        try:
            self.tablero = calibracion.escribir_tablero(
                self.ruta_tablero, self.edit_medidas.text(), self.spin_cuadros.value())
        except (ValueError, OSError) as e:
            QMessageBox.warning(self, "Medidas del tablero", str(e))
            return
        super().accept()


class VentanaCalibrarCamara(QDialog):
    """Calibrar la camara del perfil activo en tres pasos sin campos (meta
    002, fase 5; P19, P21): 1 enfocar el lente, 2 calibrar con el tablero
    guardado, 3 comprobar la escala con la regla. Lo fijo no se ve (vive en
    calibracion.py) y los textos son llanos. Cada paso lanza su receta y
    cierra la ventana para ver el registro; al reabrirla, «Última» se
    actualiza. Tras calibrar con el criterio cumplido, el panel ofrece
    apuntar el perfil (Panel._ofrecer_apuntar, ADR-018)."""

    def __init__(self, panel, ruta_cfg=None, ruta_tablero=None):
        super().__init__(panel)
        self.panel = panel
        self.ruta_cfg = str(ruta_cfg or panel.perfil_activo())
        self.ruta_tablero = ruta_tablero or calibracion.RUTA_TABLERO
        try:
            self.cfg = estado.cargar_perfil(self.ruta_cfg) or {}
        except Exception:
            self.cfg = {}
        self.slug = recetas.slug_de_perfil(self.ruta_cfg)
        try:
            modo = calibracion.modo_del_perfil(self.cfg)
        except ValueError:
            modo = "sin modo"
        self.setWindowTitle(f"Calibrar cámara — {self.slug}")
        self.resize(560, 520)
        caja = QVBoxLayout(self)
        titulo = QLabel(f"Calibrar cámara — {self.slug} ({modo}, perfil "
                        f"{Path(self.ruta_cfg).name})")
        titulo.setStyleSheet("font-weight: bold; font-size: 11pt;")
        titulo.setWordWrap(True)
        caja.addWidget(titulo)

        fila = QHBoxLayout()
        self.lbl_tablero = QLabel()
        self.lbl_tablero.setWordWrap(True)
        fila.addWidget(self.lbl_tablero, stretch=1)
        self.btn_medir = QPushButton("Volver a medir el tablero…")
        self.btn_medir.clicked.connect(self._medir_tablero)
        fila.addWidget(self.btn_medir)
        caja.addLayout(fila)

        self.btn_enfocar, self.lbl_ult_enfocar = self._paso(
            caja, "1 · Enfocar lente",
            "Gira el lente hasta que el número de nitidez sea el más alto. "
            "q para terminar.", self.componer_enfocar)
        self.btn_calibrar, self.lbl_ult_calibrar = self._paso(
            caja, "2 · Calibrar con tablero",
            "Mueve el tablero por toda la imagen, inclinándolo; pulsa ESPACIO "
            "para tomar cada foto (unas 25). u borra la última. q termina y "
            "calcula.", self.componer_calibrar)
        form = QFormLayout()
        self.spin_recorrido = QSpinBox()
        self.spin_recorrido.setRange(10, 500)
        self.spin_recorrido.setValue(calibracion.RECORRIDO_MM)
        self.spin_recorrido.setSuffix(" mm")
        self.spin_idas = QSpinBox()
        self.spin_idas.setRange(1, 10)
        self.spin_idas.setValue(calibracion.IDAS_Y_VUELTAS)
        self.btn_escala, self.lbl_ult_escala = self._paso(
            caja, "3 · Comprobar escala con regla",
            "Pon una esquina del tablero en la primera marca, pulsa ESPACIO; "
            "llévalo a la segunda sin girarlo, ESPACIO; y así.",
            self.componer_escala, extra=form)
        form.addRow("Distancia entre tus dos marcas en la regla:", self.spin_recorrido)
        form.addRow("Veces que vas y vuelves:", self.spin_idas)

        caja.addStretch(1)
        cierre = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        cierre.button(QDialogButtonBox.StandardButton.Close).setText("Cerrar")
        cierre.rejected.connect(self.reject)
        caja.addWidget(cierre)
        self.refrescar()

    def _paso(self, caja, texto_boton, ayuda, componer, extra=None):
        grupo = QGroupBox()
        c = QVBoxLayout(grupo)
        boton = QPushButton(texto_boton)
        boton.setStyleSheet("font-weight: bold; text-align: left; padding: 4px 8px;")
        boton.clicked.connect(lambda _=False, f=componer: self._lanzar(f))
        c.addWidget(boton)
        lbl_ayuda = QLabel(ayuda)
        lbl_ayuda.setWordWrap(True)
        c.addWidget(lbl_ayuda)
        if extra is not None:
            c.addLayout(extra)
        ultima = QLabel()
        ultima.setWordWrap(True)
        ultima.setStyleSheet("color: #444;")
        c.addWidget(ultima)
        caja.addWidget(grupo)
        return boton, ultima

    # --------------------------------------------------------------
    def _salidas(self):
        try:
            return calibracion.salidas_del_perfil(self.ruta_cfg, self.cfg)
        except ValueError:
            return None

    def refrescar(self):
        """El tablero, la ultima medida de cada paso y que pasos se pueden dar."""
        try:
            self.tablero = calibracion.leer_tablero(self.ruta_tablero)
            self.lbl_tablero.setText(f"Tablero medido: cada cuadro mide "
                                     f"{self.tablero.lado_mm:.2f} mm")
            motivo_tablero = None
        except (OSError, ValueError) as e:
            self.tablero = None
            motivo_tablero = "Primero mide el tablero (botón de arriba)."
            self.lbl_tablero.setText(f"Tablero sin medir ({e}).")
        s = self._salidas()
        cam = (self.cfg.get("camera") or {})
        motivo_enfocar = (None if cam.get("usb_port_windows") and s else
                          "Este perfil no dice en qué puerto está la cámara: "
                          "enfocar no está disponible.")
        self.yml_activo, _motivo = yml_del_perfil(self.ruta_cfg, self.cfg)
        motivo_escala = motivo_tablero or (None if self.yml_activo is not None else
                                           "Primero calibra la cámara (paso 2).")
        motivo_calibrar = motivo_tablero or (None if s else
                                             "El perfil no dice el tamaño de la imagen.")
        if s:
            ult_enfocar = calibracion.ultima_nitidez(s["enfoque"])
            texto_cal, ok_cal = calibracion.ultima_calibracion(s["reporte"], s["yml"])
            texto_esc, ok_esc = calibracion.ultima_escala(s["escala"])
        else:
            ult_enfocar, texto_cal, ok_cal, texto_esc, ok_esc = "—", "—", None, "—", None
        self.lbl_ult_enfocar.setText(f"Última: {ult_enfocar}")
        self.lbl_ult_calibrar.setText(f"Última: {texto_cal}{calibracion.marca(ok_cal)}")
        self.lbl_ult_escala.setText(f"Última: {texto_esc}{calibracion.marca(ok_esc)}")
        for boton, motivo in ((self.btn_enfocar, motivo_enfocar),
                              (self.btn_calibrar, motivo_calibrar),
                              (self.btn_escala, motivo_escala)):
            boton.setEnabled(motivo is None)
            boton.setToolTip(motivo or "")
        self.spin_recorrido.setEnabled(motivo_escala is None)
        self.spin_idas.setEnabled(motivo_escala is None)

    def textos_visibles(self):
        """Lo que la persona lee en la ventana (para el selftest, P21)."""
        return [w.text() for w in self.findChildren(QLabel) + self.findChildren(QPushButton)
                if w.text()]

    # --------------------------------------------------------------
    def componer_enfocar(self):
        return calibracion.receta_enfocar_perfil(self.ruta_cfg, self.cfg)

    def componer_calibrar(self):
        if self.tablero is None:
            raise ValueError("Primero mide el tablero.")
        return calibracion.receta_calibrar_perfil(self.ruta_cfg, self.cfg, self.tablero)

    def componer_escala(self):
        if self.tablero is None:
            raise ValueError("Primero mide el tablero.")
        if self.yml_activo is None:
            raise ValueError("Primero calibra la cámara (paso 2).")
        return calibracion.receta_escala_perfil(
            self.ruta_cfg, self.yml_activo, self.tablero,
            self.spin_recorrido.value(), self.spin_idas.value())

    def _lanzar(self, componer):
        try:
            receta = componer()
        except (ValueError, FileNotFoundError, OSError) as e:
            QMessageBox.warning(self, "Calibrar cámara", str(e))
            return
        self.accept()   # cerrar para ver el registro en el panel
        self.panel.lanzar_receta(receta)

    def _medir_tablero(self):
        d = DialogoMedirTablero(self, self.ruta_tablero)
        if d.exec() == QDialog.DialogCode.Accepted and d.tablero:
            self.panel.log_msg(f"tablero medido de nuevo: {d.tablero.medidas_mm} sobre "
                               f"{d.tablero.casillas_por_medida} cuadros -> "
                               f"{d.tablero.lado_mm:.2f} mm ({Path(self.ruta_tablero).name})")
            self.refrescar()


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
        self.btn_ids = QPushButton("Verificar IDs y colocar la cámara")
        self.btn_calcam = QPushButton("Calibrar cámara (enfocar, tablero, escala)…")
        c1.addWidget(self.btn_ids)
        c1.addWidget(self.btn_calcam)
        c1.addStretch(1)
        g3 = QGroupBox("2 · Operar")
        c3 = QVBoxLayout(g3)
        # Fase 8a (P14 = b): el principal, sin ventana; el de ventana, la opcion.
        self.btn_tracker = QPushButton("Arrancar tracker")
        self.btn_tracker_con_ventana = QPushButton("Arrancar tracker con ventana")
        self.btn_detener_tracker = QPushButton("Detener tracker")
        self.btn_detener_tracker.setEnabled(False)
        self.btn_detener = QPushButton("Detener proceso")
        self.btn_detener.setEnabled(False)
        c3.addWidget(self.btn_tracker)
        c3.addWidget(self.btn_tracker_con_ventana)
        c3.addWidget(self.btn_detener_tracker)
        c3.addWidget(self.btn_detener)
        c3.addStretch(1)
        fila_acc.addWidget(g1)
        fila_acc.addWidget(g3)
        raiz.addLayout(fila_acc)

        self.botones = {
            "ids": self.btn_ids, "calcam": self.btn_calcam,
            "tracker": self.btn_tracker, "tracker_con_ventana": self.btn_tracker_con_ventana,
            "detener_tracker": self.btn_detener_tracker, "detener": self.btn_detener,
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
        self.btn_calcam.clicked.connect(self._accion_calcam)
        self.btn_tracker.clicked.connect(self._accion_tracker)
        self.btn_tracker_con_ventana.clicked.connect(self._accion_tracker_con_ventana)
        self.btn_detener_tracker.clicked.connect(self._accion_detener_tracker)
        self.btn_detener.clicked.connect(self._accion_detener)

        # Perfil inicial: CLI > ultima seleccion > gs1 (ADR-024)
        if not perfiles:
            self.log_msg("[ROJO] No hay profiles/tracker_config*.yaml — nada que evaluar.")
            return
        objetivo = None
        if perfil_inicial:
            objetivo = Path(perfil_inicial).name
        elif self.settings.value("perfil_activo"):
            objetivo = Path(str(self.settings.value("perfil_activo"))).name
        idx = self.combo.findText(objetivo) if objetivo else -1
        if idx < 0:
            idx = self.combo.findText("tracker_config_gs1.yaml")
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
        # brief-02 M5: feed en vivo al origen de la receta, si lo pide (linea_hijo)
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
        self.btn_calcam.setEnabled(libre and verde("entorno")
                                   and verde("config"))
        ok, malos = estado.apto_para_tracker(self.chequeos)
        motivo = "" if ok else f"Bloqueado por: {', '.join(malos)} (fail-loud)"
        for boton in (self.btn_tracker, self.btn_tracker_con_ventana):
            boton.setEnabled(libre and ok)
            boton.setToolTip(motivo)
        activa = self.lanzador.receta_activa()
        self.btn_detener_tracker.setEnabled(
            corriendo and activa is not None and activa.clave in CLAVES_TRACKER)
        self.btn_detener.setEnabled(corriendo)
        self.combo.setEnabled(libre)

    # ------------------------------------------------------------------
    def lanzar_receta(self, receta, origen=None):
        """Lanza una receta con eco del comando y confirmacion de overwrite
        (fail-loud). API publica: la usa la ventana de calibracion."""
        if self.lanzador.hay_activo():
            QMessageBox.warning(self, "Panel", "Ya hay un proceso corriendo. "
                                "Usar 'Detener proceso' primero.")
            return False
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
        # Fase 2b de la meta 004 (P10): «Verificar IDs y colocar la cámara» pone el semaforo.
        chi = estado.chequeo_camara_tras_receta(receta.clave, rc, self.lanzador.buffer_actual(),
                                                time.strftime('%H:%M:%S'))
        if chi is not None:
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
        self.log_msg(f"calibracion: cumple el criterio (detector {campos.get('detector', '?')}, "
                     f"RMS de control {campos.get('rms_control_px', '?')[:6]} px); se ofrece "
                     f"apuntar el perfil a {valor}")
        try:
            error_px = f"{float(campos.get('rms_control_px')):.2f}"
        except (TypeError, ValueError):
            error_px = "?"
        encabezado = (f"La calibración salió bien: error {error_px} píxeles "
                      f"(aceptable hasta {calibracion.LIMITE_ERROR_PX:.2f}).\n"
                      f"¿Quieres que esta cámara use la calibración nueva "
                      f"({Path(ruta_yml).name})?")
        apuntar_perfil(self, self, ruta_yml, perfil, encabezado)

    # ------------------------------------------------------------------
    def _accion_ids(self):
        self.lanzar_receta(recetas.receta_identificar_ids(self.perfil_activo()))

    def _accion_calcam(self):
        VentanaCalibrarCamara(self).exec()

    def _confirmar_slicer(self):
        """La pregunta de Slicer de los dos botones del tracker. True si se lanza."""
        cfg = self._cfg or {}
        puerto = ((cfg.get("igtlink") or {}).get("transforms_port", 18944))
        r = QMessageBox.question(
            self, "Tracker — Slicer primero",
            f"El tracker espera a Slicer hasta 30 s y, si no llega, aborta con "
            f"código 3 (CONTEXT §4.5).\n\n"
            f"¿Slicer ya esta conectado como cliente OpenIGTLink "
            f"(localhost:{puerto}, conector Active)?")
        if r != QMessageBox.StandardButton.Yes:
            self.log_msg("tracker: cancelado — conectar Slicer primero "
                         "(codigo/slicer/README.md: receive_marker0.py)")
            return False
        return True

    def _accion_tracker(self):
        """«Arrancar tracker»: sin ventana desde la fase 8a (P14 = b)."""
        if self._confirmar_slicer():
            self.lanzar_receta(recetas.receta_tracker_sin_ventana(self.perfil_activo()))

    def _accion_tracker_con_ventana(self):
        """«Arrancar tracker con ventana»: la receta de siempre (`receta_tracker`)."""
        if self._confirmar_slicer():
            self.lanzar_receta(recetas.receta_tracker(self.perfil_activo()))

    def _accion_detener_tracker(self):
        self.log_msg("detener tracker: sin ventana, 'q' por la entrada estandar; con "
                     "ventana, 'q' a la ventana (cierre duro solo si no responde)...")
        self.lanzador.detener_async()

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
                    help="Abre, refresca, imprime estados y botones, "
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
            # Fase 8a: lo que dice cada boton (el principal del tracker, sin ventana).
            print("[panel-selftest] botones_textos="
                  + " | ".join(f"{clave}:{boton.text()}" for clave, boton in panel.botones.items()))
            # P19/P21 (fase 5): la ventana de tres pasos compone sus recetas con
            # el tablero guardado, sin lanzarlas (ninguna camara se abre aqui).
            gs1 = estado.DIR_PERFILES / "tracker_config_gs1.yaml"
            # Fase 8a: los argv de lo que lanza cada boton (ids, el tracker principal sin
            # ventana y el de ventana).
            for nombre, componer in (("ids", recetas.receta_identificar_ids),
                                     ("tracker", recetas.receta_tracker_sin_ventana),
                                     ("tracker_con_ventana", recetas.receta_tracker)):
                print(f"[panel-selftest] {nombre}_argv={' '.join(componer(str(gs1)).argv[2:])}")
            v = VentanaCalibrarCamara(panel, str(gs1))
            print(f"[panel-selftest] calcam_lado={v.tablero.lado_mm:.2f}"
                  if v.tablero else "[panel-selftest] calcam_lado=SIN TABLERO")
            for nombre, componer in (("enfocar", v.componer_enfocar),
                                     ("calcam", v.componer_calibrar),
                                     ("escala", v.componer_escala)):
                try:
                    print(f"[panel-selftest] {nombre}_argv={' '.join(componer().argv[2:])}")
                except (ValueError, OSError) as e:
                    print(f"[panel-selftest] {nombre}_no_disponible={e}")
            for clave, lbl in (("enfocar", v.lbl_ult_enfocar), ("calcam", v.lbl_ult_calibrar),
                               ("escala", v.lbl_ult_escala)):
                print(f"[panel-selftest] {clave}_ultima={lbl.text()}")
            textos = v.textos_visibles() + [panel.btn_calcam.text()]
            d = DialogoMedirTablero(v, v.ruta_tablero)   # no se guarda: solo se mira
            d.edit_medidas.setText("149.1, 149.1, 149.1, 149.1, 149.4")
            d.spin_cuadros.setValue(6)
            print(f"[panel-selftest] medir_lado={d.lbl_lado.text()}")
            textos += [w.text() for w in d.findChildren(QLabel) + d.findChildren(QPushButton)
                       if w.text()]
            print("[panel-selftest] calcam_textos=" + " | ".join(t.replace("\n", " ") for t in textos))
            d.deleteLater()
            v.deleteLater()
            # Fase 2b de la meta 004 (P10): el fin de «Verificar IDs y colocar la cámara», simulado
            # por el camino de siempre (_proceso_termino) con la salida que dejaria el proceso; no se
            # lanza nada. Codigo 0 -> «Camara» en verde; otro codigo -> rojo con el motivo.
            print(f"[panel-selftest] camara_antes={panel._chk['camara'].estado}")
            simuladas = (
                ("camara_tras_ids_rc0", 0, ["[IDs] camara 89.9 fps", "[IDs] q: saliendo.",
                                            "[Salida limpia]"]),
                ("camara_tras_ids_rc1", 1, ["[ERROR] [IDs] la camara no entrega frames desde hace "
                                            "5 s. Saliendo.", "[Salida limpia]"]),
            )
            buffer_real = panel.lanzador.buffer_actual
            try:
                for nombre, rc, lineas in simuladas:
                    panel.lanzador.buffer_actual = lambda lineas=lineas: list(lineas)
                    panel._proceso_termino(recetas.receta_identificar_ids(str(gs1)), rc)
                    c = panel._chk["camara"]
                    print(f"[panel-selftest] {nombre}={c.estado} :: {c.detalle}")
            finally:
                panel.lanzador.buffer_actual = buffer_real
            print("[panel-selftest] cerrando OK")
            panel.close()
            app.quit()
        QTimer.singleShot(1200, dump_y_cerrar)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
