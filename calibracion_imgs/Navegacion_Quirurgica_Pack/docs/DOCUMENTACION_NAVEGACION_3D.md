# Navegacion 3D con OpenCV + ArUco
## Transformaciones, fusion multi-marcador, calibracion de rigid bodies, OpenIGTLink para 3D Slicer y pivot calibration
**Documento tecnico (Python + OpenCV). Fecha: 2025-12-12**

### 1. Objetivo y arquitectura general
Este documento describe, de forma completa y operativa, como construir un sistema de navegacion 3D basado en OpenCV y marcadores ArUco siguiendo la arquitectura 'Reference + Tool' (cuerpo fijo + herramienta). Incluye: matematicas de transformaciones, fusion robusta de multiples marcadores, calibracion del rigid body (por reproyeccion), integracion con 3D Slicer mediante OpenIGTLink, pivot calibration para estimar la punta de la herramienta, y un codigo de referencia en Python.

**Arquitectura recomendada:**
*   **Cam**: camara (sistema de coordenadas de la camara).
*   **Ref**: rigid body fijo al paciente/estructura (marcadores fijos).
*   **Tool**: rigid body montado en el instrumento (puntero/taladro/guia).
*   **CT (opcional)**: sistema del modelo/volumen (TAC/CT) en 3D Slicer.

En tiempo real se estima la pose de Ref y Tool en coordenadas de camara y luego se calcula la pose relativa Tool respecto a Ref. Si existe un registro CT<->Ref, entonces tambien se obtiene la pose de Tool en coordenadas CT.

### 2. Notacion y convenciones de transformacion
Usaremos matrices homogeneas 4x4 para describir transformaciones rigidas (rotacion + traslacion). La notacion `T_{A<-B}` significa: transforma un punto expresado en B hacia A.

**Matriz homogenea:**
```
T = [ R  t ]
    [ 0  1 ]
```
donde R es 3x3 y t es 3x1.

**Aplicacion a puntos (en coordenadas homogeneas):**
`p_A = T_{A<-B} * p_B`

**Convencion importante en OpenCV:** `solvePnP` / `estimatePoseSingleMarkers` devuelve `(rvec, tvec)` tal que (aprox.) `p_cam = R * p_obj + t`. Es decir, devuelve `T_{cam<-obj}`.

**Inversa de una transformacion rigida:**
Si `T = [ R  t ]` entonces `inv(T) = [ R^T  -R^T t ]`
       `[ 0  1 ]`               `[  0      1   ]`

### 3. Estimacion de pose con ArUco en OpenCV
OpenCV detecta marcadores ArUco devolviendo, para cada marcador detectado, sus 4 esquinas en pixeles. Con esas esquinas y el modelo geometrico 3D del marcador (un cuadrado de lado `marker_size`), se resuelve Perspective-n-Point (PnP) para obtener la pose del marcador respecto a la camara.

**Datos necesarios:**
*   Intrinsecos de camara `K` (matriz 3x3) y coeficientes de distorsion (`dist`).
*   Tamanio real del marcador (`marker_size`) en milimetros (o metros; pero consistente).
*   Diccionario ArUco (por ejemplo `DICT_4X4_50`, `DICT_5X5_100`, etc.).

**Modelo 3D tipico de las esquinas del marcador (origen en el centro):**
`objp = [(-s/2, +s/2, 0), (+s/2, +s/2, 0), (+s/2, -s/2, 0), (-s/2, -s/2, 0)]`

**Recomendacion:** para cuadrados planares suele funcionar bien `SOLVEPNP_IPPE_SQUARE` cuando esta disponible. Si no, `SOLVEPNP_ITERATIVE` es una opcion general.

#### 3.1 Error de reproyeccion (para calidad y outliers)
Para evaluar la calidad de cada pose estimada, se calcula el error de reproyeccion: se proyectan las esquinas 3D (`objp`) al plano imagen usando `(rvec,tvec,K,dist)` y se comparan con las esquinas observadas. Este error en pixeles permite descartar detecciones malas.
`err_px = RMS( ||u_obs - u_proj|| )`  (sobre las 4 esquinas)

### 4. Transformaciones completas para navegacion (Reference + Tool + CT)

#### 4.1 Transformacion relativa Tool respecto a Ref
En cada frame (imagen) se estima:
*   `T_{cam<-ref}`: pose del rigid body de referencia (Ref) en coordenadas de camara.
*   `T_{cam<-tool}`: pose del rigid body de herramienta (Tool) en coordenadas de camara.

La pose de Tool expresada en coordenadas de Ref se obtiene por:
`T_{ref<-tool} = inv(T_{cam<-ref}) * T_{cam<-tool}`

#### 4.2 Ejemplo numerico simple (sin rotacion)
Ejemplo para entender el significado (solo traslaciones, R = I):
`t_{cam<-ref}  = [100,  0, 0] mm`
`t_{cam<-tool} = [130, 20, 0] mm`
`=> t_{ref<-tool} = [30, 20, 0] mm`
Interpretacion: en el sistema de coordenadas de Ref, la herramienta esta 30 mm en X y 20 mm en Y respecto al reference.

