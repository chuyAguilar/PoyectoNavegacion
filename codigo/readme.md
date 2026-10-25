# PoyectoNavegacion — Código

Sistema de navegación quirúrgica (tracking óptico con marcadores ArUco + visualización en 3D Slicer).
Esta guía explica, paso a paso, cómo dejar el entorno de Python listo para ejecutar el proyecto en **Windows**.

---

## 0. Requisitos previos

- Windows 10 / 11 (PowerShell).
- Conexión a internet.
- Git (recomendado, opcional).

> **Versión de Python del proyecto:** `3.11.9`
> Se fija en el archivo [`.python-version`](./.python-version). Si el equipo decide cambiarla,
> hay que actualizar ese archivo y volver a crear el entorno virtual.

---

## 1. Instalar pyenv-win

`pyenv-win` permite instalar y gestionar varias versiones de Python en el mismo equipo sin
interferir con la instalación del sistema. Es la forma recomendada de garantizar que todos
trabajemos con la **misma** versión de Python.

### 1.1. Instalación (PowerShell)

Abre **PowerShell** (no es necesario "como administrador").

> ⚠️ **Importante:** ejecuta los comandos **uno por uno** (Enter después de cada uno).
> NO pegues varias líneas juntas: el operador `&"./..."` y la URL larga suelen cortarse
> al pegar y el instalador falla.

**Paso 1 — permitir la ejecución de scripts** (solo la primera vez):

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Si pregunta, responde `S` (o `A`) y Enter.

**Paso 2 — descargar el instalador:**

```powershell
Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/pyenv-win/pyenv-win/master/pyenv-win/install-pyenv-win.ps1" -OutFile "./install-pyenv-win.ps1"
```

