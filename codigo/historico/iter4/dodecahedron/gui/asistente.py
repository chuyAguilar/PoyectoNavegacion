# -*- coding: utf-8 -*-
"""
asistente.py — Asistente "dodecaedro nuevo" (brief-01 §2.4, refinado brief-02).

Encadena los scripts existentes en el orden correcto: [semilla teorica] ->
capturar dataset -> chequeo de cobertura (M5) -> bundle adjustment con monitor
de convergencia en vivo (M5) -> geometria *_calibrado.txt. NO edita el YAML
del perfil (decision §E.1 de brief-01: muestra la instruccion final).

brief-02:
  M1 — la semilla default ya NO es la teorica vieja (footgun CONTEXT §4.14):
       se deriva la "gemela" de la geometria del perfil (v2_calibrado -> v2),
       con fallback a la teorica v2, o seleccion explicita obligatoria; los
       IDs de la semilla elegida quedan SIEMPRE visibles.
  M5 — gate de cobertura post-captura, monitor de estancamiento en vivo con
       auto-corte configurable, y defaults de BA mas sensatos (250/1000)
       manteniendo alcanzable el comando completo de referencia
       (--max-frames 500 --max-nfev 3000, ADR-008/009).
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QRadioButton, QSpinBox,
    QVBoxLayout, QWidget,
)

import ba_monitor
import estado
import recetas

RE_NOMBRE_VALIDO = re.compile(r"^[A-Za-z0-9_\-]+$")

# Defaults del BA en el asistente (M5, aprobados 2026-08-13). El comando
# "completo" de referencia (ADR-008/009) sigue alcanzable editando los campos:
#   --max-frames 500 --max-nfev 3000
BA_DEFAULT_FRAMES = 250
BA_DEFAULT_NFEV = 1000

AYUDA_GIRO = (
    "Nota (ADR-009): si el BA no converge o las correspondencias se ven mal, "
    "puede que la orientacion fisica de las caras difiera de la teorica (roll "
    "por-marcador). El recurso manual es iter4\\corregir_giro_esquinas.py "
    "(fuera del alcance de esta iteracion del panel).")

FALLBACK_SEMILLA = "reference_dodecaedro_v2.txt"


def _geometrias(solo_teoricas=False):
    todas = sorted(estado.DIR_DATA.glob("reference_*.txt"))
    if solo_teoricas:
        return [p for p in todas if "calibrado" not in p.name.lower()]
    teo = [p for p in todas if "calibrado" not in p.name.lower()]
    cal = [p for p in todas if "calibrado" in p.name.lower()]
    return teo + cal


def derivar_semilla_default(cfg, ruta_cfg, teoricas):
    """M1: semilla default sensata. Orden: (1) la teorica 'gemela' de la
    geometria del perfil (X_calibrado.txt -> X.txt); (2) la teorica v2
    compartida; (3) None -> seleccion explicita obligatoria."""
    nombres = {p.name: p for p in teoricas}
    geom_perfil = estado.geometria_del_perfil(cfg, ruta_cfg)
    if geom_perfil is not None:
        gemela = Path(geom_perfil).name.replace("_calibrado", "")
        if gemela in nombres:
            return nombres[gemela]
    if FALLBACK_SEMILLA in nombres:
        return nombres[FALLBACK_SEMILLA]
    return None


class AsistenteDodecaedro(QDialog):
    """Flujo "dar de alta un dodecaedro nuevo" (captura -> cobertura -> BA)."""

    def __init__(self, panel):
        super().__init__(panel)
        self.setWindowTitle("Asistente: dodecaedro nuevo (captura → BA)")
        self.panel = panel
        self.resize(620, 620)
        caja = QVBoxLayout(self)

        form = QFormLayout()

        # --- M2: modo de semilla — existente vs GENERAR (IDs nuevos) ---
        self.radio_existente = QRadioButton("Usar teorica existente")
        self.radio_generar = QRadioButton("Generar teorica nueva (IDs nuevos)")
        self.radio_existente.setChecked(True)
        fila_modo = QHBoxLayout()
        fila_modo.addWidget(self.radio_existente)
        fila_modo.addWidget(self.radio_generar)
        fila_modo.addStretch(1)
        cont_modo = QWidget()
        cont_modo.setLayout(fila_modo)
        form.addRow("Semilla:", cont_modo)

        self.combo_teo = QComboBox()
        teoricas = _geometrias(solo_teoricas=True)
        default = derivar_semilla_default(panel._cfg, panel.perfil_activo(),
                                          teoricas)
        if default is None:
            # M1: sin default derivable -> seleccion explicita obligatoria
            self.combo_teo.addItem("— elegir semilla —", None)
        for p in teoricas:
            self.combo_teo.addItem(p.name, str(p))
        if default is not None:
            i = self.combo_teo.findText(default.name)
            if i >= 0:
                self.combo_teo.setCurrentIndex(i)
        self.combo_teo.currentIndexChanged.connect(self._teorica_cambiada)
        form.addRow("Teorica semilla:", self.combo_teo)

        # Campos del layout para GENERAR (M2). Defaults: continuan tras el v2
        # compartido (IDs 3-13) -> 14 / 15-19 / 20-24.
        self.caja_generar = QWidget()
        form_gen = QFormLayout(self.caja_generar)
        form_gen.setContentsMargins(12, 0, 0, 0)
        self.spin_id_top = QSpinBox()
        self.spin_id_top.setRange(0, 999)
        self.spin_id_top.setValue(14)
        form_gen.addRow("Cara superior (ID):", self.spin_id_top)
        self.edit_ids_sup = QLineEdit("15,16,17,18,19")
        form_gen.addRow("Anillo superior (5 IDs):", self.edit_ids_sup)
        self.edit_ids_inf = QLineEdit("20,21,22,23,24")
        form_gen.addRow("Anillo inferior (5 IDs):", self.edit_ids_inf)
        self.spin_edge = QDoubleSpinBox()
        self.spin_edge.setRange(5.0, 50.0)
        self.spin_edge.setDecimals(1)
        self.spin_edge.setValue(17.5)
        self.spin_edge.setSuffix(" mm")
        form_gen.addRow("Arista del dodecaedro:", self.spin_edge)
        lbl_gen = QLabel("El lado del marker se toma del campo de abajo "
                         "(compartido con el BA: mismo ensamble). La teorica "
                         "se genera y valida con "
                         "generar_reference_dodecaedro.py.")
        lbl_gen.setWordWrap(True)
        lbl_gen.setStyleSheet("color: #555; font-size: 8pt;")
        form_gen.addRow("", lbl_gen)
        form.addRow(self.caja_generar)
        self.lbl_ids_semilla = QLabel()
        self.lbl_ids_semilla.setStyleSheet("color: #555;")
        form.addRow("", self.lbl_ids_semilla)
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

        # M5: parametros del BA editables (defaults sensatos para --no-sparse)
        self.spin_frames = QSpinBox()
        self.spin_frames.setRange(10, 5000)
        self.spin_frames.setValue(BA_DEFAULT_FRAMES)
        form.addRow("BA max frames:", self.spin_frames)
        self.spin_nfev = QSpinBox()
        self.spin_nfev.setRange(10, 10000)
        self.spin_nfev.setValue(BA_DEFAULT_NFEV)
        form.addRow("BA max nfev:", self.spin_nfev)
        lbl_ref = QLabel("Comando completo de referencia (ADR-008/009): "
                         "max frames 500, max nfev 3000 — editar arriba para "
                         "usarlo (tarda mucho mas).")
        lbl_ref.setWordWrap(True)
        lbl_ref.setStyleSheet("color: #555; font-size: 8pt;")
        form.addRow("", lbl_ref)
        self.chk_autocorte = QCheckBox(
            f"Cortar el BA automaticamente si se estanca "
            f"({ba_monitor.ESTANCADAS_CORTE} iter sin avanzar)")
        self.chk_autocorte.setChecked(True)
        form.addRow("", self.chk_autocorte)
        caja.addLayout(form)

        self.lbl_generar = QLabel("0) Generar teorica: pendiente")
        self.lbl_captura = QLabel("1) Capturar dataset: pendiente")
        self.lbl_cobertura = QLabel("")
        self.lbl_cobertura.setWordWrap(True)
        self.lbl_ba = QLabel("2) Bundle adjustment: pendiente")
        self.lbl_monitor = QLabel("")
        self.lbl_resumen = QLabel("")
        self.lbl_resumen.setWordWrap(True)
        self.lbl_resumen.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        for w in (self.lbl_generar, self.lbl_captura, self.lbl_cobertura,
                  self.lbl_ba, self.lbl_monitor, self.lbl_resumen):
            caja.addWidget(w)

        nota = QLabel(AYUDA_GIRO)
        nota.setWordWrap(True)
        nota.setStyleSheet("color: #777; font-size: 8pt;")
        caja.addWidget(nota)

        fila_botones = QHBoxLayout()
        self.btn_generar = QPushButton("0) Generar teorica")
        self.btn_capturar = QPushButton("1) Capturar dataset")
        self.btn_ba = QPushButton("2) Correr BA")
        self.btn_ba.setEnabled(False)
        self.btn_copiar = QPushButton("Copiar ruta de la geometria")
        self.btn_copiar.setEnabled(False)
        fila_botones.addWidget(self.btn_generar)
        fila_botones.addWidget(self.btn_capturar)
        fila_botones.addWidget(self.btn_ba)
        fila_botones.addWidget(self.btn_copiar)
        caja.addLayout(fila_botones)

        self.btn_generar.clicked.connect(self._generar)
        self.btn_capturar.clicked.connect(self._capturar)
        self.btn_ba.clicked.connect(self._correr_ba)
        self.btn_copiar.clicked.connect(self._copiar)
        self.radio_existente.toggled.connect(self._modo_cambiado)

        # Estado M5
        self.veredicto_cobertura = None
        self.monitor = None
        self._ba_corriendo = False
        self._corte_pedido = False
        self._t0_ba = None
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick)

        self._teorica_cambiada()
        self._modo_cambiado()

    # ------------------------------------------------------------------
    # M2: modo de semilla (existente | generar nueva)
    # ------------------------------------------------------------------
    def _modo_generar(self):
        return self.radio_generar.isChecked()

    def _modo_cambiado(self, *_):
        generar = self._modo_generar()
        self.caja_generar.setVisible(generar)
        self.btn_generar.setVisible(generar)
        self.lbl_generar.setVisible(generar)
        # En modo generar, la semilla la produce el paso 0 (el combo queda
        # de solo-lectura y se auto-selecciona la teorica generada).
        self.combo_teo.setEnabled(not generar)
        if generar:
            self.lbl_generar.setText("0) Generar teorica: pendiente")
        self.adjustSize()

    @staticmethod
    def _parse_ids(texto):
        """'15,16,17,18,19' -> [15,16,17,18,19]. ValueError si no parsea."""
        try:
            ids = [int(x.strip()) for x in texto.split(",") if x.strip()]
        except ValueError:
            raise ValueError(f"lista de IDs invalida: '{texto}' (usar enteros "
                             f"separados por comas)")
        return ids

    def _generar(self):
        if not RE_NOMBRE_VALIDO.match(self._nombre()):
            QMessageBox.warning(self, "Asistente", "Nombre base invalido: usar "
                                "solo letras, numeros, '_' y '-'.")
            return
        try:
            ids_sup = self._parse_ids(self.edit_ids_sup.text())
            ids_inf = self._parse_ids(self.edit_ids_inf.text())
            receta = recetas.receta_generar_teorica(
                output=self._teorica_generada(),
                id_top=self.spin_id_top.value(),
                ids_superior=ids_sup,
                ids_inferior=ids_inf,
                edge_mm=self.spin_edge.value(),
                marker_mm=self.spin_mm.value(),
            )
        except (ValueError, FileNotFoundError) as e:
            QMessageBox.warning(self, "Asistente", str(e))
            return
        self.lbl_generar.setText("0) Generar teorica: CORRIENDO (validacion "
                                 "geometrica incluida)")
        self.btn_generar.setEnabled(False)
        self._set_campos(False)
        if not self.panel.lanzar_receta(receta, origen=self):
            self.lbl_generar.setText("0) Generar teorica: no lanzado "
                                     "(cancelado o proceso ocupado)")
            self.btn_generar.setEnabled(True)
            self._set_campos(True)

    def _teorica_generada(self):
        """Ruta (relativa a codigo\\) de la teorica que genera el paso 0.
        Convencion v2: reference_X.txt (teorica) -> reference_X_calibrado.txt."""
        return f"iter4/data/{self._nombre()}.txt"

    # ------------------------------------------------------------------
    def _teorica_cambiada(self, *_):
        teo = self.combo_teo.currentData()
        if not teo:
            self.lbl_ids_semilla.setText(
                "⚠ elegir una semilla (sin default derivable para este perfil)")
            return
        try:
            ids = estado.parsear_geometria(teo)
        except OSError:
            ids = []
        if ids:
            self.lbl_ids_semilla.setText(
                f"Semilla: {len(ids)} markers, IDs {min(ids)}–{max(ids)}")
            self.spin_ancla.setValue(min(ids))
        else:
            self.lbl_ids_semilla.setText("⚠ semilla ilegible o vacia")

    def _nombre(self):
        return self.edit_nombre.text().strip()

    def _dataset(self):
        slug = self._nombre().replace("reference_", "")
        return f"iter4/data/captura_ba_{slug}.npz"

    def _salida(self):
        return f"iter4/data/{self._nombre()}_calibrado.txt"

    def _validar_campos(self):
        if not self.combo_teo.currentData():
            QMessageBox.warning(self, "Asistente", "Elegir la teorica semilla "
                                "(sin default derivable para este perfil).")
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
        for w in (self.edit_nombre, self.spin_ancla, self.spin_mm,
                  self.spin_dur, self.spin_frames, self.spin_nfev,
                  self.radio_existente, self.radio_generar,
                  self.spin_id_top, self.edit_ids_sup, self.edit_ids_inf,
                  self.spin_edge):
            w.setEnabled(habilitar)
        # El combo respeta el modo: en generar queda de solo-lectura.
        self.combo_teo.setEnabled(habilitar and not self._modo_generar())

    # ------------------------------------------------------------------
    def _capturar(self):
        # M2: en modo generar, la semilla DEBE ser la teorica generada con el
        # nombre actual (evita capturar con la semilla vieja del combo, o con
        # una teorica generada para otro nombre).
        if self._modo_generar():
            esperada = Path(self._teorica_generada()).name
            if self.combo_teo.currentText() != esperada:
                QMessageBox.warning(
                    self, "Asistente",
                    f"En modo 'generar', primero corre el paso 0: la semilla "
                    f"seleccionada ({self.combo_teo.currentText()}) no es la "
                    f"teorica generada esperada ({esperada}).")
                return
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
        self.lbl_cobertura.setText("")
        self.veredicto_cobertura = None
        self.btn_capturar.setEnabled(False)
        self.btn_ba.setEnabled(False)
        self._set_campos(False)
        if not self.panel.lanzar_receta(receta, origen=self):
            self.lbl_captura.setText("1) Capturar dataset: no lanzado "
                                     "(cancelado o proceso ocupado)")
            self.btn_capturar.setEnabled(True)
            self._set_campos(True)

    def _correr_ba(self):
        # M5: gate de cobertura — ROJO exige confirmacion explicita
        if self.veredicto_cobertura == "ROJO":
            r = QMessageBox.question(
                self, "Cobertura floja",
                "La cobertura del dataset es FLOJA: el BA probablemente no "
                "converja (ver detalle en el asistente).\n\n"
                "Lo recomendado es RECAPTURAR mas largo y variado.\n"
                "¿Correr el BA igual?")
            if r != QMessageBox.StandardButton.Yes:
                return
        try:
            receta = recetas.receta_ba(
                input_npz=self._dataset(),
                teorico=self.combo_teo.currentData(),
                output=self._salida(),
                ancla=self.spin_ancla.value(),
                marker_mm=self.spin_mm.value(),
                max_frames=self.spin_frames.value(),
                max_nfev=self.spin_nfev.value(),
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
                    max_frames=self.spin_frames.value(),
                    max_nfev=self.spin_nfev.value(),
                    sobrescribir=True,
                )
            else:
                QMessageBox.warning(self, "Asistente", str(e))
                return
        self.lbl_ba.setText("2) Bundle adjustment: CORRIENDO (el Jacobiano "
                            "denso tarda MINUTOS entre iteraciones)")
        self.btn_ba.setEnabled(False)
        self.btn_capturar.setEnabled(False)
        self._set_campos(False)
        if not self.panel.lanzar_receta(receta, origen=self):
            self.lbl_ba.setText("2) Bundle adjustment: no lanzado (cancelado "
                                "o proceso ocupado)")
            self.btn_ba.setEnabled(True)
            self.btn_capturar.setEnabled(True)
            self._set_campos(True)
            return
        # M5: monitor de convergencia en vivo
        self.monitor = ba_monitor.MonitorBA()
        self._ba_corriendo = True
        self._corte_pedido = False
        self._t0_ba = time.time()
        self.lbl_monitor.setText("monitor: esperando primera iteracion...")
        self.timer.start()

    def _copiar(self):
        ruta_para_yaml = f"data/{self._nombre()}_calibrado.txt"
        QGuiApplication.clipboard().setText(ruta_para_yaml)
        self.panel.log_msg(f"asistente: copiado al portapapeles: {ruta_para_yaml}")

    # ------------------------------------------------------------------
    # M5: feed en vivo desde el panel (solo mientras corre el BA)
    # ------------------------------------------------------------------
    def linea_hijo(self, texto):
        if not self._ba_corriendo or self.monitor is None:
            return
        reg = self.monitor.feed(texto)
        if reg is not None:
            self._actualizar_monitor()
            if (self.monitor.corte_recomendado()
                    and self.chk_autocorte.isChecked()
                    and not self._corte_pedido):
                self._autocorte()

    def _autocorte(self):
        """Corta el BA estancado (M5). Separado para poder verificarlo."""
        self._corte_pedido = True
        self.panel.log_msg(
            f"asistente: BA ESTANCADO {self.monitor.estancadas} iteraciones "
            f"(umbral {ba_monitor.ESTANCADAS_CORTE}) — auto-corte solicitado. "
            f"Recapturar con mejor cobertura.")
        self.panel.lanzador.detener_async()

    def _tick(self):
        if self._ba_corriendo:
            self._actualizar_monitor()

    def _actualizar_monitor(self):
        transcurrido = int(time.time() - self._t0_ba) if self._t0_ba else 0
        mm, ss = divmod(transcurrido, 60)
        est, det = self.monitor.resumen() if self.monitor else ("sin datos", "")
        marca = " ⚠ ESTANCADO" if est == "estancado" else ""
        self.lbl_monitor.setText(f"monitor BA [{mm:02d}:{ss:02d}] {est}{marca} — {det}")

    # ------------------------------------------------------------------
    def proceso_termino(self, receta, rc, buffer):
        """Llamado por el panel al terminar un proceso lanzado por este
        asistente. La cadena se corta VISIBLEMENTE si un paso falla."""
        if receta.clave == "generar":
            teorica_abs = estado.RAIZ_CODIGO / self._teorica_generada()
            if rc == 0 and teorica_abs.exists():
                nombre = teorica_abs.name
                i = self.combo_teo.findText(nombre)
                if i < 0:
                    self.combo_teo.addItem(nombre, str(teorica_abs))
                    i = self.combo_teo.findText(nombre)
                self.combo_teo.setCurrentIndex(i)   # dispara _teorica_cambiada
                # Ancla EXACTA = ID de la cara superior ingresado (la
                # heuristica min(ids) del combo puede no coincidir si el
                # layout no usa el menor ID como TOP).
                self.spin_ancla.setValue(self.spin_id_top.value())
                self.lbl_generar.setText(
                    f"0) Generar teorica: OK → {self._teorica_generada()} "
                    f"(validacion geometrica PASS)")
            else:
                self.lbl_generar.setText(
                    f"0) Generar teorica: FALLO (exit {rc}) — revisar el log "
                    f"(la validacion geometrica del script dice por que); la "
                    f"cadena se corta aca")
            self.btn_generar.setEnabled(True)
            self._set_campos(True)
        elif receta.clave == "captura":
            if rc == 0:
                utiles = ""
                for ln in reversed(buffer):
                    m = re.search(r"Frames utiles:\s*(\d+)", ln)
                    if m:
                        utiles = f" ({m.group(1)} frames utiles)"
                        break
                self.lbl_captura.setText(f"1) Capturar dataset: OK{utiles} "
                                         f"→ {self._dataset()}")
                self._evaluar_cobertura()
                self.btn_ba.setEnabled(True)
            else:
                self.lbl_captura.setText(
                    f"1) Capturar dataset: FALLO (exit {rc}) — revisar el log; "
                    f"la cadena se corta aca")
            self.btn_capturar.setEnabled(True)
            self._set_campos(True)
        elif receta.clave == "ba":
            self._ba_corriendo = False
            self.timer.stop()
            if self._corte_pedido:
                self.lbl_ba.setText(
                    "2) Bundle adjustment: CORTADO por estancamiento "
                    "(auto-corte M5) — recapturar con mejor cobertura y "
                    "reintentar")
                self.btn_ba.setEnabled(True)
            elif rc == 0:
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
                                    f"revisar el log; la cadena se corta aca. "
                                    f"{AYUDA_GIRO}")
                self.btn_ba.setEnabled(True)
            self.btn_capturar.setEnabled(True)
            self._set_campos(True)

    def _evaluar_cobertura(self):
        """M5: analiza el dataset recien capturado ANTES de ofrecer el BA."""
        ruta_abs = estado.RAIZ_CODIGO / self._dataset()
        veredicto, detalle, _m = ba_monitor.analizar_cobertura(ruta_abs)
        self.veredicto_cobertura = veredicto
        colores = {"VERDE": "#1e8e3e", "AMARILLO": "#e8a100", "ROJO": "#c5221f"}
        self.lbl_cobertura.setText(
            f"Cobertura: {veredicto}\n{detalle}")
        self.lbl_cobertura.setStyleSheet(
            f"color: {colores.get(veredicto, '#555')};")
        self.panel.log_msg(f"asistente: cobertura del dataset = {veredicto}")
        for ln in detalle.splitlines():
            self.panel.log_msg(f"  {ln}")