#### 4.3 Llevar Tool a CT (overlay en 3D Slicer)
Si se realiza un registro CT<->Ref (por fiduciales, paired points, ICP, etc.), se obtiene `T_{CT<-ref}`. Entonces:
`T_{CT<-tool} = T_{CT<-ref} * T_{ref<-tool}`
Este `T_{CT<-tool}` es el que se envia a 3D Slicer para mostrar la herramienta sobre el volumen/modelo CT.

### 5. Fusion de multiples marcadores para un rigid body (robusto y sin jitter)
Cada marcador visible produce una estimacion de pose. Para un rigid body (por ejemplo, un dodecaedro con ArUco en varias caras), se fusionan todas las estimaciones visibles en el frame para obtener una sola pose estable.

#### 5.1 Modelo geometrico del rigid body
Para cada marcador `i` del rigid body se necesita conocer la transformacion fija `T_{body<-marker_i}` (marker_i en el cuerpo). Esta transformacion se obtiene del CAD/diseno o (mejor) de una calibracion por reproyeccion.
Con esto, cada marcador observado produce una estimacion del cuerpo:
`T_{cam<-body}^{(i)} = T_{cam<-marker_i} * inv(T_{body<-marker_i})`

#### 5.2 Rechazo de outliers por error de reproyeccion
Para cada marcador `i` se calcula `err_px`. Se descarta la medicion si:
`err_px > umbral` (por ejemplo 2.0 px a 1920x1080; ajustar segun camara/ruido)

#### 5.3 Fusion (traslacion + rotacion)
**Traslacion:** promedio ponderado (mas peso para menor error):
`w_i = 1 / (err_i^2 + eps)`
`t = (sum_i w_i * t_i) / (sum_i w_i)`

**Rotacion:** convertir cada `R_i` a cuaternion `q_i`, hacer consistencia de signo y promediar; luego normalizar:
`q = normalize( sum_i w_i * q_i )`

### 6. Calibracion del dodecaedro/rigid body por reproyeccion

#### 6.1 Por que es necesaria
Aunque el rigid body este disenado con dimensiones exactas, en la practica aparecen errores por impresion 3D, pegado de los marcadores, tolerancias mecanicas y pequenas deformaciones. Estos errores se traducen en sesgos (bias) en la pose estimada. La calibracion ajusta `T_{body<-marker_i}` a valores reales.

#### 6.2 Captura de datos
*   Calibra primero la camara con ChArUco (obtener K y dist).
*   Captura M imagenes del rigid body desde muchos angulos (idealmente 20-60).
*   En cada imagen, detecta marcadores y guarda: ID y corners (4 esquinas en pixeles).
*   Asegura que en la mayoria de imagenes se vean varias caras (varios marcadores).

#### 6.3 Formulacion (bundle adjustment / minimos cuadrados no lineales)
Variables desconocidas:
*   Para cada marcador `i`: `T_{body<-marker_i}` (6 DOF por marcador).
*   Para cada imagen `k`: `T_{cam<-body}^{(k)}` (6 DOF por imagen).

Prediccion de la pose de cada marcador visible:
`T_{cam<-marker_i}^{pred}(k) = T_{cam<-body}^{(k)} * T_{body<-marker_i}`

Funcion objetivo (suma de errores de reproyeccion de esquinas):
`min  Sum_k Sum_{i en vis(k)} Sum_{j=1..4} || u_obs(k,i,j) - u_pred(k,i,j) ||^2`

Implementacion recomendada: usar `scipy.optimize.least_squares`. Una practica comun es fijar un marcador como referencia (o fijar el centro del body) para eliminar grados de libertad globales.

#### 6.4 Validacion
*   Reporte el error RMS de reproyeccion antes y despues.
*   Observe estabilidad (jitter) de la pose fusionada en tiempo real.
*   Mida error sobre un setup con distancia/puntos conocidos (si es posible).

#### 6.5 Pseudocodigo de calibracion
```python
# Entrada:
# - detections[k] = lista de (id_i, corners_2d_4x2) para imagen k
# - K, dist
# - marker_size
# - estimacion inicial de T_body_marker[i] (del CAD) y T_cam_body[k] (por PnP con varios marcadores)

# Parametros a optimizar:
# - para cada marcador i: xi_i = [rx, ry, rz, tx, ty, tz]  (se(3))
# - para cada imagen k:   xk_k = [rx, ry, rz, tx, ty, tz]

def residuals(theta):
    # theta concatena todas las variables (marcadores + imagenes)
    res = []
    for k in imagenes:
        T_cam_body = se3_to_T(xk_k)
        for (id_i, corners_obs) in detections[k]:
            T_body_marker = se3_to_T(xi_i)
            T_cam_marker_pred = T_cam_body @ T_body_marker
            corners_pred = project_marker_corners(T_cam_marker_pred, K, dist, marker_size)
            res.append((corners_obs - corners_pred).ravel())
    return np.concatenate(res)

theta_opt = least_squares(residuals, theta0).x
```