**Paso 3 — ejecutar el instalador** (usa `.\`, NO `&"./..."`):

```powershell
.\install-pyenv-win.ps1
```

> **Alternativa con git** (si el pegado de la URL se sigue cortando). Descarga pyenv-win
> directamente sin usar el script:
> ```powershell
> git clone https://github.com/pyenv-win/pyenv-win.git "$env:USERPROFILE\.pyenv"
> ```
> Luego cierra y reabre PowerShell y continúa en la sección 1.3.

### 1.2. Cerrar y reabrir la terminal

El instalador configura las variables de entorno (`PYENV`, `PYENV_ROOT`, `PATH`).
**Cierra todas las ventanas de PowerShell y abre una nueva** para que los cambios surtan efecto.

### 1.3. Verificar la instalación

```powershell
pyenv --version
```

Debe imprimir un número de versión (p. ej. `pyenv 3.x.x`). Si dice que el comando no se reconoce,
reinicia la terminal o el equipo y vuelve a probar.

---

## 2. Instalar la versión de Python del proyecto

```powershell
# Actualizar la lista de versiones disponibles
pyenv update

# Instalar la versión exacta del proyecto
pyenv install 3.11.9

# Comprobar que quedó instalada
pyenv versions
```

> Dentro de la carpeta `codigo\` ya existe (o se creará) el archivo `.python-version` con `3.11.9`,
> de modo que al entrar en la carpeta `pyenv` selecciona automáticamente esa versión.
> Para fijarla manualmente:
> ```powershell
> pyenv local 3.11.9
> ```

Verifica que Python responde con la versión correcta:

```powershell
python --version
# -> Python 3.11.9
```

---

## 3. Crear el entorno virtual (.venv)

El proyecto usa un entorno virtual en `codigo\.venv\`.

```powershell
# Situarse en la carpeta del código
cd C:\Dev\OrtoMeta\PoyectoNavegacion\codigo

# Crear el entorno virtual con la versión de Python seleccionada por pyenv
python -m venv .venv

# Activar el entorno
.\.venv\Scripts\activate
```

Una vez activado, el prompt mostrará `(.venv)` al principio de la línea.

> Para **desactivar** el entorno en cualquier momento:
> ```powershell
> deactivate
> ```

---

## 4. Instalar las dependencias

```powershell
# Con el entorno (.venv) activado:
python -m pip install --upgrade pip
pip install -r requirements.txt
```

> Si no existe `requirements.txt`, instala las dependencias principales del proyecto:
> ```powershell
 pip install opencv-python numpy scipy pyyaml pyigtl h5py
> ```
> y luego congela la lista para el resto del equipo:
> ```powershell
pip freeze > requirements.txt
> ```

---

## 5. Lista de comandos secuencial (resumen)

Copia y ejecuta en orden, en **PowerShell**:

> ⚠️ Ejecuta cada línea por separado (Enter tras cada una). No pegues bloques completos.

```powershell
# --- 1) Instalar pyenv-win (solo la primera vez) ---
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/pyenv-win/pyenv-win/master/pyenv-win/install-pyenv-win.ps1" -OutFile "./install-pyenv-win.ps1"
.\install-pyenv-win.ps1

# >>> CIERRA Y REABRE PowerShell antes de continuar <<<

# --- 2) Instalar la versión de Python del proyecto ---
pyenv --version
pyenv update
pyenv install 3.11.9
pyenv versions

# --- 3) Crear y activar el entorno virtual ---
cd C:\Dev\OrtoMeta\PoyectoNavegacion\codigo
pyenv local 3.11.9
python --version
python -m venv .venv
.\.venv\Scripts\activate

# --- 4) Instalar dependencias ---
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

## 6. Comandos habituales del proyecto

Desde la meta 003 (fase 3, ADR-027) el código vive en paquetes bajo `codigo\` y se lanza como
módulo, **siempre desde `codigo\`** y con los argumentos explícitos (principio 7):

| Carpeta | Qué hay |
|---|---|
| `tracker.py` | El bucle del tracker: cámara → detección y pose → envío por OpenIGTLink → ventana. |
| `camera\` | Backend de captura, identidad por el puerto USB y ajustes por DSHOW. |
| `vision\` | Detección ArUco, pose de un marker (IPPE_SQUARE), filtro 1-Euro y el paso por frame (`MarkerTracker`). |
| `transport\` | El servidor OpenIGTLink y el envío de transforms (`IgtlSender`). |
| `calibration\` | Calibración de la lente con tablero y comprobación de la escala con regla. |
| `diagnostics\` | Sondear la cámara, medir modos y enfocar, verificar IDs, grabar y resumir poses. |
| `gui\` | El panel de control (PySide6). |
| `profiles\` | Los perfiles de las cámaras (`tracker_config_gs1.yaml`, `tracker_config_gs2.yaml`). |
| `data\` | Los intrínsecos de cada cámara y el tablero de calibración. |
| `slicer\` | Los scripts para la consola Python de 3D Slicer. |
| `historico\` | Lo archivado (no se mantiene); `historico\iter4\README.md` dice qué es cada cosa. |

Las rutas que trae un perfil (`calibration_file: data/...`) son relativas a `codigo\`.

```powershell
# Activar el entorno (cada vez que abras una terminal nueva)
cd C:\Dev\OrtoMeta\PoyectoNavegacion\codigo
.\.venv\Scripts\activate

# Panel de control (lista los perfiles y lanza todo lo de abajo)
python -m gui.panel

# Tracker (Slicer conectado como cliente a localhost:18944 ANTES)
python -m tracker --config profiles\tracker_config_gs1.yaml

# Tracker sin ventana (más fps); sale con q + Enter o al cerrar la entrada (el panel: «Detener tracker»)
python -m tracker --config profiles\tracker_config_gs1.yaml --no-window --stop-stdin

# Verificar los IDs que ve la cámara (--timeout obligatorio, en segundos; q o la X para salir)
python -m diagnostics.identify_ids --config profiles\tracker_config_gs1.yaml --timeout 600

# Vista previa para colocar la cámara: imagen, cruz en el centro y fps de la cámara, sin detección
python -m diagnostics.identify_ids --config profiles\tracker_config_gs1.yaml --no-detect --timeout 600

# La suite de pruebas (sin cámara)
python -m pytest tests -q
```

La calibración de la lente, la escala y el enfoque se lanzan desde el panel («Calibrar cámara»),
que compone los comandos completos (`python -m calibration.calibrate_camera ...`,
`python -m calibration.check_scale ...`, `python -m diagnostics.measure_modes --enfocar ...`).

---

## 7. Problemas frecuentes

- **`pyenv` no se reconoce tras instalar:** reinicia la terminal (o el equipo); el instalador
  modifica el `PATH` y necesita una sesión nueva.
- **Error de ExecutionPolicy al lanzar el instalador:** ejecuta
  `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` y reintenta.
- **`.\.venv\Scripts\activate` bloqueado:** mismo caso de ExecutionPolicy; aplica el comando anterior.
- **La cámara baja a ~5 FPS:** revisa la configuración de cámara (backend MSMF + códec MJPG),
  ver `CLAUDE.md` y el skill `surgical-navigation-aruco`.
- **Versión de Python equivocada dentro de `.venv`:** borra la carpeta `.venv`, asegúrate de que
  `python --version` muestre `3.11.9` (con `pyenv local 3.11.9`) y vuelve a crear el entorno.

---

## 8. Recalibración de la cámara (MRPT `camera-calib`)

> **Histórico.** Desde la meta 002 la calibración se hace con el tablero desde el panel
> («Calibrar cámara») o con `python -m calibration.calibrate_camera`; esta sección queda como
> referencia de cómo se hizo con MRPT.

La calibración intrínseca de la cámara se hizo con **MRPT** (Mobile Robot Programming Toolkit),
con su aplicación gráfica **`camera-calib`**, usando un **tablero de ajedrez** normal (NO ChArUco).
El resultado quedó en `data/camera_calibration_caja_luz.yml` (RMSE ≈ 0.479 px).

> ⚠️ La calibración es **por setup de cámara**. Si mueves, reenfocas o cambias la cámara,
> hay que recalibrar y volver a generar el `.yml`.

### 8.1. Descargar MRPT (Windows)

El sitio oficial ya no publica instalador "stable" para Windows; el ejecutable se obtiene de los
**Windows nightly builds** en GitHub:

- https://github.com/MRPT/mrpt/releases/tag/Windows-nightly-builds

Descarga el `.exe` (incluye apps + DLLs), instálalo y abre la aplicación **`camera-calib`**
(aparece como "Camera Calibration" en la carpeta/menú de MRPT).

### 8.2. Tablero a usar

- Patrón del proyecto: `data/recursos/calibration_pattern_9x6_25mm.pdf` (tablero **9×6 casillas, 25 mm**).
- En MRPT se introduce el número de **esquinas interiores**, que para un tablero de 9×6 casillas
  es **8 × 5**, y el tamaño de celda **0.025 m (25 mm)**.
- Imprime el patrón a escala 100% (sin "ajustar a página") y pégalo a una superficie **plana y rígida**.

### 8.3. Procedimiento

1. Conecta la cámara y, dentro de la **caja de luz** (iluminación controlada), abre `camera-calib`.
2. Configura la resolución de captura a **1280×960** (igual que la calibración original; luego se
   escala a 640×480 para operar).
3. Parámetros del tablero en la GUI: **X = 8**, **Y = 5** esquinas interiores, **cell size = 0.025 m**.
4. Captura entre **15 y 30 vistas** del tablero variando posición, inclinación y distancia
   (centro, esquinas, cerca, lejos, inclinado). Asegúrate de que detecte bien todas las esquinas.
5. Ejecuta la optimización. **Verifica que el RMSE/error de reproyección sea < 1 px**
   (la referencia previa fue 0.479 px). Si es mayor, descarta las vistas peores y recaptura.
6. Exporta a formato **OpenCV YAML**.

### 8.4. Integrar el resultado en el proyecto

1. Guarda el `.yml` en `data\` (puedes sobrescribir `camera_calibration_caja_luz.yml`, o usar un
   nombre nuevo y actualizar la ruta).
2. Si usas un nombre nuevo, edita `tracker_config.yaml` → `camera.calibration_file:` para que apunte a él.
3. `tracker.py` espera las claves `camera_matrix` y `distortion_coefficients` (es el formato que
   exporta MRPT). Comprueba que `image_width`/`image_height` correspondan a la resolución calibrada.

> **Alternativa sin instalar MRPT:** como el proyecto ya usa OpenCV 4.13, también se puede hacer la
> calibración con un script propio (`cv2.findChessboardCorners` + `cv2.calibrateCamera`) usando el
> mismo tablero y exportando el mismo formato `.yml`. Pídelo si prefieres esta vía.
