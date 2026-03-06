# Proyecto Navegación

Sistema de navegación y tracking basado en OpenCV y ArUco.

---

## Requisitos

- Python 3.11.x (obligatorio)
- Git
- Sistema operativo: Windows, macOS o Linux

No se garantiza compatibilidad con Python 3.12+.

---

## Instalación desde cero

### 1. Clonar repositorio
git clone https://github.com/chuyAguilar/PoyectoNavegacion.git
cd PoyectoNavegacion

### 2. crear entorno virtual
python -m venv venv


### 3. Activar entorno

#### En Windows
 (Git Bash)
source venv/Scripts/activate
En Windows (PowerShell)
venv\Scripts\Activate.ps1

#### En macOS / Linux
source venv/bin/activate
Desactivar entorno

En cualquier sistema:

deactivate

### 4. Instalar proyecto
pip install -e ./project

Entorno de desarrollo (opcional)
Instalar dependencias de testing:
pip install -e ./project[dev]

Estructura del proyecto
PoyectoNavegacion/
│
├── historial/        # Código y pruebas históricas
├── project/          # Paquete instalable (navigation)
├── venv/             # Entorno virtual (no versionado)
├── README.md
└── .gitignore

camera/          → adquisición
calibration/     → intrínsecos
tracking/        → detección y pose
math3d/          → transformaciones 4x4
navigation/      → referencia espacial y roles
filters/         → suavizado
visualization/   → overlay
scripts/         → demos

---

## Integración con 3D Slicer (OpenIGTLink)

Este proyecto transmite datos de seguimiento en tiempo real desde un pipeline de seguimiento de ArUco en Python hacia 3D Slicer utilizando el protocolo OpenIGTLink.

El objetivo es visualizar las herramientas quirúrgicas rastreadas y los modelos anatómicos en 3D Slicer en tiempo real.

Resumen de la arquitectura:

Cámara
→ Detección de ArUco con OpenCV
→ Estimación de pose (rvec + tvec)
→ Clase Transform (matriz homogénea 4x4)
→ Emisor OpenIGTLink (pyigtl)
→ Módulo OpenIGTLinkIF de 3D Slicer
→ Nodo de transformación (Transform node) en Slicer
→ Modelos 3D (STL) asociados a la transformación

---

## Lado de Python

El proyecto envía transformaciones a Slicer utilizando la biblioteca:

`pyigtl`

Instalar la dependencia:

```bash
pip install pyigtl
```

El módulo de comunicación está implementado en:

`project/communication/igtl_sender.py`

Ejemplo de implementación:

* Crea un cliente de OpenIGTLink
* Se conecta a localhost por el puerto 18944
* Envía un `TransformMessage` con una matriz 4x4

La transformación (transform) proviene de la clase `Transform` del proyecto:

`project/navigation/transforms.py`

**Importante:**

La clase `Transform` devuelve una matriz homogénea 4x4 mediante:

`Transform.matrix()`

Esta matriz se envía directamente a Slicer.

---

## Ejecución de la Integración

Inicie Slicer primero.

Luego inicie el script de seguimiento en Python:

```bash
python -m project.scripts.demo_tracking_slicer
```

Cuando se detecta un marcador, la transformación se transmite continuamente.

---

## Configuración Requerida en 3D Slicer

Versión utilizada durante el desarrollo:

**3D Slicer 5.4.0**

Las versiones más recientes pueden requerir compatibilidad diferente con las extensiones.

Extensiones requeridas:

* SlicerIGT
* SlicerOpenIGTLink

Estas deben instalarse desde el Administrador de Extensiones (Extension Manager).

**Importante:**

Algunas versiones de Slicer no instalan automáticamente OpenIGTLinkIF junto con SlicerIGT.
Si el módulo OpenIGTLinkIF no aparece, instale la extensión SlicerOpenIGTLink de forma manual.

---

## Configuración del Servidor OpenIGTLink

Abra el módulo:

`Modules → OpenIGTLinkIF`

Cree un conector con la siguiente configuración:

* Type: Server
* Port: 18944
* Status: Active

Una vez que Python se conecte, el estado debería mostrar que la conexión está activa.

---

## Transmisión de Transformadas

Cuando el script de Python envía las transformaciones con:

`device_name = "Pointer"`

Slicer crea automáticamente un nodo de transformación:

`Pointer`

Este nodo se actualiza continuamente mientras el rastreador está en ejecución.

---

## Visualización de un Modelo de Herramienta

Para visualizar un instrumento rastreado:

1. Importe los modelos STL mediante:
   `File → Add Data`
2. Abra el módulo Transforms.
3. Seleccione el nodo de transformación:
   `Pointer`
4. En la sección "Apply transform", mueva el modelo (ej. "lezna") hacia la transformación del Pointer.

Resultado:

`model → Pointer`

El modelo STL ahora se moverá en tiempo real con el rastreador.

---

## Notas sobre los Sistemas de Coordenadas

OpenCV y 3D Slicer utilizan convenciones de coordenadas diferentes.

Marco de referencia de la cámara en OpenCV:
* X hacia la derecha
* Y hacia abajo
* Z hacia adelante

3D Slicer utiliza coordenadas RAS (Right, Anterior, Superior).

Por lo tanto, el modelo de la herramienta podría aparecer inicialmente rotado o desplazado.

Esto se corregirá más adelante utilizando transformaciones de calibración.

---

## Estado Actual

El pipeline de procesamiento (pipeline) actualmente soporta:

* Seguimiento en tiempo real de marcadores ArUco
* Transmisión de transformaciones a Slicer
* Movimiento en tiempo real de modelos STL en Slicer

El trabajo futuro incluye:

* Estabilización del marco de referencia
* Calibración de la herramienta
* Registro óseo (bone registration)
* Sistema de coordenadas de navegación