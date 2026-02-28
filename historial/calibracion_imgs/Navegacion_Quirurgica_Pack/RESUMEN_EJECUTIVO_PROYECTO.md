# Resumen Ejecutivo: Proyecto de Navegación Quirúrgica con ArUcos

Este documento proporciona una visión general completa del sistema de navegación desarrollado, detallando la función de cada archivo y los pasos para su implementación.

## 1. Propósito del Proyecto
El sistema permite el seguimiento en tiempo real de instrumentos quirúrgicos (lezna) mediante cámaras estéreo y marcadores ArUco, integrando los datos de posición con **3D Slicer** para navegación guiada por TAC.

---

## 2. Estructura de Archivos (Pack de Entrega)

### Directorio: `scripts/`
*   **`aruco_navegacion_relativa.py`**: El motor principal de navegación. Calcula la posición de la lezna respecto a la columna y envía los datos a 3D Slicer vía OpenIGTLink.
*   **`navegacion_dodecaedro.py`**: Versión avanzada de navegación diseñada para usar un dodecaedro (múltiples IDs) para mayor robustez en el seguimiento del instrumento.
*   **`calibracion_escala.py`**: Script para calibrar la relación entre píxeles y milímetros reales, asegurando que el movimiento en pantalla sea 1:1 con el real.
*   **`calibracion_stereo_adaptada.py`**: Utilidad para recalibrar las cámaras estéreo si se detectan errores en la profundidad.
*   **`ver_camara.py`**: Herramienta de diagnóstico para verificar que las cámaras estén funcionando y detectar IDs de ArUcos.

### Directorio: `docs/`
*   **`GUIA_CONFIGURACION_SLICER.md`**: Instrucciones paso a paso para configurar la escena en 3D Slicer.
*   **`GUIA_RAPIDA_DODECAEDRO.md`**: Cómo montar y configurar el rastreador tipo dodecaedro.
*   **`PROTOCOLO_CALIBRACION.md`**: Pasos detallados para obtener los mejores parámetros de cámara.
*   **`DOCUMENTACION_NAVEGACION_3D.md`**: Base teórica y técnica del sistema.

### Directorio: `config/`
*   **`parametros_calibracion_stereo.npz`**: Archivo maestro con los datos de distorsión y geometría de las cámaras.
*   **`tool_rigidbody.json`** y **`ref_rigidbody.json`**: Definiciones geométricas de los marcadores para el seguimiento preciso.

---

## 3. Guía de Inicio Rápido

1.  **Conexión**: Conectar las dos cámaras USB.
2.  **Slicer**: Abrir 3D Slicer, activar el servidor OpenIGTLink (Puerto 18944).
3.  **Ejecución**: Ejecutar `scripts/aruco_navegacion_relativa.py`.
4.  **Calibración**: Si el movimiento no es preciso, usar `scripts/calibracion_escala.py`.
5.  **Navegación**: Cargar el modelo de la columna y la lezna en Slicer y asignar las transformaciones según la guía en `docs/`.

---

## 4. Dependencias
El sistema requiere Python 3.x con las siguientes librerías:
*   `opencv-contrib-python` (incluye módulos de ArUco)
*   `numpy`
*   `pyigtl` (para la comunicación con 3D Slicer)
