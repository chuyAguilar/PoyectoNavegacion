# -*- coding: utf-8 -*-
"""
INYECTAR REGISTRO POR SUPERFICIE EN 3D SLICER  (iter 5)

Ejecutar en la CONSOLA PYTHON de 3D Slicer (Ctrl+3), NO en el venv.

Reemplaza el Fiducial Registration Wizard: como la nube TSDF (prueba 8) esta en
el frame del MARCADOR 0 y el registro (prueba 6) alinea el STL contra esa nube,
la transform resultante T_semilla ES directamente BoneToMarker0.

Solo hay que convertir la traslacion de metros a mm: nuestra captura uso el marcador
en metros (0.080), pero tracker.py lo define en mm (size_mm=80) con la MISMA
convencion de esquinas (TL,TR,BR,BL) + IPPE_SQUARE. La rotacion es identica; la
traslacion se escala x1000.

Requisitos ANTES de correr esto:
  1. tracker.py corriendo y enviando Marker0ToTracker (y DodecaedroToTracker).
  2. En Slicer: OpenIGTLinkIF conectado (client localhost:18944, Active) y que el
     nodo 'Marker0ToTracker' aparezca en Data.
  3. El marcador 0 debe seguir PEGADO al hueso en la misma posicion que cuando se
     hizo la captura TSDF (si lo despegaste/movuiste, hay que re-capturar y re-registrar).

EDITA las dos rutas de abajo y pega todo en la consola.
"""
import numpy as np
import vtk
import slicer

# ===================== EDITA ESTAS DOS RUTAS =====================
RUTA_T = None  # None = usar la T_semilla mas reciente de transforms/
RUTA_STL = r"C:\Dev\Dr.Milton\PoyectoNavegacion\stl\Segmentation_Bone_CT.stl"
DIR_TRANSFORMS = r"C:\Dev\Dr.Milton\PoyectoNavegacion\femto_pruebas\transforms"
# ================================================================

import glob, os
if RUTA_T is None:
    cands = sorted(glob.glob(os.path.join(DIR_TRANSFORMS, "T_semilla_*.npy")))
    if not cands:
        raise FileNotFoundError("No hay T_semilla_*.npy en transforms/. Corre la prueba 6 primero.")
    RUTA_T = cands[-1]
print("Usando transform:", RUTA_T)

# 1. Cargar T (STL_metros -> marcador0_metros) y pasar traslacion a mm
T = np.load(RUTA_T).astype(float)
T_mm = T.copy()
T_mm[:3, 3] *= 1000.0
# Slicer carga los STL convirtiendo LPS->RAS (voltea X e Y): Bone_polydata = F @ STL_crudo.
# Nuestra T se calculo sobre el STL CRUDO (como lo lee Open3D). Para que el Bone caiga
# en la posicion registrada hay que componer con F = diag(-1,-1,1,1) (F@F = I se cancela
# con el volteo de Slicer). Verificado por bounds: X,Y invertidos en el Bone de Slicer.
F = np.diag([-1.0, -1.0, 1.0, 1.0])
T_mm = T_mm @ F
print("=== BoneToMarker0 (mm, corregido LPS->RAS) ===")
print(np.array_str(T_mm, precision=3, suppress_small=True))

# 2. Crear / actualizar el nodo de transform BoneToMarker0
nodo = slicer.mrmlScene.GetFirstNodeByName('BoneToMarker0')
if nodo is None:
    nodo = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode', 'BoneToMarker0')
vm = vtk.vtkMatrix4x4()
for i in range(4):
    for j in range(4):
        vm.SetElement(i, j, float(T_mm[i, j]))
nodo.SetMatrixTransformToParent(vm)
print("BoneToMarker0 creado/actualizado.")

# 3. Cargar el STL del hueso si no esta cargado (nodo 'Bone')
bone = slicer.mrmlScene.GetFirstNodeByName('Bone')
if bone is None:
    bone = slicer.util.loadModel(RUTA_STL)
    bone.SetName('Bone')
    print(f"STL cargado: {RUTA_STL}")
else:
    print("Reuso nodo 'Bone' existente.")

# 4. Jerarquia:  Bone -> BoneToMarker0 -> Marker0ToTracker
marker0 = slicer.mrmlScene.GetFirstNodeByName('Marker0ToTracker')
if marker0 is None:
    print("AVISO: no existe 'Marker0ToTracker'. Conecta OpenIGTLink + tracker.py para "
          "que aparezca, y vuelve a ejecutar para anidar BoneToMarker0 bajo el.")
else:
    nodo.SetAndObserveTransformNodeID(marker0.GetID())
    print("BoneToMarker0 anidado bajo Marker0ToTracker.")
bone.SetAndObserveTransformNodeID(nodo.GetID())
print("Bone anidado bajo BoneToMarker0.")

# 5. Verificacion: jerarquia actual
print("\n=== Jerarquia ===")
for cls in ('vtkMRMLLinearTransformNode', 'vtkMRMLModelNode'):
    for i in range(slicer.mrmlScene.GetNumberOfNodesByClass(cls)):
        n = slicer.mrmlScene.GetNthNodeByClass(i, cls)
        nm = n.GetName()
        if nm in ('Red Volume Slice', 'Green Volume Slice', 'Yellow Volume Slice'):
            continue
        p = n.GetParentTransformNode()
        print(f"  {nm} -> {p.GetName() if p else 'ROOT'}")

print("\nListo. Mueve el marcador 0 (con el hueso): el STL 'Bone' debe seguirlo.")
print("Si el STL aparece desplazado o invertido, avisame: revisamos convencion/unidades.")