### 7. Integracion con 3D Slicer mediante OpenIGTLink

#### 7.1 Configuracion en 3D Slicer (SlicerIGT)
*   Instalar extension 'SlicerIGT' (incluye OpenIGTLinkIF).
*   Abrir modulo 'OpenIGTLinkIF'.
*   Crear un conector (IGTLConnector): modo 'Server' o 'Client'.
*   Recomendacion: hacer que Slicer sea Server en puerto 18944, y Python se conecte como Client.
*   Crear/seleccionar un nodo de transformacion en Slicer (por ejemplo 'ToolToRef' o 'ToolToCT').
*   Asegurar que el mensaje TRANSFORM recibido se asigne a ese nodo (dependiendo del flujo del conector).

#### 7.2 Transformaciones recomendadas a transmitir
Hay dos opciones practicas:
*   Enviar `T_{ref<-tool}` (Tool respecto a Ref). En Slicer puedes encadenar con un nodo `T_{CT<-ref}` (registro) para obtener Tool en CT.
*   Enviar directamente `T_{CT<-tool}` si ya aplicas el registro en tu codigo.

En ambos casos, usa unidades coherentes (mm) y mantén consistencia de coordenadas. Si tu Ref esta definido por un registro con el CT, en la practica ya habras absorbido cualquier conversion de ejes necesaria.

#### 7.3 Envio desde Python
La forma mas sencilla es usar una libreria OpenIGTLink en Python (por ejemplo 'pyigtl' u otra compatible). Si no esta disponible, se puede implementar el protocolo, pero es mas extenso. En el codigo de referencia incluido mas adelante se deja una funcion `send_transform_openigtlink` con un camino rapido si hay libreria instalada.

**Convencion sugerida para nombres:**
*   `REF_TO_TOOL` (si envias `T_{ref<-tool}`)
*   `CT_TO_TOOL` (si envias `T_{CT<-tool}`)
*   `CAM_TO_REF` y `CAM_TO_TOOL` (solo si quieres depurar en Slicer)

### 8. Pivot calibration (calibracion de punta del instrumento)

#### 8.1 Objetivo
El rigid body del Tool (por ejemplo, un dodecaedro con ArUco) normalmente no coincide con la punta fisica del instrumento. Pivot calibration estima el vector fijo `p_tip_tool`: posicion de la punta expresada en coordenadas del Tool.

#### 8.2 Modelo matematico
Durante la pivot calibration se mantiene la punta fija en un punto (centro de pivote) mientras se rota el instrumento. Para cada frame k se tiene `T_{ref<-tool}^{(k)} = [R_k, t_k]`. Entonces:
`R_k * p_tip_tool + t_k = c_pivot_ref`

Reordenando:
```
[ R_k  -I ] [ p_tip_tool ] = -t_k
          [ c_pivot_ref ]
```
Se apilan N frames y se resuelve por minimos cuadrados (lstsq).

#### 8.3 Procedimiento recomendado de captura
*   Fijar la punta en un hueco/cono/fixture para que no se deslice.
*   Mover el mango rotando en multiples orientaciones (30-200 frames).
*   Descartar frames con pocas caras visibles o alto error de reproyeccion.
*   Resolver `p_tip_tool` y validar: al aplicar `p_tip_tool`, la punta en Ref debe quedar casi estacionaria.

### 9. Codigo de referencia (Python + OpenCV)

#### 9.1 Dependencias
*   opencv-contrib-python (incluye cv2.aruco)
*   numpy
*   Opcional: una libreria OpenIGTLink para Python (por ejemplo 'pyigtl')

#### 9.2 Archivos de configuracion sugeridos
Se recomienda definir los rigid bodies (Ref y Tool) en JSON para no recompilar codigo al ajustar offsets. Cada marcador debe tener `T_body_marker` (4x4) que transforma desde coordenadas del marcador al sistema del cuerpo.

### 10. Checklist practico para que funcione en el mundo real

#### 10.1 Optica e iluminacion
*   Usar buena iluminacion para permitir shutter rapido (reduce motion blur).
*   Evitar sobreexposicion y reflejos en marcadores.
*   Mantener el dodecaedro con suficientes caras visibles; evitar oclusion por manos/cables.

#### 10.2 Calibracion
*   Calibrar camara con ChArUco y verificar error RMS bajo.
*   Calibrar rigid body (offsets reales) por reproyeccion si buscas precision milimetrica.
*   Realizar pivot calibration para obtener la punta del puntero/instrumento.

#### 10.3 Validacion de precision
*   Medir repetibilidad: dejar Ref fijo y mover Tool lentamente; observar jitter (mm).
*   Medir exactitud: usar un phantom con puntos conocidos; comparar posiciones estimadas vs ground truth.
*   Registrar y graficar error vs numero de marcadores visibles (esperas menor error con mas marcadores).
