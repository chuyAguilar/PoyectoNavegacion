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
En Git Bash / macOS / Linux:
source venv/bin/activate
En PowerShell:
venv\Scripts\Activate.ps1

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